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
            return [{"parser_name": "okta_logs-latest"}]

        def list_parser_names(self):
            return ["okta_logs-latest"]

        def build_parser(self, parser_name):
            return None

        def build_parser_with_agent(self, parser_name, force_regenerate=False):
            return {"parser_name": parser_name, "lua_code": "function processEvent(event) return event end"}

        def build_from_raw_examples(self, parser_name, raw_examples, force_regenerate=False):
            return {"parser_name": parser_name, "lua_code": "function processEvent(event) return event end"}

        def get_event_generation_strategy(self, parser_name):
            return {"source": "fallback", "jarvis_available": False, "jarvis_match_type": "none", "jarvis_generator_key": ""}

    class FakeHarness:
        def run_all_checks(self, *args, **kwargs):
            return {"confidence_score": 70, "confidence_grade": "C", "checks": {}}

    def _no_auth(fn):
        return fn

    monkeypatch.setenv("WORKBENCH_MAX_SAMPLES", "2")
    monkeypatch.setenv("WORKBENCH_MAX_SAMPLE_CHARS", "10")
    monkeypatch.setenv("WORKBENCH_MAX_TOTAL_SAMPLE_CHARS", "12")
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


def test_rejects_too_many_samples(monkeypatch):
    app = _build_app(monkeypatch)
    client = app.test_client()
    resp = client.post(
        "/api/v1/workbench/jobs",
        json={
            "job_type": "generate_from_samples",
            "payload": {"parser_name": "x", "declared_log_type": "authentication", "declared_log_detail": "okta authentication", "samples": ["a", "b", "c"]},
        },
    )
    assert resp.status_code == 400
    assert "too many samples" in resp.get_json()["error"].lower()


def test_rejects_sample_too_large(monkeypatch):
    app = _build_app(monkeypatch)
    client = app.test_client()
    resp = client.post(
        "/api/v1/workbench/jobs",
        json={
            "job_type": "generate_from_samples",
            "payload": {"parser_name": "x", "declared_log_type": "authentication", "declared_log_detail": "okta authentication", "samples": ["01234567890"]},
        },
    )
    assert resp.status_code == 400
    assert "exceeds max size" in resp.get_json()["error"].lower()


def test_rejects_total_payload_too_large(monkeypatch):
    app = _build_app(monkeypatch)
    client = app.test_client()
    resp = client.post(
        "/api/v1/workbench/jobs",
        json={
            "job_type": "generate_from_samples",
            "payload": {"parser_name": "x", "declared_log_type": "authentication", "declared_log_detail": "okta authentication", "samples": ["0123457", "abcdef"]},
        },
    )
    assert resp.status_code == 400
    assert "total sample payload exceeds max size" in resp.get_json()["error"].lower()


def test_generate_from_samples_requires_declared_log_type(monkeypatch):
    app = _build_app(monkeypatch)
    client = app.test_client()
    resp = client.post(
        "/api/v1/workbench/jobs",
        json={
            "job_type": "generate_from_samples",
            "payload": {"parser_name": "x", "samples": ["abc"]},
        },
    )
    assert resp.status_code == 400
    assert "declared_log_type is required" in resp.get_json()["error"].lower()


def test_generate_from_samples_rejects_invalid_declared_log_type(monkeypatch):
    app = _build_app(monkeypatch)
    client = app.test_client()
    resp = client.post(
        "/api/v1/workbench/jobs",
        json={
            "job_type": "generate_from_samples",
            "payload": {"parser_name": "x", "declared_log_type": "made_up_type", "samples": ["abc"]},
        },
    )
    assert resp.status_code == 400
    assert "must be one of" in resp.get_json()["error"].lower()
