# Agent 2: High Priority Security Fixes - Complete Prompt
**Claude Haiku Agent Assignment**

**Your Mission:** Fix 8 HIGH PRIORITY security issues that should be addressed before production deployment.

---

## 🎯 CONTEXT & OVERVIEW

You are working on **Purple Pipeline Parser Eater v9.0.0**, an enterprise-grade AI system that converts SentinelOne parsers to Observo.ai pipelines. The system uses:
- Python 3.11+
- Flask for web UI
- Docker for containerization
- Kubernetes for orchestration
- Prometheus for metrics
- Various external APIs (Anthropic, GitHub, Observo)

**Project Structure:**
```
purple-pipeline-parser-eater/
├── components/
│   ├── web_feedback_ui.py          # ← YOU WILL FIX THIS
│   ├── sdl_audit_logger.py         # ← YOU WILL FIX THIS
│   └── [various components]        # ← YOU WILL UPDATE THESE
├── k8s/
│   └── base/
│       ├── networkpolicy.yaml      # ← YOU WILL FIX THIS
│       └── deployment-app.yaml     # ← YOU WILL FIX THIS
├── utils/
│   └── logger.py                   # ← YOU WILL ENHANCE THIS
└── requirements.txt
```

**Your Working Directory:** `C:\Users\hexideciml\Documents\GitHub\Purple-Pipline-Parser-Eater`

---

## 🟡 YOUR TASKS (8 HIGH PRIORITY ISSUES)

### **TASK 1: Strengthen CSP Policy - Remove unsafe-inline**

**File:** `components/web_feedback_ui.py`  
**Lines:** 179-192  
**Priority:** 🟡 HIGH  
**Estimated Time:** 2 hours

**Current Code (PROBLEMATIC):**
```python
response.headers['Content-Security-Policy'] = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "  # ← PROBLEM: unsafe-inline weakens XSS protection
    "style-src 'self' 'unsafe-inline'; "  # unsafe-inline needed for inline CSS
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self';"
)
```

**The Problem:**
1. `unsafe-inline` allows inline scripts, weakening XSS protection
2. Current implementation uses embedded `<script>` tag in HTML template
3. Need to use nonce-based CSP instead

**What You Must Do:**

1. Implement nonce-based CSP for scripts
2. Keep `unsafe-inline` for styles (acceptable for CSS)
3. Update HTML template to use nonce
4. Test XSS protection

**Implementation Steps:**

**Step 1:** Update `setup_security_headers` method in `components/web_feedback_ui.py`:

```python
import secrets
from flask import g

def setup_security_headers(self):
    """
    SECURITY FIX: Phase 2 - Add security headers to all responses
    
    Headers protect against:
    - XSS attacks (Content-Security-Policy with nonce)
    - Clickjacking (X-Frame-Options)
    - MIME sniffing (X-Content-Type-Options)
    - Information leakage (Referrer-Policy)
    - Downgrade attacks (Strict-Transport-Security when TLS enabled)
    """
    @self.app.before_request
    def generate_nonce():
        """Generate CSP nonce for each request"""
        # Generate a new nonce for each request
        g.csp_nonce = secrets.token_urlsafe(16)
    
    @self.app.after_request
    def set_security_headers(response):
        # Prevent XSS
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'

        # SECURITY FIX: Phase 5 - API Versioning Header
        response.headers['X-API-Version'] = '1.0.0'

        # SECURITY FIX: Nonce-based Content Security Policy
        # Generate nonce for this request
        nonce = getattr(g, 'csp_nonce', secrets.token_urlsafe(16))
        
        # Build CSP with nonce for scripts (no unsafe-inline)
        csp_policy = (
            f"default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "  # Nonce-based, no unsafe-inline
            f"style-src 'self' 'unsafe-inline'; "  # Keep unsafe-inline for CSS (acceptable)
            f"img-src 'self' data:; "
            f"font-src 'self'; "
            f"connect-src 'self'; "
            f"frame-ancestors 'none'; "
            f"base-uri 'self'; "
            f"form-action 'self';"
        )
        response.headers['Content-Security-Policy'] = csp_policy

        # Referrer policy (privacy)
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # HTTPS enforcement (if TLS enabled)
        if self.tls_enabled:
            # HSTS: Force HTTPS for 1 year
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'

        return response
```

**Step 2:** Update the HTML template in `components/web_feedback_ui.py` to use nonce:

Find the `INDEX_TEMPLATE` constant (around line 500-600) and update the `<script>` tag:

```python
INDEX_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Purple Pipeline Parser Eater - Feedback UI</title>
    <style>
        /* CSS can stay inline - that's acceptable */
        body { font-family: Arial, sans-serif; margin: 20px; }
        /* ... rest of styles ... */
    </style>
</head>
<body>
    <!-- ... HTML content ... -->
    
    <!-- SECURITY FIX: Use nonce for inline script -->
    <script nonce="{{ csp_nonce }}">
        // JavaScript code here
        // This script will only execute if nonce matches CSP header
        const csrfToken = '{{ csrf_token() }}';
        // ... rest of JavaScript ...
    </script>
</body>
</html>
"""
```

**Step 3:** Update `render_template_string` calls to pass nonce:

```python
@self.app.route('/')
@self.require_auth
def index():
    """Main feedback UI page"""
    # Get nonce from Flask g object
    nonce = getattr(g, 'csp_nonce', secrets.token_urlsafe(16))
    
    return render_template_string(
        INDEX_TEMPLATE,
        csp_nonce=nonce,  # Pass nonce to template
        csrf_token=generate_csrf,
        # ... other template variables ...
    )
```

**Step 4:** Add tests for CSP nonce:

```python
# In tests/test_web_ui.py
import pytest
from flask import g

class TestCSPPolicy:
    """Test Content Security Policy implementation"""
    
    def test_csp_nonce_present(self, web_server):
        """Test that CSP nonce is generated and included"""
        client = web_server.app.test_client()
        headers = {'X-PPPE-Token': 'test-token-12345'}
        
        response = client.get('/', headers=headers)
        
        assert response.status_code == 200
        csp_header = response.headers.get('Content-Security-Policy', '')
        
        # Verify nonce is in CSP header
        assert 'nonce-' in csp_header
        assert "'unsafe-inline'" not in csp_header or "'unsafe-inline'" not in csp_header.split('script-src')[1]
    
    def test_csp_blocks_inline_script_without_nonce(self, web_server):
        """Test that inline scripts without nonce are blocked"""
        # This test verifies CSP is working
        # In a real browser, scripts without nonce would be blocked
        client = web_server.app.test_client()
        headers = {'X-PPPE-Token': 'test-token-12345'}
        
        response = client.get('/', headers=headers)
        html = response.get_data(as_text=True)
        
        # Verify script tag has nonce attribute
        assert 'nonce=' in html or '<script nonce' in html
    
    def test_xss_payload_blocked(self, web_server):
        """Test that XSS payloads are blocked by CSP"""
        client = web_server.app.test_client()
        headers = {'X-PPPE-Token': 'test-token-12345'}
        
        # Try to inject script via parameter
        response = client.get('/?xss=<script>alert(1)</script>', headers=headers)
        
        # CSP should prevent execution (browser would block)
        # Verify CSP header is present
        assert 'Content-Security-Policy' in response.headers
```

