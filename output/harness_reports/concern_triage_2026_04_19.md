# Classification concerns — triage 2026-04-19

Orion flagged 12 scripts in the 140-script library during independent verification. Each is sorted into one of three actions:

- **KEEP** (production truth) — UI-captured scripts reflect what Observo actually ships; Orion's alternative is noted but not overridden.
- **ANNOTATE** — agent-generated, debatable; flag in manifest with `class_uid_concern: true` and `alternative_class_uid` so the selector de-prioritizes for ambiguous lookups.
- **QUARANTINE** — agent-generated, clear misclassification that would actively mislead the few-shot prompt.

| # | Script | Tier | Current | Orion says | Action | Rationale |
|---|---|---|---|---|---|---|
| 1 | AWS CloudWatch | agent | 4001 | 6003 / 2004 | **QUARANTINE** | Logs service, not network traffic. Obvious error. |
| 2 | Google Workspace | agent | 4001 | 3002 / 6003 | **QUARANTINE** | Admin/login/API events, not network flows. Obvious error. |
| 3 | Netskope (4001 variants) | agent | 4001 | 4002 / 2004 | **QUARANTINE** | CASB web proxy; Network Activity is wrong. |
| 4 | Proofpoint (4001 variant) | agent | 4001 | 4009 / 2004 | **QUARANTINE** | Email security, not generic network. |
| 5 | DHCP | agent | 3002 | 4004 | **ANNOTATE** | 4004 DHCP Activity exists but our 77-deep 4001 bucket may treat 3002 as less-wrong; annotate. |
| 6 | ManageEngine ADauditPlus | agent | 1007 | 3001 / 3004 | **ANNOTATE** | AD audit events are user/group changes, not process activity. Debatable. |
| 7 | agent_metrics_logs | agent | 1007 | 5001 | **ANNOTATE** | Metrics ≠ process activity. Library-only, not customer-used. |
| 8 | Tenable (UI-captured) | ui | 6001 | 2002 | **KEEP** | Observo shipped this as 6001 Web Resource for audit logs specifically; their choice. |
| 9 | Netskope (UI-captured, class 2001) | ui | 2001 | 2004 / 4002 | **KEEP** | Observo production decision. |
| 10 | Azure AD (UI-captured) | ui | 3004 | 3001 / 3006 | **KEEP** | Observo production decision. |
| 11 | Palo Alto Firewall Lua (UI-captured) | ui | 99602001 | 2004 | **KEEP** | SentinelOne extended OCSF; intentional. |
| 12 | MS Defender Email x2 | agent | 2004 | 4009 for non-alerts | **ANNOTATE** | 2004 is OK for alerts; 4009 preferred for raw email events. Ambiguous without knowing log scope. |

**Action summary:**
- Quarantine: 4 scripts (AWS CloudWatch, Google Workspace, Netskope agent, Proofpoint agent) — plus the 2 already quarantined
- Annotate: 4 scripts (DHCP, ManageEngine ADauditPlus, agent_metrics_logs, MS Defender Email ×2 treated as 2 entries)
- Keep: 4 scripts (Tenable, Netskope UI, Azure AD, PAN Firewall)

**Resulting library:**
- Started: 140
- Previously quarantined: 2
- Newly quarantined: 4
- Annotated (kept): ~6 (with concern flags)
- **Active references: 134**

## Why respect UI-captured "wrong" choices

The UI-captured scripts represent Observo's production classification decisions. Even if Orion recommends a different OCSF class, Observo's engineering team made a deliberate choice shown in their shipping product. For the purposes of style reference, respecting that signal is more important than academic OCSF purity. The annotation can note Orion's alternative for downstream consideration.
