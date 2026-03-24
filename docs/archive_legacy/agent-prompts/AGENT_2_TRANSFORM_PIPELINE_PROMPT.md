# 🔄 Agent 2: Transform Pipeline & Runtime Worker Implementation

## 📋 Agent Overview

**Your Role**: Build the core transform pipeline that executes Lua transformations on live security events.

**What You're Building**: The runtime execution layer that consumes raw events from Agent 1, loads the appropriate Lua parser based on manifest routing, executes transformations, and publishes OCSF-compliant events for Agent 3.

**Timeline**: 2-3 weeks (40-60 hours)

**Dependencies**:
- ✅ Agent 1 must publish events to `raw-security-events` topic
- ✅ Existing infrastructure: Message bus, transform executor, canary router (all built, just need activation)
- ⚠️ You'll publish to `ocsf-events` topic for Agent 3 to consume

---

## 🎯 Mission Statement

**Transform raw security events into OCSF-compliant normalized events using dynamically loaded Lua parsers with canary routing, performance monitoring, and production-ready error handling.**

Your pipeline will:
1. Consume normalized events from Agent 1's message bus
2. Route events to appropriate parser based on `_metadata.parser_id`
3. Load and execute Lua transformations (with canary A/B testing)
4. Collect performance metrics and handle errors gracefully
5. Publish transformed OCSF events for Agent 3

---

## 📊 Current System State

### What Already Exists (✅ Ready to Use)

1. **Message Bus Adapter** (`components/message_bus_adapter.py` - 183 lines)
   - Kafka, Redis, Memory implementations
   - Factory pattern: `create_bus_adapter(config)`
   - Subscribe/publish methods ready

2. **Transform Executor** (`components/transform_executor.py` - 150 lines)
   - Strategy pattern: Lupa (in-process) and Dataplane (subprocess)
   - Abstract base class with concrete implementations
   ```python
   class TransformExecutor(ABC):
       @abstractmethod
       async def execute(self, lua_code: str, event: Dict) -> Dict:
           pass

   class LupaExecutor(TransformExecutor):
       # Uses lupa library for in-process Lua execution

   class DataplaneExecutor(TransformExecutor):
       # Uses dataplane binary for isolated execution
   ```

3. **Transform Worker** (`services/transform_worker.py` - 100 lines)
   - Basic structure exists but needs enhancement
   - Ready to consume from message bus
   - Needs integration with manifest system

4. **Manifest Store** (`components/manifest_store.py` - 50 lines)
   - Loads parser manifests from `output/<parser_id>/manifest.json`
   - Provides metadata: version, Lua code path, OCSF mapping

5. **Canary Router** (`components/canary_router.py` - 90 lines)
   - A/B testing for gradual rollout
   - Percentage-based routing (stable vs canary)
   ```python
   class CanaryRouter:
       def should_use_canary(self, parser_id: str) -> bool:
           # Returns True if event should use canary version
   ```

6. **Runtime Metrics Collector** (`components/runtime_metrics.py` - 60 lines)
   - Tracks: events processed, errors, latency, parser performance
   - Ready to integrate with worker

### What Needs Building (❌ Your Responsibility)

1. **RuntimeService** (`services/runtime_service.py` - Currently 40-line stub)
   - Currently just stores metrics, doesn't collect them
   - Needs to orchestrate the entire transform pipeline
   - Must integrate all existing components

2. **Manifest-Based Parser Loading**
   - Dynamic Lua code loading from manifest
   - Parser version management
   - Cache management for performance

3. **Event Routing Logic**
   - Map `_metadata.parser_id` → manifest → Lua code
   - Handle unknown parsers gracefully
   - Support parser aliases

4. **Enhanced Transform Worker**
   - Integrate with RuntimeService
   - Add error recovery and retry logic
   - Implement performance optimization

5. **Web UI Integration** (Optional but recommended)
   - Real-time metrics display
   - Parser status dashboard
   - Error monitoring

---

## 🏗️ Architecture Design

### Data Flow Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT 2: TRANSFORM PIPELINE                  │
└─────────────────────────────────────────────────────────────────┘

INPUT: raw-security-events topic (from Agent 1)
═══════════════════════════════════════════════════
Event Format:
{
  "_metadata": {
    "source_type": "kafka",
    "source_id": "netskope-alerts",
    "ingestion_time": "2025-11-07T12:00:00Z",
    "parser_id": "netskope_dlp",  ← KEY: Routing identifier
    "original_format": "json"
  },
  "log": {
    "alert_type": "DLP",
    "user": "john@example.com",
    "file": "sensitive.xlsx",
    "severity": "High"
  }
}


