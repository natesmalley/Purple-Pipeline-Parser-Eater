# Purple Pipeline Parser Eater

**Tools and patterns for turning vendor logs into OCSF-compliant Lua
serializers that drop into [Observo Pipeline Manager](https://observo.ai)
and the [SentinelOne AI SIEM](https://github.com/Sentinel-One/ai-siem)
community pipelines.**

If you just want to build new OCSF serializers, **use the Claude skill below**.
Everything else in this repo is the upstream authoring harness that produced
it — useful if you're contributing new references or extending the patterns,
but not required for the common case.

---

## 🟢 Primary: `ocsf-lua-serializer` Claude skill

A packaged Claude skill that generates production-grade OCSF Lua serializers
from a source description or sample event. Output is a 4-file bundle
(`<transform>.json`, `metadata.yaml`, `serializer.lua`, `sample.json`) that
drops directly into an Observo pipeline or the `Sentinel-One/ai-siem` community
repo.

**Current version: v1.4** — Netskope CASB reference + patterns #17–#24
extracted from cold-start A/B testing, layered on top of v1.3's full per-class
OCSF field-name reference and v1.2's 13 A/B-graded reference serializers.

### Install

**Claude Desktop / Cowork mode** — download the `.skill` file and double-click:

📦 [**Download `ocsf-lua-serializer.skill`**](skills/ocsf-lua-serializer/ocsf-lua-serializer.skill)

**Claude Code:**

```bash
mkdir -p ~/.claude/skills
curl -L -o ~/.claude/skills/ocsf-lua-serializer.skill \
  https://github.com/natesmalley/Purple-Pipeline-Parser-Eater/raw/main/skills/ocsf-lua-serializer/ocsf-lua-serializer.skill
```

Restart Claude Code and the skill is available.

**Manual unpack** (any environment with a skills directory):

```bash
unzip ocsf-lua-serializer.skill -d ~/.claude/skills/
```

### What it does

Auto-triggers when you ask Claude any of:

- "write a Lua transform for <vendor>"
- "create an OCSF serializer for <source>"
- "map <source> logs to OCSF"
- "build an Observo transform for <source>"
- "normalize <logs> to OCSF"
- "convert <vendor> logs to SentinelOne AI SIEM format"
- "contribute a transform to the ai-siem community pipelines"

Full documentation in [`skills/ocsf-lua-serializer/README.md`](skills/ocsf-lua-serializer/README.md).

### Verified behavior

Cold-start tested by fresh subagents on sources NOT in the original
reference library:

| Source | Target class | Predicted grade | Outcome |
|---|---|---|---|
| Mimecast email security | 2004 Detection Finding | B/88 | ✓ Reference promoted to library, 4 new patterns extracted |
| Cisco Umbrella DNS | 4003 DNS Activity | B/87 | ✓ Reference promoted with IANA QTYPE/RCODE maps + 2 new patterns |
| Netskope CASB | 6005 CSPM Finding | A/90 | ✓ Patterns #17–#24 extracted in v1.4 |

The skill is self-improving: running it against novel sources surfaces
vocabulary it lacks, which we capture as numbered patterns.

### Skill structure

- `SKILL.md` — description and triggering guidance
- `ocsf_class_catalog.md` — 20 OCSF classes documented inline with required
  and optional fields
- `references/ocsf-schema-index.md` — ALL OCSF classes (1001–6007) with
  authoritative SentinelOne SDL article URLs
- `references/ocsf-schema-documentation.md` — full per-class OCSF field-name
  reference (~940 KB, every class with all required and optional fields)
- `reference_examples/` — A/B-graded Lua templates (Proofpoint v8 is the
  gold-standard reference, live-deployment tested)
- `methodology.md` — numbered patterns: helper conventions, timezone
  parsing, polymorphic identity routing, vendor taxonomy handling, and more
- `validation_checklist.md` — per-class required-field checklist
- `templates/` — scaffolds for the 4-file output bundle

---

## 🔗 Live ai-siem pull requests

The transforms in this skill come from two open PRs against the SentinelOne
AI SIEM community pipelines repo:

| PR | Branch | Scope |
|---|---|---|
| [`Sentinel-One/ai-siem#53`](https://github.com/Sentinel-One/ai-siem/pull/53) | [`feat/transform-ocsf-community-pipelines`](https://github.com/natesmalley/ai-siem/tree/feat/transform-ocsf-community-pipelines) | 123 OCSF Lua transforms across 14 classes, full 4-file bundle layout, GRADES.md, README |
| [`Sentinel-One/ai-siem#54`](https://github.com/Sentinel-One/ai-siem/pull/54) | [`feat/transform-ocsf-remediation-7`](https://github.com/natesmalley/ai-siem/tree/feat/transform-ocsf-remediation-7) | 7 remediated transforms (Proofpoint Mail v8, Mimecast, Cisco Umbrella, + 4 more), stacked on #53 |

Merged transforms end up under
[`pipelines/community/transform_ocsf/`](https://github.com/Sentinel-One/ai-siem/tree/main/pipelines/community/transform_ocsf)
on `main`.

---

## 📚 Secondary: shipped transform library

The skill's reference examples are extracted from a larger library of
**130 production-graded OCSF Lua serializers** covering AWS, Azure, GCP,
Cisco, Fortinet, Okta, Microsoft, Palo Alto, Proofpoint, Snyk, Tenable,
and more.

The library lives in
[`Sentinel-One/ai-siem/pipelines/community/transform_ocsf/`](https://github.com/Sentinel-One/ai-siem/tree/main/pipelines/community/transform_ocsf)
and was validated by the harness in this repo (see Advanced below).

---

## ⚙️ Advanced: harness, generator, and workbench

The rest of this repo is an operator-focused authoring harness — Purple
Pipeline Parser Eater 2 (PPPE2). Use it if you want to:

- Grade your own Lua serializers through a 5-module validation harness
- Auto-generate new Lua from parser configs via the agentic LLM pipeline
- Hack on the Monaco-based parser workbench
- Add new reference examples to the skill library

PPPE2 takes SentinelOne SIEM parser definitions, feeds them through an
AI-powered conversion pipeline (Claude, GPT, or Gemini), and produces
OCSF-compliant Lua scripts ready to deploy on
[Observo.ai](https://observo.ai) — either the SaaS console or a standalone
dataplane binary. Every generated script is scored by a five-check
deterministic harness before a human ever sees it, and a Flask workbench
lets operators inspect, edit, re-test, and approve results one parser at
a time.

![Main Workbench View](docs/screenshots/00-main-workflow.png)

### Architecture at a glance

```text
                          +---------------------------+
                          |     Browser / Operator     |
                          +------------+--------------+
                                       |
                               :8080 (HTTP)
                                       |
               +-----------------------v-----------------------+
               |            gunicorn web worker                 |
               |  Flask review UI + workbench + Settings tab    |
               |  wsgi_production.py -> build_production_app()  |
               |                                                |
               |  StateStore (follower)   FeedbackChannel (w)   |
               |  RuntimeProxy (reader)                         |
               +----------+------------------+-----------------+
                          |                  |
                   file IPC (data/ volume)   |
                          |                  |
               +----------v------------------v-----------------+
               |           conversion worker                    |
               | continuous_conversion_service.py --worker-only |
               |                                                |
               |  1. GitHub sync loop   (~60 min)               |
               |  2. Conversion loop    (pop queue -> LLM)      |
               |  3. Feedback drain     (approve/reject/modify) |
               |                                                |
               |  StateStore (writer)   FeedbackChannel (r)     |
               +----------+-----------------------------------+
                          |
                   LLM API calls
                          |
          +---------------v---------------+
          |  Anthropic / OpenAI / Gemini  |
          +-------------------------------+

  Optional (--profile rag):
  +--------+    +------+    +-------+
  | Milvus | <- | etcd | <- | MinIO |
  +--------+    +------+    +-------+
```

**Two sibling processes, one shared `data/` volume.** The web worker serves
the UI; the conversion worker runs the AI pipeline. They coordinate through
JSON files on the `app-data` Docker volume — no Redis, no message queue,
no database required for core operation.

### Feature highlights

| Feature | Description |
|---------|-------------|
| **Multi-provider LLM** | Anthropic Claude, OpenAI GPT, and Google Gemini — switch at runtime via the Settings tab |
| **Iterative refinement** | Harness feedback loop with automatic model escalation (Haiku → Sonnet → Opus) when scores are low |
| **5-check harness** | Lua validity, linting, OCSF field mapping, source field coverage, and live event execution via `lupa` |
| **7-tab workbench** | Lua Code, Lua Fields, Lint Results, OCSF Mapping, Test Events, Playground, Settings |
| **Dual deploy targets** | SaaS REST API (camelCase JSON) and standalone dataplane binary (snake_case YAML) |
| **GitHub integration** | Auto-scan SentinelOne parser repos, upload approved Lua as PRs |
| **Feedback learning** | Inline corrections persist to JSONL and optionally to Milvus RAG for future prompt enrichment |
| **STIG-hardened Docker** | Read-only root filesystem, non-root user, capability drop, resource limits |

### Active harness areas

| Path | What it is |
|---|---|
| `components/testing_harness/` | Harness execution, linting, compatibility adapters |
| `components/web_ui/` | Parser workbench UI + API routes/jobs |
| `data/harness_examples/` | Curated parser/sample index + history |
| `output/generated_lua/` | Generated Lua artifacts |
| `output/harness_reports/` | Harness run reports |
| `output/parser_lua_serializers/` | Parser serializer outputs |
| `docs/harness/` | Roadmap + milestone acceptance gates |

Operator documentation lives in [`docs/harness/`](docs/harness/):

- [`docs/harness/technical-roadmap.md`](docs/harness/technical-roadmap.md)
- [`docs/harness/acceptance-criteria.md`](docs/harness/acceptance-criteria.md)
- [`docs/harness/model-and-scoring-strategy.md`](docs/harness/model-and-scoring-strategy.md)
- [`AGENTS.md`](AGENTS.md)

Observo Lua Script contract:
[docs.observo.ai/…/lua-script](https://docs.observo.ai/6S3TPBguCvVUaX3Cy74P/working-with-data/transforms/functions/lua-script)

### Quick start

#### Prerequisites

- Python 3.11+
- At least one LLM API key (Anthropic, OpenAI, or Gemini)
- Docker and Docker Compose (for containerized deployment)

#### Docker (recommended)

The repository includes `docker-compose.yml` at the project root. Compose
uses a published GHCR image by default:
`ghcr.io/natesmalley/purple-pipeline-parser-eater:latest`.

```bash
git clone https://github.com/natesmalley/Purple-Pipeline-Parser-Eater.git
cd Purple-Pipeline-Parser-Eater
cp .env.example .env

# Edit .env — set at least one LLM key and generate auth secrets:
#   ANTHROPIC_API_KEY=sk-ant-your-key-here
#   FLASK_SECRET_KEY=$(openssl rand -hex 32)
#   WEB_UI_AUTH_TOKEN=$(openssl rand -hex 32)

# optional: pin image tag
# export PPPE_TAG=sha-<commit>

# pull images first
docker compose --env-file .env pull

# start harness-only services (default)
docker compose --env-file .env up -d

# start with optional RAG stack (Milvus/MinIO/etcd)
docker compose --env-file .env --profile rag up -d

# check status / logs / stop
docker compose --env-file .env ps
docker compose --env-file .env logs -f parser-eater
docker compose --env-file .env down
```

Open [http://localhost:8080/workbench](http://localhost:8080/workbench)
to access the review UI.

**Notes:**

- End users should pull and run the published image; local Dockerfile
  builds are optional for contributors.
- CI publishes new images to GHCR on `main` and version tags.
- `main` is harness-first by default; full-RAG baseline is preserved on
  branch `rag-full-preservation`.
- Container runs as non-root `uid:gid 999:999`.
- Do not `chown` your repo files to `999:999` — not required.
- `config.yaml` is mounted read-only; `chmod 644` is sufficient.
- Runtime writes go to named Docker volumes (`app-output`, `app-logs`,
  `app-data`), not your repo working tree.

#### Image size expectations

- Harness-first image excludes optional RAG ML/vector dependencies by default.
- Full-RAG images are much larger (torch/CUDA wheels, embedding libraries).
- Use default compose for harness-only workflows.
- Enable `--profile rag` only when you explicitly need Milvus-backed semantic
  retrieval.

#### Local development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set at least one LLM API key
mkdir -p logs

# Service + workbench at http://localhost:8080/
python continuous_conversion_service.py

# Or one-shot CLI batch
python main.py --dry-run --max-parsers 1
```

### Workbench screenshots

| Tab | Screenshot |
|-----|-----------|
| Workbench Overview | ![Overview](docs/screenshots/01-workbench-overview.png) |
| Lua Fields | ![Fields](docs/screenshots/02-lua-fields-tab.png) |
| Lint Results | ![Lint](docs/screenshots/03-lint-results-tab.png) |
| OCSF Mapping | ![OCSF](docs/screenshots/04-ocsf-mapping-tab.png) |
| Test Events | ![Tests](docs/screenshots/05-test-events-tab.png) |
| Playground | ![Playground](docs/screenshots/06-playground-tab.png) |
| Settings | ![Settings](docs/screenshots/07-settings-tab.png) |

### Documentation

| Document | Audience | Description |
|----------|----------|-------------|
| [Operator's Guide](docs/user-guide.md) | Operators | End-to-end walkthrough of the workbench, generation, testing, and deployment |
| [Architecture](docs/architecture.md) | Developers | Two-process model, IPC, conversion pipeline, harness internals, LLM abstraction |
| [API Reference](docs/api-reference.md) | Developers | Complete REST API with request/response examples |
| [Deployment Guide](docs/deployment.md) | DevOps | Docker Compose, environment variables, production hardening, monitoring |

### Environment setup

```bash
cp .env.example .env
```

**Required in `.env`:** at least one of `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
or `GEMINI_API_KEY`. `FLASK_SECRET_KEY` is required in production.
`WEB_UI_AUTH_TOKEN` is required for non-loopback binds.

**Optional in `.env`:**

- `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` (only for `--profile rag`)
- `GITHUB_TOKEN`
- `WORKBENCH_MAX_SAMPLE_CHARS` (default `150000`)
- `WORKBENCH_MAX_TOTAL_SAMPLE_CHARS` (default `1500000`)

**Provider behavior:**

- Harness supports Anthropic, OpenAI, and Gemini keys.
- If only one key is present, that provider is used.
- If multiple keys are present, set `LLM_PROVIDER_PREFERENCE` explicitly in `.env`.
- `.env.example` defaults `LLM_PROVIDER_PREFERENCE=anthropic` to avoid
  accidental OpenAI-first failures.
- Tune cost/performance with `OPENAI_MODEL`, `ANTHROPIC_MODEL`, `GEMINI_MODEL`,
  `LLM_MAX_TOKENS`.
- Generation uses cheap-first model selection with auto-escalation when
  score stays below threshold.
- Override escalation targets with `OPENAI_STRONG_MODEL`,
  `ANTHROPIC_STRONG_MODEL`, and `GEMINI_STRONG_MODEL`.

Selected variables (see [Deployment Guide](docs/deployment.md) for the full table):

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `ANTHROPIC_API_KEY` | One LLM key required | — | Anthropic Claude API key |
| `OPENAI_API_KEY` | One LLM key required | — | OpenAI API key |
| `GEMINI_API_KEY` | One LLM key required | — | Google Gemini API key |
| `LLM_PROVIDER_PREFERENCE` | No | `anthropic` | Active provider: `anthropic`, `openai`, or `gemini` |
| `FLASK_SECRET_KEY` | Yes (production) | — | Flask session signing key |
| `WEB_UI_AUTH_TOKEN` | Yes (non-loopback) | — | Bearer token for API auth |
| `GITHUB_TOKEN` | No | — | GitHub API token for parser sync and PR upload |

### Primary harness use cases

1. **Run the workbench service**

   ```bash
   mkdir -p logs
   python continuous_conversion_service.py
   ```

2. **Targeted harness/workbench checks (smallest-first):**

   ```bash
   pytest tests/test_workbench_root_redirect.py -q
   pytest tests/test_harness_cli_smoke.py -q
   pytest tests/test_workbench_jobs_api.py -q
   pytest tests/test_parser_workbench.py -q
   pytest tests/test_harness_ocsf_alignment.py -q
   pytest tests/test_harness_deterministic_reporting.py -q
   pytest tests/test_harness_compatibility_matrix.py -q
   ```

3. **Broader harness validation (when needed):**

   ```bash
   pytest tests/test_workbench_*.py tests/test_parser_workbench.py tests/test_harness_*.py -v
   ```

4. **Type checking:**

   ```bash
   mypy components/
   ```

5. **Generate cleanup manifests for review:**

   ```bash
   python scripts/utils/harness_cleanup_inventory.py
   ```

   Manifest outputs:

   - `data/cleanup_manifests/keep_manifest.json`
   - `data/cleanup_manifests/delete_manifest.json`

`lupa` is required for Lua execution tests — `pip install lupa` if you see
unexpected skips.

### Project structure

```text
.
├── continuous_conversion_service.py   # Conversion worker (3 async loops)
├── wsgi_production.py                 # Gunicorn WSGI entry point
├── main.py                            # One-shot CLI batch entry
├── components/
│   ├── lua_generator.py               # Unified LLM conversion engine
│   ├── agentic_lua_generator.py       # Iterative-mode shim + prompt builders
│   ├── llm_provider.py                # Multi-provider LLM abstraction
│   ├── settings_store.py              # Persistent settings with env fallthrough
│   ├── feedback_system.py             # Correction persistence (JSONL + Milvus)
│   ├── state_store.py                 # Writer/follower state for IPC
│   ├── feedback_channel.py            # Append-only action bus (web → worker)
│   ├── runtime_proxy.py               # Web-side shim for worker status
│   ├── observo_client.py              # SaaS REST API client
│   ├── dataplane_yaml_builder.py      # Standalone YAML builder
│   ├── web_ui/
│   │   ├── app.py                     # Flask app factory
│   │   ├── routes.py                  # All route handlers
│   │   ├── parser_workbench.py        # Workbench build/validate/test logic
│   │   └── security.py                # Auth, CSRF, secret key enforcement
│   └── testing_harness/
│       ├── harness_orchestrator.py    # 5-check scoring engine
│       ├── dual_execution_engine.py   # Lupa Lua sandbox
│       ├── lua_linter.py              # Syntax + helper usage checks
│       ├── ocsf_schema_registry.py   # OCSF field definitions
│       └── jarvis_event_bridge.py     # Realistic test events for ~40 parsers
├── data/                              # Shared IPC volume
├── output/                            # Accepted Lua + reports
├── docs/                              # Documentation + screenshots
└── tests/                             # pytest suites
```

### Environment cleanup

There is no standalone `observo/` directory in this repository.

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

# optional full environment reset
rm -rf .venv
```

Do not remove tracked corpus files under `output/` or `data/harness_examples/`
unless a milestone explicitly requires it.

### Authoring contract

- Canonical Lua authoring contract is `processEvent(event)`.
- `transform(record)` is compatibility-only and remains supported.
- Dataset traversal and report output are expected to be deterministic.
- Scope is milestone-driven; avoid unrelated platform refactors.

### Contributing

1. Fork the repo and create a feature branch
2. Follow the existing code style (`mypy` for type checking; no ruff/black/flake8)
3. Add or update tests for your changes
4. Run `pytest tests/test_harness_cli_smoke.py -q` as a minimum before pushing
5. Run `scripts/run_gitleaks.sh` if you touched any token-shaped strings
6. Run `scripts/run_pip_audit.sh` if you modified `requirements.txt`
7. Keep diffs small and focused — one concern per PR
8. Submit a pull request with a clear description of the change

---

## License

AGPL-3.0 (matches the parent `Sentinel-One/ai-siem` repo).
