# 🔧 PHASES 2-5 IMPLEMENTATION GUIDE
**Purple Pipeline Parser Eater - Security Remediation**
**Date**: October 10, 2025
**Status**: READY FOR IMPLEMENTATION
**Estimated Total Time**: 12 hours

---

## 📊 CURRENT STATUS

✅ **Phase 1: COMPLETE** - Critical fixes (Env vars + Path traversal)
⏳ **Phase 2: PENDING** - High priority (TLS + XSS)
⏳ **Phase 3: PENDING** - Medium priority (Dependencies + CSRF)
⏳ **Phase 4: PENDING** - Hardening (Headers + polish)
⏳ **Phase 5: PENDING** - Testing & validation

---

## 🚀 PHASE 2: HIGH PRIORITY FIXES (6 hours)

### Task 2.1: TLS/HTTPS Implementation (4 hours)

**File**: `components/web_feedback_ui.py`
**Lines to Modify**: 24-53, 206-224
**Complexity**: MEDIUM

#### Step 1: Update `__init__()` Method

```python
# Add to imports
import ssl
from pathlib import Path as FilePath

# In __init__ method, add TLS configuration
class WebFeedbackServer:
    def __init__(self, config: Dict, feedback_queue: asyncio.Queue, service, event_loop=None):
        # ... existing code ...

        # TLS/HTTPS Configuration
        self.tls_enabled = web_ui_config.get("tls", {}).get("enabled", False)
        self.cert_file = web_ui_config.get("tls", {}).get("cert_file")
        self.key_file = web_ui_config.get("tls", {}).get("key_file")
        self.app_env = config.get("app_env", "development")

        # SECURITY: Enforce TLS in production
        if self.app_env == "production" and not self.tls_enabled:
            logger.error("❌ SECURITY: TLS is REQUIRED in production mode!")
            logger.error("❌ Set web_ui.tls.enabled=true and provide certificates")
            raise ValueError(
                "TLS must be enabled in production environment.\n"
                "Set web_ui.tls.enabled=true in config.yaml and provide cert/key files"
            )
```

#### Step 2: Modify `start()` Method

```python
async def start(self):
    """Start the web server with TLS support"""

    # Determine protocol
    protocol = "https" if self.tls_enabled else "http"
    logger.info(f"Starting Web Feedback UI on {protocol}://{self.bind_host}:{self.bind_port}")

    if self.tls_enabled:
        logger.info("🔒 TLS/HTTPS ENABLED")
        logger.info(f"🔒 Certificate: {self.cert_file}")
    else:
        logger.warning("⚠️  HTTP mode (development only - NOT SECURE)")

    logger.info(f"🔒 Authentication REQUIRED (header: {self.token_header})")

    # Run Flask with SSL context if enabled
    def run_flask():
        if self.tls_enabled:
            # Validate certificate files exist
            if not FilePath(self.cert_file).exists():
                raise FileNotFoundError(f"TLS certificate not found: {self.cert_file}")
            if not FilePath(self.key_file).exists():
                raise FileNotFoundError(f"TLS key not found: {self.key_file}")

            # Create SSL context
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(self.cert_file, self.key_file)

            # Optional: Set minimum TLS version
            ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

            # Run with SSL
            logger.info("🔒 Starting HTTPS server...")
            self.app.run(
                host=self.bind_host,
                port=self.bind_port,
                ssl_context=ssl_context,
                debug=False,
                use_reloader=False
            )
        else:
            # HTTP mode (development only)
            logger.warning("⚠️  Starting HTTP server (INSECURE - development only)")
            self.app.run(
                host=self.bind_host,
                port=self.bind_port,
                debug=False,
                use_reloader=False
            )

    thread = Thread(target=run_flask, daemon=True)
    thread.start()

    logger.info(f"✅ Web UI server started ({protocol.upper()})")

    # Keep task running
    while True:
        await asyncio.sleep(10)
```

#### Step 3: Update `config.yaml`

