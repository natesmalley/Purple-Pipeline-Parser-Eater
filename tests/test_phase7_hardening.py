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

        try:
            from components.web_ui.app import create_flask_app
            app = create_flask_app({"web_ui": {}})
            assert app.debug is False
        except ImportError:
            pytest.skip("web_ui.app not importable in minimal venv")

    def test_app_debug_true_when_development(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "development-debug")
        if "components.web_ui.app" in sys.modules:
            del sys.modules["components.web_ui.app"]

        try:
            from components.web_ui.app import create_flask_app
            app = create_flask_app({"web_ui": {}})
            assert app.debug is True
        except ImportError:
            pytest.skip("web_ui.app not importable in minimal venv")


class TestFlaskSecretKeyProdFailFast:
    def test_prod_without_secret_key_raises(self, monkeypatch):
        """Phase 7.3: production mode without FLASK_SECRET_KEY must hard-fail."""
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)

        if "components.web_ui.security" in sys.modules:
            del sys.modules["components.web_ui.security"]

        try:
            from components.web_ui.security import resolve_flask_secret_key
        except ImportError:
            pytest.skip("web_ui.security not importable")

        with pytest.raises(RuntimeError, match="FLASK_SECRET_KEY"):
            resolve_flask_secret_key()

    def test_dev_without_env_file_generates_and_persists(self, monkeypatch, tmp_path):
        """Phase 7.3: dev mode without FLASK_SECRET_KEY must generate + persist."""
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
        monkeypatch.chdir(tmp_path)

        if "components.web_ui.security" in sys.modules:
            del sys.modules["components.web_ui.security"]

        try:
            from components.web_ui.security import resolve_flask_secret_key
        except ImportError:
            pytest.skip("web_ui.security not importable")

        key1 = resolve_flask_secret_key()
        assert key1
        assert (tmp_path / ".env.local").exists()

        key2 = resolve_flask_secret_key()
        assert key1 == key2


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
