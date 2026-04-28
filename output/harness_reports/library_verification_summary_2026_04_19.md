# Reference library verification — 2026-04-19

Cross-check of the 140-script library:

1. **Harness grading** — every script run through `HarnessOrchestrator`
2. **Orion independent review** — library summary posted back to Orion for classification sanity check

## Harness grading (all 121 newly-imported scripts, 100% coverage)

| Tier | n | Avg score | B | C | F |
|---|---|---|---|---|---|
| Agent (`output/agent_lua_scripts/`) | 113 | **83.3** | 101 | 11 | 1 |
| Orion (pilots + batch) | 8 | 74.8 | 0 | 8 | 0 |
| **Total graded** | 121 | 82.7 | 101 | 19 | 1 |

Plus 19 UI-captured + 2 Orion = 140 library scripts total. After quarantine of 2 problem scripts, **138 active**.

### Outliers found and resolved

- **`linux_system_logs`** — syntactically invalid Lua (truncated, parse error). Quarantined.
- **`github_audit`** (agent) — script itself sets class_uid=1007; should be 6003. Same audit-keyword false-positive we fixed in the classifier, but this script was generated before the fix. Quarantined.

## Orion verification findings

Independent review by Orion flagged these classification issues in the library:

### Confirmed misclassifications (script-level)

| Script | Currently set | Orion says | Reason |
|---|---|---|---|
| AWS CloudWatch (agent) | 4001 Network | 6003 API / 2004 Detection | CloudWatch is API/metrics/alarms, not raw network traffic |
| Google Workspace (agent) | 4001 Network | 3002 Auth / 6003 API | GWS logs are auth + admin API events |
| Netskope (agent, the 4001 variant) | 4001 Network | 4002 HTTP / 2004 Detection | CASB web proxy → HTTP, alerts → Detection |
| Proofpoint (agent) | 4001 Network | 4009 Email Activity / 2004 | Email security, not generic network |
| DHCP (agent) | 3002 Authentication | **4004 DHCP Activity** | OCSF has a dedicated DHCP class |
| ManageEngine ADauditPlus (agent) | 1007 Process | 3001 Account Change / 3004 | AD audit = user/group changes |
| agent_metrics_logs | 1007 Process | 5001 Device Inventory Info | Metrics ≠ process activity |
| Tenable (UI) | 6001 Web Resource | **2002 Vulnerability Finding** | 6001 is CRUD on web resources, wrong |
| Netskope (UI) | 2001 Security Finding | 2004 / 4002 | Netskope is CASB not a vuln scanner |
| Azure AD (UI) | 3004 Entity Management | 3001 Account Change / 3006 Group Management | 3004 is for IoT/managed devices |
| Palo Alto FW | 99602001 S1 Alert | **2004 Detection Finding** | Non-standard vendor UID breaks OCSF interop |
| MS Defender Email | 2004 Detection | 4009 Email Activity for non-alert events | Alerts OK, raw events should be 4009 |

### Library-level observation

**77 of 140 scripts (55%) target class 4001 Network Activity.** Orion flags this as over-use — OCSF provides dedicated protocol classes that many firewall/network scripts should be using instead:

- 4004 DHCP Activity
- 4005 RDP Activity
- 4006 SMB Activity
- 4007 SSH Activity
- 4009 Email Activity
- 4011 Email File Activity
- 4014 Tunnel Activity

Our library doesn't use any of these. That's the single biggest classification improvement opportunity.

### Gaps — enterprise sources Orion says we're missing

High-priority:

- **AWS CloudTrail** (6003) — we have it UI-captured but it's not in the agent tier
- **Windows Security Event Log** (3002)
- **Sysmon** (1007)
- **Linux Auditd** (1007/3001)
- **Qualys / Rapid7** (2002)
- **Carbon Black / Lacework / Orca / Prisma Cloud** (2004)
- **Zscaler VPN tunnel** (4014)
- **ServiceNow incidents** (2005 Incident Finding)
- **Slack / Teams / Salesforce / Workday audit** (6003)

Note: Sysmon, Windows Security, Linux Auditd were in our **planned Orion batch** — we pivoted to the import instead, so they're still genuine gaps.

## What this means for the harness / reference library

**No change needed to the harness code** — the harness is correctly grading what it receives. The issues are in the source scripts themselves.

**Two levels of action possible:**

1. **Mark-and-keep (low cost):** annotate the manifest with `class_uid_concern` for the ~12 scripts Orion flagged, so the few-shot selector can de-prioritize them for ambiguous lookups while keeping them as structural references. Future generations informed by the prompt will still see good processEvent / FEATURES / FIELD_ORDERS patterns.

2. **Regenerate-and-replace (higher cost):** re-run the agentic generator on the ~12 problem parsers with the fixed classifier + tightened prompt. Would produce correctly-classified replacements.

For now: **keep as-is as a style reference library, document the verified issues.** The 140 scripts are still the richest few-shot pool available, even with ~12 having class-selection debates.

## Files

- `output/harness_reports/full_library_grading.json` — per-script harness scores
- `output/harness_reports/orion_library_review.txt` — Orion's full review transcript
- `output/harness_reports/library_verification_summary_2026_04_19.md` — this file
- `data/harness_examples/observo_serializers_agent/_quarantine/` — 2 quarantined scripts with reasons
