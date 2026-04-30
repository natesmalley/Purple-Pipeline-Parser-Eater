"""W5 (plan 2026-04-29): SSRF gate on POST /api/v1/settings (observo
section).

Section-shape body verified at routes.py:3337-3341 (canonical form
the JS settings client posts: ``{"section": "observo", ...}``).
"""
from __future__ import annotations

import socket

import pytest
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


class _StubSettingsStore:
    """A SettingsStore stand-in that never raises on update()."""

    def __init__(self):
        self.last_patch = None

    def update(self, patch):  # noqa: D401 - simple stub
        self.last_patch = patch
        return self.all_redacted()

    def all_redacted(self):
        return {}

    def get(self, _path, default=None):
        return default


def _make_getaddrinfo(ip: str):
    def _stub(*_args, **_kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]
    return _stub


def _build_app(monkeypatch):
    """Build a Flask app with no-op auth + a stub SettingsStore."""

    def _no_auth(fn):
        return fn

    monkeypatch.setattr(routes_module, "ParserLuaWorkbench", lambda: object())
    monkeypatch.setattr(routes_module, "HarnessOrchestrator", lambda: object())

    app = Flask(__name__)
    app.config["TESTING"] = True
    app._settings_store = _StubSettingsStore()  # type: ignore[attr-defined]
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


def test_settings_observo_loopback_rejected(monkeypatch):
    """POST observo.base_url=http://127.0.0.1 returns 400 with
    ``error == "ssrf_blocked"`` and the SettingsStore is NOT updated."""
    app = _build_app(monkeypatch)
    client = app.test_client()

    resp = client.post(
        "/api/v1/settings",
        json={"section": "observo", "base_url": "http://127.0.0.1"},
    )
    assert resp.status_code == 400, resp.get_json()
    body = resp.get_json()
    assert body["error"] == "ssrf_blocked"
    assert isinstance(body.get("reason"), str) and body["reason"]
    # Trip-wire: SettingsStore must NOT have received the bad URL.
    assert app._settings_store.last_patch is None  # type: ignore[attr-defined]


def test_settings_observo_off_allowlist_rejected(monkeypatch):
    """An attacker hostname that is NOT under *.observo.ai is rejected
    even when its resolved IP is public."""
    monkeypatch.setattr("socket.getaddrinfo", _make_getaddrinfo("8.8.8.8"))
    app = _build_app(monkeypatch)
    client = app.test_client()

    resp = client.post(
        "/api/v1/settings",
        json={
            "section": "observo",
            "base_url": "https://attacker.example/api",
        },
    )
    assert resp.status_code == 400, resp.get_json()
    body = resp.get_json()
    assert body["error"] == "ssrf_blocked"
    assert app._settings_store.last_patch is None  # type: ignore[attr-defined]


def test_settings_observo_observo_ai_accepted(monkeypatch):
    """``https://p01-api.observo.ai`` matches *.observo.ai and is
    persisted via SettingsStore."""
    monkeypatch.setattr("socket.getaddrinfo", _make_getaddrinfo("8.8.8.8"))
    app = _build_app(monkeypatch)
    client = app.test_client()

    resp = client.post(
        "/api/v1/settings",
        json={
            "section": "observo",
            "base_url": "https://p01-api.observo.ai",
        },
    )
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body.get("ok") is True
    # Confirm the patch reached SettingsStore unmodified.
    assert app._settings_store.last_patch == {  # type: ignore[attr-defined]
        "integrations": {
            "observo": {"base_url": "https://p01-api.observo.ai"},
        }
    }


def test_settings_sdl_loopback_rejected(monkeypatch):
    """SDL is gated without an allowlist (operator-supplied) but private
    IPs are still rejected."""
    app = _build_app(monkeypatch)
    client = app.test_client()

    resp = client.post(
        "/api/v1/settings",
        json={"section": "sdl", "api_url": "http://192.168.1.10/sdl"},
    )
    assert resp.status_code == 400, resp.get_json()
    body = resp.get_json()
    assert body["error"] == "ssrf_blocked"
    assert app._settings_store.last_patch is None  # type: ignore[attr-defined]


def test_settings_sdl_public_accepted(monkeypatch):
    """A public-resolving SDL endpoint is accepted (no allowlist)."""
    monkeypatch.setattr("socket.getaddrinfo", _make_getaddrinfo("8.8.8.8"))
    app = _build_app(monkeypatch)
    client = app.test_client()

    resp = client.post(
        "/api/v1/settings",
        json={
            "section": "sdl",
            "api_url": "https://sdl.example.com/api",
        },
    )
    assert resp.status_code == 200, resp.get_json()
