# Operator's Guide

A hands-on guide for operators who use Purple Pipeline Parser Eater 2 to convert SentinelOne parsers into OCSF-compliant Lua for Observo.ai.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Workbench Overview](#workbench-overview)
- [Tab-by-Tab Walkthrough](#tab-by-tab-walkthrough)
  - [Lua Code](#1-lua-code)
  - [Lua Fields](#2-lua-fields)
  - [Lint Results](#3-lint-results)
  - [OCSF Mapping](#4-ocsf-mapping)
  - [Test Events](#5-test-events)
  - [Playground](#6-playground)
  - [Settings](#7-settings)
- [Generating Lua from Samples](#generating-lua-from-samples)
- [Validating and Testing Generated Lua](#validating-and-testing-generated-lua)
- [Playground: Ad-Hoc Testing](#playground-ad-hoc-testing)
- [Settings Tab: LLM Configuration](#settings-tab-llm-configuration)
- [Integrations](#integrations)
- [Feedback System](#feedback-system)
- [RAG Toggle](#rag-toggle)
- [Troubleshooting](#troubleshooting)

---

## Getting Started

### Docker Compose (recommended)

```bash
cp .env.example .env
# Edit .env:
#   - Set at least one LLM API key (ANTHROPIC_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY)
#   - Generate FLASK_SECRET_KEY:    openssl rand -hex 32
#   - Generate WEB_UI_AUTH_TOKEN:   openssl rand -hex 32

docker compose --env-file .env up -d
```

Once the health check passes (~2 minutes), open [http://localhost:8080/workbench](http://localhost:8080/workbench).

### Local development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set at least one LLM API key
python continuous_conversion_service.py
```

The embedded Flask server starts on port 8080. No `WEB_UI_AUTH_TOKEN` is required when binding to localhost.

### First steps after startup

1. Navigate to the **Settings** tab and verify your LLM provider key is detected (a green checkmark appears next to the active provider).
2. Use the **Test Connection** button to confirm API access.
3. Switch to the main workbench view and select a parser from the dropdown -- or paste raw log samples to start a fresh build.

---

## Workbench Overview

The workbench is a single-page application at `/workbench` with seven tabs. Each tab addresses a different stage of the conversion lifecycle.

![Workbench Overview](screenshots/01-workbench-overview.png)

The left panel shows the parser selector and sample input area. The right panel contains the seven tabs described below.

---

## Tab-by-Tab Walkthrough

### 1. Lua Code

The primary editing surface. After a build completes, the generated Lua script appears here with syntax highlighting.

![Lua Code Tab](screenshots/00-main-workflow.png)

**What you can do:**

- Read through the generated `process(event, emit)` wrapper and the inner `processEvent(event)` logic
- Make inline edits directly in the code editor
- Re-run validation or lint checks after editing
- Copy the final script for deployment

The code follows the Observo Lua v3 contract: a top-level `process(event, emit)` function that receives the event, transforms it, and calls `emit()` with the result. OCSF helper functions (`getNestedField`, `setNestedField`, `flattenObject`) are inlined at the top of every script.

### 2. Lua Fields

Shows every field the generated Lua reads from the source event and every OCSF field it writes to the output.

![Lua Fields Tab](screenshots/02-lua-fields-tab.png)

Use this tab to quickly check:

- Whether critical source fields are being consumed
- Whether required OCSF fields (`class_uid`, `category_uid`, `activity_id`, `time`, `type_uid`, `severity_id`) are being set
- Field mapping completeness at a glance

### 3. Lint Results

Displays output from the built-in Lua linter, which checks for:

- Syntax errors (AST parse failures)
- Incorrect or missing helper function usage
- `setNestedField` pattern violations
- Embedded-payload extraction issues (e.g., JSON inside a `message` field)

![Lint Results Tab](screenshots/03-lint-results-tab.png)

Green means clean. Any warnings or errors appear with line numbers and descriptions. Fix issues in the Lua Code tab and re-lint to verify.

### 4. OCSF Mapping

A structured view of how source fields map to OCSF schema fields for the detected class (e.g., Security Finding 2001, Detection Finding 2004).

![OCSF Mapping Tab](screenshots/04-ocsf-mapping-tab.png)

The mapping shows:

- The OCSF class and category detected for this parser
- Required fields and whether they are present in the generated Lua
- Optional fields that were populated
- Any missing required fields flagged as errors

### 5. Test Events

Runs the generated Lua against test events in the `lupa` sandbox and shows per-event pass/fail results.

![Test Events Tab](screenshots/05-test-events-tab.png)

The harness uses two event sources:

- **Jarvis events**: hardcoded realistic events for approximately 40 known parsers (Akamai DNS, Duo, Defender, Okta, etc.) -- these produce the best coverage numbers.
- **Synthetic events**: auto-generated fallback events when a parser is not in the Jarvis bridge. Coverage will be thinner.

Each event shows the input, the transformed output, and whether OCSF required fields are present.

### 6. Playground

An ad-hoc execution environment where you can paste arbitrary log samples and run them through any generated Lua script.

![Playground Tab](screenshots/06-playground-tab.png)

Use the Playground to:

- Test edge cases not covered by the standard test events
- Paste real production log lines and verify correct parsing
- Experiment with Lua modifications before committing them
- Validate that embedded payloads (JSON inside `message` fields) are extracted correctly

### 7. Settings

Runtime configuration for LLM providers, tuning knobs, and integrations.

![Settings Tab](screenshots/07-settings-tab.png)

See the [Settings Tab: LLM Configuration](#settings-tab-llm-configuration) section below for details.

---

## Generating Lua from Samples

### Step 1: Select or create a parser

Choose an existing parser from the dropdown, or start fresh by entering a parser name and pasting raw log samples into the sample input area.

### Step 2: Build

Click **Build** (or call `POST /api/v1/workbench/build`). The system will:

1. Classify the OCSF class by analyzing parser name, vendor, product, and sample content
2. Extract source fields from the parser definition
3. Run a sample-format preflight (JSON, CSV, KV, syslog, XML, embedded payloads)
4. Build a system prompt with OCSF patterns and helper functions, plus a user prompt with the parser analysis and sample events
5. Call the LLM and return the generated Lua

### Step 3: Review

Switch between tabs to inspect the result:

- **Lua Code** for the script itself
- **Lint Results** for syntax/quality issues
- **OCSF Mapping** for field coverage
- **Test Events** to see execution results

### Step 4: Iterate (if needed)

If the harness score is below your threshold, you can:

- Edit the Lua directly in the code editor and re-validate
- Use the **Agent Build** endpoint for iterative refinement with model escalation (Haiku -> Sonnet -> Opus)
- Save inline corrections to improve future generations

### Step 5: Approve or reject

From the review queue (`GET /`), approve the conversion to move it to the `output/` directory, or reject it with a reason.

---

## Validating and Testing Generated Lua

Three validation actions are available from the workbench:

| Action | Endpoint | What it checks |
| ------ | -------- | -------------- |
| **Validate** | `GET /api/v1/workbench/validate/<parser>` | Full 5-check harness run (syntax, lint, OCSF, coverage, execution) returning a 0-100 score |
| **Lint** | `GET /api/v1/workbench/lint/<parser>` | Lua linting only (faster, no event execution) |
| **Test Run** | `POST /api/v1/workbench/test-run/<parser>` | Execute Lua against test events and return per-event results |

The validate endpoint returns a structured report:

```json
{
  "score": 85,
  "checks": {
    "lua_validity": "pass",
    "lua_lint": "pass",
    "ocsf_mapping": "pass",
    "source_coverage": "warning",
    "event_execution": "pass"
  },
  "missing_fields": ["dst_endpoint.ip"],
  "lint_errors": [],
  "events": [...]
}
```

---

## Playground: Ad-Hoc Testing

The Playground (tab 6) provides a free-form execution environment:

1. Paste one or more log lines into the **Sample Events** input
2. Paste or load a Lua script into the **Lua Script** input
3. Click **Execute**
4. Review the transformed output and any errors

The Playground uses the same `lupa` sandbox as the harness, with identical helper functions available. This is the fastest way to debug field mappings or test production log lines.

---

## Settings Tab: LLM Configuration

The Settings tab exposes runtime configuration without requiring a restart for most changes.

### Switching providers

The **Primary AI Provider** control lets you switch between Anthropic, OpenAI, and Gemini. Each provider has two model slots:

| Slot | Purpose | Env var examples |
| ---- | ------- | ---------------- |
| **Standard model** | First attempt, lower cost | `ANTHROPIC_MODEL`, `OPENAI_MODEL`, `GEMINI_MODEL` |
| **Strong model** | Escalation when harness score < 70 | `ANTHROPIC_STRONG_MODEL`, `OPENAI_STRONG_MODEL`, `GEMINI_STRONG_MODEL` |

### Test Connection

Each provider section has a **Test Connection** button that sends a minimal API call to verify credentials. A green checkmark confirms access; a red error shows the failure reason.

### Tuning knobs

| Setting | Default | Description |
| ------- | ------- | ----------- |
| Temperature | 0 (locked) | Pinned to zero for deterministic output. Read-only in the UI. |
| Max tokens | 3000 | Maximum tokens per LLM response |
| Max iterations | 2 | Number of harness-feedback iterations before escalating |
| Max sample chars | 150,000 | Per-sample character limit for workbench input |
| Max total sample chars | 1,500,000 | Total character limit across all samples |

### Restart-required settings

Some settings (provider API keys, RAG toggle) require a worker restart to take effect. The Settings tab shows a banner when a restart is needed, and the **Restart Worker** button triggers it.

---

## Integrations

### GitHub PR upload

After approving a conversion, you can upload the Lua script as a pull request to your configured GitHub repository:

1. Set `GITHUB_TOKEN` in your `.env` or via the Settings tab
2. Configure `integrations.github.owner` and `integrations.github.repo`
3. Use the **Upload PR** button in the workbench or call `POST /api/v1/workbench/upload-pr`

The PR includes the generated Lua file and a summary of the harness score.

### Observo deploy

For SaaS console users, approved Lua can be deployed directly:

1. Set your Observo API key via the Settings tab or `OBSERVO_API_KEY` env var
2. The deploy path calls `POST /gateway/v1/deserialize-pipeline` with `deployPipeline: true`
3. Use `--dry-run` in CLI mode to test without deploying

For standalone dataplane users, the system generates a Vector YAML config file that you apply with `./dataplane --config <file>.yaml`.

### SDL audit logging

When SentinelOne SDL integration is configured (`integrations.sdl.*` settings), every approve/reject/modify action is logged to the SDL audit endpoint for compliance tracking.

---

## Feedback System

PPPE2 learns from operator corrections to improve future generations.

### Providing feedback

- **Thumbs up/down**: Quick signal on generation quality. Available on the review queue and workbench.
- **Inline corrections**: Edit the Lua in the code editor, then click **Save Correction** (`POST /api/v1/workbench/save-correction`). The system records a before/after diff with your explanation.
- **Match feedback**: Use `POST /api/v1/workbench/match-feedback` to flag specific field mappings as correct or incorrect.

### How corrections improve future output

Corrections persist to `data/feedback/corrections.jsonl` as the primary sink. When RAG is enabled, they are also upserted to the Milvus vector database.

On the next build for the same parser (or a parser with similar characteristics), the correction history is injected into the LLM prompt as additional context. This is currently a re-scan process -- corrections are read from the JSONL file at prompt-build time, not streamed in real time.

---

## RAG Toggle

RAG (Retrieval-Augmented Generation) uses Milvus to store and retrieve prior corrections and examples as vector embeddings.

**With RAG enabled** (`rag.enabled: true` in `config.yaml`):

- Corrections are stored in both JSONL and Milvus
- Future builds can retrieve semantically similar corrections
- Requires Milvus, etcd, and MinIO (use `--profile rag` with Docker Compose)

**With RAG disabled** (default for local dev):

- Corrections persist to JSONL only
- No vector retrieval -- prompts use static patterns only
- No additional infrastructure required

Toggle RAG in `config.yaml` under `rag.enabled` or via the Settings tab. A worker restart is required after changing this setting.

---

## Troubleshooting

### The workbench shows "No LLM provider configured"

Set at least one API key:

- `ANTHROPIC_API_KEY` in `.env`, or
- `OPENAI_API_KEY` in `.env`, or
- `GEMINI_API_KEY` in `.env`

Alternatively, enter the key in the Settings tab and click Save.

### Build returns empty or truncated Lua

- Check `LLM_MAX_TOKENS` -- increase to 4000 or higher for complex parsers
- Verify the sample input is not exceeding `WORKBENCH_MAX_SAMPLE_CHARS` (default 150,000)
- Check the container logs: `docker compose logs -f parser-eater`

### Test events show "lupa not available"

Install the Lua runtime: `pip install lupa`. In Docker, `lupa` is included in the image.

### Harness score is low for my parser

- Check if your parser has Jarvis bridge events (only ~40 parsers are covered). Without realistic test events, scores rely on synthetic fallback data.
- Review the **OCSF Mapping** tab for missing required fields
- Check **Lint Results** for helper function issues
- Try an **Agent Build** which uses iterative refinement with model escalation

### Container fails to start with "FLASK_SECRET_KEY must be set"

Generate a key and add it to your `.env`:

```bash
echo "FLASK_SECRET_KEY=$(openssl rand -hex 32)" >> .env
```

### Container fails with "WEB_UI_AUTH_TOKEN must be set"

Required when binding to `0.0.0.0` (the Docker default). Generate and add to `.env`:

```bash
echo "WEB_UI_AUTH_TOKEN=$(openssl rand -hex 32)" >> .env
```

### Worker is not picking up settings changes

Some settings require a worker restart. Click **Restart Worker** in the Settings tab, or restart the container:

```bash
docker compose restart parser-eater-worker
```

### Permission errors with read-only filesystem in Docker

The Docker image uses a read-only root filesystem. Writable locations use tmpfs mounts. If you see permission errors:

1. Verify tmpfs mounts are configured in `docker-compose.yml`
2. Check that UID/GID 999 matches the `appuser` in the container
3. Review logs: `docker compose logs -f parser-eater`
