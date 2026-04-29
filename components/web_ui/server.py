"""Main WebFeedbackServer class - orchestrates all web UI components."""

import asyncio
import logging
import secrets
import ssl
import os
from typing import Dict, Optional
from pathlib import Path as FilePath
from threading import Thread

from .app import create_flask_app
from .security import setup_flask_security
from .routes import register_routes
from .api_docs_integration import register_api_documentation
from .auth import create_auth_decorator
# Stream A1 — single-source-of-truth wiring helper. Imported lazily inside
# __init__ to avoid a circular import (factory imports this module too).

logger = logging.getLogger(__name__)


def _resolve_web_ui_auth_token() -> str:
    """Return the WEB_UI_AUTH_TOKEN, auto-generating + persisting if missing.

    Stream H (2026-04-28): the token is an internal binding credential, not
    an operator credential — operators should not have to hand-generate one.
    Resolution order:

    1. ``WEB_UI_AUTH_TOKEN`` env var (operator override, e.g. for
       reverse-proxy injection or secrets-manager integration).
    2. ``data/state/web_ui_auth.token`` file (persistent across container
       restarts via the ``app-data`` volume).
    3. Generate ``secrets.token_hex(32)``, persist to (2) with mode 0600,
       log a prominent ``[BOOTSTRAP]`` banner so the operator can grab it
       for API calls.

    The prior behavior (RuntimeError on non-loopback bind without env var)
    was a dead-end UX — the container always binds 0.0.0.0 and operators
    had no in-product way to discover the required token before launching.
    """
    from pathlib import Path

    existing = os.environ.get("WEB_UI_AUTH_TOKEN", "").strip()
    if existing:
        return existing

    state_dir = Path(os.environ.get("STATE_DIR", "data/state"))
    token_file = state_dir / "web_ui_auth.token"

    if token_file.exists():
        try:
            value = token_file.read_text(encoding="utf-8").strip()
            if value:
                os.environ["WEB_UI_AUTH_TOKEN"] = value
                logger.info(
                    "Stream H: loaded persisted WEB_UI_AUTH_TOKEN from %s",
                    token_file,
                )
                return value
        except OSError as exc:
            logger.warning("Failed to read %s: %s", token_file, exc)

    generated = secrets.token_hex(32)
    persisted_to: Optional[str] = None
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        token_file.write_text(generated, encoding="utf-8")
        try:
            os.chmod(token_file, 0o600)
        except OSError:  # pragma: no cover — Windows doesn't enforce
            pass
        persisted_to = str(token_file)
    except OSError as exc:
        logger.warning(
            "Could not persist WEB_UI_AUTH_TOKEN to %s: %s — "
            "token will rotate on every restart",
            token_file, exc,
        )

    os.environ["WEB_UI_AUTH_TOKEN"] = generated
    # Prominent banner — operator needs this to make authenticated API
    # calls. Logged at WARNING so it's hard to miss in production logs.
    banner_lines = [
        "",
        "=" * 72,
        "[BOOTSTRAP] Generated WEB_UI_AUTH_TOKEN for this deployment:",
        f"  {generated}",
        "",
        "  Use it in API calls as:  X-Auth-Token: <token>",
    ]
    if persisted_to:
        banner_lines.append(
            f"  Persisted to: {persisted_to} (delete to force-rotate)"
        )
    else:
        banner_lines.append(
            "  NOT PERSISTED — token will regenerate on next restart"
        )
    banner_lines.append("=" * 72)
    for line in banner_lines:
        logger.warning(line)
    return generated


