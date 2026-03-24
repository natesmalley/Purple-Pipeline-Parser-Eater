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
