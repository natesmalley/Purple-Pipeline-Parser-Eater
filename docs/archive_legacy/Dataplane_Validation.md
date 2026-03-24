# Dataplane Validation Guide

## Overview
The Phase 1 hybrid integration adds an optional dataplane-backed validation stage to the Purple Pipeline Parser Eater (PPPE) workflow. When enabled, the validator executes each generated Lua transform inside the Observo dataplane binary before deployment, catching runtime and OCSF schema issues early. Phase 3 extends this flow with manifest metadata and runtime feedback so validation signals flow through the runtime worker and web UI.

## Requirements
- Observo dataplane binary staged at `/opt/dataplane/dataplane` (or override via `config.yaml`).
- Sample events available for the parser (passed into `PipelineValidator.validate_complete_pipeline`).
- Optional dependencies for runtime adapters (Kafka, Redis) remain disabled by default.

## Configuration
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

Set `dataplane.enabled` to `true` and ensure the binary path is correct. The validator runs when sample events are supplied.

## PipelineValidator Integration
- Stage added after metadata validation (Phase 1 results).
- Results recorded under `validations.dataplane_runtime` with:
  - `status`: `passed`/`failed`
  - `ocsf_missing_fields`
  - `stderr`: dataplane output (trimmed)
  - `execution_stats`: events processed, runtime, exit code (Phase 3 enhancement)
- If the binary is missing or initialization fails, the validator logs a warning and skips the dataplane stage.
- Manifests generated in Phase 4 now carry hashes and compatibility metadata that reference dataplane validation results; these artifacts are ingested into RAG and surfaced in the runtime worker.

## Testing
- Unit coverage: `tests/test_pipeline_validator_dataplane.py` verifies graceful skip behavior when the binary is unavailable.
- Full validation tests are skipped in CI until the binary is staged (`tests/test_dataplane_validator.py`). These run in staging environments where the binary is present.

## Next Steps (Beyond Phase 1)
- Add integration tests that execute dataplane validation during CI once the binary is available in build images.
- Feed dataplane validation results into the RAG corpus (Phase 6).
- Extend manifest metadata with dataplane validation summaries.

