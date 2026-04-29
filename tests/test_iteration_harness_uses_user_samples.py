"""Regression tests for the harness scoring divergence fix.

Plan: C:/Users/hexideciml/.claude/plans/abundant-munching-hanrahan.md

Pre-fix bug: ``LuaGenerator._run_iterative_loop_sync`` called the harness
without ``custom_test_events``, so iteration scored against synthetic
events while the post-generation route re-score used the user's pasted
samples. Result: the model iterated to 71 on imaginary events, the cache
locked it at 71, and the UI showed a 51 re-score against actual samples
— with no feedback path back into the iteration loop.

Post-fix:
- ``parser_workbench`` normalises user samples and stuffs them into
  ``parser_entry["_iter_test_events"]``.
- ``_run_iterative_loop_sync`` reads that key and passes it as
  ``custom_test_events`` to the harness, so iteration scores against the
  same events the UI displays.
- ``AgenticLuaGenerator.generate`` bypasses the output cache when
  ``parser_entry`` carries user samples (raw_examples or
  _iter_test_events), so workbench runs always do a fresh LLM call.
- The daemon path (no raw_examples) keeps caching unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from components.agentic_lua_generator import AgenticLuaGenerator, AgentLuaCache


# ---------------------------------------------------------------------------
# Stubs shared across the four tests below.
# ---------------------------------------------------------------------------


class _CapturingHarness:
    """Records every kwarg passed to run_all_checks for later assertions."""

    def __init__(self, score: int = 85):
        self._score = score
        self.calls: List[Dict[str, Any]] = []

    def run_all_checks(self, lua_code, parser_config, ocsf_version="1.3.0", custom_test_events=None):
        self.calls.append({
            "lua_code": lua_code,
            "parser_config": parser_config,
            "ocsf_version": ocsf_version,
            "custom_test_events": custom_test_events,
        })
        return {
            "confidence_score": self._score,
            "confidence_grade": "B",
            "checks": {
                "field_comparison": {"coverage_pct": 90},
                "lua_linting": {"issues": []},
                "ocsf_mapping": {
                    "missing_required": [],
                    "class_uid": 3002,
                    "class_name": "Authentication",
                },
            },
            "ocsf_alignment": {"required_coverage": 100.0},
        }


class _StubSourceAnalyzer:
    def analyze_parser(self, parser_entry):
        return {"fields": [{"name": "user", "type": "string"}]}


# ---------------------------------------------------------------------------
# Tests 1 & 2 — iteration harness threads user samples (or None) through.
# ---------------------------------------------------------------------------


class TestIterationHarnessReceivesUserSamples:
    """Plan/Change 2 verification: iteration must use the same events the
    UI shows, OR the daemon's synthetic fallback when no samples present."""

    def _build_generator(self):
        from components.lua_generator import LuaGenerator
        return LuaGenerator(config={
            "anthropic": {"api_key": "test-key", "model": "claude-haiku-4-5-20251001"},
            "score_threshold": 70,
        })

    def test_iteration_harness_receives_user_samples_when_present(self):
        """When parser_entry carries _iter_test_events, the iteration
        harness call must receive that exact list as custom_test_events."""
        from components.lua_generator import GenerationOptions, GenerationRequest

        user_events = [
            {"name": "user_example_1", "event": {"src_ip": "10.0.0.1", "msg": "hello"}},
        ]
        captured_lua = []

        def capturing_llm_call(messages, model_override=None):
            captured_lua.append(messages)
            return "function processEvent(event)\n  return event\nend"

        harness = _CapturingHarness(score=85)
        gen = self._build_generator()
        gen._run_iterative_loop_sync(
            request=GenerationRequest.from_workbench_entry({
                "parser_id": "p1",
                "parser_name": "p1",
                "vendor": "v",
                "product": "p",
                "source_fields": [{"name": "src_ip", "type": "string"}],
                "raw_examples": [{"src_ip": "10.0.0.1", "msg": "hello"}],
                "_iter_test_events": user_events,
            }),
            opts=GenerationOptions(mode="iterative", max_iterations=1, target_score=70),
            parser_entry={
                "parser_name": "p1",
                "raw_examples": [{"src_ip": "10.0.0.1", "msg": "hello"}],
                "_iter_test_events": user_events,
            },
            harness=harness,
            source_analyzer=_StubSourceAnalyzer(),
            llm_call=capturing_llm_call,
        )

        assert harness.calls, "harness was never invoked — iteration loop did not run"
        first_call = harness.calls[0]
        assert first_call["custom_test_events"] is user_events, (
            "iteration harness must receive the exact _iter_test_events list "
            "from parser_entry, not None or a fresh copy"
        )

    def test_iteration_harness_falls_back_to_synthetic_when_no_user_samples(self):
        """Daemon path regression gate: when _iter_test_events is absent,
        the harness must receive custom_test_events=None so the harness's
        own Jarvis/synthetic fallback chain runs."""
        from components.lua_generator import GenerationOptions, GenerationRequest

        def llm_call(messages, model_override=None):
            return "function processEvent(event)\n  return event\nend"

        harness = _CapturingHarness(score=85)
        gen = self._build_generator()
        gen._run_iterative_loop_sync(
            request=GenerationRequest.from_workbench_entry({
                "parser_id": "p2",
                "parser_name": "p2",
                "vendor": "v",
                "product": "p",
                "source_fields": [{"name": "src_ip", "type": "string"}],
            }),
            opts=GenerationOptions(mode="iterative", max_iterations=1, target_score=70),
            parser_entry={"parser_name": "p2"},  # no _iter_test_events
            harness=harness,
            source_analyzer=_StubSourceAnalyzer(),
            llm_call=llm_call,
        )

        assert harness.calls, "harness was never invoked"
        assert harness.calls[0]["custom_test_events"] is None, (
            "daemon path must pass custom_test_events=None so the harness "
            "falls back to its Jarvis/synthetic event chain"
        )


