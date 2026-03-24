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


def _build_app(monkeypatch, captured):
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

    class FakeValidity:
        def check(self, lua_code):
            captured["validity_lua"] = lua_code
            return {
                "valid": True,
                "errors": [],
                "warnings": ["compat warning"],
                "function_signature": "processEvent",
            }

    class FakeAnalyzer:
        def analyze(self, lua_code, ocsf_version):
            captured["mapping_version"] = ocsf_version
            return {"class_uid": 1007}

    class FakeRegistry:
        def get_required_fields(self, class_uid, ocsf_version):
            captured["required_query"] = (class_uid, ocsf_version)
            return ["class_uid", "time"]

    class FakeExecution:
        def execute(self, lua_code, test_events, ocsf_required_fields):
            captured["exec_lua"] = lua_code
            captured["exec_events"] = test_events
            captured["exec_required"] = ocsf_required_fields
            return {
                "function_signature": "processEvent",
                "total_events": 1,
                "passed": 1,
                "failed": 0,
                "results": [
                    {
                        "test_name": "playground",
                        "status": "passed",
                        "input_event": test_events[0]["event"],
                        "output_event": {"class_uid": 1007, "time": "now"},
                        "error": None,
                        "execution_time_ms": 1.2,
                        "field_trace": [],
                        "ocsf_validation": {
                            "required_present": ["class_uid", "time"],
                            "required_missing": [],
                            "coverage_pct": 100,
                        },
                    }
                ],
                "lupa_available": True,
            }

    class FakeHarness:
        def __init__(self):
            self.validity_checker = FakeValidity()
            self.ocsf_analyzer = FakeAnalyzer()
            self.ocsf_registry = FakeRegistry()
            self.execution_engine = FakeExecution()

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


def test_playground_execute_uses_posted_lua_and_event(monkeypatch):
    captured = {}
    app = _build_app(monkeypatch, captured)

    response = app.test_client().post(
        "/api/v1/workbench/execute",
        json={
            "parser_name": "agent_metrics_logs-latest",
            "lua_code": "function processEvent(event) return event end",
            "event": {"message": "hello"},
            "ocsf_version": "1.1.0",
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["validation_source"] == "editor_lua"
    assert payload["function_signature"] == "processEvent"
    assert captured["exec_events"][0]["event"] == {"message": "hello"}
    assert captured["required_query"] == (1007, "1.1.0")


def test_playground_execute_falls_back_to_example_event(monkeypatch):
    captured = {}
    app = _build_app(monkeypatch, captured)

    response = app.test_client().post(
        "/api/v1/workbench/execute",
        json={"parser_name": "agent_metrics_logs-latest", "lua_code": "function processEvent(event) return event end"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["validation_source"] == "editor_lua"
    assert captured["exec_events"][0]["event"] == {"message": "from-example"}


def test_playground_execute_requires_parser_name(monkeypatch):
    captured = {}
    app = _build_app(monkeypatch, captured)

    response = app.test_client().post(
        "/api/v1/workbench/execute",
        json={"lua_code": "function processEvent(event) return event end"},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert "parser_name is required" in payload["error"]
