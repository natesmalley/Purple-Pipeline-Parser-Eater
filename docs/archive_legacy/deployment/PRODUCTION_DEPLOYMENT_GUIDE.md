# Production Deployment Guide - Purple Pipeline Parser Eater v9.0.0

**Version:** 9.0.0
**Last Updated:** 2025-10-15
**Status:** ✅ READY FOR PRODUCTION USE

---

## ✅ **PRODUCTION-READY STATUS**

The Purple Pipeline Parser Eater is now configured and ready for production deployment:

- ✅ **Web UI:** Fully operational at http://localhost:8080
- ✅ **SDL Integration:** ALL events sent to SentinelOne Security Data Lake
- ✅ **Environment Variables:** All API keys secured in .env file
- ✅ **Test Data Removed:** System starts clean, processes only new parsers
- ✅ **Continuous Service:** Auto-syncs from GitHub every 60 minutes
- ✅ **Security Controls:** CSRF, XSS, input validation, duplicate prevention
- ✅ **Docker Image:** purple-pipeline-parser-eater:9.0.0 (Built: 11:04:48)

---

## 🚀 **QUICK START - PRODUCTION MODE**

### **Prerequisites:**
- Docker Desktop installed and running
- 16GB+ RAM available
- 10GB+ disk space
- API keys ready:
  - Anthropic Claude API key
  - GitHub Personal Access Token
  - SentinelOne SDL Write API key

### **Step 1: Clone Repository**
```bash
git clone <your-repo-url>
cd Purple-Pipline-Parser-Eater
```

### **Step 2: Configure Environment Variables**
```bash
# The .env file already exists with your API keys
# Verify it contains:
cat .env

# Should show:
# ANTHROPIC_API_KEY=...
# GITHUB_TOKEN=...
# SDL_API_KEY=...
# WEB_UI_AUTH_TOKEN=...
# MINIO_ACCESS_KEY=...
# MINIO_SECRET_KEY=...
```

### **Step 3: Start All Services**
```bash
# Start in detached mode
docker-compose up -d

# Check all containers are healthy
docker ps | grep purple

# Expected output:
# purple-parser-eater   Up (healthy)
# purple-milvus         Up (healthy)
# purple-etcd           Up (healthy)
# purple-minio          Up (healthy)
```

### **Step 4: Verify System Initialization**
```bash
# Watch initialization logs
docker logs -f purple-parser-eater

# Look for:
# [OK] RAG Knowledge Base initialized
# [OK] SDL Audit Logger initialized
# [OK] SDL Logging Handler initialized - ALL logs now sent to SentinelOne SDL
# [OK] Web UI Server initialized
# INITIALIZATION COMPLETE
# RAG Sync Loop started
# Conversion Loop started
# Feedback Loop started
# Running on all addresses (0.0.0.0)
# * Running on http://127.0.0.1:8080
```

### **Step 5: Access Web UI**
```bash
# Open browser to:
http://localhost:8080

# The Web UI will show:
# - Dashboard with conversion statistics
# - "No Pending Conversions" (system is clean)
# - Auto-refresh every 30 seconds
```

---

## 📊 **HOW IT WORKS IN PRODUCTION**

### **Automatic Parser Processing:**

**Every 60 Minutes:**
1. System syncs with SentinelOne GitHub repository
2. Detects NEW or UPDATED parsers
3. Automatically converts them with Claude AI + RAG
4. Presents them in Web UI for SME review

**When New Parser Detected:**
```
GitHub Sync → New Parser Found → Auto-Convert → Web UI Queue → Awaiting Review
```

**SME Review Workflow:**
```
Web UI → View Parser → Approve/Reject/Modify → SDL Audit Event → Deployed (if approved)
```

---

## 🎯 **PRODUCTION OPERATIONS**

### **Daily Operations:**

**Morning Check (5 minutes):**
```bash
# 1. Check system health
docker ps | grep purple

# 2. Check Web UI
curl http://localhost:8080/api/status | python -m json.tool

# 3. Review any pending conversions
# Visit: http://localhost:8080
```

**Parser Review (as needed):**
- New parsers appear in Web UI automatically
- Review LUA code preview
- Click **[OK] Approve** or **[ERROR] Reject** or **[EDIT] Modify**
- All actions logged to SentinelOne SDL

**Weekly Tasks:**
- Review SDL audit logs in SentinelOne
- Check for any rejected parsers
- Verify all approved parsers deployed successfully

---

## 🔍 **MONITORING & VALIDATION**

### **System Health Checks:**

**Check Container Status:**
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# All should show "Up (healthy)"
```

**Check Web UI:**
```bash
curl http://localhost:8080/api/status

