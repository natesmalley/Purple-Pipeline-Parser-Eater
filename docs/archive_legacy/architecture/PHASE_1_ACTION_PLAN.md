# 🎯 Phase 1 Action Plan: Enable Dataplane Validation & Event Processing

**Status**: Ready for Immediate Implementation
**Timeline**: 4-6 weeks to full capability
**Priority**: Critical

---

## Executive Decision Matrix

### What You Have

| Capability | Status | Evidence |
|-----------|--------|----------|
| Parser scanning (GitHub) | ✅ Complete | `github_scanner.py` 350+ lines |
| Claude analysis | ✅ Complete | `claude_analyzer.py` 400+ lines |
| Lua generation | ✅ Complete | `lua_generator.py` 500+ lines |
| **Dataplane validation** | ✅ **Complete** | **`dataplane_validator.py` 130 lines** |
| Message bus abstraction | ✅ Complete | 183 lines (Kafka/Redis/Memory) |
| Transform worker | ✅ Complete | 100 lines (ready to deploy) |
| Manifest system | ✅ Complete | Versioning, canary routing |
| Per-parser artifacts | ✅ Complete | 4 files per parser |

### What You're Missing

| Component | Status | Effort | Impact |
|-----------|--------|--------|--------|
| Binary path setup | ❌ 30 min | Low | High |
| RuntimeService impl | ❌ 4 hrs | Low | Critical |
| Event source | ❌ 8 hrs | Medium | Critical |
| Event sink | ❌ 4 hrs | Low | High |
| Web UI wiring | ❌ 8 hrs | Medium | Medium |
| Docker Compose orchestration | ❌ 4 hrs | Low | High |

---

## 🚀 Immediate Action Items (This Week)

### **TASK 1: Enable Dataplane Binary** (30 minutes)

**Current State**: Validator exists, but binary not accessible

**Action**:
```bash
# 1. Create dataplane directory
mkdir -p /opt/dataplane

# 2. Copy binary from repo to standard location
cp /path/to/dataplane.amd64 /opt/dataplane/dataplane

# 3. Make executable
chmod +x /opt/dataplane/dataplane

# 4. Test binary
/opt/dataplane/dataplane --version  # Should print version info
```

**Verification**:
```bash
# Run test
pytest tests/test_dataplane_validator.py -v

# Expected output:
# test_dataplane_validator.py::test_validate_lua PASSED
# test_dataplane_validator.py::test_ocsf_validation PASSED
```

**Impact**: ✅ All 7-point validations now work, including dataplane runtime

---

### **TASK 2: Fix Web UI Security** (15 minutes)

**Current State**: Auth disabled for testing (production risk)

**Action**:
```python
# File: components/web_feedback_ui.py
# Around line 163

# BEFORE (insecure):
def validate_feedback():
    # TODO: Re-enable authentication
    auth_token = request.headers.get('X-Auth-Token')
    # NOT CHECKED - security testing mode

# AFTER (secure):
def validate_feedback():
    auth_token = request.headers.get('X-Auth-Token')
    if not auth_token or auth_token != os.getenv('WEB_UI_AUTH_TOKEN'):
        return jsonify({"error": "Unauthorized"}), 401

    # ... rest of handler
```

**Verification**:
```bash
# Test without token (should fail)
curl http://localhost:8080/api/validate \
  -H "Content-Type: application/json" \
  -d '{}' \
  # Should return 401 Unauthorized

# Test with token (should succeed)
curl http://localhost:8080/api/validate \
  -H "X-Auth-Token: $WEB_UI_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' \
  # Should process request
```

**Impact**: ✅ Production-ready security posture

---

### **TASK 3: Test End-to-End Validation** (45 minutes)

**Current State**: Components exist, not tested together

**Action**:
```bash
# 1. Update config.yaml
cat > config.yaml << 'EOF'
dataplane:
  enabled: true
  binary_path: "/opt/dataplane/dataplane"
  timeout_seconds: 30
  ocsf_required_fields:
    - class_uid
    - class_name
    - category_uid
    - metadata

processing:
  max_parsers: 2  # Small test
  parser_types: ["community"]
  batch_size: 1
EOF

# 2. Run orchestrator
python main.py --verbose

# 3. Inspect output
find output -name "validation_report.json" -exec jq . {} \;
```

