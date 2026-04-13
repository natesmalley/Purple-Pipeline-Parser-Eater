import time
import json

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
    return _build_app_with_known_parsers(monkeypatch, ["okta_logs-latest"])


def _build_app_with_known_parsers(monkeypatch, known_parsers, harness_cls=None):
    class FakeWorkbench:
        def _find_entry(self, parser_name):
            return {"parser_name": parser_name, "config": {"parser_name": parser_name}}

        def list_parsers(self):
            return [{"parser_name": name} for name in known_parsers]

        def list_parser_names(self):
            return list(known_parsers)

        def build_parser(self, parser_name):
            return {"parser_name": parser_name, "lua_code": "function processEvent(event) return event end"}

        def build_parser_with_agent(self, parser_name, force_regenerate=False):
            return {
                "parser_name": parser_name,
                "lua_code": "function processEvent(event) return event end",
                "confidence_score": 86,
                "confidence_grade": "B",
                "iterations": 1,
                "harness_report": {"ocsf_alignment": {"status": "partial"}},
            }

        def build_from_raw_examples(self, parser_name, raw_examples, force_regenerate=False):
            return {
                "parser_name": parser_name,
                "lua_code": "function processEvent(event) return event end",
                "confidence_score": 78,
                "confidence_grade": "C",
            }

        def get_event_generation_strategy(self, parser_name):
            return {
                "source": "jarvis",
                "jarvis_available": True,
                "jarvis_match_type": "alias",
                "jarvis_generator_key": "okta_authentication",
            }

        def _get_agent(self):
            return object()

    class FakeHarness:
        def run_all_checks(self, lua_code, parser_config, ocsf_version="1.3.0", custom_test_events=None):
            return {
                "confidence_score": 75,
                "confidence_grade": "C",
                "ocsf_alignment": {"status": "partial", "attempted": True},
                "checks": {},
            }

    def _no_auth(fn):
        return fn

    monkeypatch.setattr(routes_module, "ParserLuaWorkbench", FakeWorkbench)
    monkeypatch.setattr(routes_module, "HarnessOrchestrator", harness_cls or FakeHarness)

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


def _wait_for_completion(client, job_id):
    deadline = time.time() + 2.0
    last_payload = None
    while time.time() < deadline:
        response = client.get(f"/api/v1/workbench/jobs/{job_id}")
        assert response.status_code == 200
        payload = response.get_json()
        last_payload = payload
        if payload["status"] in ("completed", "failed"):
            return payload
        time.sleep(0.05)
    return last_payload


def test_workbench_jobs_batch_known_parsers(monkeypatch):
    app = _build_app(monkeypatch)
    client = app.test_client()
    response = client.post(
        "/api/v1/workbench/jobs",
        json={"job_type": "batch_known_parsers", "payload": {"threshold": 70}},
    )
    assert response.status_code == 202
    payload = response.get_json()
    job = _wait_for_completion(client, payload["job_id"])
    assert job["status"] == "completed"
    assert job["result"]["summary"]["total"] == 1
    assert job["result"]["parsers"][0]["sample_provenance"]["jarvis_match_type"] == "alias"