def _resolve_auth_decorator(bind_host: str):
    """Construct the auth decorator. Always returns a real decorator now.

    Stream H (2026-04-28): on any bind host, ``WEB_UI_AUTH_TOKEN`` is
    auto-generated if not provided (see ``_resolve_web_ui_auth_token``).
    The previous "no-op decorator on loopback without token" dev path is
    removed — the cost of always-on auth in dev is one extra header on
    each request, the benefit is no production drift between dev and prod
    auth shapes. Loopback binds still work fine; the operator just needs
    to pass the (auto-generated) token.

    Phase 1.D / 1.E original rules preserved:
    - Caller MUST pass the EFFECTIVE bind host (after resolving env var
      AND config.yaml), not just os.environ["WEB_UI_HOST"]. An operator
      who sets ``web_ui.host: 0.0.0.0`` in config.yaml without the env
      var would otherwise silently get the noop decorator while Flask
      binds public — this was Finding #6 from the Phase 1 DA pass and is
      now moot because the no-op path is gone.
    """
    token = _resolve_web_ui_auth_token()
    return create_auth_decorator(token, token_header="X-Auth-Token")


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

        # Extract web UI configuration
        web_ui_config = config.get("web_ui", {})

        # Phase 1.D: auth is wired from WEB_UI_AUTH_TOKEN via the existing
        # create_auth_decorator plumbing. Loopback binds may run without a
        # token (dev mode); non-loopback binds hard-fail if the token is
        # missing. See _resolve_auth_decorator above.
        self.auth_token = os.environ.get("WEB_UI_AUTH_TOKEN", "").strip() or None
        self.token_header = "X-Auth-Token" if self.auth_token else None

        # Server configuration
        self.bind_host = os.getenv('WEB_UI_HOST', web_ui_config.get("host", "127.0.0.1"))
        self.bind_port = web_ui_config.get("port", 8080)

        # TLS configuration
        tls_config = web_ui_config.get("tls", {})
        self.tls_enabled = tls_config.get("enabled", False)
        self.cert_file = tls_config.get("cert_file")
        self.key_file = tls_config.get("key_file")
        self.app_env = config.get("app_env", "development")

        # Validate security configuration BEFORE the factory does any wiring,
        # so an unsafe production deployment fails fast with a clear error.
        self._validate_security_config()

        # Stream A1 — single wiring site shared with the gunicorn factory
        # path. The daemon passes its real ContinuousConversionService plus
        # the in-process queue and event loop; build_production_app
        # registers exactly the same routes that the gunicorn ServiceContext
        # path uses.
        from .factory import build_production_app
        self.app = build_production_app(
            self.service,
            config,
            feedback_queue=self.feedback_queue,
            runtime_service=self.runtime_service,
            event_loop=self.event_loop,
            feedback_channel=None,
        )

        # Re-derive rate limiter + auth decorator state (the factory has
        # already applied them to ``self.app`` — these attributes exist for
        # backwards compat with anything that pokes at the server object).
        self.rate_limiter = self.app.extensions.get("limiter") if hasattr(self.app, "extensions") else None
        self.require_auth = _resolve_auth_decorator(self.bind_host)

        if self.auth_token:
            logger.info(
                "Web UI authentication ENABLED via WEB_UI_AUTH_TOKEN "
                "(header: X-Auth-Token)"
            )
        else:
            logger.warning(
                "Web UI authentication DISABLED - loopback dev mode "
                "(WEB_UI_HOST=%s, no token). Set WEB_UI_AUTH_TOKEN to enable auth.",
                self.bind_host,
            )

        logger.info("[OK] WebFeedbackServer initialized successfully")

    def _validate_security_config(self):
        """Validate security configuration requirements.

        Stream A3 — accept ``WEB_UI_TLS_TERMINATED_UPSTREAM=1`` as an
        explicit opt-in for deployments where TLS is terminated by an
        upstream proxy (nginx, envoy, traefik, ingress controller). The
        non-loopback auth gate at ``_resolve_auth_decorator`` still
        enforces ``WEB_UI_AUTH_TOKEN`` for any public bind, so the
        upstream-TLS path cannot accidentally disable auth.
        """
        upstream_tls = os.environ.get(
            "WEB_UI_TLS_TERMINATED_UPSTREAM", ""
        ).strip().lower() in ("1", "true", "yes")

        if self.app_env == "production" and not self.tls_enabled and not upstream_tls:
            logger.error("[ERROR] SECURITY: TLS is REQUIRED in production mode!")
            logger.error("[ERROR] Set web_ui.tls.enabled=true and provide certificates")
            logger.error("[ERROR] OR set WEB_UI_TLS_TERMINATED_UPSTREAM=1 if a")
            logger.error("[ERROR] reverse proxy terminates TLS in front of this app")
            raise ValueError(
                "TLS must be enabled in production environment. "
                "Either set web_ui.tls.enabled=true with cert/key files for "
                "in-process TLS, OR set WEB_UI_TLS_TERMINATED_UPSTREAM=1 if "
                "TLS is terminated by an upstream proxy."
            )
        if upstream_tls:
            logger.info(
                "[OK] Production mode with upstream TLS termination "
                "(WEB_UI_TLS_TERMINATED_UPSTREAM=1)"
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
