#!/usr/bin/env python3
"""W10/T1 — Security fixes validation against REAL production code.

This file replaces a previous version that defined helper functions inline
and asserted against the local helpers (i.e., it was testing the test, not
production code). Each test below now exercises a real implementation in
``components/`` or ``utils/``.

If a helper had no production equivalent, the corresponding test was
deleted with a documented reason rather than left in place to give a false
sense of coverage. The deletion log:

- ``test_tmpfs_permissions`` — the original test invented a
  ``validate_tmpfs_mode`` helper that does not exist anywhere in the
  codebase. Tmpfs permissions are a docker-compose concern (not Python),
  and the live ``docker-compose.yml`` is mixed: lines 154/162/169/180/304
  use mode 1777, while line 361 uses 1770 ("SECURITY FIX: Phase 4 -
  Group-writable only") — meaning a uniform "must be 1770" assertion
  would not match the file's actual partial-hardening state. Deleted
  with no replacement; the right place to enforce mode policy is in
  the compose file itself, not a Python unit test.
- ``test_lua_string_concatenation_safety`` — the original test compared
  two inline helpers (``unsafe_wrap`` and ``safe_wrap``) that don't
  appear in production code. The Lua wrap path lives in
  ``components/lua_deploy_wrapper.py:wrap_for_observo`` and is exercised
  by ``tests/test_lua_deploy_wrapper.py`` and
  ``tests/test_emit_sites_use_wrapper.py``. Neither asserts the
  f-string-vs-concat property the original test gestured at, so this
  deletion leaves a small coverage gap; if the f-string-injection vector
  was a real regression history, file a follow-up to add a targeted
  assertion. No replacement here.
"""

import os
from pathlib import Path

import pytest

from utils.security import SecurityError, validate_path
from utils.config_expansion import expand_environment_variables
from utils.error_handler import ConversionError


PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================================
# PHASE 1 — Path traversal & env-var expansion
# ============================================================================


class TestPathTraversalSanitization:
    """Production target: ``utils.security.validate_path``."""

    def test_relative_traversal_rejected(self, tmp_path):
        """``../`` segments must be blocked when they escape the base dir."""
        base = tmp_path
        with pytest.raises(SecurityError, match="[Pp]ath traversal"):
            validate_path("../../etc/passwd", base)

    def test_absolute_path_rejected_by_default(self, tmp_path):
        """Absolute paths are rejected unless explicitly allowed."""
        with pytest.raises(SecurityError, match="[Aa]bsolute"):
            validate_path("/etc/passwd", tmp_path)

    def test_safe_relative_path_accepted(self, tmp_path):
        """A path that resolves inside the base dir is returned resolved."""
        # Pre-create the file so existence isn't the gate (validate_path
        # itself only checks containment; existence is enforced by the
        # higher-level helpers like validate_file_path).
        target = tmp_path / "subdir" / "file.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("ok", encoding="utf-8")

        resolved = validate_path("subdir/file.txt", tmp_path)
        assert resolved == target.resolve()

    def test_dotdot_collapse_still_rejected(self, tmp_path):
        """A path that contains ``..`` but resolves outside is rejected."""
        with pytest.raises(SecurityError, match="[Pp]ath traversal"):
            validate_path("subdir/../../outside", tmp_path)


class TestEnvironmentVariableExpansion:
    """Production target: ``utils.config_expansion.expand_environment_variables``."""

    def test_basic_expansion(self, monkeypatch):
        monkeypatch.setenv("PPE_TEST_VAR", "test_value")
        assert expand_environment_variables("${PPE_TEST_VAR}") == "test_value"
        assert (
            expand_environment_variables("prefix_${PPE_TEST_VAR}_suffix")
            == "prefix_test_value_suffix"
        )

    def test_default_value_used_when_var_missing(self, monkeypatch):
        monkeypatch.delenv("PPE_NONEXISTENT", raising=False)
        # Production helper uses ``${VAR:default}`` syntax (single colon).
        assert expand_environment_variables("${PPE_NONEXISTENT:fallback}") == "fallback"

    def test_default_skipped_when_var_set(self, monkeypatch):
        monkeypatch.setenv("PPE_TEST_VAR", "test_value")
        assert (
            expand_environment_variables("${PPE_TEST_VAR:fallback}") == "test_value"
        )

    def test_required_var_raises_conversion_error(self, monkeypatch):
        monkeypatch.delenv("PPE_REQUIRED", raising=False)
        with pytest.raises(ConversionError, match="PPE_REQUIRED"):
            expand_environment_variables("${PPE_REQUIRED:?Must be set}")

    def test_required_var_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv("PPE_REQUIRED", "set_value")
        assert (
            expand_environment_variables("${PPE_REQUIRED:?Should not raise}")
            == "set_value"
        )


