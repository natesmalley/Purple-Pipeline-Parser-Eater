# Future Enhancements - Nice to Have Items

**Priority:** P2 (Nice to Have)
**Timeline:** 2-4 weeks (after production MUST FIX items)
**Purpose:** Enhanced security and compliance for enterprise/government deployments

---

## 🔒 Security Enhancements (Nice to Have)

### 1. Implement Lua Sandbox
**Priority:** P2 (Important if processing untrusted parsers)
**Effort:** 3-5 days
**Risk Mitigation:** Prevents arbitrary code execution

**Implementation:**
- Create sandboxed Lua execution environment
- Whitelist allowed Lua functions
- Restrict file system access
- Limit memory/CPU for Lua execution

**Files to Modify:**
- `components/pipeline_validator.py`
- Add new: `components/lua_sandbox.py`

**When Needed:**
- If processing parsers from untrusted sources
- For enterprise/government compliance
- Current: Only processing SentinelOne official parsers (trusted)

---

### 2. Add Custom Seccomp Profile
**Priority:** P2 (STIG compliance enhancement)
**Effort:** 2-3 days
**Risk Mitigation:** Restricts syscalls to minimum required set

**Implementation:**
```json
{
  "defaultAction": "SCMP_ACT_ERRNO",
  "syscalls": [
    {
      "names": ["read", "write", "open", "close", "socket", "connect", ...],
      "action": "SCMP_ACT_ALLOW"
    }
  ]
}
```

**Files to Create:**
- `security/seccomp-profile.json`

**Files to Modify:**
- `docker-compose.yml` (add seccomp profile reference)

---

### 3. Implement SSRF Protection in RAG Scraper
**Priority:** P2 (Important if adding untrusted RAG sources)
**Effort:** 2-3 days
**Risk Mitigation:** Prevents server-side request forgery

**Implementation:**
```python
# URL validation before fetching
def validate_rag_url(url: str) -> bool:
    # Reject private IP ranges
    # Reject localhost/loopback
    # Reject file:// and other dangerous schemes
    # Whitelist only https://
    # Check against allowlist of domains
```

**Files to Modify:**
- `components/rag_sources.py`
- Add new: `components/url_validator.py`

**When Needed:**
- If adding user-configurable RAG sources
- Current: Only official SentinelOne and Observo docs (trusted)

---

### 4. Add Inter-Service mTLS
**Priority:** P2 (Enhanced internal security)
**Effort:** 3-4 days
**Risk Mitigation:** Encrypts traffic between containers

**Implementation:**
- Generate certificates for each service
- Configure Milvus with TLS
- Configure MinIO with TLS
- Configure etcd with TLS
- Update app to use TLS connections

**Files to Create:**
- `certs/milvus-cert.pem`
- `certs/minio-cert.pem`
- `certs/etcd-cert.pem`

**Files to Modify:**
- `docker-compose.yml` (add cert volumes)
- `config.yaml` (enable TLS for each service)
- `components/rag_knowledge.py` (use TLS for Milvus)

---

### 5. Install flask-limiter for Rate Limiting
**Priority:** P2 (DDoS protection)
**Effort:** 1 hour
**Risk Mitigation:** Prevents abuse/DoS attacks

**Implementation:**
```bash
# 1. Get flask-limiter hash
pip download flask-limiter==3.5.0
pip hash flask-limiter-3.5.0-py3-none-any.whl

# 2. Add to requirements.txt with hash
flask-limiter==3.5.0 \
    --hash=sha256:HASH_HERE
```

**Files to Modify:**
- `requirements.txt` (add flask-limiter with hash)
- `Dockerfile` (rebuild with new dependency)

**Current State:**
- Code already supports flask-limiter (optional dependency)
- System logs warning that it's not installed
- Graceful degradation (works without it)

---

### 6. Implement Content Sanitization (RAG Poisoning Protection)
**Priority:** P2 (RAG security)
**Effort:** 2-3 days
**Risk Mitigation:** Prevents prompt injection attacks

