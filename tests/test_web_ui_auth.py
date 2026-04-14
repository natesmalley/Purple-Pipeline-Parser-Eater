"""Phase 1.D Web UI auth re-enable tests.

Covers the host/token resolver and the real decorator's 401/200 behavior.
"""

import pytest


class TestAuthResolverStartupBehavior:
    def test_loopback_no_token_starts_with_noop(self, monkeypatch):
        """Loopback bind + missing token = dev mode, no-op decorator."""
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        from components.web_ui.server import _resolve_auth_decorator
        decorator = _resolve_auth_decorator(bind_host="127.0.0.1")

        def target():
            return "ok"

        assert decorator(target)() == "ok"

    def test_localhost_no_token_starts_with_noop(self, monkeypatch):
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        from components.web_ui.server import _resolve_auth_decorator
        decorator = _resolve_auth_decorator(bind_host="localhost")

        def target():
            return "ok"

        assert decorator(target)() == "ok"

    def test_ipv6_loopback_no_token_starts_with_noop(self, monkeypatch):
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        from components.web_ui.server import _resolve_auth_decorator
        decorator = _resolve_auth_decorator(bind_host="::1")

        def target():
            return "ok"

        assert decorator(target)() == "ok"

    def test_nonloopback_without_token_hard_fails(self, monkeypatch):
        """0.0.0.0 bind + missing token = hard fail at startup."""
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        from components.web_ui.server import _resolve_auth_decorator
        with pytest.raises(RuntimeError, match="WEB_UI_AUTH_TOKEN"):
            _resolve_auth_decorator(bind_host="0.0.0.0")

    def test_nonloopback_empty_token_hard_fails(self, monkeypatch):
        """Whitespace-only token treated as missing."""
        monkeypatch.setenv("WEB_UI_AUTH_TOKEN", "   ")
        from components.web_ui.server import _resolve_auth_decorator
        with pytest.raises(RuntimeError, match="WEB_UI_AUTH_TOKEN"):
            _resolve_auth_decorator(bind_host="0.0.0.0")

    def test_nonloopback_with_token_uses_real_decorator(self, monkeypatch):
        """0.0.0.0 + token set = real decorator (not identity)."""
        monkeypatch.setenv("WEB_UI_AUTH_TOKEN", "test-token-0123456789abcdef")
        from components.web_ui.server import _resolve_auth_decorator
        decorator = _resolve_auth_decorator(bind_host="0.0.0.0")

        def target():
            return "should-not-reach"

        wrapped = decorator(target)
        assert wrapped is not target

    def test_loopback_with_token_uses_real_decorator(self, monkeypatch):
        """Loopback bind + token set = stricter opt-in (real decorator even on loopback)."""
        monkeypatch.setenv("WEB_UI_AUTH_TOKEN", "test-token-0123456789abcdef")
        from components.web_ui.server import _resolve_auth_decorator
        decorator = _resolve_auth_decorator(bind_host="127.0.0.1")

        def target():
            return "ok"

        wrapped = decorator(target)
        assert wrapped is not target


class TestAuthDecoratorRequestHandling:
    """Test wrapped-route behavior with a tiny Flask app."""

    def _build_app(self, monkeypatch, token):
        monkeypatch.setenv("WEB_UI_AUTH_TOKEN", token)
        from flask import Flask
        from components.web_ui.server import _resolve_auth_decorator
        app = Flask(__name__)
        require_auth = _resolve_auth_decorator(bind_host="0.0.0.0")

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


class TestAuthConfigYamlMismatchFix:
    """Finding #6 regression gate — auth must honor effective bind host, not just env."""

    def test_resolve_decorator_accepts_bind_host_argument(self, monkeypatch):
        """_resolve_auth_decorator must take a bind_host argument."""
        monkeypatch.delenv("WEB_UI_HOST", raising=False)
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        from components.web_ui.server import _resolve_auth_decorator
        import inspect
        sig = inspect.signature(_resolve_auth_decorator)
        assert "bind_host" in sig.parameters, \
            "Finding #6: _resolve_auth_decorator must accept bind_host to prevent config.yaml bypass"

    def test_bind_host_0_0_0_0_via_argument_hard_fails_without_token(self, monkeypatch):
        """Passing 0.0.0.0 as bind_host with no token must hard-fail, even if env WEB_UI_HOST is unset."""
        monkeypatch.delenv("WEB_UI_HOST", raising=False)  # simulate config.yaml-only config
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        from components.web_ui.server import _resolve_auth_decorator
        with pytest.raises(RuntimeError, match="WEB_UI_AUTH_TOKEN"):
            _resolve_auth_decorator(bind_host="0.0.0.0")

    def test_bind_host_loopback_via_argument_noop_decorator(self, monkeypatch):
        """Passing loopback as bind_host with no token must return noop."""
        monkeypatch.delenv("WEB_UI_HOST", raising=False)
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        from components.web_ui.server import _resolve_auth_decorator
        d = _resolve_auth_decorator(bind_host="127.0.0.1")

        def fn():
            return "ok"
        assert d(fn)() == "ok"

    def test_webfeedback_server_passes_effective_bind_host(self, monkeypatch):
        """Integration: WebFeedbackServer with config.yaml host=0.0.0.0 and no env var must hard-fail at startup."""
        monkeypatch.delenv("WEB_UI_HOST", raising=False)
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        import asyncio
        from components.web_ui.server import WebFeedbackServer
        config = {
            "web_ui": {"host": "0.0.0.0", "port": 8080},
            "app_env": "development",
        }
        feedback_queue = asyncio.Queue()
        with pytest.raises(RuntimeError, match="WEB_UI_AUTH_TOKEN"):
            WebFeedbackServer(
                config=config,
                feedback_queue=feedback_queue,
                service=None,
                event_loop=None,
                runtime_service=None,
            )
