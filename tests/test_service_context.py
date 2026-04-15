"""Stream A2.c — ServiceContext shim for the gunicorn web process."""
from __future__ import annotations

import pytest


def _make_ctx(tmp_path):
    from components.feedback_channel import FeedbackChannel
    from components.runtime_proxy import RuntimeProxy
    from components.state_store import StateStore
    from components.web_ui.service_context import ServiceContext

    state = StateStore(persist_path=tmp_path / "state.json", follower=True)
    ch = FeedbackChannel(path=tmp_path / "actions.jsonl")
    proxy = RuntimeProxy(
        feedback_channel=ch,
        snapshot_path=tmp_path / "snapshot.json",
        pending_requests_path=tmp_path / "pending.json",
    )
    return ServiceContext(state=state, config={}, feedback_channel=ch, runtime_proxy=proxy)


def test_get_status_matches_real_service_shape(tmp_path):
    ctx = _make_ctx(tmp_path)
    status = ctx.get_status()
    expected_keys = {
        "is_running",
        "pending_conversions",
        "approved_conversions",
        "rejected_conversions",
        "modified_conversions",
        "queue_size",
        "rag_status",
        "sdl_audit_stats",
    }
    assert set(status.keys()) == expected_keys
    assert status["is_running"] is True
    assert status["pending_conversions"] == 0
    assert status["queue_size"] == 0
    assert status["rag_status"] == {}
    assert status["sdl_audit_stats"] == {}


def test_runtime_methods_delegate_to_proxy(tmp_path):
    ctx = _make_ctx(tmp_path)
    assert ctx.request_runtime_reload("p1") is True
    assert ctx.pop_runtime_reload("p1") == "p1"
    assert ctx.pop_runtime_reload("p1") is None

    assert ctx.request_canary_promotion("p2") is True
    assert ctx.pop_canary_promotion("p2") == "p2"

    status = ctx.get_runtime_status()
    assert "runtime_services" in status


def test_service_context_requires_four_args(tmp_path):
    from components.web_ui.service_context import ServiceContext
    from components.state_store import StateStore

    state = StateStore(persist_path=tmp_path / "state.json")
    with pytest.raises(TypeError):
        ServiceContext(state=state, config={})
