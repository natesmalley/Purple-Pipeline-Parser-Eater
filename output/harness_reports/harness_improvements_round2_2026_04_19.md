# Harness improvements — round 2 (2026-04-19)

Continues the work started in `harness_improvements_2026_04_19.md`. This
round adds two more quality surfaces requested after reviewing the grading
scorecard:

- A **generalized classification cross-check** that doesn't rely on the
  three hand-coded source families.
- **Timestamp-type fuzzing** in the execution engine that catches the class
  of runtime failure Marco hit in Akamai DNS before it ships to the
  dataplane.

## Grading: two rounds of improvement

| Case | Marco's UI | Before round 1 | After round 1 | **After round 2** |
|---|---|---|---|---|
| cisco_duo | lint Fair / OCSF Poor | D / 65 | D / 60 | **D / 60** |
| ms_defender_365 | (not scored) | F / 50 | C / 70 | **C / 70** |
| akamai_cdn | (not scored) | F / 50 | D / 68 | **F / 58** |
| akamai_dns | lint Poor / OCSF Fair | D / 62 | D / 63 | **D / 63** |

The Akamai CDN drop from D/68 → **F/58** is the right answer. The script sets
`class_uid = 2004` (Detection Finding) but it's a CDN access log — keyword
inference says 4002 (HTTP Activity). The harness now correctly flags this
with a −10 `source_class_mismatch` penalty. Marco's UI didn't catch this
because his AI SIEM pipeline accepted any valid OCSF class; the logs were
silently landing in the wrong bucket.

## Fixes shipped this round

### 1. Generalized `source_class_mismatch` penalty

`components/testing_harness/harness_orchestrator.py`:

- Added `_infer_expected_class_uid_from_metadata(source_info)` that mirrors
  the generator's `OCSF_CLASS_KEYWORDS` table (10 OCSF classes, ~90
  keywords).
- The penalty now falls back to this inference when the hand-curated
  family (`cisco_duo`, `akamai_dns`, `akamai_cdn_http`) doesn't match.
- Conservative: requires a strict keyword lead — if top two classes tie,
  returns None to avoid false-positive mismatches on ambiguous parsers.

### 2. Timestamp-type fuzzing in `DualExecutionEngine`

`components/testing_harness/dual_execution_engine.py`:

- For each happy-path test event, two fuzz variants run automatically:
  `timestamp_numeric` (replaces timestamp with a numeric epoch) and
  `timestamp_missing` (removes the field). The fuzz writes to all of
  `timestamp`, `Timestamp`, and `time` if present.
- Results land under `test_execution.timestamp_fuzz` as a structured
  dict: `{total, passed, failed, results}`.
- A fuzz variant only counts as "passed" if the output lacks a `lua_error`
  field — scripts commonly wrap their body in pcall and stash errors in
  the event, which the base executor otherwise marks as passed.

Fuzz results on the four cases:

| Case | happy-path | fuzz (passed/total) | what fuzz catches |
|---|---|---|---|
| cisco_duo | 0/1 | **0/2** | scope bug is unconditional |
| ms_defender_365 | 1/1 | **1/2** | `timestamp:match(...)` blows up on numeric — latent bug |
| akamai_cdn | 1/1 | **2/2** | script reads wrong-cased `Timestamp`, so numeric fuzz on `timestamp` doesn't reach `:match` (different latent bug, unrelated to fuzz target) |
| akamai_dns | 1/1 | **1/2** | `eventTime:match(...)` failure — Marco's exact production bug |

## Tests added

`tests/test_harness_semantic_improvements.py` — 9 tests covering:

- Keyword inference returns the right class for Akamai CDN/DNS, Okta, and
  conservatively returns None when metadata is ambiguous.
- The Akamai CDN regression fixture now grades F due to the new penalty.
- Fuzz reruns fire (2 variants when a timestamp field exists, 0 when
  absent), correctly mark `lua_error`-carrying outputs as failed, and
  surface Marco's Akamai DNS production bug.

**Test totals:** **155 passing** across the affected suites.

## What this unlocks for the generator

Both of these changes feed directly into the agentic refinement loop
(`components/agentic_lua_generator.py`). When the generator produces a
script with any of these defects, it now sees:

- `source_class_mismatch` in the penalty details when the wrong OCSF class
  is selected for the parser → refinement prompt can steer the next
  iteration toward the right class.
- `timestamp_fuzz.failed > 0` in the harness report → refinement prompt
  can re-emphasize `tostring(event.timestamp or "")` before any `:match`.

Combined with round 1's fixes (`pcall_return_scope`,
`string_method_type_guard`, OCSF helper-call resolution, source analyzer
helper extraction), the generator's next-round output on these same
parsers should avoid all four documented defect classes.

## Remaining roadmap

| Item | Impact | Where |
|---|---|---|
| Stronger "Unknown X" placeholder penalty + refinement re-prompt | −6/case on 2 cases | `harness_orchestrator` + `agentic_lua_generator` |
| Rewrite `copyUnmappedFields` in the template library to avoid table-in-loop | lifts lint 70 → ~85 across the board | `components/observo_lua_templates.py` + prompt |
| Pre-coerce timestamps in system prompt (`tostring(event.timestamp or "")`) | closes the whole DNS-style failure class at generation time | `SYSTEM_PROMPT` in `agentic_lua_generator.py` |
| Weight fuzz results into confidence score | ensures latent-bug scripts can't grade A just from happy-path | `_calculate_confidence` |

## Files changed this round

- `components/testing_harness/harness_orchestrator.py` — added
  `_OCSF_CLASS_KEYWORDS` table, `_infer_expected_class_uid_from_metadata`
  method, extended `_compute_semantic_penalties` to use it
- `components/testing_harness/dual_execution_engine.py` — added timestamp
  fuzz pass with deterministic 2-variant re-execution and lua_error-aware
  pass/fail counting
- `tests/test_harness_semantic_improvements.py` (new, 9 tests)

## Cumulative changes across both rounds

- `components/testing_harness/ocsf_field_analyzer.py` — setNestedField
  resolution (round 1)
- `components/testing_harness/source_parser_analyzer.py` — getValue /
  getNestedField extraction (round 1)
- `components/testing_harness/lua_linter.py` — `pcall_return_scope` +
  `string_method_type_guard` rules (round 1)
- `components/testing_harness/harness_orchestrator.py` — generalized
  classification cross-check (round 2)
- `components/testing_harness/dual_execution_engine.py` — timestamp fuzz
  (round 2)

## Cumulative new tests

- `tests/test_ocsf_class_uid_detection.py` — 9 tests
- `tests/test_lua_linter_new_rules.py` — 9 tests
- `tests/test_regression_marco_pdf.py` — 22 tests (updated)
- `tests/test_harness_semantic_improvements.py` — 9 tests
- `tests/test_reference_library.py` — 10 tests (Milestone A)

**59 new or updated tests; 155 total passing.**
