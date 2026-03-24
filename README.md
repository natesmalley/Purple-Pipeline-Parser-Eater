# Purple Pipeline Parser Eater (Harness-First Mode)

This repository is operated in a **harness-first, sample-driven mode** focused on:
- Lua generation and validation for `processEvent(event)`
- OCSF mapping analysis and test execution
- Sample-based workbench workflows with persisted example/run records

## Active Structure (Lean Harness)

- `components/testing_harness/`: harness checks, execution, OCSF analysis
- `components/web_ui/`: parser workbench UI + API routes/jobs
- `docs/harness/`: roadmap and acceptance criteria
- `docs/reference/jarvis_event_generators/`: runtime sample generator references
- `data/harness_examples/`: curated sample history + parser index
- `output/generated_lua/`: versioned generated Lua artifacts
- `output/harness_reports/`: versioned harness run reports
- `output/parser_lua_serializers/`: current serializer outputs

Knowledge objects are intentionally persisted in-repo (`data/harness_examples`, `output/generated_lua`, `output/harness_reports`) and should be updated with the newest validated runs.

Removed from active scope:
- legacy event ingestion/output service paths
- legacy sink/source component trees
- historical archive documentation

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.yaml.example config.yaml
```

Then run a small dry run:

```bash
python continuous_conversion_service.py
```

Workbench: `http://localhost:8080/workbench`

## PR Upload Setup (Default to Your Repo)

`Upload PR` in the workbench creates/updates a branch and opens a GitHub PR for the generated Lua.

Required:
- `gh` CLI installed and logged in (`gh auth login`)
- `GITHUB_TOKEN` set in your shell/.env

Repo target selection (default behavior):
1. Use `GITHUB_OWNER` + `GITHUB_REPO` if set
2. Otherwise auto-detect from your git `origin` remote (GitHub URL)

Recommended `.env`:

```bash
GITHUB_TOKEN=ghp_xxx
GITHUB_OWNER=<your-org-or-user>
GITHUB_REPO=<your-repo>
```

## Harness Verification

Run targeted harness tests first:

```bash
pytest tests/test_workbench_jobs_api.py -q
pytest tests/test_parser_workbench.py -q
pytest tests/test_harness_ocsf_alignment.py -q
```

Run broader harness/workbench tests as needed:

```bash
pytest tests/test_workbench_*.py tests/test_parser_workbench.py tests/test_harness_*.py -v
```

## Harness Cleanup Inventory

```bash
python scripts/utils/harness_cleanup_inventory.py
```

This writes:
- `data/cleanup_manifests/keep_manifest.json`
- `data/cleanup_manifests/delete_manifest.json`

## Current Contract and Rules

- `processEvent(event)` is the canonical Lua contract
- `transform(record)` remains compatibility-only unless explicitly removed in a future milestone
- Preserve backward compatibility unless a milestone explicitly changes it
- Keep dataset and report ordering deterministic
