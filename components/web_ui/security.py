"""Security configuration for web UI - headers, CORS, CSP, rate limiting."""

import logging
import os
import secrets
import socket
from urllib.parse import urlparse
from typing import Optional
from flask import Flask, request, g
from flask_wtf.csrf import CSRFProtect
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
    @app.before_request
    def generate_nonce():
        """Generate CSP nonce for each request"""
        g.csp_nonce = secrets.token_urlsafe(16)

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

        # SECURITY FIX: Phase 5 - API Versioning Header
        response.headers['X-API-Version'] = '1.0.0'

        # SECURITY: Content Security Policy (CSP)
        # Uses nonces for inline scripts to prevent XSS
        nonce = getattr(g, 'csp_nonce', secrets.token_urlsafe(16))
        csp_policy = (
            f"default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            f"style-src 'self' 'unsafe-inline'; "
            f"img-src 'self' data:; "
            f"font-src 'self'; "
            f"connect-src 'self'; "
            f"frame-ancestors 'none'; "
            f"base-uri 'self'; "
            f"form-action 'self';"
        )
        response.headers['Content-Security-Policy'] = csp_policy

        # SECURITY: Permissions Policy (formerly Feature Policy)
        response.headers['Permissions-Policy'] = (
            "geolocation=(), microphone=(), camera=(), "
            "payment=(), usb=(), magnetometer=(), gyroscope=()"
        )

        # SECURITY: HSTS for HTTPS enforcement (only in production)
        if os.environ.get('APP_ENV') == 'production':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'

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

    # Default rate limits (conservative for security)
    app_env = os.environ.get('APP_ENV', 'development')
    if app_env == 'production':
        redis_url = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
        redis_host = urlparse(redis_url).hostname
        if redis_host:
            try:
                socket.getaddrinfo(redis_host, None)
                storage_uri = redis_url
                logger.info(f"[OK] Rate limiting enabled with Redis: {redis_url}")
            except socket.gaierror:
                storage_uri = "memory://"
                logger.warning(
                    f"[WARN] Redis host '{redis_host}' not resolvable; "
                    "falling back to in-memory rate limiting."
                )
        else:
            storage_uri = "memory://"
            logger.warning(
                "[WARN] Invalid REDIS_URL configured; falling back to in-memory rate limiting."
            )
    else:
        storage_uri = "memory://"  # In-memory storage for development
        logger.info("[OK] Rate limiting enabled: 100/hour, 20/minute (in-memory, dev only)")
        logger.warning("[WARN] In-memory rate limiting doesn't work across instances. Use Redis in production.")

    limiter_config = dict(
        app=app,
        key_func=get_remote_address,
        default_limits=["100 per hour", "20 per minute"],
        storage_uri=storage_uri,
        strategy="fixed-window",
        headers_enabled=True
    )
    try:
        limiter = Limiter(**limiter_config)
    except Exception as e:
        # Harden startup in environments where Redis client/server is not available.
        # Keep strict Redis behavior as the first attempt, but fall back to memory
        # so local/dev compose stacks remain bootable.
        if storage_uri.startswith("redis://"):
            logger.error(f"[ERROR] Redis rate limiter backend failed: {e}")
            logger.warning("[WARN] Falling back to in-memory rate limiting for availability")
            limiter_config["storage_uri"] = "memory://"
            limiter = Limiter(**limiter_config)
        else:
            raise

    return limiter
