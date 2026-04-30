import subprocess

import pytest
from flask import Flask

from components.web_ui import routes as routes_module


class _ServiceStub:
    pending_conversions = {}

    def get_status(self):
        return {}

    def get_runtime_status(self):
        return {"metrics": {}, "reload_requests": {}, "pending_promotions": {}}

    def request_runtime_reload(self, parser_id):
        return False

    def pop_runtime_reload(self, parser_id):
        return None

    def request_canary_promotion(self, parser_id):
        return False

    def pop_canary_promotion(self, parser_id):
        return None


def _build_app(monkeypatch):
    class FakeWorkbench:
        def _find_entry(self, parser_name):
            return {"parser_name": parser_name, "config": {"parser_name": parser_name}}

        def list_parsers(self):
            return []

        def build_parser(self, parser_name):
            return None

        def build_parser_with_agent(self, parser_name, force_regenerate=False):
            return None

        def _get_agent(self):
            return None

    class FakeHarness:
        def run_all_checks(self, *args, **kwargs):
            return {}

        def run_single_check(self, *args, **kwargs):
            return {}

    def _no_auth(fn):
        return fn

    monkeypatch.setattr(routes_module, "ParserLuaWorkbench", FakeWorkbench)
    monkeypatch.setattr(routes_module, "HarnessOrchestrator", FakeHarness)

    app = Flask(__name__)
    app.config["TESTING"] = True
    routes_module.register_routes(
        app,
        service=_ServiceStub(),
        feedback_queue=None,
        runtime_service=None,
        event_loop=None,
        require_auth=_no_auth,
        rate_limiter=None,
    )
    return app


def test_upload_pr_requires_token(monkeypatch):
    app = _build_app(monkeypatch)
    client = app.test_client()
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    response = client.post(
        "/api/v1/workbench/upload-pr",
        json={
            "parser_name": "okta_logs-latest",
            "lua_code": "function processEvent(event) return event end",
        },
    )
    assert response.status_code == 503
    assert "GITHUB_TOKEN not configured" in response.get_json()["error"]


def test_upload_pr_success_with_preflight(monkeypatch):
    app = _build_app(monkeypatch)
    client = app.test_client()
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("GITHUB_OWNER", "example-org")
    monkeypatch.setenv("GITHUB_REPO", "example-repo")

    calls = []

    def fake_run(cmd, check=True, capture_output=True, text=True):
        calls.append(cmd)
        if cmd[:4] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="feature/testing-harness\n", stderr="")
        if cmd[:3] == ["git", "rev-parse", "--verify"]:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="not found")
        if cmd[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="https://github.com/example/pr/1\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    response = client.post(
        "/api/v1/workbench/upload-pr",
        json={
            "parser_name": "okta_logs-latest",
            "lua_code": "function processEvent(event) return event end",
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "pr_created"
    assert payload["target_repo"] == "example-org/example-repo"
    assert any(cmd[:3] == ["gh", "auth", "status"] for cmd in calls)


def test_upload_pr_includes_feedback_context_in_pr_body(monkeypatch):
    app = _build_app(monkeypatch)
    client = app.test_client()
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("GITHUB_OWNER", "example-org")
    monkeypatch.setenv("GITHUB_REPO", "example-repo")

    calls = []

    def fake_run(cmd, check=True, capture_output=True, text=True):
        calls.append(cmd)
        if cmd[:4] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="feature/testing-harness\n", stderr="")
        if cmd[:3] == ["git", "rev-parse", "--verify"]:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="not found")
        if cmd[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="https://github.com/example/pr/2\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    response = client.post(
        "/api/v1/workbench/upload-pr",
        json={
            "parser_name": "okta_logs-latest",
            "lua_code": "function processEvent(event) return event end",
            "match_feedback": {"vote": "down"},
            "inference_details": {
                "inference_reason": "Inferred known parser from high-signal sample fields.",
                "inference_signals": ["okta", "signin", "authentication"],
                "resolved_parser_name": "okta_logs-latest",
            },
        },
    )
    assert response.status_code == 200
    pr_create_cmd = next(cmd for cmd in calls if cmd[:3] == ["gh", "pr", "create"])
    body_value = pr_create_cmd[pr_create_cmd.index("--body") + 1]
    assert "Feedback Context:" in body_value
    assert "Match feedback vote: `down`" in body_value
    assert "Feedback artifact:" in body_value


