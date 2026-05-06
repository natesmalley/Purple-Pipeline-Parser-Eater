"""FU14 P2-1 + P2-3 — LuaGenerator ``messages_split`` plumbing.

Two concerns exercised here, all mocked:

  P2-1  ``LuaGenerator._build_iteration_messages_split`` returns the dict
        ``{"stable_prefix": str, "delta_first_message": str}`` (or ``None``
        when no split is meaningful), and the iteration body forwards the
        result through ``_call_llm`` -> ``_invoke_provider`` ->
        ``provider.agenerate``.

        Caller invariant (byte-equal):
            messages[0]["content"] == stable_prefix + delta_first_message

  P2-3  ``LuaGenerator._call_llm``'s truncation-retry now consults the
        provider's ``_max_output_tokens_for(model)`` instead of hardcoding
        the 16k cap. With a fake provider exposing 32k we expect the bumped
        ``max_tokens`` to land at the 32k ceiling on opus-4-7, not 16k.

No live provider calls — every test injects a fake provider via the
``provider=`` constructor kwarg or by overriding ``_invoke_provider`` /
``_call_llm`` directly.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# _build_iteration_messages_split — pure-function shape + invariants
# ---------------------------------------------------------------------------


class TestBuildIterationMessagesSplit:
    """Static-helper coverage. No provider involvement."""

    def test_build_iteration_messages_split_returns_dict_with_two_keys(self):
        from components.lua_generator import LuaGenerator
        first_content = "X" * 9000  # > default 8192 threshold (Haiku-tuned)
        out = LuaGenerator._build_iteration_messages_split(
            [{"role": "user", "content": first_content}]
        )
        assert isinstance(out, dict)
        assert set(out.keys()) == {"stable_prefix", "delta_first_message"}
        assert out["stable_prefix"] == first_content
        assert out["delta_first_message"] == ""

    def test_caller_invariant_concat_equals_first_message_content(self):
        """For ANY input that passes the threshold, the byte-equal invariant
        holds: ``messages[0]['content'] == stable_prefix + delta_first_message``.
        """
        from components.lua_generator import LuaGenerator
        for content in [
            "A" * 8192,
            "B" * 9000,
            "complex content with newlines\nand tabs\t and unicode β" * 400,
        ]:
            messages = [{"role": "user", "content": content}]
            out = LuaGenerator._build_iteration_messages_split(messages)
            assert out is not None, f"Expected split for content of length {len(content)}"
            recovered = out["stable_prefix"] + out["delta_first_message"]
            assert recovered == content, (
                "byte-equal caller invariant violated: "
                "stable_prefix + delta_first_message must reconstruct "
                "messages[0]['content']"
            )

    def test_split_returns_none_when_first_message_below_threshold(self):
        from components.lua_generator import LuaGenerator
        out = LuaGenerator._build_iteration_messages_split(
            [{"role": "user", "content": "tiny prompt"}]
        )
        assert out is None

    def test_split_returns_none_when_first_message_below_haiku_threshold(self):
        """4096-char content (~1024 tokens) should NOT trigger a split.

        DA-FU14 caught: the prior 4096-char default approximated 1024
        tokens — half of Haiku's 2048-token cache eligibility minimum.
        Anthropic accepted the cache_control block but never wrote it,
        producing zero cache benefit on the daemon's default path. The
        new 8192 default clears Haiku's floor so 4096 is now firmly below
        threshold.
        """
        from components.lua_generator import LuaGenerator
        messages = [{"role": "user", "content": "x" * 4096}]
        out = LuaGenerator._build_iteration_messages_split(messages)
        assert out is None  # below the 8192 threshold

    def test_split_returns_dict_at_8192_chars(self):
        """8192 chars = ~2048 tokens = exactly Haiku's cache-eligibility
        minimum. The boundary case must produce a split (>= comparison)."""
        from components.lua_generator import LuaGenerator
        messages = [{"role": "user", "content": "x" * 8192}]
        out = LuaGenerator._build_iteration_messages_split(messages)
        assert out is not None
        assert out["stable_prefix"] == "x" * 8192
        assert out["delta_first_message"] == ""

    def test_split_returns_none_for_empty_messages_list(self):
        from components.lua_generator import LuaGenerator
        assert LuaGenerator._build_iteration_messages_split([]) is None

    def test_split_returns_none_when_first_content_not_string(self):
        """Defensive: if ``messages[0]['content']`` is already a structured
        list (e.g. another caller pre-built it), don't try to slice it."""
        from components.lua_generator import LuaGenerator
        messages = [{"role": "user", "content": [{"type": "text", "text": "x"}]}]
        assert LuaGenerator._build_iteration_messages_split(messages) is None

    def test_split_returns_none_when_first_message_not_dict(self):
        from components.lua_generator import LuaGenerator
        # Defensive: malformed input.
        assert (
            LuaGenerator._build_iteration_messages_split(["not a dict"])  # type: ignore[list-item]
            is None
        )


