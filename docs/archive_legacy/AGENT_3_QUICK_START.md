# Agent 3: Quick Start Guide

## Installation

### 1. Install Dependencies

```bash
# Install required packages
pip install -r requirements.txt

# Or minimal setup (without ML packages)
pip install -r requirements-minimal.txt

# Add optional packages for S3 support
pip install boto3>=1.34.0
```

### 2. Configure Credentials

Set environment variables for external services:

```bash
# Observo.ai credentials
export OBSERVO_API_TOKEN="your-api-token"

# AWS credentials (for S3 archival)
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

### 3. Configure Output Service

Edit `config/output_service.yaml`:

```yaml
# Kafka/Redis/Memory message bus
message_bus:
  type: kafka
  bootstrap_servers: "localhost:9092"
  input_topic: "ocsf-events"

# Enable desired sinks
sinks:
  observo:
    enabled: true
    base_url: "https://api.observo.ai"
    api_token: "${OBSERVO_API_TOKEN}"

  s3_archive:
    enabled: true
    bucket: "my-bucket"
```

## Starting the Service

```bash
# Start output service
python scripts/start_output_service.py

# With custom config
python scripts/start_output_service.py --config config/output_service.yaml

# With logging
python scripts/start_output_service.py \
  --config config/output_service.yaml 2>&1 | tee output_service.log
```

## Testing

### Run All Tests

```bash
pytest tests/ -v
```

### Run Specific Test Suite

```bash
# Validator tests
pytest tests/test_output_validator.py -v

# ObservoIngestClient tests
pytest tests/test_observo_ingest_client.py -v

# S3 Sink tests
pytest tests/test_s3_archive_sink.py -v

# OutputService tests
pytest tests/test_output_service.py -v

# End-to-end tests
pytest tests/integration/test_e2e_pipeline.py -v
```

### Test Coverage

```bash
pytest tests/ --cov=components --cov=services --cov-report=html
```

## Docker Deployment

### Build Image

```bash
docker build -t purple-pipeline-output:latest -f Dockerfile .
```

### Run Container

```bash
docker run \
  -e OBSERVO_API_TOKEN="..." \
  -e AWS_ACCESS_KEY_ID="..." \
  -e AWS_SECRET_ACCESS_KEY="..." \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/logs:/app/logs \
  --network host \
  purple-pipeline-output:latest
```

## Kubernetes Deployment

### Create ConfigMap

```bash
kubectl create configmap output-service-config \
  --from-file=config/output_service.yaml
```

### Create Secrets

```bash
kubectl create secret generic observo-credentials \
  --from-literal=api-token="${OBSERVO_API_TOKEN}"

kubectl create secret generic aws-credentials \
  --from-literal=access-key="${AWS_ACCESS_KEY_ID}" \
  --from-literal=secret-key="${AWS_SECRET_ACCESS_KEY}"
```

### Deploy

```bash
kubectl apply -f deployment/k8s/output-service.yaml
```

## Monitoring

### Check Service Status

```bash
# View logs
tail -f logs/output_service.log

# Check metrics endpoint (if exposed)
curl http://localhost:8080/metrics
```

### Verify Deliveries

```python
# Python script to check statistics
from services.output_service import OutputService
import yaml

with open('config/output_service.yaml') as f:
    config = yaml.safe_load(f)

service = OutputService(config)
print(service.get_statistics())
```

### Test Connectivity

```python
# Test Observo.ai connection
from components.observo_ingest_client import ObservoIngestClient

client = ObservoIngestClient(
    base_url="https://api.observo.ai",
    api_token="your-token"
)
is_healthy = await client.test_connection()
print(f"Observo.ai: {'✓' if is_healthy else '✗'}")
```

## Architecture Overview

```
Agent 2: Transform Pipeline (ocsf-events topic)
    ↓
Message Bus (Kafka/Redis/Memory)
    ↓
Output Service
    ├─ Validation (OCSF compliance)
    ├─ Observo.ai Delivery
    ├─ S3 Archival
    └─ Metrics & Monitoring
    ↓
Results
    ├─ Observo.ai: Live security analytics
    ├─ S3: Long-term storage
    └─ Logs: Operational visibility
