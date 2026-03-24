# 🚀 Event Processing Pipeline - Quick Start Guide

**Status**: ✅ Complete and Ready for Deployment
**Last Updated**: 2025-11-07

---

## Overview

The Purple Pipeline Parser Eater now includes a complete event processing pipeline with three integrated agents:

```
┌─────────────────────────────────────────────────────────────┐
│                    EVENT PROCESSING PIPELINE                │
└─────────────────────────────────────────────────────────────┘

Agent 1: Event Ingestion (6 sources)
    ├─ Kafka Consumer
    ├─ SCOL API Poller
    ├─ S3 Event Processor
    ├─ Azure Event Hubs
    ├─ GCP Pub/Sub
    └─ Syslog HEC Receiver
         ↓
    raw-security-events topic
         ↓
Agent 2: Transform Pipeline
    ├─ Manifest-based routing
    ├─ Lua transformation
    ├─ Canary A/B testing
    └─ Performance metrics
         ↓
    ocsf-events topic
         ↓
Agent 3: Output Delivery
    ├─ OCSF validation
    ├─ Observo.ai ingestion
    ├─ S3 archival
    └─ Retry & error handling
         ↓
    Production systems
```

---

## 🎯 What You Can Do Now

1. **Ingest events from 6 different sources** simultaneously
2. **Transform events using Lua parsers** with automatic routing
3. **Deliver to Observo.ai and S3** with guaranteed delivery
4. **Test with canary deployments** before full rollout
5. **Monitor performance** with built-in metrics

---

## ⚡ Quick Start

### Prerequisites

```bash
# Install Python dependencies
pip install aiokafka httpx boto3 aiohttp lupa pyyaml

# Optional (for specific sources)
pip install azure-eventhub google-cloud-pubsub
```

### 1. Configure Your Environment

```bash
# Set required environment variables
export OBSERVO_API_TOKEN="your-observo-token"
export NETSKOPE_API_TOKEN="your-netskope-token"  # if using SCOL
export AWS_ACCESS_KEY_ID="your-aws-key"          # if using S3
export AWS_SECRET_ACCESS_KEY="your-aws-secret"
```

### 2. Edit Configuration Files

**Enable event sources** in [config/event_sources.yaml](config/event_sources.yaml):

```yaml
# Example: Enable Kafka source
kafka:
  enabled: true  # ← Change to true
  bootstrap_servers: "localhost:9092"
  topics:
    - "security-events"
  parser_id: "generic_kafka_event"
```

**Configure output sinks** in [config/output_service.yaml](config/output_service.yaml):

```yaml
sinks:
  observo:
    enabled: true  # ← Change to true
    base_url: "https://api.observo.ai"
    api_token: "${OBSERVO_API_TOKEN}"
```

### 3. Start the Pipeline

```bash
# Terminal 1: Start event ingestion
python -m services.event_ingest_manager

# Terminal 2: Start transform pipeline
python -m services.runtime_service

# Terminal 3: Start output delivery
python -m services.output_service
```

### 4. Verify It's Working

```bash
# Check logs
tail -f logs/*.log

# Monitor metrics (if web UI running)
curl http://localhost:5000/api/runtime/status
```

---

## 📝 Configuration Files

| File | Purpose | Location |
|------|---------|----------|
| Event sources | Configure Kafka, SCOL, S3, Azure, GCP, Syslog | [config/event_sources.yaml](config/event_sources.yaml) |
| Transform pipeline | Lua execution, canary routing | [config/runtime_service.yaml](config/runtime_service.yaml) |
| Output delivery | Observo.ai, S3, validation | [config/output_service.yaml](config/output_service.yaml) |

---

## 🔧 Common Configurations

### Use Case 1: Kafka → Lua Transform → Observo.ai

```yaml
# config/event_sources.yaml
kafka:
  enabled: true
  bootstrap_servers: "localhost:9092"
  topics: ["security-events"]
  parser_id: "netskope_dlp"

# config/output_service.yaml
sinks:
  observo:
    enabled: true
    base_url: "https://api.observo.ai"
    api_token: "${OBSERVO_API_TOKEN}"
```

