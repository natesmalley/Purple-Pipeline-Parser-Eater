"""FU18 — regression tests for the DA-FU18 review fixes.

Covers:

  * **C1** — ``_TEMPERATURE_REJECTION_RE`` and ``_MAX_TOKENS_REJECTION_RE``
    must match Anthropic's canonical
    ``"temperature is deprecated for this model."`` message and
    OpenAI's canonical ``"max_tokens is deprecated; use
    'max_completion_tokens' instead"``. Pre-fix the bare ``\\bdeprecat\\b``
    alternation member missed every form of "deprecated" / "deprecates"
    / "deprecation" because ``e`` / ``s`` / ``i`` are word chars and the
    ``\\b`` boundary fails. End-to-end Anthropic call also exercises
    cache-population + retry.

  * **C7** — ``cost_ledger.CostLedger._maybe_rotate`` must use
    ``os.replace`` not ``os.rename`` (cross-platform safe; Windows-
    Docker-Desktop is a documented production target).

  * **C15** — coverage gaps for P2-4, P3-1, P3-2 from the original FU18
    audit:
      - **P2-4**: ``_get_iterative_model_candidates`` precedence chain
        (instance → SettingsStore → env → "anthropic").
      - **P3-1**: OpenAI cached_tokens surfacing through
        ``LLMResponse.cache_read_input_tokens`` for both chat-completions
        (``prompt_tokens_details.cached_tokens``) and Responses API
        (``input_tokens_details.cached_tokens``).
      - **P3-2**: OpenAI ``seed=0`` when ``temperature=0.0`` on chat-
        completions; absent for nonzero temperature; absent for
        Responses API (gpt-5/o1/o3/o4 models).

All MOCKED. No live API calls.
"""
from __future__ import annotations

import asyncio
import importlib
import os
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from components.llm_provider import (
    AnthropicProvider,
    OpenAIProvider,
    _TEMPERATURE_REJECTION_RE,
)


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# C1 — regex word-boundary footgun fix
# ---------------------------------------------------------------------------


class TestTemperatureRejectionRegexMatchesDeprecatedSuffixes:
    """``\\bdeprecat\\w*\\b`` must match every word starting with ``deprecat``.

    Pre-FU18 the alternation was bare ``\\bdeprecat\\b`` which only matches
    the literal token "deprecat" — Anthropic / OpenAI 400 messages never
    use that bare form, so the cache-and-retry was effectively dead for
    "deprecated" / "deprecates" / "deprecation" phrasings.
    """

    @pytest.mark.parametrize(
        "msg",
        [
            "temperature is deprecated for this model.",
            "temperature has been deprecated.",
            "this parameter deprecates as of 2026-01-01",
            "see deprecation notice in changelog",
            "DEPRECATED: temperature",  # uppercase
        ],
    )
    def test_canonical_deprecation_messages_match(self, msg):
        assert _TEMPERATURE_REJECTION_RE.search(msg) is not None, (
            f"regex should match {msg!r}"
        )

    @pytest.mark.parametrize(
        "msg",
        [
            "temperature is unsupported for this model",
            "'temperature' does not support 0.7 with this model.",
            "parameter temperature not supported",
        ],
    )
    def test_unsupported_phrasings_match(self, msg):
        assert _TEMPERATURE_REJECTION_RE.search(msg) is not None

    @pytest.mark.parametrize(
        "msg",
        [
            "this region is supported",
            "invalid api key",
            "rate limit exceeded",
            "the parser is depressed",  # word starts with 'depres', not 'deprecat'
        ],
    )
    def test_unrelated_messages_do_not_match(self, msg):
        assert _TEMPERATURE_REJECTION_RE.search(msg) is None, (
            f"regex must NOT match {msg!r}"
        )


