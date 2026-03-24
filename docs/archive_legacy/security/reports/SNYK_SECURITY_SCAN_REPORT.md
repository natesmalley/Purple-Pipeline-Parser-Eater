# Snyk Security Scan Report
## Purple Pipeline Parser Eater - Full Security Assessment

**Date:** 2025-01-27  
**Scanner:** Snyk Code (SAST)  
**Version:** 1.1300.2  
**Scan Type:** Static Application Security Testing (SAST)

---

## Executive Summary

Snyk Code scan identified **18 security issues** across the codebase:

- **Medium Severity:** 6 issues
- **Low Severity:** 12 issues

### Critical Findings

1. **DOM-based XSS vulnerabilities** in `viewer.html` (2 instances)
2. **Path Traversal vulnerabilities** in multiple files (6 instances)
3. **Hardcoded credentials/passwords** in code (5 instances)
4. **Hardcoded secrets** in test files (5 instances)

---

## Detailed Findings

### 🔴 Medium Severity Issues

#### 1. DOM-based Cross-site Scripting (XSS) - viewer.html

**Issue Count:** 2  
**CWE:** CWE-79  
**Rule ID:** javascript/DOMXSS

**Location 1:** `viewer.html:293`
- **Line:** 293, Column: 73
- **Description:** Unsanitized input from an exception flows into `innerHTML`
- **Data Flow:**
  - Error message from exception handler
  - Flows into `document.getElementById('parsersContainer').innerHTML`
- **Risk:** XSS attack if error messages contain malicious content

**Location 2:** `viewer.html:358`
- **Line:** 358, Column: 35
- **Description:** Unsanitized input from remote resource flows into `innerHTML`
- **Data Flow:**
  - Data from `fetch('output/02_analyzed_parsers.json')`
  - Parser data flows through `renderParsers()` function
  - Flows into `container.innerHTML`
- **Risk:** XSS attack if JSON data contains malicious content

**Recommendation:**
```javascript
// Use textContent instead of innerHTML, or sanitize input
container.textContent = html; // Or use DOMPurify library
// Or escape HTML entities
container.innerHTML = html.replace(/</g, '&lt;').replace(/>/g, '&gt;');
```

---

#### 2. Path Traversal Vulnerabilities

**Issue Count:** 6  
**CWE:** CWE-23  
**Rule ID:** python/PT

**Location 1:** `utils/config.py:11`
- **Line:** 11, Column: 10
- **Description:** Unsanitized input from environment variable flows into `open()`
- **Data Flow:**
  - `os.environ.get("PPPE_CONFIG", "config.yaml")`
  - Flows into `open(path, "r", encoding="utf-8")`
- **Risk:** Path traversal attack could read arbitrary files

**Recommendation:**
```python
import os
from pathlib import Path

path = path or os.environ.get("PPPE_CONFIG", "config.yaml")
# Validate path is within allowed directory
config_dir = Path(__file__).parent.parent
resolved_path = (config_dir / path).resolve()
if not str(resolved_path).startswith(str(config_dir.resolve())):
    raise SecurityError("Path traversal detected")
```

**Location 2:** `scripts/rag/populate_from_local.py:119`
- **Line:** 119, Column: 18
- **Description:** Unsanitized user input flows into `open()`
- **Data Flow:**
  - User input from `input("Repository path: ")`
  - Flows through Path operations
  - Flows into `open(config_file, 'r', encoding='utf-8')`
- **Risk:** Path traversal attack could read arbitrary files

**Location 3:** `scripts/rag/populate_from_local.py:128`
- **Line:** 128, Column: 22
- **Description:** Unsanitized user input flows into `open()`
- **Data Flow:**
  - User input from `input("Repository path: ")`
  - Flows through Path operations
  - Flows into `open(lua_file, 'r', encoding='utf-8')`
- **Risk:** Path traversal attack could read arbitrary files

**Location 4:** `scripts/start_output_service.py:32`
- **Line:** 32, Column: 10
- **Description:** Unsanitized command line argument flows into `open()`
- **Data Flow:**
  - Command line argument `args.config`
  - Flows into `open(config_path, "r", encoding="utf-8")`
