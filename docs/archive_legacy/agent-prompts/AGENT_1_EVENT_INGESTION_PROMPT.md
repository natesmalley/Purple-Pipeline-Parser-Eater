# Agent 1: Multi-Source Event Ingestion Layer

**Mission**: Build comprehensive event ingestion system supporting 6 different source types, feeding into a unified message bus for downstream processing.

**Timeline**: 3-4 weeks
**Priority**: Critical Path (blocks Agent 2)
**Deliverables**: 6 event source adapters + unified ingestion pipeline

---

## Context: Current System State

### What Already Exists
You're working in the Purple Pipeline Parser Eater (PPPE) codebase located at:
```
C:\Users\hexideciml\Documents\GitHub\Purple-Pipline-Parser-Eater\
```

**Parser Conversion Pipeline**: ✅ Complete (88%)
- Scanner → Analyzer → LuaGenerator → Dataplane Validator → Deploy
- Located in `orchestrator.py` (881 lines, phases 1-5)
- Generates transform.lua for each parser

**Message Bus Infrastructure**: ✅ Complete
- File: `components/message_bus_adapter.py` (183 lines)
- Supports: Kafka, Redis Streams, Memory (for testing)
- Factory pattern: `create_bus_adapter(config)`

**Dataplane Validator**: ✅ Complete
- File: `components/dataplane_validator.py` (130 lines)
- Validates Lua code with actual binary execution

**What's Missing**: Event ingestion from multiple sources

### Current Architecture Gap

```
[NO EVENT SOURCES] ❌
    ↓
Message Bus (Kafka) ✅ Ready
    ↓
Transform Worker ✅ Ready (Agent 2 will activate)
    ↓
Observo.ai Output ✅ Ready (Agent 3 will wire)
```

---

## Your Mission: Build 6 Event Source Adapters

### Required Event Sources

1. **Kafka Consumer** (highest priority)
   - Consume from existing Kafka topics
   - Support multiple topics per source
   - Configurable consumer groups

2. **SCOL API Poller** (leverages Dataplane)
   - REST API polling with Lua scripts
   - Checkpoint management (SQLite)
   - OAuth/Bearer token auth

3. **S3 Event Processor**
   - S3 bucket event notifications
   - File-based event ingestion
   - Support JSONL, JSON, CSV formats

4. **Azure Event Hub Consumer**
   - Azure Event Hubs integration
   - Azure Blob Storage fallback
   - Azure AD authentication

5. **GCP Pub/Sub Consumer**
   - Google Cloud Pub/Sub subscriptions
   - GCS bucket monitoring
   - Service account auth

6. **Syslog HEC Receiver**
   - HTTP Event Collector endpoint
   - Splunk HEC protocol compatible
   - Token-based authentication

---

## Architecture Design

### Unified Event Flow

```
┌─────────────────────────────────────────────────────────┐
│              EVENT INGESTION LAYER (YOUR WORK)          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Kafka      │  │  SCOL API    │  │     S3       │ │
│  │  Consumer    │  │   Poller     │  │  Processor   │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                 │                 │           │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐ │
│  │   Azure      │  │     GCP      │  │   Syslog     │ │
│  │ Event Hubs   │  │   Pub/Sub    │  │     HEC      │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                 │                 │           │
│         └─────────────────┼─────────────────┘           │
│                           │                              │
│                  ┌────────▼────────┐                    │
│                  │  Event Normalizer│                    │
│                  │  (common format) │                    │
│                  └────────┬────────┘                    │
└───────────────────────────┼─────────────────────────────┘
                            │
                   ┌────────▼────────┐
                   │  Message Bus    │
                   │  (Kafka topic:  │
                   │ raw-events)     │
                   └─────────────────┘
                            │
                            ▼
                   [Agent 2 processes]
```

### Event Normalization Format

All events must be normalized to this structure:

```json
{
  "_metadata": {
    "source_type": "kafka|scol|s3|azure|gcp|syslog",
    "source_id": "unique-source-identifier",
    "ingestion_time": "2025-11-07T12:00:00Z",
    "parser_id": "netskope_dlp",
    "original_format": "json|syslog|csv"
  },
  "log": {
    // Original event data (untransformed)
    "alert_type": "DLP",
    "user": "john@example.com",
    "severity": "High",
    // ... all original fields
  }
}
```

---

## Implementation Requirements

### File Structure to Create