# ---------------------------------------------------------------------------
# _invoke_provider forwards messages_split to provider.agenerate
# ---------------------------------------------------------------------------


def _build_generator_with_fake_provider(*, agenerate_return=None):
    """Construct a LuaGenerator with a stubbed provider whose
    ``agenerate`` is a MagicMock we can read back."""
    from components.lua_generator import LuaGenerator
    from components.llm_provider import LLMResponse

    class _FakeProvider:
        name = "fake"

        def __init__(self):
            self.agenerate = MagicMock()
            self._set_default_return(agenerate_return)

        def _set_default_return(self, ret):
            async def _coro(**kwargs):
                self.agenerate.last_kwargs = kwargs
                return ret if ret is not None else LLMResponse(
                    text="ok", model=kwargs.get("model", ""), provider="fake",
                )
            # MagicMock with side_effect of an awaitable factory.
            self.agenerate.side_effect = lambda **kw: _coro(**kw)

    fake = _FakeProvider()
    gen = LuaGenerator({}, provider=fake)
    # Stub the system-prompt build so we don't drag in OCSF schema loading.
    gen._build_system_prompt = lambda: "stub system"  # type: ignore[method-assign]
    return gen, fake


class TestInvokeProviderForwardsMessagesSplit:
    def test_invoke_provider_forwards_messages_split_to_provider(self):
        gen, fake = _build_generator_with_fake_provider()
        split = {"stable_prefix": "STABLE", "delta_first_message": ""}
        gen._invoke_provider(
            messages=[{"role": "user", "content": "STABLE"}],
            model_override="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages_split=split,
        )
        # The fake's agenerate was called with messages_split=split.
        kwargs = fake.agenerate.last_kwargs
        assert kwargs.get("messages_split") == split

    def test_invoke_provider_omits_messages_split_when_none(self):
        gen, fake = _build_generator_with_fake_provider()
        gen._invoke_provider(
            messages=[{"role": "user", "content": "x"}],
            model_override="claude-haiku-4-5-20251001",
            max_tokens=4096,
            # messages_split unset
        )
        kwargs = fake.agenerate.last_kwargs
        # Forwarded but as None — preserves the existing single-block path.
        assert kwargs.get("messages_split") is None


# ---------------------------------------------------------------------------
# _call_llm forwards messages_split to _invoke_provider
# ---------------------------------------------------------------------------


class TestCallLlmForwardsMessagesSplit:
    def test_call_llm_forwards_messages_split_to_invoke_provider(self):
        from components.lua_generator import LuaGenerator
        from components.llm_provider import LLMResponse

        captured: Dict[str, Any] = {}

        class _Spy(LuaGenerator):
            def _invoke_provider(self, messages, model_override, max_tokens, **kw):
                captured["messages_split"] = kw.get("messages_split")
                captured["max_tokens"] = max_tokens
                return LLMResponse(
                    text="ok", model="m", provider="fake", finish_reason="end_turn",
                )

        gen = _Spy({})
        split = {"stable_prefix": "S", "delta_first_message": ""}
        gen._call_llm(
            messages=[{"role": "user", "content": "S"}],
            model_override="claude-haiku-4-5-20251001",
            messages_split=split,
        )
        assert captured["messages_split"] == split


# ---------------------------------------------------------------------------
# Truncation retry consults provider._max_output_tokens_for
# ---------------------------------------------------------------------------