**Verification Checklist:**
- [ ] CSP uses nonce instead of unsafe-inline for scripts
- [ ] Nonce is generated per request
- [ ] Template receives and uses nonce
- [ ] Script tags have nonce attribute
- [ ] Tests verify nonce is present
- [ ] No regressions in functionality

---

### **TASK 2: Make Rate Limiting Mandatory**

**File:** `components/web_feedback_ui.py`  
**Lines:** 32-83  
**Priority:** 🟡 HIGH  
**Estimated Time:** 1 hour

**Current Code (PROBLEMATIC):**
```python
# SECURITY FIX: Phase 4 - Rate limiting (optional, requires flask-limiter)
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    RATE_LIMITING_AVAILABLE = True
except ImportError:
    RATE_LIMITING_AVAILABLE = False
    logger.warning("flask-limiter not installed - rate limiting disabled")
```

**The Problem:**
1. Rate limiting is optional - if flask-limiter not installed, no protection
2. Critical endpoints like `/api/approve` should have mandatory rate limiting
3. No per-endpoint limits configured

**What You Must Do:**

1. Make flask-limiter a required dependency
2. Add per-endpoint rate limits
3. Configure stricter limits for state-changing operations
4. Add rate limit headers to responses

**Implementation Steps:**

**Step 1:** Update `requirements.txt` to make flask-limiter required:

```txt
# Add to requirements.txt (if not already present)
Flask-Limiter>=3.5.0
```

**Step 2:** Update `components/web_feedback_ui.py`:

```python
# SECURITY FIX: Rate limiting is MANDATORY for production
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    RATE_LIMITING_AVAILABLE = True
except ImportError:
    RATE_LIMITING_AVAILABLE = False
    # SECURITY FIX: Fail hard if rate limiting not available in production
    import os
    app_env = os.getenv('APP_ENV', 'development')
    if app_env == 'production':
        raise ImportError(
            "flask-limiter is REQUIRED for production deployment. "
            "Install with: pip install Flask-Limiter"
        )
    logger.warning("flask-limiter not installed - rate limiting disabled (development mode only)")

class WebFeedbackServer:
    def __init__(self, config: Dict, ...):
        # ... existing code ...
        
        # SECURITY FIX: Mandatory rate limiting with per-endpoint limits
        self.rate_limiter = None
        if RATE_LIMITING_AVAILABLE:
            self.rate_limiter = Limiter(
                app=self.app,
                key_func=get_remote_address,
                default_limits=["100 per hour", "20 per minute"],  # Global limits
                storage_uri="memory://",  # In-memory storage
                strategy="fixed-window",
                headers_enabled=True,  # Add rate limit headers to responses
                on_breach=self._rate_limit_breach_handler
            )
            logger.info("[OK] Rate limiting enabled: 100/hour, 20/minute (global)")
        else:
            if self.app_env == "production":
                raise RuntimeError("Rate limiting is required in production")
            logger.warning("[WARN] Rate limiting DISABLED (development mode only)")
    
    def _rate_limit_breach_handler(self, request, endpoint):
        """Handle rate limit breaches"""
        logger.warning(
            "Rate limit exceeded: %s from %s for endpoint %s",
            request.remote_addr,
            request.headers.get('User-Agent', 'Unknown'),
            endpoint
        )
        # Log to SDL if available
        # ... SDL logging code ...
```

**Step 3:** Add per-endpoint rate limits:

```python
# Update route decorators in setup_routes method

@self.app.route('/api/approve/<parser_name>', methods=['POST'])
@self.rate_limiter.limit("5 per minute") if self.rate_limiter else lambda f: f
@self.require_auth
def approve_conversion(parser_name: str):
    """Approve a conversion"""
    # ... existing code ...

@self.app.route('/api/reject/<parser_name>', methods=['POST'])
@self.rate_limiter.limit("5 per minute") if self.rate_limiter else lambda f: f
@self.require_auth
def reject_conversion(parser_name: str):
    """Reject a conversion"""
    # ... existing code ...

@self.app.route('/api/modify/<parser_name>', methods=['POST'])
@self.rate_limiter.limit("10 per minute") if self.rate_limiter else lambda f: f
@self.require_auth
def modify_conversion(parser_name: str):
    """Modify a conversion"""
    # ... existing code ...

@self.app.route('/api/pending', methods=['GET'])
@self.rate_limiter.limit("30 per minute") if self.rate_limiter else lambda f: f
@self.require_auth
def get_pending():
    """Get pending conversions"""
    # ... existing code ...
```

**Step 4:** Add tests:

```python
# In tests/test_web_ui.py
import time

class TestRateLimiting:
    """Test rate limiting functionality"""
    
    def test_rate_limiting_enforced(self, web_server):
        """Test that rate limiting blocks excessive requests"""
        client = web_server.app.test_client()
        headers = {'X-PPPE-Token': 'test-token-12345'}
        
        # Make many requests quickly
        responses = []
        for i in range(25):  # Exceed 20/minute limit
            response = client.get('/api/pending', headers=headers)
            responses.append(response.status_code)
            time.sleep(0.1)  # Small delay
        
        # Should have some 429 (Too Many Requests) responses
        assert 429 in responses, "Rate limiting not enforced"
    
    def test_rate_limit_headers_present(self, web_server):
        """Test that rate limit headers are included"""
        client = web_server.app.test_client()
        headers = {'X-PPPE-Token': 'test-token-12345'}
        
        response = client.get('/api/pending', headers=headers)
        
        # Check for rate limit headers
        assert 'X-RateLimit-Limit' in response.headers or \
               'Retry-After' in response.headers or \
               response.status_code == 200
    
    def test_per_endpoint_limits(self, web_server):
        """Test that different endpoints have different limits"""
        client = web_server.app.test_client()
        headers = {'X-PPPE-Token': 'test-token-12345'}
        
        # Approve endpoint should have stricter limit (5/min)
        approve_responses = []
        for i in range(10):
            response = client.post('/api/approve/test_parser', headers=headers, json={})
            approve_responses.append(response.status_code)
            time.sleep(0.1)
        
        # Should hit rate limit faster than pending endpoint
        assert 429 in approve_responses[:7], "Approve endpoint should have stricter limit"
```

**Verification Checklist:**
- [ ] flask-limiter is required dependency
- [ ] Application fails to start in production without flask-limiter
- [ ] Per-endpoint limits configured
- [ ] Rate limit headers included in responses
- [ ] Tests verify rate limiting works
- [ ] No regressions

---

### **TASK 3: Restrict Kubernetes NetworkPolicy Egress**

