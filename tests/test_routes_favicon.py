"""FU4 — /favicon.ico route returns 204 No Content (auth-exempt).

The favicon endpoint exists purely to silence the "GET /favicon.ico -> 404"
console error every browser logs on first hit. It returns 204 with a
24-hour Cache-Control header and is registered without @require_auth so
it succeeds pre-auth (browsers fetch favicon before the auto-cookie path
issues a cookie for HTML navigations).
"""

from flask import Flask

from components.web_ui import routes as routes_module


class _ServiceStub:
    pending_conversions: dict = {}

    def get_status(self):
        return {}

    def get_runtime_status(self):
        return {"metrics": {}, "reload_requests": {}, "pending_promotions": {}}

    def request_runtime_reload(self, parser_id):
        return False

    def pop_runtime_reload(self, parser_id):
        return None

    def request_canary_promotion(self, parser_id):
        return False

    def pop_canary_promotion(self, parser_id):
        return None


def _build_app():
    """Build a minimal Flask app with routes registered.

    We pass an auth decorator that REJECTS every call. If the favicon route
    is auth-exempt (correct), it must succeed regardless. If something
    accidentally wires @require_auth onto the favicon, this fixture catches
    it: the decorator would 401 the request.
    """

    def _rejecting_auth(fn):
        from functools import wraps

        @wraps(fn)
        def _wrapped(*args, **kwargs):
            return ("unauthorized", 401)

        return _wrapped

    app = Flask(__name__)
    app.config["TESTING"] = True
    routes_module.register_routes(
        app,
        service=_ServiceStub(),
        feedback_queue=None,
        runtime_service=None,
        event_loop=None,
        require_auth=_rejecting_auth,
        rate_limiter=None,
    )
    return app


def test_favicon_returns_204_without_auth():
    """GET /favicon.ico without any auth header returns 204 No Content."""
    app = _build_app()
    client = app.test_client()
    response = client.get("/favicon.ico")
    assert response.status_code == 204, (
        f"expected 204, got {response.status_code}; "
        f"if 401, route accidentally has @require_auth applied"
    )
    # 204 must have empty body per HTTP spec
    assert response.data == b""


def test_favicon_cache_control_header_present():
    """Cache-Control: public, max-age=86400 (24h) is set."""
    app = _build_app()
    client = app.test_client()
    response = client.get("/favicon.ico")
    cache_control = response.headers.get("Cache-Control", "")
    assert "max-age=86400" in cache_control, (
        f"expected max-age=86400 in Cache-Control, got: {cache_control!r}"
    )
    assert "public" in cache_control, (
        f"expected 'public' directive in Cache-Control, got: {cache_control!r}"
    )


def test_favicon_route_is_not_404():
    """Route must be registered — never 404 (the bug FU4 exists to fix)."""
    app = _build_app()
    client = app.test_client()
    response = client.get("/favicon.ico")
    assert response.status_code != 404, (
        "GET /favicon.ico returned 404 — route was not registered"
    )
