"""FU10 — Foundation tests for the multi-provider LLM workflow plan.

Verifies the dataclass surface, truncation predicate, and provider signatures
are wired for FU11-FU18 to land on top. ALL TESTS ARE MOCK-BASED — no live
API calls in this milestone.

Scope:
  1. LLMResponse default construction + new field defaults
  2. is_truncated() on the new OpenAI Responses API finish_reason values,
     and regression coverage for the existing 5 finish_reason paths
  3. Signature inspection: each concrete provider accepts messages_split,
     previous_response_id, response_format with default None
  4. Smoke calls with the new kwargs against fully mocked SDK clients —
     confirms no TypeError when callers pass the new kwargs through
"""
from __future__ import annotations

import asyncio
import inspect
from typing import Any
from unittest.mock import MagicMock

from components.llm_provider import (
    AnthropicProvider,
    GeminiProvider,
    LLMResponse,
    OpenAIProvider,
    _RESPONSES_TRUNCATION_REASONS,
)


# ---------------------------------------------------------------------------
# 1. Dataclass surface
# ---------------------------------------------------------------------------


class TestLLMResponseDataclass:
    def test_llm_response_default_construction(self):
        """All four FU10 forward-compat fields must default predictably.

        FU13 (DA-Arch FU10 follow-up): ``thinking_tokens`` is now
        ``Optional[int]`` with a default of ``None`` (was ``int = 0``).
        ``None`` unambiguously means "we don't know" rather than the silent
        under-count that a default of ``0`` produced for cost telemetry.
        """
        r = LLMResponse(text="hi", model="m")
        assert r.thinking_tokens is None
        assert r.cache_breakpoints_used == 0
        assert r.response_id is None
        assert r.system_fingerprint is None
        # Pre-existing defaults still in place.
        assert r.usage == {}
        assert r.cache_read_input_tokens == 0
        assert r.finish_reason == ""
        assert r.provider == ""
        assert r.raw is None

    def test_llm_response_system_fingerprint_field_exists(self):
        """system_fingerprint defaults to None and accepts a string."""
        r1 = LLMResponse(text="", model="m")
        assert r1.system_fingerprint is None
        r2 = LLMResponse(text="", model="m", system_fingerprint="fp_abc123")
        assert r2.system_fingerprint == "fp_abc123"


# ---------------------------------------------------------------------------
# 2. is_truncated() — Responses API additions + regression coverage
# ---------------------------------------------------------------------------


class TestIsTruncatedResponsesApi:
    def test_responses_truncation_reasons_constant_shape(self):
        """The module-level set must contain at least the FU10 spec values."""
        assert "max_output_tokens" in _RESPONSES_TRUNCATION_REASONS
        assert "incomplete" in _RESPONSES_TRUNCATION_REASONS

    def test_is_truncated_responses_api_max_output_tokens(self):
        r = LLMResponse(
            text="...",
            model="gpt-5",
            provider="openai",
            finish_reason="max_output_tokens",
        )
        assert r.is_truncated() is True

    def test_is_truncated_responses_api_incomplete(self):
        r = LLMResponse(
            text="...",
            model="gpt-5",
            provider="openai",
            finish_reason="incomplete",
        )
        assert r.is_truncated() is True

    def test_is_truncated_responses_api_only_when_provider_is_openai(self):
        """Guards against accidentally treating Responses-API tokens as global.

        ``max_output_tokens`` and ``incomplete`` are OpenAI Responses API
        finish_reason values. Neither contains the substring ``MAX_TOKENS``
        (the ``OUTPUT_`` infix breaks contiguity), so the existing global
        rule does NOT match — the new OpenAI-only branch is the only path
        that should return True for them.
        """
        r1 = LLMResponse(
            text="...",
            model="some-model",
            provider="anthropic",
            finish_reason="max_output_tokens",
        )
        assert r1.is_truncated() is False

        r2 = LLMResponse(
            text="...",
            model="some-model",
            provider="anthropic",
            finish_reason="incomplete",
        )
        assert r2.is_truncated() is False

        # Same finish_reason values but provider=openai — must trip the
        # new branch.
        r3 = LLMResponse(
            text="...",
            model="gpt-5",
            provider="openai",
            finish_reason="max_output_tokens",
        )
        assert r3.is_truncated() is True

        r4 = LLMResponse(
            text="...",
            model="gpt-5",
            provider="openai",
            finish_reason="incomplete",
        )
        assert r4.is_truncated() is True