```yaml
web_ui:
  enabled: true
  host: "127.0.0.1"
  port: 8443  # Standard HTTPS port
  auth_token: "${WEB_UI_TOKEN:?Web UI authentication token required}"
  token_header: "X-PPPE-Token"

  # TLS Configuration
  tls:
    enabled: true
    cert_file: "/app/certs/server.crt"
    key_file: "/app/certs/server.key"

# Application environment (development|staging|production)
app_env: "development"  # Set to "production" to enforce TLS
```

#### Step 4: Generate Development Certificates

Create script: `scripts/generate-dev-certs.sh`

```bash
#!/bin/bash
# Generate self-signed certificate for development

CERT_DIR="./certs"
mkdir -p "$CERT_DIR"

openssl req -x509 -newkey rsa:4096 \
  -keyout "$CERT_DIR/server.key" \
  -out "$CERT_DIR/server.crt" \
  -days 365 -nodes \
  -subj "/CN=localhost/O=Purple Pipeline Parser Eater/C=US"

chmod 600 "$CERT_DIR/server.key"
chmod 644 "$CERT_DIR/server.crt"

echo "✅ Development certificates generated:"
echo "   Certificate: $CERT_DIR/server.crt"
echo "   Private Key: $CERT_DIR/server.key"
echo ""
echo "⚠️  These are SELF-SIGNED certificates for development only!"
echo "   For production, use certificates from a trusted CA (Let's Encrypt, etc.)"
```

#### Testing TLS

```bash
# Generate dev certs
bash scripts/generate-dev-certs.sh

# Update config
export WEB_UI_TOKEN="test-token-12345"

# Start server (should use HTTPS)
python continuous_conversion_service.py

# Test HTTPS (ignore self-signed cert warning)
curl -k -H "X-PPPE-Token: test-token-12345" https://localhost:8443/
```

---

### Task 2.2: XSS Protection (2 hours)

**File**: `components/web_feedback_ui.py`
**Lines to Modify**: 430-560
**Complexity**: MEDIUM

#### Step 1: Enable Jinja2 Autoescaping

```python
# In __init__ method
class WebFeedbackServer:
    def __init__(self, config: Dict, feedback_queue: asyncio.Queue, service, event_loop=None):
        # ... existing code ...
        self.app = Flask(__name__)

        # SECURITY: Enable autoescaping for XSS protection
        self.app.jinja_env.autoescape = True

        # ... rest of init ...
```

#### Step 2: Add Security Headers

```python
# Add after route setup, in __init__ or setup_routes
@self.app.after_request
def set_security_headers(response):
    """
    SECURITY FIX: Phase 2 - Add security headers

    Headers protect against:
    - XSS attacks
    - Clickjacking
    - MIME sniffing
    - Information leakage
    """
    # Prevent XSS
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'

    # Content Security Policy (strict)
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "  # unsafe-inline for inline styles
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )

    # Referrer policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

    # HTTPS enforcement (if TLS enabled)
    if self.tls_enabled:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

    return response
```

#### Step 3: Remove Inline Event Handlers

**Find and replace in INDEX_TEMPLATE** (around lines 437-557):

**BEFORE (Vulnerable)**:
```html
<button class="btn btn-approve" onclick="approveConversion('{{ parser_name }}')">
    Approve
</button>
<button class="btn btn-reject" onclick="rejectConversion('{{ parser_name }}')">
    Reject
</button>
<button class="btn btn-modify" onclick="modifyConversion('{{ parser_name }}')">
    Modify
</button>
```

**AFTER (Secure)**:
```html
<button class="btn btn-approve" data-parser-id="{{ parser_name|e }}" data-action="approve">
    Approve
</button>
<button class="btn btn-reject" data-parser-id="{{ parser_name|e }}" data-action="reject">
    Reject
</button>
<button class="btn btn-modify" data-parser-id="{{ parser_name|e }}" data-action="modify">
    Modify
</button>
```

#### Step 4: Implement Event Delegation

**Add at end of INDEX_TEMPLATE before `</body>`**:

```html
<script>
// SECURITY FIX: Phase 2 - Event delegation instead of inline handlers
// Prevents XSS via onclick injection

document.addEventListener('DOMContentLoaded', function() {
    // Get auth token from page data or meta tag
    const authToken = document.querySelector('meta[name="auth-token"]')?.content || '';

    // Delegate button clicks
    document.addEventListener('click', function(e) {
        const target = e.target.closest('[data-action]');
        if (!target) return;

        const action = target.dataset.action;
        const parserId = target.dataset.parserId;

        // Validate input
        if (!parserId || parserId.length > 200) {
            alert('Invalid parser ID');
            return;
        }

        // Route to appropriate handler
        switch(action) {
            case 'approve':
                approveConversion(parserId);
                break;
            case 'reject':
                rejectConversion(parserId);
                break;
            case 'modify':
                modifyConversion(parserId);
                break;
        }
    });
});

function approveConversion(parserId) {
    if (!confirm('Approve this conversion?')) return;

    fetch('/api/approve', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-PPPE-Token': getAuthToken()
        },
        body: JSON.stringify({ parser_id: parserId })  // JSON encoding prevents injection
    })
    .then(r => r.ok ? r.json() : Promise.reject(r))
    .then(data => {
        alert('Conversion approved!');
        location.reload();
    })
    .catch(err => {
        console.error('Error:', err);
        alert('Failed to approve conversion');
    });
}

function rejectConversion(parserId) {
    if (!confirm('Reject this conversion?')) return;

    fetch('/api/reject', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-PPPE-Token': getAuthToken()
        },
        body: JSON.stringify({ parser_id: parserId })
    })
    .then(r => r.ok ? r.json() : Promise.reject(r))
    .then(data => {
        alert('Conversion rejected!');
        location.reload();
    })
    .catch(err => {
        console.error('Error:', err);
        alert('Failed to reject conversion');
    });
}

function modifyConversion(parserId) {
    // Implementation for modify functionality
    // ... similar pattern ...
}

function getAuthToken() {
    // Get token from meta tag or localStorage
    return document.querySelector('meta[name="auth-token"]')?.content || '';
}
</script>
```

#### Testing XSS Protection

```bash
# Test with malicious parser name
# Before fix: Would execute JavaScript
# After fix: Parser name is escaped in data attribute

# Test payload: test'); alert('XSS'); //
# Expected: Treated as literal string, no alert box
```

---

## 🔧 PHASE 3: MEDIUM PRIORITY FIXES (3 hours)

### Task 3.1: Dependency Pinning (1.5 hours)

**File**: `requirements.txt`
**Complexity**: LOW

#### Step 1: Install pip-tools

```bash
pip install pip-tools
```

#### Step 2: Create `requirements.in`

```txt
# Core Dependencies
anthropic>=0.25.0
requests>=2.31.0
aiohttp>=3.8.0

# Web Framework
flask>=3.0.0
flask-wtf>=1.2.0  # For CSRF protection
gunicorn>=21.2.0
gevent>=23.9.1

# Vector Database and ML
pymilvus>=2.3.0
sentence-transformers>=2.2.2
numpy>=1.24.0
torch>=2.0.0

# Data Processing
pandas>=2.0.0
pyyaml>=6.0
jsonschema>=4.19.0

# GitHub Integration
PyGithub>=1.59.0
gitpython>=3.1.0

# Lua Validation (SECURITY FIX: Phase 3 - Added missing dependency)
lupa>=2.0

# Testing and Validation
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-mock>=3.11.0

# Monitoring and Logging
structlog>=23.1.0
prometheus-client>=0.17.0

# Security and Compliance
cryptography>=41.0.0
certifi>=2023.7.22

# Utility
python-dotenv>=1.0.0
tenacity>=8.2.0
click>=8.1.0
```

#### Step 3: Compile with Hashes

```bash
pip-compile --generate-hashes requirements.in -o requirements.txt
```

#### Step 4: Verify

```bash
# Result should be:
anthropic==0.25.0 \
    --hash=sha256:abc123...
requests==2.31.0 \
    --hash=sha256:def456...
# ... etc
```

---

### Task 3.2: CSRF Protection (1.5 hours)

**File**: `components/web_feedback_ui.py`
**Complexity**: LOW

#### Step 1: Install Flask-WTF