```
components/
├── event_sources/
│   ├── __init__.py
│   ├── base_source.py              # Abstract base class
│   ├── kafka_source.py              # Kafka consumer
│   ├── scol_source.py               # SCOL API poller
│   ├── s3_source.py                 # S3 processor
│   ├── azure_source.py              # Azure Event Hubs
│   ├── gcp_source.py                # GCP Pub/Sub
│   └── syslog_hec_source.py         # Syslog HEC receiver
│
services/
├── event_ingest_manager.py          # Orchestrates all sources
└── event_normalizer.py               # Normalizes to common format
│
tests/
├── test_event_sources.py             # Unit tests for each source
├── test_event_normalizer.py          # Normalization tests
└── test_event_ingest_manager.py      # Integration tests
│
config/
└── event_sources.yaml                # Configuration for all sources
```

---

## Detailed Requirements by Source

### 1. Kafka Source (`kafka_source.py`)

**Purpose**: Consume events from existing Kafka topics

**Requirements**:
```python
class KafkaEventSource(BaseEventSource):
    """
    Kafka consumer for event ingestion

    Features:
    - Multi-topic subscription
    - Consumer group management
    - Offset tracking
    - Batch consumption
    - Auto-commit or manual commit
    """

    def __init__(self, config: Dict[str, Any]):
        self.bootstrap_servers = config['bootstrap_servers']
        self.topics = config['topics']  # List of topics
        self.consumer_group = config.get('consumer_group', 'pppe-ingest')
        self.batch_size = config.get('batch_size', 100)

    async def start(self):
        """Start consuming from Kafka"""
        pass

    async def consume_batch(self) -> List[Dict]:
        """Consume batch of events"""
        pass

    async def stop(self):
        """Graceful shutdown"""
        pass
```

**Configuration Example**:
```yaml
kafka:
  enabled: true
  bootstrap_servers: "localhost:9092"
  topics:
    - "security-events"
    - "netskope-alerts"
    - "m365-audit-logs"
  consumer_group: "pppe-event-ingestion"
  batch_size: 100
  auto_offset_reset: "earliest"
  enable_auto_commit: true
```

**Dependencies**:
- `aiokafka` (already in requirements)
- Existing `message_bus_adapter.py` for publishing

---

### 2. SCOL API Source (`scol_source.py`)

**Purpose**: Poll REST APIs using Lua-based fetch logic (leverages Dataplane SCOL design)

**Requirements**:
```python
class SCOLAPISource(BaseEventSource):
    """
    SCOL (Security Collection) API poller

    Based on Dataplane SCOL design:
    - Lua scripts define fetch logic
    - Checkpoint management for incremental polling
    - Configurable intervals
    - Retry with exponential backoff

    See: external-dataplane-docs/README.md for SCOL reference
    """

    def __init__(self, config: Dict[str, Any]):
        self.api_url = config['api_url']
        self.auth_token = config['auth_token']
        self.poll_interval = config.get('poll_interval_secs', 60)
        self.checkpoint_db = config.get('checkpoint_db', 'checkpoints.db')

    async def poll_api(self) -> List[Dict]:
        """
        Poll API endpoint

        Steps:
        1. Read checkpoint (last fetch timestamp)
        2. Calculate time window
        3. HTTP GET with query params
        4. Parse JSON response
        5. Extract events
        6. Update checkpoint
        """
        pass

    async def start(self):
        """Start periodic polling"""
        pass
```

**Configuration Example**:
```yaml
scol_api:
  enabled: true
  sources:
    - name: "netskope_alerts"
      api_url: "https://tenant.goskope.com/api/v2/events/data/alert"
      auth_token: "${NETSKOPE_API_TOKEN}"
      poll_interval_secs: 60
      checkpoint_key: "netskope_last_timestamp"
      query_params:
        type: "policy,DLP,malware"

    - name: "m365_audit"
      api_url: "https://manage.office.com/api/v1.0/activity/content"
      auth_token: "${M365_API_TOKEN}"
      poll_interval_secs: 300
```

**Checkpoint Management**:
```python
# Use SQLite for persistence
import sqlite3

class CheckpointStore:
    def get_checkpoint(self, key: str) -> Optional[str]:
        """Retrieve last checkpoint value"""
        pass

    def set_checkpoint(self, key: str, value: str):
        """Save checkpoint value"""
        pass
```

---

### 3. S3 Event Processor (`s3_source.py`)