**File:** `k8s/base/networkpolicy.yaml`  
**Lines:** 89-100  
**Priority:** 🟡 HIGH  
**Estimated Time:** 2 hours

**Current Code (PROBLEMATIC):**
```yaml
# Allow to external APIs (Observo, Claude, etc.)
- to:
    - ipBlock:
        cidr: 0.0.0.0/0  # ← PROBLEM: Allows all external IPs
        except:
          - 169.254.169.254/32  # Exclude AWS metadata
          - 127.0.0.0/8         # Exclude loopback
  ports:
    - protocol: TCP
      port: 443   # HTTPS
    - protocol: TCP
      port: 80    # HTTP (for non-HTTPS APIs)
```

**The Problem:**
1. Allows egress to all external IPs (0.0.0.0/0)
2. Only excludes AWS metadata and loopback
3. Doesn't exclude private networks (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
4. Could allow SSRF attacks or data exfiltration

**What You Must Do:**

1. Restrict egress to specific known API endpoints (DNS-based or IP ranges)
2. Exclude private network ranges
3. Document which APIs are allowed
4. Consider using DNS-based policies

**Implementation Steps:**

**Step 1:** Update `k8s/base/networkpolicy.yaml`:

```yaml
---
# Egress NetworkPolicy - Restrictive outbound traffic
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: purple-parser-eater-egress
  namespace: purple-pipeline
  labels:
    app: purple-parser-eater
    component: network-policy
spec:
  podSelector:
    matchLabels:
      app: purple-parser-eater
  policyTypes:
    - Egress
  egress:
    # Allow DNS queries (required for external services)
    - to:
        - namespaceSelector:
            matchLabels:
              name: kube-system
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
    
    # SECURITY FIX: Restrict external API access to specific endpoints
    # Anthropic Claude API
    - to:
        - ipBlock:
            cidr: 52.84.0.0/15  # AWS us-east-1 (Anthropic API)
        - ipBlock:
            cidr: 52.1.0.0/16   # AWS us-east-1 alternative range
      ports:
        - protocol: TCP
          port: 443
    
    # GitHub API
    - to:
        - ipBlock:
            cidr: 140.82.112.0/20  # GitHub API IP ranges
        - ipBlock:
            cidr: 192.30.252.0/22
        - ipBlock:
            cidr: 185.199.108.0/22
      ports:
        - protocol: TCP
          port: 443
    
    # Observo.ai API (update with actual IP ranges)
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0  # TODO: Replace with actual Observo.ai IP ranges
            except:
              - 169.254.169.254/32  # AWS metadata
              - 127.0.0.0/8         # Loopback
              - 10.0.0.0/8          # Private network A
              - 172.16.0.0/12       # Private network B
              - 192.168.0.0/16      # Private network C
              - 224.0.0.0/4         # Multicast
              - 240.0.0.0/4         # Reserved
      ports:
        - protocol: TCP
          port: 443  # HTTPS only (remove port 80)
    
    # SentinelOne SDL API (update with actual IP ranges)
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0  # TODO: Replace with actual SentinelOne IP ranges
            except:
              - 169.254.169.254/32
              - 127.0.0.0/8
              - 10.0.0.0/8
              - 172.16.0.0/12
              - 192.168.0.0/16
      ports:
        - protocol: TCP
          port: 443
    
    # Allow to Kafka (internal service)
    - to:
        - podSelector:
            matchLabels:
              app: kafka
      ports:
        - protocol: TCP
          port: 9092
    
    # Allow to Milvus (vector database)
    - to:
        - podSelector:
            matchLabels:
              app: milvus
      ports:
        - protocol: TCP
          port: 19530
        - protocol: TCP
          port: 9091
    
    # Allow internal pod-to-pod communication
    - to:
        - podSelector:
            matchLabels:
              app: purple-parser-eater
      ports:
        - protocol: TCP
          port: 8080
        - protocol: TCP
          port: 9090

---
# SECURITY FIX: Add documentation comment
# Note: For production, consider using DNS-based NetworkPolicies or
# ExternalName services to restrict egress more precisely.
# 
# To find actual IP ranges for APIs:
# - Anthropic: nslookup api.anthropic.com
# - GitHub: https://api.github.com/meta (check API IPs)
# - Observo: Contact Observo.ai support for IP ranges
# - SentinelOne: Contact SentinelOne support for SDL endpoint IPs
```

**Step 2:** Create script to discover API IP ranges:

```python
# scripts/discover_api_ips.py
#!/usr/bin/env python3
"""
Discover IP ranges for external APIs to update NetworkPolicy.

Run this script to get current IP addresses for APIs.
"""

import socket
import dns.resolver  # Requires dnspython

def get_ip_ranges(domain: str) -> list:
    """Get IP addresses for a domain"""
    try:
        # Try A records
        answers = dns.resolver.resolve(domain, 'A')
        ips = [str(rdata) for rdata in answers]
        return ips
    except Exception as e:
        print(f"Error resolving {domain}: {e}")
        return []

def main():
    apis = {
        'Anthropic': 'api.anthropic.com',
        'GitHub': 'api.github.com',
        'Observo': 'api.observo.ai',  # Update with actual domain
        'SentinelOne SDL': 'sdl.sentinelone.com',  # Update with actual domain
    }
    
    print("API IP Ranges Discovery")
    print("=" * 50)
    
    for name, domain in apis.items():
        print(f"\n{name} ({domain}):")
        ips = get_ip_ranges(domain)
        if ips:
            for ip in ips:
                print(f"  - {ip}")
        else:
            print(f"  - Could not resolve")
    
    print("\n" + "=" * 50)
    print("\nUpdate k8s/base/networkpolicy.yaml with these IP ranges")
    print("Convert to CIDR notation (e.g., 1.2.3.4 -> 1.2.3.4/32)")

if __name__ == '__main__':
    main()
```

**Step 3:** Add tests for NetworkPolicy:

```yaml
# k8s/base/networkpolicy-test.yaml (for testing)
# Test that NetworkPolicy blocks unauthorized egress
```

**Step 4:** Document the change:

Create `docs/security/NETWORK_POLICY_RESTRICTIONS.md`:

```markdown
# Network Policy Restrictions

## Egress Restrictions

The application's egress NetworkPolicy restricts outbound traffic to:

1. **DNS**: kube-system namespace only
2. **Anthropic API**: Specific IP ranges (AWS us-east-1)
3. **GitHub API**: Specific IP ranges
4. **Observo.ai API**: Specific IP ranges (TBD)
5. **SentinelOne SDL**: Specific IP ranges (TBD)
6. **Internal Services**: Kafka, Milvus, same-namespace pods

## Private Networks Blocked

The following private network ranges are explicitly blocked:
- 10.0.0.0/8
- 172.16.0.0/12
- 192.168.0.0/16
- 169.254.169.254/32 (AWS metadata)

## Updating IP Ranges

To update IP ranges:
1. Run `scripts/discover_api_ips.py`
2. Convert IPs to CIDR notation
3. Update `k8s/base/networkpolicy.yaml`
4. Test in staging before production
```

