"""FU12 — OpenAI Responses API routing in OpenAIProvider.

Covers the new behaviours introduced by FU12 (P1-4):

  * gpt-5*/o1*/o3*/o4* route to ``client.responses.create``
  * gpt-4*/gpt-3.5* keep going through ``client.chat.completions.create``
  * incomplete_details.reason="max_output_tokens" maps to
    finish_reason="max_output_tokens" so LLMResponse.is_truncated() fires
  * response.id is surfaced through LLMResponse.response_id for chaining
  * previous_response_id passes through to client.responses.create
  * response_format is wrapped as text={"format": ...} (NOT a top-level
    response_format kwarg — that's the chat-completions shape, the SDK
    rejects it on Responses API)
  * _max_output_tokens_for(model) returns 32k for reasoning families,
    16k for legacy
  * the FU11 deprecation cache (_TEMPERATURE_REJECTION_RE etc.) is NOT
    consulted on Responses API errors (different param surface)
  * the GPT-5 strategy short-circuit reaches provider.generate(...) (not
    .agenerate) from a sync workbench Flask handler call site

All mocked. No live API calls. Mocking strategy mirrors
test_llm_provider_openai_p0.py — inject a fake AsyncOpenAI-shaped client
at provider._client.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from components.llm_provider import (
    LLMProviderPermanentError,
    OpenAIProvider,
)


# ---------------------------------------------------------------------------
# Fake response shapes — Responses API
# ---------------------------------------------------------------------------


class _FakeResponsesUsage:
    input_tokens = 10
    output_tokens = 5
    input_tokens_details = None


class _FakeResponsesResponse:
    """Default Responses API response: completed cleanly with .output_text."""
    id = "resp_default_id"
    output_text = "ok"
    output = []
    usage = _FakeResponsesUsage()
    incomplete_details = None


class _FakeIncompleteDetails:
    def __init__(self, reason: str) -> None:
        self.reason = reason


class _FakeAPIStatusError(Exception):
    """Stand-in for openai.APIStatusError with .status_code."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class _FakeAPIConnectionError(Exception):
    pass


class _FakeAPITimeoutError(Exception):
    pass


@pytest.fixture
def patch_openai_exception_classes(monkeypatch):
    """Make the provider treat our fakes as the live SDK exception classes."""
    import openai  # type: ignore

    monkeypatch.setattr(openai, "APIStatusError", _FakeAPIStatusError, raising=True)
    monkeypatch.setattr(openai, "APIConnectionError", _FakeAPIConnectionError, raising=True)
    monkeypatch.setattr(openai, "APITimeoutError", _FakeAPITimeoutError, raising=True)
    yield


# ---------------------------------------------------------------------------
# Fake client builders
# ---------------------------------------------------------------------------


def _make_fake_client(
    *, chat_create: AsyncMock | None = None, responses_create: AsyncMock | None = None,
) -> MagicMock:
    """Build an AsyncOpenAI-shaped MagicMock with the requested async stubs.

    Both branches stubbed by default so a wrong-routing regression surfaces
    via call_count rather than AttributeError.
    """
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.responses = MagicMock()

    client.chat.completions.create = chat_create or AsyncMock(
        return_value=_make_chat_response()
    )
    client.responses.create = responses_create or AsyncMock(
        return_value=_FakeResponsesResponse()
    )
    return client


def _make_chat_response():
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

    return FakeResponse()


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Routing tests — which API surface does each model use?
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model", ["gpt-5", "gpt-5.4-mini", "gpt-5.1"])
def test_responses_api_routed_for_gpt5(monkeypatch, model):
    """gpt-5* must route to client.responses.create, NOT chat.completions."""
    monkeypatch.delenv("OPENAI_API_MODE", raising=False)
    OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()

    chat_create = AsyncMock(return_value=_make_chat_response())
    responses_create = AsyncMock(return_value=_FakeResponsesResponse())
    provider = OpenAIProvider(api_key="test")
    provider._client = _make_fake_client(
        chat_create=chat_create, responses_create=responses_create,
    )

    _run(
        provider.agenerate(
            system="sys",
            messages=[{"role": "user", "content": "hi"}],
            model=model,
            max_tokens=128,
        )
    )

    assert chat_create.call_count == 0
    assert responses_create.call_count == 1


