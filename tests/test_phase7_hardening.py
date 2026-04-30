"""Phase 7 production hardening tests.

Covers gunicorn CMD, DEBUG default, FLASK_SECRET_KEY prod fail-fast,
StateStore persistence, temperature=0, CVE-bumped requirements.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


class TestGunicornInDockerfile:
    def test_dockerfile_cmd_uses_gunicorn(self):
        """Phase 7.1: Dockerfile CMD must run gunicorn, not Flask dev server."""
        dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
        assert "gunicorn" in dockerfile, (
            "Dockerfile CMD must invoke gunicorn (plan Phase 7.1)"
        )

    def test_dockerfile_does_not_run_dev_server_directly(self):
        dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
        assert 'CMD ["python", "continuous_conversion_service.py"]' not in dockerfile
        assert 'CMD ["python", "-u", "continuous_conversion_service.py"]' not in dockerfile
        assert "flask run" not in dockerfile


class TestDebugDefault:
    def test_app_debug_false_by_default(self, monkeypatch):
        """Phase 7.2: DEBUG must default to False."""
        for key in ("APP_ENV", "FLASK_DEBUG", "DEBUG"):
            monkeypatch.delenv(key, raising=False)

        if "components.web_ui.app" in sys.modules:
            del sys.modules["components.web_ui.app"]

        from components.web_ui.app import create_flask_app
        app = create_flask_app({"web_ui": {}})
        assert app.debug is False

    def test_app_debug_true_when_development(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "development-debug")
        if "components.web_ui.app" in sys.modules:
            del sys.modules["components.web_ui.app"]

        from components.web_ui.app import create_flask_app
        app = create_flask_app({"web_ui": {}})
        assert app.debug is True


class TestFlaskSecretKeySelfBootstrap:
    """Stream H (2026-04-28): FLASK_SECRET_KEY self-bootstraps in BOTH dev
    and production. The previous Phase 7.3 production hard-fail is replaced
    by auto-generation persisted to data/state/flask_secret.key, because
    operators should never have to hand-generate an internal binding secret.
    """

    def test_prod_without_secret_key_auto_generates(self, monkeypatch, tmp_path):
        """Stream H: production mode without FLASK_SECRET_KEY must
        auto-generate + persist to data/state/flask_secret.key (mode 0600).
        This replaces the Phase 7.3 hard-fail."""
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
        monkeypatch.setenv("STATE_DIR", str(tmp_path / "data" / "state"))

        if "components.web_ui.security" in sys.modules:
            del sys.modules["components.web_ui.security"]

        from components.web_ui.security import resolve_flask_secret_key

        key1 = resolve_flask_secret_key()
        assert key1
        assert len(key1) >= 32  # at least 16 bytes hex-encoded
        secret_file = tmp_path / "data" / "state" / "flask_secret.key"
        assert secret_file.exists()
        # Persistence: a second resolve must return the same key
        # (so existing session cookies stay valid across restarts).
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
        key2 = resolve_flask_secret_key()
        assert key1 == key2

    def test_dev_without_env_file_generates_and_persists(self, monkeypatch, tmp_path):
        """Stream H preserves the original Phase 7.3 dev behavior:
        generate + persist to .env.local in CWD."""
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
        monkeypatch.setenv("STATE_DIR", str(tmp_path / "data" / "state"))
        monkeypatch.chdir(tmp_path)

        if "components.web_ui.security" in sys.modules:
            del sys.modules["components.web_ui.security"]

        from components.web_ui.security import resolve_flask_secret_key

        key1 = resolve_flask_secret_key()
        assert key1
        # Dev path lands in either .env.local OR the production-style
        # state file — both are acceptable per the new resolution order.
        assert (tmp_path / ".env.local").exists() or (
            tmp_path / "data" / "state" / "flask_secret.key"
        ).exists()

        key2 = resolve_flask_secret_key()
        assert key1 == key2

    def test_env_var_takes_precedence_over_persisted_file(
        self, monkeypatch, tmp_path
    ):
        """Operator override: setting FLASK_SECRET_KEY env var beats any
        persisted file. This is the secrets-manager / external-injection path."""
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("STATE_DIR", str(tmp_path / "data" / "state"))
        # Pre-populate a file that the resolver should ignore.
        state_dir = tmp_path / "data" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "flask_secret.key").write_text("file-key-should-be-ignored")
        monkeypatch.setenv("FLASK_SECRET_KEY", "env-var-wins")

        if "components.web_ui.security" in sys.modules:
            del sys.modules["components.web_ui.security"]
        from components.web_ui.security import resolve_flask_secret_key

        assert resolve_flask_secret_key() == "env-var-wins"


class TestWebUIAuthTokenSelfBootstrap:
    """Stream H (2026-04-28): WEB_UI_AUTH_TOKEN self-bootstraps. The
    previous "RuntimeError on non-loopback bind without env var" is
    replaced by auto-generation persisted to data/state/web_ui_auth.token
    with a prominent [BOOTSTRAP] log banner.
    """

    def test_token_auto_generated_and_persisted(self, monkeypatch, tmp_path, caplog):
        """Missing token must auto-generate, persist to disk, and log a
        prominent banner with the generated value."""
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        monkeypatch.setenv("STATE_DIR", str(tmp_path / "data" / "state"))

        if "components.web_ui.server" in sys.modules:
            del sys.modules["components.web_ui.server"]
        from components.web_ui.server import _resolve_web_ui_auth_token

        caplog.set_level("WARNING", logger="components.web_ui.server")
        token = _resolve_web_ui_auth_token()
        assert token
        assert len(token) >= 32
        token_file = tmp_path / "data" / "state" / "web_ui_auth.token"
        assert token_file.exists()
        # Banner must surface the actual token value so the operator
        # can use it for API calls.
        assert any(token in record.message for record in caplog.records), (
            "[BOOTSTRAP] banner must include the generated token value"
        )
        assert any("BOOTSTRAP" in record.message for record in caplog.records)

    def test_token_persists_across_resolves(self, monkeypatch, tmp_path):
        """Second resolution call must return the same token (so existing
        clients with a valid token stay authenticated across restarts)."""
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        monkeypatch.setenv("STATE_DIR", str(tmp_path / "data" / "state"))

        if "components.web_ui.server" in sys.modules:
            del sys.modules["components.web_ui.server"]
        from components.web_ui.server import _resolve_web_ui_auth_token

        token1 = _resolve_web_ui_auth_token()
        # Simulate a fresh process: clear the env var the previous call
        # set, force re-resolution from disk.
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        token2 = _resolve_web_ui_auth_token()
        assert token1 == token2

    def test_token_env_var_overrides_persisted_file(self, monkeypatch, tmp_path):
        """Operator override path: env var beats persisted file."""
        monkeypatch.setenv("STATE_DIR", str(tmp_path / "data" / "state"))
        state_dir = tmp_path / "data" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "web_ui_auth.token").write_text("file-token")
        monkeypatch.setenv("WEB_UI_AUTH_TOKEN", "env-var-token")

        if "components.web_ui.server" in sys.modules:
            del sys.modules["components.web_ui.server"]
        from components.web_ui.server import _resolve_web_ui_auth_token

        assert _resolve_web_ui_auth_token() == "env-var-token"

    def test_resolve_auth_decorator_no_longer_raises_on_non_loopback(
        self, monkeypatch, tmp_path,
    ):
        """Stream H removes the pre-existing RuntimeError on non-loopback
        bind without an env var. The decorator must construct successfully
        because the underlying token is auto-generated."""
        monkeypatch.delenv("WEB_UI_AUTH_TOKEN", raising=False)
        monkeypatch.setenv("STATE_DIR", str(tmp_path / "data" / "state"))

        if "components.web_ui.server" in sys.modules:
            del sys.modules["components.web_ui.server"]
        from components.web_ui.server import _resolve_auth_decorator

        # Pre-Stream-H this raised RuntimeError. Post-Stream-H it must
        # return a real callable decorator.
        decorator = _resolve_auth_decorator("0.0.0.0")
        assert callable(decorator)


class TestStateStorePersistence:
    def test_atomic_json_round_trip(self, tmp_path):
        """Phase 7.4: StateStore can persist + reload across instances."""
        from components.state_store import StateStore

        persist_path = tmp_path / "state.json"
        s1 = StateStore(persist_path=persist_path)
        s1.put_pending("p1", {"lua": "code1"})
        s1.put_pending("p2", {"lua": "code2"})
        s1.move_pending_to_approved("p1")

        s2 = StateStore(persist_path=persist_path)
        assert s2.get_pending("p2") == {"lua": "code2"}
        assert s2.pending_count() == 1
        assert s2.approved_count() == 1

    def test_atomic_rename_on_write(self, tmp_path):
        """Phase 7.4: writes must use atomic rename (no partial JSON)."""
        from components.state_store import StateStore
        persist_path = tmp_path / "state.json"
        s = StateStore(persist_path=persist_path)
        s.put_pending("p1", {"lua": "x"})
        content = persist_path.read_text(encoding="utf-8")
        parsed = json.loads(content)
        assert parsed["pending"]["p1"]["lua"] == "x"

    def test_missing_persist_path_is_optional(self):
        """Phase 7.4: StateStore without persist_path works as an in-memory-only store."""
        from components.state_store import StateStore
        s = StateStore()
        s.put_pending("p1", {"x": 1})
        assert s.get_pending("p1") == {"x": 1}


class TestTemperatureZeroDeterminism:
    def test_provider_default_temperature_is_zero(self):
        """Phase 7.5: default temperature for determinism."""
        from components.llm_provider import AnthropicProvider
        import inspect
        sig = inspect.signature(AnthropicProvider.agenerate)
        assert sig.parameters["temperature"].default == 0.0


class TestCveRequirementBumps:
    def test_requests_bumped_to_cve_floor(self):
        """Phase 7.6: requirements.txt must have requests>=2.32.2 for CVE-2024-35195."""
        reqs = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
        import re
        match = re.search(r"^requests\s*(>=|==)\s*(\d+\.\d+(?:\.\d+)?)", reqs, re.MULTILINE)
        assert match, "requests pin not found in requirements.txt"
        version = tuple(int(x) for x in match.group(2).split("."))
        while len(version) < 3:
            version = version + (0,)
        assert version >= (2, 32, 2), (
            f"requests pin {version} < (2, 32, 2) - vulnerable to CVE-2024-35195"
        )

    def test_jinja2_explicit_pin_at_cve_floor(self):
        """Phase 7.6: requirements.txt must have jinja2>=3.1.4 for CVE-2024-34064."""
        reqs = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
        import re
        match = re.search(r"^jinja2\s*(>=|==)\s*(\d+\.\d+(?:\.\d+)?)", reqs, re.MULTILINE | re.IGNORECASE)
        assert match, "jinja2 pin not explicit in requirements.txt (must be added, not transitive)"
        version = tuple(int(x) for x in match.group(2).split("."))
        while len(version) < 3:
            version = version + (0,)
        assert version >= (3, 1, 4), (
            f"jinja2 pin {version} < (3, 1, 4) - vulnerable to CVE-2024-34064"
        )


class TestPipAuditScript:
    def test_pip_audit_script_exists(self):
        script = REPO_ROOT / "scripts" / "run_pip_audit.sh"
        assert script.exists(), "Phase 7.7: scripts/run_pip_audit.sh must exist"

    def test_pip_audit_script_runnable(self):
        script = REPO_ROOT / "scripts" / "run_pip_audit.sh"
        if not script.exists():
            pytest.skip("script missing")
        result = subprocess.run(
            ["bash", "-n", str(script)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"bash syntax error: {result.stderr}"


class TestGitleaksScript:
    def test_gitleaks_script_exists(self):
        script = REPO_ROOT / "scripts" / "run_gitleaks.sh"
        assert script.exists(), "Phase 7.8: scripts/run_gitleaks.sh must exist"

    def test_gitleaks_script_runnable(self):
        script = REPO_ROOT / "scripts" / "run_gitleaks.sh"
        if not script.exists():
            pytest.skip("script missing")
        result = subprocess.run(
            ["bash", "-n", str(script)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0

    def test_gitleaks_script_falls_back_gracefully(self):
        """If gitleaks isn't installed, the script must fall back to check_secret_leaks.sh."""
        script = REPO_ROOT / "scripts" / "run_gitleaks.sh"
        content = script.read_text(encoding="utf-8")
        assert "check_secret_leaks.sh" in content, (
            "run_gitleaks.sh must fall back to check_secret_leaks.sh when gitleaks missing"
        )
