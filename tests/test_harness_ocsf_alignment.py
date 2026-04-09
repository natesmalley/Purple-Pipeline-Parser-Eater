from components.testing_harness.harness_orchestrator import HarnessOrchestrator


def test_ocsf_alignment_report_strong():
    orchestrator = HarnessOrchestrator()

    mapping = {
        "class_uid": 4002,
        "required_coverage": 92.0,
        "missing_required": ["activity_id"],
        "field_details": [
            {"field": "class_uid", "status": "required_present"},
            {"field": "category_uid", "status": "required_present"},
        ],
    }
    report = orchestrator._build_ocsf_alignment_report(mapping)

    assert report["attempted"] is True
    assert report["status"] == "strong"
    assert report["required_total"] == 3
    assert report["required_mapped"] == 2


def test_ocsf_alignment_report_none_when_error():
    orchestrator = HarnessOrchestrator()
    report = orchestrator._build_ocsf_alignment_report({"error": "failure"})
    assert report["attempted"] is False
    assert report["status"] == "none"


def test_confidence_applies_placeholder_and_unmapped_penalties():
    orchestrator = HarnessOrchestrator()
    results = {
        "lua_validity": {"valid": True},
        "lua_linting": {"score": 95},
        "ocsf_mapping": {
            "class_uid": 2004,
            "required_coverage": 95,
            "semantic_signals": {
                "placeholder_count": 2,
                "has_unmapped_bucket": True,
            },
        },
        "field_comparison": {"coverage_pct": 20},
        "test_execution": {"total_events": 4, "passed": 4},
        "source_fields": {"parser_name": "microsoft_365_defender-latest"},
    }

    confidence = orchestrator._compute_confidence(results)
    penalties = confidence["semantic_penalties"]
    assert penalties["total"] == 14
    assert confidence["baseline_score"] > confidence["score"]


def test_confidence_applies_source_class_mismatch_penalty_for_duo():
    orchestrator = HarnessOrchestrator()
    results = {
        "lua_validity": {"valid": True},
        "lua_linting": {"score": 90},
        "ocsf_mapping": {
            "class_uid": 2004,
            "required_coverage": 90,
            "semantic_signals": {"placeholder_count": 0, "has_unmapped_bucket": False},
        },
        "field_comparison": {"coverage_pct": 80},
        "test_execution": {"total_events": 3, "passed": 3},
        "source_fields": {"parser_name": "cisco_duo_logs-latest"},
    }

    confidence = orchestrator._compute_confidence(results)
    details = confidence["semantic_penalties"]["details"]
    assert any(d.get("id") == "source_class_mismatch" for d in details)


def test_ocsf_analyzer_emits_semantic_signals():
    orchestrator = HarnessOrchestrator()
    lua_code = """
function processEvent(event)
  local result = {}
  result.class_uid = 2004
  result.category_uid = 2
  result.activity_id = 99
  result.type_uid = 200499
  result.severity_id = 1
  result.time = 1
  result.finding_title = "Unknown Process"
  result["unmapped.foo"] = event["foo"]
  return result
end
"""
    report = orchestrator.ocsf_analyzer.analyze(lua_code)
    signals = report.get("semantic_signals", {})
    assert signals.get("placeholder_count", 0) >= 1
    assert signals.get("has_unmapped_bucket") is True
