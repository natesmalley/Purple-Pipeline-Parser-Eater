# Agent 3: Observo.ai Output Integration Architecture

## Overview

Agent 3 is the final stage of the Purple Pipeline that consumes OCSF-normalized security events from Agent 2 and reliably delivers them to multiple destinations (Observo.ai, S3, databases, etc.) with comprehensive validation, retry logic, and observability.

## Architecture

### Data Flow

```
Agent 2 (ocsf-events topic)
    ↓
OutputService
    ├─ Message Bus Subscribe
    ├─ OCSF Validation
    └─ Multi-Sink Delivery
        ├─ ObservoIngestClient → Observo.ai
        ├─ S3ArchiveSink → AWS S3
        └─ (Extensible for other sinks)
```

### Component Structure

```
components/
├── observo_ingest_client.py       # Observo.ai event ingestion
├── output_validator.py             # OCSF compliance validation
└── sinks/
    ├── __init__.py
    ├── base_sink.py                # Abstract sink interface
    └── s3_archive_sink.py          # S3 archival implementation

services/
├── output_service.py               # Main orchestration service

config/
└── output_service.yaml             # Configuration template

scripts/
└── start_output_service.py         # CLI startup script

tests/
├── test_output_validator.py        # Validator tests
├── test_observo_ingest_client.py   # Observo client tests
├── test_s3_archive_sink.py         # S3 sink tests
├── test_output_service.py          # Service orchestration tests
└── integration/
    └── test_e2e_pipeline.py        # End-to-end tests
```

## Components

### 1. ObservoIngestClient

**File**: `components/observo_ingest_client.py`

Async HTTP client for Observo.ai Event Ingestion API.

**Features**:
- Batch event ingestion (configurable batch size)
- Automatic OCSF log extraction from wrapper
- Error handling and statistics tracking
- Connection testing

**Usage**:
```python
client = ObservoIngestClient(
    base_url="https://api.observo.ai",
    api_token="your-token",
    max_batch_size=100
)

result = await client.ingest_events([event1, event2])
stats = client.get_statistics()
await client.close()
```

**API Endpoint**: `POST /api/v1/ingest/ocsf`

### 2. OutputValidator

**File**: `components/output_validator.py`

OCSF compliance validator ensuring data quality before delivery.

**Validates**:
- Required fields: `class_uid`, `category_uid`, `severity_id`, `time`, `metadata`
- Required metadata: `version`, `product`
- Data types: integers for UIDs, numeric for time
- Severity ranges: 0-6

**Usage**:
```python
validator = OutputValidator(strict_mode=False)
is_valid = validator.validate_ocsf(event_log)
stats = validator.get_statistics()
```

### 3. S3ArchiveSink

**File**: `components/sinks/s3_archive_sink.py`

Archives OCSF events to AWS S3 with partitioning and compression.

**Features**:
- Partitioned by: date (year/month/day/hour) and parser_id
- JSONL format with optional gzip compression
- Batch uploads for efficiency
- Error handling and statistics

**S3 Path Structure**:
```
s3://bucket/prefix/year=2025/month=11/day=07/hour=12/parser_id=netskope_dlp/events-{timestamp}.jsonl.gz
```

**Usage**:
```python
sink = S3ArchiveSink(
    bucket_name="my-bucket",
    prefix="ocsf-archive",
    batch_size=1000,
    compression=True
)

await sink.write_event(event)
await sink.write_events([event1, event2])
await sink.flush()
await sink.close()
```

### 4. BaseSink

**File**: `components/sinks/base_sink.py`

Abstract base class for all sinks enabling extensibility.

**Interface**:
```python
class BaseSink(ABC):
    async def write_event(event) -> bool
    async def write_events(events) -> bool
    async def flush() -> bool
    def get_statistics() -> Dict
    async def close() -> None
```

### 5. OutputService

**File**: `services/output_service.py`

Main orchestration service coordinating the entire output pipeline.

**Responsibilities**:
1. Consume OCSF events from message bus
2. Validate OCSF compliance
3. Route to multiple sinks in parallel
4. Handle retries with exponential backoff
5. Track delivery status and metrics