- **Risk:** Path traversal attack could read arbitrary files

**Location 5:** `scripts/start_output_service.py:49`
- **Line:** 49, Column: 9
- **Description:** Unsanitized command line argument flows into `pathlib.Path`
- **Data Flow:**
  - Command line argument `args.config`
  - Flows into `Path(log_file).parent.mkdir()`
- **Risk:** Path traversal attack could create directories outside intended location

**Location 6:** `scripts/start_runtime_service.py:52`
- **Line:** 52, Column: 10
- **Description:** Unsanitized command line argument flows into `open()`
- **Data Flow:**
  - Command line argument `args.config`
  - Flows into `open(config_file, "r")`
- **Risk:** Path traversal attack could read arbitrary files

**Location 7:** `scripts/start_runtime_service.py:90`
- **Line:** 90, Column: 20
- **Description:** Unsanitized command line argument flows into `pathlib.Path`
- **Data Flow:**
  - Command line argument `args.config`
  - Flows into `Path(log_file)`
- **Risk:** Path traversal attack could write logs outside intended location

**Recommendation for Scripts:**
```python
from pathlib import Path
import os

def validate_path(user_path: str, base_dir: Path) -> Path:
    """Validate and resolve path, preventing path traversal."""
    base_dir = base_dir.resolve()
    resolved = (base_dir / user_path).resolve()
    
    # Ensure resolved path is within base directory
    if not str(resolved).startswith(str(base_dir)):
        raise ValueError(f"Path traversal detected: {user_path}")
    
    return resolved
```

---

#### 3. Hardcoded Password Pattern

**Issue Count:** 1  
**CWE:** CWE-798, CWE-259  
**Rule ID:** python/NoHardcodedPasswords

**Location:** `components/request_logger.py:23`
- **Line:** 23, Column: 9
- **Description:** Hardcoded password pattern in regex
- **Pattern:** `r"password[\"']?\s*[:=]\s*[\"']?([^\"'\s]+)[\"']?"`
- **Risk:** This appears to be a regex pattern for detecting passwords in logs, not an actual hardcoded password. However, the pattern itself could be flagged.

**Recommendation:** Add comment explaining this is a detection pattern, not a credential:
```python
# SECURITY NOTE: This is a regex pattern for detecting password fields in logs,
# not a hardcoded password. Used for log sanitization.
PASSWORD_PATTERN = r"password[\"']?\s*[:=]\s*[\"']?([^\"'\s]+)[\"']?"
```

---

### 🟡 Low Severity Issues

#### 4. Hardcoded Non-Cryptographic Secrets (Test Files)

**Issue Count:** 4  
**CWE:** CWE-547  
**Rule ID:** python/HardcodedNonCryptoSecret/test

**Locations:**
1. `tests/test_claude_analyzer_comprehensive.py:114`
   - Value: `"your-anthropic-api-key-here"`
   - **Status:** ✅ Acceptable - This is a placeholder in test file

2. `tests/test_config_validator.py:111`
   - Value: `"ghp_REDACTED"`
   - **Status:** ✅ Acceptable - This is a test token in test file

3. `tests/test_sdl_audit_logger_comprehensive.py:186`
   - Value: `lua_with_secret = """`
   - **Status:** ✅ Acceptable - This is test data

4. `tests/test_security_fixes.py:305`
   - Value: `"test_secret_key_12345"`
   - **Status:** ✅ Acceptable - This is a test secret

**Recommendation:** These are acceptable in test files. Consider using environment variables or test fixtures for better practice.

---

#### 5. Hardcoded Credentials (False Positives)

**Issue Count:** 3  
**CWE:** CWE-798  
**Rule ID:** python/NoHardcodedCredentials

**Location 1:** `components/observo_models.py:36`
- **Line:** 36, Column: 5
- **Value:** `"PIPELINE_TYPE_USER"`
- **Status:** ⚠️ False Positive - This is a constant string, not a credential

**Location 2:** `components/observo_models.py:61`
- **Line:** 61, Column: 5
- **Value:** `"NODE_ORIGIN_USER"`
- **Status:** ⚠️ False Positive - This is a constant string, not a credential

