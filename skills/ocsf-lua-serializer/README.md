# ocsf-lua-serializer Claude skill

A Claude skill that generates production-grade OCSF-compliant Lua serializers
for Observo Pipeline Manager's `OCSFSerializer` transform template.

Output is a 4-file bundle (`<transform>.json`, `metadata.yaml`, `serializer.lua`,
`sample.json`) that drops directly into an Observo pipeline or the
`Sentinel-One/ai-siem` community repo.

**Current version:** v1.2 (2026-04-20)
- Adds `references/ocsf-schema-index.md` — compact index of ALL OCSF classes
  with authoritative SentinelOne SDL article URLs for each class. Distilled
  from @pmoses-s1's `sentinelone-sdl-log-parser` references doc with
  attribution, without vendoring the full 944 KB field-list (kept the skill
  at 76 KB).
- Adds **4003 DNS Activity** reference (Cisco Umbrella, B/87) with IANA
  QTYPE/RCODE integer dictionaries.
- Expands `ocsf_class_catalog.md` with 6 classes we didn't have: 1003 Kernel
  Activity, 1006 Scheduled Job, 3003 Authorize Session, 3005 User Access
  Management, 3006 Group Management, 4003 DNS Activity.
- Adds methodology pattern **#15 Polymorphic identity fields** — route to
  the right OCSF object based on a sibling type hint (user/host/network/group).
- Adds methodology pattern **#16 Vendor taxonomy labels default to `unmapped.*`** —
  don't force vendor-proprietary category/subtype/eventType into OCSF fields.

## What's inside

- **SKILL.md** — description and triggering guidance
- **ocsf_class_catalog.md** — 14 production classes with full required/
  optional field lists
- **references/ocsf-schema-index.md** — ALL OCSF classes with SDL article URLs
- **reference_examples/** — 13 A/B-graded Lua templates:
  - **Proofpoint v8** (gold-standard, live-deployment tested)
  - **Mimecast** (verdict-dictionary, direction-hint, dual-source patterns)
  - **Cisco Umbrella** (DNS Activity 4003, IANA QTYPE/RCODE, polymorphic
    identity, vendor taxonomy handling)
  - Fortinet, AWS VPC Flow, Akamai, Azure AD, Cisco Duo, Defender, Snyk,
    Tenable, SentinelOne agent, CloudTrail
- **methodology.md** — 16 numbered patterns from live Observo deployment
  and cold-start subagent testing
- **validation_checklist.md** — per-class required-field checklist
- **templates/** — scaffolds for the 4-file output bundle

## Install

### Claude Desktop / Cowork mode

1. Download [`ocsf-lua-serializer.skill`](ocsf-lua-serializer.skill) (76 KB)
2. Double-click to install — Claude registers the skill automatically.

### Claude Code

```bash
mkdir -p ~/.claude/skills
curl -L -o ~/.claude/skills/ocsf-lua-serializer.skill \
  https://github.com/natesmalley/Purple-Pipeline-Parser-Eater/raw/main/skills/ocsf-lua-serializer/ocsf-lua-serializer.skill
```

### Manual unpack

```bash
unzip ocsf-lua-serializer.skill -d ~/.claude/skills/
```

## How to trigger

The skill auto-triggers on any of:

- "write a Lua transform for <vendor>"
- "create an OCSF serializer for <source>"
- "map <source> logs to OCSF"
- "build an Observo transform for <source>"
- "normalize <logs> to OCSF"
- "convert <vendor> logs to SentinelOne AI SIEM format"
- "contribute a transform to the ai-siem community pipelines"

Or invoke explicitly: `skill ocsf-lua-serializer`.

## Verified behavior

Cold-start tested by fresh subagents on two novel sources (not in the
reference library):

- **Mimecast email security** → picked 2004 Detection Finding (right),
  applied all 10 gold-standard patterns, timezone UTC-correct, B/88.
- **Cisco Umbrella DNS** → picked 4003 DNS Activity (right), invented
  IANA QTYPE/RCODE maps, routed polymorphic `identity` field by type
  hint, B/87. The reference it produced is now in the skill library.

Both tests surfaced gaps (verdict dictionaries, direction hints, dual-source,
string→number coercion, polymorphic identity, vendor taxonomy routing) —
all now first-class patterns in v1.1/v1.2.

## Provenance

Patterns from the 130-transform library shipped in
[`Sentinel-One/ai-siem/pipelines/community/transform_ocsf/`](https://github.com/Sentinel-One/ai-siem/tree/main/pipelines/community/transform_ocsf),
validated by the
[Purple-Pipeline-Parser-Eater](https://github.com/natesmalley/Purple-Pipeline-Parser-Eater)
harness.

OCSF schema index distilled from
[@pmoses-s1/claude-skills](https://github.com/pmoses-s1/claude-skills/blob/main/sentinelone-sdl-log-parser/references/ocsf-schema-documentation.md)
(SentinelOne SDL Log Parser skill) with attribution.

Gold-standard Proofpoint reference refined through live Observo customer
deployment. Mimecast and Umbrella references produced by cold-start
subagents applying this skill and reviewed before promotion.

## License

Same as the parent repo.