**Verification Checklist:**
- [ ] Private networks excluded
- [ ] Only HTTPS (443) allowed for external APIs
- [ ] Specific IP ranges configured (or documented as TODO)
- [ ] DNS queries still work
- [ ] Internal services still accessible
- [ ] Documentation updated

---

### **TASK 4: Implement Secret Rotation Mechanism**

**Files:** Multiple (create new utility)  
**Priority:** 🟡 HIGH  
**Estimated Time:** 4 hours

**Current Situation:**
- Secrets are loaded from environment variables
- No expiration checking
- No rotation mechanism
- Secrets remain valid indefinitely

**What You Must Do:**

1. Create secret manager utility
2. Add expiration checking
3. Implement rotation mechanism
4. Add warnings for expired secrets

**Implementation Steps:**

**Step 1:** Create `utils/secret_manager.py`:

```python
#!/usr/bin/env python3
"""
Secret Management Utility

Manages secret lifecycle: expiration, rotation, validation.
"""

import os
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class SecretMetadata:
    """Metadata about a secret"""
    name: str
    created_at: str
    expires_at: Optional[str]
    rotated_at: Optional[str]
    rotation_days: int
    last_warning: Optional[str] = None


class SecretManager:
    """
    Manages secret lifecycle and rotation.
    
    Features:
    - Secret expiration tracking
    - Rotation reminders
    - Expiration warnings
    - Rotation history
    """
    
    DEFAULT_ROTATION_DAYS = 90
    
    def __init__(self, metadata_file: Optional[Path] = None):
        """
        Initialize secret manager.
        
        Args:
            metadata_file: Path to store secret metadata (default: data/secret_metadata.json)
        """
        if metadata_file is None:
            metadata_file = Path("data/secret_metadata.json")
        
        self.metadata_file = metadata_file
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        self._metadata: Dict[str, SecretMetadata] = self._load_metadata()
    
    def _load_metadata(self) -> Dict[str, SecretMetadata]:
        """Load secret metadata from file"""
        if not self.metadata_file.exists():
            return {}
        
        try:
            with open(self.metadata_file, 'r') as f:
                data = json.load(f)
                return {
                    name: SecretMetadata(**meta)
                    for name, meta in data.items()
                }
        except Exception as e:
            logger.warning(f"Could not load secret metadata: {e}")
            return {}
    
    def _save_metadata(self):
        """Save secret metadata to file"""
        try:
            data = {
                name: asdict(meta)
                for name, meta in self._metadata.items()
            }
            with open(self.metadata_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save secret metadata: {e}")
    
    def register_secret(
        self,
        name: str,
        rotation_days: int = None,
        created_at: Optional[datetime] = None
    ):
        """
        Register a secret for tracking.
        
        Args:
            name: Secret name (e.g., 'ANTHROPIC_API_KEY')
            rotation_days: Days until rotation required (default: 90)
            created_at: When secret was created (default: now)
        """
        rotation_days = rotation_days or self.DEFAULT_ROTATION_DAYS
        created_at = created_at or datetime.utcnow()
        expires_at = created_at + timedelta(days=rotation_days)
        
        if name not in self._metadata:
            self._metadata[name] = SecretMetadata(
                name=name,
                created_at=created_at.isoformat(),
                expires_at=expires_at.isoformat(),
                rotated_at=None,
                rotation_days=rotation_days
            )
            self._save_metadata()
            logger.info(f"Registered secret: {name} (expires: {expires_at.date()})")
    
    def check_secret_expiration(self, name: str) -> Tuple[bool, Optional[str]]:
        """
        Check if secret is expired or nearing expiration.
        
        Returns:
            Tuple of (is_valid, warning_message)
        """
        if name not in self._metadata:
            # Secret not registered - register it now
            self.register_secret(name)
            return True, None
        
        meta = self._metadata[name]
        
        if not meta.expires_at:
            return True, None
        
        expires_at = datetime.fromisoformat(meta.expires_at)
        now = datetime.utcnow()
        days_until_expiry = (expires_at - now).days
        
        if days_until_expiry < 0:
            return False, f"Secret {name} expired {abs(days_until_expiry)} days ago"
        
        if days_until_expiry <= 7:
            return True, f"Secret {name} expires in {days_until_expiry} days - rotate soon!"
        
        if days_until_expiry <= 30:
            # Warn once per week
            last_warning = datetime.fromisoformat(meta.last_warning) if meta.last_warning else None
            if not last_warning or (now - last_warning).days >= 7:
                meta.last_warning = now.isoformat()
                self._save_metadata()
                return True, f"Secret {name} expires in {days_until_expiry} days"
        
        return True, None
    
    def rotate_secret(self, name: str, new_secret: Optional[str] = None):
        """
        Mark secret as rotated.
        
        Args:
            name: Secret name
            new_secret: New secret value (optional, for validation)
        """
        if name not in self._metadata:
            self.register_secret(name)
        
        meta = self._metadata[name]
        meta.rotated_at = datetime.utcnow().isoformat()
        meta.created_at = datetime.utcnow().isoformat()
        
        # Calculate new expiration
        expires_at = datetime.utcnow() + timedelta(days=meta.rotation_days)
        meta.expires_at = expires_at.isoformat()
        meta.last_warning = None
        
        self._save_metadata()
        logger.info(f"Secret {name} rotated (new expiration: {expires_at.date()})")
    
    def validate_all_secrets(self) -> Dict[str, Tuple[bool, Optional[str]]]:
        """
        Validate all registered secrets.
        
        Returns:
            Dict mapping secret name to (is_valid, warning)
        """
        results = {}
        
        # Check all registered secrets
        for name in self._metadata.keys():
            is_valid, warning = self.check_secret_expiration(name)
            results[name] = (is_valid, warning)
            
            if warning:
                if is_valid:
                    logger.warning(f"Secret warning: {warning}")
                else:
                    logger.error(f"Secret expired: {warning}")
        
        return results
```

**Step 2:** Integrate into `continuous_conversion_service.py`:

```python
# At startup, check all secrets
from utils.secret_manager import SecretManager

class ContinuousConversionService:
    def __init__(self, config_path: Path):
        # ... existing code ...
        self.secret_manager = SecretManager()
    
    async def initialize(self):
        # ... existing initialization ...
        
        # SECURITY FIX: Validate secret expiration
        logger.info("Validating secret expiration...")
        secret_results = self.secret_manager.validate_all_secrets()
        
        expired_secrets = []
        for name, (is_valid, warning) in secret_results.items():
            if not is_valid:
                expired_secrets.append(name)
            elif warning:
                logger.warning(f"Secret: {warning}")
        
        if expired_secrets:
            logger.error(f"Expired secrets detected: {', '.join(expired_secrets)}")
            if self.app_env == "production":
                raise ValueError(
                    f"Cannot start in production with expired secrets: {', '.join(expired_secrets)}"
                )
        
        # Register secrets that aren't registered yet
        required_secrets = [
            'ANTHROPIC_API_KEY',
            'WEB_UI_AUTH_TOKEN',
            'GITHUB_TOKEN',
            'SDL_API_KEY',
        ]
        
        for secret_name in required_secrets:
            if os.getenv(secret_name):
                self.secret_manager.register_secret(secret_name)
```