def test_upload_pr_fails_when_gh_auth_invalid(monkeypatch):
    app = _build_app(monkeypatch)
    client = app.test_client()
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    def fake_run(cmd, check=True, capture_output=True, text=True):
        if cmd[:3] == ["gh", "auth", "status"]:
            raise subprocess.CalledProcessError(1, cmd, stderr="not logged in")
        if cmd[:4] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="feature/testing-harness\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    response = client.post(
        "/api/v1/workbench/upload-pr",
        json={
            "parser_name": "okta_logs-latest",
            "lua_code": "function processEvent(event) return event end",
        },
    )
    assert response.status_code == 500
    assert "Git/GitHub operation failed" in response.get_json()["error"]


def test_upload_pr_defaults_target_repo_from_origin(monkeypatch):
    app = _build_app(monkeypatch)
    client = app.test_client()
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.delenv("GITHUB_OWNER", raising=False)
    monkeypatch.delenv("GITHUB_REPO", raising=False)

    calls = []

    def fake_run(cmd, check=True, capture_output=True, text=True):
        calls.append(cmd)
        if cmd[:4] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="main\n", stderr="")
        if cmd[:4] == ["git", "remote", "get-url", "origin"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="git@github.com:acme/security-parsers.git\n", stderr="")
        if cmd[:3] == ["git", "rev-parse", "--verify"]:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="not found")
        if cmd[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="https://github.com/acme/security-parsers/pull/1\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    response = client.post(
        "/api/v1/workbench/upload-pr",
        json={
            "parser_name": "okta_logs-latest",
            "lua_code": "function processEvent(event) return event end",
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["target_repo"] == "acme/security-parsers"
    assert any(cmd[:3] == ["gh", "pr", "create"] and "--repo" in cmd for cmd in calls)


# ---------------------------------------------------------------------------
# W4 regression: hard-reject lint gate must fire BEFORE any git/gh subprocess
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dangerous_lua", [
    'function processEvent(event) os.execute("id"); return event end',
    'function processEvent(event) load("os.execute(\'id\')")(); return event end',
    'function processEvent(event) string.dump(processEvent); return event end',
    'function processEvent(event) _G["os"]["execute"]("rm -rf /"); return event end',
    'function processEvent(event) _ENV["io"]["popen"]("nc 1.2.3.4 443"); return event end',
])
def test_upload_pr_hard_rejects_dangerous_lua_before_subprocess(monkeypatch, dangerous_lua):
    """W4: dangerous Lua POSTed to /api/v1/workbench/upload-pr must return 400
    with `error == "hard_reject"` BEFORE the route invokes git/gh via
    subprocess. We tripwire `subprocess.run` so a regression that calls
    subprocess before the lint gate fails the test loudly."""
    app = _build_app(monkeypatch)
    client = app.test_client()
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("GITHUB_OWNER", "example-org")
    monkeypatch.setenv("GITHUB_REPO", "example-repo")

    def _tripwire(*args, **kwargs):
        pytest.fail("subprocess.run called before lint hard-reject")

    monkeypatch.setattr(subprocess, "run", _tripwire)

    response = client.post(
        "/api/v1/workbench/upload-pr",
        json={
            "parser_name": "okta_logs-latest",
            "lua_code": dangerous_lua,
        },
    )

    assert response.status_code == 400, (
        f"Expected 400 hard_reject for: {dangerous_lua!r}; got {response.status_code} "
        f"body={response.get_json()}"
    )
    payload = response.get_json()
    assert payload["error"] == "hard_reject"
    assert isinstance(payload["findings"], list)
    assert len(payload["findings"]) >= 1
    for finding in payload["findings"]:
        assert "pattern" in finding
        assert "description" in finding
    assert isinstance(payload.get("rejection_reason"), str)
    assert payload["rejection_reason"]


def test_upload_pr_lint_gate_runs_before_github_token_check(monkeypatch):
    """W4: the lint gate must fire even when GITHUB_TOKEN is unset. This
    prevents an attacker-pasted bypass from leaking into a 503 response that
    might be misinterpreted as 'safe to retry'."""
    app = _build_app(monkeypatch)
    client = app.test_client()
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    def _tripwire(*args, **kwargs):
        pytest.fail("subprocess.run called before lint hard-reject")

    monkeypatch.setattr(subprocess, "run", _tripwire)

    response = client.post(
        "/api/v1/workbench/upload-pr",
        json={
            "parser_name": "okta_logs-latest",
            "lua_code": 'function processEvent(e) os.execute("id"); return e end',
        },
    )
    # Order is: parser-name validate -> empty-body validate -> lint -> token check.
    # So with dangerous Lua we expect 400/hard_reject regardless of token presence.
    assert response.status_code == 400
    assert response.get_json()["error"] == "hard_reject"
