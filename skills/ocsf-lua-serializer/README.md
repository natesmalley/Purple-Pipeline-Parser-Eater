# ocsf-lua-serializer Claude skill

A Claude skill that generates production-grade OCSF-compliant Lua serializers
for Observo Pipeline Manager's `OCSFSerializer` transform template.

Output is a 4-file bundle (`<transform>.json`, `metadata.yaml`, `serializer.lua`,
`sample.json`) that drops directly into an Observo pipeline or the
`Sentinel-One/ai-siem` community repo.

## What's inside

- **SKILL.md** — description and triggering guidance
- **ocsf_class_catalog.md** — authoritative OCSF class list (1001–6003) with
  required/optional fields per class
- **reference_examples/** — 11 A/B-graded Lua transforms covering the most
  common SentinelOne AI SIEM sources. Proofpoint Mail is the gold-standard
  reference (v8, live-deployment tested).
- **methodology.md** — the "why" behind defensive coding rules + 9 lessons
  from live Observo deployment (timezone handling, relay-hop splitting,
  finding-lifecycle vs delivery-outcome `status_id`, vendor-extension
  `email.x_*` placement, etc.)
- **validation_checklist.md** — per-class required-field checklist
- **templates/** — scaffolds for the 4-file output bundle

## Install

### Claude Desktop / Cowork mode

1. Download [`ocsf-lua-serializer.skill`](ocsf-lua-serializer.skill) (58 KB)
2. Double-click to install — Claude Desktop registers the skill automatically.

### Claude Code

```bash
# Put the skill in your local skills directory
mkdir -p ~/.claude/skills
curl -L -o ~/.claude/skills/ocsf-lua-serializer.skill \
  https://raw.githubusercontent.com/natesmalley/Purple-Pipeline-Parser-Eater/main/skills/ocsf-lua-serializer/ocsf-lua-serializer.skill
```

Claude Code picks it up on next session start.

### Manual unpack

The `.skill` file is just a zip archive. You can unpack it and drop the
contents into any directory Claude reads skills from:

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

## Provenance

Patterns in this skill come from the 130-transform library shipped in
[`Sentinel-One/ai-siem/pipelines/community/transform_ocsf/`](https://github.com/Sentinel-One/ai-siem/tree/main/pipelines/community/transform_ocsf).
Validation grades come from the
[Purple-Pipeline-Parser-Eater](https://github.com/natesmalley/Purple-Pipeline-Parser-Eater)
harness running against realistic HELIOS/Jarvis events.

The gold-standard Proofpoint Mail reference was refined through live
Observo deployment testing with customer data.

## License

Same as the parent repo.