# ============================================================================
# PHASE 2 — TLS enforcement & XSS auto-escape
# ============================================================================


class TestTLSEnforcement:
    """Production target: ``components.web_ui.server.WebFeedbackServer
    ._validate_security_config``. Verifies the production-mode TLS gate
    exists in the live module source (substring assertion against the
    real method body) so a refactor that drops the gate fails this test.
    """

    def test_validate_security_config_method_exists(self):
        from components.web_ui import server as srv_mod

        # The method must exist on the live class.
        assert hasattr(srv_mod.WebFeedbackServer, "_validate_security_config"), (
            "WebFeedbackServer._validate_security_config was removed — "
            "TLS-in-production gate would no longer run"
        )

    def test_production_no_tls_raises_value_error(self):
        """The literal production-no-TLS branch must raise ``ValueError``
        with the canonical message. We verify by reading the method's
        source so we don't need to build a full Flask server to trigger
        it (server construction has many env-var dependencies)."""
        from components.web_ui import server as srv_mod
        import inspect

        source = inspect.getsource(srv_mod.WebFeedbackServer._validate_security_config)
        assert "TLS must be enabled in production environment" in source
        assert "raise ValueError" in source
        # The bypass for upstream-terminated TLS must remain explicit.
        assert "WEB_UI_TLS_TERMINATED_UPSTREAM" in source


class TestJinjaAutoescapeWired:
    """Production target: ``components.web_ui.security.setup_flask_security``
    must enable Jinja2 autoescape on the Flask app it configures."""

    def test_setup_flask_security_enables_autoescape(self):
        from flask import Flask

        from components.web_ui.security import setup_flask_security

        app = Flask(__name__)
        # Disable rate-limit Redis probe interference.
        os.environ.pop("REDIS_URL", None)
        setup_flask_security(app, {"web_ui": {}})

        assert app.jinja_env.autoescape is True, (
            "setup_flask_security must enable Jinja2 autoescaping for XSS protection"
        )


# ============================================================================
# PHASE 3 — CSRF protection wired in real Flask app
# ============================================================================


class TestCSRFProtectionWired:
    """Production target: ``components.web_ui.security.setup_flask_security``
    must install Flask-WTF CSRF protection and a SECRET_KEY."""

    def test_csrf_and_secret_key_configured(self):
        from flask import Flask

        from components.web_ui.security import setup_flask_security

        app = Flask(__name__)
        os.environ.pop("REDIS_URL", None)
        setup_flask_security(app, {"web_ui": {}})

        # CSRF protection is configured via app.config flags.
        assert app.config.get("WTF_CSRF_CHECK_DEFAULT") is True
        assert app.config.get("WTF_CSRF_TIME_LIMIT") is not None
        # SECRET_KEY must be a real, non-empty secret (not the literal
        # "dev" placeholder Flask uses when nothing is set).
        secret = app.config.get("SECRET_KEY")
        assert secret, "SECRET_KEY must be set by setup_flask_security"
        assert len(secret) >= 32


# ============================================================================
# PHASE 4 — Request size limits, tmpfs permissions, MD5 flag
# ============================================================================


class TestRequestSizeLimit:
    """Production target: ``components.web_ui.security.setup_flask_security``
    must install a ``MAX_CONTENT_LENGTH`` of 16 MiB."""

    def test_max_content_length_is_16mb(self):
        from flask import Flask

        from components.web_ui.security import setup_flask_security

        app = Flask(__name__)
        os.environ.pop("REDIS_URL", None)
        setup_flask_security(app, {"web_ui": {}})

        assert app.config.get("MAX_CONTENT_LENGTH") == 16 * 1024 * 1024


class TestMD5UsedForSecurityFlag:
    """Production target: the codebase must always pass
    ``usedforsecurity=False`` to ``hashlib.md5`` (Bandit B324). Verify
    by scanning ``components/`` for any naked ``hashlib.md5(`` call."""

    def test_no_naked_md5_calls_in_components(self):
        components_dir = PROJECT_ROOT / "components"
        offenders: list[tuple[str, int, str]] = []
        for py in components_dir.rglob("*.py"):
            try:
                lines = py.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for i, line in enumerate(lines, 1):
                if "hashlib.md5(" in line and "usedforsecurity=False" not in line:
                    # Walk a small forward window to catch calls split
                    # across multiple lines.
                    window = "\n".join(lines[i - 1 : min(len(lines), i + 4)])
                    if "usedforsecurity=False" not in window:
                        offenders.append(
                            (str(py.relative_to(PROJECT_ROOT)), i, line.strip())
                        )

        assert not offenders, (
            "hashlib.md5 calls without usedforsecurity=False:\n"
            + "\n".join(f"  {f}:{n}: {ln}" for f, n, ln in offenders)
        )
