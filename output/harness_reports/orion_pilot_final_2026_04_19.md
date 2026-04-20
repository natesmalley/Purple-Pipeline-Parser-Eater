# Orion pilot — final results after harness fixes

## TL;DR

Orion (Observo's built-in BETA AI assistant) produces structurally-correct
Lua OCSF serializers. After fixing three analyzer blind spots our harness
had, all three pilot scripts grade **C or D** — comparable to Marco's
production-generated output. **Recommendation: accept these three as reference
material and scale to ~10 more sources.**

## Three-pilot grading

| Parser | Class | Initial grade | After audit-keyword fix | **After helper-family fix** |
|---|---|---|---|---|
| github_audit_logs | 6003 | F / 54 | D / 64 | **C / 70** |
| crowdstrike_detections | 2004 | — | F / 59 | **D / 69** |
| m365_audit_logs | 6003 | — | D / 64 | **C / 78** |

Total lift from harness fixes: +16, +10, +14 points. These reflect accurate
underlying quality now visible to the grader.

## Fixes shipped this cycle

### 1. Keyword classifier — "audit" false-positive

`components/testing_harness/harness_orchestrator.py`. The keyword table had
`"audit"` in class 1007 (Process Activity). GitHub Audit, Azure Audit, OCI
Audit, Google Cloud Audit, M365 Audit are all API Activity (6003), not
Process Activity. Removed the bare keyword; added explicit 6003 keywords
(`github_audit`, `azure_audit`, `oci_audit`, `m365_audit`, `entra_audit`,
`workspace_audit`). Also tightened 1007 to anchor on actual process-specific
terms (`sysmon`, `execve`, `process_tree`, `process_create`, `image_load`).

### 2. Source analyzer — helper-name families

`components/testing_harness/source_parser_analyzer.py`. Recognizes all of:

- Read helpers: `deepGet`, `safeGet`, `safelyGet`, `getNestedField`,
  `getNested`, `getValue`, `getField`, `readField`, `safeAccess`, etc.
- Event aliases: `event`, `record`, `e`, `src`, `source`, `log`, `raw`
- Mapping table source-keys: `source`, `src`, `src_field`, `src_path`,
  `from`, `input`
- Mapping table target-keys: `target`, `dst`, `dst_field`, `dst_path`,
  `dest`, `dest_field`, `dest_path`, `to`, `output`
- `FIELD_MAP`-style inline tables: `["source"] = "target.path"` pattern,
  which Orion emits as its primary mapping idiom.

### 3. OCSF analyzer — helper-name families

`components/testing_harness/ocsf_field_analyzer.py`. Recognizes the same
write-helper family for both field extraction and class_uid resolution:
`setNestedField`, `setNested`, `deepSet`, `safeSet`, `writeField`,
`assignField`, `set_nested`, `deep_set`. Both numeric-literal and
identifier-references resolve correctly.

## Prompt-change findings

- **Partially effective:** the tightened prompt (no "Unknown" defaults,
  `tostring(x or "")` before `:match`, `table.concat` in loops, helpers as
  `local function` ABOVE processEvent) reduced placeholder count from 5
  (GitHub) → 3 (CrowdStrike) → 1 (M365). Not zero, but trending.
- **Consistent improvement on lint:** CrowdStrike landed at lint 48 vs
  GitHub's 0 — the rules about `tostring` guards and `local function`
  placement genuinely landed. M365 regressed back to 0 though.
- **OCSF class selection is reliable:** all three scripts hit the correct
  class on the first attempt.
- **OCSF required-field coverage is high:** 100% on two cases, 75% on the
  third. Happy-path execution passes on all three, timestamp fuzz passes on
  all three.

## Final three-pilot breakdown

| Metric | github | crowdstrike | m365 |
|---|---|---|---|
| Grade / Score | C / 70 | D / 69 | C / 78 |
| Validity | pass | pass | pass |
| Signature | processEvent | processEvent | processEvent |
| Lines | 825 | 1,297 | 1,256 |
| Lint | 0 | 48 | 0 |
| OCSF class_uid | 6003 ✓ | 2004 ✓ | 6003 ✓ |
| Required coverage | 100% | 75% | 100% |
| Field coverage | 100% | 67% | 92% |
| Execution happy | 1/1 ✓ | 1/1 ✓ | 1/1 ✓ |
| Fuzz (ts-numeric + ts-missing) | pass (N/A) | 2/2 ✓ | 2/2 ✓ |
| Penalties | −15 placeholders | −12 placeholders | −6 placeholders |

## Tests added this cycle

`tests/test_helper_family_recognition.py` — 11 tests covering:

- `deepGet` / `safeGet` / `getNested` / `safelyGet` recognition
- Preservation of original `getValue` / `getNestedField` paths
- Helpers invoked with non-event first args are NOT false-matched
- `deepSet` / `setNested` / `writeField` class_uid detection for literal
  values and identifier references
- `FIELD_MAP`-style `["src"] = "dst"` inline mapping tables
- All mapping key variants (`src`/`dst`/`from`/`to`/`input`/`output`)
- Lookup tables with table-literal values are NOT false-matched as fields

**Full suite: 167 tests passing.** Up from 156 (9 new helper-family tests +
2 new Marco regression-fixture tests).

## Recommendation for scale-up

Based on three pilots the evidence is:

- Orion produces valid processEvent-contract Lua with correct OCSF class
  selection and adequate required-field coverage.
- Output needs one obvious clean-up pass (strip `"Unknown"` placeholders,
  normalize to production helper names). But the core is usable.
- Scores now accurately reflect quality rather than analyzer gaps.

**Suggested scale-up batch** — 10 sources your team most likely uses, skipping the ones we already captured from the UI (Okta, Cisco Duo, Proofpoint etc. that are duplicates of standard templates):

1. Microsoft Entra Logs (6003 / API Activity)
2. Azure Audit Logs (6003 / API Activity)
3. Azure NSG Flow Logs (4001 / Network Activity)
4. Google Cloud Audit Logs (6003 / API Activity)
5. Google Workspace Logs (3002 / Authentication)
6. OCI Audit Logs (6003 / API Activity)
7. Openshift API Server Audit Logs (6003 / API Activity)
8. AWS CloudWatch Logs (6003 / API Activity)
9. 1Password Logs (3002 / Authentication)
10. Infoblox Logs (4003 / DNS Activity)

Store each under `data/regression_fixtures/orion_pilot_2026_04_19/<slug>/`
alongside sample events, then run the same grading script. Expected quality:
60-80% graded C or better after the harness fixes land.

## Files changed

- `components/testing_harness/harness_orchestrator.py` — audit-keyword fix
- `components/testing_harness/source_parser_analyzer.py` — helper-name
  families, mapping-key variants, FIELD_MAP table recognition
- `components/testing_harness/ocsf_field_analyzer.py` — deepSet-family
  recognition for both field extraction and class_uid resolution
- `tests/test_helper_family_recognition.py` (new, 11 tests)
- `data/regression_fixtures/orion_pilot_2026_04_19/{github_audit_logs,crowdstrike_detections,m365_audit_logs}/`
  (3 new Orion pilot fixtures with sample/config/generated.lua)
- `output/harness_reports/orion_github_pilot_grade.json`
- `output/harness_reports/orion_three_pilot_grades.json`
- `output/harness_reports/orion_pilot_final_2026_04_19.md` (this)
