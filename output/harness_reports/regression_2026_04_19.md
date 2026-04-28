# Regression report — 2026-04-19

Baseline: Marco Rottigni's *Parser Builder* test results from 2026-04-08
(Cisco DUO, MS Defender 365, Akamai CDN, Akamai DNS) plus Milestone A changes
to the agentic Lua generator.

## Summary

| Suite | Result |
|---|---|
| Milestone A unit tests (`test_reference_library.py`) | **10/10 pass** |
| Marco PDF regression (`test_regression_marco_pdf.py`) | **22/22 pass** |
| Full harness + agent suite (`test_harness_*.py`, `test_agentic_*.py`) | **155/155 pass** |
| Live Anthropic A/B on Cisco DUO | **not run** — sandbox has no egress to `api.anthropic.com`. Script is ready at `scripts/ab_reference_library.py` to run locally. |

No regressions from Milestone A changes. All pre-existing harness behavior preserved.

## What the Marco replay surfaced

The four PDF cases now live under
`data/regression_fixtures/marco_2026_04_08/<slug>/` with `sample.json`,
`parser_config.json`, `generated.lua`, and `expected.json`. Replaying them
through `HarnessOrchestrator.run_all_checks()` produced two substantive
findings beyond Marco's UI observations:

### 1. Cisco DUO has a silent scoping bug the harness now catches

Marco's Workbench flagged the DUO script as "lint Fair / OCSF Poor" but did
not catch a real runtime issue: the outer `return result` at the end of
`processEvent()` references a variable only declared inside the inner `pcall`
closure, so the function returns **nil**. Compare:

- DUO (broken): `local status, err = pcall(function() … local result = {} … return result end)` — `result` goes out of scope, outer `return result` is nil.
- MS Defender (working): `local status, result = pcall(function() … result = {} … return result end)` — `result` is the pcall return value, outer `return result` works.

The harness `test_execution` correctly reports `processEvent() returned nil`
and 1/1 failed. `test_cisco_duo_return_scope_bug_caught_by_harness` locks this
detection in.

### 2. OCSF analyzer blind spot with `setNestedField(..., "class_uid", N)`

MS Defender and Akamai CDN scripts set `class_uid` via the helper call
`setNestedField(result, "class_uid", 2004)` rather than a direct
`result.class_uid = 2004`. The current OCSF analyzer captures the string
literal of the expression (`"ts * 1000"`, `"2004"`) but does not evaluate the
helper's target to resolve `class_uid`. Result: `ocsf_alignment.class_uid:
null` even though the Lua clearly targets class 2004.

Locked in as a "known gap" by
`test_ms_defender_setnestedfield_class_uid_analyzer_gap` — if the analyzer is
ever improved to resolve helper assignments, that test will fail loudly and
can be tightened to `assert == 2004`.

### 3. Akamai DNS runtime error reproduced deterministically

Marco's AI SIEM screenshot showed the error `attempt to call a nil value
(method 'match')` — root-caused to the dataplane passing `timestamp` as a
non-string. The regression test
`test_akamai_dns_runtime_error_reproduced_when_timestamp_non_string` feeds a
numeric timestamp through the same Lua and verifies the harness captures the
failure in `output_event.lua_error` (the script's own pcall handler writes it
there).

## Findings that should drive roadmap work

| Finding | Where | Recommended fix |
|---|---|---|
| `return result` scope bug in DUO style | Generator pattern | Add a lint rule that flags `local status, err = pcall(function() ... end) return result` (result not bound) |
| OCSF analyzer misses helper-assigned class_uid | `ocsf_field_analyzer.py` | Teach analyzer to resolve literal numeric args passed to `setNestedField(_, "class_uid", N)` |
| `timestamp:match` runtime blowup | Reference library + prompt | Prompt guidance is in place ("use tostring") but failed in production. Harness should fuzz timestamp type per event to catch this in CI rather than in the dataplane. |
| Akamai CDN classified as 2004 Detection Finding | `classify_ocsf_class` | "akamai_cdn" is actually mapped to 4002 in the keyword table — the classification smell in the fixture reports this is still happening. Verify the reference library+vendor match actually lands on 4002/6002 for CDN. |

## Live A/B (deferred to local run)

The script `scripts/ab_reference_library.py` runs Cisco DUO twice through
`AgenticLuaGenerator` — once with `HARNESS_REFERENCE_LIBRARY=0` and once with
`=1` — using Anthropic (not OpenAI, because gpt-5's separate planning path in
`_generate_with_gpt5_strategy` does not yet receive reference
implementations). Results land in `output/ab_reference_library.json`.

The sandbox this regression ran from has no outbound network, so the live
call needs to be run locally. Expected cost: under $0.50 at Anthropic
Sonnet-4-5 pricing for ≤2 iterations × 2 runs.

## Pre-existing issues noted (not caused by this work)

- `tests/test_lua_generator_comprehensive.py` — 18 tests fail because the
  suite uses `@pytest.mark.asyncio` without `pytest-asyncio` declared in
  `requirements-dev.txt`. Unrelated to Milestone A (the failing file doesn't
  touch `ExampleSelector`, `build_generation_prompt`, or
  `reference_implementations`).

## Files changed by this regression work

- `data/regression_fixtures/marco_2026_04_08/` — 4 case subdirs + README
- `tests/test_regression_marco_pdf.py` — 22 replay tests
- `scripts/ab_reference_library.py` — live A/B runner for local execution
- `output/harness_reports/regression_2026_04_19.md` — this report
