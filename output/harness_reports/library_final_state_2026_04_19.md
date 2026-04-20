# Reference library — final state after Orion verification + cleanup

Outcome of the 2026-04-19 verification cycle: Orion reviewed the 140-script library, flagged 12 classification concerns. We triaged, cleaned, annotated, and re-graded. Library is now verified and production-ready.

## Final numbers

**132 active references** across three tiers:

| Tier | Active | Avg score | Notes |
|---|---|---|---|
| UI-captured (`observo_serializers/`) | 19 | 54.1* | Shipping-Observo scripts; 4 annotated with concerns |
| Agent-generated (`observo_serializers_agent/`) | 105 | 83.7 | Refined via agentic loop; 5 annotated |
| Orion-generated (`observo_serializers_orion/`) | 8 | 74.8 | 2026-04-19 on-demand; all C-grade |

*UI-captured average drags low because harness grading with an empty synthetic event doesn't exercise the deep field mappings in production serializers. When graded on realistic samples, these were the top performers (verified earlier with Marco's fixtures).

## Cleanup actions taken

### 6 newly quarantined (clear misclassifications)

Moved to `data/harness_examples/observo_serializers_agent/_quarantine/`:

- `aws_cloudwatch_logs` — claimed class 4001 (Network); CloudWatch is logs/metrics/alarms → 6003/2004
- `google_workspace_logs` — claimed class 4001; GWS emits auth + admin API events → 3002/6003
- `netskope_logshipper_logs` — claimed class 4001; Netskope is a CASB → 4002/2004
- `netskope_netskope_logs` — same as above
- `proofpoint_logs` — claimed class 4001; Proofpoint is email security → 4009/2004
- `proofpoint_proofpoint_logs` — same as above

Plus the 2 already-quarantined: `linux_system_logs` (broken Lua) and `github_audit` (audit-keyword false positive).

### 5 agent-generated annotated (kept with concern flag)

In `observo_serializers_agent/manifest.json` with `class_uid_concern: true`:

| Slug | Current | Alternative | Concern |
|---|---|---|---|
| `dhcp_logs` | 3002 | 4004 | OCSF has dedicated DHCP Activity class |
| `manageengine_adauditplus_logs` | 1007 | 3001 | AD audit is user/group change, not process |
| `agent_metrics_logs` | 1007 | 5001 | Metrics is Device Inventory, not Process Activity |
| `microsoft_eventhub_defender_email_logs` | 2004 | 4009 | Non-alert email events → Email Activity |
| `microsoft_eventhub_defender_emailforcloud_logs` | 2004 | 4009 | Non-alert email events → Email Activity |

### 4 UI-captured annotated (kept as production truth)

In `observo_serializers/manifest.json` with `class_uid_concern: true` and `kept_as_production_truth: true`:

| Slug | Current | Alternative (Orion) | Why we kept it |
|---|---|---|---|
| `azure_ad` | 3004 | 3001/3006 | Observo production choice |
| `netskope` | 2001 | 2004/4002 | Observo production choice |
| `tenable_vulnerability_management_audit_logging` | 6001 | 2002 | Observo production choice |
| `palo_alto_networks_firewall` | 99602001 | 2004 | SentinelOne-extended OCSF, intentional |

## Selector behavior post-cleanup

`ExampleSelector._index_dir` now loads `class_uid_concern` from each manifest. `select()` applies a **−15 scoring penalty** to flagged entries — small enough that a flagged script still appears when nothing better exists at the same class, but a clean alternative at the same class outranks it.

Verified by tests:
- `test_selector_unflagged_script_beats_flagged_when_class_matches` — DHCP annotated as 4004-preferable no longer tops class-3002 lookups
- `test_selector_returns_flagged_as_fallback_when_nothing_else_matches` — DHCP still appears when asked specifically for it (vendor hint)

## Tests added

`tests/test_classification_concerns.py` — 7 tests:
- UI manifest has exactly the 4 kept-with-concern entries
- Agent manifest has the 6 quarantined + 5 annotated
- Quarantined scripts are on disk only under `_quarantine/`
- Selector loads concern flags
- Selector de-prioritizes flagged entries
- Selector still returns flagged as fallback
- Library has ≥130 active references

**Full suite: 174 tests passing** (up from 167 pre-cleanup, +7 for concerns).

## Grade distribution snapshot (re-run post-cleanup)

```
Overall across 132 scripts:  B=96  C=19  D=5  F=11  A=1
                             (A+B+C = 116 of 132 = 88% usable grade)
```

F/D scores are concentrated in UI-captured tier because empty synthetic events don't exercise their real field mappings. In realistic grading (as validated on Marco's PDF fixtures), the UI-captured set was the **gold standard**.

## Ready-to-proceed

Library is now:
- Verified by independent review (Orion)
- Cleaned of clear misclassifications (6 quarantined)
- Annotated for debatable choices (9 total concerns, 5 agent + 4 UI)
- Test-covered (174 tests)
- Concern-aware in the selector (−15 penalty applied)

**Safe to proceed with Milestone B (Monaco editor workbench).**

## Files changed this cycle

- `components/agentic_lua_generator.py` — `_index_dir` loads concern flags; `select` applies penalty
- `data/harness_examples/observo_serializers/manifest.json` — 4 KEEP annotations
- `data/harness_examples/observo_serializers_agent/manifest.json` — 6 quarantine + 5 annotate
- `data/harness_examples/observo_serializers_agent/_quarantine/` — 6 new subdirs with reasons
- `tests/test_classification_concerns.py` — 7 new tests
- `output/harness_reports/concern_triage_2026_04_19.md` — triage doc
- `output/harness_reports/library_final_state_2026_04_19.md` — this file
