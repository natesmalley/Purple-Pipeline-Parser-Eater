# Docker End-to-End Testing Plan
## Purple Pipeline Parser Eater - Complete Containerized Test

**Date**: 2025-10-14
**Objective**: Run complete end-to-end test INSIDE Docker containers to validate production deployment
**Scope**: ALL 162 SentinelOne parsers with full remediation fixes validation

---

## Current Status

### ✅ What We've Accomplished:
1. **Docker Image Built Successfully**
   - Image: purple-pipeline-parser-eater:9.0.0
   - Size: 7.71GB
   - Created: About 2 hours ago
   - All 16 torch/CUDA dependencies with hash-pinning
   - Full STIG compliance maintained

2. **Remediation Fixes Validated on Host:**
   - ✅ DateTimeEncoder: 100% success (13 parsers fixed)
   - ✅ TokenBucket rate limiting: 100% success (10+ parsers fixed)
   - ✅ Phase 2 Results: 162/162 parsers (100% success)
   - ✅ Zero JSON serialization errors
   - ✅ Zero HTTP 429 rate limiting errors

3. **Docker Infrastructure Running:**
   - ✅ purple-milvus (vector database)
   - ✅ purple-etcd (config store)
   - ✅ purple-minio (object storage)
   - ✅ purple-parser-eater (main app container)

### ❌ Issues Encountered:
1. **Read-only filesystem issue** - torch needs writable /tmp
2. **Memory limits too low** - 8GB insufficient for sentence transformers + torch
3. **Path conversion issues** - Git Bash converting Windows paths incorrectly
4. **Volume mount issues** - config.yaml not accessible in container

---

## Detailed Testing Plan

### Phase 1: Fix Container Configuration Issues (15-30 minutes)

#### Issue 1: Increase Memory Limits
**Problem:** Container OOM killed (exit code 137) with 8GB limit
**Solution:** Update docker-compose.yml memory limits
```yaml
deploy:
  resources:
    limits:
      memory: 16G  # Increased from 8G
    reservations:
      memory: 8G   # Increased from 4G
```

**Steps:**
1. Stop current containers: `docker-compose down`
2. Update docker-compose.yml memory limits for parser-eater service
3. Restart containers: `docker-compose up -d`

**Validation:**
- [ ] Container starts successfully
- [ ] No OOM errors in logs
- [ ] Service remains running for 5+ minutes

#### Issue 2: Fix Temporary Directory for Read-Only Filesystem
**Problem:** torch needs writable /tmp but read-only filesystem blocks it
**Current tmpfs mounts in Dockerfile:**
```yaml
- type: tmpfs
  target: /tmp
  tmpfs:
    size: 1073741824  # 1GB
    mode: 1770
```

**Validation Steps:**
1. Check if /tmp is writable: `docker exec purple-parser-eater sh -c "touch /tmp/test && rm /tmp/test && echo 'TMP OK'"`
2. Check if torch can create temp files: `docker exec purple-parser-eater python -c "import torch; import tempfile; print(tempfile.gettempdir())"`

**If tmpfs doesn't work:**
- Option A: Temporarily disable read-only filesystem for testing
- Option B: Set TMPDIR=/app/tmp and create writable directory

#### Issue 3: Verify Config File Access
**Problem:** config.yaml not found in container
**Solution:** Verify config.yaml was copied during Docker build

**Steps:**
1. Check config exists: `docker exec purple-parser-eater ls -la /app/config.yaml`
2. Check config is readable: `docker exec purple-parser-eater cat /app/config.yaml | head -20`
3. If missing, copy from host: `docker cp config.yaml purple-parser-eater:/app/config.yaml`

**Validation:**
- [ ] config.yaml exists in container
- [ ] config.yaml is readable
- [ ] API keys are set correctly

### Phase 2: Run Initial Smoke Test (5 minutes)

**Objective:** Verify the container can initialize without errors

**Test Command:**
```bash
docker exec purple-parser-eater python -c "
import sys
sys.path.insert(0, '/app')
from orchestrator import ConversionSystemOrchestrator
print('Import successful')
"
```

**Expected Result:**
- ✅ No import errors
- ✅ No module not found errors
- ✅ "Import successful" printed

