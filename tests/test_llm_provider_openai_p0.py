"""FU11 — OpenAI P0 compatibility + DA-Architecture follow-up.

Three concerns exercised here, all mocked (no live API calls):

  P0-1  OpenAIProvider must omit `temperature` for reasoning-family models
        (gpt-5*, o1*, o3*, o4*) — server returns HTTP 400
        "temperature is unsupported"/"is deprecated" otherwise. Same shape as
        the Anthropic opus-4-7 fix that landed in commit bfbb4a0.

  P0-2  OpenAIProvider must pass `max_completion_tokens` (not `max_tokens`)
        for the same reasoning-family models. Server rejects `max_tokens`
        with "unsupported" otherwise.

  DA    OpenAIProvider.agenerate must have an explicit typed signature
        matching AnthropicProvider.agenerate (FU10 contract). The previous
        `*args, **kwargs` form bypassed Protocol static-analysis guarantees.

Mocking strategy: tests inject a fake AsyncOpenAI-shaped client at
``provider._client`` so ``_ensure_client()`` short-circuits without importing
the real SDK. The fake's ``chat.completions.create`` is an ``AsyncMock`` whose
``call_args.kwargs`` we read back to assert which params landed on the wire.
"""
from __future__ import annotations

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest

from components.llm_provider import (
    LLMProviderPermanentError,
    OpenAIProvider,
)


# ---------------------------------------------------------------------------
# Fake response + status-error helpers
# ---------------------------------------------------------------------------


class _FakeUsage:
    prompt_tokens = 10
    completion_tokens = 5


class _FakeMessage:
    content = "ok"


class _FakeChoice:
    message = _FakeMessage()
    finish_reason = "stop"


class _FakeResponse:
    choices = [_FakeChoice()]
    usage = _FakeUsage()


class _FakeAPIStatusError(Exception):
    """Stand-in for openai.APIStatusError.

    The real class requires a real httpx.Response, which we don't want to
    construct in unit tests. The provider only reads ``.status_code`` and
    ``str(exc)``, so we expose those.

    We deliberately avoid trying to make `isinstance(_, openai.APIStatusError)`
    succeed — instead we rely on the import-failure fallback in
    `_agenerate_once`: when ``openai`` is importable, the provider catches the
    real APIStatusError class. To make our fake match that path, we patch the
    provider's exception classes at the module level for the duration of the
    test via the ``_install_status_error_classes`` fixture.
    """

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class _FakeAPIConnectionError(Exception):
    """Stand-in for openai.APIConnectionError. Distinct from APIStatusError so
    the provider's ``except (APIConnectionError, APITimeoutError)`` branch
    doesn't shadow the ``except APIStatusError`` branch."""


class _FakeAPITimeoutError(Exception):
    """Stand-in for openai.APITimeoutError, parallel to the connection one."""


@pytest.fixture
def patch_openai_exception_classes(monkeypatch):
    """Make the provider treat our fakes as the live SDK exception classes.

    The provider does ``from openai import APIStatusError, APIConnectionError,
    APITimeoutError`` inside ``_agenerate_once``. We patch each symbol on the
    ``openai`` module to a DISTINCT fake class — using the same class for all
    three would cause the first ``except (APIConnectionError, APITimeoutError)``
    branch in the provider to swallow our intentional APIStatusError raise.
    """
    import openai  # type: ignore

    monkeypatch.setattr(openai, "APIStatusError", _FakeAPIStatusError, raising=True)
    monkeypatch.setattr(openai, "APIConnectionError", _FakeAPIConnectionError, raising=True)
    monkeypatch.setattr(openai, "APITimeoutError", _FakeAPITimeoutError, raising=True)
    yield


def _make_fake_client(create_mock: AsyncMock) -> MagicMock:
    """Build a MagicMock shaped like AsyncOpenAI with a custom ``create``."""
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = create_mock
    return client


def _ok_create_mock() -> AsyncMock:
    """AsyncMock whose every call returns a benign FakeResponse."""
    return AsyncMock(return_value=_FakeResponse())


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# P0-1 — temperature handling per model family
# ---------------------------------------------------------------------------