# Should return JSON with is_running: true
```

**Check SDL Integration:**
```bash
docker logs purple-parser-eater | grep "SDL.*✓"

# Should show successful event deliveries
```

**Check Parser Conversions:**
```bash
docker logs purple-parser-eater | grep "OK.*Generated LUA"

# Shows successful LUA generations
```

### **Verify SDL Events in SentinelOne:**

**Access SentinelOne Console:**
```
URL: https://xdr.us1.sentinelone.net
Navigate to: Data Lake → Query
```

**Search for Events:**
```
service="purple-pipeline-parser-eater" AND event_type="parser_*"

# Should show:
# - parser_approval events
# - parser_rejection events
# - parser_modification events
```

---

## 🛠️ **TROUBLESHOOTING**

### **Issue: Web UI Not Loading**

**Check Flask is Running:**
```bash
docker logs purple-parser-eater | grep "Running on"
# Should show: Running on all addresses (0.0.0.0)
```

**Check Port Mapping:**
```bash
docker ps | grep 8080
# Should show: 0.0.0.0:8080->8080/tcp
```

**Test Direct Access:**
```bash
curl http://localhost:8080/
# Should return HTML
```

---

### **Issue: No Parsers Appearing in Web UI**

**Check GitHub Sync:**
```bash
docker logs purple-parser-eater | grep "RAG Sync"
# Should show sync activity
```

**Manually Trigger Sync:**
```bash
# Restart container to trigger immediate sync
docker restart purple-parser-eater
```

**Check for New Parsers:**
```bash
docker logs purple-parser-eater | grep "Queued for conversion"
# Shows parsers being queued
```

---

### **Issue: SDL Events Not Sending**

**Check SDL Configuration:**
```bash
docker exec purple-parser-eater env | grep SDL_API_KEY
# Should show your API key
```

**Check SDL Logs:**
```bash
docker logs purple-parser-eater | grep "SDL AUDIT"
# Look for ✓ (success) or ✗ (failure)
```

**Test SDL Endpoint:**
```bash
# Approve a parser in Web UI
# Check logs for: [SDL AUDIT] ✓ Event sent to SentinelOne SDL
```

---

### **Issue: Parser Conversion Failing**

**Check Claude API:**
```bash
docker logs purple-parser-eater | grep "authentication_error\|401"
# Should show no errors

