# Agent Task 1: Refactor web_feedback_ui.py into Modular Components

**Agent Model:** Claude Haiku (fast, efficient)
**Estimated Time:** 90 minutes
**Risk Level:** MEDIUM
**Files Modified:** 1 large file → 7 modular files

---

## Mission Objective

Refactor `components/web_feedback_ui.py` (1,481 lines) into smaller, focused modules organized in `components/web_ui/` directory while maintaining 100% backward compatibility and zero functional regressions.

**Success Criteria:**
- [ ] Original file reduced to <100 lines (backward compatibility wrapper)
- [ ] 6-7 new focused modules created (~200 lines each)
- [ ] All Flask routes still accessible
- [ ] Authentication still works
- [ ] Security headers still applied
- [ ] Rate limiting still functional
- [ ] All imports resolve correctly
- [ ] Zero syntax errors
- [ ] Zero functional regressions

---

## Current File Analysis

**File:** `components/web_feedback_ui.py`
**Lines:** 1,481
**Main Class:** `WebFeedbackServer`

**Key Components:**
1. **Imports & Setup** (lines 1-54): Flask, security utilities, rate limiting
2. **Class Definition** (lines 56-62): WebFeedbackServer class
3. **__init__ Method** (lines 63-188): Initialization, config, Flask app setup
4. **require_auth Decorator** (lines 189-225): Authentication middleware
5. **setup_security_headers** (lines 227-289): Security headers, CORS, CSP
6. **register_api_docs_blueprint** (lines 290-320): API documentation
7. **setup_routes** (lines 321-721): All route handlers (~400 lines, LARGE)
8. **start Method** (lines 722-end): Async server startup

**Dependencies:**
```python
import asyncio, logging, ssl, os, secrets
from datetime import datetime
from typing import Dict, Optional
from functools import wraps
from pathlib import Path as FilePath
from flask import Flask, render_template_string, request, jsonify, g
from utils.security_utils import (constant_time_compare, sanitize_request_id, ...)
from flask_wtf.csrf import CSRFProtect, generate_csrf, CSRFError
from threading import Thread
from components.api_docs_blueprint import create_api_docs_blueprint
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
```

---

## Target Architecture

Create this directory structure:

```
components/web_ui/
├── __init__.py              # Public interface (backward compatibility)
├── app.py                   # Flask app initialization
├── auth.py                  # Authentication decorator
├── security.py              # Security headers, CORS, rate limiting
├── routes.py                # All route handlers
├── api_docs_integration.py  # API docs blueprint registration
└── server.py                # Main server class and startup
```

---

## Step-by-Step Execution Plan

### STEP 1: Create Directory and __init__.py

**Action:**
```bash
mkdir -p components/web_ui
```

**Create:** `components/web_ui/__init__.py`
```python
"""
Web UI module for Purple Pipeline Parser Eater.

Provides a web interface for user feedback and conversion management.
This module is refactored from web_feedback_ui.py for better maintainability.
"""

from .server import WebFeedbackServer

__all__ = ['WebFeedbackServer']
```

**Verification:**
```python
# Test import
from components.web_ui import WebFeedbackServer
print("✓ Import successful")
```

---

### STEP 2: Extract Authentication (auth.py)

**Create:** `components/web_ui/auth.py`

**Content to Extract:**
- Lines 189-225 from original file
- The `require_auth` decorator method

**Code:**
```python
"""Authentication decorator for web UI routes."""

import logging
from functools import wraps
from flask import request, jsonify, g
from utils.security_utils import constant_time_compare

logger = logging.getLogger(__name__)


def create_auth_decorator(auth_token: str, token_header: str = 'X-Auth-Token'):
    """
    Create an authentication decorator for Flask routes.

    Args:
        auth_token: The expected authentication token
        token_header: The HTTP header name for the token

    Returns:
        Authentication decorator function
    """
    def require_auth(func):
        """
        SECURITY: Authentication decorator for routes (MANDATORY)

        All routes require valid authentication token in header
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            # SECURITY: Always require authentication (mandatory for production)
            provided_token = request.headers.get(token_header)

            if not provided_token:
                request_id = getattr(g, 'request_id', 'unknown')
                logger.warning(
                    f"Unauthorized access attempt [Request {request_id}] from {request.remote_addr}: No token provided"
                )
                return jsonify({
                    'error': 'unauthorized',
                    'message': f'Authentication required. Provide token in {token_header} header',
                    'request_id': request_id
                }), 401

            # SECURITY FIX CVE-2025-RED-003: Use constant-time comparison to prevent timing attacks
            if not constant_time_compare(provided_token, auth_token):
                request_id = getattr(g, 'request_id', 'unknown')
                logger.warning(
                    f"Unauthorized access attempt [Request {request_id}] from {request.remote_addr}: Invalid token"
                )
                return jsonify({
                    'error': 'unauthorized',
                    'message': 'Invalid authentication token',
                    'request_id': request_id
                }), 401

            # Token is valid, proceed with request
            return func(*args, **kwargs)
        return wrapper
    return require_auth
```

