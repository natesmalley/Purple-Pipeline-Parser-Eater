"""Stream A2.b — RuntimeProxy web-side runtime shim."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def _make_proxy(tmp_path):
    from components.feedback_channel import FeedbackChannel
    from components.runtime_proxy import RuntimeProxy

    ch = FeedbackChannel(path=tmp_path / "actions.jsonl")
    proxy = RuntimeProxy(
        feedback_channel=ch,
        snapshot_path=tmp_path / "status_snapshot.json",
        pending_requests_path=tmp_path / "pending_requests.json",
    )
    return ch, proxy


def test_pop_returns_none_when_never_requested(tmp_path):
    _, proxy = _make_proxy(tmp_path)
    assert proxy.pop_runtime_reload("foo") is None


def test_request_then_pop_roundtrip(tmp_path):
    _, proxy = _make_proxy(tmp_path)
    assert proxy.request_runtime_reload("foo") is True
    assert proxy.pop_runtime_reload("foo") == "foo"
    assert proxy.pop_runtime_reload("foo") is None


def test_request_is_idempotent(tmp_path):
    _, proxy = _make_proxy(tmp_path)
    proxy.request_runtime_reload("foo")
    proxy.request_runtime_reload("foo")
    proxy.request_runtime_reload("foo")

    data = json.loads((tmp_path / "pending_requests.json").read_text(encoding="utf-8"))
    assert data["runtime_reload"].count("foo") == 1


def test_request_appends_feedback_channel(tmp_path):
    ch, proxy = _make_proxy(tmp_path)
    proxy.request_runtime_reload("foo")
    records, _ = ch.drain_new(0)
    assert len(records) == 1
    assert records[0]["action"] == "runtime_reload_request"
    assert records[0]["parser_id"] == "foo"


def test_canary_methods_independent_of_reload(tmp_path):
    _, proxy = _make_proxy(tmp_path)
    proxy.request_runtime_reload("a")
    proxy.request_canary_promotion("b")
    assert proxy.pop_runtime_reload("b") is None  # b is canary, not reload
    assert proxy.pop_canary_promotion("a") is None  # a is reload, not canary
    assert proxy.pop_runtime_reload("a") == "a"
    assert proxy.pop_canary_promotion("b") == "b"


def test_get_runtime_status_empty_default(tmp_path):
    _, proxy = _make_proxy(tmp_path)
    status = proxy.get_runtime_status()
    assert status == {
        "runtime_services": [],
        "reloads_pending": [],
        "canary_pending": [],
    }


def test_get_runtime_status_reads_snapshot(tmp_path):
    _, proxy = _make_proxy(tmp_path)
    snap = {"runtime_services": ["a"], "reloads_pending": ["x"], "canary_pending": []}
    (tmp_path / "status_snapshot.json").write_text(json.dumps(snap), encoding="utf-8")
    assert proxy.get_runtime_status() == snap


def test_runtime_routes_via_flask_test_client(tmp_path, monkeypatch):
    """Route-level integration test — the regression gate for the operator-caught defect."""
    from components.feedback_channel import FeedbackChannel
    from components.runtime_proxy import RuntimeProxy
    from components.state_store import StateStore
    from components.web_ui.factory import build_production_app
    from components.web_ui.service_context import ServiceContext

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("WEB_UI_HOST", "127.0.0.1")
    monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("FLASK_SECRET_KEY", "x" * 32)

    state = StateStore(persist_path=tmp_path / "state.json", follower=True)
    ch = FeedbackChannel(path=tmp_path / "actions.jsonl")
    proxy = RuntimeProxy(
        feedback_channel=ch,
        snapshot_path=tmp_path / "snapshot.json",
        pending_requests_path=tmp_path / "pending.json",
    )
    ctx = ServiceContext(
        state=state, config={}, feedback_channel=ch, runtime_proxy=proxy,
    )
    app = build_production_app(ctx, {})
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    client = app.test_client()

    r = client.post("/api/v1/runtime/reload/foo")
    assert r.status_code == 200
    assert r.get_json()["status"] == "reload_requested"

    r = client.delete("/api/v1/runtime/reload/foo")
    assert r.status_code == 200
    assert r.get_json()["status"] == "reload_cleared"

    r = client.delete("/api/v1/runtime/reload/foo")
    assert r.status_code == 404

    r = client.post("/api/v1/runtime/canary/bar/promote")
    assert r.status_code == 200
    r = client.delete("/api/v1/runtime/canary/bar/promote")
    assert r.status_code == 200
    r = client.delete("/api/v1/runtime/canary/bar/promote")
    assert r.status_code == 404