STEP 1: Event Consumption
═══════════════════════════════════════════════════
RuntimeService.start()
    ↓
Subscribe to: raw-security-events
    ↓
Receive event → parse → validate structure


STEP 2: Parser Resolution
═══════════════════════════════════════════════════
Extract: parser_id = event["_metadata"]["parser_id"]
    ↓
ManifestStore.get_manifest(parser_id)
    ↓
Load manifest from: output/<parser_id>/manifest.json
    ↓
Manifest contains:
{
  "parser_id": "netskope_dlp",
  "version": "1.0.0",
  "lua_code_path": "output/netskope_dlp/transform.lua",
  "ocsf_classification": {
    "class_uid": 2004,
    "class_name": "Detection Finding"
  },
  "canary_config": {
    "enabled": true,
    "percentage": 10
  }
}


STEP 3: Canary Routing Decision
═══════════════════════════════════════════════════
CanaryRouter.should_use_canary(parser_id)
    ↓
If canary enabled AND random() < percentage:
    use_version = "canary"
    lua_code_path = manifest["canary_lua_code_path"]
else:
    use_version = "stable"
    lua_code_path = manifest["lua_code_path"]


STEP 4: Lua Code Loading
═══════════════════════════════════════════════════
LuaCodeCache.get(lua_code_path, use_version)
    ↓
Check cache → if miss, load from disk
    ↓
Read Lua code from transform.lua file


STEP 5: Transform Execution
═══════════════════════════════════════════════════
Executor Strategy Selection:
    If production → DataplaneExecutor (isolated)
    If development → LupaExecutor (fast)
    ↓
executor.execute(lua_code, event["log"])
    ↓
Lua function: processEvent(event) → OCSF output
    ↓
Returns:
{
  "class_uid": 2004,
  "class_name": "Detection Finding",
  "category_uid": 2,
  "user": {
    "name": "john@example.com",
    "email_addr": "john@example.com"
  },
  "file": {
    "name": "sensitive.xlsx"
  },
  "severity_id": 4,
  "severity": "High",
  "metadata": {
    "version": "1.5.0",
    "product": {
      "name": "Netskope",
      "vendor_name": "Netskope"
    }
  }
}


STEP 6: Post-Processing
═══════════════════════════════════════════════════
Validate OCSF compliance:
    - Check required fields: class_uid, category_uid, metadata
    - Verify class_uid matches manifest expectation
    ↓
Add execution metadata:
{
  "_metadata": {
    ...original metadata...,
    "transform_time": "2025-11-07T12:00:01Z",
    "parser_version": "1.0.0",
    "canary_used": false,
    "execution_time_ms": 12.5
  },
  "log": {
    ...OCSF output...
  }
}


STEP 7: Metrics Collection
═══════════════════════════════════════════════════
RuntimeMetrics.record_event(parser_id, {
    "success": true,
    "latency_ms": 12.5,
    "canary_version": use_version
})
    ↓
Update aggregate statistics:
    - Total events processed
    - Average latency
    - Error rate
    - Canary performance comparison


STEP 8: Error Handling
═══════════════════════════════════════════════════
If transformation fails:
    ↓
Catch exception → log detailed error
    ↓
RuntimeMetrics.record_error(parser_id, error)
    ↓
Options:
    1. Publish to dead-letter queue (DLQ)
    2. Fallback to original event + error metadata
    3. Retry with exponential backoff


STEP 9: Output Publication
═══════════════════════════════════════════════════
Publish to: ocsf-events topic
    ↓
Event format for Agent 3:
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
    // OCSF-compliant output
    "class_uid": 2004,
    ...
  }
}


OUTPUT: ocsf-events topic (to Agent 3)
═══════════════════════════════════════════════════
Ready for Observo.ai ingestion and other sinks
```

---

## 🔧 Detailed Implementation Requirements

### 1. RuntimeService Enhancement

**File**: `services/runtime_service.py`

**Current State**: 40-line stub that only stores metrics

**Your Task**: Build complete runtime orchestration service

**Requirements**:

```python
from typing import Dict, List, Optional, Any
import asyncio
import logging
from datetime import datetime
from collections import defaultdict
from components.message_bus_adapter import create_bus_adapter
from components.manifest_store import ManifestStore
from components.canary_router import CanaryRouter
from components.transform_executor import LupaExecutor, DataplaneExecutor
from components.runtime_metrics import RuntimeMetrics
from services.lua_code_cache import LuaCodeCache

logger = logging.getLogger(__name__)


