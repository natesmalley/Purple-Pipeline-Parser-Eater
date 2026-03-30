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
- `docs/harness/model-and-scoring-strategy.md`
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

## Environment Setup

Create your local environment file from the harness-first template:

```bash
cp .env.example .env
```

Required in `.env`:
- At least one of: `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`

Optional in `.env`:
- `MINIO_ACCESS_KEY` (only for `--profile rag`)
- `MINIO_SECRET_KEY` (only for `--profile rag`)
- `GITHUB_TOKEN`

Provider behavior:
- Harness supports both Anthropic and OpenAI keys.
- If only one key is present, that provider is used.
- If both keys are present, set `LLM_PROVIDER_PREFERENCE` explicitly in `.env`.
- `.env.example` defaults `LLM_PROVIDER_PREFERENCE=anthropic` to avoid accidental OpenAI-first failures.
- Use `OPENAI_MODEL`, `ANTHROPIC_MODEL`, and `LLM_MAX_TOKENS` to tune cost/performance.
- Generation now uses cheap-first model selection with auto-escalation when score stays below threshold.
- Override escalation targets with `OPENAI_STRONG_MODEL` and `ANTHROPIC_STRONG_MODEL`.
- Workbench/API routes do not require token headers.

## Docker Compose (Recommended for Local Development)

The repository includes `docker-compose.yml` at the project root.

Prerequisite:
- Docker must be able to pull required images from registries.
- Run `docker compose pull` before first startup.
- Compose uses a registry image by default:
  - `ghcr.io/natesmalley/purple-pipeline-parser-eater:latest`

```bash
# prepare env
cp .env.example .env

# optional: pin image tag
# export PPPE_TAG=sha-<commit>

# required: pull images first
docker compose --env-file .env pull

# start harness-only services (default)
docker compose --env-file .env up -d

# start with optional RAG stack (Milvus/MinIO/etcd)
docker compose --env-file .env --profile rag up -d

# check status
docker compose --env-file .env ps

# view parser service logs
docker compose --env-file .env logs -f parser-eater

# stop all services
docker compose --env-file .env down
```

Notes:
- End users should pull and run the published image; local Dockerfile builds are optional for contributors.
- CI publishes new images to GHCR on `main` and version tags.
- `main` is harness-first by default; full-RAG baseline is preserved on branch `rag-full-preservation`.
- Container runs as non-root `uid:gid 999:999` by design.
- Do not `chown` your repo files to `999:999`; that is not required.
- `config.yaml` is mounted read-only, so it only needs to be host-readable (for example `chmod 644 config.yaml`).
- Runtime writes go to named Docker volumes (`app-output`, `app-logs`, `app-data`), not to your repo working tree.

## Image Size Expectations

- Harness-first image excludes optional RAG ML/vector dependencies by default.
- Full-RAG images are much larger due to ML stack dependencies (for example torch/CUDA wheels and embedding libraries).
- Use default compose for harness-only workflows.
- Enable `--profile rag` only when you explicitly need Milvus-backed semantic retrieval.

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