**Purpose**: Process events from S3 buckets (file-based ingestion)

**Requirements**:
```python
class S3EventSource(BaseEventSource):
    """
    S3 bucket event processor

    Features:
    - S3 event notifications (via SQS)
    - Direct bucket scanning
    - Support multiple formats: JSONL, JSON, CSV
    - Compression support: gzip, bzip2
    - Checkpointing (track processed files)
    """

    def __init__(self, config: Dict[str, Any]):
        self.bucket_name = config['bucket']
        self.prefix = config.get('prefix', '')
        self.format = config.get('format', 'jsonl')
        self.sqs_queue = config.get('sqs_queue')  # Optional

    async def process_file(self, s3_key: str) -> List[Dict]:
        """
        Download and process S3 file

        Steps:
        1. Download file
        2. Decompress if needed
        3. Parse based on format (JSONL/JSON/CSV)
        4. Extract events
        5. Mark as processed
        """
        pass

    async def listen_sqs_notifications(self):
        """Listen for S3 event notifications via SQS"""
        pass

    async def scan_bucket(self):
        """Scan bucket for new files (fallback)"""
        pass
```

**Configuration Example**:
```yaml
s3:
  enabled: true
  buckets:
    - name: "security-logs-bucket"
      prefix: "netskope/alerts/"
      format: "jsonl"
      compression: "gzip"
      sqs_queue: "s3-event-notifications"
      region: "us-east-1"
      parser_id: "netskope_dlp"

    - name: "cloudtrail-logs"
      prefix: "AWSLogs/"
      format: "json"
      parser_id: "aws_cloudtrail"
```

**File Format Handling**:
```python
class FileParser:
    @staticmethod
    def parse_jsonl(content: str) -> List[Dict]:
        """Parse JSON Lines format"""
        return [json.loads(line) for line in content.splitlines()]

    @staticmethod
    def parse_json(content: str) -> List[Dict]:
        """Parse JSON array"""
        data = json.loads(content)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # Look for common array keys
            for key in ['events', 'records', 'logs', 'data']:
                if key in data:
                    return data[key]
        return [data]

    @staticmethod
    def parse_csv(content: str) -> List[Dict]:
        """Parse CSV format"""
        import csv
        reader = csv.DictReader(content.splitlines())
        return list(reader)
```

---

### 4. Azure Event Hubs Source (`azure_source.py`)

**Purpose**: Consume events from Azure Event Hubs

**Requirements**:
```python
class AzureEventHubsSource(BaseEventSource):
    """
    Azure Event Hubs consumer

    Features:
    - Multiple Event Hub consumers
    - Checkpoint storage in Azure Blob Storage
    - Consumer groups
    - Partition management
    """

    def __init__(self, config: Dict[str, Any]):
        self.connection_string = config['connection_string']
        self.event_hub_name = config['event_hub_name']
        self.consumer_group = config.get('consumer_group', '$Default')
        self.checkpoint_store_connection = config['checkpoint_store_connection']

    async def start(self):
        """Start consuming from Event Hub"""
        from azure.eventhub.aio import EventHubConsumerClient
        from azure.eventhub.extensions.checkpointstoreblobaio import BlobCheckpointStore

        checkpoint_store = BlobCheckpointStore.from_connection_string(
            self.checkpoint_store_connection,
            container_name="eventhub-checkpoints"
        )

        client = EventHubConsumerClient.from_connection_string(
            self.connection_string,
            consumer_group=self.consumer_group,
            eventhub_name=self.event_hub_name,
            checkpoint_store=checkpoint_store
        )

        # Start receiving
        pass
```

**Configuration Example**:
```yaml
azure:
  enabled: true
  event_hubs:
    - name: "security-events-hub"
      connection_string: "${AZURE_EVENTHUB_CONNECTION}"
      event_hub_name: "security-events"
      consumer_group: "pppe-consumer"
      checkpoint_store_connection: "${AZURE_STORAGE_CONNECTION}"
      parser_id: "azure_sentinel_alerts"
```

**Dependencies to Add**:
```txt
azure-eventhub>=5.11.0
azure-eventhub-checkpointstoreblob-aio>=1.1.4
azure-storage-blob>=12.14.1
```

---

### 5. GCP Pub/Sub Source (`gcp_source.py`)

**Purpose**: Consume events from Google Cloud Pub/Sub