---

### STEP 3: Extract Security Setup (security.py)

**Create:** `components/web_ui/security.py`

**Content to Extract:**
- Lines 227-289 from original file
- The `setup_security_headers` method

**Code:**
```python
"""Security configuration for web UI - headers, CORS, CSP, rate limiting."""

import logging
import os
from typing import Optional
from flask import Flask, request, g
from flask_wtf.csrf import CSRFProtect, CSRFError
from utils.security_utils import get_secure_request_id

logger = logging.getLogger(__name__)

# Try to import rate limiting
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    RATE_LIMITING_AVAILABLE = True
except ImportError:
    RATE_LIMITING_AVAILABLE = False
    app_env = os.getenv('APP_ENV', 'development')
    if app_env == 'production':
        raise ImportError(
            "flask-limiter is REQUIRED for production deployment. "
            "Install with: pip install Flask-Limiter"
        )
    logger.warning("flask-limiter not installed - rate limiting disabled (development mode only)")


def setup_flask_security(app: Flask, config: dict) -> Optional[object]:
    """
    Configure all security features for Flask application.

    Args:
        app: Flask application instance
        config: Configuration dictionary

    Returns:
        Rate limiter instance if available, None otherwise
    """
    # SECURITY FIX: Add request ID tracking
    @app.before_request
    def set_request_id():
        """Set unique request ID for tracking and correlation"""
        g.request_id = get_secure_request_id()
        logger.debug(f"Request {g.request_id} started: {request.method} {request.path}")

    # SECURITY FIX: Enable Jinja2 autoescaping for XSS protection
    app.jinja_env.autoescape = True

    # SECURITY FIX: CSRF Protection
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', os.urandom(32).hex())
    csrf_timeout = int(os.environ.get('CSRF_TOKEN_TIMEOUT', '3600'))  # Default 1 hour
    app.config['WTF_CSRF_TIME_LIMIT'] = csrf_timeout
    app.config['WTF_CSRF_CHECK_DEFAULT'] = True
    app.config['WTF_CSRF_SSL_STRICT'] = os.environ.get('APP_ENV', 'development') == 'production'
    csrf = CSRFProtect(app)

    # SECURITY FIX: Request Size Limits
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

    # Setup security headers
    setup_security_headers(app)

    # Setup rate limiting if available
    rate_limiter = None
    if RATE_LIMITING_AVAILABLE:
        rate_limiter = setup_rate_limiting(app, config)

    return rate_limiter


def setup_security_headers(app: Flask):
    """
    Configure security headers for all responses.

    SECURITY FIX: Phase 2 - Comprehensive security headers
    """
    @app.after_request
    def add_security_headers(response):
        """Add security headers to all responses"""
        # SECURITY: Prevent clickjacking attacks
        response.headers['X-Frame-Options'] = 'DENY'

        # SECURITY: Prevent MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'

        # SECURITY: Enable browser XSS protection
        response.headers['X-XSS-Protection'] = '1; mode=block'

        # SECURITY: Referrer policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # SECURITY: Content Security Policy (CSP)
        # Uses nonces for inline scripts to prevent XSS
        nonce = getattr(g, 'csp_nonce', 'default')
        csp_policy = (
            f"default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net; "
            f"style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            f"img-src 'self' data:; "
            f"font-src 'self' https://cdn.jsdelivr.net; "
            f"connect-src 'self'; "
            f"frame-ancestors 'none';"
        )
        response.headers['Content-Security-Policy'] = csp_policy

        # SECURITY: Permissions Policy (formerly Feature Policy)
        response.headers['Permissions-Policy'] = (
            "geolocation=(), microphone=(), camera=(), "
            "payment=(), usb=(), magnetometer=(), gyroscope=()"
        )

        # SECURITY: HSTS for HTTPS enforcement (only in production)
        if os.environ.get('APP_ENV') == 'production':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        return response

    logger.info("[OK] Security headers configured")


def setup_rate_limiting(app: Flask, config: dict) -> object:
    """
    Configure rate limiting for Flask application.

    Args:
        app: Flask application instance
        config: Configuration dictionary

    Returns:
        Rate limiter instance
    """
    web_ui_config = config.get("web_ui", {})
    rate_limit_config = web_ui_config.get("rate_limit", {})

    # Default rate limits (conservative for security)
    default_limit = rate_limit_config.get("default", "100 per minute")

    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[default_limit],
        storage_uri="memory://",  # Use Redis in production for distributed rate limiting
        strategy="fixed-window"
    )

    logger.info(f"[OK] Rate limiting enabled: {default_limit}")
    return limiter
```