**Expected Output**:
```json
{
  "parser_id": "example_parser",
  "validations": {
    "schema": { "passed": true },
    "lua_syntax": { "passed": true },
    "dataplane_runtime": {
      "status": "success",
      "output_events": [...],
      "ocsf_missing_fields": []
    },
    "field_extraction": { "passed": true },
    "ocsf_compliance": { "passed": true },
    "metadata": { "passed": true }
  },
  "overall_passed": true
}
```

**Impact**: ✅ Validate all 7 points work correctly

---

## 📋 Week 2-3: Activate Runtime Pipeline

### **TASK 4: Implement RuntimeService** (4 hours)

**Current State**: Empty placeholder (40 lines, no functionality)

**File**: `services/runtime_service.py`

**Action**:
```python
"""Enhanced RuntimeService with actual metrics."""

from typing import Dict, Any, Optional
import time
from collections import defaultdict

class RuntimeService:
    """Tracks transform worker runtime metrics in real-time."""

    def __init__(self):
        self.metrics: Dict[str, Dict[str, Any]] = {}
        self.reload_requests: Dict[str, str] = {}
        self.pending_promotions: Dict[str, str] = {}

        # Actual metrics (from transform worker)
        self.parser_metrics: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total_processed": 0,
            "total_errors": 0,
            "last_error": None,
            "last_event_time": None,
            "avg_latency_ms": 0.0,
            "error_rate": 0.0,
            "canary_status": {
                "stable_errors": 0,
                "canary_errors": 0,
                "canary_percentage": 0,
                "ready_for_promotion": False
            }
        })

    def update_parser_metrics(
        self,
        parser_id: str,
        processed: int = 0,
        errors: int = 0,
        last_error: Optional[str] = None,
        latency_ms: float = 0.0
    ) -> None:
        """Update metrics for a parser."""
        if parser_id not in self.parser_metrics:
            self.parser_metrics[parser_id] = {
                "total_processed": 0,
                "total_errors": 0,
                "last_error": None,
                "last_event_time": None,
                "avg_latency_ms": 0.0,
                "error_rate": 0.0,
                "canary_status": {
                    "stable_errors": 0,
                    "canary_errors": 0,
                    "canary_percentage": 0,
                    "ready_for_promotion": False
                }
            }

        m = self.parser_metrics[parser_id]
        m["total_processed"] += processed
        m["total_errors"] += errors
        m["last_error"] = last_error
        m["last_event_time"] = time.time()
        m["avg_latency_ms"] = latency_ms

        if m["total_processed"] > 0:
            m["error_rate"] = m["total_errors"] / m["total_processed"]

    def get_runtime_status(self) -> Dict:
        """Get current runtime status."""
        return {
            "parser_metrics": dict(self.parser_metrics),
            "reload_requests": self.reload_requests,
            "pending_promotions": self.pending_promotions
        }

    def get_parser_status(self, parser_id: str) -> Dict:
        """Get status for specific parser."""
        return self.parser_metrics.get(parser_id, {})

    def request_runtime_reload(self, parser_id: str) -> bool:
        """Request reload of parser transform."""
        self.reload_requests[parser_id] = "pending"
        return True

    def pop_reload_request(self, parser_id: str) -> Optional[str]:
        """Consume reload request."""
        return self.reload_requests.pop(parser_id, None)

    def request_canary_promotion(self, parser_id: str) -> bool:
        """Request promotion of canary to stable."""
        self.pending_promotions[parser_id] = "pending"
        return True

    def pop_canary_promotion(self, parser_id: str) -> Optional[str]:
        """Consume promotion request."""
        return self.pending_promotions.pop(parser_id, None)

    def update_canary_metrics(
        self,
        parser_id: str,
        stable_errors: int,
        canary_errors: int,
        canary_pct: int
    ) -> None:
        """Update canary deployment metrics."""
        if parser_id in self.parser_metrics:
            m = self.parser_metrics[parser_id]
            m["canary_status"]["stable_errors"] = stable_errors
            m["canary_status"]["canary_errors"] = canary_errors
            m["canary_status"]["canary_percentage"] = canary_pct

            # Ready for promotion if canary error rate <= stable
            total_stable = max(1, stable_errors + 1000)  # Assume 1000 baseline
            total_canary = max(1, canary_errors + 100)   # Assume 100 canary

            stable_rate = stable_errors / total_stable
            canary_rate = canary_errors / total_canary

            m["canary_status"]["ready_for_promotion"] = canary_rate <= stable_rate
```