**Requirements**:
```python
class GCPPubSubSource(BaseEventSource):
    """
    Google Cloud Pub/Sub consumer

    Features:
    - Multiple subscription consumers
    - Acknowledgment handling
    - Service account authentication
    - Flow control (max messages)
    """

    def __init__(self, config: Dict[str, Any]):
        self.project_id = config['project_id']
        self.subscription_id = config['subscription_id']
        self.credentials_file = config.get('credentials_file')
        self.max_messages = config.get('max_messages', 100)

    async def start(self):
        """Start consuming from Pub/Sub"""
        from google.cloud import pubsub_v1

        subscriber = pubsub_v1.SubscriberClient.from_service_account_file(
            self.credentials_file
        )

        subscription_path = subscriber.subscription_path(
            self.project_id,
            self.subscription_id
        )

        # Start receiving with callback
        pass

    def callback(self, message):
        """Handle received message"""
        data = json.loads(message.data.decode('utf-8'))
        # Process event
        message.ack()
```

**Configuration Example**:
```yaml
gcp:
  enabled: true
  subscriptions:
    - name: "gcp-security-logs"
      project_id: "my-project-123"
      subscription_id: "security-events-sub"
      credentials_file: "/path/to/service-account.json"
      parser_id: "gcp_audit_logs"
      max_messages: 100
```

**Dependencies to Add**:
```txt
google-cloud-pubsub>=2.13.0
```

---

### 6. Syslog HEC Receiver (`syslog_hec_source.py`)

**Purpose**: HTTP Event Collector endpoint (Splunk HEC protocol compatible)

**Requirements**:
```python
class SyslogHECSource(BaseEventSource):
    """
    Syslog HTTP Event Collector

    Features:
    - HTTP POST endpoint (/services/collector/event)
    - Token-based authentication
    - Splunk HEC protocol compatible
    - Batch event support
    - JSON and raw format support
    """

    def __init__(self, config: Dict[str, Any]):
        self.host = config.get('host', '0.0.0.0')
        self.port = config.get('port', 8088)
        self.auth_tokens = config['auth_tokens']  # List of valid tokens
        self.ssl_enabled = config.get('ssl_enabled', False)

    async def start(self):
        """Start HTTP server"""
        from aiohttp import web

        app = web.Application()
        app.router.add_post('/services/collector/event', self.handle_event)
        app.router.add_post('/services/collector/raw', self.handle_raw)

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, self.host, self.port)
        await site.start()

    async def handle_event(self, request):
        """
        Handle HEC event POST

        Expected format:
        {
          "event": {...},
          "time": 1234567890,
          "source": "my-source",
          "sourcetype": "json"
        }
        """
        # Verify auth token
        auth_token = request.headers.get('Authorization', '').replace('Splunk ', '')
        if auth_token not in self.auth_tokens:
            return web.json_response({"error": "Invalid token"}, status=401)

        # Parse event
        data = await request.json()
        event = data.get('event', data)

        # Normalize and publish
        pass
```

**Configuration Example**:
```yaml
syslog_hec:
  enabled: true
  host: "0.0.0.0"
  port: 8088
  ssl_enabled: false
  auth_tokens:
    - "${HEC_TOKEN_1}"
    - "${HEC_TOKEN_2}"
  default_parser_id: "generic_syslog"

  # Route specific sources to parsers
  source_routing:
    "netskope": "netskope_dlp"
    "palo-alto": "palo_alto_firewall"
```

**Dependencies to Add**:
```txt
aiohttp>=3.8.0
```

---

## Event Normalizer (`event_normalizer.py`)

**Purpose**: Normalize all events to common format before publishing

```python
class EventNormalizer:
    """
    Normalizes events from all sources to unified format

    Output format:
    {
      "_metadata": {
        "source_type": "kafka|scol|s3|azure|gcp|syslog",
        "source_id": "unique-identifier",
        "ingestion_time": "ISO-8601",
        "parser_id": "parser-to-use",
        "original_format": "json|syslog|csv"
      },
      "log": {
        // Original event (untouched)
      }
    }
    """

    @staticmethod
    def normalize(
        event: Dict[str, Any],
        source_type: str,
        source_id: str,
        parser_id: str,
        original_format: str = "json"
    ) -> Dict[str, Any]:
        """Normalize event to common format"""
        return {
            "_metadata": {
                "source_type": source_type,
                "source_id": source_id,
                "ingestion_time": datetime.now().isoformat(),
                "parser_id": parser_id,
                "original_format": original_format
            },
            "log": event
        }
```

