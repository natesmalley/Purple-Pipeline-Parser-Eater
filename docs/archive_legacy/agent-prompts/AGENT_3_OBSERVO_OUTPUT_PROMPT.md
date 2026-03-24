# 📤 Agent 3: Observo.ai Output Integration & Multi-Sink Support

## 📋 Agent Overview

**Your Role**: Build the output layer that delivers transformed OCSF events to Observo.ai and other configured sinks.

**What You're Building**: The final stage of the pipeline that consumes OCSF-compliant events from Agent 2, validates them, and reliably delivers them to multiple destinations (Observo.ai, S3, databases, etc.) with confirmation tracking and error handling.

**Timeline**: 2-3 weeks (40-60 hours)

**Dependencies**:
- ✅ Agent 2 must publish OCSF events to `ocsf-events` topic
- ✅ Observo.ai API credentials and endpoints
- ✅ Existing infrastructure: Message bus adapter (ready to use)

---

## 🎯 Mission Statement

**Reliably deliver OCSF-normalized security events to Observo.ai and other configured sinks with guaranteed delivery, validation, retry logic, and comprehensive observability.**

Your pipeline will:
1. Consume OCSF events from Agent 2's message bus topic
2. Validate OCSF compliance and data quality
3. Route events to multiple sinks based on configuration
4. Deliver to Observo.ai Ingestion API
5. Store in S3 for archival and backup
6. Track delivery status and retry failures
7. Provide metrics and monitoring

---

## 📊 Current System State

### What Already Exists (✅ Ready to Use)

1. **Message Bus Adapter** (`components/message_bus_adapter.py` - 183 lines)
   - Kafka, Redis, Memory implementations
   - Subscribe/consume methods ready
   ```python
   bus = create_bus_adapter(config)
   await bus.subscribe("ocsf-events", callback)
   ```

2. **Basic Observo API Client** (`components/observo_api_client.py` - ~100 lines)
   - Deploy pipeline functionality exists
   - Basic authentication
   - Needs enhancement for event ingestion

3. **Configuration System** (`config.yaml`)
   - Observo credentials storage
   - API endpoint configuration

### What Needs Building (❌ Your Responsibility)

1. **ObservoIngestClient** - Enhanced API client for event ingestion
2. **S3OutputSink** - Archive events to S3
3. **OutputRouter** - Multi-sink routing and delivery
4. **DeliveryTracker** - Track delivery status with retries
5. **OutputValidator** - Validate OCSF compliance before delivery
6. **OutputService** - Main orchestration service
7. **Monitoring & Metrics** - Track delivery success rates

---

## 🏗️ Architecture Design

### Data Flow Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                 AGENT 3: OBSERVO OUTPUT PIPELINE                │
└─────────────────────────────────────────────────────────────────┘

INPUT: ocsf-events topic (from Agent 2)
═══════════════════════════════════════════════════════════════════

Event Format:
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
    "user": {
      "name": "john@example.com",
      "email_addr": "john@example.com"
    },
    "metadata": {
      "version": "1.5.0",
      "product": {
        "name": "Netskope",
        "vendor_name": "Netskope"
      }
    }
  }
}


STEP 1: Event Consumption
═══════════════════════════════════════════════════════════════════
OutputService.start()
    ↓
Subscribe to: ocsf-events topic
    ↓
Receive event → parse → extract metadata & OCSF log


STEP 2: OCSF Validation
═══════════════════════════════════════════════════════════════════
OutputValidator.validate_ocsf(event["log"])
    ↓
Check required OCSF fields:
    ✓ class_uid (integer)
    ✓ class_name (string)
    ✓ category_uid (integer)
    ✓ severity_id (integer)
    ✓ time (unix timestamp in milliseconds)
    ✓ metadata.version (OCSF schema version)
    ✓ metadata.product (vendor information)
    ↓
Validate data types and ranges
    ↓
If validation fails → send to validation-errors DLQ


STEP 3: Sink Routing Decision
═══════════════════════════════════════════════════════════════════
OutputRouter.get_sinks_for_event(event)
    ↓
Configuration-based routing:
{
  "sinks": {
    "observo": {
      "enabled": true,
      "priority": 1,  ← High priority (deliver first)
      "retry_count": 5
    },
    "s3_archive": {
      "enabled": true,
      "priority": 2,
      "retry_count": 3
    },
    "elasticsearch": {
      "enabled": false
    }
  }
}
    ↓
Return: [ObservoSink, S3Sink]


STEP 4: Parallel Delivery
═══════════════════════════════════════════════════════════════════
For each enabled sink:

