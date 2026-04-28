"""Tests for the 2026-04-19 harness quality improvements:

1. Generalized ``source_class_mismatch`` penalty — fires whenever parser
   keywords clearly imply one OCSF class but the script sets another.
2. Timestamp-type fuzzing in ``DualExecutionEngine`` — re-runs each test
   event with ``timestamp`` coerced to a number and missing, catching
   scripts that call ``:match(...)`` on a value that might not be a string.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from components.testing_harness.dual_execution_engine import DualExecutionEngine
from components.testing_harness.harness_orchestrator import HarnessOrchestrator


REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = REPO_ROOT / "data" / "regression_fixtures" / "marco_2026_04_08"


# ---------------------------------------------------------------------------
# Classification cross-check
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def orchestrator() -> HarnessOrchestrator:
    return HarnessOrchestrator()


def test_infer_expected_class_uid_from_metadata_returns_http_for_akamai_cdn(orchestrator):
    expected = orchestrator._infer_expected_class_uid_from_metadata(
        {"parser_name": "akamai_cdn-latest", "vendor": "akamai", "product": "akamai_cdn"}
    )
    assert expected == 4002


def test_infer_expected_class_uid_returns_dns_for_akamai_dns(orchestrator):
    expected = orchestrator._infer_expected_class_uid_from_metadata(
        {"parser_name": "akamai_dns-latest", "vendor": "akamai", "product": "akamai_dns"}
    )
    assert expected == 4003


def test_infer_expected_class_uid_returns_auth_for_okta(orchestrator):
    expected = orchestrator._infer_expected_class_uid_from_metadata(
        {"parser_name": "okta_logs-latest", "vendor": "okta", "product": "identity"}
    )
    assert expected == 3002


def test_infer_expected_class_uid_none_when_ambiguous(orchestrator):
    # "generic_parser" has no class keywords — should return None (not guess)
    assert orchestrator._infer_expected_class_uid_from_metadata(
        {"parser_name": "generic_parser", "vendor": "", "product": ""}
    ) is None


def test_akamai_cdn_classification_mismatch_now_penalized(orchestrator):
    """The Akamai CDN script sets class_uid 2004 (Detection Finding), but
    parser keywords suggest 4002 (HTTP Activity). The generalized
    ``source_class_mismatch`` penalty should now fire, dropping the grade.
    """
    case_dir = FIXTURE_ROOT / "akamai_cdn"
    report = orchestrator.run_all_checks(
        lua_code=(case_dir / "generated.lua").read_text(),
        parser_config=json.loads((case_dir / "parser_config.json").read_text()),
        custom_test_events=[{"name": "cdn", "event": json.loads((case_dir / "sample.json").read_text())}],
    )
    # F grade means we're correctly penalizing the misclassification.
    assert report.get("confidence_grade") == "F"
    # Score should be noticeably below the pre-check score of 68.
    assert report.get("confidence_score") <= 60


# ---------------------------------------------------------------------------
# Timestamp-type fuzz
# ---------------------------------------------------------------------------

UNGUARDED_TIMESTAMP_LUA = """
function processEvent(event)
    local ts = event.timestamp
    local result = { class_uid = 3002, category_uid = 3 }
    if ts then
        -- No type guard — crashes if ts is a number or missing
        local y, m, d = ts:match("(%d+)-(%d+)-(%d+)")
        result.year = tonumber(y or 0)
    end
    return result
end
"""

GUARDED_TIMESTAMP_LUA = """
function processEvent(event)
    local ts = tostring(event.timestamp or "")
    local result = { class_uid = 3002, category_uid = 3 }
    if ts ~= "" then
        local y, m, d = ts:match("(%d+)-(%d+)-(%d+)")
        result.year = tonumber(y or 0)
    end
    return result
end
"""


@pytest.fixture(scope="module")
def engine() -> DualExecutionEngine:
    return DualExecutionEngine()


def test_fuzz_exposes_unguarded_timestamp_match(engine):
    test_events = [{"name": "happy", "event": {"timestamp": "2026-04-08T10:00:00Z"}}]
    report = engine.execute(UNGUARDED_TIMESTAMP_LUA, test_events)
    # Happy path should pass — the sample is a string.
    assert report["passed"] == 1
    # Fuzz pass should run 2 variants and fail the numeric one.
    fuzz = report.get("timestamp_fuzz") or {}
    assert fuzz.get("total") == 2
    assert fuzz.get("failed") >= 1


def test_fuzz_clean_for_guarded_timestamp(engine):
    test_events = [{"name": "happy", "event": {"timestamp": "2026-04-08T10:00:00Z"}}]
    report = engine.execute(GUARDED_TIMESTAMP_LUA, test_events)
    fuzz = report.get("timestamp_fuzz") or {}
    # Both variants should pass because the script coerces to string.
    assert fuzz.get("total") == 2
    assert fuzz.get("passed") == 2


def test_fuzz_skipped_when_no_timestamp_field(engine):
    """If the event has no timestamp / Timestamp / time field, no fuzz runs."""
    test_events = [{"name": "happy", "event": {"foo": "bar"}}]
    report = engine.execute(GUARDED_TIMESTAMP_LUA, test_events)
    fuzz = report.get("timestamp_fuzz") or {}
    assert fuzz.get("total") == 0


def test_fuzz_surfaces_akamai_dns_production_bug(engine):
    case_dir = FIXTURE_ROOT / "akamai_dns"
    sample = json.loads((case_dir / "sample.json").read_text())
    lua = (case_dir / "generated.lua").read_text()
    report = engine.execute(lua, [{"name": "akamai_dns", "event": sample}])
    fuzz = report.get("timestamp_fuzz") or {}
    assert fuzz.get("total") == 2
    # At least one fuzz variant should fail — this is Marco's production bug.
    assert fuzz.get("failed") >= 1
    lua_errors = [
        (r.get("output_event") or {}).get("lua_error")
        for r in fuzz.get("results", [])
    ]
    lua_errors = [e for e in lua_errors if e]
    assert any("match" in e.lower() or "number value" in e.lower() for e in lua_errors)
