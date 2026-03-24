# Hybrid Dataplane + PPPE Architecture Plan (with RAG Enhancements)

## 1. Objectives & Constraints

- Preserve all existing Purple Pipeline Parser Eater (PPPE) functionality:
- Orchestrator phases 1–5 (`orchestrator.py`) remain authoritative for analysis, Lua generation, validation, deployment, artifact creation, and GitHub automation (442:559:orchestrator.py).
- Web Feedback UI (`components/web_feedback_ui.py`) continues to be the single approval/feedback surface; CSRF, CSP, rate limiting, audit logging (`sdl_audit_logger.py`) stay enabled.
- Artifact layout (`output/<parser_id>/analysis.json`, `transform.lua`, `pipeline.json`, `validation_report.json`) is unchanged.
- Existing tests (`pytest tests/`) and automation scripts run unmodified.
- Introduce Dataplane Vector as an ingestion and pre-normalization tier without regressing current workflows.
- Add a scalable runtime transformation worker that executes approved Lua against live event streams.
- Expand the RAG knowledge base to include Dataplane documentation, configs, manifests, validation feedback, and runtime error logs; prompts must leverage these sources.
- All new capabilities must be feature-gated (config toggles) and fully documented.

---

## 2. Target Architecture Overview

```
┌───────────────────────────────────────────────┐
│                 Dataplane Tier                │
│ SCOL sources → Pre-normalize Lua → Bus Sink  │
└───────────────────────────────────────────────┘
                │                   ▲
                ▼                   │ manifests + transforms
┌───────────────────────────────────────────────┐
│          PPPE Runtime Transformation           │
│ Event consumer → load current transform →     │
│ execute Lua (lupa/dataplane) → emit OCSF      │
└───────────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────┐
│ Outputs (Observo API, SDL, storage, analytics)│
└───────────────────────────────────────────────┘

PPPE Orchestrator & Web UI remain central for
- Parser analysis & Lua generation (Claude + RAG)
- Human approvals/editing
- Deployment & documentation
- Continuous learning (RAG updates)
```

---

## 3. Phased Delivery Roadmap

### Phase Dependencies at a Glance

```
Phase 0 (Platform Prep)
    │
    ├─→ Phase 1 (Dataplane Validator) ──→ Phase 7 (E2E / Regression Tests)
    │                                          ▲
    ├─→ Phase 2 (Message Bus + Transform Worker) ──────┐
    │        │                                         │
    │        └─→ Phase 3 (Dataplane Chained Transform) │
    │             │                                    │
    │             └─→ Phase 4 (Manifest Publish) ──────┤
    │                  │                               │
    │                  └─→ Phase 5 (Web UI Runtime) ───┤
    │                                                  │
    └─→ Phase 6 (RAG Expansion) ───────────────────────┘

Critical Path: 0 → 1 → 7 (validator-first rollout)
Parallel Path: 0 → 2 → 3 → 4 → 5 → 7 (runtime pipeline)
```

### Phase 0 – Repository & Platform Preparation

- Convert `external-dataplane-docs/` into a git submodule (or lock via hash) to ensure reproducible binaries/docs.
- Stage Dataplane assets in container images:
- Copy `dataplane.amd64`, `dataplane.aarch64`, `ocsf/`, configs into `/opt/dataplane/` during Docker build (`Dockerfile`).
- Update `docker-compose.yml` to add `dataplane-ingest` service definitions (bridged network, non-root, volume mounts).
- Create `deploy/dataplane/` with:
- `docker-compose.dataplane.yaml` for local testing
- Helm chart scaffold (`Chart.yaml`, `values.yaml`, templates for Deployment/ConfigMap/Secret/PVC) for Kubernetes rollout.
- Document new prerequisites in `SETUP.md` (Dataplane binary staging, message bus requirement, optional GPU/CPU notes).

### Phase 1 – Dataplane Validation Harness

