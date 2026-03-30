# Purple Pipeline Parser Eater (Harness-First)

This repository is currently operated as a standalone, dataset-first OCSF/Lua harness.

## Current Focus

- Canonical Lua authoring contract is `processEvent(event)`.
- `transform(record)` is compatibility-only and remains supported.
- Dataset traversal and report output are expected to be deterministic.
- Scope is milestone-driven; avoid unrelated platform refactors.

Reference docs:
- `docs/harness/technical-roadmap.md`
- `docs/harness/acceptance-criteria.md`
- `AGENTS.md`

## Active Harness Areas

- `components/testing_harness/` harness execution, linting, compatibility adapters
- `components/web_ui/` parser workbench UI + API routes/jobs
- `data/harness_examples/` curated parser/sample index + history
- `output/generated_lua/` generated Lua artifacts
- `output/harness_reports/` harness run reports
- `output/parser_lua_serializers/` parser serializer outputs
- `docs/harness/` roadmap + milestone acceptance gates

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.yaml.example config.yaml
mkdir -p logs
python continuous_conversion_service.py
```

Workbench:
- `http://localhost:8080/workbench`

## Docker Compose (Recommended for Local Development)

The repository includes `docker-compose.yml` at the project root.

```bash
# start all services
docker compose up -d

# check status
docker compose ps

# view parser service logs
docker compose logs -f parser-eater

# stop all services
docker compose down
```

## Primary Harness Use Cases

1. Run the workbench service

```bash
mkdir -p logs
python continuous_conversion_service.py
```

2. Run targeted harness/workbench checks (smallest-first)

```bash
pytest tests/test_workbench_root_redirect.py -q
pytest tests/test_harness_cli_smoke.py -q
pytest tests/test_workbench_jobs_api.py -q
pytest tests/test_parser_workbench.py -q
pytest tests/test_harness_ocsf_alignment.py -q
pytest tests/test_harness_deterministic_reporting.py -q
pytest tests/test_harness_compatibility_matrix.py -q
```

3. Run broader harness validation only when needed

```bash
pytest tests/test_workbench_*.py tests/test_parser_workbench.py tests/test_harness_*.py -v
```

4. Generate cleanup manifests for review

```bash
python scripts/utils/harness_cleanup_inventory.py
```

Manifest outputs:
- `data/cleanup_manifests/keep_manifest.json`
- `data/cleanup_manifests/delete_manifest.json`

## Environment Cleanup

There is no standalone `observo/` directory in this repository.

Safe cleanup commands:

```bash
# test cache
rm -rf .pytest_cache

# runtime logs
rm -rf logs

# untracked generated harness artifacts only
git clean -fd -- \
  output/agent_lua_cache \
  output/generated_lua \
  output/harness_reports \
  output/parser_lua_serializers \
  data/harness_examples/history
```

Optional full environment reset:

```bash
rm -rf .venv
```

Do not remove tracked corpus files under `output/` or `data/harness_examples/` unless a milestone explicitly requires it.
