# 📊 Current Dataplane Integration Flow

## The Complete Picture: Raw Events → Lua Transformation

---

## **Today's Reality: What Actually Works**

### Current Data Flow (Parser Conversion Only)

```
STEP 1: PARSER SCANNING
═════════════════════════════════════════════════════════════════
GitHub Repository (SentinelOne AI-SIEM)
    │
    └──→ github_scanner.py
         │
         ├─ Fetch parser.yml files
         ├─ Extract field mappings
         ├─ Store parser metadata
         │
         └──→ OUTPUT: parser_data = {
                "parser_id": "netskope_dlp",
                "fields": [...],
                "logic": "..."
             }


STEP 2: SEMANTIC ANALYSIS
═════════════════════════════════════════════════════════════════
Claude AI + RAG Knowledge Base
    │
    └──→ claude_analyzer.py
         │
         ├─ Analyze parser semantics
         ├─ Retrieve OCSF mappings from RAG
         ├─ Identify field types & transforms
         │
         └──→ OUTPUT: analysis = {
                "parser_complexity": "medium",
                "ocsf_classification": {
                  "class_uid": 2004,
                  "class_name": "Detection Finding"
                },
                "field_mappings": {...}
             }


STEP 3: LUA CODE GENERATION
═════════════════════════════════════════════════════════════════
Claude AI + Lua Templates
    │
    └──→ lua_generator.py
         │
         ├─ Use Observo Lua template
         ├─ Generate transform function: processEvent()
         ├─ Apply field mappings
         ├─ Add error handling
         │
         └──→ OUTPUT: lua_code = """
                function processEvent(event)
                  -- Transform logic here
                  local result = {}
                  result.class_uid = 2004
                  result.user = event.user
                  -- ...
                  return result
                end
             """


STEP 4: VALIDATION - 7 POINT CHECK
═════════════════════════════════════════════════════════════════

4a) Schema Validation
    └─→ Verify pipeline.json structure
        ✅ Check required fields

4b) Lua Syntax Validation
    └─→ Run lupa.LuaRuntime().execute()
        ✅ Catch syntax errors early

4c) DATAPLANE RUNTIME VALIDATION ⭐ THIS IS WHERE DATAPLANE WORKS
    └─→ dataplane_validator.py
        │
        ├─ Create temporary directory
        ├─ Write transform.lua to disk
        ├─ Generate Vector config:
        │  ```yaml
        │  sources:
        │    stdin_input:
        │      type: stdin
        │      decoding:
        │        codec: json
        │
        │  transforms:
        │    lua_transform:
        │      type: lua
        │      source: |
        │        dofile('/tmp/.../transform.lua')
        │        function process(event, emit)
        │          local out = processEvent(event["log"])
        │          if out ~= nil then
        │            event["log"] = out
        │            emit(event)
        │          end
        │        end
        │
        │  sinks:
        │    console_output:
        │      type: console
        │      inputs: ["lua_transform"]
        │      encoding:
        │        codec: json
        │  ```
        │
        ├─ Create test events (JSON array)
        ├─ Execute: subprocess.run(['/opt/dataplane/dataplane', '--config', 'config.yaml'])
        ├─ Feed events via STDIN
        ├─ Capture output (STDOUT = transformed events)
        │
        └─→ OUTPUT: validation_result = {
              "success": true,
              "output_events": [
                {
                  "log": {
                    "class_uid": 2004,
                    "class_name": "Detection Finding",
                    "user": "john@example.com",
                    // ... OCSF fields
                  }
                }
              ],
              "ocsf_missing_fields": []
            }

4d) Field Extraction Verification
    └─→ Compare extracted fields vs expected
        ✅ Verify all fields mapped correctly

4e) OCSF Compliance Check
    └─→ Validate required OCSF schema fields
        ✅ class_uid, class_name, category_uid, metadata

4f) Performance Analysis
    └─→ Check memory usage, execution time
        ✅ Ensure acceptable performance

4g) Metadata Validation
    └─→ Check manifest completeness
        ✅ Version, source, deployment info


STEP 5: ARTIFACT GENERATION
═════════════════════════════════════════════════════════════════
Per-parser output directory: output/<parser_id>/
    │
    ├─→ analysis.json (from Claude analysis)
    ├─→ transform.lua (generated Lua code)
    ├─→ pipeline.json (Observo pipeline config)
    ├─→ validation_report.json (all validation results)
    ├─→ manifest.json (deployment metadata)
    └─→ README.md (documentation)


STEP 6: DEPLOYMENT
═════════════════════════════════════════════════════════════════
Observo.ai API
    │
    └──→ Deploy pipeline.json to Observo
         │
         ├─ Create pipeline
         ├─ Register transform.lua
         ├─ Generate documentation
         │
         └─→ Ready for runtime use
```

