# Docker Container Testing Plan
## Purple Pipeline Parser Eater - Production Containerized Testing

**Date**: 2025-10-13
**Objective**: Run full remediation validation tests inside Docker containers to validate production deployment
**Requirement**: MANDATORY - All tests must run in containerized environment

---

## Current Situation Analysis

### What We Have Now

**Docker Containers Running**:
1. ✅ purple-milvus (Milvus vector database) - Port 19530
2. ✅ purple-etcd (Configuration store)
3. ✅ purple-minio (Object storage)

**What's Missing**:
❌ purple-parser-eater container (main application) - NOT RUNNING

**Previous Tests**:
- ⚠️ Tests ran on Windows host (NOT in container)
- ⚠️ Connected to Milvus in Docker (hybrid setup)
- ⚠️ NOT a valid production test

### Why This Is Critical

**Security Compliance**:
- STIG hardening only applies inside containers
- Read-only filesystem enforcement
- Non-root user execution (UID 999)
- Capability restrictions
- Resource limits

**Validation Requirements**:
- Must test with STIG-hardened container
- Must test with read-only root filesystem
- Must test with restricted capabilities
- Must test with proper networking isolation
- Must validate all security controls work with remediation fixes

---

## Docker Build Issue Analysis

### The Problem

Docker build fails with:
```
ERROR: In --require-hashes mode, all requirements must have their versions pinned with ==. These do not:
    hf-xet<2.0.0,>=1.1.3 from huggingface-hub==0.35.3
```

**Root Cause**:
- requirements.txt uses hash-pinned dependencies (security requirement)
- huggingface-hub has transitive dependency `hf-xet` without pinned hash
- This is a **security vs. convenience trade-off**

### Solution Options

**Option 1: Fix requirements.txt (RECOMMENDED - NO SECURITY COMPROMISE)**
- Pin hf-xet==1.1.10 with hash in requirements.txt
- Maintains hash-pinning security
- No Dockerfile changes needed
- Time: 15-30 minutes

**Option 2: Use existing image (if available)**
- Check if purple-pipeline-parser-eater:9.0.0 image exists locally
- Use existing image without rebuild
- Time: 1 minute

**Option 3: Build without hash checking (NOT RECOMMENDED - SECURITY RISK)**
- Remove --require-hashes from pip install
- ❌ COMPROMISES SECURITY
- ❌ VIOLATES STIG compliance
- ❌ DO NOT USE

---

## Detailed Testing Plan (Using Docker Containers)

### Phase 1: Fix Docker Build (15-30 minutes)

**Step 1.1**: Check for existing Docker image
```bash
docker images | grep purple-pipeline-parser-eater
```

**Step 1.2**: If no image exists, fix requirements.txt to pin hf-xet
```bash
# Add to requirements.txt with proper hash:
hf-xet==1.1.10 \
    --hash=sha256:XXXXX...
```

**Step 1.3**: Rebuild Docker image (preserving all security hardening)
```bash
docker-compose build parser-eater
```

**Validation**:
- [ ] Image builds successfully
- [ ] No security settings modified in Dockerfile
- [ ] STIG hardening preserved
- [ ] Hash-pinning maintained

### Phase 2: Start Full Docker Stack (5 minutes)

**Step 2.1**: Create .env file with credentials
```bash
# .env file
ANTHROPIC_API_KEY=your-key-here
GITHUB_TOKEN=your-token-here
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
OBSERVO_API_KEY=dry-run-mode
WEB_UI_AUTH_TOKEN=test-token
```

**Step 2.2**: Start all containers
```bash
docker-compose up -d
```

**Step 2.3**: Verify all containers healthy
```bash
docker-compose ps
docker-compose logs parser-eater
```

**Validation**:
- [ ] All 4 containers running (milvus, etcd, minio, parser-eater)
- [ ] All containers healthy
- [ ] parser-eater logs show initialization success
- [ ] Milvus connection successful

### Phase 3: Run Tests Inside Container (1-2 hours)

**Step 3.1**: Execute test inside container
```bash
docker-compose exec parser-eater python main.py --verbose
```

**OR** run as one-off command:
```bash
docker-compose run --rm parser-eater python main.py --verbose
```

**Step 3.2**: Monitor container logs in real-time
```bash
docker-compose logs -f parser-eater
```

**Step 3.3**: Validate security context
```bash
# Check running as non-root
docker-compose exec parser-eater whoami
# Expected: appuser

# Check read-only filesystem
docker-compose exec parser-eater touch /test-readonly
# Expected: Error (read-only filesystem)

# Check user ID
docker-compose exec parser-eater id
# Expected: uid=999(appuser) gid=999(appuser)
```

**Validation**:
- [ ] Test runs inside container (not on host)
- [ ] Container runs as user 999 (appuser)
- [ ] Read-only filesystem enforced
- [ ] Milvus connection works from container
- [ ] All remediation fixes work in containerized environment
- [ ] Phase 2: 162/162 parsers analyzed (100%)
- [ ] No JSON serialization errors
- [ ] No HTTP 429 rate limiting errors

