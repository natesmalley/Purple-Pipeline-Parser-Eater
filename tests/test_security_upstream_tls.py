"""Stream A3 — relax _validate_security_config for upstream TLS termination."""
from __future__ import annotations

import pytest


class _Stub:
    """Bare object pretending to be WebFeedbackServer for _validate_security_config."""

    def __init__(self, app_env, tls_enabled):
        self.app_env = app_env
        self.tls_enabled = tls_enabled


def _call(stub):
    from components.web_ui.server import WebFeedbackServer
    WebFeedbackServer._validate_security_config(stub)


def test_production_with_upstream_tls_env_passes(monkeypatch):
    monkeypatch.setenv("WEB_UI_TLS_TERMINATED_UPSTREAM", "1")
    _call(_Stub("production", False))


def test_production_without_tls_or_upstream_still_fails(monkeypatch):
    monkeypatch.delenv("WEB_UI_TLS_TERMINATED_UPSTREAM", raising=False)
    with pytest.raises(ValueError):
        _call(_Stub("production", False))


def test_production_with_in_process_tls_passes(monkeypatch):
    monkeypatch.delenv("WEB_UI_TLS_TERMINATED_UPSTREAM", raising=False)
    _call(_Stub("production", True))


def test_development_passes_without_tls(monkeypatch):
    monkeypatch.delenv("WEB_UI_TLS_TERMINATED_UPSTREAM", raising=False)
    _call(_Stub("development", False))
