"""FU9.1 regression tests for workbench post-Generate state persistence.

These tests use a REAL ``ParserLuaWorkbench`` (not the FakeWorkbench fakes
elsewhere in the suite) so they exercise the full
``register_generated_entry`` -> ``_load_converted`` -> ``_find_entry`` ->
``lua_for_entry`` chain. The unit block guards the load-bearing
``lua_code`` field; the smaller Flask integration block confirms the five
post-Generate routes plus ``source-fields`` no longer 404 against a
freshly-registered parser.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from flask import Flask

from components.web_ui import routes as routes_module
from components.web_ui.parser_workbench import ParserLuaWorkbench


WRAP_SENTINEL = "[wrap_for_observo]"
INLINE_LUA_BODY = (
    "-- [wrap_for_observo] deploy-ready akamai_cdn_fu7_smoke\n"
    "function process(event, emit)\n"
    "  emit(event)\n"
    "end\n"
)
PARSER_NAME = "akamai_cdn_fu7_smoke"


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #


def _make_workbench(tmp_path: Path) -> ParserLuaWorkbench:
    (tmp_path / "output").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "state").mkdir(parents=True, exist_ok=True)
    return ParserLuaWorkbench(repo_root=tmp_path)


def _make_generated_result(parser_name: str = PARSER_NAME) -> dict:
    return {
        "parser_name": parser_name,
        "ingestion_mode": "push",
        "lua_code": INLINE_LUA_BODY,
        "lua_file": f"output/parser_lua_serializers/{parser_name}.lua",
        "ocsf_class": "HTTP Activity",
        "confidence_score": 99,
        "confidence_grade": "A",
        "accepted": True,
        "rejection_reason": None,
    }


# --------------------------------------------------------------------------- #
# Unit tests (real ParserLuaWorkbench)                                         #
# --------------------------------------------------------------------------- #


def test_register_creates_state_file(tmp_path: Path) -> None:
    """Test 4: state file written with the expected entry."""
    wb = _make_workbench(tmp_path)
    wb.register_generated_entry(
        _make_generated_result(),
        raw_examples=["AkamaiCDN reqMethod=\"GET\" hostname=\"example.com\""],
        declared_log_type="HTTP Activity",
        declared_log_detail=None,
    )
    state_path = tmp_path / "data" / "state" / "workbench_generated.json"
    assert state_path.exists(), "workbench_generated.json must be created"
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload.get("version") == 1
    rows = payload.get("generated", [])
    assert isinstance(rows, list) and len(rows) == 1
    row = rows[0]
    assert row["parser_name"] == PARSER_NAME
    assert row["lua_code"] == INLINE_LUA_BODY
    assert row["confidence_score"] == 99
    assert row["source"] == "workbench"
    assert "generated_at" in row


def test_find_entry_returns_workbench_row(tmp_path: Path) -> None:
    """Test 5: _find_entry finds the workbench-state row."""
    wb = _make_workbench(tmp_path)
    wb.register_generated_entry(
        _make_generated_result(),
        raw_examples=["raw"],
        declared_log_type=None,
        declared_log_detail=None,
    )
    entry = wb._find_entry(PARSER_NAME)
    assert entry is not None
    assert entry["parser_name"] == PARSER_NAME
    assert entry["lua_code"] == INLINE_LUA_BODY


def test_lua_for_entry_returns_inline_lua_with_sentinel(tmp_path: Path) -> None:
    """Test 6 (LOAD-BEARING): inline lua_code returned, NOT the
    GENERIC_EXTRACTION_LUA fallback. Sentinel substring is the explicit
    guard against the schema's lua_code field being silently ignored."""
    wb = _make_workbench(tmp_path)
    wb.register_generated_entry(
        _make_generated_result(),
        raw_examples=["raw"],
        declared_log_type=None,
        declared_log_detail=None,
    )
    entry = wb._find_entry(PARSER_NAME)
    assert entry is not None
    body = wb.lua_for_entry(entry)
    assert body.startswith("-- [wrap_for_observo]"), (
        "lua_for_entry must return the inline lua_code, not GENERIC_EXTRACTION_LUA"
    )
    assert body == INLINE_LUA_BODY


def test_lua_for_entry_request_lua_returned_verbatim(tmp_path: Path) -> None:
    """Test 7: request_lua wins over inline AND is returned AS-IS (not wrapped).
    Locks the editor-Lua-verbatim contract for Validate / Playground."""
    wb = _make_workbench(tmp_path)
    wb.register_generated_entry(
        _make_generated_result(),
        raw_examples=["raw"],
        declared_log_type=None,
        declared_log_detail=None,
    )
    entry = wb._find_entry(PARSER_NAME)
    assert entry is not None
    request_lua = "function processEvent(event) return event end"
    out = wb.lua_for_entry(entry, request_lua=request_lua)
    assert out == request_lua, "request_lua must be returned verbatim, not wrapped"
    assert WRAP_SENTINEL not in out, "request_lua must not be auto-wrapped"