class RuntimeService:
    """
    Orchestrates the complete transform pipeline:
    - Consumes raw events from message bus
    - Routes to appropriate parser based on manifest
    - Executes Lua transformation with canary support
    - Publishes OCSF events to output topic
    - Collects performance metrics
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize runtime service with configuration.

        Config structure:
        {
            "message_bus": {
                "type": "kafka",
                "bootstrap_servers": "localhost:9092",
                "input_topic": "raw-security-events",
                "output_topic": "ocsf-events",
                "consumer_group": "transform-workers"
            },
            "executor": {
                "type": "dataplane",  # or "lupa"
                "dataplane_binary": "/opt/dataplane/dataplane",
                "timeout_seconds": 30
            },
            "manifest_directory": "./output",
            "canary_enabled": true,
            "metrics_enabled": true,
            "error_handling": {
                "retry_attempts": 3,
                "retry_backoff_seconds": 5,
                "dlq_enabled": true,
                "dlq_topic": "transform-errors"
            }
        }
        """
        self.config = config
        self.running = False

        # Initialize components
        self.message_bus = None
        self.manifest_store = ManifestStore(
            directory=config.get("manifest_directory", "./output")
        )
        self.canary_router = CanaryRouter()
        self.metrics = RuntimeMetrics() if config.get("metrics_enabled") else None
        self.lua_cache = LuaCodeCache(max_size=100)

        # Initialize executor based on config
        executor_type = config.get("executor", {}).get("type", "lupa")
        if executor_type == "dataplane":
            self.executor = DataplaneExecutor(
                binary_path=config["executor"]["dataplane_binary"],
                timeout=config["executor"].get("timeout_seconds", 30)
            )
        else:
            self.executor = LupaExecutor()

        # Statistics
        self.stats = {
            "total_events": 0,
            "successful_transforms": 0,
            "failed_transforms": 0,
            "parsers_active": set()
        }

        logger.info(f"RuntimeService initialized with {executor_type} executor")

    async def start(self):
        """Start the runtime service - begin consuming and processing events."""
        logger.info("Starting RuntimeService...")
        self.running = True

        # Initialize message bus
        self.message_bus = create_bus_adapter(self.config["message_bus"])
        await self.message_bus.connect()

        # Subscribe to input topic
        input_topic = self.config["message_bus"]["input_topic"]
        await self.message_bus.subscribe(input_topic, self._process_event)

        logger.info(f"RuntimeService started, consuming from '{input_topic}'")

        # Keep running until stopped
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            await self.stop()

    async def stop(self):
        """Stop the runtime service gracefully."""
        logger.info("Stopping RuntimeService...")
        self.running = False

        if self.message_bus:
            await self.message_bus.disconnect()

        # Log final statistics
        logger.info(f"Final statistics: {self.stats}")

    async def _process_event(self, event: Dict[str, Any]):
        """
        Process a single event through the transform pipeline.

        Args:
            event: Normalized event from Agent 1 with structure:
                {
                    "_metadata": {
                        "parser_id": "netskope_dlp",
                        "source_type": "kafka",
                        ...
                    },
                    "log": { ... raw event data ... }
                }
        """
        start_time = datetime.utcnow()
        parser_id = None

        try:
            # Extract metadata
            metadata = event.get("_metadata", {})
            parser_id = metadata.get("parser_id")

            if not parser_id:
                raise ValueError("Event missing _metadata.parser_id")

            # Update statistics
            self.stats["total_events"] += 1
            self.stats["parsers_active"].add(parser_id)

            # Step 1: Load parser manifest
            manifest = self.manifest_store.get_manifest(parser_id)
            if not manifest:
                raise ValueError(f"No manifest found for parser: {parser_id}")

            # Step 2: Canary routing decision
            use_canary = False
            if self.canary_router and manifest.get("canary_config", {}).get("enabled"):
                use_canary = self.canary_router.should_use_canary(parser_id)

            # Step 3: Load Lua code
            lua_code_path = (
                manifest.get("canary_lua_code_path")
                if use_canary
                else manifest.get("lua_code_path")
            )

            if not lua_code_path:
                raise ValueError(f"Manifest for {parser_id} missing lua_code_path")

            lua_code = self.lua_cache.get(lua_code_path, "canary" if use_canary else "stable")

            # Step 4: Execute transformation
            raw_log = event.get("log", {})
            transformed_log = await self.executor.execute(lua_code, raw_log)

            # Step 5: Validate OCSF compliance
            self._validate_ocsf_output(transformed_log, manifest)

            # Step 6: Build output event with enhanced metadata
            execution_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            output_event = {
                "_metadata": {
                    **metadata,
                    "parser_version": manifest.get("version", "unknown"),
                    "transform_time": datetime.utcnow().isoformat() + "Z",
                    "execution_time_ms": round(execution_time_ms, 2),
                    "canary_used": use_canary
                },
                "log": transformed_log
            }

            # Step 7: Publish to output topic
            output_topic = self.config["message_bus"]["output_topic"]
            await self.message_bus.publish(output_topic, output_event)

            # Step 8: Record metrics
            self.stats["successful_transforms"] += 1
            if self.metrics:
                self.metrics.record_event(parser_id, {
                    "success": True,
                    "latency_ms": execution_time_ms,
                    "canary_version": "canary" if use_canary else "stable"
                })

            logger.debug(
                f"Transformed event with {parser_id} "
                f"(canary={use_canary}, latency={execution_time_ms:.2f}ms)"
            )

        except Exception as e:
            # Error handling
            self.stats["failed_transforms"] += 1

            error_info = {
                "error": str(e),
                "error_type": type(e).__name__,
                "parser_id": parser_id,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

            logger.error(f"Transform error for parser {parser_id}: {e}", exc_info=True)

            if self.metrics and parser_id:
                self.metrics.record_error(parser_id, error_info)

            # Retry logic or DLQ
            await self._handle_transform_error(event, error_info)

    def _validate_ocsf_output(self, output: Dict, manifest: Dict):
        """
        Validate that transformed output meets OCSF requirements.

        Raises ValueError if validation fails.
        """
        required_fields = ["class_uid", "category_uid", "metadata"]

        missing = [field for field in required_fields if field not in output]
        if missing:
            raise ValueError(f"OCSF validation failed: missing fields {missing}")

        # Verify class_uid matches manifest expectation
        expected_class_uid = manifest.get("ocsf_classification", {}).get("class_uid")
        actual_class_uid = output.get("class_uid")

        if expected_class_uid and actual_class_uid != expected_class_uid:
            logger.warning(
                f"Class UID mismatch: expected {expected_class_uid}, "
                f"got {actual_class_uid}"
            )

    async def _handle_transform_error(self, event: Dict, error_info: Dict):
        """
        Handle transformation errors with retry or DLQ.

        Args:
            event: Original event that failed
            error_info: Error details
        """
        error_config = self.config.get("error_handling", {})

        if error_config.get("dlq_enabled"):
            # Publish to dead-letter queue
            dlq_topic = error_config.get("dlq_topic", "transform-errors")

            dlq_event = {
                **event,
                "_error": error_info
            }

            try:
                await self.message_bus.publish(dlq_topic, dlq_event)
                logger.info(f"Published failed event to DLQ: {dlq_topic}")
            except Exception as dlq_error:
                logger.error(f"Failed to publish to DLQ: {dlq_error}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get current runtime statistics."""
        return {
            **self.stats,
            "parsers_active": list(self.stats["parsers_active"]),
            "success_rate": (
                self.stats["successful_transforms"] / self.stats["total_events"]
                if self.stats["total_events"] > 0
                else 0
            )
        }

    def get_parser_metrics(self, parser_id: str) -> Optional[Dict]:
        """Get detailed metrics for a specific parser."""
        if not self.metrics:
            return None
        return self.metrics.get_parser_metrics(parser_id)
```

### 2. Lua Code Cache

**File**: `services/lua_code_cache.py`

**Purpose**: Cache Lua code in memory to avoid repeated disk reads

```python
from typing import Dict, Optional
from pathlib import Path
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class LuaCodeCache:
    """
    In-memory cache for Lua transformation code.

    Cache key format: f"{file_path}:{version}"
    """

    def __init__(self, max_size: int = 100):
        self.cache: Dict[str, Dict] = {}
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def get(self, file_path: str, version: str = "stable") -> str:
        """
        Get Lua code from cache or load from disk.

        Args:
            file_path: Path to transform.lua file
            version: "stable" or "canary"

        Returns:
            Lua code as string
        """
        cache_key = f"{file_path}:{version}"

        # Check cache
        if cache_key in self.cache:
            cached = self.cache[cache_key]

            # Verify file hasn't changed
            file_path_obj = Path(file_path)
            if file_path_obj.exists():
                current_mtime = file_path_obj.stat().st_mtime
                if current_mtime == cached["mtime"]:
                    self.hits += 1
                    logger.debug(f"Cache hit: {cache_key}")
                    return cached["code"]

        # Cache miss - load from disk
        self.misses += 1
        logger.debug(f"Cache miss: {cache_key}")

        lua_code = self._load_from_disk(file_path)

        # Store in cache
        self._put(cache_key, lua_code, file_path)

        return lua_code

    def _load_from_disk(self, file_path: str) -> str:
        """Load Lua code from disk."""
        file_path_obj = Path(file_path)

        if not file_path_obj.exists():
            raise FileNotFoundError(f"Lua file not found: {file_path}")

        with open(file_path_obj, "r", encoding="utf-8") as f:
            return f.read()

    def _put(self, cache_key: str, code: str, file_path: str):
        """Store Lua code in cache."""
        # Evict oldest entry if cache is full
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k]["accessed"])
            del self.cache[oldest_key]
            logger.debug(f"Evicted from cache: {oldest_key}")

        file_path_obj = Path(file_path)
        mtime = file_path_obj.stat().st_mtime if file_path_obj.exists() else 0

        self.cache[cache_key] = {
            "code": code,
            "mtime": mtime,
            "accessed": datetime.utcnow()
        }

    def invalidate(self, file_path: Optional[str] = None):
        """
        Invalidate cache entries.

        Args:
            file_path: Specific file to invalidate, or None to clear all
        """
        if file_path:
            keys_to_remove = [k for k in self.cache.keys() if k.startswith(f"{file_path}:")]
            for key in keys_to_remove:
                del self.cache[key]
            logger.info(f"Invalidated cache for: {file_path}")
        else:
            self.cache.clear()
            logger.info("Cache cleared")

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(hit_rate, 3)
        }
