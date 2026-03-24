# Phase 3 (Production Hardening) Status

## Completed
- Manifest schema validation (`components/manifest_schema.py`) and manifest writing via `ParserOutputManager`.
- Runtime scaffolding: `components/runtime_metrics.py`, `components/canary_router.py`, `components/manifest_store.py`, `services/runtime_service.py`.
- Transform worker wiring for manifest loading and optional runtime service injection.
- RAG checksum store (`components/rag_checksum_store.py`) and ingestion script (`start_rag_autosync_dataplane.py`).
- Dockerfile support for optional dataplane binary staging.
- Documentation: Phase 3 plan added to `docs/Hybrid_Architecture_Plan.md`.

## In Progress / TODO
1. **Canary Routing & Promotion** *(focus next)*
   - Emit stable/canary manifests with semantic version + percentage from orchestrator.
   - Implement transform worker routing, metrics, and promotion-triggered reloads.

2. **Runtime Metrics & Web UI**
   - Collect per-parser stats, expose via `/api/runtime/status` and UI dashboard.
   - Support `/api/runtime/reload/<parser_id>` with manifest reload logic + audit logging.

3. **RAG Checksum Automation**
   - Integrate `start_rag_autosync_dataplane.py` into ingestion pipeline.
   - Document usage and ensure deduped ingestion into Milvus/OpenSearch.

4. **Rollback Automation & Performance Testing**
   - Create rollback integration tests + scheduled CI run.
   - Build load harness for transform worker (synthetic events) to benchmark throughput.

5. **Documentation**
   - Update `docs/Transform_Worker.md`, web UI guide, and README with runtime metrics, canary operations, and rollback procedures.