def test_responses_api_routed_for_o1(monkeypatch):
    monkeypatch.delenv("OPENAI_API_MODE", raising=False)
    OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()

    chat_create = AsyncMock(return_value=_make_chat_response())
    responses_create = AsyncMock(return_value=_FakeResponsesResponse())
    provider = OpenAIProvider(api_key="test")
    provider._client = _make_fake_client(
        chat_create=chat_create, responses_create=responses_create,
    )

    _run(
        provider.agenerate(
            system="sys",
            messages=[{"role": "user", "content": "hi"}],
            model="o1-pro",
            max_tokens=128,
        )
    )

    assert chat_create.call_count == 0
    assert responses_create.call_count == 1


def test_responses_api_routed_for_o3(monkeypatch):
    monkeypatch.delenv("OPENAI_API_MODE", raising=False)
    OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()

    chat_create = AsyncMock(return_value=_make_chat_response())
    responses_create = AsyncMock(return_value=_FakeResponsesResponse())
    provider = OpenAIProvider(api_key="test")
    provider._client = _make_fake_client(
        chat_create=chat_create, responses_create=responses_create,
    )

    _run(
        provider.agenerate(
            system="sys",
            messages=[{"role": "user", "content": "hi"}],
            model="o3-mini",
            max_tokens=128,
        )
    )

    assert chat_create.call_count == 0
    assert responses_create.call_count == 1


def test_responses_api_routed_for_o4(monkeypatch):
    monkeypatch.delenv("OPENAI_API_MODE", raising=False)
    OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()

    chat_create = AsyncMock(return_value=_make_chat_response())
    responses_create = AsyncMock(return_value=_FakeResponsesResponse())
    provider = OpenAIProvider(api_key="test")
    provider._client = _make_fake_client(
        chat_create=chat_create, responses_create=responses_create,
    )

    _run(
        provider.agenerate(
            system="sys",
            messages=[{"role": "user", "content": "hi"}],
            model="o4-mini",
            max_tokens=128,
        )
    )

    assert chat_create.call_count == 0
    assert responses_create.call_count == 1


def test_chat_completions_routed_for_gpt4(monkeypatch):
    """gpt-4o is NOT in the Responses API prefix list -> chat.completions."""
    monkeypatch.delenv("OPENAI_API_MODE", raising=False)
    OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()

    chat_create = AsyncMock(return_value=_make_chat_response())
    responses_create = AsyncMock(return_value=_FakeResponsesResponse())
    provider = OpenAIProvider(api_key="test")
    provider._client = _make_fake_client(
        chat_create=chat_create, responses_create=responses_create,
    )

    _run(
        provider.agenerate(
            system="sys",
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o",
            max_tokens=128,
        )
    )

    assert chat_create.call_count == 1
    assert responses_create.call_count == 0


# ---------------------------------------------------------------------------
# Truncation, response_id, previous_response_id, response_format pass-through
# ---------------------------------------------------------------------------


def test_responses_api_incomplete_max_output_tokens_marks_truncated(monkeypatch):
    """incomplete_details.reason='max_output_tokens' -> is_truncated()=True."""
    monkeypatch.delenv("OPENAI_API_MODE", raising=False)
    OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()

    class _TruncatedResponse:
        id = "resp_truncated"
        output_text = "partial output before cutoff"
        output = []
        usage = _FakeResponsesUsage()
        incomplete_details = _FakeIncompleteDetails(reason="max_output_tokens")

    responses_create = AsyncMock(return_value=_TruncatedResponse())
    provider = OpenAIProvider(api_key="test")
    provider._client = _make_fake_client(responses_create=responses_create)

    resp = _run(
        provider.agenerate(
            system="sys",
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-5",
            max_tokens=64,
        )
    )

    assert resp.finish_reason == "max_output_tokens"
    assert resp.is_truncated() is True