**Configuration**:
```yaml
message_bus:
  type: kafka  # kafka, redis, or memory
  input_topic: "ocsf-events"

validator:
  strict_mode: false

sinks:
  observo:
    enabled: true
    base_url: "https://api.observo.ai"
    api_token: "${OBSERVO_API_TOKEN}"

  s3_archive:
    enabled: true
    bucket: "purple-pipeline-events"

retry:
  max_attempts: 5
  base_backoff_seconds: 2
  max_backoff_seconds: 60
```

**Usage**:
```python
config = load_config("config/output_service.yaml")
service = OutputService(config)
await service.start()  # Blocks until shutdown
stats = service.get_statistics()
```

## Event Format

### Input (from Agent 2)

```json
{
  "_metadata": {
    "source_type": "kafka",
    "parser_id": "netskope_dlp",
    "parser_version": "1.0.0",
    "transform_time": "2025-11-07T12:00:01Z",
    "execution_time_ms": 12.5,
    "canary_used": false
  },
  "log": {
    "class_uid": 2004,
    "class_name": "Detection Finding",
    "category_uid": 2,
    "severity_id": 4,
    "time": 1699363200000,
    "metadata": {
      "version": "1.5.0",
      "product": {
        "name": "Netskope",
        "vendor_name": "Netskope"
      }
    }
  }
}
```

### Output to Observo.ai

The OutputService extracts the `log` field and sends it to Observo.ai:

```json
{
  "events": [
    {
      "class_uid": 2004,
      "class_name": "Detection Finding",
      "category_uid": 2,
      "severity_id": 4,
      "time": 1699363200000,
      "metadata": {
        "version": "1.5.0",
        "product": {
          "name": "Netskope",
          "vendor_name": "Netskope"
        }
      }
    }
  ],
  "source": "purple-pipeline",
  "dataset": "netskope_dlp",
  "timestamp": "2025-11-07T12:00:01Z"
}
```

## Retry Logic

Failed deliveries are retried with exponential backoff:

```
Attempt 1: Immediate
Attempt 2: 2 seconds
Attempt 3: 4 seconds
Attempt 4: 8 seconds
Attempt 5: 16 seconds (capped at max_backoff_seconds)
```

Configuration:
```yaml
retry:
  max_attempts: 5              # Number of retry attempts
  base_backoff_seconds: 2      # Initial backoff
  max_backoff_seconds: 60      # Maximum backoff
```

## Error Handling

### Validation Failures
- Events failing OCSF validation are logged and skipped
- Optional: Can be sent to validation-errors DLQ
- Statistics tracked separately

### Delivery Failures
- Automatic retry with exponential backoff
- After max retries exhausted: logged as failed
- Optional: Can be sent to output-failures DLQ
- Per-sink error tracking

### Sink Failures
- Individual sink failures don't block other sinks
- All sinks deliver in parallel
- Partial success is recorded

## Statistics

The OutputService tracks comprehensive metrics:

```python
{
  "total_received": 1000,
  "validation_passed": 950,
  "validation_failed": 50,
  "delivery_success": 945,
  "delivery_failed": 5,
  "by_sink": {
    "observo": {
      "success": 945,
      "failed": 5,
      "avg_latency_ms": 45.2,
      "max_latency_ms": 150.0
    },
    "s3_archive": {
      "success": 945,
      "failed": 5,
      "avg_latency_ms": 120.5,
      "max_latency_ms": 500.0
    }
  }
}
```

## Configuration

### config/output_service.yaml

Complete configuration with all options:

```yaml
message_bus:
  type: kafka
  bootstrap_servers: "localhost:9092"
  input_topic: "ocsf-events"
  consumer_group: "output-workers"
  security_protocol: "PLAINTEXT"

validator:
  strict_mode: false
  log_warnings: true

sinks:
  observo:
    enabled: true
    base_url: "https://api.observo.ai"
    api_token: "${OBSERVO_API_TOKEN}"
    batch_size: 100
    timeout_seconds: 30

  s3_archive:
    enabled: true
    bucket: "purple-pipeline-events"
    prefix: "ocsf-archive"
    aws_region: "us-east-1"
    batch_size: 1000
    compression: true

retry:
  max_attempts: 5
  base_backoff_seconds: 2
  max_backoff_seconds: 60

error_handling:
  dlq_enabled: true
  dlq_topic: "output-failures"
  validation_error_topic: "validation-errors"

logging:
  level: INFO
  file: "./logs/output_service.log"
```

