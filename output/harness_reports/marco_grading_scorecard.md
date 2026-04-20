# Grading Scorecard — Marco's 4 PDF cases through our current harness

Date: 2026-04-19
Baseline: Marco Rottigni's Parser Builder test, 2026-04-08.
Harness: post–Milestone A (reference library in place for generator;
grading modules unchanged by that milestone).

## Top-level grades

| Case | Dataplane truth | Marco's UI | Our harness | Score |
|---|---|---|---|---|
| cisco_duo | **Silently returns nil** | lint Fair / OCSF Poor | **D** | 65 |
| ms_defender_365 | Works in AI SIEM | not scored in PDF | **F** | 50 |
| akamai_cdn | Works in AI SIEM | not scored in PDF | **F** | 50 |
| akamai_dns | **Runtime `method 'match'` failure** | lint Poor / OCSF Fair | **D** | 62 |

**The scoring has an inversion problem.** The two scripts Marco saw working in
AI SIEM get the lowest grade (F/50), and the two that failed one way or
another get the better grade (D). That's a ranking issue worth surfacing.

The cause is the OCSF analyzer's blind spot with `setNestedField(result,
"class_uid", N)`: the working scripts use that helper, so the analyzer cannot
resolve their class_uid and the ocsf_mapping module zeroes out — costing them
25% of the weighted score. The "failing" scripts happen to use
`local CLASS_UID = 4003` or a direct `class_uid = 3002` literal that the
analyzer *can* read.

## Per-case detail

### cisco_duo — **D / 65**

| Module | Score | Notes |
|---|---|---|
| Lua Validity | PASS | `processEvent`, 81 lines |
| Lua Linting | 70.5 / Fair | 1 err (`nil_safety`), 1 warn (`string_concat_in_loop`), 1 info (`table_in_loop`) |
| OCSF Mapping | **Excellent — 100%** | class_uid 3002 detected, all required fields present in the source (but see execution) |
| Field Comparison | **84.6%** | Good source→Lua coverage |
| Test Execution | **0/1 pass** | `processEvent() returned nil` — scope bug |

Marco saw lint Fair and OCSF Poor. We now see OCSF *Excellent* **because the
linter got better at field detection** since his run, but execution reveals the
real defect he missed: the script returns nil. Net grade D (65) is about right
— validity and OCSF coverage look great on paper, but the script doesn't
actually produce output.

### ms_defender_365 — **F / 50**

| Module | Score | Notes |
|---|---|---|
| Lua Validity | PASS | `processEvent`, 113 lines |
| Lua Linting | 70.5 / Fair | same three rules as above |
| OCSF Mapping | **Poor — 0%** | **class_uid not detected** (analyzer blind spot with `setNestedField`) |
| Field Comparison | 0% | Analyzer gap cascades — no fields mapped |
| Test Execution | 1/1 pass | Runs clean, no errors |

This is a **false negative from the harness**, not Marco's script. In reality
the output has class_uid 2004, category 2, activity 99, time, type_uid — all
correct — and renders in AI SIEM. Our grading just can't see it because the
analyzer doesn't resolve the helper-call assignment.

### akamai_cdn — **F / 50**

Identical profile to MS Defender — same `setNestedField` pattern, same
analyzer blind spot, same false F.

Caveat: the class_uid the script *should* be targeting is debatable. Marco's
generator produced 2004 (Detection Finding) for a CDN access log, which is
likely wrong (4002 HTTP Activity or 6002 Web Resource would fit better). Even
if our analyzer fixed the helper-resolution gap, this script would still
deserve a "class selection smell" flag.

### akamai_dns — **D / 62**

| Module | Score | Notes |
|---|---|---|
| Lua Validity | PASS | `processEvent`, 103 lines |
| Lua Linting | **40.5 / Poor** | 2 err, 1 warn, 1 info — including `unsafe_string_concat` |
| OCSF Mapping | **Excellent — 100%** | class_uid 4003 detected |
| Field Comparison | 12.5% | Very weak — most DNS-specific fields not mapped |
| Test Execution | 1/1 pass* | *passes on the sampled input, fails on numeric timestamp (Marco's production case) |

Marco saw lint Poor / OCSF Fair. We see lint Poor / OCSF Excellent (same
analyzer-got-better effect as cisco_duo). The runtime failure Marco hit
doesn't show with the sample in the fixture, but our regression test
`test_akamai_dns_runtime_error_reproduced_when_timestamp_non_string`
reproduces it deterministically by feeding a numeric `timestamp`.

## Weighted module breakdown (from `model-and-scoring-strategy.md`)

| Module | Weight | cisco_duo | ms_defender | akamai_cdn | akamai_dns |
|---|---|---|---|---|---|
| Lua validity | 25% | 100 | 100 | 100 | 100 |
| Lua linting | 15% | 70.5 | 70.5 | 70.5 | 40.5 |
| OCSF mapping | 25% | 100 | 0 | 0 | 100 |
| Field coverage | 15% | 84.6 | 0 | 0 | 12.5 |
| Test execution | 20% | 0 | 100 | 100 | 100 |
| **Weighted score** | | **65** | **50** | **50** | **62** |

## What Marco's UI caught that our grading misses

- **Classification smell on akamai_cdn** — 2004 Detection Finding is the wrong
  OCSF class for a CDN access log; the harness accepts it as long as the
  fields mapped match that class. No module penalizes class selection.
- **Poor OCSF coverage for cisco_duo** — Marco saw 33% because the Workbench's
  OCSF analyzer version didn't resolve `setNestedField(result, "time",
  timestamp)` either. We now see 100% on cisco_duo because our analyzer
  evolved — but in the *inverse* direction for the MS/CDN setNestedField
  pattern. The analyzer's behavior is inconsistent across patterns.

## What our grading caught that Marco's UI missed

- **cisco_duo processEvent returns nil** — the real scope bug. No UI flag; the
  dataplane would silently emit `nil`, and downstream enrichment would drop.
- **akamai_dns timestamp-type fragility** — deterministically reproducible via
  our fuzzer, surfaces the exact production error he hit.

## Recommended fixes driven by this scoring review

1. **OCSF analyzer: resolve `setNestedField(result, "class_uid", LITERAL)`** —
   single highest-value fix. Would lift MS Defender and Akamai CDN from F/50
   to ~B/80, and make the grading consistent across patterns. Target:
   `components/testing_harness/ocsf_field_analyzer.py`.
2. **Lint rule: `pcall_return_scope_bug`** — detect
   `local status, err = pcall(function() … end); return result` where
   `result` only lives inside the closure. Would have caught cisco_duo in the
   UI before the dataplane test.
3. **Lint rule: `string_method_on_any_value`** — detect
   `<var>:match(...)` / `:gsub(...)` / `:gmatch(...)` without a `type(var) ==
   "string"` guard. Would catch the akamai_dns pattern before the dataplane.
4. **Execution fuzzer: timestamp polymorphism** — when the harness execution
   engine runs a test event, also run it with `timestamp` as a number, as a
   missing key, and as an empty string. Catches class-3 runtime errors that
   pass the happy-path test but fail in production.
5. **OCSF class-selection sanity check** — when a parser's `parser_name`
   keyword-matches one class but the script sets another, emit a warning.
   Would have flagged Akamai CDN's 2004 selection.

## Raw data

Machine-readable scorecard: `output/harness_reports/marco_grading_2026_04_19.json`