Already added to `requirements.in` above.

#### Step 2: Initialize CSRF Protection

```python
from flask_wtf.csrf import CSRFProtect

class WebFeedbackServer:
    def __init__(self, config: Dict, feedback_queue: asyncio.Queue, service, event_loop=None):
        # ... existing code ...
        self.app = Flask(__name__)

        # Set secret key for CSRF (use from environment)
        self.app.config['SECRET_KEY'] = os.environ.get(
            'FLASK_SECRET_KEY',
            os.urandom(32).hex()  # Random fallback
        )

        # SECURITY FIX: Phase 3 - Enable CSRF protection
        self.csrf = CSRFProtect(self.app)

        # ... rest of init ...
```

#### Step 3: Exempt API Endpoints (Use Header Auth Instead)

```python
# After CSRFProtect initialization
self.csrf.exempt(self.app)  # Exempt all (we use token header auth)
```

Or for specific routes:

```python
@self.app.route('/api/approve', methods=['POST'])
@self.csrf.exempt  # Use token header instead
@self.require_auth
def approve():
    # ... implementation ...
```

---

## 🛡️ PHASE 4: HARDENING & POLISH (2 hours)

### Task 4.1: Additional Security Measures

**File**: `components/web_feedback_ui.py`

#### Add Request Size Limits

```python
# In __init__
self.app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
```

#### Add Rate Limiting (Optional)

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["60 per minute"]
)

@app.route('/api/approve', methods=['POST'])
@limiter.limit("10 per minute")  # Stricter limit
@require_auth
def approve():
    ...
```

### Task 4.2: Fix Tmpfs Permissions

**File**: `docker-compose.yml`

```yaml
# Change from 1777 to 1770
tmpfs:
  size: 1073741824
  mode: 1770  # Group writable only (not world)
```

### Task 4.3: Fix Lua Validator F-String

**File**: `components/pipeline_validator.py`
**Line**: 198

**BEFORE**:
```python
lua.eval(f"function temp_validate() {lua_code} end")
```

**AFTER**:
```python
lua.execute("function temp_validate() " + lua_code + " end")
```

---

## ✅ PHASE 5: TESTING & VALIDATION (1 hour)

### Task 5.1: Security Scanning

```bash
# Run Bandit (Python SAST)
bandit -r . -f json -o security/bandit-report.json

# Run pip-audit (dependency vulnerabilities)
pip-audit --format=json --output=security/pip-audit.json

# Run Semgrep
semgrep --config=auto --json -o security/semgrep-report.json .
```

### Task 5.2: Manual Testing

**Test Checklist**:

```
Authentication:
  [ ] No token = 401
  [ ] Invalid token = 401
  [ ] Valid token = 200

TLS/HTTPS:
  [ ] Production mode requires TLS
  [ ] HTTPS works with valid cert
  [ ] HTTP→HTTPS redirect (if configured)
  [ ] HSTS header present

XSS Protection:
  [ ] Malicious parser name doesn't execute JavaScript
  [ ] Parser name with <script> tag is escaped
  [ ] CSP header blocks inline scripts
  [ ] No inline event handlers present

Path Traversal:
  [ ] ../../etc/passwd is sanitized
  [ ] Directory stays within output/
  [ ] Symlink attacks blocked

Environment Variables:
  [ ] ${VAR} expands correctly
  [ ] ${VAR:default} uses default
  [ ] ${VAR:?error} raises error

CSRF Protection:
  [ ] POST without CSRF token blocked (or using header auth)
  [ ] CSRF token validated correctly

Dependencies:
  [ ] All dependencies pinned with hashes
  [ ] pip install -r requirements.txt deterministic
  [ ] lupa available and working