class TestIsTruncatedExistingBehaviorPreserved:
    """Regression: the 5 existing finish_reason paths still work."""

    def test_anthropic_max_tokens(self):
        r = LLMResponse(text="", model="m", provider="anthropic", finish_reason="max_tokens")
        assert r.is_truncated() is True

    def test_openai_chat_length(self):
        r = LLMResponse(text="", model="m", provider="openai", finish_reason="length")
        assert r.is_truncated() is True

    def test_gemini_max_tokens_string(self):
        r = LLMResponse(text="", model="m", provider="gemini", finish_reason="MAX_TOKENS")
        assert r.is_truncated() is True

    def test_gemini_protobuf_enum_int_form(self):
        r = LLMResponse(text="", model="m", provider="gemini", finish_reason="2")
        assert r.is_truncated() is True

    def test_empty_finish_reason_no_truncation(self):
        r = LLMResponse(text="", model="m", finish_reason="")
        assert r.is_truncated() is False

    def test_normal_stop_no_truncation(self):
        for reason in ("end_turn", "stop", "STOP", "FINISH_REASON_STOP"):
            r = LLMResponse(text="", model="m", finish_reason=reason)
            assert r.is_truncated() is False, f"unexpected truncation for {reason!r}"


# ---------------------------------------------------------------------------
# 3. Signature inspection — concrete providers accept the new kwargs
# ---------------------------------------------------------------------------


_NEW_KWARGS = ("messages_split", "previous_response_id", "response_format")


def _assert_kwargs_with_none_defaults(sig: inspect.Signature) -> None:
    for name in _NEW_KWARGS:
        assert name in sig.parameters, f"missing parameter {name!r} in signature {sig}"
        param = sig.parameters[name]
        assert param.default is None, (
            f"parameter {name!r} default is {param.default!r}, expected None"
        )


class TestProviderSignaturesAcceptNewKwargs:
    def test_anthropic_signature_accepts_new_kwargs(self):
        sig = inspect.signature(AnthropicProvider.agenerate)
        _assert_kwargs_with_none_defaults(sig)

    def test_openai_signature_accepts_new_kwargs(self):
        # OpenAI public agenerate is typed post-FU11; Gemini still pending FU15.
        # Assert directly on the public surface now that it carries the
        # explicit Protocol-shaped signature.
        sig = inspect.signature(OpenAIProvider.agenerate)
        _assert_kwargs_with_none_defaults(sig)

    def test_gemini_signature_accepts_new_kwargs(self):
        # Gemini public agenerate is still *args/**kwargs pre-FU15 — assert on
        # the inner method which has the explicit signature.
        sig = inspect.signature(GeminiProvider._agenerate_once)
        _assert_kwargs_with_none_defaults(sig)


# ---------------------------------------------------------------------------
# 4. Smoke calls with new kwargs through fully mocked SDK clients
# ---------------------------------------------------------------------------


def _make_anthropic_fake_client():
    """Returns a MagicMock-backed client with messages.create as an async stub."""

    class FakeUsage:
        input_tokens = 10
        output_tokens = 5
        cache_read_input_tokens = 0

    class FakeBlock:
        type = "text"
        text = "ok"

    class FakeResponse:
        content = [FakeBlock()]
        usage = FakeUsage()
        stop_reason = "end_turn"

    async def fake_create(**kwargs: Any) -> Any:
        return FakeResponse()

    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = fake_create
    return client