**Implementation:**
```python
# Sanitize RAG content before ingestion
def sanitize_rag_content(content: str) -> str:
    # Remove potential prompt injection patterns
    # Strip dangerous instructions
    # Validate content structure
    # Check for adversarial examples
```

**Files to Create:**
- `components/rag_content_sanitizer.py`

**Files to Modify:**
- `components/rag_sources.py`
- `components/rag_knowledge.py`

---

### 7. Add Kubernetes NetworkPolicies
**Priority:** P2 (If deploying to Kubernetes)
**Effort:** 1-2 days
**Risk Mitigation:** Network segmentation in K8s

**Implementation:**
```yaml
# Only allow specific pod-to-pod communication
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: parser-eater-netpol
spec:
  podSelector:
    matchLabels:
      app: parser-eater
  ingress:
    - from:
      - podSelector:
          matchLabels:
            app: allowed-client
```

**Files to Create:**
- `kubernetes/network-policy.yaml`

---

### 8. Implement Secrets Rotation
**Priority:** P2 (Long-term operations)
**Effort:** 2-3 days
**Risk Mitigation:** Limits exposure window for compromised credentials

**Implementation:**
- Automated 90-day credential rotation
- HashiCorp Vault integration
- AWS Secrets Manager integration
- Kubernetes Secrets with rotation

**Files to Create:**
- `components/secrets_manager.py`
- `scripts/rotate_credentials.sh`

---

### 9. Add User Authentication System
**Priority:** P2 (Multi-user deployments)
**Effort:** 5-7 days
**Risk Mitigation:** User attribution and RBAC

**Implementation:**
- Replace "web-ui-user" with real user IDs
- Implement OAuth2/SAML integration
- Role-based access control (RBAC)
- Audit logs with real user attribution

**Files to Create:**
- `components/user_auth.py`
- `components/rbac_manager.py`

**Files to Modify:**
- `components/web_feedback_ui.py`
- `components/sdl_audit_logger.py`

---

### 10. Add IP Whitelisting
**Priority:** P2 (Enhanced access control)
**Effort:** 1 day
**Risk Mitigation:** Restricts Web UI to corporate networks

**Implementation:**
```python
# Restrict access to corporate IP ranges
ALLOWED_IP_RANGES = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16"
]

@app.before_request
def check_ip_whitelist():
    if request.remote_addr not in allowed_ranges:
        abort(403)
```

**Files to Modify:**
- `components/web_feedback_ui.py`
- `config.yaml` (add IP whitelist config)

---

## 📋 Implementation Strategy

### **Phase 1: MUST FIX (Weeks 1-2)**
Complete all 5 production-blocking items:
1. Re-enable authentication
2. Environment variables for secrets
3. Strong MinIO credentials
4. TLS/HTTPS
5. Read-only FS with tmpfs

### **Phase 2: NICE TO HAVE - Quick Wins (Week 3)**
6. Install flask-limiter (1 hour)
7. IP whitelisting (1 day)

### **Phase 3: NICE TO HAVE - Security (Week 4)**
8. SSRF protection (2-3 days)
9. Content sanitization (2-3 days)

### **Phase 4: NICE TO HAVE - Enterprise (Weeks 5-6)**
10. Custom seccomp profile (2-3 days)
11. Inter-service mTLS (3-4 days)
12. Lua sandbox (3-5 days)

### **Phase 5: NICE TO HAVE - Operations (Weeks 7-8)**
13. User authentication system (5-7 days)
14. Secrets rotation (2-3 days)
15. K8s NetworkPolicies (1-2 days)

---

## 🎯 Total Timeline

**Production Ready:** 1-2 weeks (MUST FIX items)
**Enterprise Ready:** 6-8 weeks (MUST FIX + NICE TO HAVE items)

---

**Document Created:** 2025-10-15
**Status:** Reference for future work
**Priority:** P2 (After production MUST FIX items)
