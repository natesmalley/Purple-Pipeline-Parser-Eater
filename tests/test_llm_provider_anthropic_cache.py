"""FU14 P2-1 + P2-3 — Anthropic dual cache breakpoint + per-model output ceilings.

Two concerns exercised here, all mocked (no live API calls):

  P2-1  AnthropicProvider must consume ``messages_split={"stable_prefix": ...,
        "delta_first_message": ...}`` and rewrite ``messages[0]`` into a
        structured-content list whose first block carries
        ``cache_control={"type": "ephemeral"}``. Combined with the existing
        cache_control on the system block, this gives Anthropic two cache
        breakpoints per request — one for the system prompt, one for the
        stable prefix of the first user message.

        Caller invariant (enforced upstream in
        ``LuaGenerator._build_iteration_messages_split``):
            messages[0]["content"] == stable_prefix + delta_first_message

        Semantic-parity invariant: with ``messages_split`` provided, the wire
        payload to Anthropic carries IDENTICAL content to the wire payload
        that would have been built from ``messages`` alone — the only
        difference is the ``cache_control`` marker on the stable block of
        ``messages[0]``.

  P2-3  ``AnthropicProvider._max_output_tokens_for(model)`` exposes the
        per-model output ceiling consumed by the FU14 truncation retry in
        ``LuaGenerator._call_llm``. Anthropic publishes per-model output
        windows that are larger than the legacy 16k cap (opus-4-7 -> 32k,
        sonnet-4-6 -> 64k, haiku-4-5 -> 8k); the lookup table here is the
        single source of truth.

        Same predicate is added to ``GeminiProvider`` for the same reason.

Mocking strategy: tests inject a fake AsyncAnthropic-shaped client at
``provider._client`` so ``_ensure_client()`` short-circuits without importing
the real SDK. The fake's ``messages.create`` is an ``AsyncMock`` whose
``call_args.kwargs`` we read back to assert which params landed on the wire.
This mirrors the FU13 pattern from ``test_llm_provider_anthropic_thinking.py``.

Test-order safety: every test does a late-bound ``from components import
llm_provider as mod`` and resolves ``AnthropicProvider`` / ``GeminiProvider``
/ ``LLMResponse`` through ``mod`` so a re-import in a sibling test file
doesn't strand our references on a stale module object. See
``test_llm_provider_anthropic_thinking.py``'s ``_live_module()`` docstring
for the full rationale.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


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


def _live_module():
    """Return the CURRENT ``components.llm_provider`` module object.

    Late-bound to defend against ``test_llm_provider.TestModuleImportIsLight``
    re-importing the module mid-suite — see the docstring on the FU13 helper
    of the same name in ``test_llm_provider_anthropic_thinking.py``.
    """
    import importlib
    return importlib.import_module("components.llm_provider")


# ---------------------------------------------------------------------------
# P2-1 — dual cache breakpoint when messages_split provided
# ---------------------------------------------------------------------------


class TestDualCacheBreakpointFromMessagesSplit:
    """``messages_split`` rewrites ``messages[0]`` into a structured-content
    list whose first block carries ``cache_control``."""

    def test_dual_cache_breakpoint_when_messages_split(self):
        mod = _live_module()
        AnthropicProvider = mod.AnthropicProvider
        AnthropicProvider._NO_TEMPERATURE_DISCOVERED.clear()

        create = _ok_create_mock()
        provider = AnthropicProvider(api_key="test")
        provider._client = _make_fake_client(create)

        stable_prefix = "OCSF schema + reference Lua + samples..."
        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": stable_prefix}],
                model="claude-haiku-4-5-20251001",  # haiku to skip thinking
                max_tokens=4096,
                temperature=0.0,
                cache_breakpoints=True,
                messages_split={
                    "stable_prefix": stable_prefix,
                    "delta_first_message": "",
                },
            )
        )

        kwargs = create.call_args.kwargs
        wire_messages = kwargs["messages"]
        assert isinstance(wire_messages, list) and len(wire_messages) == 1
        first = wire_messages[0]
        assert first["role"] == "user"
        # Content is now a list of structured blocks, not a raw string.
        assert isinstance(first["content"], list)
        assert len(first["content"]) == 1
        block = first["content"][0]
        assert block["type"] == "text"
        assert block["text"] == stable_prefix
        assert block["cache_control"] == {"type": "ephemeral"}

    def test_dual_cache_breakpoint_with_nonempty_delta(self):
        """Two-block content list when delta_first_message is non-empty:
        stable prefix carries cache_control, delta does NOT (it's
        per-iteration-volatile)."""
        mod = _live_module()
        AnthropicProvider = mod.AnthropicProvider
        AnthropicProvider._NO_TEMPERATURE_DISCOVERED.clear()

        create = _ok_create_mock()
        provider = AnthropicProvider(api_key="test")
        provider._client = _make_fake_client(create)

        stable_prefix = "STABLE-PREFIX-CONTENT"
        delta = "DELTA-PER-ITERATION"
        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": stable_prefix + delta}],
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                temperature=0.0,
                cache_breakpoints=True,
                messages_split={
                    "stable_prefix": stable_prefix,
                    "delta_first_message": delta,
                },
            )
        )

        kwargs = create.call_args.kwargs
        wire_messages = kwargs["messages"]
        first_content = wire_messages[0]["content"]
        assert isinstance(first_content, list)
        assert len(first_content) == 2
        # Block 0: stable prefix WITH cache_control.
        assert first_content[0]["type"] == "text"
        assert first_content[0]["text"] == stable_prefix
        assert first_content[0]["cache_control"] == {"type": "ephemeral"}
        # Block 1: delta WITHOUT cache_control.
        assert first_content[1]["type"] == "text"
        assert first_content[1]["text"] == delta
        assert "cache_control" not in first_content[1]

    def test_single_cache_breakpoint_when_messages_unsplit_backcompat(self):
        """No ``messages_split`` -> existing single-block behavior preserved.
        ``messages[0]`` flows through as the original string-content dict."""
        mod = _live_module()
        AnthropicProvider = mod.AnthropicProvider
        AnthropicProvider._NO_TEMPERATURE_DISCOVERED.clear()

        create = _ok_create_mock()
        provider = AnthropicProvider(api_key="test")
        provider._client = _make_fake_client(create)

        original = "raw user content as a plain string"
        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": original}],
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                temperature=0.0,
                cache_breakpoints=True,
                # No messages_split.
            )
        )

        kwargs = create.call_args.kwargs
        wire_messages = kwargs["messages"]
        assert wire_messages == [{"role": "user", "content": original}]


# ---------------------------------------------------------------------------
# cache_breakpoints_used reporting
# ---------------------------------------------------------------------------


class TestCacheBreakpointsUsedField:
    """``LLMResponse.cache_breakpoints_used`` reports the count of
    cache_control blocks the provider attached on the wire."""

    def test_cache_breakpoints_used_reports_2_when_split(self):
        mod = _live_module()
        AnthropicProvider = mod.AnthropicProvider
        AnthropicProvider._NO_TEMPERATURE_DISCOVERED.clear()

        create = _ok_create_mock()
        provider = AnthropicProvider(api_key="test")
        provider._client = _make_fake_client(create)

        stable_prefix = "X" * 100
        resp = _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": stable_prefix}],
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                temperature=0.0,
                cache_breakpoints=True,
                messages_split={
                    "stable_prefix": stable_prefix,
                    "delta_first_message": "",
                },
            )
        )

        # System block (1) + first-user-stable block (1) = 2.
        assert resp.cache_breakpoints_used == 2

    def test_cache_breakpoints_used_reports_1_when_unsplit(self):
        mod = _live_module()
        AnthropicProvider = mod.AnthropicProvider
        AnthropicProvider._NO_TEMPERATURE_DISCOVERED.clear()

        create = _ok_create_mock()
        provider = AnthropicProvider(api_key="test")
        provider._client = _make_fake_client(create)

        resp = _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": "x"}],
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                temperature=0.0,
                cache_breakpoints=True,
                # No messages_split.
            )
        )

        # Only the system block has cache_control on the legacy path.
        assert resp.cache_breakpoints_used == 1


# ---------------------------------------------------------------------------
# Backwards-compatibility — split ignored when caching disabled
# ---------------------------------------------------------------------------


class TestMessagesSplitIgnoredWhenCachingDisabled:
    def test_messages_split_ignored_when_cache_breakpoints_false(self):
        """``cache_breakpoints=False`` skips both system AND messages-level
        cache_control. ``messages_split`` is silently ignored."""
        mod = _live_module()
        AnthropicProvider = mod.AnthropicProvider
        AnthropicProvider._NO_TEMPERATURE_DISCOVERED.clear()

        create = _ok_create_mock()
        provider = AnthropicProvider(api_key="test")
        provider._client = _make_fake_client(create)

        original = "raw content"
        _run(
            provider.agenerate(
                system="sys",
                messages=[{"role": "user", "content": original}],
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                temperature=0.0,
                cache_breakpoints=False,
                messages_split={
                    "stable_prefix": "anything",
                    "delta_first_message": "",
                },
            )
        )

        kwargs = create.call_args.kwargs
        # Single-block string content preserved.
        assert kwargs["messages"] == [{"role": "user", "content": original}]
        # System wasn't wrapped either (cache_breakpoints=False).
        assert kwargs["system"] == "sys"


# ---------------------------------------------------------------------------
# Multi-turn pass-through — messages[1:] preserved exactly
# ---------------------------------------------------------------------------


class TestMultiTurnPassThrough:
    """When the iteration history grows, ``messages[1:]`` must pass through
    AS-IS — only ``messages[0]`` gets the structured-content rewrite."""

    def test_messages_after_first_passed_through_unchanged(self):
        mod = _live_module()
        AnthropicProvider = mod.AnthropicProvider
        AnthropicProvider._NO_TEMPERATURE_DISCOVERED.clear()

        create = _ok_create_mock()
        provider = AnthropicProvider(api_key="test")
        provider._client = _make_fake_client(create)

        first_content = "OCSF prompt..."
        prior_assistant = "previous lua attempt"
        refinement = "score=42, missing fields: time, severity_id"
        messages = [
            {"role": "user", "content": first_content},
            {"role": "assistant", "content": prior_assistant},
            {"role": "user", "content": refinement},
        ]
        _run(
            provider.agenerate(
                system="sys",
                messages=messages,
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                temperature=0.0,
                cache_breakpoints=True,
                messages_split={
                    "stable_prefix": first_content,
                    "delta_first_message": "",
                },
            )
        )

        kwargs = create.call_args.kwargs
        wire_messages = kwargs["messages"]
        assert len(wire_messages) == 3
        # First message rewritten to structured-content list.
        assert isinstance(wire_messages[0]["content"], list)
        assert wire_messages[0]["content"][0]["text"] == first_content
        # Subsequent turns identical to the originals.
        assert wire_messages[1] == {"role": "assistant", "content": prior_assistant}
        assert wire_messages[2] == {"role": "user", "content": refinement}


# ---------------------------------------------------------------------------
# P2-3 — Anthropic per-model output ceilings
# ---------------------------------------------------------------------------


class TestAnthropicMaxOutputTokensFor:
    def test_max_output_tokens_for_opus47_returns_32k(self):
        AnthropicProvider = _live_module().AnthropicProvider
        assert AnthropicProvider._max_output_tokens_for("claude-opus-4-7") == 32000
        # Future point releases match by prefix.
        assert (
            AnthropicProvider._max_output_tokens_for("claude-opus-4-7-20251101")
            == 32000
        )

    def test_max_output_tokens_for_sonnet46_returns_64k(self):
        AnthropicProvider = _live_module().AnthropicProvider
        assert (
            AnthropicProvider._max_output_tokens_for("claude-sonnet-4-6")
            == 64000
        )
        assert (
            AnthropicProvider._max_output_tokens_for("claude-sonnet-4-6-20251001")
            == 64000
        )

    def test_max_output_tokens_for_haiku45_returns_8192(self):
        AnthropicProvider = _live_module().AnthropicProvider
        assert (
            AnthropicProvider._max_output_tokens_for("claude-haiku-4-5")
            == 8192
        )
        assert (
            AnthropicProvider._max_output_tokens_for("claude-haiku-4-5-20251001")
            == 8192
        )

    def test_max_output_tokens_for_unknown_model_returns_default_16k(self):
        AnthropicProvider = _live_module().AnthropicProvider
        # Unknown / older model falls back to the conservative legacy default.
        assert AnthropicProvider._max_output_tokens_for("claude-3-5-sonnet") == 16000
        assert AnthropicProvider._max_output_tokens_for("") == 16000


# ---------------------------------------------------------------------------
# P2-3 — Gemini per-model output ceilings
# ---------------------------------------------------------------------------


class TestGeminiMaxOutputTokensFor:
    def test_max_output_tokens_for_gemini_25_pro_returns_65536(self):
        GeminiProvider = _live_module().GeminiProvider
        assert (
            GeminiProvider._max_output_tokens_for("gemini-2.5-pro") == 65536
        )
        # Suffix variants match.
        assert (
            GeminiProvider._max_output_tokens_for("gemini-2.5-pro-002") == 65536
        )

    def test_max_output_tokens_for_gemini_25_flash_returns_16384(self):
        GeminiProvider = _live_module().GeminiProvider
        assert (
            GeminiProvider._max_output_tokens_for("gemini-2.5-flash") == 16384
        )
        assert (
            GeminiProvider._max_output_tokens_for("gemini-2.5-flash-002")
            == 16384
        )

    def test_max_output_tokens_for_unknown_gemini_returns_default_16k(self):
        GeminiProvider = _live_module().GeminiProvider
        assert GeminiProvider._max_output_tokens_for("gemini-1.5-pro") == 16000
        assert GeminiProvider._max_output_tokens_for("") == 16000