**Wire into Transform Worker**:
```python
# In services/transform_worker.py

async def process_event(self, event: Dict, runtime_service: RuntimeService):
    """Process event with metrics tracking."""
    parser_id = event['_metadata']['parser_id']
    start_time = time.time()

    try:
        result = await self.execute_transform(event)
        latency = (time.time() - start_time) * 1000  # ms

        runtime_service.update_parser_metrics(
            parser_id,
            processed=1,
            latency_ms=latency
        )

        return result
    except Exception as e:
        runtime_service.update_parser_metrics(
            parser_id,
            errors=1,
            last_error=str(e)
        )
        raise
```

**Verification**:
```bash
# Should be wired to web UI
curl http://localhost:8080/api/runtime/status \
  -H "X-Auth-Token: $WEB_UI_AUTH_TOKEN" | jq .
```

**Impact**: ✅ Real-time monitoring in web UI

---

### **TASK 5: Setup Event Processing Pipeline** (8 hours)

**Current State**: Transform worker exists but not receiving events

**Action**: Setup Kafka-based event flow

**Step 1: Start Kafka**
```bash
# Using docker-compose
docker-compose up -d kafka zookeeper

# Verify
docker exec -it kafka-broker kafka-topics.sh \
  --list --bootstrap-server localhost:9092
```

**Step 2: Create Event Topics**
```bash
docker exec -it kafka-broker kafka-topics.sh \
  --create --topic raw-security-events \
  --bootstrap-server localhost:9092 \
  --partitions 3 \
  --replication-factor 1

docker exec -it kafka-broker kafka-topics.sh \
  --create --topic ocsf-events \
  --bootstrap-server localhost:9092 \
  --partitions 3 \
  --replication-factor 1
```

**Step 3: Update Configuration**
```yaml
# config.yaml

message_bus:
  type: "kafka"
  kafka:
    bootstrap_servers: "localhost:9092"
    consumer_group: "pppe-transform-worker"
    auto_offset_reset: "earliest"
    input_topic: "raw-security-events"
    output_topic: "ocsf-events"

transform_worker:
  enabled: true
  executor: "lupa"  # Use lupa (fast) for runtime
  parallelism: 4
  batch_size: 100
  batch_timeout_secs: 5
```

**Step 4: Create Event Producer**
```python
# scripts/produce_sample_events.py

from kafka import KafkaProducer
import json
import time

producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Sample events
events = [
    {
        "_metadata": {"parser_id": "netskope_dlp"},
        "log": {
            "alert_type": "DLP",
            "user": "john@example.com",
            "file": "sensitive.xlsx",
            "severity": "High",
            "action": "quarantine"
        }
    },
    {
        "_metadata": {"parser_id": "netskope_dlp"},
        "log": {
            "alert_type": "Policy",
            "user": "jane@example.com",
            "file": "config.json",
            "severity": "Medium",
            "action": "blocked"
        }
    }
]

# Produce events
for event in events:
    producer.send('raw-security-events', value=event)
    time.sleep(0.5)

producer.flush()
print("Events produced")
```

**Step 5: Start Transform Worker**
```bash
# Terminal 1: Start worker
python start_transform_worker.py \
  --config config.yaml \
  --log-level debug

# Terminal 2: Produce events
python scripts/produce_sample_events.py

# Terminal 3: Consume output
docker exec -it kafka-broker kafka-console-consumer.sh \
  --topic ocsf-events \
  --bootstrap-server localhost:9092 \
  --from-beginning
```

**Expected Output**:
```json
{
  "log": {
    "class_uid": 2004,
    "class_name": "Detection Finding",
    "user": "john@example.com",
    "file": "sensitive.xlsx",
    "severity": "High",
    "message": "{\"alert_type\":\"DLP\", ...}"
  }
}
```

**Impact**: ✅ Live event processing working

---

## 📊 Week 4-6: Production Hardening

### **TASK 6: Web UI Integration** (8 hours)

**Current State**: RuntimeService and API endpoints exist, UI not connected

**Action**: Update Web UI template to show runtime metrics