```

### 3. Enhanced Manifest Store

**File**: `components/manifest_store.py` (Enhancement)

**Current**: Basic manifest loading exists

**Your Task**: Add caching and error handling

```python
from typing import Dict, Optional, List
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


class ManifestStore:
    """
    Loads and caches parser manifests from output directory.

    Directory structure:
        output/
            netskope_dlp/
                manifest.json
                transform.lua
                pipeline.json
            okta_audit/
                manifest.json
                transform.lua
                pipeline.json
    """

    def __init__(self, directory: str = "./output"):
        self.directory = Path(directory)
        self.cache: Dict[str, Dict] = {}
        self.aliases: Dict[str, str] = {}  # alias -> canonical parser_id

        # Load all manifests on initialization
        self._load_all_manifests()

    def _load_all_manifests(self):
        """Scan output directory and load all manifests."""
        if not self.directory.exists():
            logger.warning(f"Manifest directory does not exist: {self.directory}")
            return

        for parser_dir in self.directory.iterdir():
            if not parser_dir.is_dir():
                continue

            manifest_path = parser_dir / "manifest.json"
            if manifest_path.exists():
                try:
                    manifest = self._load_manifest_file(manifest_path)
                    parser_id = parser_dir.name
                    self.cache[parser_id] = manifest

                    # Register aliases if defined
                    for alias in manifest.get("aliases", []):
                        self.aliases[alias] = parser_id

                    logger.debug(f"Loaded manifest for: {parser_id}")
                except Exception as e:
                    logger.error(f"Failed to load manifest from {manifest_path}: {e}")

        logger.info(f"Loaded {len(self.cache)} parser manifests")

    def _load_manifest_file(self, path: Path) -> Dict:
        """Load manifest JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_manifest(self, parser_id: str) -> Optional[Dict]:
        """
        Get manifest for a parser by ID or alias.

        Args:
            parser_id: Parser identifier or alias

        Returns:
            Manifest dict or None if not found
        """
        # Check if it's an alias
        if parser_id in self.aliases:
            parser_id = self.aliases[parser_id]

        return self.cache.get(parser_id)

    def list_parsers(self) -> List[str]:
        """Get list of all available parser IDs."""
        return list(self.cache.keys())

    def reload(self):
        """Reload all manifests from disk."""
        self.cache.clear()
        self.aliases.clear()
        self._load_all_manifests()
        logger.info("Manifests reloaded")
```

---

## 🧪 Testing Requirements

### Unit Tests

**File**: `tests/test_runtime_service.py`

```python
import pytest
import asyncio
from services.runtime_service import RuntimeService
from unittest.mock import Mock, AsyncMock, patch


@pytest.fixture
def runtime_config():
    return {
        "message_bus": {
            "type": "memory",
            "input_topic": "raw-security-events",
            "output_topic": "ocsf-events"
        },
        "executor": {
            "type": "lupa"
        },
        "manifest_directory": "./test_output",
        "canary_enabled": False,
        "metrics_enabled": True
    }


@pytest.fixture
def sample_event():
    return {
        "_metadata": {
            "source_type": "kafka",
            "parser_id": "netskope_dlp",
            "ingestion_time": "2025-11-07T12:00:00Z"
        },
        "log": {
            "alert_type": "DLP",
            "user": "john@example.com",
            "severity": "High"
        }
    }


@pytest.mark.asyncio
async def test_runtime_service_initialization(runtime_config):
    """Test RuntimeService initializes correctly."""
    service = RuntimeService(runtime_config)

    assert service.config == runtime_config
    assert service.manifest_store is not None
    assert service.executor is not None
    assert not service.running


@pytest.mark.asyncio
async def test_event_processing_success(runtime_config, sample_event):
    """Test successful event transformation."""
    service = RuntimeService(runtime_config)

    # Mock dependencies
    service.manifest_store.get_manifest = Mock(return_value={
        "parser_id": "netskope_dlp",
        "version": "1.0.0",
        "lua_code_path": "./test_lua/transform.lua",
        "ocsf_classification": {
            "class_uid": 2004,
            "class_name": "Detection Finding"
        }
    })

    service.lua_cache.get = Mock(return_value="""
        function processEvent(event)
            local result = {}
            result["class_uid"] = 2004
            result["category_uid"] = 2
            result["metadata"] = {version = "1.5.0"}
            result["user"] = event["user"]
            return result
        end
    """)

    service.message_bus = AsyncMock()

    # Process event
    await service._process_event(sample_event)

    # Verify output published
    assert service.message_bus.publish.called
    output_event = service.message_bus.publish.call_args[0][1]

    assert output_event["_metadata"]["parser_id"] == "netskope_dlp"
    assert output_event["log"]["class_uid"] == 2004
    assert "execution_time_ms" in output_event["_metadata"]


@pytest.mark.asyncio
async def test_event_processing_missing_parser(runtime_config, sample_event):
    """Test handling of unknown parser."""
    service = RuntimeService(runtime_config)
    service.manifest_store.get_manifest = Mock(return_value=None)
    service.message_bus = AsyncMock()

    # Should handle gracefully
    await service._process_event(sample_event)

    assert service.stats["failed_transforms"] == 1


@pytest.mark.asyncio
async def test_ocsf_validation(runtime_config):
    """Test OCSF compliance validation."""
    service = RuntimeService(runtime_config)

    manifest = {
        "ocsf_classification": {
            "class_uid": 2004
        }
    }

    # Valid output
    valid_output = {
        "class_uid": 2004,
        "category_uid": 2,
        "metadata": {"version": "1.5.0"}
    }
    service._validate_ocsf_output(valid_output, manifest)  # Should not raise

    # Invalid output - missing field
    invalid_output = {
        "class_uid": 2004
    }
    with pytest.raises(ValueError, match="missing fields"):
        service._validate_ocsf_output(invalid_output, manifest)
```

### Integration Tests

**File**: `tests/integration/test_transform_pipeline.py`

```python
import pytest
import asyncio
from services.runtime_service import RuntimeService
from components.message_bus_adapter import create_bus_adapter


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_transform_pipeline():
    """Test complete pipeline from raw event to OCSF output."""

    # Setup: Create test manifest and Lua code
    # (Implementation details...)

    # Start RuntimeService
    config = {
        "message_bus": {
            "type": "memory",
            "input_topic": "test-raw-events",
            "output_topic": "test-ocsf-events"
        },
        # ... rest of config
    }

    service = RuntimeService(config)

    # Publish test event
    input_bus = create_bus_adapter(config["message_bus"])
    await input_bus.connect()

    test_event = {
        "_metadata": {"parser_id": "test_parser"},
        "log": {"test": "data"}
    }

    await input_bus.publish("test-raw-events", test_event)

    # Start service and wait for processing
    await asyncio.wait_for(service.start(), timeout=5.0)

    # Verify output
    # (Check output topic for transformed event)
```

---

## 📝 Configuration Files

### Runtime Configuration

**File**: `config/runtime_service.yaml`

```yaml
# Runtime Transform Pipeline Configuration

message_bus:
  type: kafka  # kafka, redis, or memory

  # Kafka configuration
  bootstrap_servers: "localhost:9092"
  input_topic: "raw-security-events"
  output_topic: "ocsf-events"
  consumer_group: "transform-workers"

  # Consumer settings
  consumer_config:
    auto_offset_reset: "earliest"
    enable_auto_commit: true
    max_poll_records: 100

  # Producer settings
  producer_config:
    acks: "all"
    compression_type: "snappy"

executor:
  type: dataplane  # dataplane or lupa

  # Dataplane executor config
  dataplane_binary: "/opt/dataplane/dataplane"
  timeout_seconds: 30

  # Lupa executor config
  max_memory_mb: 256

manifest:
  directory: "./output"
  reload_interval_seconds: 300  # Reload manifests every 5 min

canary:
  enabled: true
  default_percentage: 10  # 10% canary traffic by default

metrics:
  enabled: true
  collection_interval_seconds: 60
  retention_hours: 24

error_handling:
  retry_attempts: 3
  retry_backoff_seconds: 5
  dlq_enabled: true
  dlq_topic: "transform-errors"

  # Fallback behavior on persistent failure
  fallback_strategy: "passthrough"  # passthrough, drop, or dlq

performance:
  lua_cache_size: 100
  max_concurrent_transforms: 50
  event_queue_size: 1000

logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "./logs/runtime_service.log"
```

---

## 🚀 Startup Script

**File**: `scripts/start_runtime_service.py`

```python
#!/usr/bin/env python3
"""
Start the RuntimeService for live event transformation.

