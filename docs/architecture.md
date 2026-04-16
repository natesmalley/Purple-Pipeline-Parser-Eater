# Technical Architecture

A deep dive into how PPPE2 is built, for developers and contributors.

---

## Table of Contents

- [System Overview](#system-overview)
- [Two-Process Model](#two-process-model)
- [File-Backed IPC](#file-backed-ipc)
- [Conversion Pipeline](#conversion-pipeline)
- [Testing Harness](#testing-harness)
- [LLM Provider Abstraction](#llm-provider-abstraction)
- [Settings Persistence](#settings-persistence)
- [Feedback Loop](#feedback-loop)
- [Observo Target Consoles](#observo-target-consoles)
- [Docker Topology](#docker-topology)
- [Key Design Decisions](#key-design-decisions)

---

## System Overview

PPPE2 converts SentinelOne SIEM parser definitions into OCSF-compliant Lua scripts for Observo.ai. The system has two entry points that share one conversion engine:

- **Continuous service** (`continuous_conversion_service.py`): long-running daemon with GitHub sync, conversion queue, and feedback drain
- **One-shot batch** (`main.py`): CLI tool for scan-analyze-generate-test-deploy in a single run

Both paths feed through `components/lua_generator.py`, the unified LLM conversion engine.

---

## Two-Process Model

Production deployment splits into two sibling containers from the same image:

```text
+----------------------------------+     +----------------------------------+
|        parser-eater              |     |     parser-eater-worker          |
|  gunicorn web worker             |     |  conversion worker               |
|  wsgi_production.py              |     |  continuous_conversion_service   |
|  -> build_production_app()       |     |  --worker-only                   |
|                                  |     |                                  |
|  Serves:                         |     |  Runs:                           |
|  - Flask review UI (:8080)       |     |  1. GitHub sync loop (~60 min)   |
|  - Workbench + 7 tabs            |     |  2. Conversion loop (LLM calls)  |
|  - Settings API                  |     |  3. Feedback drain loop          |
|  - Approve/reject/modify API     |     |                                  |
|                                  |     |  StateStore: WRITER              |
|  StateStore: FOLLOWER            |     |  FeedbackChannel: READER         |
|  FeedbackChannel: WRITER         |     |                                  |
|  RuntimeProxy: READER            |     |                                  |
+----------------------------------+     +----------------------------------+
              |                                        |
              +------------ data/ volume --------------+
```

**Why two processes?** The web worker needs fast, synchronous request handling. The conversion worker runs long async LLM calls (seconds to minutes per parser). Splitting them prevents slow conversions from blocking the UI and allows independent scaling.

**Single-process dev mode**: Running `python continuous_conversion_service.py` without `--worker-only` starts the embedded Flask server and all three loops in one process. This is the convenience fallback for local development.

---

## File-Backed IPC

The two processes coordinate through JSON files on the shared `data/` Docker volume. No Redis, no database, no message queue for core operation.

### StateStore (`components/state_store.py`)

Tracks pending conversions (parser name, status, Lua output, harness score).

- **Writer mode** (conversion worker): holds an `asyncio.Lock` + `threading.Lock`, writes atomically via temp-file-then-rename
- **Follower mode** (web worker): mtime-based hot-reload with a 5-second re-stat throttle; read-only, never writes
- File: `data/state/pending_state.json`

### FeedbackChannel (`components/feedback_channel.py`)

Append-only JSONL bus for user actions (approve, reject, modify).

- **Writer** (web worker): appends action records via `O_APPEND` (atomic for records under `PIPE_BUF`)
- **Reader** (conversion worker): drains actions from a tracked offset
- File: `data/feedback/actions.jsonl`

### RuntimeProxy (`components/runtime_proxy.py`)

Read-only shim that lets the web worker display conversion worker status without an in-process handle.

- Files: `data/runtime/status_snapshot.json`, `data/runtime/pending_requests.json`
- The conversion worker writes snapshots; the web worker reads them

### Advisory locking

`portalocker` provides advisory file locks for the StateStore follower mode, preventing torn reads during atomic writes.

---

## Conversion Pipeline

For each parser, the pipeline runs these steps:

### 1. OCSF class classification

`classify_ocsf_class()` in `agentic_lua_generator.py` keyword-matches the parser name, vendor, product, and sample content to determine the OCSF `class_uid` (e.g., 2001 Security Finding, 2004 Detection Finding, 6001 Network Activity).

### 2. Source field extraction

`SourceParserAnalyzer` from the testing harness extracts the field names that the parser definition reads from raw events.

### 3. Sample-format preflight

`_infer_sample_preflight()` detects the format of sample events: JSON, CSV, KV, syslog, XML, or embedded message payloads (e.g., JSON inside a `message` KV field, common in Akamai and CloudTrail logs).

### 4. Prompt construction

Two prompts are built:

- **System prompt**: static OCSF patterns (A-E), the inlined helper library (`getNestedField`, `setNestedField`, `flattenObject`), and the Observo `process(event, emit)` contract
- **User prompt**: parser analysis, OCSF schema fragment for the detected class, and 1-2 test-event samples

Prior operator corrections from `data/feedback/corrections.jsonl` are injected when available.

### 5. LLM generation

Two modes exist in the unified engine (`components/lua_generator.py`):

**Fast mode** (`mode="fast"`): Single LLM call, no harness feedback, no escalation. Used by the continuous conversion worker and `main.py` batch.

**Iterative mode** (`_run_iterative_loop_sync`): Up to 3 iterations per model tier. Each iteration:

1. Call the LLM with the current prompt
2. Extract Lua from the response
3. Run the full 5-check harness
4. If score >= 70, accept
5. If score < 70, build a refinement prompt with missing fields and lint errors, then retry
6. If still failing after all iterations at one tier, escalate: Haiku -> Sonnet -> Opus (or equivalent for OpenAI/Gemini)

Used by the workbench via `AgenticLuaGenerator`.

### 6. Caching

Accepted Lua + score are written to `output/`. This cache is a manual reference pool -- the `ExampleSelector` retrieval wiring for few-shot learning is not yet implemented.

---

## Testing Harness

The harness (`components/testing_harness/`) runs five checks and produces a 0-100 score.

### Check 1: Lua validity

Parses the script into an AST. Catches syntax errors before any execution.

### Check 2: Lua linting

`lua_linter.py` checks for:

- Correct helper function usage (`setNestedField`, `getNestedField`)
- Pattern violations in field access
- Embedded-payload extraction issues
- Style and correctness warnings

### Check 3: OCSF field mapping

Verifies that required OCSF fields are set for the detected class:

- `class_uid` -- OCSF class identifier
- `category_uid` -- OCSF category
- `activity_id` -- activity type
- `time` -- event timestamp
- `type_uid` -- event type
- `severity_id` -- severity level

### Check 4: Source field coverage

Cross-references the source fields extracted from the parser definition against the generated Lua. Reports the percentage of source fields that are actually consumed.

### Check 5: Test event execution

Runs the Lua against 4 test events in the `lupa` sandbox:

- **Jarvis events** (`jarvis_event_bridge.py`): hardcoded realistic events for ~40 known parsers. These are preferred because they reflect real-world data shapes.
- **Synthetic events** (`TestEventBuilder`): auto-generated fallback when a parser is not in the Jarvis bridge.

Each event is checked for successful execution (no Lua errors) and OCSF field presence in the output.

### Lua sandbox

Both the local runtime executor (`components/transform_executor.py`) and the harness executor (`components/testing_harness/dual_execution_engine.py`) sandbox Lua with:

- `register_eval=False`, `register_builtins=False` in `lupa`
- Dangerous globals (`io`, `package`, `debug`, `load`, `loadfile`, `dofile`) set to `nil`

The two sandbox prelude copies have drifted slightly -- keep them in sync when editing.

---

## LLM Provider Abstraction

`components/llm_provider.py` provides a unified interface across three providers:

```text
LLMProvider (abstract)
  +-- AnthropicProvider   (anthropic SDK)
  +-- OpenAIProvider      (openai SDK)
  +-- GeminiProvider      (google-generativeai SDK)
```

### Provider selection

The active provider is determined by `LLM_PROVIDER_PREFERENCE` (env var) or `providers.active` (settings store). Each provider has two model slots:

| Slot | Purpose | Used when |
| ---- | ------- | --------- |
| Standard | First attempt, lower cost | Always (first iteration) |
| Strong | Escalation target | Harness score < 70 after standard model iterations |

### Escalation ladder

In iterative mode, the escalation follows the model tiers within the active provider:

- Anthropic: Haiku -> Sonnet -> Opus
- OpenAI: gpt-5.4-mini -> gpt-5.4
- Gemini: gemini-3.1-flash-lite -> gemini-3.1-pro

### Temperature

Pinned to `0` for deterministic output. The Settings tab enforces this with a read-only input. Do not reintroduce nonzero temperature.

### `get_provider()` factory

Returns a configured `LLMProvider` instance based on the active settings. Used by `LuaGenerator` and accessed via lazy singleton in `_get_settings_store()`.

---

## Settings Persistence

`components/settings_store.py` manages runtime configuration.

### Storage

- File: `data/settings/credentials.json` on the `app-data` volume
- Thread-safe via `threading.RLock`
- Read performance: mtime-cached with 5-second re-stat throttle

### Schema

```json
{
  "providers": {
    "active": "anthropic",
    "anthropic": { "api_key": "...", "model": "...", "strong_model": "..." },
    "openai": { "api_key": "...", "model": "...", "strong_model": "..." },
    "gemini": { "api_key": "...", "model": "...", "strong_model": "..." }
  },
  "tuning": {
    "llm_max_tokens": 3000,
    "llm_max_iterations": 2,
    "workbench_max_sample_chars": 150000,
    "workbench_max_total_sample_chars": 1500000
  },
  "integrations": {
    "github": { "token": "...", "owner": "...", "repo": "..." },
    "observo": { "api_key": "...", "base_url": "..." },
    "sdl": { "api_url": "...", "api_key": "...", "enabled": false }
  },
  "rag": { "enabled": true }
}
```

### Env-var fallthrough

Every settings path has a corresponding environment variable fallback (defined in `_ENV_FALLBACK`). The resolution order is:

1. Value in `credentials.json`
2. Environment variable
3. Default from `config.yaml`

### Secret redaction

Paths listed in `_SECRET_PATHS` are masked in API responses (`all_redacted()` output). API keys show only the last 4 characters.

### Startup overlay

Settings that cannot change at runtime (e.g., provider API keys for already-initialized clients) are snapshotted at startup. The Settings tab shows a "restart required" banner when these are modified.

---

## Feedback Loop

### Write path

1. Operator provides feedback via the workbench UI:
   - Thumbs up/down on a generation
   - Inline Lua correction with reason
   - Field mapping feedback
2. `FeedbackSystem.record_lua_correction()` writes a record to `data/feedback/corrections.jsonl` (atomic `O_APPEND`)
3. If RAG is enabled, the correction is also upserted to Milvus as a vector embedding (best-effort secondary)

### Read path

At prompt-build time, `read_corrections_for_prompt()` queries the JSONL file for prior corrections matching the current parser name, OCSF class, or vendor. Matched corrections are formatted as before/after/reason strings and injected into the LLM user prompt.

### Limitations

- Corrections are not hot-reloaded into in-flight prompts
- The JSONL reader scans linearly (no index) -- acceptable for the expected correction volume
- Few-shot retrieval from `output/` is not yet wired (the `ExampleSelector` class exists but `.select()` is never called)

---

## Observo Target Consoles

PPPE2 supports two completely separate Observo deployment targets. The generated Lua body is portable; only the surrounding pipeline shape differs.

### SaaS console (REST API)

- Wire format: camelCase JSON
- Deployment: `POST` to `https://p01-api.observo.ai/gateway/v1/*`
- Auth: `Authorization: Bearer <JWT>`
- Code: `components/observo_client.py`, `components/observo_models.py`, `components/observo_pipeline_builder.py`
- Key field: `luaScript` (not `source`, not `script`)

### Standalone dataplane binary (YAML)

- Wire format: snake_case Vector YAML
- Deployment: `./dataplane validate --config file.yaml && ./dataplane --config file.yaml`
- Code: `components/dataplane_yaml_builder.py`
- Key field: `source` (not `luaScript`, not `script`)
- Lua transform version: v3 (`lv3` crate in the Rust binary)

### Runtime details

The dataplane binary is a Rust fork of `timberio/vector` 0.44.7 embedding PUC-Rio Lua 5.4.7 via `mlua` 0.10.2. The Lua VM is unsandboxed (`unsafe_new_with` with all 10 stdlibs). Generated Lua must use Lua 5.4 syntax.

The Observo-injected globals for the v3 `type: lua` transform are:

- `emit` -- function to emit transformed events
- `json` -- JSON encode/decode module

No other helpers are injected. All OCSF helper functions must be inlined in the generated script.

---

## Docker Topology

```text
docker compose up -d
  +-- parser-eater          (web worker, port 8080)
  +-- parser-eater-worker   (conversion worker, no ports)

docker compose --profile rag up -d
  +-- parser-eater          (web worker, port 8080)
  +-- parser-eater-worker   (conversion worker)
  +-- milvus                (vector DB, ports 19530/9091)
  +-- etcd                  (Milvus metadata store)
  +-- minio                 (Milvus object storage)
```

### Volumes

| Volume | Mount point | Purpose |
| ------ | ----------- | ------- |
| `app-data` | `/app/data` | IPC state, feedback, settings, runtime snapshots |
| `app-output` | `/app/output` | Accepted Lua scripts and reports |
| `app-logs` | `/app/logs` | Application logs |
| `milvus-data` | `/var/lib/milvus` | Milvus vector storage (RAG profile only) |
| `etcd-data` | `/etcd` | etcd data (RAG profile only) |
| `minio-data` | `/minio_data` | MinIO object storage (RAG profile only) |

### Security hardening

The Docker configuration implements STIG controls:

- V-230276: Non-root execution (UID/GID 999)
- V-230285: Read-only root filesystem
- V-230286: All capabilities dropped (`cap_drop: ALL`)
- V-230287: No new privileges (`no-new-privileges:true`)
- V-230289: Structured JSON logging with rotation
- V-230290: CPU and memory resource limits

---

## Key Design Decisions

### Temperature = 0

All LLM calls use `temperature=0` for deterministic output. This is enforced in the Settings tab (read-only input) and should not be changed.

### Deterministic traversal

Dataset traversal and report ordering are stable across runs. Tests assert this. No dict-iteration-order or time-based sorting in pipeline logic.

### No tool-use / ReAct

The LLM integration is single-turn per iteration with static harness feedback. The system does not use tool-use or ReAct patterns.

### File IPC over message queues

File-backed IPC was chosen over Redis/Kafka for simplicity and zero-dependency operation. The `message_bus_adapter.py` abstract skeleton exists but has no concrete implementations wired in.

### Lua sandbox divergence from production

The `lupa` sandbox is more restrictive than the production Observo runtime (which is fully unsandboxed). This is intentional -- generated Lua should work in both environments, and the sandbox catches accidental use of dangerous globals.