**Step 3:** Add CLI command for rotation:

```python
# scripts/rotate_secret.py
#!/usr/bin/env python3
"""Secret rotation utility"""

import sys
import os
from pathlib import Path
from utils.secret_manager import SecretManager

def main():
    if len(sys.argv) < 2:
        print("Usage: python rotate_secret.py <SECRET_NAME>")
        sys.exit(1)
    
    secret_name = sys.argv[1]
    manager = SecretManager()
    
    # Check current status
    is_valid, warning = manager.check_secret_expiration(secret_name)
    print(f"Secret: {secret_name}")
    print(f"Status: {'Valid' if is_valid else 'Expired'}")
    if warning:
        print(f"Warning: {warning}")
    
    # Mark as rotated
    manager.rotate_secret(secret_name)
    print(f"\nSecret {secret_name} marked as rotated")
    print("Update the actual secret value in your .env file or secrets manager")

if __name__ == '__main__':
    main()
```

**Step 4:** Add tests:

```python
# tests/test_secret_manager.py
import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from utils.secret_manager import SecretManager, SecretMetadata

class TestSecretManager:
    def test_secret_registration(self):
        """Test secret registration"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SecretManager(metadata_file=Path(tmpdir) / "secrets.json")
            
            manager.register_secret("TEST_SECRET", rotation_days=30)
            
            is_valid, warning = manager.check_secret_expiration("TEST_SECRET")
            assert is_valid
            assert warning is None
    
    def test_secret_expiration_detection(self):
        """Test expired secret detection"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SecretManager(metadata_file=Path(tmpdir) / "secrets.json")
            
            # Register secret that expired 10 days ago
            expired_date = datetime.utcnow() - timedelta(days=100)
            manager.register_secret("EXPIRED_SECRET", rotation_days=90, created_at=expired_date)
            
            is_valid, warning = manager.check_secret_expiration("EXPIRED_SECRET")
            assert not is_valid
            assert "expired" in warning.lower()
    
    def test_secret_rotation(self):
        """Test secret rotation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SecretManager(metadata_file=Path(tmpdir) / "secrets.json")
            
            manager.register_secret("ROTATE_SECRET", rotation_days=90)
            manager.rotate_secret("ROTATE_SECRET")
            
            meta = manager._metadata["ROTATE_SECRET"]
            assert meta.rotated_at is not None
            assert meta.created_at != meta.rotated_at
```

**Verification Checklist:**
- [ ] Secret manager created
- [ ] Expiration checking works
- [ ] Rotation mechanism works
- [ ] Warnings logged appropriately
- [ ] Integration with service startup
- [ ] Tests pass
- [ ] Documentation updated

---

### **TASK 5: Add Log Sanitization**

**Files:** Multiple (create utility, update logging)  
**Priority:** 🟡 HIGH  
**Estimated Time:** 2 hours

**Current Situation:**
- Logging may contain sensitive data (API keys, tokens)
- No sanitization before logging
- Secrets could leak in logs

**What You Must Do:**

1. Create log sanitization utility
2. Update all logging calls to use sanitization
3. Detect and redact API keys, tokens, passwords
4. Test that no secrets appear in logs

**Implementation Steps:**

**Step 1:** Create `utils/log_sanitizer.py`:

```python
#!/usr/bin/env python3
"""
Log Sanitization Utility

Removes sensitive data from logs before writing.
"""

import re
import logging
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)


class LogSanitizer:
    """
    Sanitizes log data to prevent secret leakage.
    
    Detects and redacts:
    - API keys (Anthropic, GitHub, etc.)
    - Authentication tokens
    - Passwords
    - Other sensitive patterns
    """
    
    # Patterns for detecting secrets
    SECRET_PATTERNS = [
        # Anthropic API keys: sk-ant-api03-...
        (r'sk-ant-[a-zA-Z0-9-]{20,}', '***ANTHROPIC_API_KEY_REDACTED***'),
        
        # GitHub tokens: ghp_... or github_pat_...
        (r'ghp_[a-zA-Z0-9]{36}', '***GITHUB_TOKEN_REDACTED***'),
        (r'github_pat_[a-zA-Z0-9_]{82}', '***GITHUB_TOKEN_REDACTED***'),
        
        # Generic API keys
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_-]{20,})', r'api_key="***REDACTED***"'),
        (r'token["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_-]{20,})', r'token="***REDACTED***"'),
        
        # Passwords
        (r'password["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'password="***REDACTED***"'),
        (r'passwd["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'passwd="***REDACTED***"'),
        
        # AWS credentials
        (r'AKIA[0-9A-Z]{16}', '***AWS_ACCESS_KEY_REDACTED***'),
        (r'aws[_-]?secret[_-]?access[_-]?key["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'aws_secret_access_key="***REDACTED***"'),
        
        # MinIO credentials (if default)
        (r'minioadmin', '***MINIO_CREDENTIAL_REDACTED***'),
    ]
    
    # Keys that should always be redacted
    SENSITIVE_KEYS = [
        'api_key', 'api-key', 'apikey',
        'token', 'auth_token', 'auth-token',
        'password', 'passwd', 'pwd',
        'secret', 'secret_key', 'secret-key',
        'credential', 'credentials',
        'access_key', 'access-key',
        'private_key', 'private-key',
    ]
    
    @classmethod
    def sanitize_string(cls, text: str) -> str:
        """
        Sanitize a string by redacting secrets.
        
        Args:
            text: String that may contain secrets
            
        Returns:
            Sanitized string with secrets redacted
        """
        if not isinstance(text, str):
            return text
        
        sanitized = text
        
        # Apply pattern-based redaction
        for pattern, replacement in cls.SECRET_PATTERNS:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        
        return sanitized
    
    @classmethod
    def sanitize_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize a dictionary by redacting sensitive values.
        
        Args:
            data: Dictionary that may contain secrets
            
        Returns:
            Sanitized dictionary with secrets redacted
        """
        if not isinstance(data, dict):
            return data
        
        sanitized = {}
        
        for key, value in data.items():
            # Check if key indicates sensitive data
            key_lower = key.lower()
            is_sensitive_key = any(
                sensitive in key_lower
                for sensitive in cls.SENSITIVE_KEYS
            )
            
            if is_sensitive_key and isinstance(value, str):
                # Redact sensitive values
                sanitized[key] = '***REDACTED***'
            elif isinstance(value, dict):
                # Recursively sanitize nested dicts
                sanitized[key] = cls.sanitize_dict(value)
            elif isinstance(value, list):
                # Sanitize list items
                sanitized[key] = [
                    cls.sanitize_dict(item) if isinstance(item, dict)
                    else cls.sanitize_string(item) if isinstance(item, str)
                    else item
                    for item in value
                ]
            elif isinstance(value, str):
                # Sanitize string values
                sanitized[key] = cls.sanitize_string(value)
            else:
                sanitized[key] = value
        
        return sanitized
    
    @classmethod
    def sanitize_log_data(cls, data: Union[str, Dict, List]) -> Union[str, Dict, List]:
        """
        Sanitize log data (handles multiple types).
        
        Args:
            data: Data to sanitize (string, dict, or list)
            
        Returns:
            Sanitized data
        """
        if isinstance(data, str):
            return cls.sanitize_string(data)
        elif isinstance(data, dict):
            return cls.sanitize_dict(data)
        elif isinstance(data, list):
            return [
                cls.sanitize_log_data(item)
                for item in data
            ]
        else:
            return data
```

