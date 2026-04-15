"""Stream B Phase 3.H — iterative-mode tests for unified LuaGenerator.

These tests pin the harness-feedback loop, model escalation, hard-reject
security gate, and below-threshold exhaustion behavior of
LuaGenerator._agenerate_iterative as ported from the legacy
AgenticLuaGenerator iteration body.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


# ----- shared test stubs -----


def _make_request(parser_id: str = "p1") -> Any:
    from components.lua_generator import GenerationRequest
    return GenerationRequest.from_workbench_entry({
        "parser_id": parser_id,
        "parser_name": parser_id,
        "vendor": "acme",
        "product": "auth",
        "source_fields": [{"name": "user", "type": "string"}],
        "raw_examples": ['{"user":"alice"}'],
    })


class _ScriptedHarness:
    """Returns scores from a queue, in order. Tracks calls."""

    def __init__(self, scores: List[int]):
        self._scores = list(scores)
        self.calls = 0
        self.lua_seen: List[str] = []

    def run_all_checks(self, lua_code, parser_config=None, ocsf_version="1.3.0", custom_test_events=None):
        self.calls += 1
        self.lua_seen.append(lua_code)
        score = self._scores.pop(0) if self._scores else 0
        return {
            "confidence_score": score,
            "confidence_grade": "A" if score >= 90 else "B" if score >= 70 else "D",
            "checks": {
                "lua_linting": {"issues": []},
                "ocsf_mapping": {"missing_required": [] if score >= 70 else ["activity_id"]},
                "field_comparison": {"coverage_pct": 95},
            },
        }


def _iterative_opts(max_iterations=3, target_score=70, ladder=("haiku-stub", "sonnet-stub")):
    from components.lua_generator import GenerationOptions
    return GenerationOptions(
        mode="iterative",
        max_iterations=max_iterations,
        target_score=target_score,
        escalation_ladder=list(ladder),
    )


def _build_generator(*, llm_responses, harness):
    """Build a LuaGenerator subclass that returns scripted LLM outputs and uses
    the supplied harness stub. _call_llm is overridden so no real provider is
    constructed.
    """
    from components.lua_generator import LuaGenerator

    class _SpyGenerator(LuaGenerator):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._llm_outputs = list(llm_responses)
            self.calls_made: List[Dict[str, Any]] = []
            self.harness = harness  # type: ignore[attr-defined]

        def _call_llm(self, messages, model_override=None):
            self.calls_made.append({
                "messages": list(messages),
                "model": model_override,
            })
            if not self._llm_outputs:
                return None
            return self._llm_outputs.pop(0)

    return _SpyGenerator({})


# ----- B5.1 — harness called every iteration -----


def test_iterative_mode_invokes_harness_per_iteration():
    """Mocked provider returns progressively better Lua. The harness must be
    invoked once per non-rejected iteration. We fail on the first iteration
    (score 50), pass on the second (score 85)."""
    harness = _ScriptedHarness(scores=[50, 85])
    gen = _build_generator(
        llm_responses=[
            "function processEvent(event)\n  return event\nend\n",
            "function processEvent(event)\n  -- v2\n  return event\nend\n",
        ],
        harness=harness,
    )
    req = _make_request()
    result = gen.generate(req, _iterative_opts(max_iterations=3))

    assert harness.calls == 2, f"expected harness called twice, got {harness.calls}"
    assert result.quality == "accepted"
    assert result.confidence_score == 85
    assert result.iterations == 2


# ----- B5.2 — escalation on low score -----


def test_iterative_mode_escalates_on_low_score():
    """First model exhausts iterations at score 60; escalate to next model
    which scores 85 and is accepted."""
    harness = _ScriptedHarness(scores=[60, 60, 85])
    gen = _build_generator(
        llm_responses=[
            "function processEvent(event)\n  return event\nend\n",
            "function processEvent(event)\n  -- r2\n  return event\nend\n",
            "function processEvent(event)\n  -- strong\n  return event\nend\n",
        ],
        harness=harness,
    )
    req = _make_request()
    result = gen.generate(
        req, _iterative_opts(max_iterations=2, ladder=("model-a", "model-b")),
    )

    assert result.quality == "accepted"
    assert result.confidence_score == 85
    assert result["model"] == "model-b"
    models_seen = [c["model"] for c in gen.calls_made]
    assert "model-a" in models_seen and "model-b" in models_seen
    # model-a runs to its iteration cap, then model-b
    assert models_seen.index("model-b") > models_seen.index("model-a")


# ----- B5.3 — max_iterations cap honored -----


def test_iterative_mode_respects_max_iterations():
    """All harness scores < threshold; verify exactly max_iterations LLM calls
    per ladder step."""
    harness = _ScriptedHarness(scores=[50] * 10)
    gen = _build_generator(
        llm_responses=["function processEvent(event)\n  return event\nend\n"] * 10,
        harness=harness,
    )
    req = _make_request()
    result = gen.generate(
        req, _iterative_opts(max_iterations=2, ladder=("only-model",)),
    )

    assert len(gen.calls_made) == 2
    assert harness.calls == 2
    assert result.quality == "below_threshold"


# ----- B5.4 — hard-reject security gate -----


def test_iterative_mode_hard_rejects_dangerous_lua():
    """Provider returns Lua containing os.execute. The hard-reject path must
    fire BEFORE the harness; the next iteration receives a refinement prompt
    with the rejection reason; the harness is not invoked on the rejected Lua.
    """
    harness = _ScriptedHarness(scores=[85])  # only the second (clean) iter scores
    dangerous = (
        "function processEvent(event)\n"
        "  os.execute('id')\n"
        "  return event\n"
        "end\n"
    )
    clean = "function processEvent(event)\n  return event\nend\n"
    gen = _build_generator(
        llm_responses=[dangerous, clean],
        harness=harness,
    )
    req = _make_request()
    result = gen.generate(req, _iterative_opts(max_iterations=3))

    # Only the clean iteration reaches the harness.
    assert harness.calls == 1
    # The second LLM call must have a refinement message mentioning the rejection.
    assert len(gen.calls_made) == 2
    second_msgs = gen.calls_made[1]["messages"]
    refinement_text = " ".join(
        m.get("content", "") for m in second_msgs if isinstance(m, dict)
    )
    assert "REJECTED" in refinement_text or "rejected" in refinement_text.lower()
    assert "os.execute" in refinement_text or "forbidden" in refinement_text.lower()
    assert result.quality == "accepted"
    assert result.confidence_score == 85


# ----- B5.5 — exhaustion returns below_threshold with best model -----


def test_iterative_mode_returns_below_threshold_on_exhaustion():
    """All models, all iterations < threshold. quality must be below_threshold,
    model must be populated with the best iteration's model id, harness_report
    populated, success=True (soft failure)."""
    # First model peaks at 50, second model peaks at 65 — second is best
    harness = _ScriptedHarness(scores=[40, 50, 60, 65])
    gen = _build_generator(
        llm_responses=["function processEvent(event)\n  return event\nend\n"] * 4,
        harness=harness,
    )
    req = _make_request()
    result = gen.generate(
        req,
        _iterative_opts(max_iterations=2, target_score=70, ladder=("ma", "mb")),
    )

    assert result.quality == "below_threshold"
    assert result.success is True
    assert result["model"] == "mb"  # best score came from second model
    assert result.confidence_score == 65
    assert result.harness_report is not None
    assert result.iterations == 4