Usage:
    python scripts/start_runtime_service.py [--config path/to/config.yaml]
"""

import asyncio
import argparse
import logging
import sys
import yaml
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.runtime_service import RuntimeService


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def setup_logging(config: dict):
    """Setup logging based on configuration."""
    log_config = config.get("logging", {})

    logging.basicConfig(
        level=log_config.get("level", "INFO"),
        format=log_config.get(
            "format",
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    )

    # File handler
    if "file" in log_config:
        log_file = Path(log_config["file"])
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_config.get("level", "INFO"))
        logging.getLogger().addHandler(file_handler)


async def main():
    parser = argparse.ArgumentParser(
        description="Start the Purple Pipeline Runtime Transform Service"
    )
    parser.add_argument(
        "--config",
        default="./config/runtime_service.yaml",
        help="Path to configuration file"
    )
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)
    setup_logging(config)

    logger = logging.getLogger(__name__)
    logger.info("=" * 70)
    logger.info("Purple Pipeline Runtime Service Starting")
    logger.info("=" * 70)

    # Create and start service
    service = RuntimeService(config)

    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await service.stop()
        logger.info("Runtime service stopped")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🎯 Success Criteria

### Phase 1: Core Implementation (Week 1)
- [ ] RuntimeService fully implemented with all methods
- [ ] LuaCodeCache working with hit/miss tracking
- [ ] ManifestStore enhanced with aliases and caching
- [ ] Unit tests passing (>80% coverage)
- [ ] Basic integration test working

### Phase 2: Production Features (Week 2)
- [ ] Error handling with DLQ support
- [ ] Canary routing functional
- [ ] Metrics collection integrated
- [ ] Performance optimization (cache, async)
- [ ] Comprehensive logging

### Phase 3: Integration & Testing (Week 3)
- [ ] Successfully consume from Agent 1's output topic
- [ ] Successfully publish to Agent 3's input topic
- [ ] End-to-end integration test passing
- [ ] Performance benchmarks met:
  - < 50ms average transform latency
  - > 1000 events/sec throughput
  - < 1% error rate

---

## 📊 Integration with Other Agents

### Agent 1 (Event Ingestion) → **Your Work**

**What Agent 1 Provides**:
- Publishes normalized events to `raw-security-events` topic
- Event structure:
  ```json
  {
    "_metadata": {
      "source_type": "kafka|scol|s3|azure|gcp|syslog",
      "source_id": "unique-source-identifier",
      "parser_id": "netskope_dlp",  ← You need this!
      "ingestion_time": "2025-11-07T12:00:00Z"
    },
    "log": { /* raw event data */ }
  }
  ```

**What You Do**:
- Subscribe to `raw-security-events` topic
- Extract `parser_id` from metadata
- Load appropriate Lua transformation
- Execute and validate

### **Your Work** → Agent 3 (Observo Output)

**What You Provide**:
- Publish OCSF events to `ocsf-events` topic
- Event structure:
  ```json
  {
    "_metadata": {
      "parser_id": "netskope_dlp",
      "parser_version": "1.0.0",
      "transform_time": "2025-11-07T12:00:01Z",
      "execution_time_ms": 12.5,
      "canary_used": false
    },
    "log": {
      "class_uid": 2004,
      "class_name": "Detection Finding",
      /* ... OCSF-compliant fields ... */
    }
  }
  ```

**What Agent 3 Does**:
- Consumes your transformed events
- Sends to Observo.ai and other sinks
- Handles delivery confirmation

---

## 📦 Deliverables Checklist

- [ ] **services/runtime_service.py** - Complete RuntimeService implementation (400+ lines)
- [ ] **services/lua_code_cache.py** - Lua code caching layer (150+ lines)
- [ ] **components/manifest_store.py** - Enhanced manifest management (200+ lines)
- [ ] **config/runtime_service.yaml** - Production configuration file
- [ ] **scripts/start_runtime_service.py** - Startup script with CLI
- [ ] **tests/test_runtime_service.py** - Comprehensive unit tests (300+ lines)
- [ ] **tests/test_lua_code_cache.py** - Cache unit tests
- [ ] **tests/test_manifest_store.py** - Manifest store tests
- [ ] **tests/integration/test_transform_pipeline.py** - E2E integration test
- [ ] **docs/RUNTIME_SERVICE_ARCHITECTURE.md** - Architecture documentation

---

## 🔍 Testing Guide

### Manual Testing

```bash
# 1. Setup: Copy dataplane binary
mkdir -p /opt/dataplane
cp /path/to/dataplane.amd64 /opt/dataplane/dataplane
chmod +x /opt/dataplane/dataplane

# 2. Generate test manifest and Lua code
# (Use existing orchestrator to generate parser)
python main.py --max-parsers 1

# 3. Start Kafka (if using Kafka message bus)
docker-compose up -d kafka

# 4. Start RuntimeService
python scripts/start_runtime_service.py --config config/runtime_service.yaml

# 5. In another terminal, publish test event
python3 << 'EOF'
import asyncio
from components.message_bus_adapter import create_bus_adapter

async def publish_test():
    config = {
        "type": "kafka",
        "bootstrap_servers": "localhost:9092"
    }
    bus = create_bus_adapter(config)
    await bus.connect()

    event = {
        "_metadata": {
            "parser_id": "netskope_dlp",
            "source_type": "test",
            "ingestion_time": "2025-11-07T12:00:00Z"
        },
        "log": {
            "alert_type": "DLP",
            "user": "test@example.com"
        }
    }

    await bus.publish("raw-security-events", event)
    print("Test event published!")
    await bus.disconnect()

asyncio.run(publish_test())
EOF

# 6. Verify output
# Check logs: tail -f logs/runtime_service.log
# Check output topic for transformed event
```

---

## ⚠️ Common Issues & Solutions

### Issue 1: Dataplane Binary Not Found
**Error**: `FileNotFoundError: /opt/dataplane/dataplane`
**Solution**:
```bash
mkdir -p /opt/dataplane
cp /path/to/dataplane.amd64 /opt/dataplane/dataplane
chmod +x /opt/dataplane/dataplane
```

### Issue 2: Manifest Not Found
**Error**: `No manifest found for parser: xxx`
**Solution**: Run orchestrator first to generate manifests:
```bash
python main.py --max-parsers 1
ls -la output/*/manifest.json
```

### Issue 3: Kafka Connection Issues
**Error**: `KafkaError: Unable to connect to broker`
**Solution**:
```bash
# Start Kafka
docker-compose up -d kafka zookeeper

# Verify Kafka is running
docker ps | grep kafka
```

### Issue 4: Lua Execution Timeout
**Error**: `Transform execution timeout after 30s`
**Solution**: Increase timeout in config:
```yaml
executor:
  timeout_seconds: 60  # Increase from 30
```

---

## 📚 Additional Resources

- **Existing Components**:
  - [components/message_bus_adapter.py](components/message_bus_adapter.py) - Message bus abstraction
  - [components/transform_executor.py](components/transform_executor.py) - Lua execution strategies
  - [components/canary_router.py](components/canary_router.py) - A/B testing logic
  - [components/runtime_metrics.py](components/runtime_metrics.py) - Metrics collection

- **Documentation**:
  - [docs/Hybrid_Architecture_Plan.md](docs/Hybrid_Architecture_Plan.md) - Overall architecture
  - [DATAPLANE_INTEGRATION_STATUS.md](DATAPLANE_INTEGRATION_STATUS.md) - Current integration state
  - [INVESTIGATION_SUMMARY.md](INVESTIGATION_SUMMARY.md) - System status summary

---

## 🎓 Key Takeaways

1. **You're Not Starting From Scratch**: 60% of infrastructure already exists (message bus, executors, canary router)
2. **Focus on Orchestration**: Your main task is wiring existing components together in RuntimeService
3. **Manifest is King**: Everything is driven by manifest.json - parser resolution, versioning, canary config
4. **Error Handling is Critical**: Production systems must handle failures gracefully (DLQ, retries, metrics)
5. **Integration Points Matter**: Ensure compatibility with Agent 1 (input) and Agent 3 (output)

---

## 🚀 Ready to Begin?

You have everything you need:
- ✅ Detailed architecture and data flow
- ✅ Complete code templates with documentation
- ✅ Configuration examples
- ✅ Testing requirements and examples
- ✅ Integration specifications

**Your next step**: Start with RuntimeService implementation, then build supporting components (cache, enhanced manifest store), and finally create comprehensive tests.

**Questions?** Refer to existing code in `components/` and `services/` directories for patterns and examples.

**Good luck! 🎉**