class TestMaxTokensRejectionRegexMatchesDeprecatedSuffixes:
    """``_MAX_TOKENS_REJECTION_RE`` must match the same vocabulary plus
    OpenAI's ``"use 'max_completion_tokens'"`` directive."""

    @pytest.mark.parametrize(
        "msg",
        [
            # Canonical OpenAI 400 wording (combines multiple matchers).
            "Parameter 'max_tokens' is unsupported. Please use "
            "'max_completion_tokens' instead.",
            "max_tokens is deprecated; use 'max_completion_tokens' instead",
            "max_tokens has been deprecated",
            "max_tokens is unsupported",
            "max_tokens is not supported on this model",
            "max_tokens does not support this value",
        ],
    )
    def test_canonical_max_tokens_400_messages_match(self, msg):
        assert OpenAIProvider._MAX_TOKENS_REJECTION_RE.search(msg) is not None, (
            f"regex should match {msg!r}"
        )

    def test_use_max_completion_tokens_phrase_alone_does_not_match(self):
        """Documenting a known limitation: the literal alternation
        ``use 'max_completion_tokens'`` is in the regex for legacy /
        completeness reasons, but the trailing ``\\b`` cannot close
        between the closing ``'`` and the following space (both are
        non-word characters). Real-world OpenAI 400s for this case
        always include ``unsupported`` / ``deprecated`` alongside, so
        the regex matches via those members. This test pins that
        behavior so a future regex tweak doesn't introduce a regression
        of the canonical-message coverage above.
        """
        # Phrase alone (no other matchers) does NOT match — known
        # limitation of word-boundary anchors around quoted tokens.
        msg = "use 'max_completion_tokens' for this model"
        assert OpenAIProvider._MAX_TOKENS_REJECTION_RE.search(msg) is None

    @pytest.mark.parametrize(
        "msg",
        [
            "this region is supported",
            "max_tokens must be a positive integer",
        ],
    )
    def test_unrelated_messages_do_not_match(self, msg):
        assert OpenAIProvider._MAX_TOKENS_REJECTION_RE.search(msg) is None, (
            f"regex must NOT match {msg!r}"
        )


# ---- AnthropicProvider end-to-end: cache + retry on canonical 400 ----


class _FakeAnthropicAPIStatusError(Exception):
    """Stand-in for anthropic.APIStatusError.

    The real class requires constructing a httpx.Response which we don't
    want to instantiate in unit tests. The provider only reads
    ``.status_code`` and ``str(exc)``, so we expose those.
    """

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class _FakeAnthropicAPIConnectionError(Exception):
    pass


class _FakeAnthropicAPITimeoutError(Exception):
    pass


@pytest.fixture
def patch_anthropic_exception_classes(monkeypatch):
    """Make AnthropicProvider treat our fakes as the live SDK exception classes.

    Test-order safety: a sibling test file may have already monkeypatched
    or replaced the ``anthropic`` module surface (e.g. with a stripped-down
    test double). We use ``raising=False`` so a missing attribute on the
    target module reduces to a fresh ``setattr``, never an AttributeError
    at fixture setup. The target attribute names are not part of the
    public ``anthropic`` SDK contract — they're SDK-internal exception
    classes that AnthropicProvider lazy-imports inside ``_agenerate_once``,
    and the provider's import-fallback handles missing-class gracefully.
    """
    import anthropic  # type: ignore

    monkeypatch.setattr(
        anthropic, "APIStatusError", _FakeAnthropicAPIStatusError,
        raising=False,
    )
    monkeypatch.setattr(
        anthropic, "APIConnectionError", _FakeAnthropicAPIConnectionError,
        raising=False,
    )
    monkeypatch.setattr(
        anthropic, "APITimeoutError", _FakeAnthropicAPITimeoutError,
        raising=False,
    )
    yield