---

## Event Ingest Manager (`event_ingest_manager.py`)

**Purpose**: Orchestrate all event sources and publish to message bus

```python
class EventIngestManager:
    """
    Manages all event sources and coordinates ingestion

    Features:
    - Start/stop all sources
    - Route events to message bus
    - Monitor ingestion metrics
    - Handle source failures gracefully
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.sources: List[BaseEventSource] = []
        self.message_bus = None
        self.normalizer = EventNormalizer()
        self.metrics = IngestionMetrics()

    async def initialize(self):
        """Initialize all enabled sources"""
        # Create message bus adapter
        from components.message_bus_adapter import create_bus_adapter
        self.message_bus = create_bus_adapter(self.config)

        # Initialize each source
        if self.config.get('kafka', {}).get('enabled'):
            self.sources.append(KafkaEventSource(self.config['kafka']))

        if self.config.get('scol_api', {}).get('enabled'):
            for source_config in self.config['scol_api']['sources']:
                self.sources.append(SCOLAPISource(source_config))

        # ... initialize other sources

    async def start(self):
        """Start all sources"""
        tasks = [source.start() for source in self.sources]
        await asyncio.gather(*tasks)

    async def process_event(self, event: Dict, source_type: str, source_id: str, parser_id: str):
        """Normalize and publish event"""
        normalized = self.normalizer.normalize(
            event,
            source_type=source_type,
            source_id=source_id,
            parser_id=parser_id
        )

        # Publish to message bus
        await self.message_bus.publish("raw-security-events", normalized)

        # Update metrics
        self.metrics.record_event(source_type, source_id)

    async def stop(self):
        """Graceful shutdown"""
        tasks = [source.stop() for source in self.sources]
        await asyncio.gather(*tasks)
        await self.message_bus.close()
```

---

## Configuration File (`config/event_sources.yaml`)

Create comprehensive configuration:

```yaml
# Event Ingestion Configuration
# Loaded by EventIngestManager

# Message Bus (where normalized events are published)
message_bus:
  type: "kafka"
  kafka:
    bootstrap_servers: "localhost:9092"
    output_topic: "raw-security-events"

# Kafka Source
kafka:
  enabled: true
  bootstrap_servers: "localhost:9092"
  topics:
    - "security-events"
    - "netskope-alerts"
  consumer_group: "pppe-event-ingestion"
  batch_size: 100

# SCOL API Sources
scol_api:
  enabled: true
  checkpoint_db: "data/scol_checkpoints.db"
  sources:
    - name: "netskope_alerts"
      api_url: "https://tenant.goskope.com/api/v2/events/data/alert"
      auth_token: "${NETSKOPE_API_TOKEN}"
      poll_interval_secs: 60
      parser_id: "netskope_dlp"

    - name: "m365_audit"
      api_url: "https://manage.office.com/api/v1.0/activity/content"
      auth_token: "${M365_API_TOKEN}"
      poll_interval_secs: 300
      parser_id: "m365_audit_logs"

# S3 Sources
s3:
  enabled: true
  buckets:
    - name: "security-logs-bucket"
      prefix: "netskope/alerts/"
      format: "jsonl"
      compression: "gzip"
      region: "us-east-1"
      parser_id: "netskope_dlp"

# Azure Event Hubs
azure:
  enabled: true
  event_hubs:
    - name: "security-events-hub"
      connection_string: "${AZURE_EVENTHUB_CONNECTION}"
      event_hub_name: "security-events"
      consumer_group: "pppe-consumer"
      checkpoint_store_connection: "${AZURE_STORAGE_CONNECTION}"
      parser_id: "azure_sentinel_alerts"

# GCP Pub/Sub
gcp:
  enabled: true
  subscriptions:
    - name: "gcp-security-logs"
      project_id: "my-project-123"
      subscription_id: "security-events-sub"
      credentials_file: "${GCP_CREDENTIALS_FILE}"
      parser_id: "gcp_audit_logs"

# Syslog HEC
syslog_hec:
  enabled: true
  host: "0.0.0.0"
  port: 8088
  ssl_enabled: false
  auth_tokens:
    - "${HEC_TOKEN}"
  source_routing:
    "netskope": "netskope_dlp"
    "palo-alto": "palo_alto_firewall"
```

---

## Testing Requirements

### Unit Tests (`tests/test_event_sources.py`)