```

## Event Flow

### 1. Event Ingestion

Events arrive from Agent 2 on the `ocsf-events` topic:

```json
{
  "_metadata": {
    "parser_id": "netskope_dlp",
    "parser_version": "1.0.0"
  },
  "log": {
    "class_uid": 2004,
    "category_uid": 2,
    "severity_id": 4,
    "time": 1699363200000,
    "metadata": { "version": "1.5.0", "product": {...} }
  }
}
```

### 2. Validation

OCSF compliance is verified:
- Required fields present
- Data types correct
- Value ranges valid

Invalid events are logged and skipped.

### 3. Delivery

Events delivered in parallel to configured sinks:

- **Observo.ai**: Real-time security analytics
- **S3**: Archival with partitioning by date and parser
- **Other sinks**: Extensible framework

### 4. Retry Logic

Failed deliveries automatically retry with exponential backoff:
```
Attempt 1: Immediate
Attempt 2: 2s
Attempt 3: 4s
Attempt 4: 8s
Attempt 5: 16s (max 60s)
```

## Configuration Examples

### Memory Bus (Development)

```yaml
message_bus:
  type: memory
  input_topic: "ocsf-events"

sinks:
  observo:
    enabled: false
  s3_archive:
    enabled: false
```

### Kafka (Production)

```yaml
message_bus:
  type: kafka
  bootstrap_servers:
    - "kafka1:9092"
    - "kafka2:9092"
    - "kafka3:9092"
  input_topic: "ocsf-events"
  consumer_group: "output-workers"
  security_protocol: "SASL_SSL"

sinks:
  observo:
    enabled: true
    base_url: "https://api.observo.ai"
    api_token: "${OBSERVO_API_TOKEN}"
    batch_size: 100

  s3_archive:
    enabled: true
    bucket: "purple-pipeline-events"
    prefix: "ocsf"
    batch_size: 1000
```

### Redis (High-Performance)

```yaml
message_bus:
  type: redis
  host: "redis:6379"
  port: 6379
  input_topic: "ocsf-events"

sinks:
  observo:
    enabled: true
    base_url: "https://api.observo.ai"
    api_token: "${OBSERVO_API_TOKEN}"
```

## Troubleshooting

### Issue: "Connection refused" to Observo.ai

**Solution**: Verify API token and endpoint:
```bash
curl -H "Authorization: Bearer $OBSERVO_API_TOKEN" \
  https://api.observo.ai/api/v1/health
```

### Issue: S3 authentication errors

**Solution**: Check AWS credentials:
```bash
aws sts get-caller-identity
aws s3 ls
```

### Issue: Events not being consumed

**Solution**: Verify message bus configuration:
```bash
# For Kafka
kafka-console-consumer --bootstrap-server localhost:9092 \
  --topic ocsf-events --from-beginning

# For Redis
redis-cli
> XLEN ocsf-events
```

### Issue: Validation failures

**Solution**: Check event format from Agent 2:
```python
from components.output_validator import OutputValidator
validator = OutputValidator()
validator.validate_ocsf(your_event_log)
print(validator.get_statistics())
```

## Performance Tuning

### Increase Throughput

```yaml
# Larger batches
sinks:
  observo:
    batch_size: 500  # Default 100
  s3_archive:
    batch_size: 5000  # Default 1000

# Faster retries
retry:
  base_backoff_seconds: 0.5  # Default 2
  max_backoff_seconds: 10    # Default 60
```

### Reduce Latency

```yaml
# Immediate flush
retry:
  max_attempts: 2  # Reduce from 5

# No compression (trade storage for speed)
sinks:
  s3_archive:
    compression: false
```

## Health Checks

### Prometheus Metrics (if exposed)

```bash
curl http://localhost:8080/metrics | grep purple_pipeline
```

### Service Statistics

```bash
# Query service stats via HTTP API (if implemented)
curl http://localhost:8000/stats
```

### Log Monitoring

```bash
# Follow logs in real-time
tail -f logs/output_service.log | grep -E "(ERROR|WARNING|delivered)"
```

## Next Steps

1. **Read Full Documentation**: See `docs/OUTPUT_SERVICE_ARCHITECTURE.md`
2. **Run Tests**: Ensure all tests pass: `pytest tests/ -v`
3. **Deploy Service**: Use Docker or Kubernetes manifests
4. **Monitor**: Set up alerts for delivery failures
5. **Extend**: Add custom sinks if needed

## Support

- **Issues**: Check logs in `logs/output_service.log`
- **Testing**: Run full test suite: `pytest tests/ -v`
- **Documentation**: See `docs/OUTPUT_SERVICE_ARCHITECTURE.md`
- **Debugging**: Enable DEBUG logging in config

## License

MIT License - See LICENSE file
