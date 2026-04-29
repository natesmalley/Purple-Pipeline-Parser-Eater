"""Authentication decorator for web UI routes."""

import logging
from functools import wraps
from flask import request, jsonify, g, make_response
from utils.security_utils import constant_time_compare

logger = logging.getLogger(__name__)

AUTH_COOKIE_NAME = "pppe_auth_token"


def _request_looks_like_browser() -> bool:
    """Best-effort guess: does this request come from a browser navigating
    to an HTML page (vs a script / API client)?

    Stream I (2026-04-28): browser GUI must work without operator-side
    auth ceremony. We use the ``Accept`` header to distinguish: browsers
    send ``Accept: text/html,...`` on navigation; curl / fetch / scripts
    send ``*/*`` or ``application/json``. The check is intentionally
    permissive on the browser side and conservative on the API side.
    """
    accept = (request.headers.get("Accept") or "").lower()
    return "text/html" in accept


def create_auth_decorator(auth_token: str, token_header: str = 'X-Auth-Token'):
    """
    Create an authentication decorator for Flask routes.

    Stream I (2026-04-28) auth resolution:
      1. ``token_header`` HTTP header (canonical for API clients) →
         validate, pass on match, 401 on mismatch.
      2. ``pppe_auth_token`` cookie (browser session) → same.
      3. Neither, AND request looks HTML → server auto-issues the cookie
         from its own ``WEB_UI_AUTH_TOKEN`` env value and serves the
         page. This is the "self-hosted single-operator" mode: anyone
         who can reach the port with a browser gets the GUI, but API
         consumers (curl / scripts / XHR with non-HTML Accept) still
         need explicit auth.
      4. Neither, AND request is non-HTML → 401 JSON.

    Operator note: for exposed-to-internet deployments, place this
    container behind a reverse proxy with its own auth. The browser
    auto-issue path is intentional UX, not a security boundary.

    Args:
        auth_token: The expected authentication token.
        token_header: The HTTP header name for the token.

    Returns:
        Authentication decorator function.
    """
    def require_auth(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from_header = request.headers.get(token_header)
            from_cookie = request.cookies.get(AUTH_COOKIE_NAME)
            provided_token = from_header or from_cookie

            # Header path is API-strict: a present-but-wrong header
            # always 401s, no auto-rewrite.
            if from_header:
                if constant_time_compare(from_header, auth_token):
                    return func(*args, **kwargs)
                request_id = getattr(g, 'request_id', 'unknown')
                logger.warning(
                    "Unauthorized access attempt [Request %s] from %s: "
                    "Invalid header token",
                    request_id, request.remote_addr,
                )
                return jsonify({
                    'error': 'unauthorized',
                    'message': 'Invalid authentication token',
                    'request_id': request_id
                }), 401

            # Cookie path: valid → pass; invalid OR missing AND HTML
            # request → auto-issue a fresh cookie from the server's
            # known token. Covers stale-cookie recovery (token rotated)
            # AND the "first browser visit" case in one path.
            cookie_valid = bool(from_cookie) and constant_time_compare(
                from_cookie, auth_token,
            )
            if cookie_valid:
                return func(*args, **kwargs)

            if _request_looks_like_browser():
                # Stream I (2026-04-28): self-hosted single-operator
                # mode. Anyone reaching the port with a browser gets the
                # GUI; cookie is HttpOnly so XSS can't steal it; API
                # consumers (non-HTML Accept) still need explicit auth.
                response = make_response(func(*args, **kwargs))
                response.set_cookie(
                    AUTH_COOKIE_NAME,
                    auth_token,
                    httponly=True,
                    samesite="Lax",
                    secure=request.is_secure,
                    max_age=60 * 60 * 24 * 7,  # 1 week
                )
                return response

            request_id = getattr(g, 'request_id', 'unknown')
            if from_cookie:
                logger.warning(
                    "Unauthorized access attempt [Request %s] from %s: "
                    "Stale cookie token (non-HTML request, no recovery)",
                    request_id, request.remote_addr,
                )
                msg = 'Stale or invalid authentication cookie'
            else:
                logger.warning(
                    "Unauthorized access attempt [Request %s] from %s: "
                    "No token provided",
                    request_id, request.remote_addr,
                )
                msg = (
                    f'Authentication required. Provide token via '
                    f'{token_header} header or {AUTH_COOKIE_NAME} cookie.'
                )
            return jsonify({
                'error': 'unauthorized',
                'message': msg,
                'request_id': request_id,
            }), 401
        return wrapper
    return require_auth