class TestTruncationRetryUsesProviderCeiling:
    def test_lua_generator_truncation_retry_uses_provider_ceiling(self):
        """When ``response.is_truncated()`` fires on attempt 1, the bumped
        ``max_tokens`` must come from ``provider._max_output_tokens_for(model)``,
        not the legacy hardcoded 16k cap.

        We pass max_tokens=8192. Doubled = 16384. With a 32k ceiling, the
        bumped value should land at 16384 (within ceiling). With a legacy
        16k cap, it would have been clamped to 16000 — so we use a smaller
        starting max_tokens that, when doubled, exceeds 16k AND is below
        the ceiling we want to verify.

        Concretely: max_tokens=10000 -> doubled=20000. With ceiling=32000,
        bumped should be 20000. With the legacy 16k cap it would have been
        16000. The 20000 result PROVES we read the provider ceiling.
        """
        from components.lua_generator import LuaGenerator
        from components.llm_provider import LLMResponse

        truncated_resp = LLMResponse(
            text="partial", model="claude-opus-4-7", provider="anthropic",
            finish_reason="max_tokens",
        )
        good_resp = LLMResponse(
            text="ok", model="claude-opus-4-7", provider="anthropic",
            finish_reason="end_turn",
        )

        captured_max_tokens: List[int] = []

        class _FakeProvider:
            name = "anthropic"

            @classmethod
            def _max_output_tokens_for(cls, model: str) -> int:
                return 32000  # mimic Anthropic opus-4-7

            async def agenerate(self, **kwargs):
                captured_max_tokens.append(kwargs["max_tokens"])
                # First call truncated, second returns ok.
                if len(captured_max_tokens) == 1:
                    return truncated_resp
                return good_resp

        gen = LuaGenerator({}, provider=_FakeProvider())
        gen._build_system_prompt = lambda: "stub"  # type: ignore[method-assign]
        gen.max_tokens = 10000

        result = gen._call_llm(
            messages=[{"role": "user", "content": "x"}],
            model_override="claude-opus-4-7",
        )

        assert result == "ok"
        assert len(captured_max_tokens) == 2
        # Attempt 1: original.
        assert captured_max_tokens[0] == 10000
        # Attempt 2: doubled, NOT clamped to 16k, since the provider
        # advertises a 32k ceiling. Old behavior would have clamped to 16000.
        assert captured_max_tokens[1] == 20000

    def test_lua_generator_truncation_retry_clamps_at_provider_ceiling(self):
        """When the doubled value exceeds the provider's ceiling, it clamps
        AT the ceiling (not at the legacy 16k)."""
        from components.lua_generator import LuaGenerator
        from components.llm_provider import LLMResponse

        truncated_resp = LLMResponse(
            text="partial", model="claude-haiku-4-5", provider="anthropic",
            finish_reason="max_tokens",
        )
        good_resp = LLMResponse(
            text="ok", model="claude-haiku-4-5", provider="anthropic",
            finish_reason="end_turn",
        )
        captured: List[int] = []

        class _FakeProvider:
            name = "anthropic"

            @classmethod
            def _max_output_tokens_for(cls, model: str) -> int:
                return 8192  # mimic haiku-4-5

            async def agenerate(self, **kwargs):
                captured.append(kwargs["max_tokens"])
                return truncated_resp if len(captured) == 1 else good_resp

        gen = LuaGenerator({}, provider=_FakeProvider())
        gen._build_system_prompt = lambda: "stub"  # type: ignore[method-assign]
        gen.max_tokens = 6000

        result = gen._call_llm(
            messages=[{"role": "user", "content": "x"}],
            model_override="claude-haiku-4-5",
        )

        assert result == "ok"
        # 6000 * 2 = 12000, but ceiling is 8192 -> clamped.
        assert captured[1] == 8192

    def test_lua_generator_truncation_retry_falls_back_to_16k_without_helper(self):
        """If the provider doesn't expose ``_max_output_tokens_for`` (forward
        compat), the explicit-branch fallback returns 16000 (legacy cap)."""
        from components.lua_generator import LuaGenerator
        from components.llm_provider import LLMResponse

        truncated = LLMResponse(
            text="x", model="m", provider="custom", finish_reason="max_tokens",
        )
        good = LLMResponse(
            text="ok", model="m", provider="custom", finish_reason="end_turn",
        )
        captured: List[int] = []

        class _BareProvider:
            """No ``_max_output_tokens_for`` attr."""
            name = "custom"

            async def agenerate(self, **kwargs):
                captured.append(kwargs["max_tokens"])
                return truncated if len(captured) == 1 else good

        gen = LuaGenerator({}, provider=_BareProvider())
        gen._build_system_prompt = lambda: "stub"  # type: ignore[method-assign]
        gen.max_tokens = 10000

        gen._call_llm(messages=[{"role": "user", "content": "x"}])
        # 10000 * 2 = 20000, clamped to 16000 by the explicit fallback branch.
        assert captured[1] == 16000

    def test_truncation_retry_logs_warning_when_provider_missing_ceiling_fn(
        self, caplog,
    ):
        """DA-FU14: if a provider lacks ``_max_output_tokens_for``, the
        truncation-retry path must log a single WARNING per provider
        instance so the silent 16k regression is observable. Spam-protect
        flag prevents the warning from firing on every iteration."""
        import logging
        from components.lua_generator import LuaGenerator
        from components.llm_provider import LLMResponse

        truncated = LLMResponse(
            text="x", model="m", provider="custom", finish_reason="max_tokens",
        )
        good = LLMResponse(
            text="ok", model="m", provider="custom", finish_reason="end_turn",
        )
        call_count = {"n": 0}

        class _BareProvider:
            """No ``_max_output_tokens_for`` attr."""
            name = "custom"

            async def agenerate(self, **kwargs):
                call_count["n"] += 1
                # First call truncated, then good; subsequent calls also good.
                return truncated if call_count["n"] == 1 else good

        gen = LuaGenerator({}, provider=_BareProvider())
        gen._build_system_prompt = lambda: "stub"  # type: ignore[method-assign]
        gen.max_tokens = 10000

        # Capture logs from the lua_generator module.
        with caplog.at_level(logging.WARNING, logger="components.lua_generator"):
            gen._call_llm(messages=[{"role": "user", "content": "x"}])

        # Exactly one WARNING about the missing helper should have fired.
        missing_warnings = [
            r for r in caplog.records
            if r.levelno == logging.WARNING
            and "missing _max_output_tokens_for" in r.getMessage()
        ]
        assert len(missing_warnings) == 1, (
            f"expected exactly one missing-helper warning, got "
            f"{len(missing_warnings)}: {[r.getMessage() for r in missing_warnings]}"
        )

    def test_truncation_retry_warning_is_once_per_provider_instance(
        self, caplog,
    ):
        """The spam-protection flag (``_warned_missing_ceiling_fn``) must
        suppress the warning on subsequent truncation retries against the
        same provider instance — one signal per missing-helper provider,
        not one per iteration."""
        import logging
        from components.lua_generator import LuaGenerator
        from components.llm_provider import LLMResponse

        # Always truncate so attempt 1 of every _call_llm triggers the path.
        truncated = LLMResponse(
            text="x", model="m", provider="custom", finish_reason="max_tokens",
        )

        class _BareProvider:
            name = "custom"

            async def agenerate(self, **kwargs):
                return truncated

        gen = LuaGenerator({}, provider=_BareProvider())
        gen._build_system_prompt = lambda: "stub"  # type: ignore[method-assign]
        gen.max_tokens = 10000

        with caplog.at_level(logging.WARNING, logger="components.lua_generator"):
            # Two separate _call_llm invocations — the warning must fire only
            # on the first because the provider instance is the same.
            gen._call_llm(messages=[{"role": "user", "content": "x"}])
            gen._call_llm(messages=[{"role": "user", "content": "y"}])

        missing_warnings = [
            r for r in caplog.records
            if r.levelno == logging.WARNING
            and "missing _max_output_tokens_for" in r.getMessage()
        ]
        # Exactly one warning despite multiple truncation-retry traversals.
        assert len(missing_warnings) == 1, (
            f"expected one warning across multiple _call_llm invocations on "
            f"the same provider instance; got {len(missing_warnings)}"
        )

    def test_truncation_retry_no_warning_when_provider_has_helper(self, caplog):
        """Happy path: providers that DO expose ``_max_output_tokens_for``
        must not emit the missing-helper warning."""
        import logging
        from components.lua_generator import LuaGenerator
        from components.llm_provider import LLMResponse

        truncated = LLMResponse(
            text="x", model="claude-opus-4-7", provider="anthropic",
            finish_reason="max_tokens",
        )
        good = LLMResponse(
            text="ok", model="claude-opus-4-7", provider="anthropic",
            finish_reason="end_turn",
        )
        call_count = {"n": 0}

        class _GoodProvider:
            name = "anthropic"

            @classmethod
            def _max_output_tokens_for(cls, model: str) -> int:
                return 32000

            async def agenerate(self, **kwargs):
                call_count["n"] += 1
                return truncated if call_count["n"] == 1 else good

        gen = LuaGenerator({}, provider=_GoodProvider())
        gen._build_system_prompt = lambda: "stub"  # type: ignore[method-assign]
        gen.max_tokens = 10000

        with caplog.at_level(logging.WARNING, logger="components.lua_generator"):
            gen._call_llm(
                messages=[{"role": "user", "content": "x"}],
                model_override="claude-opus-4-7",
            )

        missing_warnings = [
            r for r in caplog.records
            if "missing _max_output_tokens_for" in r.getMessage()
        ]
        assert missing_warnings == [], (
            "no missing-helper warning expected when provider exposes the "
            f"classmethod; got: {[r.getMessage() for r in missing_warnings]}"
        )