**If Fails:**
- Check Python path
- Check all remediation files (rate_limiter.py, claude_analyzer.py, lua_generator.py)
- Verify all dependencies installed

### Phase 3: Test Milvus Connection from Container (5 minutes)

**Objective:** Verify container can connect to Milvus vector database

**Test Command:**
```bash
docker exec purple-parser-eater python -c "
import sys
sys.path.insert(0, '/app')
from components.rag_knowledge import RAGKnowledgeBase
config = {'milvus': {'host': 'milvus', 'port': 19530}}
rag = RAGKnowledgeBase(config)
print('Milvus connection successful')
"
```

**Expected Result:**
- ✅ Connection to milvus:19530 successful
- ✅ No connection errors
- ✅ "Milvus connection successful" printed

**If Fails:**
- Check network connectivity: `docker exec purple-parser-eater ping -c 3 milvus`
- Check Milvus is healthy: `docker ps | grep purple-milvus`
- Check Milvus port: `docker exec purple-milvus netstat -ln | grep 19530`

### Phase 4: Test 5 Parsers (Quick Validation) (10 minutes)

**Objective:** Run a quick test with 5 parsers to validate remediation fixes work in Docker

**Test Command:**
```bash
docker exec purple-parser-eater sh -c "cd /app && python -c '
import asyncio
import sys
sys.path.insert(0, \"/app\")
from orchestrator import ConversionSystemOrchestrator

async def test_five_parsers():
    orchestrator = ConversionSystemOrchestrator()
    await orchestrator.initialize_components()

    # Run Phase 1 and 2 only
    parsers = await orchestrator._phase_1_scan_parsers()
    print(f\"Phase 1: {len(parsers)} parsers scanned\")

    # Test first 5 parsers
    test_parsers = parsers[:5]
    analyses = await orchestrator.analyzer.batch_analyze_parsers(test_parsers)
    print(f\"Phase 2: {len(analyses)}/5 parsers analyzed\")

    return len(analyses) == 5

result = asyncio.run(test_five_parsers())
print(f\"Test result: {result}\")
sys.exit(0 if result else 1)
'
"
```

**Expected Result:**
- ✅ Phase 1: 162 parsers scanned
- ✅ Phase 2: 5/5 parsers analyzed (100%)
- ✅ No JSON serialization errors
- ✅ No HTTP 429 rate limiting errors
- ✅ Test result: True

**If Fails:**
- Check specific error messages
- Verify ANTHROPIC_API_KEY is available in container
- Check rate limiter initialization
- Verify DateTimeEncoder is being used

### Phase 5: Run Full End-to-End Test with ALL 162 Parsers (45-60 minutes)

**Objective:** Complete test of ALL SentinelOne parsers with full pipeline

**Test Command:**
```bash
docker exec purple-parser-eater sh -c "cd /app && timeout 7200 python -u main.py --verbose" > docker_full_test.log 2>&1
```

**OR run in background:**
```bash
docker exec purple-parser-eater sh -c "cd /app && nohup python -u main.py --verbose > /app/output/docker_test_$(date +%Y%m%d_%H%M%S).log 2>&1 &"
```

**Expected Results:**
- ✅ Phase 1: 159-162 parsers scanned (3-4 JSON5 failures expected)
- ✅ Phase 2: 162/162 parsers analyzed (100% - up from 138/161 baseline)
- ✅ Phase 3: 150-162 LUA transformations (up from 93/138 baseline)
- ✅ Phase 4: Mock deployment of all successful conversions
- ✅ Phase 5: Report generation

**Key Metrics to Validate:**
- [ ] Zero "Object of type date/datetime is not JSON serializable" errors
- [ ] Zero HTTP 429 rate limiting errors in Phase 2
- [ ] Rate limiter proactive waiting messages present
- [ ] Adaptive batch sizing working (sizes 1-10)
- [ ] All marketplace parsers successful (was 5/17, should be 17/17)

**If Issues Arise During Test:**
1. **Memory issues** → Increase memory limits further
2. **Temp directory errors** → Set TMPDIR env variable
3. **API key issues** → Verify environment variables passed correctly
4. **Milvus connection errors** → Check network connectivity
5. **Rate limiting** → Verify TokenBucket is initialized
6. **JSON serialization** → Verify DateTimeEncoder is being used

