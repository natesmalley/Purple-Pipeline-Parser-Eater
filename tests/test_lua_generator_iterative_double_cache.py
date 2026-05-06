"""FU18 DA-FU16 deferred — FU15 + FU16 double-cache integration test.

Pins the end-to-end caching contract under iterative-mode generation with
the Gemini provider:

  * **FU15 contract**: ``CachedContent.create`` (server-side context cache)
    fires exactly ONCE for a stable (model, system) tuple across all 3
    iterations of an iterative_loop_sync run.
  * **FU16 contract**: ``GenerativeModel.from_cached_content`` (Python
    object cache) ALSO fires exactly ONCE — the constructed model_obj is
    reused across iterations 2 and 3.
  * Iteration counting: ``model_obj.generate_content`` is invoked once per
    iteration (3 times across the run).

Pre-FU18 we had unit-level coverage of each cache independently
(test_llm_provider_gemini_caching.py for FU15, test_llm_provider_gemini_
model_cache.py for FU16). The DA-FU16 review flagged a missing
end-to-end verification that BOTH caches engage simultaneously through
the iteration loop — this file closes that gap.

All MOCKED. No live API calls. Mocking strategy mirrors the existing
gemini test files: inject a fake ``google.generativeai`` shape at
``provider._genai`` so ``_ensure_client()`` short-circuits without
importing the real SDK; assert directly on the mock call_count.
"""
from __future__ import annotations

import importlib
from typing import Any, Dict, List
from unittest.mock import MagicMock


def _live_module():
    """Late-bound module reference (matches the FU13/14/15/16 test pattern)."""
    return importlib.import_module("components.llm_provider")


# ---------------------------------------------------------------------------
# SDK fake shapes (subset of the FU16 model-cache test fakes)
# ---------------------------------------------------------------------------


class _FakeUsageMetadata:
    def __init__(
        self,
        prompt_token_count: int = 100,
        candidates_token_count: int = 50,
        cached_content_token_count: int = 0,
    ) -> None:
        self.prompt_token_count = prompt_token_count
        self.candidates_token_count = candidates_token_count
        self.cached_content_token_count = cached_content_token_count


class _FakeCandidate:
    finish_reason = "STOP"


class _FakeGeminiResponse:
    """Mimics ``GenerativeModel.generate_content``'s result shape."""

    def __init__(
        self,
        text: str = "function processEvent(event)\n  return event\nend\n",
        cached_content_token_count: int = 0,
    ) -> None:
        self._text = text
        self.candidates = [_FakeCandidate()]
        self.usage_metadata = _FakeUsageMetadata(
            cached_content_token_count=cached_content_token_count,
        )

    @property
    def text(self) -> str:
        return self._text


def _make_fake_genai_for_iter():
    """Build a fake ``google.generativeai`` whose ``generate_content`` returns
    a fresh response every call (so the iteration loop can re-score each).

    The iteration test asserts:
      * cached_content_create.call_count == 1 (server-side cache HIT on
        iter 2 and iter 3)
      * from_cached_content.call_count == 1 (model-obj cache HIT on iter
        2 and iter 3)
      * cached_model_instance.generate_content.call_count == 3 (one per
        iteration — the WHOLE point of caching is to reuse the model
        across many generate_content calls)
    """
    genai = MagicMock(name="genai")

    cached_obj = MagicMock(name="cached_obj")
    cached_obj.name = "cachedContents/it_xyz"

    cached_content_create = MagicMock(name="CachedContent.create")
    cached_content_create.return_value = cached_obj
    genai.caching = MagicMock(name="caching")
    genai.caching.CachedContent = MagicMock(name="CachedContent")
    genai.caching.CachedContent.create = cached_content_create

    cached_model_instance = MagicMock(name="cached_model_instance")
    # Each call returns a fresh response so the iteration loop sees three
    # distinct outputs to score; the cached_content_token_count is > 0 on
    # iters 2 and 3 to mirror real Gemini usage shape but the iteration
    # contract doesn't depend on this — what matters is call_count.
    responses = [
        _FakeGeminiResponse(cached_content_token_count=0),
        _FakeGeminiResponse(cached_content_token_count=80),
        _FakeGeminiResponse(cached_content_token_count=80),
    ]
    cached_model_instance.generate_content = MagicMock(side_effect=responses)

    uncached_model_instance = MagicMock(name="uncached_model_instance")
    uncached_model_instance.generate_content = MagicMock(
        return_value=_FakeGeminiResponse(),
    )

    generative_model = MagicMock(
        name="GenerativeModel",
        return_value=uncached_model_instance,
    )
    generative_model.from_cached_content = MagicMock(
        return_value=cached_model_instance,
    )

    genai.GenerativeModel = generative_model
    genai.configure = MagicMock()

    mocks = {
        "genai": genai,
        "cached_content_create": cached_content_create,
        "cached_obj": cached_obj,
        "GenerativeModel": generative_model,
        "from_cached_content": generative_model.from_cached_content,
        "cached_model_instance": cached_model_instance,
        "uncached_model_instance": uncached_model_instance,
    }
    return genai, mocks


def _new_gemini_provider(genai_mock):
    """Construct a GeminiProvider with both class-level caches cleared."""
    GeminiProvider = _live_module().GeminiProvider
    GeminiProvider._context_cache_index.clear()
    GeminiProvider._generative_model_cache_index.clear()
    provider = GeminiProvider(api_key="test-key")
    provider._genai = genai_mock
    return provider