# ---------------------------------------------------------------------------
# Tests 3 & 4 — cache bypass logic.
# ---------------------------------------------------------------------------


class _DummyHarness:
    def run_all_checks(self, lua_code, parser_config, ocsf_version="1.3.0", custom_test_events=None):
        return {
            "confidence_score": 85,
            "confidence_grade": "B",
            "checks": {
                "field_comparison": {"coverage_pct": 90},
                "lua_linting": {"issues": []},
                "ocsf_mapping": {
                    "missing_required": [],
                    "class_uid": 3002,
                    "class_name": "Authentication",
                },
            },
            "ocsf_alignment": {"required_coverage": 100.0},
        }


class _BypassTestGenerator(AgenticLuaGenerator):
    """Subclass that captures whether a fresh LLM call ran by stubbing
    the inner _run_iterative_loop_sync surface. Lets us test the
    cache-bypass logic in AgenticLuaGenerator.generate without booting a
    real LLM."""

    def __init__(self, cache_dir: Path, marker_lua: str = "function processEvent(event)\n  return 'FRESH_RUN' end"):
        # Bypass the parent constructor — we don't need the real init for
        # the cache-bypass test surface.
        self.provider = "anthropic"
        self.model = "claude-haiku-4-5-20251001"
        self.score_threshold = 70
        self.max_iterations = 1
        self.cache = AgentLuaCache(cache_dir=cache_dir)
        self.harness = _DummyHarness()
        self.source_analyzer = _StubSourceAnalyzer()
        self._marker_lua = marker_lua
        self.fresh_calls = 0
        # A real _inner is required because generate() delegates to
        # _inner._run_iterative_loop_sync. We synthesise a minimal stub
        # that returns a successful result without invoking the LLM.
        outer = self

        class _InnerStub:
            def _run_iterative_loop_sync(self, *, request, opts, parser_entry, llm_call, harness, source_analyzer):
                from components.lua_generator import GenerationResult
                outer.fresh_calls += 1
                return GenerationResult(
                    parser_id=request.parser_id,
                    parser_name=request.parser_name,
                    lua_code=outer._marker_lua,
                    test_cases="",
                    performance_metrics={},
                    memory_analysis="",
                    deployment_notes="",
                    monitoring_recommendations=[],
                    generated_at="2026-04-29T00:00:00Z",
                    confidence_score=85.0,
                    confidence_grade="B",
                    iterations=1,
                    quality="accepted",
                    model="claude-haiku-4-5-20251001",
                    ocsf_class_uid=3002,
                    ocsf_class_name="Authentication",
                    success=True,
                )

        self._inner = _InnerStub()

    def _call_llm(self, messages, model_override=None):
        # Defensive — should never be reached because _inner stub
        # short-circuits before _call_llm is invoked.
        self.fresh_calls += 1
        return self._marker_lua