---

### STEP 4: Extract Routes (routes.py)

**Create:** `components/web_ui/routes.py`

**Content to Extract:**
- Lines 321-721 from original file
- The entire `setup_routes` method content
- All route handler definitions

**Code Structure:**
```python
"""Route handlers for web UI."""

import logging
import asyncio
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, g
from utils.security_utils import (
    validate_parser_name, sanitize_log_input,
    validate_json_depth, get_secure_nonce
)

logger = logging.getLogger(__name__)


def register_routes(app: Flask, service, feedback_queue, runtime_service, event_loop, auth_decorator, rate_limiter=None):
    """
    Register all Flask routes for the web UI.

    Args:
        app: Flask application instance
        service: Continuous conversion service instance
        feedback_queue: Asyncio queue for feedback
        runtime_service: Runtime service instance
        event_loop: Event loop for async operations
        auth_decorator: Authentication decorator function
        rate_limiter: Optional rate limiter instance
    """

    # Apply rate limiting decorator if available
    def rate_limit(limit_string):
        if rate_limiter:
            return rate_limiter.limit(limit_string)
        else:
            # No-op decorator if rate limiting not available
            def decorator(f):
                return f
            return decorator

    # ========================================================================
    # ROUTE: Home Page / Status Dashboard
    # ========================================================================
    @app.route('/')
    @auth_decorator
    @rate_limit("60 per minute")
    def home():
        """Main dashboard with pending conversions"""
        # [COPY ENTIRE HOME ROUTE IMPLEMENTATION FROM ORIGINAL FILE]
        # Lines ~332-450 from original file
        pass  # Replace with actual implementation

    # ========================================================================
    # ROUTE: API Status Endpoint
    # ========================================================================
    @app.route('/api/status')
    @auth_decorator
    @rate_limit("120 per minute")
    def api_status():
        """API endpoint for service status"""
        # [COPY ENTIRE API_STATUS IMPLEMENTATION FROM ORIGINAL FILE]
        pass  # Replace with actual implementation

    # ========================================================================
    # ROUTE: Approve Conversion
    # ========================================================================
    @app.route('/api/approve/<parser_name>', methods=['POST'])
    @auth_decorator
    @rate_limit("30 per minute")
    def approve(parser_name):
        """Approve a conversion"""
        # [COPY ENTIRE APPROVE IMPLEMENTATION FROM ORIGINAL FILE]
        pass  # Replace with actual implementation

    # ... COPY ALL OTHER ROUTES FROM ORIGINAL FILE ...

    logger.info("[OK] All routes registered successfully")
```

**CRITICAL:** You must copy ALL route implementations from lines 321-721 of the original file.

---

### STEP 5: Extract API Docs Integration (api_docs_integration.py)

**Create:** `components/web_ui/api_docs_integration.py`

**Content to Extract:**
- Lines 290-320 from original file
- The `register_api_docs_blueprint` method

**Code:**
```python
"""API documentation blueprint integration."""

import logging
from flask import Flask
from components.api_docs_blueprint import create_api_docs_blueprint

logger = logging.getLogger(__name__)


def register_api_documentation(app: Flask, config: dict):
    """
    Register API documentation blueprint with Flask app.

    Args:
        app: Flask application instance
        config: Configuration dictionary
    """
    # SECURITY FIX: Phase 5 - Register API documentation blueprint
    # Provides endpoints for OpenAPI spec, Swagger UI, and documentation
    try:
        api_docs_bp = create_api_docs_blueprint(config)
        app.register_blueprint(api_docs_bp, url_prefix='/api/docs')
        logger.info("[OK] API documentation registered at /api/docs")
    except Exception as e:
        logger.warning(f"[WARN] Could not register API docs blueprint: {e}")
        logger.warning("[WARN] API documentation endpoints will not be available")
```