class TestTemperatureSkippedForReasoningFamilies:
    """Static-prefix list must drop `temperature` for gpt-5/o1/o3/o4.

    FU12 NOTE: in production, gpt-5*/o1*/o3*/o4* now route to the Responses
    API (`client.responses.create`) where the legacy chat-completions
    `temperature` param doesn't apply at all. The FU11 chat-completions
    deprecation logic is still load-bearing for two cases:
      1. Operators who set ``OPENAI_API_MODE=chat`` to force the legacy path
         on a reasoning-family model (e.g. for cost or behaviour reasons).
      2. Future reasoning models the operator hasn't explicitly opted into
         Responses API for via the prefix list.
    These tests set ``OPENAI_API_MODE=chat`` to pin the chat-completions
    deprecation behaviour. A separate suite
    (test_llm_provider_openai_responses.py) covers the Responses API path.
    """

    @pytest.mark.parametrize(
        "model",
        ["gpt-5", "gpt-5.4-mini", "gpt-5.1", "o1", "o1-pro", "o3-mini", "o4-mini"],
    )
    def test_temperature_skipped_for_reasoning_models(self, model, monkeypatch):
        # FU12: force chat-completions so this test exercises the legacy
        # deprecation logic. In production these models go to Responses API.
        monkeypatch.setenv("OPENAI_API_MODE", "chat")

        # Reset the runtime cache so a previous test's discovery doesn't bleed
        # into this assertion.
        OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()
        OpenAIProvider._NO_MAX_TOKENS_DISCOVERED.clear()

        create = _ok_create_mock()
        provider = OpenAIProvider(api_key="test")
        provider._client = _make_fake_client(create)

        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model=model,
                max_tokens=64,
                temperature=0.0,
            )
        )

        kwargs = create.call_args.kwargs
        assert "temperature" not in kwargs, (
            f"temperature must NOT be sent for {model!r}; got kwargs={list(kwargs)}"
        )

    def test_temperature_passed_for_legacy_gpt4(self):
        OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()
        OpenAIProvider._NO_MAX_TOKENS_DISCOVERED.clear()

        create = _ok_create_mock()
        provider = OpenAIProvider(api_key="test")
        provider._client = _make_fake_client(create)

        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4o",
                max_tokens=64,
                temperature=0.3,
            )
        )

        kwargs = create.call_args.kwargs
        assert kwargs.get("temperature") == 0.3
        # And legacy max_tokens path stays put for gpt-4*
        assert kwargs.get("max_tokens") == 64
        assert "max_completion_tokens" not in kwargs

    def test_temperature_passed_for_gpt35(self):
        OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()

        create = _ok_create_mock()
        provider = OpenAIProvider(api_key="test")
        provider._client = _make_fake_client(create)

        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-3.5-turbo",
                max_tokens=64,
                temperature=0.0,
            )
        )

        kwargs = create.call_args.kwargs
        assert kwargs.get("temperature") == 0.0


# ---------------------------------------------------------------------------
# P0-2 — max_completion_tokens handling per model family
# ---------------------------------------------------------------------------


class TestMaxCompletionTokensForReasoningFamilies:
    """Static-prefix list must rewrite max_tokens -> max_completion_tokens.

    FU12 NOTE: same caveat as TestTemperatureSkippedForReasoningFamilies —
    production reasoning-family calls use Responses API which takes
    ``max_output_tokens`` directly. These tests force chat-completions via
    ``OPENAI_API_MODE=chat`` to pin the legacy deprecation logic for the
    forced-chat-mode and unknown-future-reasoning-model cases.
    """

    @pytest.mark.parametrize(
        "model",
        ["gpt-5", "gpt-5.4-mini", "o1-pro", "o3-mini", "o4-mini"],
    )
    def test_max_completion_tokens_for_reasoning_models(self, model, monkeypatch):
        monkeypatch.setenv("OPENAI_API_MODE", "chat")

        OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()
        OpenAIProvider._NO_MAX_TOKENS_DISCOVERED.clear()

        create = _ok_create_mock()
        provider = OpenAIProvider(api_key="test")
        provider._client = _make_fake_client(create)

        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model=model,
                max_tokens=128,
                temperature=0.0,
            )
        )

        kwargs = create.call_args.kwargs
        assert kwargs.get("max_completion_tokens") == 128
        assert "max_tokens" not in kwargs, (
            f"legacy max_tokens must NOT be sent for {model!r}; got {list(kwargs)}"
        )

    def test_max_tokens_for_legacy_gpt4(self):
        OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()
        OpenAIProvider._NO_MAX_TOKENS_DISCOVERED.clear()

        create = _ok_create_mock()
        provider = OpenAIProvider(api_key="test")
        provider._client = _make_fake_client(create)

        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4o-mini",
                max_tokens=256,
                temperature=0.0,
            )
        )

        kwargs = create.call_args.kwargs
        assert kwargs.get("max_tokens") == 256
        assert "max_completion_tokens" not in kwargs


