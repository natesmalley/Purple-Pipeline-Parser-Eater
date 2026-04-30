"""W5 (plan 2026-04-29): SSRF gate on POST /api/v1/settings/test/observo.

Trip-wire approach: we monkeypatch ``urllib.request.urlopen`` to fail
loudly. If the gate ever fails to short-circuit before the outbound
``urlopen`` call, the test fails with a clear message.
"""
from __future__ import annotations

import socket
from unittest import mock

import pytest
from flask import Flask

from components.web_ui import routes as routes_module
from utils import security_utils as _security_utils


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


def _make_getaddrinfo(ip: str):
    def _stub(*_args, **_kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]
    return _stub


def _build_app(monkeypatch):
    def _no_auth(fn):
        return fn

    monkeypatch.setattr(routes_module, "ParserLuaWorkbench", lambda: object())
    monkeypatch.setattr(routes_module, "HarnessOrchestrator", lambda: object())

    app = Flask(__name__)
    app.config["TESTING"] = True
    routes_module.register_routes(
        app,
        service=_ServiceStub(),
        feedback_queue=None,
        runtime_service=None,
        event_loop=None,
        require_auth=_no_auth,
        rate_limiter=None,
    )
    return app


# Trip-wire: a urlopen that screams if reached.
def _make_trip_wire_urlopen(reason: str):
    def _trip(*_args, **_kwargs):
        pytest.fail(
            f"urllib.request.urlopen must NOT be reached: {reason}"
        )
    return _trip


# ---------------------------------------------------------------------------
# Case 1: OBSERVO_BASE_URL=http://127.0.0.1 — IP-literal loopback rejection.
# ---------------------------------------------------------------------------

def test_provider_test_observo_loopback_rejected(monkeypatch):
    """Loopback URL is rejected by the SSRF gate BEFORE ``urlopen`` is
    invoked. Verified via a trip-wire urlopen that fails the test if
    reached."""
    monkeypatch.setenv("OBSERVO_BASE_URL", "http://127.0.0.1")
    monkeypatch.setenv("OBSERVO_API_KEY", "fake-key-shaped-like-real")

    # Patch the canonical urlopen import path. The route does
    # ``import urllib.request`` inline before calling
    # ``urllib.request.urlopen``, so patching the module attr is enough.
    import urllib.request as _ur
    monkeypatch.setattr(
        _ur, "urlopen", _make_trip_wire_urlopen("loopback case")
    )

    app = _build_app(monkeypatch)
    client = app.test_client()

    resp = client.post("/api/v1/settings/test/observo", json={})
    assert resp.status_code == 400, resp.get_json()
    body = resp.get_json()
    assert body["error"] == "ssrf_blocked"
    assert isinstance(body.get("reason"), str) and body["reason"]


# ---------------------------------------------------------------------------
# Case 2: off-allowlist hostname (resolves to public IP via stubbed DNS).
# ---------------------------------------------------------------------------

def test_provider_test_observo_off_allowlist_rejected(monkeypatch):
    """``https://attacker.example`` resolves to a public IP but is NOT
    under *.observo.ai → rejected before ``urlopen``."""
    monkeypatch.setenv("OBSERVO_BASE_URL", "https://attacker.example")
    monkeypatch.setenv("OBSERVO_API_KEY", "fake-key-shaped-like-real")
    monkeypatch.setattr("socket.getaddrinfo", _make_getaddrinfo("8.8.8.8"))

    import urllib.request as _ur
    monkeypatch.setattr(
        _ur, "urlopen", _make_trip_wire_urlopen("off-allowlist case")
    )

    app = _build_app(monkeypatch)
    client = app.test_client()

    resp = client.post("/api/v1/settings/test/observo", json={})
    assert resp.status_code == 400, resp.get_json()
    body = resp.get_json()
    assert body["error"] == "ssrf_blocked"
    assert isinstance(body.get("reason"), str) and body["reason"]


# ---------------------------------------------------------------------------
# Case 3: legit p01-api.observo.ai with stubbed urlopen — must succeed,
# and validate_url_for_ssrf must have been called exactly once.
# ---------------------------------------------------------------------------

def test_provider_test_observo_observo_ai_accepted(monkeypatch):
    monkeypatch.setenv(
        "OBSERVO_BASE_URL", "https://p01-api.observo.ai"
    )
    monkeypatch.setenv("OBSERVO_API_KEY", "fake-key-shaped-like-real")
    monkeypatch.setattr("socket.getaddrinfo", _make_getaddrinfo("8.8.8.8"))

    # Stub urlopen to return a tiny dummy response; track invocations.
    urlopen_calls = []

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def read(self):
            return b"{}"

    def _stub_urlopen(req, timeout=None):
        urlopen_calls.append((getattr(req, "full_url", None), timeout))
        return _Resp()

    import urllib.request as _ur
    monkeypatch.setattr(_ur, "urlopen", _stub_urlopen)

    # Wrap validate_url_for_ssrf through the routes_module symbol so we
    # observe call count without changing behavior.
    real_validate = _security_utils.validate_url_for_ssrf
    call_count = {"n": 0}

    def _counting_validate(*args, **kwargs):
        call_count["n"] += 1
        return real_validate(*args, **kwargs)

    # routes_module imported the symbol at module load, so patch THAT
    # binding (the route calls ``validate_url_for_ssrf(...)`` which is
    # the routes_module attr).
    monkeypatch.setattr(
        routes_module, "validate_url_for_ssrf", _counting_validate
    )

    app = _build_app(monkeypatch)
    client = app.test_client()

    resp = client.post("/api/v1/settings/test/observo", json={})
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body.get("ok") is True
    # validate_url_for_ssrf called exactly once on the happy path.
    assert call_count["n"] == 1, (
        f"expected 1 SSRF validation, saw {call_count['n']}"
    )
    # urlopen reached, with the expected URL shape.
    assert len(urlopen_calls) == 1
    assert "p01-api.observo.ai" in (urlopen_calls[0][0] or "")