### Phase 4: Collect Results (10 minutes)

**Step 4.1**: Copy output from container
```bash
docker cp purple-parser-eater:/app/output ./docker-test-output
docker cp purple-parser-eater:/app/logs ./docker-test-logs
```

**Step 4.2**: Generate test report
```bash
docker-compose exec parser-eater python -c "
import json
with open('/app/output/conversion_report.json', 'r') as f:
    report = json.load(f)
    print(json.dumps(report, indent=2))
"
```

**Step 4.3**: Verify security compliance
```bash
# Check no files written to read-only areas
docker-compose exec parser-eater ls -la /

# Check process running as correct user
docker-compose exec parser-eater ps aux

# Check no new capabilities
docker inspect purple-parser-eater | grep -i cap
```

**Validation**:
- [ ] All output files in /app/output volume
- [ ] No files written to read-only filesystem
- [ ] Process running as UID 999
- [ ] Security restrictions maintained
- [ ] Test results match host test results

### Phase 5: Cleanup & Documentation (5 minutes)

**Step 5.1**: Stop containers
```bash
docker-compose down
```

**Step 5.2**: Generate final report documenting:
- Container test results
- Security compliance validation
- Comparison with host test results
- Production deployment approval

---

## Alternative: Fix requirements.txt Hash Issue

If we need to rebuild, here's the proper fix WITHOUT compromising security:

**Step 1**: Generate hash for hf-xet==1.1.10
```bash
pip hash hf-xet==1.1.10
```

**Step 2**: Add to requirements.txt (maintaining hash-pinning)
```
hf-xet==1.1.10 \
    --hash=sha256:GENERATED_HASH_HERE
```

**Step 3**: Update huggingface-hub line to NOT pull hf-xet as transitive
```
# In requirements.txt, change:
huggingface-hub==0.35.3 \
    --hash=sha256:HASH

# To explicitly list both:
huggingface-hub==0.35.3 \
    --hash=sha256:HASH
hf-xet==1.1.10 \
    --hash=sha256:NEW_HASH
```

This maintains STIG compliance and hash-pinning security while fixing the build.

---

## Testing Checklist

### Pre-Test Validation
- [ ] Dockerfile unchanged (security hardening preserved)
- [ ] docker-compose.yml unchanged (STIG controls preserved)
- [ ] requirements.txt hash-pinning maintained
- [ ] .env file created with API credentials
- [ ] All remediation code fixes present in container

### Container Build Validation
- [ ] Image builds successfully
- [ ] No security compromises
- [ ] User 999:999 configured
- [ ] Read-only filesystem enabled
- [ ] Capabilities dropped (cap_drop: ALL)
- [ ] No new privileges
- [ ] Resource limits configured

### Runtime Validation
- [ ] Container starts successfully
- [ ] Runs as UID 999 (appuser)
- [ ] Read-only filesystem enforced
- [ ] Milvus connection successful (milvus:19530)
- [ ] RAG knowledge base accessible
- [ ] API calls work from container

### Functional Validation
- [ ] Phase 1: Scan completes (159-162 parsers)
- [ ] Phase 2: 162/162 parsers analyzed (100%)
- [ ] No JSON serialization errors
- [ ] No HTTP 429 rate limiting errors
- [ ] DateTimeEncoder working
- [ ] TokenBucket rate limiter working
- [ ] AdaptiveBatchSizer working
- [ ] Phase 3: LUA generation (target 155-160/162)
- [ ] Phase 4: Deployment validation
- [ ] Phase 5: Report generation

### Security Validation
- [ ] No writes to read-only areas
- [ ] Process runs as non-root
- [ ] Network isolation maintained
- [ ] Secrets not logged
- [ ] Resource limits enforced
- [ ] Health checks passing

---

## Execution Steps

**IMPORTANT**: Do NOT modify Dockerfile or docker-compose.yml security settings

1. Check if image exists: `docker images | grep purple-pipeline`
2. If image doesn't exist:
   - Fix requirements.txt with proper hash for hf-xet
   - Build: `docker-compose build parser-eater`
3. Create .env file with API credentials
4. Start stack: `docker-compose up -d`
5. Run test INSIDE container: `docker-compose exec parser-eater python main.py --verbose`
6. Monitor: `docker-compose logs -f parser-eater`
7. Collect results: `docker cp purple-parser-eater:/app/output ./docker-test-results`
8. Generate report comparing containerized test vs. host test
9. Validate security compliance maintained

---

## Expected Outcome

**Success Criteria**:
- ✅ All tests run inside purple-parser-eater container (NOT on host)
- ✅ STIG hardening maintained throughout
- ✅ Phase 2: 162/162 parsers (100% success)
- ✅ Zero JSON serialization errors
- ✅ Zero HTTP 429 errors
- ✅ All security controls validated
- ✅ Results match host test (proving code portability)

**Deliverable**:
- Docker-based test report confirming remediation works in production STIG-hardened containerized environment

---

END OF DOCKER TESTING PLAN