## Running the Service

### Starting the Service

```bash
python scripts/start_output_service.py --config config/output_service.yaml
```

### Environment Variables

Set credentials before starting:

```bash
export OBSERVO_API_TOKEN="your-observo-token"
export AWS_ACCESS_KEY_ID="your-aws-access-key"
export AWS_SECRET_ACCESS_KEY="your-aws-secret-key"
```

### Docker Deployment

```bash
docker build -t purple-pipeline-output .
docker run \
  -e OBSERVO_API_TOKEN="..." \
  -e AWS_ACCESS_KEY_ID="..." \
  -e AWS_SECRET_ACCESS_KEY="..." \
  -v $(pwd)/config:/app/config \
  purple-pipeline-output
```

## Testing

### Unit Tests

Test individual components:

```bash
pytest tests/test_output_validator.py -v
pytest tests/test_observo_ingest_client.py -v
pytest tests/test_s3_archive_sink.py -v
pytest tests/test_output_service.py -v
```

### Integration Tests

Test end-to-end pipeline:

```bash
pytest tests/integration/test_e2e_pipeline.py -v
```

### Running All Tests

```bash
pytest tests/ -v --tb=short
```

### Test Coverage

```bash
pytest tests/ --cov=components --cov=services --cov-report=html
```

## Extension Points

### Adding a New Sink

1. Create new class inheriting from `BaseSink`
2. Implement required methods
3. Register in `OutputService._initialize_sinks()`
4. Add configuration section

Example:
```python
class ElasticsearchSink(BaseSink):
    async def write_event(self, event: Dict[str, Any]) -> bool:
        # Your implementation
        pass
```

## Performance Characteristics

### Throughput
- Target: >1000 events/sec
- Depends on: Message bus, sink performance, network latency

### Latency
- Target: <100ms average delivery latency
- Per-event: Validation (<1ms) + Sink delivery (10-100ms)

### Scalability
- Horizontal: Multiple OutputService instances with shared message bus
- Vertical: Async concurrency handles thousands of concurrent operations

## Monitoring

### Metrics to Track
- Events received per second
- Validation pass rate
- Delivery success rate
- Average latency per sink
- Error rates and types

### Logging
- All operations logged with appropriate levels
- Configurable log file location
- Structured logging with metadata

### Health Checks
```python
# Test Observo.ai connection
is_healthy = await client.test_connection()

# Get statistics
stats = service.get_statistics()
```

## Dependencies

### Required
- `aiohttp>=3.8.0` - Async HTTP for event delivery
- `httpx>=0.24.0` - Observo.ai API client
- `pyyaml>=6.0` - Configuration parsing

### Optional (for S3)
- `boto3>=1.34.0` - AWS SDK

### For Testing
- `pytest>=8.4.2`
- `pytest-asyncio>=1.2.0`
- `pytest-mock>=3.15.1`

## Troubleshooting

### Events Not Delivered

1. Check configuration: `output_service.yaml`
2. Verify credentials: `OBSERVO_API_TOKEN`, AWS keys
3. Check message bus connection
4. Review validation logs for failures
5. Check sink statistics for errors

### High Latency

1. Increase batch sizes
2. Increase concurrent deliveries
3. Check network connectivity
4. Review sink performance metrics

### Memory Issues

1. Reduce batch sizes
2. Reduce buffer sizes
3. Monitor event arrival rate
4. Check for event processing bottlenecks

## Future Enhancements

1. Dead-letter queue (DLQ) implementation
2. Elasticsearch sink
3. Splunk HEC sink
4. Kafka producer for output events
5. Metrics export (Prometheus, CloudWatch)
6. Advanced routing (by severity, source, etc.)
7. Event transformation/enrichment
8. Delivery confirmations and acknowledgments

## References

- OCSF Specification: https://github.com/ocsf/ocsf-spec
- Observo.ai Documentation: https://observo.ai/docs
- AWS S3: https://docs.aws.amazon.com/s3/
