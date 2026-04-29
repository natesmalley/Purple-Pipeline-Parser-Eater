from pathlib import Path

from components.agentic_lua_generator import AgenticLuaGenerator, GPT5_PLAN_SCHEMA


class _HarnessStub:
    def run_all_checks(self, lua_code, parser_config, ocsf_version="1.3.0", custom_test_events=None):
        return {
            "confidence_score": 84,
            "confidence_grade": "B",
            "checks": {
                "field_comparison": {"coverage_pct": 85},
                "lua_linting": {"issues": []},
                "ocsf_mapping": {"missing_required": [], "class_uid": 4003, "class_name": "DNS Activity"},
            },
            "ocsf_alignment": {"required_coverage": 100.0},
        }


class _SourceStub:
    def analyze_parser(self, parser_entry):
        return {"fields": [{"name": "message", "type": "string"}]}


class _GPT5FlowGenerator(AgenticLuaGenerator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calls = []

    def _call_openai_responses_raw(
        self,
        model,
        instructions,
        input_items,
        previous_response_id=None,
        response_format=None,
    ):
        self.calls.append(
            {
                "model": model,
                "instructions": instructions,
                "input_items": input_items,
                "previous_response_id": previous_response_id,
                "response_format": response_format,
            }
        )
        if response_format:
            return {
                "text": (
                    '{"class_uid":4003,"class_name":"DNS Activity","category_uid":4,'
                    '"category_name":"Network Activity","activity_id":1,"activity_name":"DNS Query",'
                    '"timestamp_sources":["timestamp"],"severity_strategy":"default 0",'
                    '"embedded_payload_strategy":"parse message kv",'
                    '"mappings":[{"target":"src_endpoint.ip","source_candidates":["cliIP"],"transform":"direct","required":false}],'
                    '"notes":["parse embedded payload"]}'
                ),
                "response_id": "resp_plan",
                "data": {},
            }
        return {
            "text": "function processEvent(event)\n  return event\nend",
            "response_id": "resp_code",
            "data": {},
        }


def test_gpt5_strategy_uses_planner_and_previous_response_id(tmp_path: Path):
    gen = _GPT5FlowGenerator(
        api_key="test-key",
        model="gpt-5-mini",
        provider="openai",
        max_iterations=1,
        score_threshold=80,
        output_dir=tmp_path,
    )
    gen.harness = _HarnessStub()
    gen.source_analyzer = _SourceStub()

    result = gen.generate(
        {
            "parser_name": "akamai_dns-latest",
            "ingestion_mode": "push",
            "raw_examples": [{"message": 'AkamaiDNS cliIP="1.2.3.4" domain="example.com"'}],
            "config": {"attributes": {"dataSource": {"vendor": "Akamai", "product": "DNS"}}},
        },
        force_regenerate=True,
    )

    assert len(gen.calls) == 2
    assert gen.calls[0]["response_format"]["schema"] == GPT5_PLAN_SCHEMA
    assert gen.calls[1]["previous_response_id"] == "resp_plan"
    assert result["generation_method"] == "agentic_llm_gpt5_plan"
    assert result["confidence_score"] == 84


def test_gpt5_plan_schema_requires_all_declared_top_level_properties():
    assert sorted(GPT5_PLAN_SCHEMA["required"]) == sorted(GPT5_PLAN_SCHEMA["properties"].keys())


class _UserSamplesCapturingHarness:
    """Records custom_test_events on every harness call so the GPT-5
    short-circuit can be verified to propagate user samples."""

    def __init__(self):
        self.received_custom_test_events = []

    def run_all_checks(self, lua_code, parser_config, ocsf_version="1.3.0", custom_test_events=None):
        self.received_custom_test_events.append(custom_test_events)
        return {
            "confidence_score": 84,
            "confidence_grade": "B",
            "checks": {
                "field_comparison": {"coverage_pct": 85},
                "lua_linting": {"issues": []},
                "ocsf_mapping": {"missing_required": [], "class_uid": 4003, "class_name": "DNS Activity"},
            },
            "ocsf_alignment": {"required_coverage": 100.0},
        }


def test_gpt5_strategy_receives_user_samples(tmp_path: Path):
    """Plan/Change 2 verification for the GPT-5 short-circuit path.

    When AgenticLuaGenerator.generate() short-circuits into
    _run_gpt5_strategy for gpt-5* models, the strategy's harness call at
    agentic_lua_generator.py:2126 must propagate parser_entry's
    _iter_test_events as custom_test_events. Otherwise the GPT-5 path has
    the same scoring divergence the unified iterative loop just got
    fixed for: model refines toward synthetic events while UI shows a
    re-score against user samples.
    """
    gen = _GPT5FlowGenerator(
        api_key="test-key",
        model="gpt-5-mini",
        provider="openai",
        max_iterations=1,
        score_threshold=80,
        output_dir=tmp_path,
    )
    capturing_harness = _UserSamplesCapturingHarness()
    gen.harness = capturing_harness
    gen.source_analyzer = _SourceStub()

    user_events = [
        {"name": "user_example_1", "event": {"cliIP": "1.2.3.4", "domain": "example.com"}},
    ]

    gen.generate(
        {
            "parser_name": "gpt5_test",
            "ingestion_mode": "push",
            "raw_examples": [{"cliIP": "1.2.3.4", "domain": "example.com"}],
            "_iter_test_events": user_events,
            "config": {"attributes": {"dataSource": {"vendor": "Akamai", "product": "DNS"}}},
        },
        force_regenerate=True,
    )

    assert capturing_harness.received_custom_test_events, (
        "GPT-5 strategy harness was never invoked"
    )
    # Every harness call inside the GPT-5 strategy must propagate the
    # user samples — None would be the pre-fix behaviour.
    for received in capturing_harness.received_custom_test_events:
        assert received is user_events, (
            "GPT-5 strategy harness call did not receive _iter_test_events "
            f"as custom_test_events; got: {received!r}"
        )


def test_gpt5_strategy_skips_cache_put_for_workbench_run(tmp_path: Path):
    """DA-Round2 NF-3 fold-back: the GPT-5 short-circuit has its own
    cache.put guard at agentic_lua_generator.py:2249-2272 (separate from
    the legacy iterative path). Without dedicated coverage, a future
    refactor could regress the GPT-5 path's skip predicate while the
    legacy-path test stays green.

    Wires the exact GPT-5 plan→code chain, lets the strategy reach the
    cache.put site, and asserts no cache file was created on disk —
    pinning the GPT-5-side skip guard.
    """
    gen = _GPT5FlowGenerator(
        api_key="test-key",
        model="gpt-5-mini",
        provider="openai",
        max_iterations=1,
        score_threshold=80,
        output_dir=tmp_path,
    )
    gen.harness = _HarnessStub()
    gen.source_analyzer = _SourceStub()

    cache_dir = tmp_path / "agent_lua_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Point the cache at our tmp dir so we can assert no file landed.
    from components.agentic_lua_generator import AgentLuaCache
    gen.cache = AgentLuaCache(cache_dir=cache_dir)

    gen.generate(
        {
            "parser_name": "gpt5_workbench",
            "ingestion_mode": "push",
            "raw_examples": [{"cliIP": "1.2.3.4", "domain": "example.com"}],
            "config": {"attributes": {"dataSource": {"vendor": "Akamai", "product": "DNS"}}},
        },
        force_regenerate=True,
    )

    # cache.put MUST be skipped on the GPT-5 path when raw_examples is set
    cache_file = cache_dir / "gpt5_workbench.json"
    assert not cache_file.exists(), (
        "GPT-5 strategy wrote to the cache during a workbench run; "
        "this would poison the daemon's next read on the same parser_name"
    )


# ---------------------------------------------------------------------------
# Stream G review fold-back regression tests
# ---------------------------------------------------------------------------


class _DangerousLuaGenerator(AgenticLuaGenerator):
    """Returns Lua containing `os.execute(...)` to verify the Phase 1.C
    dangerous-Lua hard-reject gate fires in the GPT-5 strategy path.

    Stream G review fold-back (Blocker, Security #1, 2026-04-27): the
    DA's reproduction showed the original GPT-5 strategy accepted
    adversarial Lua because it called harness.run_all_checks directly
    without lint_script(..., context="lv3"). This test pins that the
    restored hard-reject gate forces a refinement.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calls = []

    def _call_openai_responses_raw(
        self,
        model,
        instructions,
        input_items,
        previous_response_id=None,
        response_format=None,
    ):
        self.calls.append(
            {
                "model": model,
                "instructions": instructions,
                "input_items": input_items,
                "previous_response_id": previous_response_id,
                "response_format": response_format,
            }
        )
        if response_format:
            return {
                "text": (
                    '{"class_uid":4003,"class_name":"DNS Activity","category_uid":4,'
                    '"category_name":"Network Activity","activity_id":1,"activity_name":"DNS Query",'
                    '"timestamp_sources":["timestamp"],"severity_strategy":"default 0",'
                    '"embedded_payload_strategy":"none",'
                    '"mappings":[{"target":"src_endpoint.ip","source_candidates":["cliIP"],"transform":"direct","required":false}],'
                    '"notes":[]}'
                ),
                "response_id": "resp_plan",
                "data": {},
            }
        # First (code) call: dangerous Lua. Subsequent (refinement) calls
        # after the security reject return clean Lua.
        non_plan_calls = sum(1 for c in self.calls if not c.get("response_format"))
        if non_plan_calls == 1:
            return {
                "text": (
                    "function processEvent(event)\n"
                    "  os.execute(\"id\")\n"
                    "  return event\n"
                    "end"
                ),
                "response_id": "resp_code",
                "data": {},
            }
        return {
            "text": "function processEvent(event)\n  return event\nend",
            "response_id": "resp_refined",
            "data": {},
        }


def test_gpt5_strategy_hard_rejects_dangerous_lua_and_forces_refinement(tmp_path: Path):
    """Stream G review fold-back: dangerous Lua from the GPT-5 code call
    must NOT be accepted. The restored lint_script(context='lv3') gate
    forces a refinement turn instead. The DA reproduced the pre-fix
    bug as a live exploit."""
    gen = _DangerousLuaGenerator(
        api_key="test-key",
        model="gpt-5-mini",
        provider="openai",
        max_iterations=3,
        score_threshold=80,
        output_dir=tmp_path,
    )
    gen.harness = _HarnessStub()
    gen.source_analyzer = _SourceStub()

    result = gen.generate(
        {
            "parser_name": "akamai_dns-latest",
            "ingestion_mode": "push",
            "raw_examples": [{"message": 'AkamaiDNS cliIP="1.2.3.4"'}],
            "config": {"attributes": {"dataSource": {"vendor": "Akamai", "product": "DNS"}}},
        },
        force_regenerate=True,
    )

    # Sequence: plan + dangerous-code + security-reject-refinement = 3 calls
    assert len(gen.calls) == 3
    # The third call is the security-rejection refinement, NOT a normal
    # build_gpt5_refinement_prompt — the prompt must mention the security reject.
    third_call_prompt = gen.calls[2]["input_items"][0]["content"]
    assert "REJECTED by the security linter" in third_call_prompt, (
        "GPT-5 strategy did not issue a security-rejection refinement; "
        "the Phase 1.C hard-reject gate is missing or misplaced."
    )
    # Final returned Lua must NOT contain os.execute.
    assert "os.execute" not in result["lua_code"], (
        "Stream G Blocker regressed: dangerous Lua reached the cache. "
        "The lint_script(..., context='lv3') gate failed."
    )
    assert result["generation_method"] == "agentic_llm_gpt5_plan"


def test_gpt5_strategy_skips_when_api_key_is_empty(tmp_path: Path):
    """Stream G review fold-back (Container #1, High): empty api_key
    must short-circuit the GPT-5 strategy without burning a network
    round-trip. _run_gpt5_strategy returns None → caller falls through
    to the unified iterative loop.

    We can't easily exercise the full fallback here (it would require
    mocking the entire LLMProvider chain), but we can verify the
    short-circuit by calling _run_gpt5_strategy directly and asserting
    it returns None without making any LLM calls.
    """

    class _NeverCalledGenerator(AgenticLuaGenerator):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.calls = []

        def _call_openai_responses_raw(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            raise AssertionError(
                "_run_gpt5_strategy should NOT issue a network call when "
                "api_key is empty"
            )

    gen = _NeverCalledGenerator(
        api_key="",
        model="gpt-5-mini",
        provider="openai",
        output_dir=tmp_path,
    )
    gen.harness = _HarnessStub()
    gen.source_analyzer = _SourceStub()

    result = gen._run_gpt5_strategy(
        {"parser_name": "x", "ingestion_mode": "push", "raw_examples": []},
        "x",
    )
    assert result is None
    assert len(gen.calls) == 0


def test_gpt5_strategy_strips_markdown_fences_before_scoring(tmp_path: Path):
    """Stream G review fold-back (Python #1, High): GPT-5 family models
    routinely emit ```lua ... ``` fences despite the instruction to
    output bare Lua. _clean_lua_response must run before the harness
    sees the script, otherwise the linter trips on fences as syntax
    errors and every GPT-5 run scores low."""

    class _FencedGenerator(AgenticLuaGenerator):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.scored_lua = []

        def _call_openai_responses_raw(
            self, model, instructions, input_items,
            previous_response_id=None, response_format=None,
        ):
            if response_format:
                return {
                    "text": (
                        '{"class_uid":4003,"class_name":"DNS Activity","category_uid":4,'
                        '"category_name":"Network Activity","activity_id":1,"activity_name":"DNS Query",'
                        '"timestamp_sources":["timestamp"],"severity_strategy":"default 0",'
                        '"embedded_payload_strategy":"none","mappings":[],"notes":[]}'
                    ),
                    "response_id": "resp_plan", "data": {},
                }
            return {
                "text": (
                    "```lua\n"
                    "function processEvent(event)\n"
                    "  return event\n"
                    "end\n"
                    "```"
                ),
                "response_id": "resp_code", "data": {},
            }

    captured: list = []

    class _CapturingHarness:
        def run_all_checks(self, lua_code, parser_config, ocsf_version="1.3.0", custom_test_events=None):
            captured.append(lua_code)
            return {
                "confidence_score": 84,
                "confidence_grade": "B",
                "checks": {
                    "field_comparison": {"coverage_pct": 85},
                    "lua_linting": {"issues": []},
                    "ocsf_mapping": {"missing_required": [], "class_uid": 4003, "class_name": "DNS Activity"},
                },
                "ocsf_alignment": {"required_coverage": 100.0},
            }

    gen = _FencedGenerator(
        api_key="test-key",
        model="gpt-5-mini",
        provider="openai",
        max_iterations=1,
        score_threshold=80,
        output_dir=tmp_path,
    )
    gen.harness = _CapturingHarness()
    gen.source_analyzer = _SourceStub()

    gen.generate(
        {"parser_name": "akamai_dns-latest", "ingestion_mode": "push",
         "raw_examples": [{"message": "test"}]},
        force_regenerate=True,
    )

    assert captured, "harness.run_all_checks was never invoked"
    # Pre-fix the harness saw the fenced text. Post-fix it sees clean Lua.
    assert "```" not in captured[0], (
        "Stream G review fold-back regressed: harness saw markdown fences "
        "from the GPT-5 code call. _clean_lua_response is not being called "
        "before scoring."
    )
    assert "function processEvent" in captured[0]
