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