class TestCacheBypassWhenUserSamplesPresent:
    """Plan/Change 3 verification: cache bypass when raw_examples or
    _iter_test_events present; daemon path keeps caching."""

    def test_workbench_bypasses_cache_when_raw_examples_present(self, tmp_path):
        """Pre-populate the cache with a known stale entry. Call generate
        with raw_examples present. Assert the fresh marker Lua wins
        (proving the LLM call ran) and the stale cache entry was NOT
        returned."""
        cache_dir = tmp_path / "cache"
        gen = _BypassTestGenerator(cache_dir=cache_dir, marker_lua="function processEvent(event)\n  return 'FRESH_RUN' end")
        # Seed the cache with a stale entry that scores above threshold.
        # Pre-fix this would have short-circuited and returned STALE_LUA.
        gen.cache.put("awsroute53", {
            "parser_name": "awsroute53",
            "lua_code": "function processEvent(event)\n  return 'STALE_LUA'\nend",
            "confidence_score": 99,
            "confidence_grade": "A",
        })

        result = gen.generate(
            {
                "parser_name": "awsroute53",
                "raw_examples": [{"qname": "example.com"}],
            },
            force_regenerate=False,
        )

        assert "FRESH_RUN" in result["lua_code"], (
            "cache bypass failed — generate returned the stale cached blob "
            "instead of running a fresh LLM call. With raw_examples present "
            "the cache lookup must be skipped."
        )
        assert "STALE_LUA" not in result["lua_code"]
        assert gen.fresh_calls >= 1, "no fresh LLM call ran"

    def test_daemon_path_still_caches(self, tmp_path):
        """Regression gate for the daemon's batch flow: when no user
        samples are present, the cache lookup must still fire and a
        good cached blob must short-circuit before the LLM is called."""
        cache_dir = tmp_path / "cache"
        gen = _BypassTestGenerator(cache_dir=cache_dir, marker_lua="function processEvent(event)\n  return 'FRESH_RUN' end")
        # Cached blob scores above threshold and contains processEvent —
        # both conditions required for cache hit.
        gen.cache.put("okta_logs", {
            "parser_name": "okta_logs",
            "lua_code": "function processEvent(event)\n  return 'CACHED_LUA'\nend",
            "confidence_score": 99,
            "confidence_grade": "A",
        })

        result = gen.generate(
            {
                "parser_name": "okta_logs",
                # NO raw_examples, NO _iter_test_events — daemon shape
            },
            force_regenerate=False,
        )

        assert "CACHED_LUA" in result["lua_code"], (
            "cache hit failed — daemon path must still benefit from the "
            "output cache when no user samples are passed."
        )
        assert "FRESH_RUN" not in result["lua_code"]
        assert gen.fresh_calls == 0, (
            "fresh LLM call ran on the daemon path — cache should have "
            "short-circuited before the inner runtime was invoked."
        )


# ---------------------------------------------------------------------------
# Review fold-back tests (post-team-review fixes).
# ---------------------------------------------------------------------------