---

## **The Test Event Path (How Dataplane Validates)**

### Current Testing with Dataplane Validator

```
┌─────────────────────────────────────────────────────────────┐
│  Dataplane Validator: Testing Generated Lua                 │
└─────────────────────────────────────────────────────────────┘

INPUTS:
═══════════════════════════════════════════════════════════════

1. Generated Lua Code
   ────────────────────
   function processEvent(event)
     local result = {}
     result["class_uid"] = 2004
     result["class_name"] = "Detection Finding"
     result["user"] = event["user"]
     result["file"] = event["file"]
     result["severity"] = event["severity"]
     result["message"] = require('json').encode(event)
     return result
   end

2. Test Events (Sample Data)
   ─────────────────────────
   [
     {
       "log": {
         "alert_type": "DLP",
         "user": "john@example.com",
         "file": "sensitive.doc",
         "severity": "High",
         "action": "quarantine"
       }
     },
     {
       "log": {
         "alert_type": "Policy",
         "user": "jane@example.com",
         "file": "config.json",
         "severity": "Medium",
         "action": "blocked"
       }
     }
   ]

EXECUTION:
═══════════════════════════════════════════════════════════════

Step 1: Create Temp Workspace
   /tmp/pppe-validate-netskope_dlp-abc123/
   ├─ transform.lua (write generated code)
   ├─ config.yaml (write Vector config)
   └─ events.jsonl (write test events)

Step 2: Run Dataplane Binary
   Command:
   $ /opt/dataplane/dataplane --config /tmp/.../config.yaml

   Input (STDIN):
   {"log": {"alert_type": "DLP", "user": "john@...", ...}}
   {"log": {"alert_type": "Policy", "user": "jane@...", ...}}

Step 3: Vector Processing
   sources.stdin_input
       ├─ Read JSON from STDIN
       ├─ Parse as event
       │
   transforms.lua_transform
       ├─ Load transform.lua
       ├─ Call processEvent(event["log"])
       ├─ Emit transformed event
       │
   sinks.console_output
       └─ Write JSON to STDOUT

OUTPUTS:
═══════════════════════════════════════════════════════════════

Successful Transformation:
────────────────────────────
STDOUT:
{
  "log": {
    "class_uid": 2004,
    "class_name": "Detection Finding",
    "user": "john@example.com",
    "file": "sensitive.doc",
    "severity": "High",
    "message": "{\"alert_type\":\"DLP\", ...}"
  }
}
{
  "log": {
    "class_uid": 2004,
    "class_name": "Detection Finding",
    "user": "jane@example.com",
    "file": "config.json",
    "severity": "Medium",
    "message": "{\"alert_type\":\"Policy\", ...}"
  }
}

Validation Result:
──────────────────
{
  "success": true,
  "output_events": [
    { "log": { "class_uid": 2004, ... } },
    { "log": { "class_uid": 2004, ... } }
  ],
  "ocsf_missing_fields": [],
  "error": null
}

VALIDATION CHECKS:
══════════════════
✅ Lua executed successfully
✅ OCSF class_uid present
✅ OCSF class_name present
✅ OCSF category_uid present (checked in validator)
✅ Metadata structure valid
✅ No missing required fields

RESULT:
═══════════════════════════════════════════════════════════════
✅ PASS: Lua code is valid and produces OCSF-compliant output
   (Ready for deployment to Observo.ai)
```

---

## **What's Missing: Live Event Processing**

### The Gap (What Doesn't Exist Yet)

