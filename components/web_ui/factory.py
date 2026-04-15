"""Stream A1 — reusable production app factory.

Mirrors the wiring sequence in ``WebFeedbackServer.__init__`` so both the
gunicorn path (``wsgi_production:create_app``) and the daemon path
(``WebFeedbackServer``) share one wiring site.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from flask import Flask

from .api_docs_integration import register_api_documentation
from .app import create_flask_app
from .routes import register_routes
from .security import setup_flask_security
from .server import _resolve_auth_decorator
from .service_context import ServiceContext

logger = logging.getLogger(__name__)


def build_production_app(
    service,
    config: Optional[dict] = None,
    *,
    feedback_queue=None,
    runtime_service=None,
    event_loop=None,
    feedback_channel=None,
) -> Flask:
    """Build the production Flask app and register all routes.

    Used by both wiring sites:

    - ``wsgi_production:create_app`` passes a ``ServiceContext`` plus a
      file-backed ``feedback_channel`` and leaves queue/event_loop/runtime
      as ``None``.
    - ``WebFeedbackServer.__init__`` (daemon path) passes the real
      ``ContinuousConversionService`` plus its in-process queue and event
      loop and leaves ``feedback_channel`` as ``None``.

    When ``feedback_channel`` is omitted and the passed ``service`` is a
    ``ServiceContext`` (i.e. it carries its own channel), we pull it off
    the context automatically — that's the wsgi convenience path.
    """
    config = config or {}

    if feedback_channel is None and isinstance(service, ServiceContext):
        feedback_channel = service.feedback_channel

    app = create_flask_app(config)
    rate_limiter = setup_flask_security(app, config)

    bind_host = os.getenv(
        "WEB_UI_HOST",
        config.get("web_ui", {}).get("host", "127.0.0.1"),
    )
    require_auth = _resolve_auth_decorator(bind_host)

    register_routes(
        app,
        service,
        feedback_queue=feedback_queue,
        runtime_service=runtime_service,
        event_loop=event_loop,
        require_auth=require_auth,
        rate_limiter=rate_limiter,
        feedback_channel=feedback_channel,
    )

    try:
        register_api_documentation(app, config, require_auth)
    except Exception as exc:
        logger.warning("API documentation registration skipped: %s", exc)

    return app