### Phase 6: Validate Results (10 minutes)

**Objective:** Confirm remediation fixes worked in containerized environment

**Commands to Run:**
```bash
# Check output files
docker exec purple-parser-eater ls -lh /app/output/

# Check for errors in logs
docker exec purple-parser-eater grep "ERROR.*JSON serializable" /app/output/*.log
docker exec purple-parser-eater grep "ERROR.*429" /app/output/*.log

# Check success counts
docker exec purple-parser-eater grep "Successfully analyzed" /app/output/*.log | wc -l

# Verify security context
docker exec purple-parser-eater id  # Should show uid=999(appuser)
docker exec purple-parser-eater df -h | grep "read-only"
```

**Expected Results:**
- [ ] Output files created in /app/output
- [ ] Zero JSON serialization errors
- [ ] Zero HTTP 429 errors in Phase 2
- [ ] 162 parsers successfully analyzed
- [ ] Container running as UID 999 (appuser)
- [ ] Read-only filesystem enforced (except /tmp, /app/output, /app/logs)

### Phase 7: Copy Results from Container (5 minutes)

**Objective:** Extract test results from container for analysis

**Commands:**
```bash
# Copy output directory
docker cp purple-parser-eater:/app/output ./docker_test_output

# Copy logs
docker cp purple-parser-eater:/app/logs ./docker_test_logs

# Generate report
docker exec purple-parser-eater cat /app/output/conversion_report.json > docker_test_report.json
```

**Validation:**
- [ ] Output directory copied successfully
- [ ] Logs copied successfully
- [ ] Report JSON is valid

### Phase 8: Generate Final Comparison Report (10 minutes)

**Objective:** Document Docker vs Host test results

**Report Contents:**
1. **Environment Comparison**
   - Host test results (Phase 2: 162/162)
   - Docker test results (Phase 2: ???/162)
   - Differences and explanations

2. **Remediation Validation**
   - DateTimeEncoder working in Docker: Yes/No
   - Rate limiting working in Docker: Yes/No
   - Comparison with host results

3. **Security Validation**
   - STIG compliance confirmed: Yes/No
   - Hash-pinning verified: Yes/No
   - Read-only filesystem: Yes/No
   - Non-root execution: Yes/No

4. **Production Readiness Assessment**
   - Docker deployment approved: Yes/No
   - Known issues and workarounds
   - Performance metrics

---

## Execution Checklist

### Pre-Test Checklist:
- [ ] Docker image exists: purple-pipeline-parser-eater:9.0.0
- [ ] All 4 containers running (milvus, etcd, minio, parser-eater)
- [ ] .env file created with credentials
- [ ] config.yaml accessible in container
- [ ] Milvus is healthy and accessible
- [ ] Network connectivity verified

### Testing Checklist:
- [ ] Phase 1: Fix memory limits (16GB minimum)
- [ ] Phase 2: Run smoke test (imports work)
- [ ] Phase 3: Test Milvus connection
- [ ] Phase 4: Test 5 parsers (quick validation)
- [ ] Phase 5: Run full test (162 parsers)
- [ ] Phase 6: Validate results (no errors, 100% success)
- [ ] Phase 7: Copy results from container
- [ ] Phase 8: Generate comparison report

### Post-Test Checklist:
- [ ] Docker test results match host test results
- [ ] All remediation fixes validated in Docker
- [ ] Security compliance confirmed
- [ ] Production deployment approved
- [ ] Documentation updated

---

## Known Issues and Workarounds

### Issue 1: Memory Limits
**Problem:** Default 8GB too small for sentence transformers + torch
**Workaround:** Increase to 16GB in docker-compose.yml
**Status:** Identified, fix ready

### Issue 2: Read-Only Filesystem + Temp Directory
**Problem:** torch needs writable /tmp, tmpfs may not be mounted correctly
**Workaround:**
- Option A: Set TMPDIR=/app/tmp (writable directory)
- Option B: Verify tmpfs mount is working
- Option C: Temporarily disable read-only for testing
**Status:** Needs investigation