def test_response_id_surfaced_for_chaining(monkeypatch):
    """response.id should populate LLMResponse.response_id."""
    monkeypatch.delenv("OPENAI_API_MODE", raising=False)
    OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()

    class _IdResponse:
        id = "resp_abc123"
        output_text = "ok"
        output = []
        usage = _FakeResponsesUsage()
        incomplete_details = None

    responses_create = AsyncMock(return_value=_IdResponse())
    provider = OpenAIProvider(api_key="test")
    provider._client = _make_fake_client(responses_create=responses_create)

    resp = _run(
        provider.agenerate(
            system="sys",
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-5",
            max_tokens=64,
        )
    )

    assert resp.response_id == "resp_abc123"


def test_previous_response_id_passed_through(monkeypatch):
    """previous_response_id flows through to client.responses.create kwargs."""
    monkeypatch.delenv("OPENAI_API_MODE", raising=False)
    OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()

    responses_create = AsyncMock(return_value=_FakeResponsesResponse())
    provider = OpenAIProvider(api_key="test")
    provider._client = _make_fake_client(responses_create=responses_create)

    _run(
        provider.agenerate(
            system="sys",
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-5",
            max_tokens=64,
            previous_response_id="resp_xyz",
        )
    )

    kwargs = responses_create.call_args.kwargs
    assert kwargs.get("previous_response_id") == "resp_xyz"


def test_response_format_translated_to_text_format(monkeypatch):
    """response_format must land at text={"format": ...}, NOT top-level."""
    monkeypatch.delenv("OPENAI_API_MODE", raising=False)
    OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()

    responses_create = AsyncMock(return_value=_FakeResponsesResponse())
    provider = OpenAIProvider(api_key="test")
    provider._client = _make_fake_client(responses_create=responses_create)

    rf = {
        "type": "json_schema",
        "name": "test_schema",
        "schema": {"type": "object", "properties": {"x": {"type": "string"}}},
        "strict": True,
    }
    _run(
        provider.agenerate(
            system="sys",
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-5",
            max_tokens=64,
            response_format=rf,
        )
    )

    kwargs = responses_create.call_args.kwargs
    # CRITICAL: nested under text.format, NOT a top-level response_format kwarg.
    assert kwargs.get("text") == {"format": rf}
    assert "response_format" not in kwargs, (
        "response_format must NOT be a top-level kwarg on the Responses API; "
        "the SDK rejects that shape (it's the chat-completions form)."
    )


# ---------------------------------------------------------------------------
# FU12-DA-FU12 REFUTE-1 — operator-tunable env vars wire-through
# ---------------------------------------------------------------------------
#
# OPENAI_REASONING_EFFORT and OPENAI_TEXT_VERBOSITY are documented operator
# tunables (.env.example:60-61). Pre-FU12 they flowed through the deleted
# _build_openai_responses_request helper in agentic_lua_generator.py;
# DA-FU12 caught the regression where the unified provider didn't pick
# them up. These tests pin the wire-through.


def test_responses_api_reasoning_effort_passed_when_env_set(monkeypatch):
    """OPENAI_REASONING_EFFORT=high must land at kwargs['reasoning']['effort']."""
    monkeypatch.delenv("OPENAI_API_MODE", raising=False)
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "high")
    monkeypatch.delenv("OPENAI_TEXT_VERBOSITY", raising=False)
    OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()

    responses_create = AsyncMock(return_value=_FakeResponsesResponse())
    provider = OpenAIProvider(api_key="test")
    provider._client = _make_fake_client(responses_create=responses_create)

    _run(
        provider.agenerate(
            system="sys",
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-5.4-mini",
            max_tokens=64,
        )
    )

    kwargs = responses_create.call_args.kwargs
    assert kwargs.get("reasoning") == {"effort": "high"}


