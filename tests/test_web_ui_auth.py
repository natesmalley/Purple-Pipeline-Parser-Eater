"""Phase 1.D Web UI auth re-enable tests.

Covers the host/token resolver and the real decorator's 401/200 behavior.
"""

import pytest


class TestAuthResolverStartupBehavior:
    def test_loopback_no_token_starts_with_noop(self, monkeypatch):
        """Loopback bind + missing token = dev mode, no-op decorator."""
        monkeypatch.setenv("WEB_UI_HOST", "127.0.0.1")
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        from components.web_ui.server import _resolve_auth_decorator
        decorator = _resolve_auth_decorator()

        def target():
            return "ok"

        assert decorator(target)() == "ok"

    def test_localhost_no_token_starts_with_noop(self, monkeypatch):
        monkeypatch.setenv("WEB_UI_HOST", "localhost")
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        from components.web_ui.server import _resolve_auth_decorator
        decorator = _resolve_auth_decorator()

        def target():
            return "ok"

        assert decorator(target)() == "ok"

    def test_ipv6_loopback_no_token_starts_with_noop(self, monkeypatch):
        monkeypatch.setenv("WEB_UI_HOST", "::1")
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        from components.web_ui.server import _resolve_auth_decorator
        decorator = _resolve_auth_decorator()

        def target():
            return "ok"

        assert decorator(target)() == "ok"

    def test_nonloopback_without_token_hard_fails(self, monkeypatch):
        """0.0.0.0 bind + missing token = hard fail at startup."""
        monkeypatch.setenv("WEB_UI_HOST", "0.0.0.0")
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        from components.web_ui.server import _resolve_auth_decorator
        with pytest.raises(RuntimeError, match="WEB_UI_AUTH_TOKEN"):
            _resolve_auth_decorator()

    def test_nonloopback_empty_token_hard_fails(self, monkeypatch):
        """Whitespace-only token treated as missing."""
        monkeypatch.setenv("WEB_UI_HOST", "0.0.0.0")
        monkeypatch.setenv("WEB_UI_AUTH_TOKEN", "   ")
        from components.web_ui.server import _resolve_auth_decorator
        with pytest.raises(RuntimeError, match="WEB_UI_AUTH_TOKEN"):
            _resolve_auth_decorator()

    def test_nonloopback_with_token_uses_real_decorator(self, monkeypatch):
        """0.0.0.0 + token set = real decorator (not identity)."""
        monkeypatch.setenv("WEB_UI_HOST", "0.0.0.0")
        monkeypatch.setenv("WEB_UI_AUTH_TOKEN", "test-token-0123456789abcdef")
        from components.web_ui.server import _resolve_auth_decorator
        decorator = _resolve_auth_decorator()

        def target():
            return "should-not-reach"

        wrapped = decorator(target)
        assert wrapped is not target

    def test_loopback_with_token_uses_real_decorator(self, monkeypatch):
        """Loopback bind + token set = stricter opt-in (real decorator even on loopback)."""
        monkeypatch.setenv("WEB_UI_HOST", "127.0.0.1")
        monkeypatch.setenv("WEB_UI_AUTH_TOKEN", "test-token-0123456789abcdef")
        from components.web_ui.server import _resolve_auth_decorator
        decorator = _resolve_auth_decorator()

        def target():
            return "ok"

        wrapped = decorator(target)
        assert wrapped is not target


class TestAuthDecoratorRequestHandling:
    """Test wrapped-route behavior with a tiny Flask app."""

    def _build_app(self, monkeypatch, token):
        monkeypatch.setenv("WEB_UI_HOST", "0.0.0.0")
        monkeypatch.setenv("WEB_UI_AUTH_TOKEN", token)
        from flask import Flask
        from components.web_ui.server import _resolve_auth_decorator
        app = Flask(__name__)
        require_auth = _resolve_auth_decorator()

        @app.route("/protected")
        @require_auth
        def protected():
            return "secret"

        return app

    def test_request_without_token_gets_401(self, monkeypatch):
        app = self._build_app(monkeypatch, "secret-token-32-chars-long-xxxxxx")
        with app.test_client() as client:
            resp = client.get("/protected")
            assert resp.status_code == 401

    def test_request_with_valid_token_passes(self, monkeypatch):
        token = "secret-token-32-chars-long-xxxxxx"
        app = self._build_app(monkeypatch, token)
        with app.test_client() as client:
            resp = client.get("/protected", headers={"X-Auth-Token": token})
            assert resp.status_code == 200
            assert b"secret" in resp.data

    def test_request_with_wrong_token_gets_401(self, monkeypatch):
        app = self._build_app(monkeypatch, "the-real-token-0123456789abcdefff")
        with app.test_client() as client:
            resp = client.get("/protected", headers={"X-Auth-Token": "wrong-token"})
            assert resp.status_code == 401