# ---------------------------------------------------------------------------
# Runtime discovery — server-side rejection caches the model
# ---------------------------------------------------------------------------


class TestRuntimeDiscoveryAndRetry:
    """When a model NOT in the static prefix list rejects a param at runtime,
    the provider must cache the model and retry without the param."""

    def test_runtime_temperature_400_caches_and_retries(
        self, patch_openai_exception_classes
    ):
        # Use a model name that is NOT in either static prefix list so the
        # discovery path is the only thing under test.
        model = "future-model-x1"

        # Sanity: model is not pre-registered in either cache.
        OpenAIProvider._NO_TEMPERATURE_DISCOVERED.discard(model)
        OpenAIProvider._NO_MAX_TOKENS_DISCOVERED.discard(model)

        # First call raises 400 with the temperature deprecation; second call
        # (the retry) succeeds.
        create = AsyncMock(
            side_effect=[
                _FakeAPIStatusError(
                    "temperature is deprecated for this model and unsupported.",
                    status_code=400,
                ),
                _FakeResponse(),
            ]
        )
        provider = OpenAIProvider(api_key="test")
        provider._client = _make_fake_client(create)

        resp = _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model=model,
                max_tokens=64,
                temperature=0.0,
            )
        )

        assert resp.text == "ok"
        # First call sent temperature; second call (retry) did NOT.
        assert create.call_count == 2
        first_kwargs = create.call_args_list[0].kwargs
        retry_kwargs = create.call_args_list[1].kwargs
        assert "temperature" in first_kwargs
        assert "temperature" not in retry_kwargs
        # Cache populated.
        assert model in OpenAIProvider._NO_TEMPERATURE_DISCOVERED

        # A subsequent call to the SAME model on a fresh provider must skip
        # temperature up front (no extra round trip).
        create2 = _ok_create_mock()
        provider2 = OpenAIProvider(api_key="test")
        provider2._client = _make_fake_client(create2)
        _run(
            provider2.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model=model,
                max_tokens=64,
                temperature=0.0,
            )
        )
        assert create2.call_count == 1
        assert "temperature" not in create2.call_args.kwargs

        # Cleanup so this discovery doesn't bleed into other test modules.
        OpenAIProvider._NO_TEMPERATURE_DISCOVERED.discard(model)

    def test_runtime_max_tokens_400_caches_and_retries(
        self, patch_openai_exception_classes
    ):
        model = "future-model-x2"
        OpenAIProvider._NO_TEMPERATURE_DISCOVERED.discard(model)
        OpenAIProvider._NO_MAX_TOKENS_DISCOVERED.discard(model)

        create = AsyncMock(
            side_effect=[
                _FakeAPIStatusError(
                    "Parameter 'max_tokens' is unsupported. Please use "
                    "'max_completion_tokens' instead.",
                    status_code=400,
                ),
                _FakeResponse(),
            ]
        )
        provider = OpenAIProvider(api_key="test")
        provider._client = _make_fake_client(create)

        resp = _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model=model,
                max_tokens=200,
                temperature=0.0,
            )
        )

        assert resp.text == "ok"
        assert create.call_count == 2
        first_kwargs = create.call_args_list[0].kwargs
        retry_kwargs = create.call_args_list[1].kwargs
        assert first_kwargs.get("max_tokens") == 200
        assert "max_completion_tokens" not in first_kwargs
        # Retry swapped the param name and preserved the value.
        assert "max_tokens" not in retry_kwargs
        assert retry_kwargs.get("max_completion_tokens") == 200
        # Cache populated.
        assert model in OpenAIProvider._NO_MAX_TOKENS_DISCOVERED

        OpenAIProvider._NO_MAX_TOKENS_DISCOVERED.discard(model)

    def test_runtime_unrelated_400_is_permanent(
        self, patch_openai_exception_classes
    ):
        """A 400 that doesn't match either deprecation pattern must NOT retry,
        and must surface as a permanent error so the iteration loop sees it."""
        model = "future-model-x3"
        OpenAIProvider._NO_TEMPERATURE_DISCOVERED.discard(model)
        OpenAIProvider._NO_MAX_TOKENS_DISCOVERED.discard(model)

        create = AsyncMock(
            side_effect=_FakeAPIStatusError(
                "Some other 400 about messages content policy.",
                status_code=400,
            )
        )
        provider = OpenAIProvider(api_key="test")
        provider._client = _make_fake_client(create)

        with pytest.raises(LLMProviderPermanentError):
            _run(
                provider.agenerate(
                    system="sys",
                    messages=[{"role": "user", "content": "hi"}],
                    model=model,
                    max_tokens=64,
                    temperature=0.0,
                )
            )
        # No retry: only one call landed on the wire.
        assert create.call_count == 1
        # Neither cache touched.
        assert model not in OpenAIProvider._NO_TEMPERATURE_DISCOVERED
        assert model not in OpenAIProvider._NO_MAX_TOKENS_DISCOVERED

    def test_runtime_temperature_real_world_does_not_support_message(
        self, patch_openai_exception_classes
    ):
        """FU11 R1: real-world OpenAI gpt-5 wording uses "does not support" /
        "is supported", NOT "unsupported"/"deprecated". The substring filter
        must broaden to catch this variant or runtime discovery never fires
        and every gpt-5 call surfaces as LLMProviderPermanentError."""
        model = "future-model-r1"
        OpenAIProvider._NO_TEMPERATURE_DISCOVERED.discard(model)
        OpenAIProvider._NO_MAX_TOKENS_DISCOVERED.discard(model)

        # Verbatim shape from real-world OpenAI gpt-5 server responses.
        real_msg = (
            "'temperature' does not support 0.7 with this model. "
            "Only the default (1) value is supported."
        )
        create = AsyncMock(
            side_effect=[
                _FakeAPIStatusError(real_msg, status_code=400),
                _FakeResponse(),
            ]
        )
        provider = OpenAIProvider(api_key="test")
        provider._client = _make_fake_client(create)

        resp = _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model=model,
                max_tokens=64,
                temperature=0.7,
            )
        )

        assert resp.text == "ok"
        # Filter MUST have matched: cache populated, retry happened.
        assert model in OpenAIProvider._NO_TEMPERATURE_DISCOVERED
        assert create.call_count == 2
        first_kwargs = create.call_args_list[0].kwargs
        retry_kwargs = create.call_args_list[1].kwargs
        assert first_kwargs.get("temperature") == 0.7
        assert "temperature" not in retry_kwargs

        OpenAIProvider._NO_TEMPERATURE_DISCOVERED.discard(model)

    def test_runtime_max_tokens_real_world_is_not_supported_message(
        self, patch_openai_exception_classes
    ):
        """FU11 R1: same broadened-filter check for the max_tokens branch.
        "is not supported" is a known wording variant alongside "unsupported"."""
        model = "future-model-r1b"
        OpenAIProvider._NO_TEMPERATURE_DISCOVERED.discard(model)
        OpenAIProvider._NO_MAX_TOKENS_DISCOVERED.discard(model)

        real_msg = (
            "Parameter 'max_tokens' is not supported with this model. "
            "Use 'max_completion_tokens' instead."
        )
        create = AsyncMock(
            side_effect=[
                _FakeAPIStatusError(real_msg, status_code=400),
                _FakeResponse(),
            ]
        )
        provider = OpenAIProvider(api_key="test")
        provider._client = _make_fake_client(create)

        resp = _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model=model,
                max_tokens=200,
                temperature=0.0,
            )
        )

        assert resp.text == "ok"
        assert model in OpenAIProvider._NO_MAX_TOKENS_DISCOVERED
        assert create.call_count == 2
        first_kwargs = create.call_args_list[0].kwargs
        retry_kwargs = create.call_args_list[1].kwargs
        assert first_kwargs.get("max_tokens") == 200
        assert "max_tokens" not in retry_kwargs
        assert retry_kwargs.get("max_completion_tokens") == 200

        OpenAIProvider._NO_MAX_TOKENS_DISCOVERED.discard(model)

    def test_runtime_unrelated_supported_message_does_not_trigger_cache(
        self, patch_openai_exception_classes
    ):
        """FU11 R2 negative coverage: the word-boundary regex must NOT match
        innocuous prose containing "supported". A 400 like
            "this region is supported but the model isn't available here"
        carries the substring "supported" but is NOT a parameter-deprecation
        signal — caching would be a false positive that permanently strips
        `temperature` from a model that supports it. Asserts neither cache
        is touched and the call surfaces as LLMProviderPermanentError."""
        model = "future-model-r2neg"
        OpenAIProvider._NO_TEMPERATURE_DISCOVERED.discard(model)
        OpenAIProvider._NO_MAX_TOKENS_DISCOVERED.discard(model)

        unrelated_msg = (
            "this region is supported but the model isn't available here. "
            "temperature was 0.7 in the request."
        )
        create = AsyncMock(
            side_effect=_FakeAPIStatusError(unrelated_msg, status_code=400)
        )
        provider = OpenAIProvider(api_key="test")
        provider._client = _make_fake_client(create)

        with pytest.raises(LLMProviderPermanentError):
            _run(
                provider.agenerate(
                    system="sys",
                    messages=[{"role": "user", "content": "hi"}],
                    model=model,
                    max_tokens=64,
                    temperature=0.7,
                )
            )

        # No retry — no rejection-pattern match.
        assert create.call_count == 1
        # Neither cache populated.
        assert model not in OpenAIProvider._NO_TEMPERATURE_DISCOVERED
        assert model not in OpenAIProvider._NO_MAX_TOKENS_DISCOVERED