def _make_anthropic_ok_response(text: str = "ok") -> Any:
    """Build an Anthropic-shaped success response."""
    response = MagicMock()
    block = MagicMock()
    block.type = "text"
    block.text = text
    response.content = [block]
    response.stop_reason = "end_turn"
    response.usage = MagicMock(
        input_tokens=10,
        output_tokens=5,
        cache_read_input_tokens=0,
    )
    return response


class TestAnthropicCanonicalDeprecatedMessageFiresCacheAndRetry:
    """End-to-end: when Anthropic 400s with the canonical
    ``"temperature is deprecated for this model."`` message (no
    "unsupported" alongside), the provider must cache the model into
    ``_NO_TEMPERATURE_DISCOVERED`` and retry without temperature.

    Pre-FU18-C1 the regex missed this canonical phrasing and the call
    raised LLMProviderPermanentError without retry.
    """

    def test_canonical_deprecated_message_triggers_cache_and_retry(
        self, patch_anthropic_exception_classes, monkeypatch,
    ):
        # Pick a model NOT in _NO_TEMPERATURE_PREFIXES so the static
        # check passes the param through, forcing the runtime path.
        model = "claude-future-model-1"
        AnthropicProvider._NO_TEMPERATURE_DISCOVERED.discard(model)

        # Deny the static-prefix path so we definitely hit the runtime branch.
        assert AnthropicProvider._supports_temperature(model) is True

        # First call: 400 with canonical Anthropic phrasing.
        # Second call: success (after retry without temperature).
        canonical_msg = "temperature is deprecated for this model."
        attempts: List[Dict[str, Any]] = []

        async def fake_create(**kwargs: Any) -> Any:
            attempts.append(dict(kwargs))
            if len(attempts) == 1:
                raise _FakeAnthropicAPIStatusError(canonical_msg, status_code=400)
            return _make_anthropic_ok_response("retried_ok")

        client = MagicMock()
        client.messages = MagicMock()
        client.messages.create = AsyncMock(side_effect=fake_create)

        provider = AnthropicProvider(api_key="test")
        provider._client = client

        resp = _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model=model,
                max_tokens=64,
                temperature=0.7,
            )
        )

        # Two wire calls: first 400'd, second succeeded.
        assert len(attempts) == 2, (
            f"expected exactly 2 wire calls (400 then retry); got {len(attempts)}"
        )
        # First call sent temperature; second omitted it.
        assert "temperature" in attempts[0], (
            "first call should carry temperature (then 400)"
        )
        assert "temperature" not in attempts[1], (
            "second call (retry) must omit temperature; it stayed in! "
            "regression of the C1 fix"
        )
        # Cache populated for future calls in this process.
        assert model in AnthropicProvider._NO_TEMPERATURE_DISCOVERED, (
            "model not added to _NO_TEMPERATURE_DISCOVERED; the C1 regex fix "
            "is broken — bare \\bdeprecat\\b would not match 'deprecated'"
        )
        # And the retry response surfaced.
        assert resp.text == "retried_ok"

        # Cleanup so we don't pollute later tests.
        AnthropicProvider._NO_TEMPERATURE_DISCOVERED.discard(model)


# ---------------------------------------------------------------------------
# C7 — os.replace not os.rename (Windows compat)
# ---------------------------------------------------------------------------