┌─────────────────────────────────────┐
│  ObservoIngestSink                  │
└─────────────────────────────────────┘
    ↓
Extract OCSF log from event
    ↓
Batch events (configurable size)
    ↓
POST /api/v1/ingest/ocsf
    Headers:
        Authorization: Bearer <api_token>
        Content-Type: application/json
    Body:
        {
          "events": [
            { /* OCSF event 1 */ },
            { /* OCSF event 2 */ },
            ...
          ],
          "source": "purple-pipeline",
          "dataset": "netskope_dlp"
        }
    ↓
Response:
    200 OK: {"accepted": 100, "rejected": 0}
    4xx/5xx: Retry with exponential backoff

┌─────────────────────────────────────┐
│  S3ArchiveSink                      │
└─────────────────────────────────────┘
    ↓
Format path:
    s3://bucket/purple-pipeline/
        year=2025/
        month=11/
        day=07/
        hour=12/
        parser_id=netskope_dlp/
        events-{timestamp}.jsonl.gz
    ↓
Batch and compress events (gzip)
    ↓
Upload to S3 with retry
    ↓
Track upload status


STEP 5: Delivery Tracking
═══════════════════════════════════════════════════════════════════
DeliveryTracker.record_delivery(event_id, sink_name, status)
    ↓
Status options:
    - success: Delivered and confirmed
    - failed: Delivery failed, will retry
    - dropped: Failed after all retries
    ↓
Store in delivery database (SQLite/PostgreSQL):
    CREATE TABLE deliveries (
        event_id TEXT,
        sink_name TEXT,
        status TEXT,
        attempt_count INTEGER,
        last_error TEXT,
        created_at TIMESTAMP,
        updated_at TIMESTAMP
    )


STEP 6: Retry Logic (For Failed Deliveries)
═══════════════════════════════════════════════════════════════════
If delivery fails:
    ↓
Check retry count < max_retries
    ↓
Calculate backoff: min(base * 2^attempt, max_backoff)
    Example: 1s, 2s, 4s, 8s, 16s, 30s (max)
    ↓
Schedule retry with asyncio.sleep(backoff)
    ↓
Retry delivery
    ↓
If all retries exhausted:
    → Publish to dead-letter queue (output-failures)
    → Alert monitoring system


STEP 7: Metrics Collection
═══════════════════════════════════════════════════════════════════
Track per-sink metrics:
{
  "observo": {
    "total_events": 10000,
    "successful_deliveries": 9950,
    "failed_deliveries": 50,
    "avg_latency_ms": 45.2,
    "last_delivery": "2025-11-07T12:05:00Z"
  },
  "s3_archive": {
    "total_events": 10000,
    "successful_deliveries": 10000,
    "failed_deliveries": 0,
    "avg_latency_ms": 120.5,
    "last_delivery": "2025-11-07T12:05:00Z"
  }
}