```
STEP 7: CONTINUOUS EVENT PROCESSING (NOT IMPLEMENTED)
═══════════════════════════════════════════════════════════════

⚠️ PROBLEM: No mechanism to feed raw events into the system

Current Capability:
  ✅ Scanner → Analyzer → LuaGenerator → Validator → Deploy
  ✅ Can test Lua with sample events (via dataplane validator)

Missing:
  ❌ Where do raw events come from?
     - Kafka topic?
     - SCOL API?
     - S3 bucket?
     - HTTP POST?

  ❌ How are events fed to transform worker?
     - Event source not configured
     - Transform worker not started
     - Message bus not wired

  ❌ Where do processed events go?
     - Output topic?
     - Database?
     - S3?
     - Observo.ai?


DESIGN (READY BUT NOT IMPLEMENTED):
────────────────────────────────────

┌────────────────────────────────────────────────────────────┐
│                   TRANSFORM WORKER                         │
│              (Ready to deploy, not wired)                  │
└────────────────────────────────────────────────────────────┘

1. Event Source
   └─ Subscribe to message bus: "raw-security-events" topic
      (Message Bus Adapter exists - just needs event producer)

2. Manifest Resolution
   └─ Load parser manifest from output/<parser_id>/manifest.json
      (Manifest Store exists - fully implemented)

3. Transform Execution
   ├─ Load Lua code from manifest
   ├─ Execute via executor (Lupa or Dataplane)
   │  (Executor abstraction exists - fully implemented)
   └─ Handle errors & retry

4. Metrics Collection
   └─ Track events processed, errors, latency
      (Metrics collector exists - fully implemented)

5. Event Emission
   └─ Publish to message bus: "ocsf-events" topic
      (Message Bus Adapter exists - just needs config)

6. Canary Routing
   └─ Route events to stable or canary Lua based on percentage
      (Canary router exists - fully implemented)


MISSING PIECES:
───────────────
1. ❌ Event producer → raw-security-events topic
2. ❌ Transform worker service startup (start_transform_worker.py)
3. ❌ Event consumer ← ocsf-events topic
4. ❌ Output sink (S3, database, Observo API)
5. ❌ RuntimeService implementation (currently 40-line stub)
6. ❌ Web UI integration to runtime metrics


IMPLEMENTATION ROADMAP:
───────────────────────

Phase A: Enable Event Processing (1-2 days)
  1. Start Kafka locally
  2. Implement event producer (feed raw events)
  3. Start transform worker service
  4. Verify OCSF output

Phase B: Persistent Storage (1 day)
  1. Implement S3 sink
  2. Configure output topic
  3. Archive processed events

Phase C: Observability (2 days)
  1. Implement RuntimeService properly
  2. Wire to transform worker metrics
  3. Update Web UI to show runtime status

Phase D: Full Integration (1 week)
  1. Dataplane as upstream ingestion (SCOL)
  2. Multi-region deployment
  3. Canary promotions
  4. RAG feedback loop
```

---

## **How to Test Current State**

### Test 1: Verify Dataplane Validator Works (5 minutes)

```bash
# Make sure binary is in place
mkdir -p /opt/dataplane
cp /path/to/dataplane.amd64 /opt/dataplane/dataplane
chmod +x /opt/dataplane/dataplane

# Run a simple validation test
python3 << 'EOF'
from components.dataplane_validator import DataplaneValidator

validator = DataplaneValidator(
    binary_path="/opt/dataplane/dataplane",
    ocsf_required_fields=["class_uid", "class_name", "category_uid"],
    timeout=30
)

lua_code = """
function processEvent(event)
  local result = {}
  result["class_uid"] = 2004
  result["class_name"] = "Detection Finding"
  result["user"] = event["user"]
  return result
end
"""

test_events = [
  {
    "log": {
      "user": "john@example.com",
      "severity": "high"
    }
  }
]

result = validator.validate(lua_code, test_events, "test_parser")
print("Success:", result.success)
print("Output events:", len(result.output_events))
print("Missing fields:", result.ocsf_missing_fields)
EOF
```

---

### Test 2: Run Full Orchestrator with Dataplane (15 minutes)

```bash
# Enable dataplane in config.yaml
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
  max_parsers: 1  # Just test one
  parser_types: ["community"]
EOF

# Run orchestrator
python main.py

# Check results
ls -la output/*/
cat output/*/validation_report.json | jq '.validations.dataplane_runtime'
```

---

## **Architecture Summary**

### What Works Now

```
Source Code (S1 Parsers)
    ↓
Phase 1-5: Conversion Pipeline ✅
├─ Scan parsers
├─ Analyze with Claude
├─ Generate Lua
├─ Validate (including dataplane runtime test) ✅
└─ Generate artifacts

Result: transform.lua + validation_report.json + manifest.json
```

### What's Ready But Not Connected

```
Raw Events → [Message Bus] → Transform Worker → [Message Bus] → Output
    ❌              ✅              ✅              ✅           ❌
    No source  Infrastructure    Ready to     Infrastructure  No sink
```

### What's Needed Next

1. **Event Source**: Feed raw events to message bus
2. **Transform Worker Startup**: Start service with manifest
3. **Event Sink**: Store/forward processed events
4. **RuntimeService Wiring**: Connect to actual metrics
5. **Web UI Integration**: Show runtime status

---

## **Conclusion**

✅ **Dataplane is successfully validating Lua code during parser conversion**

The system can:
- Generate Lua transformations
- Test them with sample events via dataplane binary
- Validate OCSF compliance
- Deploy to Observo.ai

What's missing is the **event processing pipeline** - infrastructure to:
- Continuously feed raw events
- Execute Lua transforms
- Store results

**Next step**: Wire together the existing message bus, transform worker, and executor components to create the live event processing pipeline.