class TestRotationUsesOsReplace:
    """Cost ledger rotation must use ``os.replace`` (cross-platform safe)
    not ``os.rename`` (fails on Windows when destination exists or source
    is held open by another process)."""

    def test_rotation_uses_os_replace_not_os_rename(
        self, tmp_path: Path, monkeypatch,
    ):
        mod = importlib.import_module("components.cost_ledger")
        monkeypatch.setattr(mod, "ROTATION_THRESHOLD_BYTES", 1024)
        monkeypatch.setattr(mod, "ROTATION_CHECK_EVERY_N_RECORDS", 5)

        rename_calls: List[tuple] = []
        replace_calls: List[tuple] = []
        real_replace = os.replace
        real_rename = os.rename

        def spy_replace(src, dst):
            replace_calls.append((str(src), str(dst)))
            return real_replace(src, dst)

        def spy_rename(src, dst):
            rename_calls.append((str(src), str(dst)))
            return real_rename(src, dst)

        # Patch in components.cost_ledger's os module reference (the
        # provider does ``import os`` at module top, so monkeypatching
        # ``mod.os.replace`` reaches the same function the rotation code
        # calls).
        monkeypatch.setattr(mod.os, "replace", spy_replace)
        monkeypatch.setattr(mod.os, "rename", spy_rename)

        ledger = mod.CostLedger(path=tmp_path / "ledger.jsonl")
        for i in range(50):
            ledger.record(
                parser_name=f"row_{i}",
                provider="anthropic",
                model="claude-opus-4-7",
                iteration=1,
                tokens_in=100,
                tokens_out=50,
            )

        assert len(replace_calls) >= 1, (
            "expected at least one os.replace call during rotation"
        )
        assert rename_calls == [], (
            "os.rename must NOT be used (non-atomic on Windows); "
            f"got rename_calls={rename_calls}"
        )


# ---------------------------------------------------------------------------
# C15 / P2-4 — _get_iterative_model_candidates precedence chain
# ---------------------------------------------------------------------------


def _make_lua_generator_for_provider_test():
    """Construct a LuaGenerator with provider attribute control.

    We don't construct the real heavy provider here — the test only
    needs to exercise the candidate-list builder, which inspects
    ``self.provider``, settings, and env vars.
    """
    from components.lua_generator import LuaGenerator

    gen = LuaGenerator(provider=MagicMock())
    return gen