# ---------------------------------------------------------------------------
# Iteration loop end-to-end — split is computed and reaches the provider
# ---------------------------------------------------------------------------


class TestIterationLoopComputesAndForwardsSplit:
    """End-to-end: the iteration body computes the split per-iteration and
    threads it to the provider."""

    def test_iteration_loop_passes_messages_split_to_default_call_llm(self):
        """Use a LuaGenerator subclass that overrides ``_call_llm`` with a
        kwargs-accepting signature; assert ``messages_split`` is one of the
        forwarded kwargs and that ``stable_prefix + delta`` reconstructs the
        original first-message content."""
        from components.lua_generator import (
            GenerationOptions, GenerationRequest, LuaGenerator,
        )

        # Build a long enough first prompt to clear the 8192-char threshold.
        # The iteration body builds the prompt itself via build_generation_prompt;
        # we rely on its output exceeding the threshold for typical OCSF inputs.
        captured_kwargs: List[Dict[str, Any]] = []

        class _SpyGen(LuaGenerator):
            def _call_llm(self, messages, model_override=None, **kwargs):
                captured_kwargs.append({
                    "first_content_len": len(messages[0]["content"]),
                    "messages_split": kwargs.get("messages_split"),
                })
                # Return acceptable Lua to terminate fast.
                return (
                    "function processEvent(event)\n"
                    "  return event\n"
                    "end\n"
                )

        # Stub harness so it always passes -> exits after one iteration.
        class _PassHarness:
            def run_all_checks(self, lua_code, parser_config=None,
                               ocsf_version="1.3.0", custom_test_events=None):
                return {
                    "confidence_score": 95,
                    "confidence_grade": "A",
                    "checks": {
                        "lua_linting": {"issues": []},
                        "ocsf_mapping": {"missing_required": []},
                        "field_comparison": {"coverage_pct": 95},
                    },
                }

        gen = _SpyGen({})
        gen.harness = _PassHarness()
        req = GenerationRequest.from_workbench_entry({
            "parser_id": "p1",
            "parser_name": "p1",
            "vendor": "acme",
            "product": "auth",
            "source_fields": [{"name": "user", "type": "string"}],
            "raw_examples": ['{"user":"alice"}'],
        })
        opts = GenerationOptions(
            mode="iterative",
            max_iterations=1,
            target_score=70,
            escalation_ladder=["test-model"],
        )
        gen.generate(req, opts)

        assert captured_kwargs, "expected at least one _call_llm invocation"
        first = captured_kwargs[0]
        first_len = first["first_content_len"]
        split = first["messages_split"]
        if first_len >= 8192:
            # Threshold exceeded -> split must be a dict whose concat
            # reconstructs the original first-message content length.
            assert split is not None, (
                f"expected messages_split for prompt of length {first_len}"
            )
            assert set(split.keys()) == {"stable_prefix", "delta_first_message"}
            assert (
                len(split["stable_prefix"]) + len(split["delta_first_message"])
                == first_len
            )
        else:
            # Below threshold — split is None (no behavior change). This
            # branch keeps the test robust if build_generation_prompt
            # output ever shrinks below 8192 for the minimal stub input.
            assert split is None

    def test_iteration_loop_works_with_legacy_call_llm_signature(self):
        """Legacy test stubs define ``_call_llm(self, messages, model_override=None)``
        WITHOUT ``**kwargs``. The iteration body must detect via inspect and
        skip the ``messages_split`` kwarg so back-compat with existing tests
        is preserved."""
        from components.lua_generator import (
            GenerationOptions, GenerationRequest, LuaGenerator,
        )

        class _LegacyGen(LuaGenerator):
            # Note: NO **kwargs — legacy signature.
            def _call_llm(self, messages, model_override=None):
                return (
                    "function processEvent(event)\n"
                    "  return event\n"
                    "end\n"
                )

        class _PassHarness:
            def run_all_checks(self, lua_code, parser_config=None,
                               ocsf_version="1.3.0", custom_test_events=None):
                return {
                    "confidence_score": 95,
                    "confidence_grade": "A",
                    "checks": {
                        "lua_linting": {"issues": []},
                        "ocsf_mapping": {"missing_required": []},
                        "field_comparison": {"coverage_pct": 95},
                    },
                }

        gen = _LegacyGen({})
        gen.harness = _PassHarness()
        req = GenerationRequest.from_workbench_entry({
            "parser_id": "p1",
            "parser_name": "p1",
            "vendor": "acme",
            "product": "auth",
            "source_fields": [{"name": "user", "type": "string"}],
            "raw_examples": ['{"user":"alice"}'],
        })
        opts = GenerationOptions(
            mode="iterative",
            max_iterations=1,
            target_score=70,
            escalation_ladder=["test-model"],
        )
        # Must not raise TypeError("unexpected kwarg messages_split").
        result = gen.generate(req, opts)
        assert result.confidence_score == 95