def test_workbench_agent_build_backfills_detailed_harness_report(monkeypatch):
    app = _build_app(monkeypatch)
    client = app.test_client()
    response = client.post(
        "/api/v1/workbench/agent-build",
        json={"parser_name": "okta_logs-latest"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert "harness_report" in payload
    assert "checks" in payload["harness_report"]
    assert payload["confidence_score"] == 75
    assert payload["confidence_grade"] == "C"


def test_workbench_jobs_known_parser_from_examples(monkeypatch):
    app = _build_app(monkeypatch)
    client = app.test_client()
    response = client.post(
        "/api/v1/workbench/jobs",
        json={
            "job_type": "known_parser_from_examples",
            "payload": {
                "parser_name": "okta_logs-latest",
                "samples": ["{\"message\":\"sample\"}"],
            },
        },
    )
    assert response.status_code == 202
    payload = response.get_json()
    job = _wait_for_completion(client, payload["job_id"])
    assert job["status"] == "completed"
    assert job["result"]["raw_examples_count"] == 1
    assert "generated_lua" in job["result"]
    assert "sample_provenance" in job["result"]


def test_workbench_jobs_new_parser_from_raw(monkeypatch):
    app = _build_app(monkeypatch)
    client = app.test_client()
    response = client.post(
        "/api/v1/workbench/jobs",
        json={
            "job_type": "new_parser_from_raw",
            "payload": {
                "parser_name": "custom_from_raw",
                "samples": ["raw log line"],
            },
        },
    )
    assert response.status_code == 202
    payload = response.get_json()
    job = _wait_for_completion(client, payload["job_id"])
    assert job["status"] == "completed"
    assert job["result"]["parser_name"] == "custom_from_raw"


def test_new_parser_job_passes_raw_examples_into_parser_config(monkeypatch):
    class CaptureHarness:
        last_parser_config = None

        def run_all_checks(self, lua_code, parser_config, ocsf_version="1.3.0", custom_test_events=None):
            CaptureHarness.last_parser_config = parser_config
            return {
                "confidence_score": 75,
                "confidence_grade": "C",
                "ocsf_alignment": {"status": "partial", "attempted": True},
                "checks": {},
            }

    app = _build_app_with_known_parsers(monkeypatch, ["okta_logs-latest"], harness_cls=CaptureHarness)
    client = app.test_client()
    sample = '{"message":"reqMethod=\\"GET\\" reqPath=\\"/health\\" statusCode=200"}'
    response = client.post(
        "/api/v1/workbench/jobs",
        json={
            "job_type": "new_parser_from_raw",
            "payload": {
                "parser_name": "custom_from_raw",
                "samples": [sample],
            },
        },
    )
    assert response.status_code == 202
    payload = response.get_json()
    job = _wait_for_completion(client, payload["job_id"])
    assert job["status"] == "completed"
    assert CaptureHarness.last_parser_config is not None
    assert CaptureHarness.last_parser_config.get("raw_examples") == [sample]


def test_workbench_jobs_rejects_unknown_type(monkeypatch):
    app = _build_app(monkeypatch)
    client = app.test_client()
    response = client.post("/api/v1/workbench/jobs", json={"job_type": "unknown", "payload": {}})
    assert response.status_code == 400


def test_workbench_jobs_rejects_non_text_samples(monkeypatch):
    app = _build_app(monkeypatch)
    client = app.test_client()
    response = client.post(
        "/api/v1/workbench/jobs",
        json={
            "job_type": "new_parser_from_raw",
            "payload": {"parser_name": "custom", "samples": [{"not": "text"}]},
        },
    )
    assert response.status_code == 400
    assert "text sample" in response.get_json()["error"].lower()


def test_generate_from_samples_auto_detects_known_parser(monkeypatch):
    app = _build_app(monkeypatch)
    client = app.test_client()
    response = client.post(
        "/api/v1/workbench/jobs",
        json={
            "job_type": "generate_from_samples",
            "payload": {"parser_name": "okta_logs-latest", "samples": ["raw sample"]},
        },
    )
    assert response.status_code == 202
    payload = response.get_json()
    assert payload["job_type"] == "known_parser_from_examples"


def test_generate_from_samples_auto_detects_new_parser(monkeypatch):
    app = _build_app(monkeypatch)
    client = app.test_client()
    response = client.post(
        "/api/v1/workbench/jobs",
        json={
            "job_type": "generate_from_samples",
            "payload": {"parser_name": "brand_new_parser", "samples": ["raw sample"]},
        },
    )
    assert response.status_code == 202
    payload = response.get_json()
    assert payload["job_type"] == "new_parser_from_raw"


def test_generate_from_samples_infers_known_parser_from_content(monkeypatch):
    app = _build_app(monkeypatch)
    client = app.test_client()
    response = client.post(
        "/api/v1/workbench/jobs",
        json={
            "job_type": "generate_from_samples",
            "payload": {
                "parser_name": "uuid_sample_20260323",
                "samples": [
                    "{\"eventType\":\"user.session.start\",\"vendor\":\"okta\",\"actor\":{\"type\":\"User\"}}"
                ],
            },
        },
    )
    assert response.status_code == 202
    payload = response.get_json()
    assert payload["job_type"] == "known_parser_from_examples"
    assert payload["resolved_parser_name"] == "okta_logs-latest"
    assert payload["inferred_parser_match"] is True
    assert "high-signal sample fields" in payload["inference_reason"]
    assert "okta" in payload["inference_signals"]


def test_generate_from_samples_okta_inference_end_to_end(monkeypatch):
    app = _build_app(monkeypatch)
    client = app.test_client()
    response = client.post(
        "/api/v1/workbench/jobs",
        json={
            "job_type": "generate_from_samples",
            "payload": {
                "parser_name": "custom_auth_parser",
                "samples": [
                    "{\"eventType\":\"user.session.start\",\"displayMessage\":\"User login to Okta\",\"vendor\":\"okta\",\"actor\":{\"type\":\"User\"}}"
                ],
            },
        },
    )
    assert response.status_code == 202
    payload = response.get_json()
    assert payload["job_type"] == "known_parser_from_examples"
    assert payload["resolved_parser_name"] == "okta_logs-latest"

    job = _wait_for_completion(client, payload["job_id"])
    assert job["status"] == "completed"
    assert job["result"]["parser_name"] == "okta_logs-latest"


def test_generate_from_samples_infers_complex_datasource_end_to_end(monkeypatch):
    app = _build_app_with_known_parsers(
        monkeypatch,
        ["okta_logs-latest", "cloudflare_inc_waf-lastest"],
    )
    client = app.test_client()
    response = client.post(
        "/api/v1/workbench/jobs",
        json={
            "job_type": "generate_from_samples",
            "payload": {
                "parser_name": "custom_waf_parser",
                "samples": [
                    "{\"vendor\":\"cloudflare\",\"product\":\"inc_waf\",\"eventType\":\"http.request.blocked\",\"client\":{\"ipAddress\":\"203.0.113.10\"},\"http\":{\"request\":{\"method\":\"GET\"}},\"outcome\":{\"result\":\"SUCCESS\"}}"
                ],
            },
        },
    )
    assert response.status_code == 202
    payload = response.get_json()
    assert payload["job_type"] == "known_parser_from_examples"
    assert payload["resolved_parser_name"] == "cloudflare_inc_waf-lastest"

    job = _wait_for_completion(client, payload["job_id"])
    assert job["status"] == "completed"
    assert job["result"]["parser_name"] == "cloudflare_inc_waf-lastest"


def test_generate_from_samples_does_not_infer_windows_from_user_agent_noise(monkeypatch):
    app = _build_app_with_known_parsers(
        monkeypatch,
        ["okta_logs-latest", "windows_event_log_logs-latest"],
    )
    client = app.test_client()
    response = client.post(
        "/api/v1/workbench/jobs",
        json={
            "job_type": "generate_from_samples",
            "payload": {
                "parser_name": "custom_parser_user_signin_new_device",
                "samples": [
                    "{\"event_type\":\"user.signin.attempt\",\"client\":{\"user_agent\":\"Mozilla/5.0 (Windows NT 10.0)\"},\"outcome\":{\"result\":\"failure\"},\"authentication\":{\"method\":\"password\",\"mfa_required\":true}}"
                ],
            },
        },
    )
    assert response.status_code == 202
    payload = response.get_json()
    assert payload["job_type"] == "new_parser_from_raw"
    assert payload["resolved_parser_name"] == "custom_parser_user_signin_new_device"


def test_workbench_match_feedback_records_vote(monkeypatch, tmp_path):
    feedback_log = tmp_path / "workbench_match_feedback.jsonl"
    monkeypatch.setenv("PPPE_MATCH_FEEDBACK_LOG", str(feedback_log))

    app = _build_app(monkeypatch)
    client = app.test_client()
    response = client.post(
        "/api/v1/workbench/match-feedback",
        json={
            "parser_name": "okta_logs-latest",
            "submitted_parser_name": "custom_parser",
            "vote": "down",
            "sample_provenance": {"source": "fallback", "jarvis_match_type": "none"},
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "recorded"
    assert feedback_log.exists()

    lines = feedback_log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["parser_name"] == "okta_logs-latest"
    assert record["submitted_parser_name"] == "custom_parser"
    assert record["vote"] == "down"


def test_workbench_match_feedback_rejects_invalid_vote(monkeypatch):
    app = _build_app(monkeypatch)
    client = app.test_client()
    response = client.post(
        "/api/v1/workbench/match-feedback",
        json={"parser_name": "okta_logs-latest", "vote": "maybe"},
    )
    assert response.status_code == 400
    assert "up, down" in response.get_json()["error"]