- Implement `components/dataplane_validator.py`:
- Accepts Lua code, sample events, parser metadata.
- Generates temporary Vector config based on `external-dataplane-docs/local_ocsf.yaml` (ensure `processEvent` vs `transform` naming matches generator output).
- Executes staged binary (`/opt/dataplane/dataplane` or override via config) using `subprocess.run`, controlled timeout, streaming stdout/stderr.
- Validates OCSF compliance within `event["log"]`, collects metrics (#events, missing fields, runtime errors).
- Extend `PipelineValidator.validate_complete_pipeline()` to call the dataplane validator after existing schema/Lua checks. Append results under `validations.dataplane_runtime` with `status`, `errors`, `warnings`, `ocsf_metrics`, and raw logs (trimmed/hashed if large).
- Config additions (`config.yaml`):

```yaml
  dataplane:
    enabled: true
    binary_path: "/opt/dataplane/dataplane"
    max_events: 10
    timeout_seconds: 30
    ocsf_required_fields:
      - class_uid
      - class_name
      - category_uid
      - metadata
```

- Tests: `tests/test_dataplane_validator.py` (skipped unless binary available), `tests/test_pipeline_validator_dataplane.py`; see `docs/Dataplane_Validation.md` for CI strategy.
- CI: add job that downloads binary (if not in image) and runs validator tests; fallback skip when binary absent.

### Phase 2 – Message Bus & Transform Worker Service

- Select transport:
- Primary: Kafka (schema registry optional).
- Alternative: Redis Streams for lightweight deployments.
- Implement message bus abstraction (`components/message_bus_adapter.py`):
- Abstract base `MessageBusAdapter` with `publish`, `subscribe`, `close` methods.
- Concrete adapters: `KafkaAdapter` (using `aiokafka`), `RedisAdapter`, `MemoryAdapter` for tests.
- Factory `create_bus_adapter(config)` selects transport; enables seamless switching and in-memory testing.
- Implement `services/transform_worker.py`:
- Async consumer using the adapter’s `subscribe` for `raw-security-events` topic.
- Resolves parser metadata via `ManifestStore` (reads `output/<parser_id>/manifest.json`).
- Executes Lua via pluggable executor (`components/transform_executor.py`):
- `LupaExecutor` (in-process `lupa.LuaRuntime`, cached per parser) for fast path.
- `DataplaneExecutor` (subprocess using staged binary) for parity validation.
- Factory `create_executor(config)` chooses strategy per deployment.
- Publishes transformed OCSF events via adapter to `ocsf-events` topic.
- Emits runtime metrics (success/fail counts, latency, last error) via Prometheus client or stats queue.
- Add entrypoint `start_transform_worker.py` that reads config, instantiates adapter, executor, worker, handles graceful shutdown/retry backoff.
- Update `docker-compose.yml` with `transform-worker` service (depends on message bus + PPPE image, uses same codebase but with separate command).
- Tests: `tests/test_message_bus.py`, `tests/test_transform_executor.py` (unit), `tests/test_pipeline_validator_dataplane.py` (smoke); add worker integration tests once manifest store implemented.

### Phase 3 – Dataplane Chained Transform Integration

- Update Dataplane configs (templates in `deploy/dataplane/configs/`):

```yaml
  transforms:
    preprocess:
      type: lua
      ...
    pppe_transform:
      type: lua
      inputs: ["preprocess"]
      search_dirs:
        - /opt/dataplane/ocsf/generated
      source: |
        require('pppe_<parser_id>')
        function process(event, emit)
          local out = processEvent(event["log"])
          if out then
            event["log"] = out
            emit(event)
          end
        end
  sinks:
    kafka_sink:
      type: kafka
      inputs: ["pppe_transform"]
      ...
```

- Create sync script (`deploy/dataplane/sync_transforms.sh`) to copy latest `transform.lua` + `manifest.json` into Dataplane volume, enforce checksums, and restart service gracefully.
- Provide Kubernetes ConfigMap + sidecar (optional) for auto-sync in cluster environments.
- Smoke test: run Dataplane locally with sample events to confirm chain loads and outputs to Kafka without errors.

### Phase 4 – Orchestrator Publish Hook & Manifests

- Extend `ParserOutputManager` with `save_manifest()` to write `output/<parser_id>/manifest.json` validated via `components/manifest_schema.py` (Pydantic). Manifest captures semantic versioning, compatibility, deployment metadata:

```json
  {
    "manifest_version": "1.0",
    "parser_id": "netskope_dlp",
    "version": {
      "lua_sha256": "abc123...",
      "semantic": "2.1.0",
      "previous": "2.0.5",
      "changelog": ["Fixed nil check", "Added nested DLP rules"]
    },
    "generated_at": "2025-10-20T12:34:56Z",
    "compatibility": {
      "min_dataplane_version": "0.30.0",
      "ocsf_version": "1.5.0"
    },
    "lua_metadata": {
      "file": "transform.lua",
      "entry_function": "processEvent",
      "search_dirs": ["ocsf"],
      "estimated_memory_mb": 5,
      "avg_execution_time_ms": 2.3
    },
    "ocsf_output": {
      "class_uid": 2004,
      "class_name": "Detection Finding",
      "extracted_fields": ["user", "file", "dlp_rule", "severity", "action", "timestamp"]
    },
    "source": {
      "repository": "sentinel-one/ai-siem",
      "parser_path": "parsers/netskope/dlp/parser.yml",
      "git_commit": "def456..."
    },
    "deployment": {
      "deployed_at": "2025-10-20T13:00:00Z",
      "deployed_by": "orchestrator-v9.0.0",
      "environment": "production",
      "canary_percentage": 10
    }
  }
```

- After successful validation & deployment in Phase 4, write manifest and enqueue notification via new `RuntimeNotifier` (simple Redis pub/sub or local file watch). Transform worker subscribes and reloads manifests on change.
- Ensure GitHub automation uploads `manifest.json` alongside existing artifacts.

### Phase 5 – Web UI & Runtime Observability

- Enhance Web UI API:
- `/api/runtime/status` (DONE – Phase 3)
- `/api/runtime/reload/<parser_id>` (DONE – Phase 3)
- `/api/runtime/canary/<parser_id>/promote` (DONE – Phase 3)
- UI updates (template inside `web_feedback_ui.py`):
- Add runtime status panel to parser view (success/error badges, last event timestamp, version hash, canary vs stable comparison) (IN PROGRESS).
- Provide “Re-run Dataplane Validation” and “Force Runtime Reload” buttons (respect queue-based actions) (TODO).
- Display canary health metrics and promotion readiness sourced from `RuntimeService` (partially satisfied via new API, UI wiring pending).
- Ensure audit logging (`sdl_audit_logger.py`) captures runtime commands with user ID, timestamp, parser ID, action (TODO).
- Update integration tests (`tests/test_web_ui.py`) to cover new endpoints and ensure auth headers enforced when testing mode disabled (TODO).

### Phase 6 – RAG Expansion & Continuous Learning

#### 6.1 Ingestion Scope

- Extend ingestion scripts to cover new assets:
- `external-dataplane-docs/` docs: `README.md`, `CLAUDE_INTEGRATION_GUIDE.md`, `ARCHITECTURE.md`, `PLATFORM_GUIDE.md`, `SCOL_REFERENCE.md`, `EXAMPLES.md`, `FIELD_MAPPINGS.md`, etc.
- Lua sources (`ocsf/*.lua`, `netskope_lua.lua`) segmented into logical chunks with metadata (function names, event types).
- Config templates (`netskope.yaml`, `local_ocsf.yaml`, `test-scol-host.yaml`).
- Newly created docs: `docs/Hybrid_Pipeline.md`, `docs/Transform_Worker.md`, this plan (`docs/Hybrid_Architecture_Plan.md`).
- Update `components/rag_sources.py` to include new source definitions with tags: `dataplane_doc`, `dataplane_config`, `dataplane_lua`, `hybrid_architecture`.
- Implement checksum tracking (`components/rag_checksum_store.py`) backed by SQLite to avoid re-ingesting unchanged documents (SHA-256). Ingestion jobs consult store before pushing updates to Milvus.

#### 6.2 Validation & Runtime Feedback Ingestion

- After each dataplane validation run, create a summary document (parser ID, errors, timestamps, fix applied) and enqueue for RAG ingestion.
- Transform worker logs runtime issues (missing fields, nil errors, performance anomalies) to `data/runtime_feedback.jsonl`; nightly job ingests with tag `runtime_feedback`.
- Extend `start_rag_autosync_github.py` or add `start_rag_autosync_dataplane.py` to monitor new/changed Dataplane files and manifests, re-indexing only when checksums differ.
- Update Claude prompt builders (`components/claude_analyzer.py`, `components/claude_lua_generator.py`) to request context by tags: `dataplane_doc`, `manifest`, `runtime_feedback`, `ocsf_mapping`.
- Tests: augment `tests/test_rag_components_fixed.py` with assertions that new tags return expected documents; add regression tests for prompt composition pulling in manifest/feedback snippets.

### Phase 7 – End-to-End & Regression Testing

- **Unit tests**: Already noted in phases 1–6.
- **Integration tests**:
- `tests/test_hybrid_pipeline.py`: spin up local Kafka (test container), run Dataplane ingest with sample events, start transform worker, orchestrator publish, ensure OCSF outputs match expectations.
- `tests/test_runtime_reload.py`: modify manifest, trigger reload via notifier, assert worker picks up new version.
- `tests/test_web_runtime_endpoints.py`: call new API endpoints with/without auth, assert responses + SDL logging.
- **System tests (staging)**:
- Deploy Dataplane + PPPE services via Docker Compose or K8s; run orchestrator full cycle on a subset of parsers using real sample data.
- Verify web UI, runtime worker metrics, Dataplane logs, RAG ingestion jobs.
- **Performance tests**: simulate high event volume through message bus; scale transform worker horizontally, ensure throughput/latency metrics meet targets.
- **Rollback drills**: turn off feature flags (`dataplane.enabled=false`, `transform_worker.enabled=false`) and confirm system reverts to pre-hybrid behavior without redeploying code.
- **Automated rollback tests**: add `tests/test_rollback_scenarios.py` covering orchestrator/transform worker/RAG behavior with flags off; schedule GitHub Actions workflow (`.github/workflows/rollback-drill.yml`) weekly to exercise rollback path.

---

## 4. RAG Data & Prompt Strategy

- **Source tagging**: enforce consistent metadata for all ingested documents (e.g., `{"parser_id": "netskope_dlp", "category": "dataplane_doc", "version": "2025-10-20"}`).
- **Manifest ingestion**: each manifest revision stored as separate entry; retrieval prompts can reference “latest manifest for parser X”.
- **Validation feedback**: store per-parser dataplane validation summaries; cross-link with runtime feedback so LLM has both pre-deployment and production contexts.
- **Prompt updates**:
- Analyzer prompt: “Use Dataplane integration docs and latest manifest to confirm transform expectations.”
- Lua generator prompt: include runtime feedback snippet when available to guide corrections.
- Fix prompt: reference specific errors from dataplane validator/run-time logs when re-generating Lua.
- **Verification**: new CLI `scripts/rag_list_docs.py` to inspect documents by tag; nightly job checks Milvus counts per category.

---

## 5. Documentation Deliverables

- `docs/Hybrid_Pipeline.md`: architecture diagram, service responsibilities, deployment instructions, scaling tactics.
- `docs/Transform_Worker.md`: runtime worker configuration, environment variables, operational playbook.
- `docs/RAG_Data_Sources.md` (update existing or create new): enumerate new sources, tags, ingestion schedule, validation checks.
- Update existing docs:
- `README.md` (add hybrid overview & quick start)
- `SETUP.md` (prerequisites, enabled feature flags)
- `WEB_UI_VERIFICATION.md` (runtime status UI)
- `PRODUCTION_DEPLOYMENT_GUIDE.md` (Dataplane & worker deployment steps)

---

## 6. Risk Mitigation & Feature Flags

- Configuration toggles:
- `dataplane.enabled` (default false for dev)
- `transform_worker.enabled`
- `rag.ingest_dataplane_docs`
- Rollback strategy:
- Disable toggles → orchestrator reverts to legacy behavior.
- Dataplane service can be stopped independently; transform worker drains queue gracefully.
- Security considerations:
- Maintain token-based auth & TLS for web UI; extend to new endpoints.
- Ensure Dataplane configs avoid leaking secrets (use ${ENV} expansions).
- Audit logs capture runtime actions via SDL logger.
- Monitoring:
- Prometheus exporters for Dataplane & transform worker (CPU, memory, queue lag, error rates).
- Alerting on repeated runtime failures (feed into RAG feedback ingestion).

---

## 7. Implementation Checklist (Condensed)

1. Submodule & deployment scaffolding
2. `components/dataplane_validator.py` + tests + config
3. Message bus integration + `transform_worker`
4. Dataplane chained transform configs + sync tooling
5. Manifest publish hook + notifier + worker reload logic
6. Web UI runtime endpoints & UI updates (with audit logging)
7. RAG ingestion expansion (docs, manifests, validations, runtime feedback)
8. Prompt template updates & verification
9. Documentation refresh/new guides
10. Full test suite: unit, integration, system, performance, rollback

Once all phases pass staging validation, enable feature flags in production and schedule regular reviews of runtime metrics and RAG corpus freshness.

---

## 8. AWS Production Scale Roadmap (100s PB/day)

### 8.1 Platform Architecture

- **Landing Zone**: Deploy into AWS Control Tower-managed accounts with separate environments (dev/stage/prod), enforce IAM boundaries, centralized logging (CloudTrail, GuardDuty).
- **Networking**: Multi-AZ VPC with private subnets for data-plane workloads; AWS Transit Gateway for cross-account connectivity; use AWS PrivateLink for managed services (MSK, S3, DynamoDB).
- **Kubernetes Runtime**: Amazon EKS (Bottlerocket or Managed Node Groups) for PPPE services and Dataplane pods; enable Cluster Autoscaler & Karpenter for automated scaling; isolate namespaces per workload.
- **Dataplane Deployment**: Run Dataplane Vector as StatefulSets with persistent volumes (EBS gp3 or io2), use node affinity to dedicate high-throughput nodes (c7g/c7i). Horizontal Pod Autoscaler driven by ingestion lag.
- **Event Bus**: Amazon MSK (Kafka) with multi-AZ brokers, tiered storage for long retention; configure partitions per data source to parallelize ingestion; leverage MSK Serverless for spiky workloads.
- **Storage**:
- Raw landing in Amazon S3 (multi-region replication) via Dataplane sinks or MSK Connect.
- Checkpoints in Amazon DynamoDB (global tables) or Amazon Aurora PostgreSQL for transactional consistency.
- Long-term OCSF outputs to S3 + Glacier; optionally push to Amazon OpenSearch for search.
- **Compute Scaling**: Use Graviton-based autoscaling groups (ARM) for Dataplane (aligns with `dataplane.aarch64`). Transformation worker pods scale horizontally; use AWS Fargate for burst workloads if necessary.

### 8.2 Data Volume Strategy (100s PB/day)

- **Partitioning**: Pre-shard Kafka/MSK topics by source, tenant, time bucket. Scale to ≥10,000 partitions for `raw-security-events` to sustain 100 PB/day throughput. Representative MSK sizing:

```yaml
  msk:
    cluster_type: provisioned
    broker_count: 90
    broker_instance_type: kafka.m7g.24xlarge
    storage_per_broker_gb: 64000
    tiered_storage: enabled

    topic_configs:
      raw-security-events:
        partitions: 10000
        replication_factor: 3
        min_insync_replicas: 2
        retention_bytes: -1
        retention_ms: 604800000

      ocsf-events:
        partitions: 5000
        replication_factor: 3
        min_insync_replicas: 2
```

- **Throughput Nodes**: Employ c7gn or m7i-flex instances with enhanced networking (ENA Express) for ingestion pods.
- **Autoscaling Policies**: Scale Dataplane pods based on MSK consumer lag, CPU utilization > 60%, and memory pressure. Use predictive scaling for known peaks.
- **Storage Lifecycle**: Enable S3 Intelligent-Tiering; configure MSK tiered storage to offload historical data. For checkpoints, purge old states via TTL policies.
- **Backpressure Handling**: Implement overflow buffer (SQS DLQ or separate Kafka topic) when downstream lag exceeds SLA; automate replays once capacity recovered.

### 8.3 Resilience & Disaster Recovery

- **Multi-AZ**: All critical services span at least 3 AZs; use AWS Fault Injection Simulator to test failovers.
- **Multi-Region Active/Active**: Deploy parallel stacks (EKS, MSK, S3) in two AWS regions; replicate manifests & RAG indexes using AWS DMS or custom Lambda. Route traffic via AWS Global Accelerator.
- **Backups**: Automated EBS snapshots, DynamoDB point-in-time recovery, S3 versioning. Store critical configs/manifests in AWS Backup vaults.
- **chaos Testing**: Run weekly chaos experiments (terminate pods, kill brokers) to validate auto-healing.

### 8.4 Observability & Operations

- **Logging**: Centralize via CloudWatch Logs + OpenTelemetry Collector; stream to S3 and security tools.
- **Metrics**: Prometheus (AMP) with Grafana dashboards; key KPIs—ingest throughput, ms/event, MSK lag, validation failure rate, RAG freshness.
- **Tracing**: AWS X-Ray or AWS Distro for OpenTelemetry for end-to-end tracing (Dataplane → worker → outputs).
- **Cost Controls**: Leverage Savings Plans for compute, tiered storage policies, monitor via AWS Cost Explorer & budgets.
- **Security**: IAM least privilege, Secrets Manager for API keys, KMS encryption (S3, EBS, MSK), AWS WAF in front of web UI, Cognito for auth replacement of static tokens.

### 8.5 Continuous Delivery & Compliance

- **CI/CD**: GitHub Actions or AWS CodePipeline triggers building container images (ECR), Helm releases (Argo CD). Include integration tests, dataplane validation, and RAG ingestion dry runs.
- **Policy Enforcement**: Use OPA/Gatekeeper in EKS for pod security; AWS Config/Control Tower guardrails; integrate with Security Hub.
- **Compliance**: Map controls to SOC2/FedRAMP as needed; maintain evidence via AWS Audit Manager. Ensure audit logs (SDL + CloudTrail) retained per policy.

### 8.6 Data Science & RAG at Scale

- **Vector Store**: Managed Milvus-on-EKS or switch to AWS OpenSearch Vector Search; scale shards to accommodate massive corpora (dataplane docs, runtime feedback, manifests).
- **RAG Updates**: Use AWS Step Functions nightly pipeline to ingest new docs, manifests, runtime logs; store embeddings in dedicated cluster. Use SQS to queue ingestion tasks on change events (git push, manifest publish, validation summary).
- **LLM Integration**: Host Claude via Bedrock or secure VPC endpoints; implement caching of frequent prompts, retrieval filtering by AWS tags.

### 8.7 Roadmap Timeline (High-Level)

- **T0–T2 (0–6 months)**: Complete Phases 0–6 in staging, deploy Dataplane validator & transform worker in AWS dev account, integrate MSK + S3, stand up basic observability. Pilot <1 PB/day in production with single-region footprint.
- **T3–T4 (6–12 months)**: Ramp to 1–10 PB/day, introduce multi-region active/active, autoscaling policies, FinOps dashboards, Cognito-based auth, compliance guardrails.
- **T5–T7 (12–18 months)**: Grow to 10–50 PB/day, mature cost optimization (Spot, lifecycle management), expand RAG infra, execute quarterly DR drills, refine canary promotion heuristics.
- **T8–T10 (18–24 months)**: Reach 50–100 PB/day capability by scaling worker pools, enabling tiered storage everywhere, finalizing DR playbooks, completing compliance certifications, hardening cross-region replication.

---

## 9. Additional AWS Production Considerations

### 9.1 Network Architecture & Bandwidth Planning

- **VPC**: /16 CIDR with dedicated /17 pod subnet (amazon-vpc-cni or Cilium). Private subnets only; NAT for limited egress.
- **Transit Gateway**: Attach on-prem/other accounts; request 100 Gbps bandwidth quota.
- **PrivateLink**: Interface endpoints for MSK, DynamoDB, Bedrock; gateway endpoints for S3. Minimizes data-transfer cost and exposure.
- **Bandwidth budget**: Plan for ~150 Gbps ingress (SCOL sources), 500 Gbps east-west (MSK ↔ workers), 100 Gbps egress to S3, 50 Gbps cross-region replication (manifests/checkpoints only to control spend).
- **Acceleration**: Enable S3 Transfer Acceleration for multi-region writes; use CloudFront/Global Accelerator for web UI.

### 9.2 Compliance & Data Governance

- **Classification**: Define public/confidential/restricted tiers with corresponding retention, encryption (KMS CMK, HSM), access logging.
- **GDPR automation**: Lambda + SQS pipeline for right-to-erasure with ≤30 day SLA; verify via S3 inventory.
- **Audit trail**: CloudTrail (management + data events for S3 buckets), DynamoDB/Aurora streams; enforce WAF and VPC Flow Logs.
- **Secrets & IAM**: AWS Secrets Manager (90-day rotation), IAM roles with session tags, AWS Config guardrails.

### 9.3 Disaster Recovery Playbooks

- **Single AZ outage**: MSK rebalance auto-recovers (<5 min); monitor broker alarms.
- **Regional failover**: Route53 health checks trigger manual playbook (`scripts/dr_failover.sh`). RPO ≤15 min, RTO ≤60 min. Steps include MSK topic sync, Dataplane config swap, E2E validation.
- **Data corruption**: Use S3 versioning to restore corrupted prefixes; replay transform worker for affected window; document via CloudTrail audit.

### 9.4 Cost Modeling & FinOps

- **Cost model**: Maintain calculator (e.g., `scripts/cost_model.py`) covering MSK, S3, EKS, observability, RAG, support services. Baseline cost ≈$3.4M/month (~$0.0011/GB, ~$0.000001/event) at 100 PB/day.
- **Optimization levers**: Spot/Fargate for non-critical workers, S3 lifecycle to Glacier (≥90 days), MSK right-sizing through tiered storage, 3-year Savings Plans, OpenSearch tuning.
- **FinOps dashboard**: Track cost per parser/tenant, highlight outliers, surface cost-per-GB/event trends, recommend actions.

---

## 10. Iterative Delivery Strategy & Priority Matrix

### 10.1 Implementation Priority Matrix

| Priority | Goal | Scope | Effort (hrs) | Dependencies |
|----------|------|-------|--------------|---------------|
| 🔴 Critical Path | Dataplane validation | Phase 0 prep, message bus abstraction, transform executor, dataplane validator, integration tests | ~28 | Phase 0 → Phase 1 → Phase 7 |
| 🟡 Runtime Pipeline | Live event processing | Transform worker, chained transforms, manifest schema/publish hook, system tests | ~38 | Critical Path |
| 🟢 Production Hardening | Observability & resilience | Web UI enhancements, canary routing, RAG checksum store & ingestion, runtime feedback loop, performance tests, rollback automation | ~56 | Runtime Pipeline |

### 10.2 Sprint Plan (3-Week Execution)

- **Sprint 1 – Foundation**
- Day 1–2: Platform prep (Phase 0) + message bus abstraction
- Day 3–5: Dataplane validator & executor strategy (Phase 1)
- Day 5: Integration tests for validator + abstractions
- Outcome: PPPE validates Lua via dataplane prior to deployment.

- **Sprint 2 – Runtime Pipeline**
- Day 1–2: Transform worker implementation (Phase 2)
- Day 3: Dataplane chained transforms (Phase 3)
- Day 4: Manifest schema/versioning + publish hook (Phase 4)
- Day 5: System tests (Phase 7 subset)
- Outcome: Event bus powered pipeline producing OCSF outputs end-to-end.

- **Sprint 3 – Production Readiness**
- Day 1–2: Web UI runtime metrics & canary control (Phase 5)
- Day 3: Canary router & promotion logic (Phase 5 enhancement)
- Day 4: RAG expansion with checksum store + feedback ingestion (Phase 6)
- Day 5: Performance benchmarking + automated rollback drill (Phase 7)
- Outcome: Production-ready stack with observability, staged rollouts, resilient RAG pipeline.

### 10.3 Risk Assessment Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Lua runtime divergence (lupa vs dataplane) | Medium | High | Maintain executor abstraction, run parity tests across executors |
| Message bus outage | Low | High | Bus adapter fallback to memory queue for testing; monitor & failover strategy |
| Manifest version conflicts | Medium | Medium | Semantic versioning, compatibility checks, CI validation of manifest schema |
| RAG ingestion overload | Low | Medium | Checksum deduplication, ingestion throttling, monitor Milvus latency |
| Canary routing bugs | Medium | Medium | Consistent hashing selection, promotion gates, audit logging |
| Rollback gaps | Low | Critical | Automated rollback CI workflow, manual playbooks |

---

## 11. Phase 3 Detailed Implementation Plan

1. **Runtime Telemetry & Web UI Enhancements**

- Extend runtime service to expose metrics (processed events, errors, canary error rates).
- Implement `/api/runtime/status` and `/api/runtime/reload/<parser_id>` with backing service logic.
- Update web dashboard to surface canary vs stable stats and reload actions.
- Ensure SDL audit logging captures runtime actions.

2. **Canary Deployment Pipeline**

- Integrate `CanaryRouter` into transform worker; load manifests (stable/canary) and route events using consistent hash.
- Add orchestrator hooks to publish canary manifests (semantic version bump, canary percentage).
- Implement promotion endpoint/action that swaps canary → stable once metrics meet thresholds.
- Persist canary metrics for later analysis.

3. **RAG Checksum Integration**

- Wire `start_rag_autosync_dataplane.py` into ingestion workflow; document usage.
- Update RAG prompts to leverage new `dataplane_doc`/`runtime_feedback` tags.
- Add tests ensuring checksum store prevents duplicate ingestion.

4. **Rollback Automation & Testing**

- Implement automated rollback tests (`tests/test_rollback_scenarios.py`) covering feature flag toggles.
- Configure GitHub Actions (scheduled) to execute rollback drill.
- Document rollback procedure and update CI guidelines.

5. **Performance Benchmarking**

- Add load-test harness for transform worker (synthetic events via memory adapter).
- Capture baseline latency/throughput metrics.

6. **Documentation Updates**

- Update `docs/Transform_Worker.md`, `docs/Dataplane_Validation.md`, and web UI docs with runtime features.
- Add section on canary operations, promotion process, and rollback steps.
