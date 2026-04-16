# CLAUDE.md

Converts SentinelOne parsers into Observo.ai OCSF-compliant Lua using Claude, with a deterministic testing harness and a Flask workbench for human review. Two entry points share one conversion engine.

## What the app actually is

Phase 7 / Stream A split what used to be a single long-running daemon into **two sibling processes** that share state over file-backed IPC. Don't describe it as one process — the gunicorn web worker and the conversion worker run independently and talk through files on the `data/` volume.

- **gunicorn web worker** — serves the Flask review UI + workbench on :8080. Built by [wsgi_production.py](wsgi_production.py) `create_app()`, which constructs a four-argument `ServiceContext(state, config, feedback_channel, runtime_proxy)` and hands it to `build_production_app` ([components/web_ui/app.py](components/web_ui/app.py)). `StateStore` runs in **follower mode** here (mtime hot-reload from the conversion worker). Init failures raise a real traceback in the gunicorn worker exit log — no silent `sys.exit(1)` fallback.
- **conversion worker** — [continuous_conversion_service.py](continuous_conversion_service.py) run with `--worker-only`. `async main()` builds `ContinuousConversionService(worker_only=True)` and runs three concurrent loops (the Flask server is skipped when `worker_only=True`, lines 201-203):
  1. **GitHub sync loop** (~60 min): `GitHubParserScanner` pulls new/changed SentinelOne parsers and queues them.
  2. **Conversion loop**: pops queued parsers, calls `convert_parser()` → `ClaudeLuaGenerator.generate_lua()` ([components/lua_generator.py:937](components/lua_generator.py#L937) — now a **legacy shim** that delegates to `LuaGenerator.agenerate(mode="fast")`; single Anthropic call per parser, **no harness feedback loop, no model escalation** — this is a *mode choice*, not a separate engine, see "One generator, two modes" below), stores results via `StateStore` (writer side) into `data/state/pending_state.json`.
  3. **Feedback loop**: drains the file-backed `feedback_channel` ([components/feedback_channel.py](components/feedback_channel.py)) of approve/reject/modify actions written by the web worker, records SDL audit + feedback entries.
- **IPC layout** (all under `data/`, the app-data volume in the two-service compose topology):
  - `data/state/pending_state.json` — `StateStore` writer (worker) / follower (web) for pending conversions. See [components/state_store.py](components/state_store.py), `asyncio.Lock` + `threading.Lock`, mtime hot-reload in follower mode.
  - `data/feedback/actions.jsonl` — append-only `feedback_channel` bus; the web worker writes user actions, the conversion worker drains them.
  - `data/runtime/status_snapshot.json` + `data/runtime/pending_requests.json` — `runtime_proxy` ([components/runtime_proxy.py](components/runtime_proxy.py)): web-side shim that exposes worker runtime status + pending workbench requests without an in-process handle.
- **Single-process dev mode still works**: running `python continuous_conversion_service.py` **without** `--worker-only` starts the old embedded Flask server on :8080 for quick local work. The gunicorn split is the production shape; this is the convenience fallback.
- **[main.py](main.py)** — one-shot batch via `ConversionSystemOrchestrator.run_complete_conversion()`. Flow: scan → analyze → generate → harness test → (optionally) deploy to Observo → upload to GitHub → report. `--dry-run` skips deploy by injecting invalid keys. Args: `--config --dry-run --max-parsers --parser-types --verbose`.

## Phase 7 hardening (enforced, not aspirational)

- `DEBUG=False` is enforced in the production Flask app; `FLASK_SECRET_KEY` is **fail-fast** — missing/empty key raises at startup ([components/web_ui/security.py](components/web_ui/security.py)).
- `temperature=0` is pinned for the generator — do not reintroduce nonzero temperature "for variety." The Settings tab enforces this with a read-only input.
- `scripts/run_pip_audit.sh` and `scripts/run_gitleaks.sh` are the supply-chain + secret-scan gates wired into CI. Run them locally before pushing if you touched `requirements.txt` or added any token-shaped strings.
- Dataplane BuildID pin (Phase 5.C) and secret-leak guard (Phase 5.D) are load-bearing — don't strip them.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env   # set ANTHROPIC_API_KEY (required)

# Service + workbench at http://localhost:8080/
python continuous_conversion_service.py

# One-shot CLI
python main.py --dry-run --max-parsers 1

# Docker
docker compose --env-file .env up -d
```

After starting, LLM credentials can also be configured (or changed at runtime) via the Settings tab at `http://localhost:8080/workbench` instead of editing `.env`.

## Tests — smallest first

```bash
pytest tests/test_harness_cli_smoke.py -q
pytest tests/test_harness_ocsf_alignment.py -q
pytest tests/test_workbench_jobs_api.py tests/test_parser_workbench.py -q
# Broader sweep only after targeted runs pass
pytest tests/test_workbench_*.py tests/test_parser_workbench.py tests/test_harness_*.py -v

# Type-check (mypy.ini is the only lint config in the repo — no ruff/black/flake8)
mypy components/
```

## Architecture — where things live

- [continuous_conversion_service.py](continuous_conversion_service.py) — conversion worker; three async loops under `--worker-only`, or embedded Flask fallback without the flag
- [wsgi_production.py](wsgi_production.py) — gunicorn entry; builds `ServiceContext` + `build_production_app`
- [components/service_context.py](components/service_context.py) / [components/state_store.py](components/state_store.py) / [components/feedback_channel.py](components/feedback_channel.py) / [components/runtime_proxy.py](components/runtime_proxy.py) — cross-process IPC layer for the gunicorn + worker split
- [main.py](main.py) — one-shot batch entry
- [components/lua_generator.py](components/lua_generator.py) — **the** conversion engine. Two modes: `mode="fast"` (single LLM call, no harness loop) and the iterative mode in `_run_iterative_loop_sync` ([lua_generator.py:496](components/lua_generator.py#L496)) which runs the harness feedback loop + Haiku→Sonnet→Opus model escalation. `ClaudeLuaGenerator` ([line 937](components/lua_generator.py#L937)) is a legacy shim pinned to fast mode. `AgenticLuaGenerator` ([components/agentic_lua_generator.py](components/agentic_lua_generator.py)) is a ~196-line shim that delegates to the iterative path and is used by the workbench. "Few-shot" today is just static Patterns A-E in the SYSTEM_PROMPT — the `ExampleSelector` class is dead code (`.select()` is never called).
- [components/testing_harness/](components/testing_harness/) — harness core
  - [harness_orchestrator.py](components/testing_harness/harness_orchestrator.py) — `run_all_checks()` runs 5 checks and returns an in-memory report (score, missing fields, lint errors, per-event pass/fail, trace)
  - [dual_execution_engine.py](components/testing_harness/dual_execution_engine.py) — runs Lua against test events in the `lupa` sandbox
  - [lua_linter.py](components/testing_harness/lua_linter.py) — Lua syntax, helper usage, `setNestedField` patterns, embedded-payload extraction checks
  - [ocsf_schema_registry.py](components/testing_harness/ocsf_schema_registry.py) — OCSF field schema (statically embedded)
  - [jarvis_event_bridge.py](components/testing_harness/jarvis_event_bridge.py) — hardcoded realistic event generators for ~40 parsers (Akamai DNS, Duo, Defender, etc.); harness prefers these over synthetic events
  - [lua_helpers/ocsf_helpers.lua](components/testing_harness/lua_helpers/ocsf_helpers.lua) — **our** helper library (`getNestedField` / `setNestedField` / `flattenObject`). Observo does NOT inject these at runtime (verified from `observo docs/lua-script.md` and the `lv3` binary symbol audit — only `emit` and `json` are injected into the v3 transform scope). The file's contents are pasted into the LLM SYSTEM_PROMPT via `get_helpers_for_prompt()` ([agentic_lua_generator.py:26,390](components/agentic_lua_generator.py#L26)) — **the LLM is instructed to inline them at the top of every emitted script**, but nothing in the codebase auto-prepends them. Verification is via [lua_linter.py](components/testing_harness/lua_linter.py) only. Edits to this file affect both the lupa sandbox and the LLM prompt; do not duplicate the definitions anywhere else.
- [components/web_ui/routes.py](components/web_ui/routes.py) — Flask routes (~3700 lines)
  - Review queue: `GET /`, `GET /api/v1/pending`, `POST /api/v1/approve|reject|modify`
  - Workbench: `POST /api/v1/workbench/build|validate/<parser>|lint/<parser>|test-run/<parser>|jobs`
- [components/web_ui/parser_workbench.py](components/web_ui/parser_workbench.py) — `ParserLuaWorkbench.build()` drives live generation + harness
- [components/settings_store.py](components/settings_store.py) — persistent operator-settings store on the `app-data` volume (`data/settings/settings.json`), with env-var fallthrough and a startup overlay contract for restart-required singletons. Settings tab is the 7th tab in `/workbench`. Routes: `GET/POST /api/v1/settings`, `POST /api/v1/settings/test/<provider>`, `POST /api/v1/workbench/save-correction` for inline correction persistence.
- [components/llm_provider.py](components/llm_provider.py) — unified LLM provider abstraction; dispatches to Anthropic, OpenAI, or Gemini based on the active provider setting
- [components/feedback_system.py](components/feedback_system.py) — `record_lua_correction/success/failure`; persists to JSONL at `data/feedback/corrections.jsonl` as the primary sink, with best-effort Milvus upsert as a secondary when RAG is enabled
- [output/](output/) — accepted Lua. **Not** auto-retrieved as few-shot today (see the `ExampleSelector` dead-code note above); kept as a manual reference pool and as the sink the workbench writes back into.
- [docs/harness/technical-roadmap.md](docs/harness/technical-roadmap.md), [docs/harness/acceptance-criteria.md](docs/harness/acceptance-criteria.md) — milestone context

## The conversion pipeline

For each parser, [agentic_lua_generator.py](components/agentic_lua_generator.py):

1. Classify OCSF class by keyword-matching parser name/vendor/product/samples to a `class_uid`.
2. Extract source fields from parser config.
3. Deterministic sample-format preflight — JSON / CSV / KV / syslog / XML, plus embedded-message-payload detection.
4. Build system + user prompt. System prompt carries Patterns A-E + the inlined OCSF helper library. User prompt carries parser analysis, OCSF schema fragment, and ~2 **test-event samples** from `raw_examples` / `historical_examples` (these are sample events, **not** prior approved Lua — the few-shot-from-`output/` retrieval is unimplemented today; see the `ExampleSelector` dead-code note in Architecture).
5. **Iterative refinement with escalation**: Haiku first, up to 3 iterations. Each iteration = one LLM call + full harness run. If score < 70, feed missing fields + lint errors into a refinement prompt. If still failing after iterations, escalate Haiku → Sonnet → Opus. Best result across all iterations wins.
6. Cache the accepted Lua + score to disk under `output/`. Future runs do **not** currently retrieve it as a few-shot example (the `ExampleSelector` retrieval wiring is missing) — the cache is a manual reference pool until that's wired in.

Not tool-use / ReAct — single-turn per iteration with static harness feedback.

## The harness (5 checks → 0–100 score)

1. Lua validity (AST parse)
2. Lua linting (luacheck-style)
3. OCSF field mapping — required fields per class (`class_uid`, `category_uid`, `activity_id`, `time`, `type_uid`, `severity_id`)
4. Source field coverage — cross-refs source fields against generated Lua, computes %
5. Test event execution — 4 events via `lupa`; Jarvis events preferred, synthetic fallback

Report is returned in-memory to the caller (UI or orchestrator). It is **not** written to a report directory by default.

## Observo runtime reality (verified against the real dataplane binary + docs)

Two sibling folders (both outside this repo, both gitignored) hold Observo source-of-truth material:

- `../Purple-Pipline-Parser-Eater/Observo-dataPlane/` — binary + minimal production configs, used for the first round of mining.
- `../Purple-Pipline-Parser-Eater/observo-dataplane-vector/` — same binary plus **19 markdown docs** including the 38 KB `CLAUDE_INTEGRATION_GUIDE.md`, `ARCHITECTURE.md`, `SCOL_REFERENCE.md`, `SCOL_DESIGN_VS_IMPLEMENTATION.md`, `FIELD_MAPPINGS.md`, and `SECURITY.md`. Treat this as the authoritative doc set; the earlier `observo docs/` folder describes a different layer.

**Two products, one binary, one SaaS tier.** The dataplane binary runs from static YAML via `./dataplane --config file.yaml`. The REST API at `https://p01-api.observo.ai/gateway/v1/...` (documented in the earlier `observo docs/` folder) is a **SaaS control plane layered above** the standalone binary. Our generator has to target whichever one a given user is running. Don't conflate them.

- **Lua runtime: PUC-Rio Lua 5.4.7 embedded via `mlua` 0.10.2 in a Rust fork of `timberio/vector`.** Vector base is **`0.44.7`**, git short SHA **`dbac53e`**, build timestamp **`2025-10-15 12:43:52`**, BuildID **`5de1d972760330258cda3554c36e67cae5c57bde`** — all four extracted directly from `dataplane.amd64`. Not gopher-lua, not LuaJIT, not Go. Templates must be Lua 5.4 syntax (`_ENV` not `setfenv`, `//` integer div, `<const>` / `<close>`, `goto`, native bitwise `&|~<<>>`).
- **Sandbox: DEFINITIVELY UNSANDBOXED.** Resolved by binary symbol audit. The constructor is `mlua::state::Lua::unsafe_new_with` (not `Lua::new` or `Lua::new_with` — `unsafe_new_with` permits loading `package`, `debug`, etc.). All ten PUC Lua 5.4 stdlibs are loaded via `luaL_openlibs`: `base`, `package`, `io`, `os`, `debug`, `math`, `string`, `utf8`, `table`, `coroutine`. `io_popen`, `os_execute`, `os_remove` symbols are statically linked. **Zero** Rust-side blocklist symbols (no `set_global("io", nil)`, no `nil_global`, no `remove_global`, no `sandbox_lua`, no instruction-count hook, no memory cap). The `SECURITY.md`/`CLAUDE_INTEGRATION_GUIDE.md` blocklist claims are aspirational documentation, not enforced behavior. The `scol::config::Sandbox` symbol is for **external command jail**, not Lua VM sandboxing — it wraps `ExecBulk` subprocess spawns, not Lua scripts. Treat **every** Lua transform script as fully trusted code that can call `os.execute`, `io.open`, `io.popen`, `package.loadlib`, `debug.sethook`, etc. Operator-supplied configs only — never expose Lua transforms to tenant input.
- **SCOL has TWO independent RCE vectors**: (1) the unsandboxed Lua stdlib gives `os.execute` / `io.popen`, and (2) `scol::types::ExecBulk` / `ExecParams` / `ExecFetchArg` cross the Lua boundary as `IntoLua` / `FromLua` — a SCOL Lua script can construct an `ExecBulk` table in Lua and hand it to Rust for process spawning as a first-class framework feature. The only mitigation for path (2) is `scol.sandbox.jail` + `sandbox.clean_up`, which is a chroot/uid jail (not a syscall filter) and is empty by default ("sandbox `jail` found empty (must be a valid command)" message at strings line 183634).
- **Two Lua code paths with different injected globals**:
  - **`lv3` v3 `type: lua` transform**: only `emit` is injected (scoped via `mlua::scope::Scope::create_function`, lifetime is one `transform()` call). Plus `json` from `mlua_json::preload`. Plus the full Lua 5.4 stdlib because of `luaL_openlibs`. **No** `fetch`, `mark_complete`, `on_complete`, `get_chkpt`, `set_chkpt`, `log`, `hex_decode`, `base64_*`, `sha256`, `url_encode` injected here.
  - **`scol` source**: gets `fetch`, `on_complete`, `get_chkpt`, `set_chkpt`, plus a `log` table with 5 levels (`trace/debug/info/warn/error` via `scol::log::preload`), plus a `package.preload`-registered helper module exposing `hex_decode`, `base64_encode`, `base64_decode`, `base32_encode`, `base32_decode`, `url_encode`, `url_decode`, `url_encode_bin`, `url_decode_bin` (these helpers live in rodata immediately adjacent to `lib/observo/scol/src/scol/config.rs`). Plus `json`. Plus the full stdlib. The user's entry function is named via the `start_routine:` config field (default `start`).
- **`processEvent` is NOT a binary contract — it's a community convention.** Verified by absence: the literal string `processEvent` does not appear in the binary except as a substring of `host_processEventsReceived` (a Kubernetes struct). lv3 loads the entire script as a Lua chunk via `Lua::load_with_location` + `Function::call`; it does NOT look up a global named `processEvent`. The v2 `type: lua` (`hooks.process`) and lv3 `type: lua, version: "3"` paths both expect a function named **`process`** for their respective hook contracts. Our generator can still emit a user-defined `processEvent(event)` helper called from the outer `process(event, emit)` wrapper — that's the community pattern — but the binary doesn't enforce it.
- **Two-layer contract.** The outer contract Observo actually invokes is `process(event, emit)` where `event.log` is the unwrapped payload. User code typically defines a module-level `processEvent(event)` that the outer `process` wrapper calls:

  ```lua
  require('netskope_lua')          -- or inline the helpers here instead
  function process(event, emit)
    local out = processEvent(event["log"])
    if out ~= nil then
      event["log"] = out
      emit(event)
    end
  end
  ```

  `processEvent` is a **user convention**, not an Observo contract. The *only* thing Observo sees is `process(event, emit)` and whatever you `emit()`. `transform(record)` does not exist anywhere in the real dataplane.
- **Zero injected helpers for the v3 Lua transform.** No `getNestedField`, `setNestedField`, `flattenObject`, `log`, `metrics`. Only `emit` is injected into the `process` scope. Production `netskope_lua.lua` defines all helpers inline at the top (`encodeJson`, `setNestedField`, `getNestedField`, `copyField`, `getValue`).
- **Error handling:** raising inside `process` emits an internal `LuaScriptError` event; default behavior is the original event **passes through unchanged**. **Important correction**: `drop_on_error`, `drop_on_abort`, and `reroute_dropped` are **REMAP/VRL transform-only**, NOT lua. The wire-format reviewer confirmed they live on `RemapConfig` only and the lua deserializer will REJECT them. (My earlier TODO item to wire them into Lua transforms was wrong — emitting them on a `type: lua` block will fail YAML validation.) For Lua transforms, error handling means using `pcall` inside the script body and routing failures via `emit` or by returning early; there's no transform-config-level drop knob.
- **OCSF classes actually used by production Lua:** the header of `netskope_lua.lua` claims "Detection Finding [2004]" but the real code at lines 892/1058/1203/1273/1411/1694 emits `class_uid = 2001` (Security Finding), at lines 890-1055 + 1409-1556 emits `class_uid = 2004` (Detection Finding), at line 1559 emits `class_uid = 6001`, and at line 1842 emits `class_uid = 0` in a default fall-through. **Class 0 is not valid OCSF** — that's a latent bug in the production Lua, not something we should copy. Our generator should emit 2001 / 2004 / 6001 as appropriate and never 0.
- **Scriptable Collector (`scol`) sources** are a separate code path for API polling. Confirmed primitives from the internal Observo engineering PDF (8 pages, Janmejay Singh, pre-build design doc — names may differ in the shipped binary):
  - **Entry point**: `function start(config)` only — no `emit`, no `ctx` parameter at entry. The function name is configurable via `start_routine:`.
  - **Fetch callbacks**: user-named, called with `(config, res, ctx)` where `res = {status, body, headers}` and `ctx` is the table you passed into the originating `fetch{context = ...}`. Dispatched by name via `fetch{fn = "callback_name"}`.
  - **`fetch` is async, non-blocking.** Returns a uuid work-identifier immediately. Never write code that treats `fetch` as synchronous — always pass `fn` and resume state in the callback.
  - **Three-way completion model**: a fetch handler can either (a) explicitly call `mark_complete{...}`, (b) pass an `on_complete{result = ..., fn = ...}` block whose callback fires when the work tree drains, or (c) do neither and let work be considered complete when the handler returns.
  - **Serializability rule**: tables exchanged via `fetch.context`, `on_complete.result`, and `set_chkpt` values must contain only `number`, `string`, `table`, `bool`. No functions, no userdata.
  - **Blessed helpers** (per PDF): `json = require("json")`, `strptime`, `strftime`. The PDF does NOT bless `log`, `io`, `os`, `debug`, `package`, or any binary helper lib. The `log` / `hex_decode` / `base64_*` / `sha256` / `url_encode` helpers I previously listed came from binary strings, not from this design doc — treat as binary-only until verified at runtime.
  - **`exec{}` exists** as a primitive but is sandbox-gated and security-disabled by default. Never generate it.
  - **Per-domain HTTP config** is keyed by hostname under `rpc_domain:` in the design doc (the binary may have renamed it to `http_cfgs:` — verify against shipped YAML before emitting). Three auth strategies: `oauth2` (client_id / client_secret / token_url), `bearer` (token), `basic` (user / password). **mTLS is first-class** with `tls.{ca_file, cert_file, key_file, key_pass, server_name, verify_certificate, verify_hostname, enabled}`.
  - **Trigger** is `{interval: <Go duration string e.g. 30m>, await_completion: <bool>}` per the design doc; binary may also accept `interval_secs: <int>`. Only one trigger mode (interval) — no cron, no event-driven, no manual.
  - **v1 checkpoint store is file-per-value on a Persistent Volume**, NOT SQLite, organized by source-id directories. Earlier "SQLite checkpoint" claim from `SCOL_DESIGN_VS_IMPLEMENTATION.md` was wrong.
  - **v1 does NOT distribute work across dataplane pods** — single-node only.
  - **Things the PDF does NOT cover** (and which therefore remain ambiguous): Lua stdlib allowlist, resource/CPU/memory limits, observability metrics, DLQ behavior, error-path routing, hot reload semantics. Treat all of those as undefined until binary or live test answers them.
- **Control-plane API:** base URL `https://p01-api.observo.ai`, auth `Authorization: Bearer <JWT>`, all endpoints under `/gateway/v1/`. See `observo docs/pipeline.md`.

## Target consoles — we support BOTH

Two completely separate Observo products. Our generator must emit the right shape for whichever one the user is running. **Do not cross-contaminate the two code paths** — earlier audits tried to "unify" them and broke the SaaS path.

| Target | Wire format | How it deploys | Lives in |
| --- | --- | --- | --- |
| **SaaS console** | camelCase JSON over REST | `POST` to `https://p01-api.observo.ai/gateway/v1/*` with `Authorization: Bearer <JWT>` | [components/observo_client.py](components/observo_client.py), [components/observo_models.py](components/observo_models.py), [components/observo_pipeline_builder.py](components/observo_pipeline_builder.py) — **correct as-is, do not rewrite to snake_case** |
| **Standalone console** | snake_case Vector YAML | `./dataplane validate --config file.yaml` then `./dataplane --config file.yaml` (no API, no auth, file-driven) | [components/dataplane_yaml_builder.py](components/dataplane_yaml_builder.py) — sibling to the SaaS builder; enforces a `_FORBIDDEN_V3_LUA_TRANSFORM_KEYS` set (`lua_script`, `script`, `bypass_transform`, `metric_event`, `drop_on_error`, `drop_on_abort`, `reroute_dropped`, `rpc_domain`). Extend this file; never mutate the SaaS builder to snake_case |

The Lua body itself (`process(event, emit)` outer wrapper + inlined OCSF helpers + `processEvent` inner dispatcher) is portable across both targets. Only the surrounding pipeline shape differs.

### SaaS console wire format (REST control plane)

Documented in the gitignored `observo docs/` folder. Endpoint table (from `pipeline.md`, `node.md`, `transform.md`, `lua-script.md`):

```text
POST   /gateway/v1/pipeline                 — create
PATCH  /gateway/v1/pipeline                 — update
PUT    /gateway/v1/pipeline-graph           — rewire
PATCH  /gateway/v1/pipeline/action          — deploy/pause/delete via {action} enum
GET    /gateway/v1/pipelines                — list (plural, only on GET)
POST   /gateway/v1/deserialize-pipeline     — atomic upload + optional deploy ({"spec":{...},"deployPipeline":true})
POST   /gateway/v1/transform                — add one transform
GET    /gateway/v1/transform-templates      — discover template ids
POST   /gateway/v1/source                   — add source
POST   /gateway/v1/sink                     — add sink
```

The `transform.config` blob for the `lua_script` template is camelCase per `observo docs/lua-script.md:15-24`:

- `luaScript` — the Lua body string (NOT `source`, NOT `script`)
- `metricEvent` — boolean, treats output as a metric event
- `bypassTransform` — boolean, skips the transform without removing it from the graph

These ARE the keys the SaaS UI emits and the SaaS API accepts. **Do NOT delete them from `observo_models.py` / `observo_pipeline_builder.py` based on dataplane-binary findings** — that's a different product. (A 2026-04 audit round flagged them as "phantom keys"; verification proved that finding wrong — they are real SaaS keys, just absent from the standalone binary.)

**Real bug to fix in this path:** [components/observo_client.py:290](components/observo_client.py#L290) builds `f"{self.base_url}/pipelines"` against `https://p01-api.observo.ai`, producing a URL with no `/gateway/v1/` prefix. There is no `/pipelines` root path in the SaaS API.

### Standalone console wire format (YAML for the dataplane binary)

The dataplane binary is the Rust Vector fork (0.44.7 / `dbac53e` / 2025-10-15). It accepts vanilla Vector YAML with a few Observo-internal extensions (`lv3`, `scol`, `ssa`, `obvrl`, `chkpts`, `azs`, `stcp`). Schema keys are **snake_case Vector schema** — the camelCase SaaS keys do not exist in this path and the binary's deserializer will reject them.

```yaml
transforms:
  ocsf_serializer_lua:
    type: lua                       # NOT "lua_script"
    version: "3"                    # string, quoted
    inputs: [upstream_id]
    parallelism: 1
    search_dirs: [/etc/dataplane/ocsf]   # NEVER /Users/<name>/... or other absolute dev paths
    process: process                # name of the Lua function to invoke (default "process")
    source: |                       # the Lua body — NOT "luaScript", NOT "script"
      function process(event, emit)
        local out = processEvent(event["log"])
        if out ~= nil then
          event["log"] = out
          emit(event)
        end
      end
```

**Keys this path does NOT accept** (verified against `dataplane.amd64` symbols — these are facts about the standalone binary only, NOT statements about the SaaS keys above):

- `lua_script`, `script` — the Lua body key for the v3 transform is `source`. (`script:` is correct ONLY on `scol` sources, which are a separate code path.)
- `bypass_transform` — never existed in the binary; prior "found" hit was a substring of `host_processEventsReceived` (a Kubernetes struct).
- `metric_event` (as a YAML field) — `metricEvent` IS a Lua-table discriminator key inside `event/lua/metric.rs`, but it is NOT a YAML config field.
- `rpc_domain` — the Confluence PDF used this name; the shipped binary uses `http_cfgs` (verified — `BTreeMap<String, scol::scol::config::HttpCfg>`).
- `drop_on_error`, `drop_on_abort`, `reroute_dropped` — REMAP/VRL transform-only. The lua-transform deserializer rejects them. For lua, use `pcall` inside the script body; the default behavior on raise is "emit `LuaScriptError`, original event passes through unchanged."

**Three Lua transform versions exist as distinct Configurable impls** (verified from binary serde symbols):

- `version: "1"` → `vector::transforms::lua::v1::LuaConfig` — single `source` Lua body, deprecated. No hooks.
- `version: "2"` → `vector::transforms::lua::v2::LuaConfig` — `hooks: { init, process, shutdown }` + `timers[]` with `interval_seconds`/`handler` + `metric_tag_values`.
- `version: "3"` → `lv3::lv3::LuaConfigV3` (separate Observo crate `lv3`) — `source` + `process` + `search_dirs` + `parallelism` + `metric_tag_values`.

Default to v3. Fall back to v2 if the operator's binary lacks the `lv3` crate (probe with `./dataplane validate --config <v3-sample.yaml>` before committing). Don't bother with v1 — deprecated.

**SentinelOne sink** is modeled as `type: splunk_hec_logs` with a SentinelOne endpoint + `path: /services/collector/event?isParsed=true`, not a dedicated `sentinelone` sink type. See `../Purple-Pipline-Parser-Eater/Observo-dataPlane/s1_hec.yaml` for the authoritative shape — and **redact `default_token` before reusing** (the shipped sample contains a real-format token).

**Preflight before claiming a generated YAML is valid:** run `./dataplane validate --config <generated.yaml>` against the operator's binary. The harness can't substitute for this because we don't ship the binary.

## Legacy "contract rules" still in force

- **Determinism is mandatory.** Dataset traversal and report ordering must be stable across runs; tests assert this. No dict-iteration-order or time-based sorting.
- **Don't touch `output/` in place** unless the task explicitly requires it — it's the few-shot example pool.
- **Harness-first scope:** don't reintroduce removed legacy ingestion/output stacks. Full RAG baseline is preserved on branch `rag-full-preservation`.

## Gotchas (non-obvious)

- **One generator, two modes — but the daemon is still pinned to fast.** Streams B.1–B.4 (commits `bc693cb`, `d16ef95`) unified what used to be two independent generator classes into a single `LuaGenerator` with `mode="fast"` vs iterative (`_run_iterative_loop_sync`). Both shims — `ClaudeLuaGenerator` ([lua_generator.py:937](components/lua_generator.py#L937)) used by the worker + `main.py`, and `AgenticLuaGenerator` used by the workbench — now delegate into this shared engine. **However**, the daemon/worker path still constructs requests with `mode="fast"`, so worker users still don't get the harness feedback loop or model escalation at runtime. Switching the worker to iterative is a config-level change now, not a refactor. When editing the iteration body, edit [lua_generator.py](components/lua_generator.py) — editing `agentic_lua_generator.py` only touches the re-export surface.
- **Both Lua runtimes are now sandboxed.** The local runtime executor ([components/transform_executor.py](components/transform_executor.py)) and the harness executor ([dual_execution_engine.py](components/testing_harness/dual_execution_engine.py)) both sandbox Lua with `register_eval=False` / `register_builtins=False` and nil out dangerous globals (`io`, `package`, `debug`, `load`, `loadfile`, `dofile`). Note: the two sandbox prelude copies have drifted slightly — keep them in sync when editing either one.
- **Embedded message payloads:** malformed-JSON samples (Akamai, CloudTrail-style) carry the real event inside a `message` KV. Preflight + agentic generator detect and enrich these — see the extraction checks in [lua_linter.py](components/testing_harness/lua_linter.py) before changing sample ingestion.
- **All three LLM providers are wired.** Anthropic, OpenAI, and Gemini are all live through [components/llm_provider.py](components/llm_provider.py). The Settings tab in `/workbench` surfaces a "Primary AI provider" segmented control for switching between them. Each provider has cheap + strong model env vars (`ANTHROPIC_MODEL`/`ANTHROPIC_STRONG_MODEL`, `OPENAI_MODEL`/`OPENAI_STRONG_MODEL`, `GEMINI_MODEL`/`GEMINI_STRONG_MODEL`). Escalation (harness score < 70) promotes cheap to strong within the active provider.
- **Workbench sample limits:** `WORKBENCH_MAX_SAMPLE_CHARS` (default 150k), `WORKBENCH_MAX_TOTAL_SAMPLE_CHARS` (default 1.5M).
- **Feedback persists to JSONL but is not hot-reloaded.** User corrections are now durably written to `data/feedback/corrections.jsonl` (via `POST /api/v1/workbench/save-correction`) and optionally to Milvus when RAG is enabled. However, corrections only influence the *next* parser once the example pool is re-scanned — no mid-prompt RAG retrieval.
- **RAG (Milvus / sentence-transformers / torch) is optional.** If not installed, the system works fine; lessons are written to JSON logs instead.
- **Jarvis bridge drives realistic test events.** If your parser isn't in `jarvis_event_bridge.py`, the harness falls back to synthetic events from `TestEventBuilder` — coverage numbers will look thinner.
- **SaaS deploy path is real, not a stub.** [orchestrator/pipeline_deployer.py:107](orchestrator/pipeline_deployer.py#L107) → `observo_client.deploy_validated_pipeline` ([observo_client.py:465](components/observo_client.py#L465)) → `_deploy_pipeline` ([line 288](components/observo_client.py#L288)) does a real `aiohttp.session.post`. `mock_mode` only kicks in when `api_key` is missing or equals `"your-observo-api-key-here"` / `"dry-run-mode"` ([observo_client.py:45-51](components/observo_client.py#L45)). The path has never been exercised in CI — use `--dry-run` until a recorded-cassette test covers it. Standalone-binary deploy is YAML-handoff only — no API to call, no live test path needed.
- **Most messaging/cloud deps are unused.** `requirements.txt` lists `redis>=5.0.0`, `boto3`, `azure-*`, `google-cloud-pubsub`, but **none are imported by runtime code**. `aiokafka` is **not** in `requirements.txt` and **not** imported. [components/message_bus_adapter.py](components/message_bus_adapter.py) is an abstract `abc` skeleton with no concrete adapter implementations — it does not pull in any messaging library. Treat the message-bus surface as unwired.
- **Web UI auth is disabled.** Single shared pending list; no multi-tenancy.
- **lupa required for Lua tests:** they skip gracefully if missing; `pip install lupa` if you see unexplained skips.
- **Keep diffs small.** `rg --files` for discovery; `git diff --name-only` to self-audit scope before committing.
