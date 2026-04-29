"""Phase 1.D Web UI auth re-enable tests.

Covers the host/token resolver and the real decorator's 401/200 behavior.
"""

import pytest


class TestAuthResolverStartupBehavior:
    """Stream H (2026-04-28): the resolver always returns a real decorator.
    The previous noop-on-loopback dev path is gone (because auth-on in dev
    has zero meaningful cost and removing it eliminates dev/prod drift).
    The previous hard-fail on non-loopback is also gone (because the token
    auto-generates if missing). Both replaced by ``_resolve_web_ui_auth_token``
    self-bootstrap. See ``test_phase7_hardening.py::TestWebUIAuthTokenSelfBootstrap``
    for the auto-generation contract.
    """

    def test_loopback_no_token_uses_real_decorator(self, monkeypatch, tmp_path):
        """Loopback bind + missing token: real decorator (token auto-generated).
        Pre-Stream-H this returned a no-op decorator."""
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        monkeypatch.setenv("STATE_DIR", str(tmp_path / "data" / "state"))
        from components.web_ui.server import _resolve_auth_decorator
        decorator = _resolve_auth_decorator(bind_host="127.0.0.1")
        assert callable(decorator)

        def target():
            return "ok"

        # Wrapping with the real decorator wraps; calling unwrapped fn
        # directly returns "ok" but the decorated path now has auth checks
        # — still callable as a function-decorator outside a Flask request
        # context (it returns a wrapper, not the original).
        wrapped = decorator(target)
        assert wrapped is not target

    def test_localhost_no_token_uses_real_decorator(self, monkeypatch, tmp_path):
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        monkeypatch.setenv("STATE_DIR", str(tmp_path / "data" / "state"))
        from components.web_ui.server import _resolve_auth_decorator
        decorator = _resolve_auth_decorator(bind_host="localhost")
        assert callable(decorator)

        def target():
            return "ok"
        assert decorator(target) is not target

    def test_ipv6_loopback_no_token_uses_real_decorator(self, monkeypatch, tmp_path):
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        monkeypatch.setenv("STATE_DIR", str(tmp_path / "data" / "state"))
        from components.web_ui.server import _resolve_auth_decorator
        decorator = _resolve_auth_decorator(bind_host="::1")
        assert callable(decorator)

        def target():
            return "ok"
        assert decorator(target) is not target

    def test_nonloopback_without_token_auto_generates(self, monkeypatch, tmp_path):
        """0.0.0.0 bind + missing token: auto-generate, no startup error.
        Pre-Stream-H this raised RuntimeError. See Stream H tests in
        ``test_phase7_hardening.py`` for the persistence + banner contract."""
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        monkeypatch.setenv("STATE_DIR", str(tmp_path / "data" / "state"))
        from components.web_ui.server import _resolve_auth_decorator
        decorator = _resolve_auth_decorator(bind_host="0.0.0.0")
        assert callable(decorator)
        # Token was generated and persisted to STATE_DIR
        assert (tmp_path / "data" / "state" / "web_ui_auth.token").exists()

    def test_nonloopback_empty_token_auto_generates(self, monkeypatch, tmp_path):
        """Whitespace-only token treated as missing → auto-generates fresh
        token. Pre-Stream-H this raised RuntimeError."""
        monkeypatch.setenv("WEB_UI_AUTH_TOKEN", "   ")
        monkeypatch.setenv("STATE_DIR", str(tmp_path / "data" / "state"))
        from components.web_ui.server import _resolve_auth_decorator
        decorator = _resolve_auth_decorator(bind_host="0.0.0.0")
        assert callable(decorator)
        # Verify the env var was overwritten with a non-whitespace token
        import os as _os
        actual = _os.environ.get("WEB_UI_AUTH_TOKEN", "").strip()
        assert actual and actual != "   "

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

    def test_bind_host_0_0_0_0_via_argument_auto_generates_without_token(
        self, monkeypatch, tmp_path,
    ):
        """Stream H: 0.0.0.0 as bind_host with no token auto-generates the
        token instead of hard-failing. Pre-Stream-H this raised RuntimeError.
        Finding #6 (config.yaml host bypass) is now moot because the
        auto-generation path applies to every bind host."""
        monkeypatch.delenv("WEB_UI_HOST", raising=False)
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        monkeypatch.setenv("STATE_DIR", str(tmp_path / "data" / "state"))
        from components.web_ui.server import _resolve_auth_decorator
        decorator = _resolve_auth_decorator(bind_host="0.0.0.0")
        assert callable(decorator)

    def test_bind_host_loopback_via_argument_uses_real_decorator(
        self, monkeypatch, tmp_path,
    ):
        """Stream H: loopback bind also uses the real decorator (token
        auto-generated). Pre-Stream-H this returned the noop decorator."""
        monkeypatch.delenv("WEB_UI_HOST", raising=False)
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        monkeypatch.setenv("STATE_DIR", str(tmp_path / "data" / "state"))
        from components.web_ui.server import _resolve_auth_decorator
        d = _resolve_auth_decorator(bind_host="127.0.0.1")
        assert callable(d)

        def fn():
            return "ok"
        # Real decorator wraps the function (does not return it untouched).
        assert d(fn) is not fn

    def test_webfeedback_server_starts_with_auto_generated_token(
        self, monkeypatch, tmp_path,
    ):
        """Stream H integration: WebFeedbackServer with config.yaml
        host=0.0.0.0 and no env var must START SUCCESSFULLY (not raise).
        The token is auto-generated via _resolve_web_ui_auth_token."""
        monkeypatch.delenv("WEB_UI_HOST", raising=False)
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        monkeypatch.setenv("STATE_DIR", str(tmp_path / "data" / "state"))
        monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret-for-init")
        import asyncio
        from components.web_ui.server import WebFeedbackServer
        config = {
            "web_ui": {"host": "0.0.0.0", "port": 8080},
            "app_env": "development",
        }
        feedback_queue = asyncio.Queue()
        # Pre-Stream-H this raised RuntimeError. Post-Stream-H init
        # succeeds and the token is on the env var.
        server = WebFeedbackServer(
            config=config,
            feedback_queue=feedback_queue,
            service=None,
            event_loop=None,
            runtime_service=None,
        )
        assert server is not None
        import os as _os
        assert _os.environ.get("WEB_UI_AUTH_TOKEN", "").strip()