### Use Case 2: SCOL API Polling → S3 Archive

```yaml
# config/event_sources.yaml
scol_api:
  enabled: true
  sources:
    - name: "netskope_alerts"
      api_url: "https://tenant.goskope.com/api/v2/events/data/alert"
      auth_token: "${NETSKOPE_API_TOKEN}"
      parser_id: "netskope_dlp"

# config/output_service.yaml
sinks:
  s3_archive:
    enabled: true
    bucket: "security-events-archive"
    prefix: "purple-pipeline"
```

### Use Case 3: Multiple Sources → Canary Testing → Dual Output

```yaml
# config/event_sources.yaml
kafka:
  enabled: true
  # ... kafka config

scol_api:
  enabled: true
  # ... SCOL config

# config/runtime_service.yaml
canary:
  enabled: true
  promotion_threshold: 1000
  error_tolerance: 0.01

# config/output_service.yaml
sinks:
  observo:
    enabled: true
  s3_archive:
    enabled: true
```

---

## 🎮 Operational Commands

### Check Pipeline Status

```bash
# View agent 1 metrics
curl http://localhost:5000/api/ingestion/metrics

# View agent 2 runtime status
curl http://localhost:5000/api/runtime/status

# View agent 3 delivery stats
curl http://localhost:5000/api/output/statistics
```

### Reload a Parser

```bash
# Request runtime reload
curl -X POST http://localhost:5000/api/runtime/reload/netskope_dlp

# The transform worker will reload the manifest on next event
```

### Promote a Canary

```bash
# Request canary promotion
curl -X POST http://localhost:5000/api/runtime/canary/netskope_dlp/promote

# Canary will be promoted once promotion threshold is met
```

### View Logs

```bash
# All logs
tail -f logs/*.log

# Specific component
tail -f logs/runtime_service.log
tail -f logs/output_service.log

# Follow errors only
grep ERROR logs/*.log | tail -f
```

---

## 🔍 Verification & Testing

### Test Event Ingestion

```bash
# Publish test event to Kafka
echo '{"alert_type":"DLP","user":"test@example.com"}' | \
  kafka-console-producer --broker-list localhost:9092 \
  --topic security-events

# Check logs for event processing
grep "Normalized event" logs/event_ingest_manager.log
```

### Test Transform Pipeline

```bash
# Verify Lua execution
grep "Transformed event" logs/runtime_service.log

# Check for errors
grep "Transform failed" logs/runtime_service.log
```

### Test Output Delivery

```bash
# Verify Observo.ai delivery
grep "Observo.ai ingestion" logs/output_service.log

# Check S3 uploads
grep "Uploaded.*events to s3" logs/output_service.log
```

---

## 📊 Monitoring

### Key Metrics to Watch

**Agent 1 (Ingestion)**:
- `events_processed` - Total events ingested
- `events_by_source` - Per-source counts
- `errors` - Ingestion failures

**Agent 2 (Transform)**:
- `total_events` - Events processed
- `successful_transforms` - Successful Lua executions
- `failed_transforms` - Transform failures
- `success_rate` - Transform success percentage

**Agent 3 (Output)**:
- `delivery_success` - Successfully delivered events
- `delivery_failed` - Failed deliveries
- `by_sink` - Per-sink statistics

### Dashboard Integration

If using the web UI:

```bash
# Open dashboard
http://localhost:5000/dashboard

# View parser-specific metrics
http://localhost:5000/parsers/netskope_dlp
```

---

## 🐛 Troubleshooting

### Issue: Events Not Being Ingested

```bash
# Check source is enabled
grep "enabled: true" config/event_sources.yaml

# Check source started
grep "source initialized" logs/*.log

# Verify connectivity
# For Kafka:
kafka-topics --bootstrap-server localhost:9092 --list

# For SCOL API:
curl -H "Authorization: Bearer $NETSKOPE_API_TOKEN" \
  https://tenant.goskope.com/api/v2/events/data/alert
```

### Issue: Transform Failures