**Step 2:** Update `utils/logger.py` to use sanitization:

```python
# Update utils/logger.py
from utils.log_sanitizer import LogSanitizer

class SanitizedLogger:
    """Logger wrapper that sanitizes log data"""
    
    def __init__(self, logger_instance):
        self.logger = logger_instance
    
    def _sanitize_args(self, args):
        """Sanitize log arguments"""
        return tuple(LogSanitizer.sanitize_log_data(arg) for arg in args)
    
    def _sanitize_kwargs(self, kwargs):
        """Sanitize log keyword arguments"""
        sanitized = {}
        for key, value in kwargs.items():
            if key == 'extra' and isinstance(value, dict):
                sanitized[key] = LogSanitizer.sanitize_dict(value)
            else:
                sanitized[key] = LogSanitizer.sanitize_log_data(value)
        return sanitized
    
    def info(self, msg, *args, **kwargs):
        args = self._sanitize_args(args)
        kwargs = self._sanitize_kwargs(kwargs)
        self.logger.info(msg, *args, **kwargs)
    
    def warning(self, msg, *args, **kwargs):
        args = self._sanitize_args(args)
        kwargs = self._sanitize_kwargs(kwargs)
        self.logger.warning(msg, *args, **kwargs)
    
    def error(self, msg, *args, **kwargs):
        args = self._sanitize_args(args)
        kwargs = self._sanitize_kwargs(kwargs)
        self.logger.error(msg, *args, **kwargs)
    
    def debug(self, msg, *args, **kwargs):
        args = self._sanitize_args(args)
        kwargs = self._sanitize_kwargs(kwargs)
        self.logger.debug(msg, *args, **kwargs)
```

**Step 3:** Update logging calls in critical files:

```python
# In components/web_feedback_ui.py
from utils.log_sanitizer import LogSanitizer

# Update logging calls
logger.info("Request", extra=LogSanitizer.sanitize_dict({
    'method': request.method,
    'path': request.path,
    'headers': dict(request.headers),  # Will be sanitized
    'remote_addr': request.remote_addr,
}))
```

**Step 4:** Add tests:

```python
# tests/test_log_sanitizer.py
import pytest
from utils.log_sanitizer import LogSanitizer

class TestLogSanitizer:
    def test_anthropic_key_redaction(self):
        """Test Anthropic API key is redacted"""
        text = "API key: sk-ant-REDACTED"
        sanitized = LogSanitizer.sanitize_string(text)
        
        assert "sk-ant-" not in sanitized
        assert "***ANTHROPIC_API_KEY_REDACTED***" in sanitized
    
    def test_github_token_redaction(self):
        """Test GitHub token is redacted"""
        text = "Token: ghp_REDACTED"
        sanitized = LogSanitizer.sanitize_string(text)
        
        assert "ghp_" not in sanitized
        assert "***GITHUB_TOKEN_REDACTED***" in sanitized
    
    def test_dict_sanitization(self):
        """Test dictionary sanitization"""
        data = {
            'api_key': 'sk-ant-api03-test123',
            'user': 'testuser',
            'config': {
                'token': 'ghp_test123',
                'setting': 'value'
            }
        }
        
        sanitized = LogSanitizer.sanitize_dict(data)
        
        assert sanitized['api_key'] == '***REDACTED***'
        assert sanitized['user'] == 'testuser'  # Not sensitive
        assert sanitized['config']['token'] == '***REDACTED***'
        assert sanitized['config']['setting'] == 'value'
    
    def test_no_false_positives(self):
        """Test that legitimate data is not redacted"""
        text = "User api_key field contains: test_value"
        sanitized = LogSanitizer.sanitize_string(text)
        
        # Should not redact "test_value" (too short, not a real key)
        assert "test_value" in sanitized
```

**Verification Checklist:**
- [ ] Log sanitizer created
- [ ] All secret patterns detected
- [ ] Dictionary sanitization works
- [ ] Logging calls updated
- [ ] Tests verify redaction
- [ ] No secrets in test logs

---

### **TASK 6: Fix Health Check Authentication Issue**

**File:** `components/web_feedback_ui.py`  
**Lines:** 456-470  
**Priority:** 🟡 HIGH  
**Estimated Time:** 1 hour

**Current Code (PROBLEMATIC):**
```python
@self.app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint"""
    # Does NOT require auth - OK for metrics
```

But `/api/status` requires auth, and Docker health check doesn't provide token.

**The Problem:**
1. Docker health check calls `/api/status` without authentication
2. Health check will fail if auth is required
3. Need a public health endpoint or health check needs token

**What You Must Do:**

1. Create `/health` endpoint that doesn't require auth (read-only status)
2. Update Docker health checks to use `/health`
3. Keep `/api/status` with full details (requires auth)

**Implementation Steps:**

**Step 1:** Add `/health` endpoint in `components/web_feedback_ui.py`:

```python
@self.app.route('/health')
def health_check():
    """
    Public health check endpoint (no authentication required).
    
    SECURITY: Contains only non-sensitive status information.
    Used by Docker/Kubernetes health probes.
    
    Returns:
        JSON with basic health status
    """
    try:
        # Get basic status (no sensitive data)
        status = {
            'status': 'healthy',
            'service': 'purple-pipeline-parser-eater',
            'version': '9.0.0',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        
        # Optionally check if service is running
        if hasattr(self, 'service') and self.service:
            try:
                service_status = self.service.get_status()
                status['is_running'] = service_status.get('is_running', False)
            except Exception:
                status['is_running'] = False
        else:
            status['is_running'] = False
        
        # Return 200 if healthy, 503 if unhealthy
        http_status = 200 if status.get('is_running', False) else 503
        return jsonify(status), http_status
    
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': 'Health check failed'
        }), 503
```

**Step 2:** Update `Dockerfile` health check:

```dockerfile
# SECURITY FIX: Use /health endpoint (no auth required)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1
```