# ---------------------------------------------------------------------------
# R3 (nice-to-have) — both transformations apply to a single reasoning model
# ---------------------------------------------------------------------------


class TestReasoningModelCrossFeature:
    def test_o1_model_omits_temperature_AND_uses_max_completion_tokens(self, monkeypatch):
        """One call with model="o1" must produce wire kwargs that BOTH:
          - omit `temperature` entirely (P0-1), AND
          - send `max_completion_tokens` instead of `max_tokens` (P0-2).
        Guards against a regression where one transformation lands without
        the other (e.g. early draft branched on the same prefix list but
        only patched one kwarg).

        FU12: forces chat-completions via ``OPENAI_API_MODE=chat`` because o1
        now routes to Responses API by default. The cross-feature contract
        being pinned here is the chat-completions deprecation logic, which
        still applies whenever an operator forces the legacy path.
        """
        monkeypatch.setenv("OPENAI_API_MODE", "chat")

        OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()
        OpenAIProvider._NO_MAX_TOKENS_DISCOVERED.clear()

        create = _ok_create_mock()
        provider = OpenAIProvider(api_key="test")
        provider._client = _make_fake_client(create)

        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="o1",
                max_tokens=512,
                temperature=0.4,
            )
        )

        # Exactly one wire call (no retry needed — static prefix matched).
        assert create.call_count == 1
        kwargs = create.call_args.kwargs
        # P0-1 transformation
        assert "temperature" not in kwargs
        # P0-2 transformation
        assert kwargs.get("max_completion_tokens") == 512
        assert "max_tokens" not in kwargs
        # Sanity: model + messages still passed through.
        assert kwargs.get("model") == "o1"
        assert kwargs.get("messages")[-1] == {"role": "user", "content": "hi"}