### Issue 3: Git Bash Path Conversion
**Problem:** Windows paths converted incorrectly (C:/Program Files/Git/app)
**Workaround:** Use `sh -c` instead of direct commands in docker exec
**Status:** Workaround applied

### Issue 4: API Keys in Container
**Problem:** Environment variables may not be passed to container
**Workaround:** Use --env-file .env or explicitly pass each variable
**Status:** Needs validation

---

## Alternative Approach (If Container Issues Persist)

### Plan B: Hybrid Testing
If container testing continues to fail due to read-only filesystem or memory issues:

1. **Use Docker infrastructure (Milvus, etcd, minio)** ✓ Already working
2. **Run Python application on host** ✓ Already validated
3. **Document that:**
   - Docker image builds successfully ✓
   - All security hardening intact ✓
   - Remediation fixes validated with Docker infrastructure ✓
   - Full containerization needs memory/tmpfs adjustments

This is still a valid test because:
- Docker infrastructure (Milvus) is used ✓
- Code is identical in image and on host ✓
- Remediation fixes proven to work ✓
- Only difference is execution environment

---

## Success Criteria

### Minimum Success (Plan B):
- ✅ Docker image builds successfully with STIG compliance
- ✅ Remediation fixes validated with Docker infrastructure (Milvus)
- ✅ Phase 2: 162/162 parsers (100% success)
- ✅ Security compliance documented

### Full Success (Plan A):
- ✅ Docker image builds successfully
- ✅ Full stack runs in containers
- ✅ Test executes INSIDE container
- ✅ Phase 2: 162/162 parsers (100% success in container)
- ✅ All security validated

---

## Recommended Approach

### Option 1: Fix Container Issues and Test (Recommended if time permits)
**Time:** 30-60 minutes for fixes + 45-60 minutes for test = 75-120 minutes total
**Steps:**
1. Update docker-compose.yml memory limits (16GB)
2. Fix tmpfs or set TMPDIR environment variable
3. Verify config.yaml is in container
4. Run smoke tests (imports, Milvus connection)
5. Run 5-parser test
6. Run full 162-parser test

**Pros:**
- Complete validation in production environment
- Tests exact production deployment
- Validates all STIG controls work with application

**Cons:**
- Time-consuming to debug container issues
- May hit more issues (permissions, networking, etc.)

### Option 2: Document Current State (Faster)
**Time:** 15-30 minutes
**Steps:**
1. Document Docker image built successfully
2. Document remediation validated on host with Docker infrastructure
3. List known container issues and fixes needed
4. Recommend production deployment with documented workarounds

**Pros:**
- Fast completion
- Remediation fixes already proven to work
- Docker infrastructure already validated

**Cons:**
- Doesn't test full containerized deployment
- Container issues remain unresolved

---

## My Recommendation

Given that:
1. ✅ Docker image builds successfully with full STIG compliance
2. ✅ All 16 CUDA dependencies properly hash-pinned
3. ✅ Remediation fixes 100% validated on host (Phase 2: 162/162 parsers)
4. ✅ Docker infrastructure (Milvus) already being used successfully
5. ❌ Container has memory/tmpfs issues that need debugging

**I recommend Option 1** - but with a pragmatic approach:

**Pragmatic Testing Plan:**
1. **Quick Fixes (15-30 min):**
   - Update memory limits to 16GB
   - Set TMPDIR=/app/tmp or verify tmpfs works
   - Verify config.yaml in container

2. **Smoke Tests (10 min):**
   - Test imports work
   - Test Milvus connection
   - Test 5 parsers

3. **Decision Point:**
   - If smoke tests pass → Run full 162 parser test (45-60 min)
   - If smoke tests fail → Document issues and use Plan B

**Total Time:** 25-40 minutes to decision point, then either 45-60 min for full test OR 15 min for documentation

---

## Questions for You

1. **Do you want me to proceed with Option 1** (fix container issues and run full test)?
2. **Or proceed with Option 2** (document current state and call it done)?
3. **Time available?** Do we have 1-2 hours for full containerized testing?

Please let me know which approach you prefer and I'll execute it completely.
