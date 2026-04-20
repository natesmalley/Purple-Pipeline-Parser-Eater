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

**Current version: v1.2** — 13 A/B-graded reference serializers, 16 numbered
patterns from live deployment + cold-start subagent testing, full OCSF schema
index with SentinelOne SDL article URLs.

### Install

**Claude Desktop / Cowork mode** — download the `.skill` file and double-click:

📦 [**Download `ocsf-lua-serializer.skill`**](skills/ocsf-lua-serializer/ocsf-lua-serializer.skill) (76 KB)

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

Cold-start tested by fresh subagents on two sources NOT in the original
reference library:

| Source | Target class | Predicted grade | Outcome |
|---|---|---|---|
| Mimecast email security | 2004 Detection Finding | B/88 | ✓ Reference promoted to library, 4 new patterns extracted |
| Cisco Umbrella DNS | 4003 DNS Activity | B/87 | ✓ Reference promoted with IANA QTYPE/RCODE maps + 2 new patterns |

Both tests surfaced real gaps that became first-class patterns in v1.1/v1.2.
The skill is self-improving: running it against novel sources surfaces
vocabulary it lacks, which we capture as numbered patterns.

### Skill structure

- `SKILL.md` — description and triggering guidance
- `ocsf_class_catalog.md` — 20 OCSF classes documented inline with required
  and optional fields
- `references/ocsf-schema-index.md` — ALL OCSF classes (1001–6007) with
  authoritative SentinelOne SDL article URLs
- `reference_examples/` — 13 A/B-graded Lua templates (Proofpoint v8 is the
  gold-standard reference, live-deployment tested)
- `methodology.md` — 16 numbered patterns: helper conventions, timezone
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

The rest of this repo is an operator-focused authoring harness. Use it if you
want to:

- Grade your own Lua serializers through a 5-module validation harness
- Auto-generate new Lua from parser configs via the agentic LLM pipeline
- Hack on the Monaco-based parser workbench
- Add new reference examples to the skill library

Full operator documentation in [`docs/harness/`](docs/harness/):

- [`docs/harness/technical-roadmap.md`](docs/harness/technical-roadmap.md)
- [`docs/harness/acceptance-criteria.md`](docs/harness/acceptance-criteria.md)
- [`docs/harness/model-and-scoring-strategy.md`](docs/harness/model-and-scoring-strategy.md)
- [`AGENTS.md`](AGENTS.md)

Observo Lua Script contract:
[docs.observo.ai/…/lua-script](https://docs.observo.ai/6S3TPBguCvVUaX3Cy74P/working-with-data/transforms/functions/lua-script)

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

### Quick start (harness)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.yaml.example ./config.yaml
mkdir -p logs
python continuous_conversion_service.py
```

Workbench: `http://localhost:8080/workbench`

### Environment setup (harness)

```bash
cp .env.example .env
```

**Required in `.env`:** at least one of `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`.

**Optional in `.env`:**
- `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` (only for `--profile rag`)
- `GITHUB_TOKEN`
- `WORKBENCH_MAX_SAMPLE_CHARS` (default `150000`)
- `WORKBENCH_MAX_TOTAL_SAMPLE_CHARS` (default `1500000`)

**Provider behavior:**

- Harness supports both Anthropic and OpenAI keys.
- If only one key is present, that provider is used.
- If both keys are present, set `LLM_PROVIDER_PREFERENCE` explicitly in `.env`.
- `.env.example` defaults `LLM_PROVIDER_PREFERENCE=anthropic` to avoid
  accidental OpenAI-first failures.
- Tune cost/performance with `OPENAI_MODEL`, `ANTHROPIC_MODEL`, `LLM_MAX_TOKENS`.
- Generation uses cheap-first model selection with auto-escalation when
  score stays below threshold.
- Override escalation targets with `OPENAI_STRONG_MODEL` and
  `ANTHROPIC_STRONG_MODEL`.
- Workbench/API routes do not require token headers.

### Docker Compose (recommended for local development)

The repository includes `docker-compose.yml` at the project root. Compose
uses a published GHCR image by default:
`ghcr.io/natesmalley/purple-pipeline-parser-eater:latest`.

```bash
cp .env.example .env

# optional: pin image tag
# export PPPE_TAG=sha-<commit>

# required: pull images first
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

**Notes:**

- End users should pull and run the published image; local Dockerfile builds
  are optional for contributors.
- CI publishes new images to GHCR on `main` and version tags.
- `main` is harness-first by default; full-RAG baseline is preserved on
  branch `rag-full-preservation`.
- Container runs as non-root `uid:gid 999:999`.
- Do not `chown` your repo files to `999:999` — not required.
- `config.yaml` is mounted read-only; `chmod 644` is sufficient.
- Runtime writes go to named Docker volumes (`app-output`, `app-logs`,
  `app-data`), not your repo working tree.

### Image size expectations

- Harness-first image excludes optional RAG ML/vector dependencies by default.
- Full-RAG images are much larger (torch/CUDA wheels, embedding libraries).
- Use default compose for harness-only workflows.
- Enable `--profile rag` only when you explicitly need Milvus-backed semantic
  retrieval.

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

4. **Generate cleanup manifests for review:**

   ```bash
   python scripts/utils/harness_cleanup_inventory.py
   ```

   Manifest outputs:

   - `data/cleanup_manifests/keep_manifest.json`
   - `data/cleanup_manifests/delete_manifest.json`

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

---

## License

AGPL-3.0 (matches the parent `Sentinel-One/ai-siem` repo).
