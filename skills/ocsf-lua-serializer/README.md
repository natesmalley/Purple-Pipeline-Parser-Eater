# ocsf-lua-serializer Claude skill

A Claude skill that generates production-grade OCSF-compliant Lua serializers
for Observo Pipeline Manager's `OCSFSerializer` transform template.

Output is a 4-file bundle (`<transform>.json`, `metadata.yaml`, `serializer.lua`,
`sample.json`) that drops directly into an Observo pipeline or the
`Sentinel-One/ai-siem` community repo.

**Current version: v1.3** (2026-04-20)
- Bundles the full OCSF schema documentation (~940 KB, all classes,
  field-name lists) adapted from
  [pmoses-s1/claude-skills](https://github.com/pmoses-s1/claude-skills/blob/main/sentinelone-sdl-log-parser/references/ocsf-schema-documentation.md)
  with all login-walled URLs stripped out — everything is usable without
  credentials.
- Swapped the compact schema-index from SentinelOne Customer Community
  URLs (login-walled) to the public [schema.ocsf.io](https://schema.ocsf.io/)
  + [github.com/ocsf/ocsf-schema](https://github.com/ocsf/ocsf-schema) as
  authoritative references, with representative in-the-wild examples from
  `Sentinel-One/ai-siem/pipelines/community/transform_ocsf/` per class.

Previous highlights:
- v1.2: 4003 DNS reference (Cisco Umbrella cold-test), 5 new class
  catalog entries, methodology patterns #15 (polymorphic identity) and
  #16 (vendor taxonomy).
- v1.1: Mimecast reference + 4 patterns from cold-start testing.
- v1.0: 10 reference transforms, 10 methodology patterns, packaged from
  the 130-transform ai-siem shipped library.

## What's inside

- **SKILL.md** — description and triggering guidance
- **ocsf_class_catalog.md** — 20 production OCSF classes documented inline
  with required and optional fields
- **references/ocsf-schema-index.md** — compact navigation table: every OCSF
  class (1001–6007) with public [schema.ocsf.io](https://schema.ocsf.io/) URL
  and a top-graded example transform from `Sentinel-One/ai-siem`
- **references/ocsf-schema-documentation.md** — full per-class field-name
  reference (~940 KB); vendored from @pmoses-s1/claude-skills with
  login-walled URLs stripped
- **reference_examples/** — 13 A/B-graded Lua templates (Proofpoint v8 as
  gold-standard, Mimecast + Umbrella as complementary patterns)
- **methodology.md** — 16 numbered patterns from live Observo deployment and
  cold-start subagent testing
- **validation_checklist.md** — per-class required-field checklist
- **templates/** — scaffolds for the 4-file output bundle

## Install

### Claude Desktop / Cowork mode

1. Download [`ocsf-lua-serializer.skill`](ocsf-lua-serializer.skill) (140 KB)
2. Double-click to install.

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

Auto-triggers on any of:

- "write a Lua transform for <vendor>"
- "create an OCSF serializer for <source>"
- "map <source> logs to OCSF"
- "build an Observo transform for <source>"
- "normalize <logs> to OCSF"
- "convert <vendor> logs to SentinelOne AI SIEM format"
- "contribute a transform to the ai-siem community pipelines"

Or invoke explicitly: `skill ocsf-lua-serializer`.

## Data provenance & sources

Every reference in this skill uses open, login-free URLs:

- **OCSF schema authority:** [schema.ocsf.io](https://schema.ocsf.io/) and
  [github.com/ocsf/ocsf-schema](https://github.com/ocsf/ocsf-schema)
- **In-the-wild transform examples:**
  [github.com/Sentinel-One/ai-siem](https://github.com/Sentinel-One/ai-siem)
  (130 production OCSF Lua transforms)
- **Harness that validated them:**
  [github.com/natesmalley/Purple-Pipeline-Parser-Eater](https://github.com/natesmalley/Purple-Pipeline-Parser-Eater)
- **Full per-class field-name reference:** adapted from
  [pmoses-s1/claude-skills](https://github.com/pmoses-s1/claude-skills/blob/main/sentinelone-sdl-log-parser/references/ocsf-schema-documentation.md),
  attribution preserved, login-walled URLs stripped

No SentinelOne Customer Community URLs remain as active references. The
only remaining `community.sentinelone.com` mention is in explanatory prose
describing what was removed and why.

## Verified behavior

Cold-start tested by fresh subagents on two sources NOT in the original
reference library:

| Source | Target class | Predicted grade | Outcome |
|---|---|---|---|
| Mimecast email security | 2004 Detection Finding | B/88 | ✓ Reference promoted, 4 patterns extracted (v1.1) |
| Cisco Umbrella DNS | 4003 DNS Activity | B/87 | ✓ Reference promoted with IANA QTYPE/RCODE maps + 2 patterns (v1.2) |

## License

Same as parent repo (AGPL-3.0).