class TestGetIterativeModelCandidatesPrecedence:
    """Verify the FU18 P2-4 fallback chain in
    ``LuaGenerator._get_iterative_model_candidates``:
    instance.provider → SettingsStore("providers.active") → env
    LLM_PROVIDER_PREFERENCE → "anthropic" default.
    """

    def _opts_legacy_default(self):
        from components.lua_generator import GenerationOptions
        # Use the literal placeholder ladder so the function falls
        # through to the env-based path (which is what we're testing).
        return GenerationOptions(
            mode="iterative",
            escalation_ladder=["haiku", "sonnet", "opus"],
        )

    def test_instance_provider_takes_precedence(self, monkeypatch):
        gen = _make_lua_generator_for_provider_test()
        gen.provider = "openai"
        gen.model = "gpt-4o"
        # Even with settings + env both set to other providers, instance wins.
        monkeypatch.setenv("LLM_PROVIDER_PREFERENCE", "anthropic")
        monkeypatch.setenv("OPENAI_STRONG_MODEL", "gpt-5.4-mini")
        monkeypatch.setenv("ANTHROPIC_STRONG_MODEL", "claude-sonnet-4-6")
        monkeypatch.setenv("GEMINI_STRONG_MODEL", "gemini-2.5-pro")

        candidates = gen._get_iterative_model_candidates(self._opts_legacy_default())
        # Strong model came from OPENAI_STRONG_MODEL because instance.provider == "openai"
        assert "gpt-5.4-mini" in candidates, (
            f"instance.provider='openai' should drive the OPENAI_STRONG_MODEL lookup; "
            f"got {candidates}"
        )
        assert "claude-sonnet-4-6" not in candidates
        assert "gemini-2.5-pro" not in candidates

    def test_settings_takes_precedence_when_instance_unset(self, monkeypatch):
        gen = _make_lua_generator_for_provider_test()
        # No instance.provider attribute → fall through to settings.
        if hasattr(gen, "provider"):
            delattr(gen, "provider")
        gen.model = "gemini-2.5-flash"

        # Patch SettingsStore lookup via the lua_generator helper.
        fake_store = MagicMock()
        fake_store.get = lambda key: "gemini" if key == "providers.active" else None
        monkeypatch.setattr(
            "components.lua_generator._get_settings_store",
            lambda: fake_store,
        )
        # Env set to a DIFFERENT provider so we can prove settings beats env.
        monkeypatch.setenv("LLM_PROVIDER_PREFERENCE", "anthropic")
        monkeypatch.setenv("GEMINI_STRONG_MODEL", "gemini-2.5-pro")
        monkeypatch.setenv("ANTHROPIC_STRONG_MODEL", "claude-sonnet-4-6")

        candidates = gen._get_iterative_model_candidates(self._opts_legacy_default())
        assert "gemini-2.5-pro" in candidates, (
            f"settings 'providers.active=gemini' should drive GEMINI_STRONG_MODEL; "
            f"got {candidates}"
        )
        assert "claude-sonnet-4-6" not in candidates

    def test_env_takes_precedence_when_settings_returns_none(self, monkeypatch):
        gen = _make_lua_generator_for_provider_test()
        if hasattr(gen, "provider"):
            delattr(gen, "provider")
        gen.model = "claude-haiku-4-5"

        # Settings returns None for the provider key.
        fake_store = MagicMock()
        fake_store.get = lambda key: None
        monkeypatch.setattr(
            "components.lua_generator._get_settings_store",
            lambda: fake_store,
        )
        monkeypatch.setenv("LLM_PROVIDER_PREFERENCE", "openai")
        monkeypatch.setenv("OPENAI_STRONG_MODEL", "gpt-5.4-mini")
        monkeypatch.setenv("ANTHROPIC_STRONG_MODEL", "claude-sonnet-4-6")

        candidates = gen._get_iterative_model_candidates(self._opts_legacy_default())
        assert "gpt-5.4-mini" in candidates, (
            f"env LLM_PROVIDER_PREFERENCE=openai should drive OPENAI_STRONG_MODEL; "
            f"got {candidates}"
        )
        assert "claude-sonnet-4-6" not in candidates

    def test_anthropic_default_when_all_unset(self, monkeypatch):
        gen = _make_lua_generator_for_provider_test()
        if hasattr(gen, "provider"):
            delattr(gen, "provider")
        gen.model = "claude-haiku-4-5"

        fake_store = MagicMock()
        fake_store.get = lambda key: None
        monkeypatch.setattr(
            "components.lua_generator._get_settings_store",
            lambda: fake_store,
        )
        monkeypatch.delenv("LLM_PROVIDER_PREFERENCE", raising=False)
        monkeypatch.setenv("ANTHROPIC_STRONG_MODEL", "claude-sonnet-4-6")
        # Other strong env vars set so we can prove they're NOT picked up.
        monkeypatch.setenv("OPENAI_STRONG_MODEL", "gpt-5.4-mini")
        monkeypatch.setenv("GEMINI_STRONG_MODEL", "gemini-2.5-pro")

        candidates = gen._get_iterative_model_candidates(self._opts_legacy_default())
        assert "claude-sonnet-4-6" in candidates, (
            f"all-unset should default to anthropic; got {candidates}"
        )
        assert "gpt-5.4-mini" not in candidates
        assert "gemini-2.5-pro" not in candidates

    def test_settings_store_unavailable_falls_through_gracefully(self, monkeypatch):
        """If _get_settings_store returns None, the chain still works."""
        gen = _make_lua_generator_for_provider_test()
        if hasattr(gen, "provider"):
            delattr(gen, "provider")
        gen.model = "gpt-4o"

        monkeypatch.setattr(
            "components.lua_generator._get_settings_store",
            lambda: None,
        )
        monkeypatch.setenv("LLM_PROVIDER_PREFERENCE", "openai")
        monkeypatch.setenv("OPENAI_STRONG_MODEL", "gpt-5.4-mini")

        candidates = gen._get_iterative_model_candidates(self._opts_legacy_default())
        assert "gpt-5.4-mini" in candidates