**Location 3:** `scripts/utils/preflight_check.py:322`
- **Line:** 322, Column: 25
- **Value:** `"dry-run-mode"`
- **Status:** ⚠️ False Positive - This is a special mode identifier, not a credential

**Recommendation:** These are false positives. The Snyk scanner is flagging string constants that contain the word "USER" or look like credentials. No action needed.

---

#### 6. Hardcoded Password in Test File

**Issue Count:** 1  
**CWE:** CWE-798, CWE-259  
**Rule ID:** python/NoHardcodedPasswords/test

**Location:** `tests/test_pipeline_validator_comprehensive.py:308`
- **Line:** 308, Column: 13
- **Value:** `'password': 'my-password'`
- **Status:** ✅ Acceptable - This is test data in a test file

**Recommendation:** Acceptable in test files. Consider using test fixtures.

---

## Summary by Severity

### Medium Severity (6 issues)
- DOM-based XSS: 2 issues
- Path Traversal: 6 issues (some files have multiple instances)
- Hardcoded Password Pattern: 1 issue (likely false positive)

### Low Severity (12 issues)
- Hardcoded Secrets in Tests: 4 issues (acceptable)
- Hardcoded Credentials (False Positives): 3 issues
- Hardcoded Passwords in Tests: 1 issue (acceptable)

---

## Risk Assessment

### High Risk Issues
1. **DOM-based XSS in viewer.html** - Requires immediate attention
   - Impact: XSS attacks could compromise user sessions
   - Likelihood: Medium (requires malicious JSON or error injection)
   - Priority: HIGH

2. **Path Traversal in config loading** - Requires attention
   - Impact: Unauthorized file access
   - Likelihood: Low (requires control of environment variables or command line)
   - Priority: MEDIUM

### Medium Risk Issues
3. **Path Traversal in scripts** - Requires attention
   - Impact: Unauthorized file access
   - Likelihood: Low (requires local access or malicious user input)
   - Priority: MEDIUM

### Low Risk Issues
4. **Hardcoded values in test files** - Acceptable
   - Impact: None (test files only)
   - Priority: LOW

5. **False positive credential detections** - No action needed
   - Impact: None
   - Priority: NONE

---

## Remediation Priority

### Immediate (This Week)
1. ✅ Fix DOM-based XSS in `viewer.html` (2 instances)
   - Use `textContent` or sanitize HTML
   - Implement DOMPurify or similar library

### Short Term (This Month)
2. ✅ Fix Path Traversal in `utils/config.py`
   - Add path validation
   - Restrict to allowed directories

3. ✅ Fix Path Traversal in script files
   - Add path validation functions
   - Restrict to allowed directories

### Low Priority
4. ⚠️ Review hardcoded password pattern in `request_logger.py`
   - Add clarifying comment
   - Verify it's used correctly

5. ✅ Test file hardcoded values - Acceptable as-is

---

## Code Examples for Fixes

### Fix DOM-based XSS

**Before:**
```javascript
container.innerHTML = `<div class="parsers-grid">${html}</div>`;
```

**After:**
```javascript
// Option 1: Use textContent (if HTML not needed)
container.textContent = html;

// Option 2: Sanitize HTML
import DOMPurify from 'dompurify';
container.innerHTML = DOMPurify.sanitize(`<div class="parsers-grid">${html}</div>`);

// Option 3: Escape HTML entities
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
container.innerHTML = `<div class="parsers-grid">${escapeHtml(html)}</div>`;
```

### Fix Path Traversal

**Before:**
```python
path = os.environ.get("PPPE_CONFIG", "config.yaml")
with open(path, "r", encoding="utf-8") as handle:
    return yaml.safe_load(handle)
```

**After:**
```python
from pathlib import Path
import os

def load_config(path: str = None) -> dict:
    """Load configuration with path traversal protection."""
    base_dir = Path(__file__).parent.parent
    config_dir = base_dir / "config"
    
    path = path or os.environ.get("PPPE_CONFIG", "config.yaml")
    
    # Resolve and validate path
    resolved_path = (config_dir / path).resolve()
    config_dir_resolved = config_dir.resolve()
    
    # Ensure path is within config directory
    if not str(resolved_path).startswith(str(config_dir_resolved)):
        raise SecurityError(f"Path traversal detected: {path}")
    
    with open(resolved_path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)
```