```python
import pytest
from components.event_sources.kafka_source import KafkaEventSource
from components.event_sources.scol_source import SCOLAPISource
# ... import all sources

@pytest.mark.asyncio
async def test_kafka_source_consumes_events():
    """Test Kafka source can consume events"""
    config = {
        'bootstrap_servers': 'localhost:9092',
        'topics': ['test-topic'],
        'consumer_group': 'test-group'
    }

    source = KafkaEventSource(config)
    # Test consumption
    pass

@pytest.mark.asyncio
async def test_scol_source_polls_api():
    """Test SCOL source polls API correctly"""
    # Mock HTTP responses
    # Test checkpoint management
    pass

# Similar tests for each source
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_event_ingest_manager_routes_to_bus():
    """Test manager routes events from all sources to message bus"""
    config = load_test_config()
    manager = EventIngestManager(config)

    await manager.initialize()
    await manager.start()

    # Produce test events to each source
    # Verify they appear in message bus

    await manager.stop()
```

---

## Integration Points with Other Agents

### Agent 2 (Transform Pipeline) Dependencies

**What Agent 2 Needs from You**:
```python
# Message bus topic with normalized events
topic = "raw-security-events"

# Event format:
{
  "_metadata": {
    "source_type": "kafka",
    "parser_id": "netskope_dlp",  # Which transform to use
    "ingestion_time": "2025-11-07T12:00:00Z"
  },
  "log": {
    // Raw event data
  }
}
```

**How to Test Integration**:
1. Start your event ingest manager
2. Produce test events
3. Verify events appear in `raw-security-events` topic
4. Agent 2 will consume from this topic

---

## Success Criteria

### Phase 1 (Week 1-2): Core Sources
- [ ] Kafka source consuming events
- [ ] SCOL API source polling successfully
- [ ] S3 source processing files
- [ ] Event normalizer working
- [ ] EventIngestManager orchestrating sources
- [ ] All events published to message bus

### Phase 2 (Week 3): Cloud Sources
- [ ] Azure Event Hubs consuming
- [ ] GCP Pub/Sub consuming
- [ ] Cloud authentication working

### Phase 3 (Week 4): Syslog HEC & Testing
- [ ] Syslog HEC receiver operational
- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] Performance: 10K events/sec throughput

---

## Dependencies to Install

Add to `requirements.txt`:
```txt
# Existing (already present)
aiokafka>=0.8.0

# New for your work
aiohttp>=3.8.0
azure-eventhub>=5.11.0
azure-eventhub-checkpointstoreblob-aio>=1.1.4
azure-storage-blob>=12.14.1
google-cloud-pubsub>=2.13.0
boto3>=1.26.0  # For S3
```

---

## Deliverables Checklist

- [ ] `components/event_sources/` directory with 7 Python files
- [ ] `services/event_ingest_manager.py` (orchestrator)
- [ ] `services/event_normalizer.py` (normalization)
- [ ] `config/event_sources.yaml` (configuration)
- [ ] `tests/test_event_sources.py` (unit tests)
- [ ] `tests/test_event_ingest_manager.py` (integration tests)
- [ ] `docs/Event_Ingestion_Architecture.md` (documentation)
- [ ] `scripts/start_event_ingestion.py` (entrypoint)
- [ ] Updated `requirements.txt`
- [ ] Docker Compose service definition

---

## Example Entrypoint Script

Create `scripts/start_event_ingestion.py`:

```python
#!/usr/bin/env python3
"""
Event Ingestion Service Entrypoint
Starts all enabled event sources
"""
import asyncio
import logging
import yaml
from pathlib import Path

from services.event_ingest_manager import EventIngestManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Load configuration
    config_path = Path("config/event_sources.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Create manager
    manager = EventIngestManager(config)

    # Initialize
    await manager.initialize()
    logger.info("Event ingestion manager initialized")

    # Start
    await manager.start()
    logger.info("All event sources started")

    # Run forever
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await manager.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Questions?

If you need clarification on:
- Message bus integration
- Event format expectations
- Checkpoint management
- Integration with Agent 2/3

Refer to these existing files in the codebase:
- `components/message_bus_adapter.py` - Message bus interface
- `DATAPLANE_INTEGRATION_STATUS.md` - Architecture overview
- `external-dataplane-docs/README.md` - SCOL reference

**Start with Kafka and SCOL sources first** - these are highest priority and will unblock Agent 2.

Good luck! 🚀