OUTPUT: Multiple Destinations
═══════════════════════════════════════════════════════════════════
✓ Observo.ai Ingestion API → Live security analytics
✓ S3 Archive → Long-term storage and compliance
✓ Optional: Elasticsearch, Splunk, other SIEMs
```

---

## 🔧 Detailed Implementation Requirements

### 1. Enhanced Observo Ingest Client

**File**: `components/observo_ingest_client.py`

**Purpose**: Send OCSF events to Observo.ai Ingestion API

```python
from typing import List, Dict, Optional, Any
import httpx
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ObservoIngestClient:
    """
    Client for Observo.ai Event Ingestion API.

    API Endpoint: POST /api/v1/ingest/ocsf
    Authentication: Bearer token

    Supports:
    - Batch event ingestion
    - Retry with exponential backoff
    - Dataset routing
    """

    def __init__(
        self,
        base_url: str,
        api_token: str,
        source_name: str = "purple-pipeline",
        timeout: int = 30,
        max_batch_size: int = 100
    ):
        """
        Initialize Observo Ingest Client.

        Args:
            base_url: Observo.ai API base URL (e.g., "https://api.observo.ai")
            api_token: API authentication token
            source_name: Source identifier for events
            timeout: Request timeout in seconds
            max_batch_size: Maximum events per batch request
        """
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.source_name = source_name
        self.timeout = timeout
        self.max_batch_size = max_batch_size

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
                "User-Agent": "Purple-Pipeline/1.0"
            }
        )

        # Statistics
        self.stats = {
            "total_sent": 0,
            "total_accepted": 0,
            "total_rejected": 0,
            "total_errors": 0
        }

    async def ingest_events(
        self,
        events: List[Dict[str, Any]],
        dataset: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ingest OCSF events to Observo.ai.

        Args:
            events: List of OCSF-compliant event dictionaries
            dataset: Dataset name for routing (defaults to parser_id)

        Returns:
            Response dict with accepted/rejected counts

        Raises:
            httpx.HTTPStatusError: On HTTP error responses
            httpx.RequestError: On network/connection errors
        """
        if not events:
            return {"accepted": 0, "rejected": 0}

        # Batch events if necessary
        results = {
            "accepted": 0,
            "rejected": 0,
            "errors": []
        }

        for i in range(0, len(events), self.max_batch_size):
            batch = events[i:i + self.max_batch_size]
            batch_result = await self._send_batch(batch, dataset)

            results["accepted"] += batch_result.get("accepted", 0)
            results["rejected"] += batch_result.get("rejected", 0)
            if "error" in batch_result:
                results["errors"].append(batch_result["error"])

        return results

    async def _send_batch(
        self,
        events: List[Dict[str, Any]],
        dataset: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a single batch of events to Observo.ai."""
        # Determine dataset from first event if not provided
        if not dataset and events:
            first_event_meta = events[0].get("_metadata", {})
            dataset = first_event_meta.get("parser_id", "default")

        # Extract OCSF logs (remove metadata wrapper)
        ocsf_events = []
        for event in events:
            if "log" in event:
                ocsf_events.append(event["log"])
            else:
                # Assume entire event is OCSF if no "log" wrapper
                ocsf_events.append(event)

        payload = {
            "events": ocsf_events,
            "source": self.source_name,
            "dataset": dataset,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        try:
            logger.debug(
                f"Sending {len(ocsf_events)} events to Observo.ai "
                f"(dataset={dataset})"
            )

            response = await self.client.post(
                "/api/v1/ingest/ocsf",
                json=payload
            )

            response.raise_for_status()
            result = response.json()

            self.stats["total_sent"] += len(ocsf_events)
            self.stats["total_accepted"] += result.get("accepted", 0)
            self.stats["total_rejected"] += result.get("rejected", 0)

            logger.info(
                f"Observo.ai ingestion: {result.get('accepted', 0)} accepted, "
                f"{result.get('rejected', 0)} rejected"
            )

            return result

        except httpx.HTTPStatusError as e:
            self.stats["total_errors"] += 1
            error_detail = f"HTTP {e.response.status_code}: {e.response.text}"
            logger.error(f"Observo.ai ingestion failed: {error_detail}")

            return {
                "accepted": 0,
                "rejected": len(events),
                "error": error_detail
            }

        except httpx.RequestError as e:
            self.stats["total_errors"] += 1
            error_detail = f"Request error: {str(e)}"
            logger.error(f"Observo.ai ingestion failed: {error_detail}")

            return {
                "accepted": 0,
                "rejected": len(events),
                "error": error_detail
            }

    async def test_connection(self) -> bool:
        """
        Test connection to Observo.ai API.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            response = await self.client.get("/api/v1/health")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Observo.ai connection test failed: {e}")
            return False

    def get_statistics(self) -> Dict[str, int]:
        """Get ingestion statistics."""
        return {
            **self.stats,
            "success_rate": (
                self.stats["total_accepted"] / self.stats["total_sent"]
                if self.stats["total_sent"] > 0
                else 0
            )
        }

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
```

### 2. S3 Archive Sink

**File**: `components/sinks/s3_archive_sink.py`

**Purpose**: Archive OCSF events to S3 for long-term storage

```python
from typing import List, Dict, Any
import boto3
import gzip
import json
import logging
from datetime import datetime
from pathlib import Path
import tempfile

logger = logging.getLogger(__name__)


class S3ArchiveSink:
    """
    Archive OCSF events to AWS S3.

    Features:
    - Partitioned by date and parser_id
    - JSONL format with gzip compression
    - Batch uploads for efficiency
    """

    def __init__(
        self,
        bucket_name: str,
        prefix: str = "purple-pipeline",
        aws_region: str = "us-east-1",
        batch_size: int = 1000,
        compression: bool = True
    ):
        """
        Initialize S3 Archive Sink.

        Args:
            bucket_name: S3 bucket name
            prefix: Key prefix (folder path)
            aws_region: AWS region
            batch_size: Events per file
            compression: Enable gzip compression
        """
        self.bucket_name = bucket_name
        self.prefix = prefix
        self.batch_size = batch_size
        self.compression = compression

        # Initialize S3 client
        self.s3_client = boto3.client("s3", region_name=aws_region)

        # Event buffer
        self.buffer: List[Dict] = []

        # Statistics
        self.stats = {
            "total_archived": 0,
            "total_files": 0,
            "total_bytes": 0,
            "errors": 0
        }

        logger.info(
            f"S3ArchiveSink initialized: "
            f"s3://{bucket_name}/{prefix}"
        )

    async def write_event(self, event: Dict[str, Any]) -> bool:
        """
        Write event to S3 (buffered).

        Args:
            event: OCSF event with metadata

        Returns:
            True if successful, False on error
        """
        self.buffer.append(event)

        # Flush if buffer is full
        if len(self.buffer) >= self.batch_size:
            return await self.flush()

        return True

    async def write_events(self, events: List[Dict[str, Any]]) -> bool:
        """
        Write multiple events to S3.

        Args:
            events: List of OCSF events

        Returns:
            True if successful, False on error
        """
        for event in events:
            self.buffer.append(event)

        # Flush if buffer exceeds batch size
        while len(self.buffer) >= self.batch_size:
            success = await self.flush()
            if not success:
                return False

        return True

    async def flush(self) -> bool:
        """
        Flush buffered events to S3.

        Returns:
            True if successful, False on error
        """
        if not self.buffer:
            return True

        try:
            # Group events by parser_id for partitioning
            events_by_parser: Dict[str, List[Dict]] = {}

            for event in self.buffer:
                parser_id = event.get("_metadata", {}).get("parser_id", "unknown")
                if parser_id not in events_by_parser:
                    events_by_parser[parser_id] = []
                events_by_parser[parser_id].append(event)

            # Upload each partition
            for parser_id, events in events_by_parser.items():
                await self._upload_partition(parser_id, events)

            # Clear buffer
            count = len(self.buffer)
            self.buffer.clear()

            logger.info(f"Flushed {count} events to S3")
            return True

        except Exception as e:
            logger.error(f"Failed to flush events to S3: {e}", exc_info=True)
            self.stats["errors"] += 1
            return False

    async def _upload_partition(self, parser_id: str, events: List[Dict]):
        """Upload events for a specific parser partition."""
        now = datetime.utcnow()

        # Build S3 key with partitioning
        # s3://bucket/purple-pipeline/year=2025/month=11/day=07/hour=12/parser_id=netskope_dlp/events-{ts}.jsonl.gz
        key = (
            f"{self.prefix}/"
            f"year={now.year}/"
            f"month={now.month:02d}/"
            f"day={now.day:02d}/"
            f"hour={now.hour:02d}/"
            f"parser_id={parser_id}/"
            f"events-{now.strftime('%Y%m%d-%H%M%S')}.jsonl"
        )

        if self.compression:
            key += ".gz"

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as tmp_file:
            tmp_path = tmp_file.name

            if self.compression:
                # Write compressed JSONL
                with gzip.open(tmp_file, "wt", encoding="utf-8") as gz_file:
                    for event in events:
                        json.dump(event, gz_file)
                        gz_file.write("\n")
            else:
                # Write uncompressed JSONL
                for event in events:
                    tmp_file.write(json.dumps(event).encode("utf-8"))
                    tmp_file.write(b"\n")

        try:
            # Upload to S3
            file_size = Path(tmp_path).stat().st_size

            self.s3_client.upload_file(
                tmp_path,
                self.bucket_name,
                key,
                ExtraArgs={
                    "ContentType": "application/x-ndjson",
                    "ContentEncoding": "gzip" if self.compression else None
                }
            )

            self.stats["total_archived"] += len(events)
            self.stats["total_files"] += 1
            self.stats["total_bytes"] += file_size

            logger.info(
                f"Uploaded {len(events)} events to s3://{self.bucket_name}/{key} "
                f"({file_size} bytes)"
            )

        finally:
            # Clean up temp file
            Path(tmp_path).unlink(missing_ok=True)

    def get_statistics(self) -> Dict[str, Any]:
        """Get archive statistics."""
        return {
            **self.stats,
            "buffer_size": len(self.buffer)
        }
```

### 3. Output Validator

**File**: `components/output_validator.py`

**Purpose**: Validate OCSF compliance before delivery

```python
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class OutputValidator:
    """
    Validates OCSF event compliance before delivery to sinks.

    Checks:
    - Required OCSF fields present
    - Data type correctness
    - Value range validation
    - Schema version compatibility
    """

    # Required OCSF fields for all event classes
    REQUIRED_FIELDS = [
        "class_uid",
        "category_uid",
        "severity_id",
        "time",
        "metadata"
    ]

    # Required metadata fields
    REQUIRED_METADATA_FIELDS = [
        "version",  # OCSF schema version
        "product"   # Vendor/product information
    ]

    def __init__(self, strict_mode: bool = False):
        """
        Initialize validator.

        Args:
            strict_mode: If True, fail on warnings; if False, only log warnings
        """
        self.strict_mode = strict_mode
        self.stats = {
            "total_validated": 0,
            "passed": 0,
            "failed": 0
        }

    def validate_ocsf(self, event: Dict[str, Any]) -> bool:
        """
        Validate OCSF event.

        Args:
            event: OCSF event dictionary (the "log" portion)

        Returns:
            True if valid, False if invalid

        Raises:
            ValueError: If validation fails and strict_mode=True
        """
        self.stats["total_validated"] += 1
        errors = []

        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in event:
                errors.append(f"Missing required field: {field}")

        # Validate metadata
        if "metadata" in event:
            for field in self.REQUIRED_METADATA_FIELDS:
                if field not in event["metadata"]:
                    errors.append(f"Missing required metadata field: metadata.{field}")

        # Validate data types
        if "class_uid" in event and not isinstance(event["class_uid"], int):
            errors.append(f"class_uid must be integer, got {type(event['class_uid'])}")

        if "category_uid" in event and not isinstance(event["category_uid"], int):
            errors.append(f"category_uid must be integer, got {type(event['category_uid'])}")

        if "severity_id" in event and not isinstance(event["severity_id"], int):
            errors.append(f"severity_id must be integer, got {type(event['severity_id'])}")

        if "time" in event and not isinstance(event["time"], (int, float)):
            errors.append(f"time must be numeric (unix timestamp), got {type(event['time'])}")

        # Validate ranges
        if "severity_id" in event:
            severity = event["severity_id"]
            if not (0 <= severity <= 6):
                errors.append(f"severity_id out of range [0-6]: {severity}")

        # Log or raise errors
        if errors:
            self.stats["failed"] += 1
            error_msg = "; ".join(errors)

            if self.strict_mode:
                raise ValueError(f"OCSF validation failed: {error_msg}")
            else:
                logger.warning(f"OCSF validation warnings: {error_msg}")
                return False
        else:
            self.stats["passed"] += 1
            return True

    def get_statistics(self) -> Dict[str, Any]:
        """Get validation statistics."""
        return {
            **self.stats,
            "pass_rate": (
                self.stats["passed"] / self.stats["total_validated"]
                if self.stats["total_validated"] > 0
                else 0
            )
        }
```

### 4. Output Service (Main Orchestrator)

**File**: `services/output_service.py`

**Purpose**: Orchestrate entire output pipeline

```python
from typing import Dict, List, Any, Optional
import asyncio
import logging
from datetime import datetime
from collections import defaultdict

from components.message_bus_adapter import create_bus_adapter
from components.observo_ingest_client import ObservoIngestClient
from components.sinks.s3_archive_sink import S3ArchiveSink
from components.output_validator import OutputValidator

logger = logging.getLogger(__name__)


class OutputService:
    """
    Main output service that:
    - Consumes OCSF events from Agent 2
    - Validates OCSF compliance
    - Delivers to multiple sinks (Observo, S3, etc.)
    - Tracks delivery status
    - Handles retries and errors
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize output service.

        Config structure:
        {
            "message_bus": {
                "type": "kafka",
                "bootstrap_servers": "localhost:9092",
                "input_topic": "ocsf-events",
                "consumer_group": "output-workers"
            },
            "validator": {
                "strict_mode": false
            },
            "sinks": {
                "observo": {
                    "enabled": true,
                    "base_url": "https://api.observo.ai",
                    "api_token": "...",
                    "batch_size": 100,
                    "retry_count": 5
                },
                "s3_archive": {
                    "enabled": true,
                    "bucket": "purple-pipeline-events",
                    "prefix": "ocsf-archive",
                    "batch_size": 1000
                }
            },
            "retry": {
                "max_attempts": 5,
                "base_backoff_seconds": 2,
                "max_backoff_seconds": 60
            }
        }
        """
        self.config = config
        self.running = False

        # Initialize components
        self.message_bus = None
        self.validator = OutputValidator(
            strict_mode=config.get("validator", {}).get("strict_mode", False)
        )

        # Initialize sinks
        self.sinks: Dict[str, Any] = {}
        self._initialize_sinks()

        # Statistics
        self.stats = {
            "total_received": 0,
            "validation_passed": 0,
            "validation_failed": 0,
            "delivery_success": 0,
            "delivery_failed": 0,
            "by_sink": defaultdict(lambda: {
                "success": 0,
                "failed": 0,
                "latency_ms": []
            })
        }

        logger.info("OutputService initialized")

    def _initialize_sinks(self):
        """Initialize configured sinks."""
        sinks_config = self.config.get("sinks", {})

        # Observo.ai sink
        if sinks_config.get("observo", {}).get("enabled"):
            observo_cfg = sinks_config["observo"]
            self.sinks["observo"] = ObservoIngestClient(
                base_url=observo_cfg["base_url"],
                api_token=observo_cfg["api_token"],
                max_batch_size=observo_cfg.get("batch_size", 100)
            )
            logger.info("Observo.ai sink enabled")

        # S3 Archive sink
        if sinks_config.get("s3_archive", {}).get("enabled"):
            s3_cfg = sinks_config["s3_archive"]
            self.sinks["s3_archive"] = S3ArchiveSink(
                bucket_name=s3_cfg["bucket"],
                prefix=s3_cfg.get("prefix", "purple-pipeline"),
                batch_size=s3_cfg.get("batch_size", 1000)
            )
            logger.info(f"S3 archive sink enabled: s3://{s3_cfg['bucket']}")

    async def start(self):
        """Start the output service."""
        logger.info("Starting OutputService...")
        self.running = True

        # Initialize message bus
        self.message_bus = create_bus_adapter(self.config["message_bus"])
        await self.message_bus.connect()

        # Subscribe to input topic
        input_topic = self.config["message_bus"]["input_topic"]
        await self.message_bus.subscribe(input_topic, self._process_event)

        logger.info(f"OutputService started, consuming from '{input_topic}'")

        # Test sink connections
        await self._test_connections()

        # Keep running
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            await self.stop()

    async def stop(self):
        """Stop the output service gracefully."""
        logger.info("Stopping OutputService...")
        self.running = False

        # Flush any buffered events
        if "s3_archive" in self.sinks:
            await self.sinks["s3_archive"].flush()

        # Close connections
        if self.message_bus:
            await self.message_bus.disconnect()

        if "observo" in self.sinks:
            await self.sinks["observo"].close()

        logger.info(f"Final statistics: {self.get_statistics()}")

    async def _test_connections(self):
        """Test connections to all sinks."""
        logger.info("Testing sink connections...")

        if "observo" in self.sinks:
            observo_ok = await self.sinks["observo"].test_connection()
            if observo_ok:
                logger.info("✓ Observo.ai connection successful")
            else:
                logger.error("✗ Observo.ai connection failed")

    async def _process_event(self, event: Dict[str, Any]):
        """
        Process a single OCSF event through output pipeline.

        Args:
            event: OCSF event from Agent 2 with structure:
                {
                    "_metadata": {...},
                    "log": { OCSF event }
                }
        """
        start_time = datetime.utcnow()
        self.stats["total_received"] += 1

        try:
            # Extract OCSF log
            metadata = event.get("_metadata", {})
            ocsf_log = event.get("log", {})

            if not ocsf_log:
                raise ValueError("Event missing 'log' field")

            # Step 1: Validate OCSF compliance
            is_valid = self.validator.validate_ocsf(ocsf_log)

            if not is_valid:
                self.stats["validation_failed"] += 1
                logger.warning(
                    f"Event validation failed for parser: "
                    f"{metadata.get('parser_id', 'unknown')}"
                )
                # Optionally send to validation-errors DLQ
                return

            self.stats["validation_passed"] += 1

            # Step 2: Deliver to all enabled sinks
            delivery_tasks = []

            for sink_name, sink in self.sinks.items():
                task = self._deliver_to_sink(sink_name, sink, event)
                delivery_tasks.append(task)

            # Execute deliveries in parallel
            results = await asyncio.gather(*delivery_tasks, return_exceptions=True)

            # Check results
            success_count = sum(1 for r in results if r is True)
            failed_count = len(results) - success_count

            if success_count > 0:
                self.stats["delivery_success"] += 1
            if failed_count > 0:
                self.stats["delivery_failed"] += 1

            # Calculate total latency
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.debug(
                f"Event processed: {success_count} sinks succeeded, "
                f"{failed_count} failed (latency={latency_ms:.2f}ms)"
            )

        except Exception as e:
            logger.error(f"Error processing event: {e}", exc_info=True)
            self.stats["delivery_failed"] += 1

    async def _deliver_to_sink(
        self,
        sink_name: str,
        sink: Any,
        event: Dict[str, Any]
    ) -> bool:
        """
        Deliver event to a specific sink with retry logic.

        Args:
            sink_name: Name of sink
            sink: Sink instance
            event: Full event with metadata

        Returns:
            True if successful, False if failed after retries
        """
        retry_config = self.config.get("retry", {})
        max_attempts = retry_config.get("max_attempts", 5)
        base_backoff = retry_config.get("base_backoff_seconds", 2)
        max_backoff = retry_config.get("max_backoff_seconds", 60)

        start_time = datetime.utcnow()

        for attempt in range(1, max_attempts + 1):
            try:
                # Deliver based on sink type
                if isinstance(sink, ObservoIngestClient):
                    result = await sink.ingest_events([event])
                    success = result.get("accepted", 0) > 0

                elif isinstance(sink, S3ArchiveSink):
                    success = await sink.write_event(event)

                else:
                    logger.warning(f"Unknown sink type: {type(sink)}")
                    success = False

                if success:
                    # Record success
                    latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                    self.stats["by_sink"][sink_name]["success"] += 1
                    self.stats["by_sink"][sink_name]["latency_ms"].append(latency_ms)

                    logger.debug(
                        f"Delivered to {sink_name} "
                        f"(attempt {attempt}, latency={latency_ms:.2f}ms)"
                    )
                    return True
                else:
                    raise Exception("Delivery returned failure status")

            except Exception as e:
                logger.warning(
                    f"Delivery to {sink_name} failed (attempt {attempt}/{max_attempts}): {e}"
                )

                if attempt < max_attempts:
                    # Calculate exponential backoff
                    backoff = min(base_backoff * (2 ** (attempt - 1)), max_backoff)
                    logger.info(f"Retrying in {backoff}s...")
                    await asyncio.sleep(backoff)
                else:
                    # All retries exhausted
                    self.stats["by_sink"][sink_name]["failed"] += 1
                    logger.error(
                        f"Delivery to {sink_name} failed after {max_attempts} attempts"
                    )
                    return False

        return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get output service statistics."""
        stats = dict(self.stats)

        # Calculate average latencies
        for sink_name, sink_stats in stats["by_sink"].items():
            latencies = sink_stats["latency_ms"]
            if latencies:
                sink_stats["avg_latency_ms"] = sum(latencies) / len(latencies)
                sink_stats["max_latency_ms"] = max(latencies)
                del sink_stats["latency_ms"]  # Remove raw list

        return stats
```

---

## 📝 Configuration Files

### Output Service Configuration

**File**: `config/output_service.yaml`

```yaml
# Output Service Configuration

message_bus:
  type: kafka  # kafka, redis, or memory
  bootstrap_servers: "localhost:9092"
  input_topic: "ocsf-events"
  consumer_group: "output-workers"

  consumer_config:
    auto_offset_reset: "earliest"
    enable_auto_commit: true

validator:
  strict_mode: false  # If true, fail on validation errors
  log_warnings: true

sinks:
  # Observo.ai Ingestion
  observo:
    enabled: true
    base_url: "https://api.observo.ai"
    api_token: "${OBSERVO_API_TOKEN}"  # Environment variable
    batch_size: 100
    timeout_seconds: 30
    retry_count: 5

  # S3 Archive
  s3_archive:
    enabled: true
    bucket: "purple-pipeline-events"
    prefix: "ocsf-archive"
    aws_region: "us-east-1"
    batch_size: 1000
    compression: true  # gzip compression

  # Elasticsearch (optional)
  elasticsearch:
    enabled: false
    hosts: ["localhost:9200"]
    index_pattern: "ocsf-events-{yyyy.MM.dd}"

  # Splunk HEC (optional)
  splunk_hec:
    enabled: false
    endpoint: "https://splunk.example.com:8088/services/collector"
    token: "${SPLUNK_HEC_TOKEN}"

retry:
  max_attempts: 5
  base_backoff_seconds: 2
  max_backoff_seconds: 60

error_handling:
  dlq_enabled: true
  dlq_topic: "output-failures"
  validation_error_topic: "validation-errors"

performance:
  max_concurrent_deliveries: 100
  batch_flush_interval_seconds: 10

logging:
  level: INFO
  file: "./logs/output_service.log"
```

---

## 🧪 Testing Requirements

### Unit Tests

**File**: `tests/test_output_service.py`

```python
import pytest
from services.output_service import OutputService
from unittest.mock import Mock, AsyncMock


@pytest.fixture
def output_config():
    return {
        "message_bus": {
            "type": "memory",
            "input_topic": "ocsf-events"
        },
        "validator": {
            "strict_mode": False
        },
        "sinks": {
            "observo": {
                "enabled": False  # Disable for unit tests
            },
            "s3_archive": {
                "enabled": False
            }
        }
    }


@pytest.fixture
def sample_ocsf_event():
    return {
        "_metadata": {
            "parser_id": "netskope_dlp",
            "parser_version": "1.0.0",
            "transform_time": "2025-11-07T12:00:01Z"
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


@pytest.mark.asyncio
async def test_output_service_initialization(output_config):
    """Test OutputService initializes correctly."""
    service = OutputService(output_config)
    assert service.config == output_config
    assert service.validator is not None


@pytest.mark.asyncio
async def test_event_validation_success(output_config, sample_ocsf_event):
    """Test valid OCSF event passes validation."""
    service = OutputService(output_config)
    service.message_bus = AsyncMock()

    await service._process_event(sample_ocsf_event)

    assert service.stats["validation_passed"] == 1
    assert service.stats["validation_failed"] == 0


@pytest.mark.asyncio
async def test_event_validation_failure(output_config):
    """Test invalid OCSF event fails validation."""
    service = OutputService(output_config)
    service.message_bus = AsyncMock()

    invalid_event = {
        "_metadata": {"parser_id": "test"},
        "log": {
            "class_uid": 2004
            # Missing required fields
        }
    }

    await service._process_event(invalid_event)

    assert service.stats["validation_failed"] == 1
```

---

## 🚀 Startup Script

**File**: `scripts/start_output_service.py`

```python
#!/usr/bin/env python3
"""
Start the Output Service for event delivery.

Usage:
    python scripts/start_output_service.py [--config path/to/config.yaml]
"""

import asyncio
import argparse
import logging
import sys
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.output_service import OutputService


def load_config(config_path: str) -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


async def main():
    parser = argparse.ArgumentParser(description="Start Output Service")
    parser.add_argument("--config", default="./config/output_service.yaml")
    args = parser.parse_args()

    config = load_config(args.config)

    logging.basicConfig(
        level=config.get("logging", {}).get("level", "INFO"),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger = logging.getLogger(__name__)
    logger.info("=" * 70)
    logger.info("Purple Pipeline Output Service Starting")
    logger.info("=" * 70)

    service = OutputService(config)

    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🎯 Success Criteria

### Phase 1: Core Implementation (Week 1)
- [ ] ObservoIngestClient fully implemented with batching
- [ ] S3ArchiveSink with partitioning and compression
- [ ] OutputValidator with OCSF compliance checks
- [ ] OutputService orchestrating all components
- [ ] Unit tests passing (>80% coverage)

### Phase 2: Production Features (Week 2)
- [ ] Retry logic with exponential backoff
- [ ] Dead-letter queue for failures
- [ ] Metrics and monitoring
- [ ] Multiple sink support
- [ ] Performance optimization

### Phase 3: Integration & Testing (Week 3)
- [ ] Successfully consume from Agent 2's output topic
- [ ] Successfully deliver to Observo.ai
- [ ] Successfully archive to S3
- [ ] End-to-end integration test passing
- [ ] Performance benchmarks met:
  - < 100ms average delivery latency
  - > 1000 events/sec throughput
  - > 99.9% delivery success rate

---

## 📊 Integration with Other Agents

### Agent 2 (Transform Pipeline) → **Your Work**

**What Agent 2 Provides**:
- OCSF-compliant events on `ocsf-events` topic
- Event structure with metadata and transformed log

**What You Do**:
- Subscribe to `ocsf-events` topic
- Validate OCSF compliance
- Deliver to configured sinks

---

## 📦 Deliverables Checklist

- [ ] **components/observo_ingest_client.py** - Enhanced Observo API client
- [ ] **components/sinks/s3_archive_sink.py** - S3 archival sink
- [ ] **components/output_validator.py** - OCSF validator
- [ ] **services/output_service.py** - Main orchestrator (400+ lines)
- [ ] **config/output_service.yaml** - Configuration file
- [ ] **scripts/start_output_service.py** - Startup script
- [ ] **tests/test_output_service.py** - Comprehensive tests
- [ ] **tests/test_observo_client.py** - API client tests
- [ ] **tests/integration/test_e2e_pipeline.py** - Full pipeline test
- [ ] **docs/OUTPUT_SERVICE_ARCHITECTURE.md** - Documentation

---

## 🎓 Key Takeaways

1. **Reliability First**: Implement robust retry logic and error handling
2. **Multi-Sink Architecture**: Support multiple output destinations
3. **OCSF Compliance**: Validate before delivery to catch issues early
4. **Performance**: Use batching and async I/O for throughput
5. **Observability**: Track metrics for every sink

---

## 🚀 Ready to Begin!

You have complete specifications for building a production-ready output pipeline. Start with core components (Observo client, S3 sink, validator), then build the orchestration service, and finally add comprehensive testing.

**Good luck! 🎉**