---

## SCA Scan Status

**Status:** ⚠️ Failed  
**Reason:** Python environment not configured or dependencies not installed  
**Action Required:** Set up Python virtual environment and install dependencies

**To Run SCA Scan:**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Run Snyk SCA scan
snyk test --command=python
```

---

## Compliance Impact

### FedRAMP SI-2 (Flaw Remediation)
- ✅ Security flaws identified and documented
- ⚠️ Remediation plan required
- ⚠️ Timeline: Immediate for high-risk issues

### NIST 800-53 SI-2
- ✅ Vulnerability scanning completed
- ⚠️ Remediation required for identified vulnerabilities

---

## Next Steps

1. **Immediate:** Fix DOM-based XSS vulnerabilities
2. **This Week:** Fix Path Traversal vulnerabilities
3. **This Month:** Set up Python environment and run SCA scan
4. **Ongoing:** Regular Snyk scans in CI/CD pipeline

---

## References

- [Snyk Documentation](https://docs.snyk.io/)
- [OWASP XSS Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)
- [OWASP Path Traversal](https://owasp.org/www-community/attacks/Path_Traversal)
- [CWE-79: XSS](https://cwe.mitre.org/data/definitions/79.html)
- [CWE-23: Path Traversal](https://cwe.mitre.org/data/definitions/23.html)

---

**Report Generated:** 2025-01-27  
**Scanner:** Snyk Code v1.1300.2  
**Total Issues:** 18 (6 Medium, 12 Low)  
**Files Scanned:** All Python and JavaScript files

---

## Appendix: Full Issue List

| # | Severity | Type | File | Line | CWE | Status |
|---|----------|------|------|------|-----|--------|
| 1 | Medium | DOM XSS | viewer.html | 293 | CWE-79 | 🔴 Fix Required |
| 2 | Medium | DOM XSS | viewer.html | 358 | CWE-79 | 🔴 Fix Required |
| 3 | Medium | Path Traversal | utils/config.py | 11 | CWE-23 | 🔴 Fix Required |
| 4 | Medium | Path Traversal | scripts/rag/populate_from_local.py | 119 | CWE-23 | 🔴 Fix Required |
| 5 | Medium | Path Traversal | scripts/rag/populate_from_local.py | 128 | CWE-23 | 🔴 Fix Required |
| 6 | Medium | Path Traversal | scripts/start_output_service.py | 32 | CWE-23 | 🔴 Fix Required |
| 7 | Medium | Path Traversal | scripts/start_output_service.py | 49 | CWE-23 | 🔴 Fix Required |
| 8 | Medium | Path Traversal | scripts/start_runtime_service.py | 52 | CWE-23 | 🔴 Fix Required |
| 9 | Medium | Path Traversal | scripts/start_runtime_service.py | 90 | CWE-23 | 🔴 Fix Required |
| 10 | Medium | Hardcoded Password | components/request_logger.py | 23 | CWE-798 | ⚠️ Review |
| 11 | Low | Hardcoded Secret | tests/test_claude_analyzer_comprehensive.py | 114 | CWE-547 | ✅ Acceptable |
| 12 | Low | Hardcoded Secret | tests/test_config_validator.py | 111 | CWE-547 | ✅ Acceptable |
| 13 | Low | Hardcoded Secret | tests/test_sdl_audit_logger_comprehensive.py | 186 | CWE-547 | ✅ Acceptable |
| 14 | Low | Hardcoded Secret | tests/test_security_fixes.py | 305 | CWE-547 | ✅ Acceptable |
| 15 | Low | Hardcoded Credential | components/observo_models.py | 36 | CWE-798 | ✅ False Positive |
| 16 | Low | Hardcoded Credential | components/observo_models.py | 61 | CWE-798 | ✅ False Positive |
| 17 | Low | Hardcoded Credential | scripts/utils/preflight_check.py | 322 | CWE-798 | ✅ False Positive |
| 18 | Low | Hardcoded Password | tests/test_pipeline_validator_comprehensive.py | 308 | CWE-798 | ✅ Acceptable |