# ---------------------------------------------------------------------------
# DA-Architecture follow-up — explicit typed signature on agenerate
# ---------------------------------------------------------------------------


_EXPECTED_AGENERATE_PARAMS = (
    "self",
    "system",
    "messages",
    "model",
    "max_tokens",
    "temperature",
    "cache_breakpoints",
    "messages_split",
    "previous_response_id",
    "response_format",
)


class TestAgenerateTypedSignature:
    def test_typed_signature_present_on_agenerate(self):
        sig = inspect.signature(OpenAIProvider.agenerate)
        params = list(sig.parameters.keys())
        assert params == list(_EXPECTED_AGENERATE_PARAMS), (
            f"OpenAIProvider.agenerate parameters drift: got {params}, "
            f"expected {list(_EXPECTED_AGENERATE_PARAMS)}"
        )
        # No *args or **kwargs sentinel on the public surface.
        for name, param in sig.parameters.items():
            assert param.kind not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ), f"parameter {name!r} is {param.kind}; expected explicit typed param"

    def test_typed_signature_defaults_match_protocol(self):
        sig = inspect.signature(OpenAIProvider.agenerate)
        assert sig.parameters["max_tokens"].default == 4096
        assert sig.parameters["temperature"].default == 0.0
        assert sig.parameters["cache_breakpoints"].default is True
        assert sig.parameters["messages_split"].default is None
        assert sig.parameters["previous_response_id"].default is None
        assert sig.parameters["response_format"].default is None