docker exec purple-parser-eater env | grep ANTHROPIC_API_KEY
# Should show your API key
```

**Check RAG Knowledge Base:**
```bash
docker logs purple-parser-eater | grep "RAG Knowledge Base"
# Should show: [OK] RAG Knowledge Base initialized
```

**Check for Specific Errors:**
```bash
docker logs purple-parser-eater | grep -i "error\|exception" | tail -20
```

---

## 🔐 **SECURITY CHECKLIST**

### **Before Production Use:**

**Configuration:**
- [x] .env file created with all API keys
- [x] config.yaml uses ${ENV_VAR} references (no hardcoded secrets)
- [x] .env in .gitignore (secrets won't be committed)
- [ ] WEB_UI_AUTH_TOKEN changed from default (optional - for auth)
- [ ] Authentication enabled (remove testing bypass) - **DEFERRED TO v9.1.0**
- [ ] TLS/HTTPS configured - **DEFERRED TO v9.1.0**

**Docker Security:**
- [x] Non-root user (UID 999)
- [x] All capabilities dropped
- [x] No new privileges enabled
- [x] Resource limits set (4 CPU, 16GB RAM)
- [x] SUID/SGID removed
- [x] File permissions restrictive (750)

**Application Security:**
- [x] CSRF protection active
- [x] XSS protection (CSP + autoescaping)
- [x] Security headers enabled (8 headers)
- [x] Input validation on all endpoints
- [x] Duplicate action prevention
- [x] SDL audit logging active

**Network Security:**
- [x] Internal Docker network isolation
- [x] Minimal port exposure (8080 only)
- [ ] TLS/HTTPS enabled - **DEFERRED TO v9.1.0**
- [x] All external API calls use HTTPS

---

## 📈 **WHAT TO EXPECT**

### **First 24 Hours:**
- System syncs parsers from SentinelOne GitHub (first run)
- RAG knowledge base populated with 149 parsers
- No conversions yet (waiting for NEW parsers to appear)
- Web UI shows "No Pending Conversions"

### **When New Parser Appears:**
1. GitHub sync detects new parser (every 60 min)
2. System automatically queues for conversion
3. Claude AI + RAG generates LUA code
4. Parser appears in Web UI "Pending Review"
5. SME reviews and approves/rejects/modifies
6. SDL receives audit event
7. Approved parser ready for deployment

### **Typical Usage Pattern:**
- **Morning:** Check Web UI for pending parsers
- **Review:** Approve/reject/modify as needed
- **Afternoon:** System syncs again, may detect more parsers
- **End of Day:** Review SDL audit logs in SentinelOne

---

## 🎯 **PRODUCTION vs TESTING MODE**

### **Current Configuration (PRODUCTION MODE):**

| Feature | Status | Notes |
|---------|--------|-------|
| **Historical Parser Loading** | ✅ DISABLED | Only process NEW parsers from GitHub |
| **Test Data** | ✅ REMOVED | System starts clean (0 conversions) |
| **SDL Logging** | ✅ ENABLED | ALL events + logs to SentinelOne |
| **Environment Variables** | ✅ ENABLED | All secrets in .env |
| **Auto-Sync** | ✅ ENABLED | Every 60 minutes |
| **Web UI** | ✅ ENABLED | http://localhost:8080 |
| **Authentication** | ⚠️ TESTING MODE | Bypass active (optional - enable in v9.1.0) |
| **TLS/HTTPS** | ⚠️ HTTP | TLS infrastructure ready (enable in v9.1.0) |

### **To Enable Testing Mode:**
```python
# In continuous_conversion_service.py line 190:
# Uncomment this line to load 10 test parsers on startup:
await self.load_historical_parsers()
```

---

## 📊 **EXPECTED BEHAVIOR**

### **Clean Production Start:**
```json
{
  "approved_conversions": 0,
  "rejected_conversions": 0,
  "modified_conversions": 0,
  "pending_conversions": 0,    ← No test parsers!
  "queue_size": 0,
  "rag_status": {
    "tracked_parsers": 149,    ← RAG knows 149 parsers
    "total_updates": 0          ← Fresh start
  },
  "sdl_audit_stats": {
    "events_sent": 0,           ← Clean slate
    "success_rate": 0.0
  }
}
```

### **After First GitHub Sync:**
- `tracked_parsers`: 149-165 (depending on SentinelOne repo)
- `pending_conversions`: 0 (unless NEW parser appears)
- System ready to process NEW parsers automatically

---

## 🎊 **PRODUCTION FEATURES**

### **What Makes This Production-Ready:**

1. ✅ **Continuous Operation**
   - Runs 24/7 without intervention
   - Auto-syncs from GitHub
   - Auto-converts new parsers
   - Auto-presents for review

2. ✅ **Complete Audit Trail**
   - ALL actions logged to SentinelOne SDL
   - ALL application logs sent to SDL
   - Complete compliance and forensics capability

3. ✅ **Self-Improving System**
   - Learns from approvals (what good looks like)
   - Learns from rejections (what to avoid)
   - Learns from modifications (how to improve)
   - RAG gets smarter with each conversion

4. ✅ **Enterprise Security**
   - Environment variable secrets
   - CSRF + XSS protection
   - Docker STIG hardening (83%)
   - Dependency hash-pinning
   - No hardcoded credentials

5. ✅ **Error Recovery**
   - Automatic retry on rejection
   - Graceful error handling
   - SDL fallback logging
   - Container auto-restart

---

## 📝 **DEPLOYMENT CHECKLIST**

**Pre-Deployment:**
- [x] .env file configured with API keys
- [x] Docker images built successfully
- [x] All containers tested and working
- [x] Web UI tested (approve/reject/modify)
- [x] SDL integration verified (events sent)
- [x] Documentation reviewed

**Deployment:**
- [x] docker-compose up -d
- [x] Verify all containers healthy
- [x] Check Web UI accessible
- [x] Verify RAG initialized
- [x] Confirm SDL events sending

**Post-Deployment:**
- [ ] Monitor for first 24 hours
- [ ] Verify GitHub sync working
- [ ] Check SentinelOne SDL for events
- [ ] Test parser approval workflow
- [ ] Document any issues

---

## ✅ **READY FOR PRODUCTION!**

**The system is now:**
- ✅ Clean (no test data)
- ✅ Secure (environment variables, SDL logging)
- ✅ Operational (continuous service running)
- ✅ Monitored (all events to SentinelOne SDL)
- ✅ Self-improving (learns from feedback)

**Just start it and it runs!** 🚀

```bash
docker-compose up -d
```

**Web UI:** http://localhost:8080
**Mode:** Production (clean start, only process new parsers)

---

**Deployment Date:** 2025-10-15
**Status:** ✅ PRODUCTION-READY
**Security Grade:** B+ (testing mode) → A- (after enabling auth + TLS in v9.1.0)
