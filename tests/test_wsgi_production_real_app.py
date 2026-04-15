"""Stream A5 — wsgi_production.create_app builds a real app via ServiceContext."""
from __future__ import annotations

import importlib
import sys

import pytest


@pytest.fixture
def env_setup(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("WEB_UI_HOST", "127.0.0.1")
    monkeypatch.setenv("WEB_UI_TLS_TERMINATED_UPSTREAM", "1")
    monkeypatch.setenv("FLASK_SECRET_KEY", "x" * 64)
    monkeypatch.setenv("WEB_UI_AUTH_TOKEN", "tok-" + "a" * 32)
    monkeypatch.setenv("STATE_STORE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setenv("FEEDBACK_CHANNEL_PATH", str(tmp_path / "actions.jsonl"))
    monkeypatch.setenv("RUNTIME_SNAPSHOT_PATH", str(tmp_path / "snapshot.json"))
    monkeypatch.setenv("RUNTIME_PENDING_REQUESTS_PATH", str(tmp_path / "pending.json"))
    yield tmp_path


def _import_fresh():
    if "wsgi_production" in sys.modules:
        del sys.modules["wsgi_production"]
    return importlib.import_module("wsgi_production")


def test_app_has_health_endpoint(env_setup):
    mod = _import_fresh()
    rules = [r.rule for r in mod.app.url_map.iter_rules()]
    assert "/health" in rules


def test_app_has_routes_registered(env_setup):
    mod = _import_fresh()
    rules = list(mod.app.url_map.iter_rules())
    # Stub had 0 routes; real wiring registers many
    assert len(rules) > 5


def test_service_context_is_fully_populated(env_setup, monkeypatch):
    captured = {}

    from components.web_ui import service_context as sc_mod
    real_init = sc_mod.ServiceContext.__init__

    def spy_init(self, *args, **kwargs):
        real_init(self, *args, **kwargs)
        captured["state"] = self.state
        captured["feedback_channel"] = self.feedback_channel
        captured["runtime_proxy"] = self.runtime_proxy

    monkeypatch.setattr(sc_mod.ServiceContext, "__init__", spy_init)
    _import_fresh()
    assert captured.get("feedback_channel") is not None
    assert captured.get("runtime_proxy") is not None
    assert captured.get("state") is not None


def test_state_store_wired_with_follower_true(env_setup, monkeypatch):
    captured = {}

    from components import state_store as ss_mod
    real_init = ss_mod.StateStore.__init__

    def spy_init(self, *args, **kwargs):
        captured["follower"] = kwargs.get("follower", False)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(ss_mod.StateStore, "__init__", spy_init)
    _import_fresh()
    assert captured.get("follower") is True
