"""Flask application factory and initialization."""

import logging
import os
from flask import Flask

logger = logging.getLogger(__name__)


# Plan Phase 7.2 — DEBUG defaults to False. Stack traces are only enabled when
# APP_ENV explicitly matches a debug-friendly alias. The config dict's
# ``app_env`` key wins over the environment if it is set to production; any
# other value (including unset) is interpreted as production by default.
_DEBUG_ENV_VALUES = frozenset({"development-debug", "dev-debug", "debug"})


def _resolve_debug(config: dict) -> bool:
    """Resolve DEBUG flag from config + env. Defaults to False.

    Order of precedence:
      1. FLASK_DEBUG env var (``1``/``true``/``yes`` enables)
      2. APP_ENV env var (must be one of the debug aliases)
      3. config['app_env'] (same aliases)
    """
    flask_debug = os.environ.get("FLASK_DEBUG", "").strip().lower()
    if flask_debug in ("1", "true", "yes"):
        return True

    app_env = (os.environ.get("APP_ENV") or config.get("app_env") or "").strip().lower()
    return app_env in _DEBUG_ENV_VALUES


def create_flask_app(config: dict) -> Flask:
    """
    Create and configure Flask application instance.

    Args:
        config: Configuration dictionary

    Returns:
        Configured Flask application
    """
    app = Flask(__name__)

    # Plan Phase 7.2: DEBUG defaults to False. Opt in via APP_ENV=development-debug
    # or FLASK_DEBUG=1.
    app.config['DEBUG'] = _resolve_debug(config)
    app.debug = app.config['DEBUG']

    logger.info("[OK] Flask application created (debug=%s)", app.debug)
    return app