def test_responses_api_text_verbosity_passed_when_env_set(monkeypatch):
    """OPENAI_TEXT_VERBOSITY=low must land at kwargs['text']['verbosity']."""
    monkeypatch.delenv("OPENAI_API_MODE", raising=False)
    monkeypatch.delenv("OPENAI_REASONING_EFFORT", raising=False)
    monkeypatch.setenv("OPENAI_TEXT_VERBOSITY", "low")
    OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()

    responses_create = AsyncMock(return_value=_FakeResponsesResponse())
    provider = OpenAIProvider(api_key="test")
    provider._client = _make_fake_client(responses_create=responses_create)

    _run(
        provider.agenerate(
            system="sys",
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-5.4-mini",
            max_tokens=64,
        )
    )

    kwargs = responses_create.call_args.kwargs
    assert isinstance(kwargs.get("text"), dict)
    assert kwargs["text"].get("verbosity") == "low"


def test_responses_api_reasoning_effort_unset_means_no_reasoning_kwarg(monkeypatch):
    """No OPENAI_REASONING_EFFORT env var -> 'reasoning' absent from kwargs."""
    monkeypatch.delenv("OPENAI_API_MODE", raising=False)
    monkeypatch.delenv("OPENAI_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("OPENAI_TEXT_VERBOSITY", raising=False)
    OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()

    responses_create = AsyncMock(return_value=_FakeResponsesResponse())
    provider = OpenAIProvider(api_key="test")
    provider._client = _make_fake_client(responses_create=responses_create)

    _run(
        provider.agenerate(
            system="sys",
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-5.4-mini",
            max_tokens=64,
        )
    )

    kwargs = responses_create.call_args.kwargs
    assert "reasoning" not in kwargs
    # And no text kwarg either, since we didn't pass response_format
    # nor verbosity.
    assert "text" not in kwargs


def test_responses_api_text_verbosity_merges_with_response_format(monkeypatch):
    """Both OPENAI_TEXT_VERBOSITY AND response_format -> text carries both."""
    monkeypatch.delenv("OPENAI_API_MODE", raising=False)
    monkeypatch.delenv("OPENAI_REASONING_EFFORT", raising=False)
    monkeypatch.setenv("OPENAI_TEXT_VERBOSITY", "low")
    OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()

    responses_create = AsyncMock(return_value=_FakeResponsesResponse())
    provider = OpenAIProvider(api_key="test")
    provider._client = _make_fake_client(responses_create=responses_create)

    rf = {
        "type": "json_schema",
        "name": "test_schema",
        "schema": {"type": "object", "properties": {"x": {"type": "string"}}},
        "strict": True,
    }
    _run(
        provider.agenerate(
            system="sys",
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-5.4-mini",
            max_tokens=64,
            response_format=rf,
        )
    )

    kwargs = responses_create.call_args.kwargs
    text_cfg = kwargs.get("text")
    assert isinstance(text_cfg, dict)
    # Both knobs landed on the same `text` config.
    assert text_cfg.get("format") == rf
    assert text_cfg.get("verbosity") == "low"
    # And response_format must NOT be a top-level kwarg — that's the
    # chat-completions form, the SDK rejects it on Responses API.
    assert "response_format" not in kwargs


def test_responses_api_reasoning_effort_for_non_gpt5_ignored(monkeypatch):
    """OPENAI_REASONING_EFFORT applies only to gpt-5*; o1/o3/o4 ignore it.

    Pre-FU12 the build helper gated the reasoning/verbosity knobs on
    ``model.startswith("gpt-5")`` only — o1/o3/o4 were Responses-API
    routed but did NOT apply these env vars. Preserve that behaviour so
    the FU12 wire-through is a faithful port, not a behaviour change.
    """
    monkeypatch.delenv("OPENAI_API_MODE", raising=False)
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "high")
    monkeypatch.setenv("OPENAI_TEXT_VERBOSITY", "low")
    OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()

    responses_create = AsyncMock(return_value=_FakeResponsesResponse())
    provider = OpenAIProvider(api_key="test")
    provider._client = _make_fake_client(responses_create=responses_create)

    _run(
        provider.agenerate(
            system="sys",
            messages=[{"role": "user", "content": "hi"}],
            model="o1",
            max_tokens=64,
        )
    )

    kwargs = responses_create.call_args.kwargs
    assert "reasoning" not in kwargs, (
        "OPENAI_REASONING_EFFORT must only apply to gpt-5*; o1/o3/o4 "
        "preserve pre-FU12 behaviour by ignoring this env var."
    )
    assert "text" not in kwargs, (
        "OPENAI_TEXT_VERBOSITY must only apply to gpt-5*; o1/o3/o4 "
        "preserve pre-FU12 behaviour by ignoring this env var."
    )


