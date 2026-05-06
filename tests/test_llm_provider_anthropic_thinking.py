"""FU13 — Anthropic extended thinking (adaptive-only, omit temperature).

Two concerns exercised here, all mocked (no live API calls):

  P1-1  AnthropicProvider must add ``thinking={"type": "adaptive"}`` to the
        ``client.messages.create`` kwargs for adaptive-thinking-capable models
        (``claude-opus-4-7``, ``claude-sonnet-4-6``). When thinking is
        enabled, ``temperature`` must NOT be present in the kwargs — Anthropic
        rejects requests that combine the two as incompatible.

        Per Anthropic's adaptive-thinking docs, opus-4-7 ONLY accepts the
        ``adaptive`` form (``{"type": "enabled", "budget_tokens": N}`` 400s).
        We do NOT supply ``budget_tokens`` and we do NOT partition
        ``max_tokens``: the model self-allocates within its overall response
        budget.

  DA    DA-Architecture FU10 follow-up: ``LLMResponse.thinking_tokens`` is
        ``Optional[int]`` with default ``None`` (was ``int = 0``). ``None``
        unambiguously means "we don't know" — the previous default of ``0``
        was a footgun for cost telemetry (silent under-count).

Mocking strategy: tests inject a fake AsyncAnthropic-shaped client at
``provider._client`` so ``_ensure_client()`` short-circuits without importing
the real SDK. The fake's ``messages.create`` is an ``AsyncMock`` whose
``call_args.kwargs`` we read back to assert which params landed on the wire.
This mirrors the FU11 pattern from test_llm_provider_openai_p0.py.

No live API calls. We do NOT assert ``thinking_tokens > 0`` after a call —
the Anthropic SDK does not reliably expose ``response.usage.thinking_tokens``
across versions, so FU13 does not populate the field.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from components.llm_provider import (
    AnthropicProvider,
    LLMResponse,
)


# ---------------------------------------------------------------------------
# Fake response helpers
# ---------------------------------------------------------------------------


class _FakeUsage:
    input_tokens = 10
    output_tokens = 5
    cache_read_input_tokens = 0


class _FakeBlock:
    type = "text"
    text = "ok"


class _FakeResponse:
    content = [_FakeBlock()]
    usage = _FakeUsage()
    stop_reason = "end_turn"


def _make_fake_client(create_mock: AsyncMock) -> MagicMock:
    """Build a MagicMock shaped like AsyncAnthropic with a custom ``create``."""
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = create_mock
    return client


def _ok_create_mock() -> AsyncMock:
    """AsyncMock whose every call returns a benign FakeResponse."""
    return AsyncMock(return_value=_FakeResponse())


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# P1-1 — thinking={"type": "adaptive"} added for adaptive-capable models
# ---------------------------------------------------------------------------


class TestThinkingAdaptiveAddedForCapableModels:
    """``thinking={"type": "adaptive"}`` must land on the wire for
    claude-opus-4-7 and claude-sonnet-4-6.
    """

    def test_thinking_adaptive_added_for_opus_47(self):
        # Reset runtime-discovery cache so it doesn't bleed in either way.
        AnthropicProvider._NO_TEMPERATURE_DISCOVERED.clear()

        create = _ok_create_mock()
        provider = AnthropicProvider(api_key="test")
        provider._client = _make_fake_client(create)

        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="claude-opus-4-7",
                max_tokens=4096,
                temperature=0.0,
            )
        )

        kwargs = create.call_args.kwargs
        assert kwargs.get("thinking") == {"type": "adaptive"}, (
            f"thinking=adaptive must be sent for claude-opus-4-7; "
            f"got kwargs={list(kwargs)}"
        )
        # No budget_tokens — the model self-allocates.
        assert "budget_tokens" not in kwargs.get("thinking", {})

    def test_thinking_adaptive_added_for_sonnet_46(self):
        AnthropicProvider._NO_TEMPERATURE_DISCOVERED.clear()

        create = _ok_create_mock()
        provider = AnthropicProvider(api_key="test")
        provider._client = _make_fake_client(create)

        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="claude-sonnet-4-6",
                max_tokens=4096,
                temperature=0.0,
            )
        )

        kwargs = create.call_args.kwargs
        assert kwargs.get("thinking") == {"type": "adaptive"}, (
            f"thinking=adaptive must be sent for claude-sonnet-4-6; "
            f"got kwargs={list(kwargs)}"
        )

    def test_thinking_skipped_for_haiku(self):
        """Haiku is not in _THINKING_CAPABLE_PREFIXES — no thinking key."""
        AnthropicProvider._NO_TEMPERATURE_DISCOVERED.clear()

        create = _ok_create_mock()
        provider = AnthropicProvider(api_key="test")
        provider._client = _make_fake_client(create)

        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                temperature=0.0,
            )
        )

        kwargs = create.call_args.kwargs
        assert "thinking" not in kwargs, (
            f"thinking must NOT be sent for haiku; got kwargs={list(kwargs)}"
        )
        # And temperature stays put because haiku accepts it.
        assert kwargs.get("temperature") == 0.0


# ---------------------------------------------------------------------------
# Settings-store gating — extended_thinking=False disables the wire-through
# ---------------------------------------------------------------------------


class TestThinkingDisabledViaSetting:
    """``providers.anthropic.extended_thinking=False`` must skip thinking
    even on adaptive-capable models, and must restore default-True semantics
    when the setting is unset (None)."""

    def test_thinking_disabled_when_setting_false(self, monkeypatch):
        AnthropicProvider._NO_TEMPERATURE_DISCOVERED.clear()

        # Patch the module-level _settings_get so it reports False for the
        # extended_thinking path (and None for everything else).
        from components import llm_provider as mod

        def fake_settings_get(path: str):
            if path == "providers.anthropic.extended_thinking":
                return False
            return None

        monkeypatch.setattr(mod, "_settings_get", fake_settings_get)

        create = _ok_create_mock()
        provider = AnthropicProvider(api_key="test")
        provider._client = _make_fake_client(create)

        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="claude-opus-4-7",
                max_tokens=4096,
                temperature=0.0,
            )
        )

        kwargs = create.call_args.kwargs
        assert "thinking" not in kwargs, (
            "extended_thinking=False must skip the thinking param; "
            f"got kwargs={list(kwargs)}"
        )

    def test_thinking_settings_default_true_when_unset(self, monkeypatch):
        """When _settings_get returns None for the path, the default is True
        (matches settings_store.py:100 default)."""
        AnthropicProvider._NO_TEMPERATURE_DISCOVERED.clear()

        from components import llm_provider as mod

        def fake_settings_get(path: str):
            return None  # nothing configured

        monkeypatch.setattr(mod, "_settings_get", fake_settings_get)

        create = _ok_create_mock()
        provider = AnthropicProvider(api_key="test")
        provider._client = _make_fake_client(create)

        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="claude-opus-4-7",
                max_tokens=4096,
                temperature=0.0,
            )
        )

        kwargs = create.call_args.kwargs
        assert kwargs.get("thinking") == {"type": "adaptive"}, (
            "settings None should default to True; thinking missing "
            f"in kwargs={list(kwargs)}"
        )


# ---------------------------------------------------------------------------
# Temperature is popped when thinking is enabled
# ---------------------------------------------------------------------------


class TestTemperaturePopWhenThinkingEnabled:
    """Anthropic rejects ``thinking`` + ``temperature`` together. The provider
    must pop ``temperature`` whenever it adds the thinking param."""

    def test_temperature_omitted_when_thinking_enabled_for_sonnet_46(self):
        """Sonnet-4-6 normally accepts temperature (not in
        _NO_TEMPERATURE_PREFIXES). With thinking enabled, kwargs must NOT
        contain temperature anyway because Anthropic rejects the combo."""
        AnthropicProvider._NO_TEMPERATURE_DISCOVERED.clear()

        create = _ok_create_mock()
        provider = AnthropicProvider(api_key="test")
        provider._client = _make_fake_client(create)

        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="claude-sonnet-4-6",
                max_tokens=4096,
                temperature=0.7,
            )
        )

        kwargs = create.call_args.kwargs
        # Thinking landed.
        assert kwargs.get("thinking") == {"type": "adaptive"}
        # Temperature was popped.
        assert "temperature" not in kwargs, (
            "temperature must be omitted when thinking is enabled; "
            f"got kwargs={list(kwargs)}"
        )

    def test_temperature_still_omitted_for_opus_47_with_thinking(self):
        """Opus-4-7 already omits temperature (FU0 fix via
        _NO_TEMPERATURE_PREFIXES). Thinking enabled must not change that
        — kwargs still has no temperature."""
        AnthropicProvider._NO_TEMPERATURE_DISCOVERED.clear()

        create = _ok_create_mock()
        provider = AnthropicProvider(api_key="test")
        provider._client = _make_fake_client(create)

        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="claude-opus-4-7",
                max_tokens=4096,
                temperature=0.0,
            )
        )

        kwargs = create.call_args.kwargs
        assert kwargs.get("thinking") == {"type": "adaptive"}
        assert "temperature" not in kwargs

    def test_temperature_still_omitted_for_opus_47_without_thinking(
        self, monkeypatch
    ):
        """Opus-4-7 with extended_thinking=False: still no temperature, no
        thinking — both omissions are independent."""
        AnthropicProvider._NO_TEMPERATURE_DISCOVERED.clear()

        from components import llm_provider as mod

        def fake_settings_get(path: str):
            if path == "providers.anthropic.extended_thinking":
                return False
            return None

        monkeypatch.setattr(mod, "_settings_get", fake_settings_get)

        create = _ok_create_mock()
        provider = AnthropicProvider(api_key="test")
        provider._client = _make_fake_client(create)

        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="claude-opus-4-7",
                max_tokens=4096,
                temperature=0.0,
            )
        )

        kwargs = create.call_args.kwargs
        assert "thinking" not in kwargs
        # FU0 behavior preserved: opus-4-7 never gets temperature.
        assert "temperature" not in kwargs


# ---------------------------------------------------------------------------
# Wire-payload smoke — exact kwargs the SDK sees
# ---------------------------------------------------------------------------


class TestWirePayload:
    """Capture the exact kwargs handed to ``client.messages.create`` and
    verify both the thinking shape and the temperature absence."""

    def test_wire_payload_for_opus_47_carries_adaptive_and_no_temperature(self):
        AnthropicProvider._NO_TEMPERATURE_DISCOVERED.clear()

        create = _ok_create_mock()
        provider = AnthropicProvider(api_key="test")
        provider._client = _make_fake_client(create)

        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="claude-opus-4-7",
                max_tokens=4096,
                temperature=0.0,
            )
        )

        # Exactly one wire call.
        assert create.call_count == 1
        kwargs = create.call_args.kwargs
        # Required: adaptive thinking shape, exactly.
        assert kwargs.get("thinking") == {"type": "adaptive"}
        # Forbidden: temperature.
        assert "temperature" not in kwargs
        # Sanity: model + messages still passed through.
        assert kwargs.get("model") == "claude-opus-4-7"
        assert kwargs.get("max_tokens") == 4096
        assert kwargs.get("messages") == [{"role": "user", "content": "hi"}]


# ---------------------------------------------------------------------------
# Predicate sanity — _thinking_supported by model prefix
# ---------------------------------------------------------------------------


class TestThinkingCapablePredicate:
    def test_thinking_capable_predicate_returns_true_for_opus_47(self):
        assert AnthropicProvider._thinking_supported("claude-opus-4-7") is True
        # Future point releases must match by prefix.
        assert (
            AnthropicProvider._thinking_supported("claude-opus-4-7-20251101")
            is True
        )

    def test_thinking_capable_predicate_returns_true_for_sonnet_46(self):
        assert AnthropicProvider._thinking_supported("claude-sonnet-4-6") is True
        assert (
            AnthropicProvider._thinking_supported("claude-sonnet-4-6-20251001")
            is True
        )

    def test_thinking_capable_predicate_returns_false_for_haiku(self):
        assert (
            AnthropicProvider._thinking_supported("claude-haiku-4-5-20251001")
            is False
        )

    def test_thinking_capable_predicate_returns_false_for_legacy_sonnet(self):
        # Older sonnet families (4-5, 3-7-sonnet) must not match the 4-6 prefix.
        assert AnthropicProvider._thinking_supported("claude-sonnet-4-5") is False
        assert (
            AnthropicProvider._thinking_supported("claude-3-5-sonnet-20241022")
            is False
        )


# ---------------------------------------------------------------------------
# DA-Architecture FU10 follow-up — LLMResponse.thinking_tokens type change
# ---------------------------------------------------------------------------


class TestLLMResponseThinkingTokensType:
    """``thinking_tokens`` is now ``Optional[int]`` with default ``None``
    (was ``int = 0``). ``None`` unambiguously means "we don't know" rather
    than the silent under-count that ``0`` produced for cost telemetry."""

    def test_llm_response_thinking_tokens_default_is_none(self):
        r = LLMResponse(text="x", model="y")
        assert r.thinking_tokens is None
        # Belt-and-braces: not the legacy ``0`` integer.
        assert r.thinking_tokens != 0

    def test_llm_response_thinking_tokens_accepts_int(self):
        """The field type is ``Optional[int]`` — explicit int values are
        still accepted for forward-compat with a future milestone that wires
        through SDK-reported counts."""
        r = LLMResponse(text="x", model="y", thinking_tokens=42)
        assert r.thinking_tokens == 42
