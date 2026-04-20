# Harness improvements — 2026-04-19

Follow-up to Marco's PDF regression. This cycle closed the two highest-leverage
analyzer gaps and added two lint rules that catch the exact production bugs
his PDF documented, so the generator's refinement loop can self-correct next
time.

## Fixes shipped

1. **OCSF analyzer now resolves `setNestedField(result, "class_uid", N)`**
   (`components/testing_harness/ocsf_field_analyzer.py`). Previously the
   analyzer only saw direct `class_uid = N` assignments; MS Defender and
   Akamai CDN use the helper-call pattern and came back as `class_uid: null`.
   Added two new detection patterns — numeric literal and identifier
   resolved to a preceding `local CLASS_UID = N`.

2. **Source analyzer now sees `getValue(event, "X", …)` and
   `getNestedField(event, "X")`** (`source_parser_analyzer.py`). Scripts
   that pull fields through these helpers (all four PDF cases) previously
   reported 0–12% coverage even when they legitimately read most fields.

3. **New lint rule `pcall_return_scope`** (error, weight 12) catches the
   Cisco DUO bug: `local status, err = pcall(function() local result = {}
   … return result end) … return result` where the outer `return result`
   is nil because `result` only lives in the closure.

4. **New lint rule `string_method_type_guard`** (warning, weight 3) catches
   the Akamai DNS bug: `<ident>:match(…)` (or `gsub`, `gmatch`, `sub`,
   `find`, `lower`, `upper`) without a prior `type(ident) == "string"`
   check or `tostring(ident)` coercion. Accepts literal-string assignments
   and library namespaces (`string.match`, `table.concat`).

## Grading before / after

| Case | Marco's UI | Before fixes | After (OCSF+fields) | After (+ new lint rules) |
|---|---|---|---|---|
| cisco_duo | lint Fair / OCSF Poor | D / 65 | D / 65 | **D / 60** |
| ms_defender_365 | (not scored) | **F / 50** | C / 75 | **C / 70** |
| akamai_cdn | (not scored) | **F / 50** | D / 68 | **D / 68** |
| akamai_dns | lint Poor / OCSF Fair | D / 62 | D / 64 | **D / 63** |

**Net score movement from the analyzer fixes alone:** MS Defender +20, Akamai
CDN +18, Akamai DNS +1, Cisco DUO unchanged. The two F's became passing
grades.

**Net movement from the new lint rules:** Cisco DUO −5, MS Defender −1,
Akamai CDN 0, Akamai DNS −1. The lint-rule-driven drops are **intentional** —
the rules correctly penalize known-bad patterns. The real value is that
the generator's refinement loop now sees these rules fire and will iterate
to fix them on future generation runs.

## Why scores didn't move more

With Milestone A (reference library) + these fixes, the remaining per-case
losses come almost entirely from:

- **Semantic penalties** (`_compute_semantic_penalties`):
  - `placeholder_values`: −6 on MS Defender and Akamai CDN for
    `"Unknown Process"` / `"Unknown UID"` default values.
  - `excessive_unmapped`: −8 when `has_unmapped_bucket` and
    field_coverage < 40%. Fires on Akamai CDN (12.5%) and Akamai DNS (25%).

- **Linter Fair (70.5) ceiling** from `nil_safety` + `string_concat_in_loop`
  + `table_in_loop`. These are generic patterns in the helper code all four
  scripts share (`setNestedField` builds tables inside loops). Fixing those
  would require rewriting the helpers.

- **Cisco DUO execution 0/20** is the one unrecoverable loss — the scope
  bug means the script returns nil in production. Only a regenerate (with
  the new lint rule guiding the refinement loop) can fix it.

## Test coverage added

- `tests/test_ocsf_class_uid_detection.py` — 9 tests covering all 5
  `class_uid` detection patterns plus negative cases.
- `tests/test_lua_linter_new_rules.py` — 9 tests for `pcall_return_scope`
  (positive + 3 negative) and `string_method_type_guard` (positive + 4
  negative).
- `tests/test_regression_marco_pdf.py` — updated: the "known gap" test for
  MS Defender is now a positive assertion (`class_uid == 2004`,
  `required_coverage == 100`).

**Test totals:** 146 passing across the affected suites. No regressions
outside of the deliberately tightened regression-fixture assertions.

## What would most improve the remaining scores

Ordered by estimated impact:

1. **Strengthen prompt guidance against `"Unknown X"` placeholders**
   (−6 on two cases). The system prompt already warns but the generator
   ignored it. A refinement loop that re-prompts when placeholders appear
   would close this cleanly.

2. **Classification cross-check** (could save −10 on Akamai CDN). When
   `parser_name` keyword-matches one class but the script sets another
   (CDN → keyword says 4002 HTTP, script sets 2004 Detection Finding),
   emit a warning. Existing `source_class_mismatch` penalty only fires for
   three hand-coded source families.

3. **Rewrite the `copyUnmappedFields` helper to not build tables inside
   loops** (lifts lint 70.5 → ~85 across the board). Replace the per-key
   `setNestedField(result, "unmapped." .. k, v)` pattern with a batched
   assignment. This is a template change, not a lint rule.

4. **Pre-coerce timestamp in the prompt template** — the reference library
   Observo scripts all do `local t = tostring(event.timestamp or "")`
   before any `:match` call. Pulling that pattern into the system prompt
   as a required step would eliminate the entire class of DNS-style
   failures.

5. **Teach `test_event_builder` to fuzz timestamp types** (already noted in
   the first regression report). Pass each event three ways — string,
   number, missing — so execution catches type-polymorphism bugs in CI.

## Files changed this cycle

- `components/testing_harness/ocsf_field_analyzer.py` — 2 new class_uid
  detection patterns
- `components/testing_harness/source_parser_analyzer.py` — `getValue` /
  `getNestedField` extraction
- `components/testing_harness/lua_linter.py` — 2 new rules registered and
  implemented
- `tests/test_ocsf_class_uid_detection.py` (new)
- `tests/test_lua_linter_new_rules.py` (new)
- `tests/test_regression_marco_pdf.py` — tightened known-gap test
- `output/harness_reports/marco_grading_after_fix.json` (artifact)

## Rollup of scoring deltas at the module level

| Module (weight) | cisco_duo | ms_defender | akamai_cdn | akamai_dns |
|---|---|---|---|---|
| Lua validity (25%) | 100 | 100 | 100 | 100 |
| Lua linting (15%) | 34.5 *(was 70.5)* | 66 *(was 70.5)* | 66 *(was 70.5)* | 36 *(was 40.5)* |
| OCSF mapping (25%) | 100 | 100 *(was 0)* | 100 *(was 0)* | 100 |
| Field coverage (15%) | 84.6 | 30 *(was 0)* | 12.5 *(was 0)* | 25 *(was 12.5)* |
| Test execution (20%) | 0 | 100 | 100 | 100 |
