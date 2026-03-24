"""Authentication decorator for web UI routes."""

import logging
from functools import wraps
from flask import request, jsonify, g
from utils.security_utils import constant_time_compare

logger = logging.getLogger(__name__)


def create_auth_decorator(auth_token: str, token_header: str = 'X-Auth-Token'):
    """
    Create an authentication decorator for Flask routes.

    Args:
        auth_token: The expected authentication token
        token_header: The HTTP header name for the token

    Returns:
        Authentication decorator function
    """
    def require_auth(func):
        """
        SECURITY: Authentication decorator for routes (MANDATORY)

        All routes require valid authentication token in header
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            # SECURITY: Always require authentication (mandatory for production)
            provided_token = request.headers.get(token_header)

            if not provided_token:
                request_id = getattr(g, 'request_id', 'unknown')
                logger.warning(
                    f"Unauthorized access attempt [Request {request_id}] from {request.remote_addr}: No token provided"
                )
                return jsonify({
                    'error': 'unauthorized',
                    'message': f'Authentication required. Provide token in {token_header} header',
                    'request_id': request_id
                }), 401

            # SECURITY FIX CVE-2025-RED-003: Use constant-time comparison to prevent timing attacks
            if not constant_time_compare(provided_token, auth_token):
                request_id = getattr(g, 'request_id', 'unknown')
                logger.warning(
                    f"Unauthorized access attempt [Request {request_id}] from {request.remote_addr}: Invalid token"
                )
                return jsonify({
                    'error': 'unauthorized',
                    'message': 'Invalid authentication token',
                    'request_id': request_id
                }), 401

            # Token is valid, proceed with request
            return func(*args, **kwargs)
        return wrapper
    return require_auth