# ---------------------------------------------------------------------------
# _max_output_tokens_for predicate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model", ["gpt-5", "gpt-5.4-mini", "o1", "o3-mini", "o4-mini"])
def test_max_output_tokens_for_gpt5_returns_32k(model):
    assert OpenAIProvider._max_output_tokens_for(model) == 32000


@pytest.mark.parametrize("model", ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"])
def test_max_output_tokens_for_gpt4_returns_16k(model):
    assert OpenAIProvider._max_output_tokens_for(model) == 16000


# ---------------------------------------------------------------------------
# FU11 deprecation-cache isolation: must NOT fire on Responses API errors
# ---------------------------------------------------------------------------


def test_responses_api_call_does_not_apply_temperature_cache_path(
    patch_openai_exception_classes, monkeypatch,
):
    """FU11's deprecation cache (_NO_TEMPERATURE_DISCOVERED) is chat-only.

    Responses API uses different params (max_output_tokens, no
    temperature for reasoning models by spec) — a 400 from
    client.responses.create must NOT pollute the FU11 chat-completions
    cache nor trigger the chat-only retry path.
    """
    monkeypatch.delenv("OPENAI_API_MODE", raising=False)
    model = "gpt-5"
    OpenAIProvider._NO_TEMPERATURE_DISCOVERED.discard(model)
    OpenAIProvider._NO_MAX_TOKENS_DISCOVERED.discard(model)

    # Simulate a 400 from the Responses API — the wording mentions
    # "temperature" deliberately to prove the chat-only regex isn't
    # consulted here.
    responses_create = AsyncMock(
        side_effect=_FakeAPIStatusError(
            "'temperature' does not support 0.7 with this model.",
            status_code=400,
        )
    )
    provider = OpenAIProvider(api_key="test")
    provider._client = _make_fake_client(responses_create=responses_create)

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

    # No retry: chat-completions deprecation logic is NOT consulted on
    # the Responses API path. Exactly one wire call landed.
    assert responses_create.call_count == 1
    # FU11 caches must NOT have been populated by a Responses API 400.
    assert model not in OpenAIProvider._NO_TEMPERATURE_DISCOVERED
    assert model not in OpenAIProvider._NO_MAX_TOKENS_DISCOVERED


# ---------------------------------------------------------------------------
# GPT-5 strategy sync entry point — call site uses provider.generate, not agenerate
# ---------------------------------------------------------------------------


def test_gpt5_strategy_uses_sync_generate_from_direct_workbench_call_site(
    tmp_path, monkeypatch,
):
    """Sync workbench Flask handler -> provider.generate (the sync wrapper).

    AgenticLuaGenerator.generate(parser_entry) is invoked synchronously
    from the workbench's Flask handler (no running event loop). Inside,
    _run_gpt5_strategy must use the sync provider.generate(...) wrapper
    rather than agenerate(...) directly — agenerate would require an
    awaiting context. This test pins the sync call site by mocking
    provider.generate() and asserting it (not agenerate) was reached.
    """
    monkeypatch.delenv("OPENAI_API_MODE", raising=False)

    from components.agentic_lua_generator import AgenticLuaGenerator

    gen = AgenticLuaGenerator(
        api_key="test-key",
        model="gpt-5-mini",
        provider="openai",
        max_iterations=1,
        score_threshold=80,
        output_dir=tmp_path,
    )

    # Stub out the harness so the strategy reaches a deterministic outcome.
    class _Harness:
        def run_all_checks(
            self, lua_code, parser_config, ocsf_version="1.3.0",
            custom_test_events=None,
        ):
            return {
                "confidence_score": 84,
                "confidence_grade": "B",
                "checks": {
                    "field_comparison": {"coverage_pct": 85},
                    "lua_linting": {"issues": []},
                    "ocsf_mapping": {
                        "missing_required": [],
                        "class_uid": 4003,
                        "class_name": "DNS Activity",
                    },
                },
                "ocsf_alignment": {"required_coverage": 100.0},
            }

    class _SourceAnalyzer:
        def analyze_parser(self, parser_entry):
            return {"fields": [{"name": "message", "type": "string"}]}

    gen.harness = _Harness()
    gen.source_analyzer = _SourceAnalyzer()

    # Track which method gets called. Builds an LLMResponse-shaped object
    # so the strategy's downstream consumers (text, response_id, raw)
    # work without bespoke type matching.
    from components.llm_provider import LLMResponse

    plan_payload = (
        '{"class_uid":4003,"class_name":"DNS Activity","category_uid":4,'
        '"category_name":"Network Activity","activity_id":1,'
        '"activity_name":"DNS Query","timestamp_sources":["timestamp"],'
        '"severity_strategy":"default 0",'
        '"embedded_payload_strategy":"none",'
        '"mappings":[{"target":"src_endpoint.ip",'
        '"source_candidates":["cliIP"],"transform":"direct",'
        '"required":false}],"notes":[]}'
    )

    sync_calls: list = []
    async_calls: list = []

    def fake_generate(**kwargs: Any) -> LLMResponse:
        sync_calls.append(kwargs)
        # First call (with response_format) is the planner; second is code.
        if kwargs.get("response_format"):
            return LLMResponse(
                text=plan_payload,
                model=kwargs.get("model", ""),
                provider="openai",
                response_id="resp_plan_x1",
            )
        return LLMResponse(
            text="function processEvent(event)\n  return event\nend",
            model=kwargs.get("model", ""),
            provider="openai",
            response_id="resp_code_x1",
        )

    async def fake_agenerate(**kwargs: Any) -> LLMResponse:
        async_calls.append(kwargs)
        return LLMResponse(
            text="should-not-be-reached",
            model=kwargs.get("model", ""),
            provider="openai",
        )

    class _StubProvider:
        generate = staticmethod(fake_generate)
        agenerate = staticmethod(fake_agenerate)

    gen._inner._provider_override = _StubProvider()  # type: ignore[assignment]

    result = gen.generate(
        {
            "parser_name": "gpt5_sync_test",
            "ingestion_mode": "push",
            "raw_examples": [
                {"cliIP": "1.2.3.4", "domain": "example.com"},
            ],
            "config": {
                "attributes": {
                    "dataSource": {"vendor": "Akamai", "product": "DNS"},
                },
            },
        },
        force_regenerate=True,
    )

    # Sync entrypoint MUST have been used (>=1 call: planner + code).
    assert len(sync_calls) >= 2, (
        f"provider.generate(...) should be the sync entry point used by the "
        f"GPT-5 strategy from a non-async workbench call site; "
        f"got sync_calls={len(sync_calls)} async_calls={len(async_calls)}"
    )
    # And agenerate (the async path) MUST NOT have been used in this flow.
    assert async_calls == [], (
        "agenerate() is the async path and must not be reached from the "
        "sync workbench call site; sync_generate is the right wrapper."
    )
    # Sanity: result completed and is the GPT-5 strategy method.
    assert result["generation_method"] == "agentic_llm_gpt5_plan"