def _make_openai_fake_client():
    """Returns a fake client with both chat.completions.create AND responses.create
    wired to benign responses.

    FU12: gpt-5*/o1*/o3*/o4* now route through ``client.responses.create``
    instead of ``client.chat.completions.create``. The dual-stub keeps a
    single helper viable for both kwargs-passthrough tests (model="gpt-5"
    -> Responses API) and legacy-path tests (model="gpt-4o" -> chat).
    """

    class FakeUsage:
        prompt_tokens = 10
        completion_tokens = 5

    class FakeMessage:
        content = "ok"

    class FakeChoice:
        message = FakeMessage()
        finish_reason = "stop"

    class FakeResponse:
        choices = [FakeChoice()]
        usage = FakeUsage()

    async def fake_create(**kwargs: Any) -> Any:
        return FakeResponse()

    # FU12: Responses API stub. Mirrors the response_id + output_text shape
    # the SDK exposes; usage uses input_tokens/output_tokens (not
    # prompt_tokens/completion_tokens like chat-completions).
    class FakeRespUsage:
        input_tokens = 10
        output_tokens = 5
        input_tokens_details = None

    class FakeResponsesResponse:
        id = "resp_test_123"
        output_text = "ok"
        output = []
        usage = FakeRespUsage()
        incomplete_details = None

    async def fake_responses_create(**kwargs: Any) -> Any:
        return FakeResponsesResponse()

    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = fake_create
    client.responses = MagicMock()
    client.responses.create = fake_responses_create
    return client


class _FakeGeminiResponse:
    def __init__(self) -> None:
        self.text = "ok"
        self.candidates = [MagicMock(finish_reason="STOP")]
        self.usage_metadata = MagicMock(prompt_token_count=10, candidates_token_count=5)


class _FakeGeminiModel:
    def generate_content(self, contents: Any) -> _FakeGeminiResponse:
        return _FakeGeminiResponse()


class _FakeGenAI:
    def configure(self, api_key: str) -> None:  # noqa: D401
        return None

    def GenerativeModel(self, **kwargs: Any) -> _FakeGeminiModel:  # noqa: D401
        return _FakeGeminiModel()


class TestProviderCallsAcceptNewKwargs:
    """Smoke: passing all three new kwargs must not raise TypeError."""

    def test_anthropic_call_with_new_kwargs_does_not_raise(self):
        p = AnthropicProvider(api_key="test")
        p._client = _make_anthropic_fake_client()

        async def run() -> LLMResponse:
            return await p.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="claude-haiku-4-5-20251001",
                messages_split={"stable_prefix": "x", "delta_first_message": "y"},
                previous_response_id="resp_123",
                response_format={"type": "json_schema", "json_schema": {}},
            )

        resp = asyncio.run(run())
        assert resp.text == "ok"
        # FU10 fields default cleanly through the existing code path.
        # FU13 (DA-Arch follow-up): thinking_tokens default is now None.
        assert resp.thinking_tokens is None
        assert resp.cache_breakpoints_used == 0
        assert resp.response_id is None
        assert resp.system_fingerprint is None

    def test_openai_call_with_new_kwargs_does_not_raise(self):
        # OpenAIProvider.agenerate is typed post-FU11 (Protocol-shaped) — the
        # forwarding still passes through to _agenerate_once with the
        # FU10 kwargs plumbed explicitly. Gemini still pending FU15.
        p = OpenAIProvider(api_key="test")
        p._client = _make_openai_fake_client()

        async def run() -> LLMResponse:
            return await p.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-5",
                max_tokens=1024,
                temperature=0.0,
                cache_breakpoints=False,
                messages_split={"stable_prefix": "x", "delta_first_message": "y"},
                previous_response_id="resp_123",
                response_format={"type": "json_schema", "json_schema": {}},
            )

        resp = asyncio.run(run())
        assert resp.text == "ok"
        assert resp.provider == "openai"

    def test_gemini_call_with_new_kwargs_does_not_raise(self):
        p = GeminiProvider(api_key="test")
        p._genai = _FakeGenAI()

        async def run() -> LLMResponse:
            return await p.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.5-pro",
                max_tokens=1024,
                temperature=0.0,
                cache_breakpoints=False,
                messages_split={"stable_prefix": "x", "delta_first_message": "y"},
                previous_response_id="resp_123",
                response_format={"type": "json_schema", "json_schema": {}},
            )

        resp = asyncio.run(run())
        assert resp.text == "ok"
        assert resp.provider == "gemini"