```html
<!-- In web_feedback_ui.py template -->

<div id="runtime-status">
  <h3>Runtime Status</h3>

  <!-- Per-parser metrics -->
  <table id="parser-metrics">
    <thead>
      <tr>
        <th>Parser</th>
        <th>Events Processed</th>
        <th>Error Rate</th>
        <th>Avg Latency</th>
        <th>Last Error</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody id="metrics-body">
      <!-- Populated via JavaScript -->
    </tbody>
  </table>

  <!-- Canary status -->
  <div id="canary-status">
    <h4>Canary Deployments</h4>
    <table>
      <tr>
        <th>Parser</th>
        <th>Stable Errors</th>
        <th>Canary Errors</th>
        <th>Status</th>
        <th>Action</th>
      </tr>
      <!-- Populated via JavaScript -->
    </table>
  </div>
</div>

<script>
// Fetch runtime status every 5 seconds
setInterval(async () => {
  const response = await fetch('/api/runtime/status', {
    headers: {'X-Auth-Token': authToken}
  });
  const data = await response.json();

  // Update metrics table
  updateMetricsTable(data.parser_metrics);

  // Update canary status
  updateCanaryStatus(data.pending_promotions);
}, 5000);
</script>
```

**Impact**: ✅ Operational visibility

---

### **TASK 7: Docker Compose Orchestration** (4 hours)

**File**: `docker-compose-hybrid.yml`

```yaml
version: '3.8'

services:
  # Message bus
  kafka:
    image: confluentinc/cp-kafka:7.5.0
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT

  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    ports:
      - "2181:2181"
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

  # PPPE Orchestrator + Web UI
  pppe:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8080:8080"
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      WEB_UI_AUTH_TOKEN: ${WEB_UI_AUTH_TOKEN}
      KAFKA_BOOTSTRAP_SERVERS: kafka:29092
    depends_on:
      - kafka
    volumes:
      - ./output:/app/output
      - ./Observo-dataPlane:/opt/dataplane

  # Transform Worker
  transform-worker:
    build:
      context: .
      dockerfile: Dockerfile
    command: python start_transform_worker.py --config config.yaml
    environment:
      KAFKA_BOOTSTRAP_SERVERS: kafka:29092
    depends_on:
      - kafka
      - pppe
    volumes:
      - ./output:/app/output
      - ./Observo-dataPlane:/opt/dataplane
```

**Usage**:
```bash
# Start entire stack
docker-compose -f docker-compose-hybrid.yml up -d

# Check status
docker-compose -f docker-compose-hybrid.yml ps

# View logs
docker-compose -f docker-compose-hybrid.yml logs -f transform-worker
```

**Impact**: ✅ One-command deployment

---

## 📈 Timeline & Effort Summary

| Phase | Tasks | Effort | Value | Week |
|-------|-------|--------|-------|------|
| **Week 1** | Binary setup, security fix, E2E test | 1-2 hrs | ✅ High | Immediate |
| **Week 2-3** | RuntimeService, Kafka pipeline | 12-16 hrs | ✅ Critical | Start ASAP |
| **Week 4-6** | Web UI, Docker Compose, testing | 12-16 hrs | ✅ Medium | Follow-up |
| **TOTAL** | Full hybrid system operational | ~28-34 hrs | ✅ Excellent | 4-6 weeks |

---

## ✅ Success Criteria

- [ ] Dataplane binary accessible at `/opt/dataplane/dataplane`
- [ ] All 7-point validation passes for test parser
- [ ] Web UI enforces authentication
- [ ] RuntimeService tracks real metrics
- [ ] Kafka topics created and topics visible
- [ ] Transform worker starts successfully
- [ ] Sample events processed end-to-end
- [ ] OCSF-compliant output in ocsf-events topic
- [ ] Web UI displays runtime metrics
- [ ] Docker Compose brings up entire stack
- [ ] System handles 1000 events/sec without errors
- [ ] Canary routing works correctly

---

## 🎯 Next Immediate Action

**TODAY:**
1. ✅ Run TASK 1 (binary setup) - 30 min
2. ✅ Run TASK 2 (security fix) - 15 min
3. ✅ Run TASK 3 (E2E test) - 45 min

**Total: ~90 minutes to enable dataplane validation**

Then proceed to Tasks 4-7 in parallel over weeks 2-6.

---

## Questions?

- **Q**: Can I start with just validation (TASK 1-3)?
- **A**: Yes! Complete those first, then events processing follows naturally.

- **Q**: Can I use different message bus?
- **A**: Yes! Redis Streams or in-memory queue work via adapter pattern.

- **Q**: Do I need Docker Compose?
- **A**: No, but it simplifies operational management at scale.

- **Q**: What about AWS deployment?
- **A**: After local setup, follow AWS Production Roadmap in `Hybrid_Architecture_Plan.md`.