def test_curated_wins_on_collision(tmp_path: Path) -> None:
    """Test 8 (NEGATIVE): curated entry wins on parser_name collision so
    workbench experimentation cannot shadow real curated entries."""
    wb = _make_workbench(tmp_path)
    # Curated entry with same parser_name + a known processing_profile body.
    curated_script = "-- curated processEvent body\nfunction processEvent(event) return event end"
    curated_entry = {
        "parser_name": PARSER_NAME,
        "ingestion_mode": "push",
        "processing_profile": {
            "serialization_components": [
                {
                    "config": {
                        "config_groups": [
                            {"script": curated_script}
                        ]
                    }
                }
            ]
        },
    }
    (tmp_path / "output").mkdir(parents=True, exist_ok=True)
    (tmp_path / "output" / "ai_siem_parser_source_components.json").write_text(
        json.dumps({"converted": [curated_entry]}),
        encoding="utf-8",
    )

    # Now register a workbench entry with the SAME name.
    wb.register_generated_entry(
        _make_generated_result(),
        raw_examples=["raw"],
        declared_log_type=None,
        declared_log_detail=None,
    )

    # Curated must win.
    entry = wb._find_entry(PARSER_NAME)
    assert entry is not None
    assert entry.get("processing_profile") is not None
    assert entry.get("source") != "workbench"

    # lua_for_entry on the curated entry returns curated body, not workbench.
    body = wb.lua_for_entry(entry)
    assert curated_script in body
    assert INLINE_LUA_BODY not in body


def test_lua_for_entry_curated_branch_is_wrapped(tmp_path: Path) -> None:
    """Test 9: when lua_code is empty/absent but processing_profile resolves
    to a known body via build_lua_content, the curated branch keeps wrap
    behavior (build_lua_content calls ensure_wrapped internally)."""
    wb = _make_workbench(tmp_path)
    curated_script = "-- curated body\nfunction processEvent(event) return event end"
    entry = {
        "parser_name": "curated_only",
        "ingestion_mode": "push",
        "processing_profile": {
            "serialization_components": [
                {
                    "config": {
                        "config_groups": [
                            {"script": curated_script}
                        ]
                    }
                }
            ]
        },
        # lua_code intentionally absent
    }
    body = wb.lua_for_entry(entry)
    assert WRAP_SENTINEL in body, (
        "curated branch must keep build_lua_content -> ensure_wrapped wrap"
    )


def test_register_replaces_prior_row_with_same_name(tmp_path: Path) -> None:
    """Re-registering the same parser_name overwrites — at most 1 row each."""
    wb = _make_workbench(tmp_path)
    wb.register_generated_entry(
        _make_generated_result(),
        raw_examples=["raw1"],
        declared_log_type=None,
        declared_log_detail=None,
    )
    second = _make_generated_result()
    second["confidence_score"] = 75
    second["lua_code"] = "-- [wrap_for_observo] second\nfunction process(e,emit) emit(e) end"
    wb.register_generated_entry(
        second,
        raw_examples=["raw2"],
        declared_log_type=None,
        declared_log_detail=None,
    )
    state = json.loads((tmp_path / "data" / "state" / "workbench_generated.json").read_text())
    rows = state["generated"]
    assert len(rows) == 1
    assert rows[0]["confidence_score"] == 75
    assert rows[0]["lua_code"].startswith("-- [wrap_for_observo] second")


def test_register_skips_entries_without_parser_name(tmp_path: Path) -> None:
    wb = _make_workbench(tmp_path)
    wb.register_generated_entry(
        {"lua_code": "ignored", "accepted": True},
        raw_examples=[],
        declared_log_type=None,
        declared_log_detail=None,
    )
    assert not (tmp_path / "data" / "state" / "workbench_generated.json").exists()


def test_load_converted_falls_back_to_curated_on_workbench_parse_error(tmp_path: Path) -> None:
    """Fail-closed merge: bad workbench-state JSON returns curated-only."""
    wb = _make_workbench(tmp_path)
    (tmp_path / "output" / "ai_siem_parser_source_components.json").write_text(
        json.dumps({"converted": [{"parser_name": "curated_a", "ingestion_mode": "push"}]}),
        encoding="utf-8",
    )
    (tmp_path / "data" / "state" / "workbench_generated.json").write_text(
        "not valid json {{{",
        encoding="utf-8",
    )
    rows = wb._load_converted()
    assert any(r.get("parser_name") == "curated_a" for r in rows)


