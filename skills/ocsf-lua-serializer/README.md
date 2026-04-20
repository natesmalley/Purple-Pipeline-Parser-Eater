# ocsf-lua-serializer Claude skill

A Claude skill that generates production-grade OCSF-compliant Lua serializers
for Observo Pipeline Manager's `OCSFSerializer` transform template.

Output is a 4-file bundle (`<transform>.json`, `metadata.yaml`, `serializer.lua`,
`sample.json`) that drops directly into an Observo pipeline or the
`Sentinel-One/ai-siem` community repo.

**Current version:** v1.1 (2026-04-20) — adds Mimecast reference + 4 patterns
from live subagent testing (vendor verdict dictionaries, explicit direction
hints, dual-source reconciliation, string→number coercion).

## What's inside

- **SKILL.md** — description and triggering guidance
- **ocsf_class_catalog.md** — authoritative OCSF class list (1001–6003)
  with required/optional fields per class
- **reference_examples/** — 12 A/B-graded Lua transforms covering the most
  common SentinelOne AI SIEM sources. **Proofpoint Mail v8** is the
  gold-standard reference (live-deployment tested); **Mimecast** is the
  complementary reference for verdict-driven email security gateways.
- **methodology.md** — the "why" behind defensive coding rules + 13 lessons
  from live Observo deployment and subagent testing (timezone handling,
  relay-hop splitting, vendor verdict dictionaries, explicit direction
  hints, dual-source reconciliation, string→number coercion, etc.)
- **validation_checklist.md** — per-class required-field checklist
- **templates/** — scaffolds for the 4-file output bundle

## Install

### Claude Desktop / Cowork mode

1. Download [`ocsf-lua-serializer.skill`](ocsf-lua-serializer.skill) (65 KB)
2. Double-click to install — Claude registers the skill automatically.

### Claude Code

```bash
mkdir -p ~/.claude/skills
curl -L -o ~/.claude/skills/ocsf-lua-serializer.skill \
  https://github.com/natesmalley/Purple-Pipeline-Parser-Eater/raw/main/skills/ocsf-lua-serializer/ocsf-lua-serializer.skill
```

Claude Code picks it up on next session start.

### Manual unpack

The `.skill` file is just a zip archive:

```bash
unzip ocsf-lua-serializer.skill -d ~/.claude/skills/
```

## How to trigger

The skill auto-triggers when you ask Claude any of:

- "write a Lua transform for <vendor>"
- "create an OCSF serializer for <source>"
- "map <source> logs to OCSF"
- "build an Observo transform for <source>"
- "normalize <logs> to OCSF"
- "convert <vendor> logs to SentinelOne AI SIEM format"
- "contribute a transform to the ai-siem community pipelines"

You can also invoke it explicitly: `skill ocsf-lua-serializer`.

## Verified behavior

Tested cold-start by a fresh subagent on a novel source (Mimecast email
security, not in the original reference library):

- Picked target OCSF class correctly (2004 Detection Finding)
- Applied all 10 gold-standard patterns from the Proofpoint reference
- Handled timezone offsets correctly (landed event at `1776712931512 ms`,
  UTC-accurate for a `-05:00` source timestamp)
- Parsed the sendmail-style `relay=host [ip]` into `src/dst_endpoint`
- Predicted grade B/88, verified by running the output under `lupa`

The four gaps surfaced by that test (verdict dictionary, direction hints,
dual-source reconciliation, string→number coercion) are now first-class
patterns in v1.1.

## Provenance

Patterns in this skill come from the 130-transform library shipped in
[`Sentinel-One/ai-siem/pipelines/community/transform_ocsf/`](https://github.com/Sentinel-One/ai-siem/tree/main/pipelines/community/transform_ocsf).
Validation grades come from the
[Purple-Pipeline-Parser-Eater](https://github.com/natesmalley/Purple-Pipeline-Parser-Eater)
harness running against realistic HELIOS/Jarvis events.

The gold-standard Proofpoint Mail reference was refined through live
Observo deployment testing with customer data. The Mimecast reference
was produced by a fresh subagent running this skill on a cold start and
reviewed + kept as a v1.1 addition.

## License

Same as the parent repo.
