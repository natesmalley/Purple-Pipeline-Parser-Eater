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


# Plan Phase 7.3 / Stream H (2026-04-28) — persisted FLASK_SECRET_KEY resolution.
#
# Self-bootstrapping in BOTH dev and production:
#   - env var set            -> use it
#   - data/state/flask_secret.key exists -> use it (production persistence)
#   - .env.local has it (dev) -> use it
#   - otherwise              -> generate, persist, and use
#
# Stream H removed the previous "production hard-fail" path. Operators should
# never need to hand-generate a Flask session key — it's an internal binding
# secret, not a credential. It IS persisted across restarts so existing
# session cookies stay valid through container redeploys (cookies become
# invalid only if the persistent file is deleted, which is the right
# escape hatch).
def resolve_flask_secret_key() -> str:
    """Return a persistent FLASK_SECRET_KEY.

    Stream H (2026-04-28): always self-bootstraps. Resolution order:

    1. ``FLASK_SECRET_KEY`` env var (operator override).
    2. ``data/state/flask_secret.key`` file (production persistence on the
       ``app-data`` volume so the key survives container restarts).
    3. ``.env.local`` in CWD (dev convenience — kept for parity with the
       pre-Stream-H dev behavior).
    4. Generate ``secrets.token_hex(32)`` + persist to (2) in production
       or (3) in dev.

    The generated file is mode 0600 so other UIDs on the host can't read it.
    """
    from pathlib import Path

    existing = os.environ.get("FLASK_SECRET_KEY")
    if existing:
        return existing

    app_env = (os.environ.get("APP_ENV") or "").strip().lower()
    is_prod = app_env == "production"

    # Production persistence path: data/state/flask_secret.key on the
    # app-data volume. The directory is created with mode 0700 if absent.
    state_dir = Path(os.environ.get("STATE_DIR", "data/state"))
    secret_file = state_dir / "flask_secret.key"

    if secret_file.exists():
        try:
            value = secret_file.read_text(encoding="utf-8").strip()
            if value:
                os.environ["FLASK_SECRET_KEY"] = value
                return value
        except OSError as exc:
            logger.warning("Failed to read %s: %s", secret_file, exc)

    # Dev secondary path: .env.local. Only consulted in non-production.
    env_local = Path.cwd() / ".env.local"
    if not is_prod and env_local.exists():
        try:
            for line in env_local.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, _, v = line.partition("=")
                    if k.strip() == "FLASK_SECRET_KEY":
                        value = v.strip().strip('"').strip("'")
                        if value:
                            os.environ["FLASK_SECRET_KEY"] = value
                            return value
        except OSError as exc:
            logger.warning("Failed to read %s: %s", env_local, exc)

    # Generate + persist.
    generated = secrets.token_hex(32)
    if is_prod:
        try:
            state_dir.mkdir(parents=True, exist_ok=True)
            secret_file.write_text(generated, encoding="utf-8")
            try:
                os.chmod(secret_file, 0o600)
            except OSError:  # pragma: no cover — Windows doesn't enforce
                pass
            logger.info(
                "Stream H: generated + persisted production FLASK_SECRET_KEY "
                "to %s (mode 0600). Sessions will survive restarts; delete "
                "the file to force-rotate.", secret_file,
            )
        except OSError as exc:
            logger.warning(
                "Could not persist FLASK_SECRET_KEY to %s: %s — using "
                "in-memory key (sessions will invalidate on restart)",
                secret_file, exc,
            )
    else:
        try:
            with env_local.open("a", encoding="utf-8") as fh:
                if env_local.stat().st_size > 0:
                    fh.write("\n")
                fh.write(f"FLASK_SECRET_KEY={generated}\n")
            logger.info("Generated + persisted dev FLASK_SECRET_KEY to %s", env_local)
        except OSError as exc:
            logger.warning("Could not persist FLASK_SECRET_KEY to %s: %s", env_local, exc)

    os.environ["FLASK_SECRET_KEY"] = generated
    return generated

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
    # Plan Phase 7.3: hard-fail in prod if missing; persist generated key in dev.
    app.config['SECRET_KEY'] = resolve_flask_secret_key()
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
        parsed = urlparse(redis_url)
        redis_host = parsed.hostname
        redis_port = parsed.port or 6379
        if redis_host:
            # Stream H follow-up (2026-04-28): Docker DNS will resolve a
            # service hostname even when the container is stopped, so a
            # bare getaddrinfo() check returns success and request-time
            # TCP connects then hang for 60s, tripping gunicorn's worker
            # timeout. Actually attempt a TCP connect with a short
            # timeout before claiming Redis is reachable. Falls through
            # to in-memory storage if the probe fails.
            storage_uri = "memory://"
            connect_timeout = float(
                os.environ.get("REDIS_CONNECT_TIMEOUT_SECS", "1.5")
            )
            try:
                with socket.create_connection(
                    (redis_host, redis_port), timeout=connect_timeout,
                ):
                    storage_uri = redis_url
                    logger.info(
                        "[OK] Rate limiting enabled with Redis: %s", redis_url,
                    )
            except (socket.gaierror, socket.timeout, OSError) as exc:
                logger.warning(
                    "[WARN] Redis at %s:%s not reachable (%s); "
                    "falling back to in-memory rate limiting.",
                    redis_host, redis_port, exc,
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
