"""API documentation blueprint integration."""

import logging
from flask import Flask
from components.api_docs_blueprint import create_api_docs_blueprint

logger = logging.getLogger(__name__)


def register_api_documentation(app: Flask, config: dict, require_auth):
    """
    Register API documentation blueprint with Flask app.

    Args:
        app: Flask application instance
        config: Configuration dictionary
        require_auth: Authentication decorator function
    """
    # SECURITY FIX: Phase 5 - Register API documentation blueprint
    # Provides endpoints for OpenAPI spec, Swagger UI, and documentation
    try:
        api_docs_bp = create_api_docs_blueprint(
            auth_required=True,
            require_auth=require_auth
        )
        app.register_blueprint(api_docs_bp)
        logger.info("[OK] API documentation blueprint registered successfully")
        logger.info("[OK] Available at: /api/docs/")
    except Exception as e:
        logger.error(f"[ERROR] Failed to register API documentation blueprint: {e}")
        raise
