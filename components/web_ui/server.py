"""Main WebFeedbackServer class - orchestrates all web UI components."""

import asyncio
import logging
import ssl
import os
from typing import Dict, Optional
from pathlib import Path as FilePath
from threading import Thread

from .app import create_flask_app
from .security import setup_flask_security
from .routes import register_routes
from .api_docs_integration import register_api_documentation

logger = logging.getLogger(__name__)


class WebFeedbackServer:
    """
    Web server for user feedback interface.
    Runs on http://localhost:8080 (or configured host)
    SECURITY: Includes security headers, CSRF protection, and rate limiting.
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

        # Authentication has been removed for harness-first local workflows.
        # Keep route decorator interface, but use a no-op implementation.
        self.auth_token = None
        self.token_header = None

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

        logger.info("Web UI authentication disabled - routes are open without token headers")

        def _no_auth(func):
            return func
        self.require_auth = _no_auth

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

        # Register API documentation (non-fatal if it fails)
        try:
            register_api_documentation(self.app, config, self.require_auth)
        except Exception as e:
            logger.warning(f"API documentation registration skipped: {e}")

        logger.info("[OK] WebFeedbackServer initialized successfully")

    def _validate_security_config(self):
        """Validate security configuration requirements."""
        # SECURITY: Enforce TLS in production
        if self.app_env == "production" and not self.tls_enabled:
            logger.error("[ERROR] SECURITY: TLS is REQUIRED in production mode!")
            logger.error("[ERROR] Set web_ui.tls.enabled=true and provide certificates")
            logger.error("[ERROR] Update config.yaml with cert_file and key_file paths")
            raise ValueError(
                "TLS must be enabled in production environment.\n"
                "Set web_ui.tls.enabled=true in config.yaml and provide cert/key files"
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
            cert_path = FilePath(self.cert_file)
            key_path = FilePath(self.key_file)

            if not cert_path.exists():
                raise FileNotFoundError(
                    f"TLS certificate not found: {self.cert_file}\n"
                    f"Generate development certificates with: bash scripts/generate-dev-certs.sh\n"
                    f"Or provide production certificates from a trusted CA"
                )
            if not key_path.exists():
                raise FileNotFoundError(
                    f"TLS private key not found: {self.key_file}\n"
                    f"Generate development certificates with: bash scripts/generate-dev-certs.sh\n"
                    f"Or provide production certificates from a trusted CA"
                )

            # Create SSL context
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(str(cert_path), str(key_path))

            # SECURITY: Set minimum TLS version (TLS 1.2+)
            ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

            # SECURITY: Use secure cipher suites
            ssl_context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')

            logger.info("[OK] TLS/SSL context configured (TLS 1.2+)")

        # Start Flask in background thread
        def run_flask():
            try:
                self.app.run(
                    host=self.bind_host,
                    port=self.bind_port,
                    ssl_context=ssl_context,
                    debug=False,
                    use_reloader=False,
                    threaded=True
                )
            except Exception as e:
                logger.error(f"[ERROR] Flask server failed: {e}")

        flask_thread = Thread(target=run_flask, daemon=True)
        flask_thread.start()

        protocol = "https" if self.tls_enabled else "http"
        logger.info(f"[OK] Web UI started: {protocol}://{self.bind_host}:{self.bind_port}")
        logger.info("[OK] Security headers enabled")
        logger.info("[OK] XSS protection enabled (CSP + autoescaping)")

        # Keep task running
        while True:
            await asyncio.sleep(10)
