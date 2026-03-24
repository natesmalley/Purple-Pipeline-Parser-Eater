import subprocess

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