---

### STEP 6: Extract Flask App Initialization (app.py)

**Create:** `components/web_ui/app.py`

**Content:**
```python
"""Flask application factory and initialization."""

import logging
from flask import Flask

logger = logging.getLogger(__name__)


def create_flask_app(config: dict) -> Flask:
    """
    Create and configure Flask application instance.

    Args:
        config: Configuration dictionary

    Returns:
        Configured Flask application
    """
    app = Flask(__name__)

    # Basic Flask configuration
    web_ui_config = config.get("web_ui", {})
    app.config['DEBUG'] = config.get("app_env", "development") != "production"

    logger.info("[OK] Flask application created")
    return app
```

---

### STEP 7: Create Main Server Class (server.py)

**Create:** `components/web_ui/server.py`

**Content:**
```python
"""Main WebFeedbackServer class - orchestrates all web UI components."""

import asyncio
import logging
import ssl
import os
from typing import Dict, Optional
from pathlib import Path as FilePath
from threading import Thread
from flask import Flask

from .app import create_flask_app
from .auth import create_auth_decorator
from .security import setup_flask_security
from .routes import register_routes
from .api_docs_integration import register_api_documentation

logger = logging.getLogger(__name__)


class WebFeedbackServer:
    """
    Web server for user feedback interface.
    Runs on http://localhost:8080 (or configured host)
    SECURITY: Includes authentication via bearer token
    """

    def __init__(self, config: Dict, feedback_queue: asyncio.Queue, service, event_loop=None, runtime_service=None):
        """
        Initialize web feedback server.

        Args:
            config: Configuration dictionary
            feedback_queue: Asyncio queue for feedback
            service: Continuous conversion service
            event_loop: Event loop for async operations
            runtime_service: Runtime service instance
        """
        self.config = config
        self.feedback_queue = feedback_queue
        self.service = service
        self.runtime_service = runtime_service
        self.event_loop = event_loop

        # Create Flask app
        self.app = create_flask_app(config)

        # Extract web UI configuration
        web_ui_config = config.get("web_ui", {})

        # Authentication configuration
        self.auth_token = os.environ.get('WEB_UI_AUTH_TOKEN') or web_ui_config.get("auth_token")
        self.token_header = web_ui_config.get("auth_header", "X-Auth-Token")

        # Server configuration
        self.bind_host = os.getenv('WEB_UI_HOST', web_ui_config.get("host", "127.0.0.1"))
        self.bind_port = web_ui_config.get("port", 8080)

        # TLS configuration
        tls_config = web_ui_config.get("tls", {})
        self.tls_enabled = tls_config.get("enabled", False)
        self.cert_file = tls_config.get("cert_file")
        self.key_file = tls_config.get("key_file")
        self.app_env = config.get("app_env", "development")

        # Validate security configuration
        self._validate_security_config()

        # Setup security
        self.rate_limiter = setup_flask_security(self.app, config)

        # Create authentication decorator
        self.require_auth = create_auth_decorator(self.auth_token, self.token_header)

        # Register all routes
        register_routes(
            self.app,
            self.service,
            self.feedback_queue,
            self.runtime_service,
            self.event_loop,
            self.require_auth,
            self.rate_limiter
        )

        # Register API documentation
        register_api_documentation(self.app, config)

        logger.info("[OK] WebFeedbackServer initialized successfully")

    def _validate_security_config(self):
        """Validate security configuration requirements."""
        # SECURITY: Enforce TLS in production
        if self.app_env == "production" and not self.tls_enabled:
            logger.error("[ERROR] SECURITY: TLS is REQUIRED in production mode!")
            raise ValueError(
                "TLS must be enabled in production environment.\n"
                "Set web_ui.tls.enabled=true in config.yaml"
            )

        # SECURITY: Require authentication token
        if not self.auth_token or self.auth_token == "change-me-before-production":
            logger.error("[ERROR] SECURITY: No valid auth_token configured!")
            raise ValueError(
                "Web UI authentication token is required. "
                "Set web_ui.auth_token in config.yaml"
            )

        logger.info("[OK] Security configuration validated")

    async def start(self):
        """
        Start the web server (async method).

        This method starts Flask in a background thread and returns immediately.
        """
        logger.info("=" * 70)
        logger.info("Starting Web Feedback UI Server...")
        logger.info(f"Host: {self.bind_host}")
        logger.info(f"Port: {self.bind_port}")
        logger.info(f"TLS: {'Enabled' if self.tls_enabled else 'Disabled'}")
        logger.info(f"Environment: {self.app_env}")
        logger.info("=" * 70)

        # Setup SSL context if TLS enabled
        ssl_context = None
        if self.tls_enabled:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(self.cert_file, self.key_file)
            ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
            logger.info("[OK] TLS/SSL context configured (TLS 1.2+)")

        # Start Flask in background thread
        def run_flask():
            try:
                self.app.run(
                    host=self.bind_host,
                    port=self.bind_port,
                    ssl_context=ssl_context,
                    threaded=True,
                    use_reloader=False
                )
            except Exception as e:
                logger.error(f"[ERROR] Flask server failed: {e}")

        flask_thread = Thread(target=run_flask, daemon=True)
        flask_thread.start()

        protocol = "https" if self.tls_enabled else "http"
        logger.info(f"\n[OK] Web UI started: {protocol}://{self.bind_host}:{self.bind_port}")
        logger.info(f"[OK] Authenticate with header: {self.token_header}: <your-token>")
```