```

### Task 5.3: Update Documentation

**Files to Update**:
- `README.md` - Add TLS configuration section
- `SETUP.md` - Add certificate generation instructions
- `SECURITY.md` - Update with all fixes applied
- `CHANGELOG.md` - Document version 9.1.0 changes

---

## 📊 EXPECTED FINAL METRICS

### Vulnerability Status

| Severity | Before | After Phase 5 | Reduction |
|----------|--------|---------------|-----------|
| Critical | 2 | 0 | 100% |
| High | 2 | 0 | 100% |
| Medium | 6 | 0 | 100% |
| Low | 5 | 0 | 100% |
| **TOTAL** | **15** | **0** | **100%** |

### Security Score

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| CVSS Score | 8.1 | 0.0 | -8.1 ✅ |
| STIG Compliance | 52% | 73% | +40% ✅ |
| Production Ready | ❌ NO | ✅ YES | ACHIEVED ✅ |

---

## 🎯 DEPLOYMENT CHECKLIST

Before deploying to production:

```
Environment Setup:
  [ ] ANTHROPIC_API_KEY set in environment
  [ ] OBSERVO_API_KEY set in environment
  [ ] WEB_UI_TOKEN set with strong random value
  [ ] FLASK_SECRET_KEY set with strong random value
  [ ] MINIO_ACCESS_KEY set
  [ ] MINIO_SECRET_KEY set
  [ ] All required env vars validated

TLS/HTTPS:
  [ ] Production certificates obtained (Let's Encrypt, CA)
  [ ] Certificates installed in /app/certs/
  [ ] web_ui.tls.enabled=true in config
  [ ] app_env=production in config
  [ ] Certificate expiry monitoring configured

Security Configuration:
  [ ] auth_token changed from default
  [ ] Debug mode disabled
  [ ] Error messages don't leak sensitive data
  [ ] Logging configured (no secrets in logs)
  [ ] File permissions correct (600 for keys)

Dependencies:
  [ ] requirements.txt pinned with hashes
  [ ] pip-audit shows no vulnerabilities
  [ ] All dependencies up to date

Testing:
  [ ] All security tests passing
  [ ] Penetration testing completed
  [ ] No critical/high findings
  [ ] Functional tests passing
  [ ] Performance tests passing

Documentation:
  [ ] README updated
  [ ] Security docs current
  [ ] Runbooks available
  [ ] Incident response plan ready

Monitoring:
  [ ] Logging configured (CloudWatch/ELK)
  [ ] Alerts configured
  [ ] On-call rotation defined
  [ ] Backup/restore tested
```

---

## 📄 VERSION CONTROL

### Git Workflow

```bash
# Create branch for each phase
git checkout -b security-fix-phase-2-tls-xss
# ... make changes ...
git add -A
git commit -m "fix(security): Phase 2 - Add TLS/HTTPS and XSS protection

- Implemented TLS/HTTPS with SSL context
- Added development certificate generation
- Enforced TLS in production mode
- Removed inline onclick handlers
- Implemented event delegation for XSS protection
- Added Content Security Policy headers
- Enabled Jinja2 autoescaping

SECURITY FIXES:
- CVSS 7.5 (No TLS) → FIXED
- CVSS 7.4 (XSS) → FIXED

Closes: #SECURITY-HIGH-1, #SECURITY-HIGH-2"

git push origin security-fix-phase-2-tls-xss

# Create PR, review, merge
# Then tag
git tag -a v9.1.0 -m "Security hardening release - All vulnerabilities fixed"
git push origin v9.1.0
```

---

## 🔒 FINAL SECURITY SIGN-OFF

After completing all phases:

```
Phase 1: Critical Fixes
  [✅] Environment variable expansion
  [✅] Path traversal protection

Phase 2: High Priority
  [ ] TLS/HTTPS implementation
  [ ] XSS protection

Phase 3: Medium Priority
  [ ] Dependency pinning
  [ ] CSRF protection
  [ ] Add missing lupa dependency

Phase 4: Hardening
  [ ] Security headers
  [ ] Request size limits
  [ ] Tmpfs permissions
  [ ] Lua validator f-string fix

Phase 5: Validation
  [ ] Security scans clean
  [ ] Manual testing complete
  [ ] Documentation updated
  [ ] Deployment checklist verified

OVERALL STATUS: [ ] READY FOR PRODUCTION

Signed: _____________________
Date: _______________________
```

---

**IMPLEMENTATION GUIDE COMPLETE**

**Next Action**: Begin Phase 2 implementation following this guide