**Step 3:** Update `docker-compose.yml` health check:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/health"]  # ← Changed from /api/status
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 120s
```

**Step 4:** Update Kubernetes health probes:

```yaml
# In k8s/base/deployment-app.yaml
livenessProbe:
  httpGet:
    path: /health  # ← Changed from /api/status
    port: http
    scheme: HTTP
  # ... rest unchanged

readinessProbe:
  httpGet:
    path: /health  # ← Changed from /api/status
    port: http
    scheme: HTTP
  # ... rest unchanged

startupProbe:
  httpGet:
    path: /health  # ← Changed from /api/status
    port: http
    scheme: HTTP
  # ... rest unchanged
```

**Step 5:** Add tests:

```python
# In tests/test_web_ui.py
class TestHealthCheck:
    def test_health_endpoint_no_auth_required(self, web_server):
        """Test that /health endpoint doesn't require authentication"""
        client = web_server.app.test_client()
        
        # Should work without auth token
        response = client.get('/health')
        
        assert response.status_code in [200, 503]  # Healthy or unhealthy, but accessible
        data = response.get_json()
        assert 'status' in data
        assert 'service' in data
    
    def test_health_endpoint_returns_basic_info(self, web_server):
        """Test that /health returns basic status"""
        client = web_server.app.test_client()
        
        response = client.get('/health')
        data = response.get_json()
        
        assert data['service'] == 'purple-pipeline-parser-eater'
        assert 'version' in data
        assert 'timestamp' in data
```

**Verification Checklist:**
- [ ] `/health` endpoint created
- [ ] No authentication required
- [ ] Docker health check updated
- [ ] Kubernetes probes updated
- [ ] Tests verify health endpoint works
- [ ] No sensitive data in health response

---

### **TASK 7: Add Input Size Limits**

**Files:** `components/dataplane_validator.py`, `components/transform_executor.py`  
**Priority:** 🟡 HIGH  
**Estimated Time:** 2 hours

**Current Situation:**
- No limits on Lua code size
- No limits on event file size
- Large inputs could cause DoS

**What You Must Do:**

1. Add size limits for Lua code
2. Add size limits for events
3. Add count limits for events
4. Validate before processing

**Implementation Steps:**

**Step 1:** Add constants and validation to `components/dataplane_validator.py`:

```python
class DataplaneValidator:
    """Validates generated Lua via dataplane binary."""
    
    # SECURITY FIX: Input size limits
    MAX_LUA_CODE_SIZE = 1 * 1024 * 1024  # 1MB
    MAX_EVENTS_COUNT = 10000
    MAX_EVENT_SIZE = 100 * 1024  # 100KB per event
    MAX_TOTAL_EVENTS_SIZE = 10 * 1024 * 1024  # 10MB total
    
    def __init__(self, binary_path: str, ocsf_required_fields: List[str], timeout: int = 30) -> None:
        # ... existing code ...
    
    def validate(self, lua_code: str, events: List[Dict[str, Any]], parser_id: str) -> DataplaneValidationResult:
        # SECURITY FIX: Validate input sizes before processing
        validation_error = self._validate_input_sizes(lua_code, events, parser_id)
        if validation_error:
            return DataplaneValidationResult(
                success=False,
                output_events=[],
                stderr=validation_error,
                ocsf_missing_fields=[],
                error="input_size_exceeded",
            )
        
        # ... rest of existing validation code ...
    
    def _validate_input_sizes(
        self,
        lua_code: str,
        events: List[Dict[str, Any]],
        parser_id: str
    ) -> Optional[str]:
        """
        Validate input sizes are within limits.
        
        Returns:
            Error message if validation fails, None if valid
        """
        # Check Lua code size
        lua_size = len(lua_code.encode('utf-8'))
        if lua_size > self.MAX_LUA_CODE_SIZE:
            return (
                f"Lua code too large: {lua_size} bytes "
                f"(maximum: {self.MAX_LUA_CODE_SIZE} bytes)"
            )
        
        # Check event count
        if len(events) > self.MAX_EVENTS_COUNT:
            return (
                f"Too many events: {len(events)} "
                f"(maximum: {self.MAX_EVENTS_COUNT})"
            )
        
        # Check individual event sizes and total size
        total_size = 0
        for i, event in enumerate(events):
            try:
                event_json = json.dumps(event)
                event_size = len(event_json.encode('utf-8'))
                
                if event_size > self.MAX_EVENT_SIZE:
                    return (
                        f"Event {i} too large: {event_size} bytes "
                        f"(maximum: {self.MAX_EVENT_SIZE} bytes per event)"
                    )
                
                total_size += event_size
                
            except Exception as e:
                return f"Error serializing event {i}: {str(e)}"
        
        if total_size > self.MAX_TOTAL_EVENTS_SIZE:
            return (
                f"Total events size too large: {total_size} bytes "
                f"(maximum: {self.MAX_TOTAL_EVENTS_SIZE} bytes)"
            )
        
        return None  # All validations passed
```

**Step 2:** Apply same limits to `components/transform_executor.py`:

```python
class DataplaneExecutor(TransformExecutor):
    """Execute transform via dataplane binary (parity with production)."""
    
    # SECURITY FIX: Input size limits (same as validator)
    MAX_LUA_CODE_SIZE = 1 * 1024 * 1024  # 1MB
    MAX_EVENT_SIZE = 100 * 1024  # 100KB
    
    def _run_sync(self, lua_code: str, event: Dict[str, Any], parser_id: str) -> Tuple[bool, Dict[str, Any]]:
        # SECURITY FIX: Validate input sizes
        lua_size = len(lua_code.encode('utf-8'))
        if lua_size > self.MAX_LUA_CODE_SIZE:
            logger.error("Lua code too large: %d bytes", lua_size)
            return False, {"error": f"Lua code too large: {lua_size} bytes"}
        
        try:
            event_json = json.dumps(event)
            event_size = len(event_json.encode('utf-8'))
            if event_size > self.MAX_EVENT_SIZE:
                logger.error("Event too large: %d bytes", event_size)
                return False, {"error": f"Event too large: {event_size} bytes"}
        except Exception as e:
            logger.error("Error serializing event: %s", e)
            return False, {"error": f"Invalid event: {str(e)}"}
        
        # ... rest of existing code ...
