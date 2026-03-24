# Transform Worker Service

## Overview
The transform worker consumes raw events from the message bus, retrieves the latest parser artifacts (manifest, Lua transform), executes the transform using the configured executor, and publishes normalized OCSF events downstream.

```
raw-security-events ──> transform_worker ──> ocsf-events
                              │
                              └─► runtime metrics + canary signals ──► Web UI / API
```

## Components
- `components/message_bus_adapter.py`: abstraction over Kafka, Redis Streams, or in-memory queues.
- `components/transform_executor.py`: executes Lua via lupa (fast path) or dataplane subprocess (parity path).
- `components/manifest_store.py`: loads `transform.lua` and `manifest.json` from `output/<parser_id>/`.
- `services/transform_worker.py`: main worker logic (runtime metrics, canary router, promotion readiness, reload handling).
- `services/start_transform_worker.py`: CLI entrypoint.

## Configuration
`config.yaml`
```yaml
message_bus:
  type: "kafka"  # or redis, memory
  kafka:
    bootstrap_servers: "kafka:9092"
    group_id: "pppe-transform-worker"

transform_worker:
  enabled: true
  executor: "lupa"  # or dataplane
  input_topic: "raw-security-events"
  output_topic: "ocsf-events"

canary:
  enabled: true
  percentage: 10
  promotion_threshold: 1000
  error_tolerance: 0.01
  semantic_suffix: "-canary"
  deployed_by: "pppe"
  environment: "staging"

dataplane:
  enabled: true
  binary_path: "/opt/dataplane/dataplane"
```

- `executor` controls runtime strategy: `lupa` (in-process) or `dataplane` (subprocess).
- `message_bus.type` selects adapter; choose `memory` for local testing.
- `canary` governs stable/canary routing, promotion thresholds, and metadata persisted in manifests.

## Deployment
### Docker Compose
Add service:
```yaml
transform-worker:
  build: .
  command: ["python", "services/start_transform_worker.py"]
  environment:
    - PPPE_CONFIG=/app/config.yaml
  depends_on:
    - parser-eater
```

### Kubernetes
- Deploy as Deployment with config map for `config.yaml`.
- Set resource requests/limits based on throughput target.
- Attach to MSK/Redis via service endpoints.

## Operations
- **Runtime metrics**: `RuntimeMetricsStore` tracks total events, successes/failures, canary vs stable counts, last error, error rate. Exposed via `RuntimeService` and `/api/runtime/status`.
- **Canary routing**: `CanaryRouter` registers stable/canary manifests, hashes events for routing, records per-version metrics, and reports promotion readiness when error rate stays within tolerance above the configured sample threshold.
- **Reload workflow**: `/api/runtime/reload/<parser_id>` sets a pending reload flag in `RuntimeService`; workers poll via `pop_runtime_reload` to hot-reload manifests (implementation forthcoming).
- **Promotion workflow**: `/api/runtime/canary/<parser_id>/promote` marks parser for promotion; worker evaluates metrics and updates status to `ready` when thresholds met, enabling operator action.
- **Logging**: worker logs missing manifests/Lua, execution failures, and promotion readiness changes.
- **Shutdown**: `start_transform_worker.py` handles graceful shutdown.

## Testing
- Unit tests: `tests/test_message_bus.py`, `tests/test_transform_executor.py`, `tests/test_pipeline_validator_dataplane.py`.
- Upcoming: add coverage for `CanaryRouter` promotion heuristics, runtime metrics serialization, and `/api/runtime/*` endpoints.