class TestParserWorkbenchPopulatesIterTestEvents:
    """QA gap surfaced by the review team: the original 4 tests assert
    AT the iteration boundary that custom_test_events arrives. They do
    NOT assert that ParserLuaWorkbench actually populates the key on
    the entry dict before agent.generate(). A future refactor that drops
    those lines in parser_workbench.py would let all 4 prior tests stay
    green while the bug returns. Pin both producer call sites here.
    """

    def _capturing_workbench(self, tmp_path):
        """Build a real ParserLuaWorkbench with a dummy agent that
        records the entry dict it receives."""
        from components.web_ui.parser_workbench import ParserLuaWorkbench

        captured: List[Dict[str, Any]] = []

        class _FakeAgent:
            def generate(self, entry, force_regenerate=False):
                # Defensive deep-snapshot — we want the dict shape AT
                # the boundary, not after any later mutation.
                captured.append({k: v for k, v in entry.items()})
                return {
                    "lua_code": "function processEvent(event)\n  return event\nend",
                    "confidence_score": 80,
                    "confidence_grade": "B",
                    "iterations": 1,
                    "ocsf_class_name": "Authentication",
                    "ingestion_mode": "push",
                    "examples_used": 1,
                    "harness_report": {},
                    "quality": "accepted",
                }

        wb = ParserLuaWorkbench(repo_root=tmp_path)
        wb.lua_dir = tmp_path / "lua"
        wb.lua_dir.mkdir(parents=True, exist_ok=True)
        wb._agent = _FakeAgent()
        return wb, captured

    def test_build_from_raw_examples_sets_iter_test_events(self, tmp_path):
        """Producer-side regression gate for build_from_raw_examples."""
        from components.lua_generator import ITER_TEST_EVENTS_KEY

        wb, captured = self._capturing_workbench(tmp_path)
        wb.build_from_raw_examples(
            parser_name="aws_route53",
            raw_examples=[{"qname": "example.com", "client_ip": "1.2.3.4"}],
        )

        assert captured, "agent.generate was never called"
        entry = captured[0]
        assert ITER_TEST_EVENTS_KEY in entry, (
            "build_from_raw_examples must populate _iter_test_events on the "
            "entry dict before agent.generate(...)"
        )
        events = entry[ITER_TEST_EVENTS_KEY]
        assert isinstance(events, list) and events, "_iter_test_events must be a non-empty list"
        assert events[0].get("name") == "user_example_1"
        assert events[0].get("event", {}).get("qname") == "example.com"

    def test_build_parser_with_agent_sets_iter_test_events_when_raw_examples_supplied(self, tmp_path):
        """Producer-side regression gate for build_parser_with_agent.

        We can't easily call build_parser_with_agent without a real
        parser entry on disk, so we exercise its mutation logic via a
        synthesised entry path. The function reads `entry["raw_examples"]`
        only after `_find_entry` returns; we monkeypatch _find_entry to
        return a synthesised entry so the rest of the path runs.
        """
        from components.lua_generator import ITER_TEST_EVENTS_KEY

        wb, captured = self._capturing_workbench(tmp_path)
        # Synthesise an entry shape that matches what _find_entry returns
        # in production. Inject via _find_entry monkeypatch.
        wb._find_entry = lambda name: {
            "parser_name": name,
            "config": {"parser_name": name},
            "ingestion_mode": "push",
        }

        wb.build_parser_with_agent(
            parser_name="aws_route53",
            raw_examples=[{"qname": "example.com"}],
        )

        assert captured, "agent.generate was never called"
        entry = captured[0]
        assert ITER_TEST_EVENTS_KEY in entry, (
            "build_parser_with_agent must populate _iter_test_events on the "
            "entry dict whenever raw_examples is supplied"
        )
        events = entry[ITER_TEST_EVENTS_KEY]
        assert isinstance(events, list) and events
        assert events[0].get("event", {}).get("qname") == "example.com"

    def test_no_iter_test_events_set_when_no_raw_examples(self, tmp_path):
        """Daemon shape preserved: no raw_examples → no _iter_test_events
        key on the entry dict, so the iteration loop falls back to
        Jarvis/synthetic events."""
        from components.lua_generator import ITER_TEST_EVENTS_KEY

        wb, captured = self._capturing_workbench(tmp_path)
        wb._find_entry = lambda name: {
            "parser_name": name,
            "config": {"parser_name": name},
            "ingestion_mode": "push",
        }

        wb.build_parser_with_agent(parser_name="okta_logs")

        assert captured, "agent.generate was never called"
        entry = captured[0]
        assert ITER_TEST_EVENTS_KEY not in entry, (
            "_iter_test_events must NOT be set when no raw_examples are "
            "provided — daemon path must continue to use harness fallback"
        )


