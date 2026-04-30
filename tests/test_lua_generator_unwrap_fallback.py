"""W8 (N7) — daemon-path silent unwrap fallback regression test.

Before W8, _agenerate_fast caught ValueError from wrap_for_observo and
silently set wrapped = lua_body while still flagging quality="accepted".
That meant the worker shipped UNWRAPPED Lua flagged as accepted, which
the standalone dataplane binary refused to load.

W8 changes the failure path so:
  - the diagnostic body is preserved on lua_code (for debugging)
  - quality is "rejected"
  - confidence_score is 0.0
  - error contains the underlying ValueError message

This test pair locks in the new contract AND a positive control to
prove the success path is unchanged.
"""
import asyncio

import pytest

from components.lua_generator import (
    GenerationOptions,
    GenerationRequest,
    LuaGenerator,
)
from components.llm_provider import LLMResponse


class _StubProvider:
    """Minimal LLMProvider stub that returns a canned Lua body.

    LuaGenerator only reads .agenerate() in _agenerate_fast — the .name
    attr and the sync .generate() shim are unused on this code path so
    we don't bother implementing them.
    """

    name = "stub"

    def __init__(self, response_text: str = "function processEvent(event)\n  return event\nend\n") -> None:
        self._response_text = response_text

    async def agenerate(  # noqa: D401 - protocol shape
        self,
        system: str,
        messages,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        cache_breakpoints: bool = True,
    ) -> LLMResponse:
        return LLMResponse(
            text=self._response_text,
            model=model,
            usage={"input_tokens": 1, "output_tokens": 1},
            provider="stub",
            finish_reason="stop",
        )


def _make_generator(response_text: str = "function processEvent(event)\n  return event\nend\n") -> LuaGenerator:
    return LuaGenerator(
        config={"anthropic": {"api_key": "test-key"}},
        provider=_StubProvider(response_text),
    )


def _make_request() -> GenerationRequest:
    return GenerationRequest.from_legacy_args(
        "akamai_dns",
        {
            "parser_name": "akamai_dns",
            "source_fields": [{"name": "queryName", "type": "string"}],
            "ocsf_classification": {"class_uid": 4003},
            "vendor": "Akamai", "product": "DNS",
        },
    )


def test_wrap_failure_marks_result_rejected(monkeypatch):
    """Negative control: wrap_for_observo raising ValueError must
    produce quality='rejected', confidence_score=0.0, populated error."""
    def _raise(_lua_body: str) -> str:
        raise ValueError("test boundary")

    monkeypatch.setattr(
        "components.lua_generator.wrap_for_observo",
        _raise,
    )

    gen = _make_generator()
    result = asyncio.run(
        gen.agenerate(_make_request(), GenerationOptions(mode="fast")),
    )

    assert result.quality == "rejected", (
        f"expected quality='rejected', got {result.quality!r}"
    )
    assert result.confidence_score == 0.0, (
        f"expected confidence_score=0.0, got {result.confidence_score!r}"
    )
    assert result.error, "error must be non-empty on wrap failure"
    assert "test boundary" in result.error, (
        f"expected ValueError message in error, got {result.error!r}"
    )
    # Diagnostic body preserved (W8 requirement) — caller can still
    # inspect what the LLM produced even though we refuse to ship it.
    assert result.lua_code, (
        "lua_code should retain the unwrapped diagnostic body"
    )
    # Hard-rejected results must not look successful anywhere.
    assert result.success is False
    assert result.confidence_grade == "F"


def test_wrap_success_path_unchanged(monkeypatch):
    """Positive control: when wrap_for_observo succeeds, the result
    keeps the legacy success contract — quality='accepted',
    confidence_score=70.0, error=None. Confirms W8 did not regress
    the happy path."""
    def _wrap(lua_body: str) -> str:
        return f"-- wrapped\n{lua_body}\n-- end\n"

    monkeypatch.setattr(
        "components.lua_generator.wrap_for_observo",
        _wrap,
    )

    gen = _make_generator()
    result = asyncio.run(
        gen.agenerate(_make_request(), GenerationOptions(mode="fast")),
    )

    assert result.quality == "accepted", (
        f"expected quality='accepted', got {result.quality!r}"
    )
    assert result.confidence_score == 70.0
    assert result.error is None
    assert result.success is True
    assert result.lua_code.startswith("-- wrapped")


def test_wrap_failure_error_message_includes_underlying_text(monkeypatch):
    """The ValueError message must round-trip into result.error so
    operators reading worker logs can diagnose the wrap failure."""
    def _raise(_lua_body: str) -> str:
        raise ValueError("missing process(event, emit) wrapper")

    monkeypatch.setattr(
        "components.lua_generator.wrap_for_observo",
        _raise,
    )

    gen = _make_generator()
    result = asyncio.run(
        gen.agenerate(_make_request(), GenerationOptions(mode="fast")),
    )

    assert result.quality == "rejected"
    assert "missing process(event, emit) wrapper" in (result.error or "")


def test_empty_lua_body_remains_below_threshold(monkeypatch):
    """Sanity: when the LLM returns nothing usable (empty body),
    the result is still 'below_threshold' (NOT 'rejected') — the new
    'rejected' state is reserved for wrap failures specifically.

    This guards against accidentally collapsing the empty-body and
    wrap-failure branches together.
    """
    # No wrap monkeypatch — the body is empty so wrap is never called.
    gen = _make_generator(response_text="")
    result = asyncio.run(
        gen.agenerate(_make_request(), GenerationOptions(mode="fast")),
    )

    assert result.quality == "below_threshold"
    assert result.confidence_score == 0.0
    assert result.success is False
    assert result.error == "empty lua body after parse"