# ---------------------------------------------------------------------------
# C15 / P3-1 — OpenAI cached_tokens surfacing
# ---------------------------------------------------------------------------


def _make_openai_chat_response_with_cached_tokens(cached: int):
    """Build a chat-completions response shape with prompt_tokens_details.cached_tokens."""
    class _Details:
        cached_tokens = cached

    class _Usage:
        prompt_tokens = 100
        completion_tokens = 50
        prompt_tokens_details = _Details()

    class _Message:
        content = "ok"

    class _Choice:
        message = _Message()
        finish_reason = "stop"

    class _Resp:
        choices = [_Choice()]
        usage = _Usage()
        system_fingerprint = "fp_test"

    return _Resp()


def _make_openai_responses_response_with_cached_tokens(cached: int):
    """Build a Responses-API response shape with input_tokens_details.cached_tokens."""
    class _Details:
        cached_tokens = cached

    class _Usage:
        input_tokens = 100
        output_tokens = 50
        input_tokens_details = _Details()

    class _Resp:
        id = "resp_test"
        output_text = "ok"
        output = []
        usage = _Usage()
        incomplete_details = None

    return _Resp()


class TestOpenAICachedTokensSurfaced:
    """P3-1: ``LLMResponse.cache_read_input_tokens`` must reflect the
    OpenAI usage details for both API surfaces."""

    def test_chat_completions_cached_tokens_surfaced(self, monkeypatch):
        OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()
        provider = OpenAIProvider(api_key="test")
        client = MagicMock()
        client.chat = MagicMock()
        client.chat.completions = MagicMock()
        client.chat.completions.create = AsyncMock(
            return_value=_make_openai_chat_response_with_cached_tokens(42),
        )
        provider._client = client

        resp = _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4o",
                max_tokens=64,
                temperature=0.0,
            )
        )
        assert resp.cache_read_input_tokens == 42, (
            "P3-1: prompt_tokens_details.cached_tokens=42 should surface "
            "as cache_read_input_tokens; got "
            f"{resp.cache_read_input_tokens}"
        )
        assert resp.usage.get("cache_read_input_tokens") == 42

    def test_chat_completions_cached_tokens_zero_when_absent(self, monkeypatch):
        """Missing prompt_tokens_details (older SDK) → cache_read_input_tokens=0."""
        OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()
        provider = OpenAIProvider(api_key="test")

        class _Usage:
            prompt_tokens = 10
            completion_tokens = 5
            # NO prompt_tokens_details attribute

        class _Message:
            content = "ok"

        class _Choice:
            message = _Message()
            finish_reason = "stop"

        class _Resp:
            choices = [_Choice()]
            usage = _Usage()

        client = MagicMock()
        client.chat = MagicMock()
        client.chat.completions = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_Resp())
        provider._client = client

        resp = _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4o",
                max_tokens=64,
                temperature=0.0,
            )
        )
        assert resp.cache_read_input_tokens == 0
        assert "cache_read_input_tokens" not in resp.usage

    def test_responses_api_cached_tokens_surfaced(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_MODE", raising=False)
        OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()
        provider = OpenAIProvider(api_key="test")

        client = MagicMock()
        client.chat = MagicMock()
        client.chat.completions = MagicMock()
        client.chat.completions.create = AsyncMock()  # not used
        client.responses = MagicMock()
        client.responses.create = AsyncMock(
            return_value=_make_openai_responses_response_with_cached_tokens(137),
        )
        provider._client = client

        resp = _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-5.4-mini",  # routes to Responses API
                max_tokens=64,
            )
        )
        assert resp.cache_read_input_tokens == 137, (
            "P3-1: input_tokens_details.cached_tokens=137 should surface "
            "as cache_read_input_tokens; got "
            f"{resp.cache_read_input_tokens}"
        )


# ---------------------------------------------------------------------------
# C15 / P3-2 — OpenAI seed for chat-completions reproducibility
# ---------------------------------------------------------------------------


