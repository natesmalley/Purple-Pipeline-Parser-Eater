# Harness Repository Scope

## Active Product Surface
This repository now keeps only the active harness-first workflow:
- sample-driven parser workbench UI
- Lua generation/validation for `processEvent(event)`
- OCSF mapping analysis and deterministic harness reporting
- persisted local knowledge objects under `data/harness_examples/` and `output/`

## Explicitly Removed Surface
The following legacy areas were removed as part of lean-harness cleanup:
- legacy event source adapters and ingestion service paths
- legacy sink/output delivery service paths
- legacy standalone runtime/worker startup scripts and service config files
- historical archive documentation previously stored under `docs/archive_legacy/`

## Guardrails
- Do not reintroduce removed legacy stacks unless a roadmap milestone explicitly requires it.
- Keep changes focused on harness/workbench behavior.
- Keep test and report ordering deterministic.
- Preserve compatibility behavior (`transform(record)`) unless a milestone explicitly removes it.
