"""
Production WSGI Entry Point for Purple Pipeline Parser Eater

This module provides the WSGI application for production deployment with Gunicorn.
It handles:
- Application factory pattern
- Configuration loading
- Error handling
- Security headers
- Logging

Usage:
    gunicorn -c gunicorn_config.py wsgi_production:app

Type hints:
    None - imported from components

Examples:
    # Basic startup
    gunicorn wsgi_production:app

    # With SSL/TLS
    gunicorn --certfile=certs/server.crt \\
             --keyfile=certs/server.key \\
             wsgi_production:app

    # With workers
    gunicorn -w 4 -b 0.0.0.0:8080 wsgi_production:app
"""

import os
import sys
import logging
from typing import Optional

# Add project root to path for imports
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Stream A5 — let import errors propagate. A real ImportError should produce
# a full traceback in gunicorn's worker exit log, not a silent ``sys.exit(1)``.
from pathlib import Path

import yaml

from components.feedback_channel import FeedbackChannel
from components.runtime_proxy import RuntimeProxy
from components.state_store import StateStore
from components.web_ui.factory import build_production_app
from components.web_ui.service_context import ServiceContext


def _load_production_config() -> dict:
    """Load config.yaml if present; otherwise return ``{}`` so the app can
    still boot with environment-variable defaults."""
    config_path = Path(os.getenv("PPPE_CONFIG_FILE", "config.yaml"))
    if not config_path.exists():
        logger.warning("config.yaml not found at %s; using empty config", config_path)
        return {}
    try:
        return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("Failed to load %s: %s", config_path, exc)
        return {}


def create_app() -> object:
    """Build the production Flask app via the Stream A1 factory.

    Constructs the four-argument ``ServiceContext`` (state, config,
    feedback_channel, runtime_proxy) the routes contract requires.
    All four args are required — ``feedback_channel`` and ``runtime_proxy``
    are NOT optional because the routes from A2.d / routes.py:3593 assume
    they exist.
    """
    logger.info("Creating production Flask application via build_production_app...")

    config = _load_production_config()
    config.setdefault("app_env", os.getenv("APP_ENV", "production"))

    # StateStore — single shared JSON snapshot on the app-data volume.
    # follower=True is LOAD-BEARING for Stream A — it turns on the mtime-
    # based hot-reload from A2.f so the web process sees worker writes.
    state_path = Path(os.environ.get(
        "STATE_STORE_PATH", "data/state/pending_state.json",
    ))
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = StateStore(persist_path=state_path, follower=True)

    # FeedbackChannel — file-backed cross-process bus (A2.a).
    feedback_path = Path(os.environ.get(
        "FEEDBACK_CHANNEL_PATH", "data/feedback/actions.jsonl",
    ))
    feedback_path.parent.mkdir(parents=True, exist_ok=True)
    feedback_channel = FeedbackChannel(path=feedback_path)

    # RuntimeProxy — web-side shim over the worker's persisted runtime
    # snapshot (A2.b). Tracks POSTed reload/promotion requests in its own
    # pending_requests.json file.
    runtime_snapshot_path = Path(os.environ.get(
        "RUNTIME_SNAPSHOT_PATH", "data/runtime/status_snapshot.json",
    ))
    runtime_pending_path = Path(os.environ.get(
        "RUNTIME_PENDING_REQUESTS_PATH", "data/runtime/pending_requests.json",
    ))
    runtime_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_pending_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_proxy = RuntimeProxy(
        feedback_channel=feedback_channel,
        snapshot_path=runtime_snapshot_path,
        pending_requests_path=runtime_pending_path,
    )

    ctx = ServiceContext(
        state=state,
        config=config,
        feedback_channel=feedback_channel,
        runtime_proxy=runtime_proxy,
    )

    app = build_production_app(ctx, config)
    configure_production(app)
    logger.info("Production Flask app created with %d routes",
                len(list(app.url_map.iter_rules())))
    return app


def configure_production(app: object) -> None:
    """
    Configure Flask app for production environment.

    Adds:
    - Security headers
    - Error handlers
    - Logging configuration
    - Performance optimizations

    Args:
        app: Flask application instance

    Returns:
        None

    Example:
        >>> app = Flask(__name__)
        >>> configure_production(app)
    """
    logger.info("Configuring production settings...")

    # Disable debug mode
    app.debug = False
    app.testing = False

    # Add security headers via after_request handler
    @app.after_request
    def add_security_headers(response):
        """Add security headers to all responses."""
        # Prevent MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'

        # Enable XSS protection
        response.headers['X-XSS-Protection'] = '1; mode=block'

        # Prevent clickjacking
        response.headers['X-Frame-Options'] = 'DENY'

        # Referrer policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Feature policy
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'

        # HTTP Strict Transport Security (HSTS)
        response.headers['Strict-Transport-Security'] = (
            'max-age=31536000; includeSubDomains; preload'
        )

        # Content Security Policy (CSP)
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

        return response

    # Configure error handlers
    @app.errorhandler(400)
    def bad_request(error):
        """Handle 400 Bad Request errors."""
        logger.warning(f"Bad request: {error}")
        return {
            'error': 'Bad Request',
            'message': str(error),
            'status_code': 400
        }, 400

    @app.errorhandler(401)
    def unauthorized(error):
        """Handle 401 Unauthorized errors."""
        logger.warning(f"Unauthorized access attempt: {error}")
        return {
            'error': 'Unauthorized',
            'message': 'Authentication required',
            'status_code': 401
        }, 401

    @app.errorhandler(403)
    def forbidden(error):
        """Handle 403 Forbidden errors."""
        logger.warning(f"Forbidden access attempt: {error}")
        return {
            'error': 'Forbidden',
            'message': 'Access denied',
            'status_code': 403
        }, 403

    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 Not Found errors."""
        logger.debug(f"Resource not found: {error}")
        return {
            'error': 'Not Found',
            'message': 'Resource not found',
            'status_code': 404
        }, 404

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 Internal Server errors."""
        logger.error(f"Internal server error: {error}", exc_info=True)
        return {
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred',
            'status_code': 500
        }, 500

    logger.info("Production configuration complete")


# Stream A5 — let init errors propagate so gunicorn's worker exit handler
# logs a full traceback. Silent ``sys.exit(1)`` hid bring-up failures.
app = create_app()


if __name__ == '__main__':
    # This is only for testing - use Gunicorn in production
    logger.warning("Running in development mode. Use Gunicorn in production!")
    logger.warning("Run: gunicorn wsgi_production:app")

    if app:
        # Load SSL context if certificates exist
        ssl_context = None
        cert_file = os.path.join(project_root, 'certs/server.crt')
        key_file = os.path.join(project_root, 'certs/server.key')

        if os.path.exists(cert_file) and os.path.exists(key_file):
            import ssl
            try:
                ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                ssl_context.load_cert_chain(cert_file, key_file)
                logger.info(f"Loaded SSL certificates from {cert_file}")
            except Exception as e:
                logger.error(f"Failed to load SSL certificates: {e}")

        # Run application
        app.run(
            host='0.0.0.0',
            port=int(os.getenv('PORT', 8080)),
            debug=False,
            ssl_context=ssl_context
        )