```

**Step 3:** Add tests:

```python
# In tests/test_dataplane_validator.py
class TestInputSizeLimits:
    def test_lua_code_size_limit(self):
        """Test that oversized Lua code is rejected"""
        validator = DataplaneValidator(
            binary_path="/fake/path",
            ocsf_required_fields=["class_uid"],
            timeout=30
        )
        
        # Create oversized Lua code (2MB)
        oversized_lua = "-- " + "x" * (2 * 1024 * 1024)
        
        result = validator.validate(
            lua_code=oversized_lua,
            events=[{"test": "data"}],
            parser_id="test"
        )
        
        assert not result.success
        assert result.error == "input_size_exceeded"
        assert "too large" in result.stderr.lower()
    
    def test_event_count_limit(self):
        """Test that too many events are rejected"""
        validator = DataplaneValidator(
            binary_path="/fake/path",
            ocsf_required_fields=["class_uid"],
            timeout=30
        )
        
        # Create too many events (15000)
        too_many_events = [{"test": i} for i in range(15000)]
        
        result = validator.validate(
            lua_code="-- test",
            events=too_many_events,
            parser_id="test"
        )
        
        assert not result.success
        assert "too many events" in result.stderr.lower()
    
    def test_valid_inputs_pass(self):
        """Test that valid-sized inputs pass"""
        validator = DataplaneValidator(
            binary_path="/fake/path",
            ocsf_required_fields=["class_uid"],
            timeout=30
        )
        
        # Valid Lua code (small)
        valid_lua = "-- test code"
        # Valid events (small)
        valid_events = [{"test": "data"}]
        
        # Should not fail on size (may fail on other validation, but not size)
        # We can't fully test without binary, but we can test size validation
        error = validator._validate_input_sizes(valid_lua, valid_events, "test")
        assert error is None
```

**Verification Checklist:**
- [ ] Size limits defined as constants
- [ ] Validation before processing
- [ ] Clear error messages
- [ ] Tests for all limits
- [ ] Both files updated consistently

---

### **TASK 8: Remove Unnecessary Kubernetes Capability**

**File:** `k8s/base/deployment-app.yaml`  
**Lines:** 66-70  
**Priority:** 🟡 HIGH  
**Estimated Time:** 30 minutes

**Current Code (PROBLEMATIC):**
```yaml
capabilities:
  drop:
    - ALL
  add:
    - NET_BIND_SERVICE  # ← PROBLEM: Not needed for port 8080
```

**The Problem:**
1. `NET_BIND_SERVICE` allows binding to ports < 1024
2. Application uses port 8080, which doesn't require this capability
3. Unnecessary privilege escalation

**What You Must Do:**

Remove the `add` section entirely.

**Implementation Steps:**

**Step 1:** Update `k8s/base/deployment-app.yaml`:

```yaml
securityContext:
  allowPrivilegeEscalation: false
  runAsNonRoot: true
  runAsUser: 999
  runAsGroup: 999
  readOnlyRootFilesystem: true
  capabilities:
    drop:
      - ALL
    # SECURITY FIX: Removed NET_BIND_SERVICE - not needed for port 8080
    # Port 8080 does not require special capabilities
    # No 'add' section needed
  seccompProfile:
    type: RuntimeDefault
```

**Step 2:** Verify application works:

```bash
# Test that application starts without NET_BIND_SERVICE
kubectl apply -f k8s/base/deployment-app.yaml
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=purple-pipeline-parser-eater --timeout=300s
kubectl logs -l app.kubernetes.io/name=purple-pipeline-parser-eater
```

**Step 3:** Add comment explaining the change:

```yaml
# SECURITY FIX: Removed NET_BIND_SERVICE capability
# 
# NET_BIND_SERVICE allows binding to ports < 1024 (privileged ports)
# Our application uses port 8080, which is an unprivileged port
# and does not require this capability.
#
# Removing unnecessary capabilities reduces attack surface and
# follows principle of least privilege (STIG V-242437)
```

**Verification Checklist:**
- [ ] NET_BIND_SERVICE removed
- [ ] Application starts successfully
- [ ] Port 8080 accessible
- [ ] No capability-related errors
- [ ] Documentation updated

---

## 📋 COMPLETE DELIVERABLES CHECKLIST

After completing all 8 tasks:

### **Code Changes:**
- [ ] `components/web_feedback_ui.py` - CSP nonce, rate limiting, health endpoint
- [ ] `k8s/base/networkpolicy.yaml` - Restricted egress
- [ ] `k8s/base/deployment-app.yaml` - Removed capability
- [ ] `utils/secret_manager.py` - NEW FILE
- [ ] `utils/log_sanitizer.py` - NEW FILE
- [ ] `components/dataplane_validator.py` - Input size limits
- [ ] `components/transform_executor.py` - Input size limits
- [ ] `continuous_conversion_service.py` - Secret validation
- [ ] `Dockerfile` - Health check updated
- [ ] `docker-compose.yml` - Health check updated

### **Tests:**
- [ ] `tests/test_web_ui.py` - CSP, rate limiting, health tests
- [ ] `tests/test_secret_manager.py` - NEW FILE
- [ ] `tests/test_log_sanitizer.py` - NEW FILE
- [ ] `tests/test_dataplane_validator.py` - Size limit tests
- [ ] `tests/test_network_policy.py` - NEW FILE (optional)

### **Documentation:**
- [ ] `docs/security/NETWORK_POLICY_RESTRICTIONS.md` - NEW FILE
- [ ] `docs/security/SECRET_ROTATION.md` - NEW FILE
- [ ] Code comments explain all security fixes

### **Verification:**
- [ ] Run all tests: `pytest tests/ -v`
- [ ] Test CSP: Verify nonce in headers and HTML
- [ ] Test rate limiting: Verify 429 responses
- [ ] Test health endpoint: Verify no auth required
- [ ] Test secret manager: Verify expiration checking
- [ ] Test log sanitization: Verify no secrets in logs
- [ ] Test size limits: Verify oversized inputs rejected
- [ ] Test Kubernetes: Verify deployment works without NET_BIND_SERVICE

---

## 🚨 IMPORTANT NOTES

1. **Test Each Fix Independently:** Don't batch changes - test each fix separately
2. **Backward Compatibility:** Ensure fixes don't break existing functionality
3. **Documentation:** Update docs as you make changes
4. **Error Messages:** Make error messages helpful but not verbose
5. **Security First:** When in doubt, choose the more secure option

---

## 📞 IF YOU GET STUCK

**Common Issues:**

1. **CSP nonce not working:** Check template receives nonce, verify script tag has nonce attribute
2. **Rate limiting too strict:** Adjust limits based on testing, document rationale
3. **NetworkPolicy blocks legitimate traffic:** Use DNS-based policies or ExternalName services
4. **Secret manager file permissions:** Ensure metadata file is readable/writable by app user
5. **Log sanitization false positives:** Refine patterns, test with real log data

**Resources:**
- Flask CSP: https://flask.palletsprojects.com/en/2.3.x/security/
- Kubernetes NetworkPolicy: https://kubernetes.io/docs/concepts/services-networking/network-policies/
- Python secrets: https://docs.python.org/3/library/secrets.html

---

## ✅ SUCCESS CRITERIA

Your work is complete when:

1. ✅ All 8 high-priority issues are fixed
2. ✅ All tests pass (new and existing)
3. ✅ No security vulnerabilities remain in your assigned areas
4. ✅ Code follows best practices
5. ✅ Documentation is updated
6. ✅ No regressions in application functionality

---

**START WORKING NOW. Good luck! 🚀**