# --------------------------------------------------------------------------- #
# Flask integration (5 routes + source-fields return 200 not 404)             #
# --------------------------------------------------------------------------- #


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


def _build_app_with_real_workbench(monkeypatch, tmp_path: Path):
    """Use a real ParserLuaWorkbench (constructed by routes_module via
    monkey-patched factory) so the integration block exercises the merged
    _load_converted path. The harness is faked so it returns a benign result."""

    real_wb = _make_workbench(tmp_path)
    real_wb.register_generated_entry(
        _make_generated_result(),
        raw_examples=["AkamaiCDN reqMethod=\"GET\""],
        declared_log_type="HTTP Activity",
        declared_log_detail=None,
    )

    def _wb_factory(*args, **kwargs):
        return real_wb

    class FakeHarness:
        def run_all_checks(self, lua_code, parser_config, ocsf_version="1.3.0", custom_test_events=None):
            return {
                "confidence_score": 80,
                "confidence_grade": "B",
                "elapsed_seconds": 0.01,
                "check_summary": {
                    "lua_validity": "passed",
                    "lua_linting": "good",
                    "ocsf_mapping": "fair",
                    "field_comparison": "good",
                    "test_execution": "passed",
                },
                "checks": {"test_execution": {"per_event": []}},
            }

        def run_single_check(self, check_name, lua_code, parser_config=None, ocsf_version="1.3.0"):
            return {"check": check_name, "status": "passed"}

        class _Validity:
            def check(self, lua_code):
                return {"valid": True, "errors": [], "warnings": [], "function_signature": None}

        class _Analyzer:
            def analyze(self, lua_code, ocsf_version):
                return {"class_uid": 4002, "found_fields": [], "missing_fields": []}

        class _Registry:
            def get_required_fields(self, class_uid, ocsf_version):
                return []

        class _Engine:
            def execute(self, lua_code, test_events, ocsf_required_fields=None):
                return {"events_passed": 1, "events_total": 1, "per_event_results": []}

        validity_checker = _Validity()
        ocsf_analyzer = _Analyzer()
        ocsf_registry = _Registry()
        execution_engine = _Engine()

    def _no_auth(fn):
        return fn

    monkeypatch.setattr(routes_module, "ParserLuaWorkbench", _wb_factory)
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


def test_validate_route_returns_200_for_workbench_generated(monkeypatch, tmp_path):
    app = _build_app_with_real_workbench(monkeypatch, tmp_path)
    client = app.test_client()
    response = client.post(
        f"/api/v1/workbench/validate/{PARSER_NAME}",
        json={},
    )
    assert response.status_code == 200, response.get_data(as_text=True)


def test_lint_route_returns_200_for_workbench_generated(monkeypatch, tmp_path):
    app = _build_app_with_real_workbench(monkeypatch, tmp_path)
    client = app.test_client()
    response = client.get(f"/api/v1/workbench/lint/{PARSER_NAME}")
    assert response.status_code == 200, response.get_data(as_text=True)


def test_ocsf_mapping_route_returns_200_for_workbench_generated(monkeypatch, tmp_path):
    app = _build_app_with_real_workbench(monkeypatch, tmp_path)
    client = app.test_client()
    response = client.get(f"/api/v1/workbench/ocsf-mapping/{PARSER_NAME}")
    assert response.status_code == 200, response.get_data(as_text=True)


def test_source_fields_route_returns_200_for_workbench_generated(monkeypatch, tmp_path):
    app = _build_app_with_real_workbench(monkeypatch, tmp_path)
    client = app.test_client()
    response = client.get(f"/api/v1/workbench/source-fields/{PARSER_NAME}")
    assert response.status_code == 200, response.get_data(as_text=True)


def test_test_run_route_returns_200_for_workbench_generated(monkeypatch, tmp_path):
    app = _build_app_with_real_workbench(monkeypatch, tmp_path)
    client = app.test_client()
    response = client.post(
        f"/api/v1/workbench/test-run/{PARSER_NAME}",
        json={"test_events": [{"event": {"foo": "bar"}}]},
    )
    assert response.status_code == 200, response.get_data(as_text=True)


def test_execute_route_returns_200_for_workbench_generated(monkeypatch, tmp_path):
    app = _build_app_with_real_workbench(monkeypatch, tmp_path)
    client = app.test_client()
    response = client.post(
        "/api/v1/workbench/execute",
        json={
            "parser_name": PARSER_NAME,
            "event": {"foo": "bar"},
        },
    )
    assert response.status_code == 200, response.get_data(as_text=True)
