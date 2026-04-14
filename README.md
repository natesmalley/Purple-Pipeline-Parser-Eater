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
- Observo Lua Script contract:
  - https://docs.observo.ai/6S3TPBguCvVUaX3Cy74P/working-with-data/transforms/functions/lua-script
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
cp config.yaml.example ./config.yaml
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
- `WORKBENCH_MAX_SAMPLE_CHARS` (default `150000`)
- `WORKBENCH_MAX_TOTAL_SAMPLE_CHARS` (default `1500000`)

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

Fresh-clone local build:

```bash
cp .env.example .env          # set ANTHROPIC_API_KEY at minimum
docker compose build          # builds the image from the local Dockerfile
docker compose up -d
curl -sf http://localhost:8080/health
```

The compose file declares both `build: .` and `image:` so the same service
definition supports a local build (tagged with the registry name) and a
remote pull. By default the container binds `./config.yaml.example` into
`/app/config.yaml`; once you have a real config, export
`PPPE_CONFIG_FILE=./config.yaml` before `docker compose up`.

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

On a fresh clone, the fastest path from zero to a green harness test subset
is the `test-fast` Makefile target, which builds a throwaway `.venv-test`,
installs `requirements-test.txt` (pytest + lupa + flask + flask-wtf only —
no RAG/ML deps), and runs the four targeted suites:

```bash
make test-fast
```

Or run the individual suites against your existing environment:

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

4. Run the full tests/ sweep (Phase 6.A widened CI target)

```bash
make test-all
# or directly:
pytest tests/ --continue-on-collection-errors -q
```

The `test-all` target runs the entire `tests/` tree. Note: some
pre-existing collection errors and failures remain from legacy suites
that Phase 6.A zombie-fix-or-delete follow-ups will resolve; keep
`test-fast` as the default dev iteration loop until then.

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

## Secret-leak guard (Phase 5.D)

Before committing, run:

```bash
bash scripts/check_secret_leaks.sh
```

To install as a git pre-commit hook:

```bash
ln -s ../../scripts/check_secret_leaks.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

The hook catches the specific SentinelOne HEC token that leaked into
`../Purple-Pipline-Parser-Eater/Observo-dataPlane/s1_hec.yaml` AND any
`default_token:` value that looks like a real 30+ char HEC token. Placeholders
like `your-token-here` and `PLACEHOLDER` are explicitly allowed.

To add a file to the allowed-mention list, edit the `ALLOWED_MENTIONS` array
in `scripts/check_secret_leaks.sh`.

## CVE audit and broader secret scanning (Phase 7.7 / 7.8)

Two additional CI hooks wrap optional third-party scanners and degrade
gracefully when they are not installed:

```bash
# Phase 7.7 — pip-audit CVE scan of requirements.txt
pip install pip-audit          # one-time
bash scripts/run_pip_audit.sh

# Phase 7.8 — gitleaks, with fallback to scripts/check_secret_leaks.sh
# Install: brew install gitleaks  /  scoop install gitleaks
bash scripts/run_gitleaks.sh
```

If `pip-audit` / `gitleaks` are missing the scripts print an install hint and
exit 0 (or delegate to the MVP secret-leak guard), so CI stays green on hosts
that have not yet provisioned the extra tooling.