---

### STEP 8: Update Original File to Backward Compatibility Wrapper

**Modify:** `components/web_feedback_ui.py`

Replace entire content with:

```python
"""
Web Feedback UI Server - Backward Compatibility Wrapper

DEPRECATED: This file now imports from components.web_ui module.
For new code, import directly from components.web_ui:
    from components.web_ui import WebFeedbackServer

This wrapper maintains backward compatibility with existing code.
"""

from components.web_ui import WebFeedbackServer

__all__ = ['WebFeedbackServer']
```

---

## Verification Checklist

After completing all steps, verify:

### 1. File Structure Check
```bash
ls -la components/web_ui/
# Should show:
# __init__.py
# app.py
# auth.py
# security.py
# routes.py
# api_docs_integration.py
# server.py
```

### 2. Import Verification
```python
# Test all import paths
from components.web_ui import WebFeedbackServer  # New path
from components.web_feedback_ui import WebFeedbackServer  # Old path (should still work)
print("✓ All imports successful")
```

### 3. Syntax Check
```bash
python -m py_compile components/web_ui/*.py
echo "✓ No syntax errors"
```

### 4. Module Size Check
```bash
wc -l components/web_ui/*.py
# Each file should be <400 lines
# Most should be <250 lines
```

### 5. Backward Compatibility Test
```python
# Old import should still work
from components.web_feedback_ui import WebFeedbackServer
server = WebFeedbackServer(config, queue, service)
# Should create instance without errors
```

---

## Rollback Instructions

If anything goes wrong:

```bash
# Restore original file
git checkout -- components/web_feedback_ui.py

# Remove new directory
rm -rf components/web_ui/

# Verify restoration
ls -la components/web_feedback_ui.py
```

---

## Success Criteria

- [ ] All 7 new files created in `components/web_ui/`
- [ ] Original file reduced to <50 lines (wrapper only)
- [ ] No syntax errors (verified with py_compile)
- [ ] All imports resolve correctly
- [ ] Backward compatibility maintained
- [ ] Average module size <300 lines
- [ ] All route handlers preserved
- [ ] Authentication still works
- [ ] Security headers still applied

---

## Notes for Agent

**Important:**
1. Copy ALL code - don't summarize or skip routes
2. Maintain exact same functionality
3. Keep all comments and security fixes
4. Preserve all decorators
5. Test imports after each step
6. If unsure, ask for clarification

**Critical Routes to Preserve:**
- / (home/dashboard)
- /api/status
- /api/approve/<parser_name>
- /api/reject/<parser_name>
- /api/modify/<parser_name>
- /api/conversions
- /api/runtime/status
- /api/runtime/reload/<parser_name>
- All other routes from original file

**Security Features to Preserve:**
- CSRF protection
- Rate limiting
- Security headers
- TLS/HTTPS support
- Authentication decorator
- Request ID tracking

---

**EXECUTION COMMAND FOR HAIKU AGENT:**
```
Read this file completely, execute all steps sequentially, verify at each checkpoint, and report status.
```

**END OF AGENT 1 PROMPT**
