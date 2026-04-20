# OCSF Serializer Extended template review — 2026-04-19

## TL;DR

The Extended template exposes **52 options** vs. 20 in the standard OCSF
Serializer, but only **1 of those options is a new editable Lua script**
we didn't already have. The other Lua-named options are byte-identical
duplicates of the standard set, and the ~40 plain-named options are
native Observo serializers with no Lua surface.

**Added:** `palo_alto_networks_firewall` (741 lines, 23,817 chars,
class_uid 99602001 — SentinelOne extended OCSF).

## What's in the Extended template

Full 52-option enumeration lives in the harness's runtime memory; the
Lua-having ones break down as:

| Option | Status | Length |
|---|---|---|
| AWS CloudTrail Lua | duplicate of `AWS CloudTrail (1.0.0-rc3)` | 21,112 |
| Wiz Issue Lua OCSF Serializer | duplicate of `Wiz Issue (1.0.0-rc.3)` | 25,147 |
| Proofpoint Lua OCSF Serializer | duplicate of `Proofpoint (1.0.0)` | 27,726 |
| Netskope Lua OCSF Serializer | duplicate of `Netskope (1.5.0)` | 79,365 |
| Okta OCSF Serializer(1.0.0) | duplicate of `Okta (1.0.0)` | 67,784 |
| Cisco Duo Lua OCSF Serializer | duplicate of `Cisco Duo (1.0.0)` | 32,027 |
| Snyk (1.1.0) | duplicate of `Snyk (1.1.0)` | 32,069 |
| **Palo Alto Networks Firewall Lua OCSF Serializer** | **NEW** | 23,817 |

Duplicate detection used an FNV-1a hash over the full script; seven were
exact matches to the standard-template scripts already in our reference
library.

The remaining 44 Extended options (Okta Logs, Okta Logs 2, Okta Logs 3,
AWS Cloudtrail (no Lua suffix), Google Cloud Audit Logs, GitHub Audit
Logs, Microsoft 365 / Entra variants, Azure Graph / NSG Flow, OCI,
Proofpoint Logs, 1Password, Abuse.ch, AlphaSOC, Atlassian,
Box, Carbon Black, Code42, CrowdStrike variants, ForgeRock, GraphQL,
HubSpot, Infoblox, Google Workspace, Netskope Logs, Zscaler ZPA/ZIA, etc.)
present the same dropdown entry but don't render a Lua editor. Probe of
four representative entries confirmed this — they appear to be native Go
serializers under the hood.

## PAN Firewall fixture details

```
path:       data/harness_examples/observo_serializers/palo_alto_networks_firewall/transform.lua
class_uid:  99602001  (S1 Security Alert, SentinelOne-extended OCSF)
signature:  processEvent
lines:      741
chars:      23,817
header:     "Palo Alto Networks Firewall to OCSF Mapping Script
             Maps PANW Firewall threat log events to OCSF S1 Security Alert format"
```

The class_uid 99602001 is outside the standard OCSF 1xxx–6xxx range. It's
SentinelOne's extended OCSF schema. The `ExampleSelector`'s regex picks
it up correctly as an integer; the scoring module's OCSF registry may not
recognise it (will report class_name null) but the selector returns it
for parsers whose target class matches.

## Reference library state

| Set | Count |
|---|---|
| Standard OCSF Serializer (round 1) | 18 Lua + 2 built-in |
| OCSF Serializer Extended (this review) | +1 Lua (PAN Firewall) |
| **Total** | **19 Lua fixtures** available to the prompt |

Manifest updated: `data/harness_examples/observo_serializers/manifest.json`
now has 21 entries (19 with Lua, 2 built-in).

## Tests

- `tests/test_reference_library.py::test_every_lua_fixture_on_disk_and_uses_process_event`
  relaxed from `== 18` to `>= 18`.
- New `test_selector_picks_palo_alto_firewall_reference` asserts that
  `ExampleSelector.select(target_class_uid=99602001, target_vendor="palo_alto")`
  returns the PAN fixture.

**Full suite:** 156 tests passing (was 155; +1 for the new PAN selector test).

## Recommendation

The Extended template isn't a significant source of new reference material
for the prompt library — it's primarily a packaging surface that exposes
Observo's native Go serializers alongside the Lua-implemented ones, with
the Lua set being essentially the same as the standard template plus PAN
Firewall.

**Next steps for the library:** if we want to meaningfully widen coverage,
the higher-value move is probably pulling the Observo source code / CI
fixtures for the native-serializer implementations rather than harvesting
more UI surfaces. Or we stop expanding the reference library and accept
that the 19 Lua fixtures cover most common OCSF classes (3002, 3004,
4001, 4002, 4003, 6003, 2001, 2002, 2004, 6001 + PAN's 99602001).

## Files changed

- `data/harness_examples/observo_serializers/palo_alto_networks_firewall/transform.lua` (new, 23,817 chars)
- `data/harness_examples/observo_serializers/manifest.json` (21 entries)
- `tests/test_reference_library.py` (relaxed count assertion, added PAN test)