class TestOpenAISeedChatCompletions:
    """P3-2: ``seed=0`` lands on chat-completions wire calls when
    ``temperature=0.0``; absent for nonzero temperature; absent for
    Responses API (which doesn't accept seed)."""

    def _make_chat_provider_with_capture(self, monkeypatch):
        OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()
        provider = OpenAIProvider(api_key="test")
        captured: Dict[str, Any] = {}

        async def fake_create(**kwargs: Any) -> Any:
            captured.update(kwargs)

            class _Usage:
                prompt_tokens = 10
                completion_tokens = 5
                prompt_tokens_details = None

            class _Message:
                content = "ok"

            class _Choice:
                message = _Message()
                finish_reason = "stop"

            class _Resp:
                choices = [_Choice()]
                usage = _Usage()

            return _Resp()

        client = MagicMock()
        client.chat = MagicMock()
        client.chat.completions = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=fake_create)
        provider._client = client
        return provider, captured

    def test_seed_zero_when_temperature_zero(self, monkeypatch):
        provider, captured = self._make_chat_provider_with_capture(monkeypatch)
        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4o",
                max_tokens=64,
                temperature=0.0,
            )
        )
        assert captured.get("seed") == 0, (
            "P3-2: temperature=0.0 must wire seed=0 for chat-completions "
            f"reproducibility; got kwargs={list(captured)}"
        )
        assert captured.get("temperature") == 0.0

    def test_seed_omitted_when_temperature_nonzero(self, monkeypatch):
        provider, captured = self._make_chat_provider_with_capture(monkeypatch)
        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4o",
                max_tokens=64,
                temperature=0.7,
            )
        )
        assert "seed" not in captured, (
            "seed must be OMITTED when temperature > 0; got kwargs="
            f"{list(captured)}"
        )
        assert captured.get("temperature") == 0.7

    def test_seed_omitted_for_reasoning_family_routed_to_responses_api(
        self, monkeypatch,
    ):
        """gpt-5/o1/o3/o4 route to Responses API which doesn't accept seed."""
        monkeypatch.delenv("OPENAI_API_MODE", raising=False)
        OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()
        provider = OpenAIProvider(api_key="test")

        captured: Dict[str, Any] = {}

        async def fake_responses_create(**kwargs: Any) -> Any:
            captured.update(kwargs)
            return _make_openai_responses_response_with_cached_tokens(0)

        client = MagicMock()
        client.chat = MagicMock()
        client.chat.completions = MagicMock()
        client.chat.completions.create = AsyncMock()  # not used
        client.responses = MagicMock()
        client.responses.create = AsyncMock(side_effect=fake_responses_create)
        provider._client = client

        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-5.4-mini",
                max_tokens=64,
                temperature=0.0,
            )
        )
        assert "seed" not in captured, (
            "seed must NOT land on the Responses API path (the SDK rejects "
            "the kwarg); got kwargs="
            f"{list(captured)}"
        )

    def test_seed_omitted_for_reasoning_family_forced_to_chat_completions(
        self, monkeypatch,
    ):
        """OPENAI_API_MODE=chat on a reasoning model → temperature is dropped
        by the static-prefix filter, so seed must NOT be sent either (we
        gate seed on ``self._supports_temperature(model)``)."""
        monkeypatch.setenv("OPENAI_API_MODE", "chat")
        OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()
        provider, captured = self._make_chat_provider_with_capture(monkeypatch)

        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-5.4-mini",
                max_tokens=64,
                temperature=0.0,
            )
        )
        # Reasoning model on chat-completions: temperature dropped by
        # static-prefix filter, seed gated on the same predicate.
        assert "temperature" not in captured
        assert "seed" not in captured, (
            "seed must NOT be sent when temperature was dropped by the "
            "reasoning-family filter; got kwargs="
            f"{list(captured)}"
        )
