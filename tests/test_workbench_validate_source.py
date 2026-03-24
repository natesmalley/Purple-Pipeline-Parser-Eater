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


def _register_with_fakes(monkeypatch, captured):
    class FakeWorkbench:
        def _find_entry(self, parser_name):
            return {"parser_name": parser_name, "config": {"id": parser_name}}

        def list_parsers(self):
            return []

        def build_parser(self, parser_name):
            return None

        def build_parser_with_agent(self, parser_name, force_regenerate=False):
            return None

        def _get_agent(self):
            return None

    class FakeHarness:
        def run_all_checks(self, lua_code, parser_config, ocsf_version="1.3.0", custom_test_events=None):
            captured["lua_code"] = lua_code
            captured["ocsf_version"] = ocsf_version
            return {
                "confidence_score": 70,
                "confidence_grade": "C",
                "elapsed_seconds": 0.01,
                "check_summary": {
                    "lua_validity": "passed",
                    "lua_linting": "good",
                    "ocsf_mapping": "fair",
                    "field_comparison": "good",
                    "test_execution": "passed",
                },
                "checks": {},
            }

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


def test_validate_post_uses_editor_lua(monkeypatch):
    captured = {}
    app = _register_with_fakes(monkeypatch, captured)

    client = app.test_client()
    response = client.post(
        "/api/v1/workbench/validate/agent_metrics_logs-latest",
        json={"ocsf_version": "1.1.0", "lua_code": "function processEvent(event) return event end"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["validation_source"] == "editor_lua"
    assert captured["lua_code"] == "function processEvent(event) return event end"
    assert captured["ocsf_version"] == "1.1.0"
    assert "sample_provenance" in payload
    assert "runtime_test_source" in payload["sample_provenance"]


def test_validate_get_uses_baseline_parser_lua(monkeypatch):
    captured = {}

    def fake_build_lua_content(entry):
        return {"content": "function processEvent(event) return event end"}

    monkeypatch.setattr("components.lua_exporter.build_lua_content", fake_build_lua_content)
    app = _register_with_fakes(monkeypatch, captured)

    client = app.test_client()
    response = client.get(
        "/api/v1/workbench/validate/agent_metrics_logs-latest?ocsf_version=1.3.0"
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["validation_source"] == "baseline_parser_lua"
    assert captured["lua_code"] == "function processEvent(event) return event end"
    assert captured["ocsf_version"] == "1.3.0"
    assert "sample_provenance" in payload
