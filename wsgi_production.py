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

try:
    from components.web_ui.app import create_flask_app
except ImportError as e:
    logger.error(f"Failed to import Flask app: {e}")
    sys.exit(1)


def create_app() -> Optional[object]:
    """
    Create and configure the Flask application for production.

    This factory function:
    - Loads configuration from environment
    - Creates Flask app instance
    - Registers blueprints
    - Configures security headers
    - Sets up error handlers

    Returns:
        Flask application instance or None if creation fails

    Raises:
        Exception: If configuration loading or app creation fails

    Example:
        >>> app = create_app()
        >>> app.run()
    """
    logger.info("Creating Flask application for production...")

    try:
        # Create Flask app using factory from web_ui.app
        # Load minimal config for WSGI production use
        config = {
            'app_env': os.getenv('APP_ENV', 'production'),
            'web_ui': {}
        }
        app = create_flask_app(config)

        if app is None:
            logger.error("Failed to create Flask application")
            return None

        logger.info("Flask application created successfully")

        # Add production-specific configuration
        configure_production(app)

        return app

    except Exception as e:
        logger.error(f"Failed to create application: {e}", exc_info=True)
        return None


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


# Create application instance for Gunicorn
try:
    app = create_app()
    if app is None:
        logger.error("Failed to initialize application")
        sys.exit(1)
except Exception as e:
    logger.error(f"Fatal error during initialization: {e}", exc_info=True)
    sys.exit(1)


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