```bash
# Check manifest exists
ls output/*/manifest.json

# Verify Lua code
cat output/netskope_dlp/transform.lua

# Check executor type
grep "executor:" config/runtime_service.yaml

# Test Lua manually
lua output/netskope_dlp/transform.lua
```

### Issue: Output Delivery Failing

```bash
# Check Observo.ai connectivity
curl -H "Authorization: Bearer $OBSERVO_API_TOKEN" \
  https://api.observo.ai/api/v1/health

# Verify S3 credentials
aws s3 ls s3://purple-pipeline-events/

# Check validation errors
grep "validation failed" logs/output_service.log

# Review retry attempts
grep "Retrying in" logs/output_service.log
```

---

## 🚨 Error Handling

### Dead Letter Queues (DLQ)

Failed events are automatically sent to DLQ topics:

```
transform-errors    - Transform failures (Agent 2)
output-failures     - Delivery failures (Agent 3)
validation-errors   - OCSF validation failures (Agent 3)
```

To process DLQ messages:

```bash
# View transform errors
kafka-console-consumer --bootstrap-server localhost:9092 \
  --topic transform-errors --from-beginning

# Review error details
kafka-console-consumer --bootstrap-server localhost:9092 \
  --topic transform-errors --from-beginning | jq '._error'
```

### Retry Behavior

- **Transform failures**: Sent to DLQ immediately (no retries)
- **Output delivery failures**: 5 retries with exponential backoff
  - Attempt 1: 2 seconds
  - Attempt 2: 4 seconds
  - Attempt 3: 8 seconds
  - Attempt 4: 16 seconds
  - Attempt 5: 32 seconds (max 60s)

---

## 📚 Additional Resources

**Detailed Documentation**:
- [AGENT_IMPLEMENTATION_VERIFICATION.md](AGENT_IMPLEMENTATION_VERIFICATION.md) - Complete verification report
- [AGENT_1_EVENT_INGESTION_PROMPT.md](AGENT_1_EVENT_INGESTION_PROMPT.md) - Agent 1 architecture
- [AGENT_2_TRANSFORM_PIPELINE_PROMPT.md](AGENT_2_TRANSFORM_PIPELINE_PROMPT.md) - Agent 2 architecture
- [AGENT_3_OBSERVO_OUTPUT_PROMPT.md](AGENT_3_OBSERVO_OUTPUT_PROMPT.md) - Agent 3 architecture

**Architecture**:
- [docs/Hybrid_Architecture_Plan.md](docs/Hybrid_Architecture_Plan.md) - Overall architecture
- [INVESTIGATION_SUMMARY.md](INVESTIGATION_SUMMARY.md) - Current system status

**Code Reference**:
- Agent 1: [services/event_ingest_manager.py](services/event_ingest_manager.py)
- Agent 2: [services/runtime_service.py](services/runtime_service.py)
- Agent 3: [services/output_service.py](services/output_service.py)

---

## 🎯 Performance Tips

1. **Scale horizontally**: Run multiple instances of each agent
2. **Tune batch sizes**: Increase for higher throughput
3. **Use memory bus for testing**: Faster than Kafka locally
4. **Enable Lua caching**: Already enabled by default
5. **Partition Kafka topics**: More partitions = more parallelism
6. **Monitor DLQ sizes**: High DLQ traffic indicates issues

---

## 💡 Best Practices

1. **Start with one source**: Enable one event source at a time
2. **Test with memory bus**: Use `type: memory` for local development
3. **Monitor metrics**: Watch success rates and latencies
4. **Use canary routing**: Test new parser versions safely
5. **Archive to S3**: Always enable S3 sink for data retention
6. **Review DLQ regularly**: Fix issues causing repeated failures

---

## 🆘 Getting Help

**Found an issue?**
1. Check logs: `logs/*.log`
2. Review configuration: `config/*.yaml`
3. Verify environment variables are set
4. Check external service connectivity

**Still stuck?**
- Review detailed documentation (links above)
- Check error messages in DLQ topics
- Verify all dependencies are installed
- Ensure infrastructure (Kafka, S3) is running

---

**Quick Start Guide Version**: 1.0
**Last Updated**: 2025-11-07
**Status**: ✅ Production Ready