def _long_system(min_chars: int = 5000) -> str:
    """System prompt big enough to clear the 2.5-flash 4096-char threshold."""
    base = (
        "You are an expert OCSF Lua transform generator. "
        "Apply patterns A-E. Inline OCSF helpers. "
    )
    n = (min_chars // len(base)) + 1
    out = base * n
    assert len(out) >= min_chars
    return out


# ---------------------------------------------------------------------------
# The integration test
# ---------------------------------------------------------------------------


class _ScriptedHarness:
    """Harness stub returning sub-threshold scores so the iteration loop
    runs the full 3 iterations (no early accept)."""

    def __init__(self, scores: List[int]) -> None:
        self._scores = list(scores)
        self.calls = 0

    def run_all_checks(
        self,
        lua_code,
        parser_config=None,
        ocsf_version="1.3.0",
        custom_test_events=None,
    ):
        self.calls += 1
        score = self._scores.pop(0) if self._scores else 0
        return {
            "confidence_score": score,
            "confidence_grade": "B" if score >= 70 else "D",
            "checks": {
                "lua_linting": {"issues": []},
                "ocsf_mapping": {
                    "missing_required": [] if score >= 70 else ["activity_id"],
                },
                "field_comparison": {"coverage_pct": 60},
            },
        }


def test_fu15_fu16_double_cache_hits_on_iter_2_and_3():
    """Three iterations on Gemini → CachedContent.create == 1, from_cached_content == 1,
    generate_content == 3.

    This pins the FU15 + FU16 caching contract through the iteration loop:
    a single (model, system) tuple should produce ONE server-side cache
    create AND ONE Python-side model construction across the entire run,
    while still issuing three distinct generate_content wire calls (one
    per iteration).
    """
    from components.lua_generator import (
        GenerationOptions,
        GenerationRequest,
        LuaGenerator,
    )

    genai, mocks = _make_fake_genai_for_iter()
    provider = _new_gemini_provider(genai)

    # Construct a generator pinned to the Gemini provider so the iteration
    # loop routes through it. We override ``_provider_override`` to bypass
    # the SettingsStore lookup that would otherwise be config-dependent.
    gen = LuaGenerator(
        config={"score_threshold": 70},
        provider=provider,
    )
    # Force a long system prompt so caching engages — the pre-built
    # SYSTEM_PROMPT is already long enough but pinning it explicitly here
    # avoids surprises if the prompt is shrunk in a future refactor.
    long_system = _long_system()
    gen._build_system_prompt = lambda: long_system  # type: ignore[method-assign]

    # Inject the harness so we don't pull in the heavy real harness.
    # All three iterations score 50 (sub-threshold) so the loop runs
    # the full max_iterations (no early accept).
    harness = _ScriptedHarness(scores=[50, 50, 50])
    gen.harness = harness

    # Stub source_analyzer so the iterative path doesn't need real parser
    # introspection; the iteration loop only calls analyze_parser once.
    gen.source_analyzer = MagicMock()
    gen.source_analyzer.analyze_parser = MagicMock(
        return_value={"fields": [{"name": "user", "type": "string"}]},
    )

    request = GenerationRequest.from_workbench_entry({
        "parser_id": "fu18_double_cache_test",
        "parser_name": "fu18_double_cache_test",
        "vendor": "acme",
        "product": "auth",
        "source_fields": [{"name": "user", "type": "string"}],
        "raw_examples": ['{"user":"alice"}'],
    })

    opts = GenerationOptions(
        mode="iterative",
        max_iterations=3,
        target_score=70,
        # Single model in the ladder — we want exactly 3 iterations on the
        # SAME model, not escalation across different models. Escalation
        # would change the cache key and create a second CachedContent,
        # which is correct behavior but not what this test pins.
        escalation_ladder=["gemini-2.5-flash"],
    )

    result = gen.generate(request, opts)

    # Sanity: 3 iterations actually ran (harness called 3 times).
    assert harness.calls == 3, (
        f"expected 3 iterations (harness calls) but got {harness.calls}"
    )

    # FU15 contract: ONE server-side CachedContent.create across the run.
    assert mocks["cached_content_create"].call_count == 1, (
        "FU15: expected exactly 1 CachedContent.create across 3 iterations "
        "(iter 2/3 should HIT the _context_cache_index); got "
        f"{mocks['cached_content_create'].call_count}"
    )

    # FU16 contract: ONE Python-side from_cached_content across the run.
    assert mocks["from_cached_content"].call_count == 1, (
        "FU16: expected exactly 1 from_cached_content across 3 iterations "
        "(iter 2/3 should HIT the _generative_model_cache_index); got "
        f"{mocks['from_cached_content'].call_count}"
    )

    # generate_content fires once per iteration — the whole point of
    # caching is to reuse the model_obj across many wire calls.
    assert mocks["cached_model_instance"].generate_content.call_count == 3, (
        "expected 3 generate_content calls (one per iteration); got "
        f"{mocks['cached_model_instance'].generate_content.call_count}"
    )

    # Sanity: the from_cached_content call wired up cached_obj correctly.
    assert (
        mocks["from_cached_content"].call_args.kwargs["cached_content"]
        is mocks["cached_obj"]
    )

    # The result quality is below_threshold (all iterations < 70) — pin so
    # an accidental harness-stub change that ramps scores doesn't silently
    # invalidate the "3 iterations actually ran" assumption.
    assert result.quality == "below_threshold"