class TestAgentLuaCacheAtomicity:
    """Container review fold-back: verify cache.put is atomic.

    Pre-fix used `path.write_text(...)` (truncate + write), which can be
    observed half-written by a concurrent reader. Post-fix uses
    atomic-rename so a reader either sees the previous file or the
    fully-written new file, never a partial write.
    """

    def test_cache_put_uses_atomic_rename(self, tmp_path):
        """Patch os.replace to detect that put goes through it."""
        import os as _os

        from components.agentic_lua_generator import AgentLuaCache

        cache = AgentLuaCache(cache_dir=tmp_path)
        replace_calls: List[Any] = []
        original_replace = _os.replace

        def tracking_replace(src, dst):
            replace_calls.append((str(src), str(dst)))
            return original_replace(src, dst)

        import components.agentic_lua_generator as alg_module
        original_module_replace = alg_module.os.replace
        alg_module.os.replace = tracking_replace
        try:
            cache.put("foo_parser", {"lua_code": "x", "confidence_score": 80})
        finally:
            alg_module.os.replace = original_module_replace

        assert replace_calls, "cache.put must use os.replace for atomicity"
        src, dst = replace_calls[0]
        assert src.endswith(".tmp"), f"src should be a tmp file, got {src}"
        assert dst.endswith("foo_parser.json"), f"dst should be the target, got {dst}"
        assert (tmp_path / "foo_parser.json").exists()
        # Tmp file must be cleaned up
        assert not list(tmp_path.glob("*.tmp")), "tmp files leaked"

    def test_cache_get_logs_corrupt_json(self, tmp_path, caplog):
        """Pre-fix swallowed JSONDecodeError silently. Post-fix logs at
        WARNING so operators can see corruption."""
        import logging
        from components.agentic_lua_generator import AgentLuaCache

        cache = AgentLuaCache(cache_dir=tmp_path)
        # Write a half-baked JSON file directly (simulates a crash mid-write).
        (tmp_path / "broken.json").write_text("{not valid json", encoding="utf-8")

        with caplog.at_level(logging.WARNING, logger="components.agentic_lua_generator"):
            assert cache.get("broken") is None
        assert any("corrupt JSON" in rec.message for rec in caplog.records), (
            "cache.get must log corrupt JSON at WARNING level"
        )


class TestCachePutSkippedOnWorkbenchRun:
    """Architecture review fold-back: cache.put must skip when the run
    was driven by user-supplied samples, otherwise narrow workbench
    samples poison the daemon's next cache read for the same parser_name.
    """

    def test_cache_put_skipped_when_raw_examples_set(self, tmp_path):
        """Generate via the legacy iterative path with raw_examples set.
        cache.put MUST NOT fire."""
        cache_dir = tmp_path / "cache"
        gen = _BypassTestGenerator(cache_dir=cache_dir)

        gen.generate(
            {
                "parser_name": "awsroute53",
                "raw_examples": [{"qname": "x"}],
            },
            force_regenerate=False,
        )

        # The cache directory should have no awsroute53.json — workbench
        # runs do not pollute the daemon-shared cache.
        cache_file = cache_dir / "awsroute53.json"
        assert not cache_file.exists(), (
            "workbench run wrote to the cache; this would poison future "
            "daemon reads on the same parser_name"
        )

    def test_cache_put_skipped_when_only_iter_test_events_set(self, tmp_path):
        """DA-Round2 REOPENED gap: the skip predicate is
        ``raw_examples OR _iter_test_events``. The previous test only
        exercised the raw_examples branch — a future refactor narrowing
        the predicate to ``raw_examples`` alone would slip through. Pin
        the OR branch by setting ONLY _iter_test_events.
        """
        from components.lua_generator import ITER_TEST_EVENTS_KEY

        cache_dir = tmp_path / "cache"
        gen = _BypassTestGenerator(cache_dir=cache_dir)

        gen.generate(
            {
                "parser_name": "awsroute53_iter_only",
                ITER_TEST_EVENTS_KEY: [
                    {"name": "user_example_1", "event": {"qname": "x"}}
                ],
                # NOTE: no "raw_examples" key
            },
            force_regenerate=False,
        )

        cache_file = cache_dir / "awsroute53_iter_only.json"
        assert not cache_file.exists(), (
            "_iter_test_events alone must also bypass cache.put; "
            "narrowing the predicate to raw_examples-only would slip past"
        )

    def test_cache_put_fires_for_daemon_shape(self, tmp_path):
        """Daemon shape (no raw_examples / _iter_test_events) MUST still
        write to the cache so daemon batch runs accumulate cached Lua
        for downstream reads."""
        cache_dir = tmp_path / "cache"
        gen = _BypassTestGenerator(cache_dir=cache_dir)

        gen.generate(
            {"parser_name": "okta_daemon"},
            force_regenerate=True,  # bypass any pre-existing cache to force fresh path
        )

        cache_file = cache_dir / "okta_daemon.json"
        assert cache_file.exists(), (
            "daemon-shape generation should populate the cache; "
            "without raw_examples the cache write is the contract"
        )
