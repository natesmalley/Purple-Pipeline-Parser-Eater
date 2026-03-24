import json

import pytest

from components.testing_harness.harness_dataset import HarnessDatasetLoader, iter_case_events


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_loads_dataset_with_deterministic_case_ordering(tmp_path):
    dataset_dir = tmp_path / "auth_dataset"
    cases_dir = dataset_dir / "cases"
    cases_dir.mkdir(parents=True)

    _write_json(
        dataset_dir / "metadata.json",
        {
            "dataset_id": "auth_login_dataset",
            "parser_name": "okta_log_collector",
            "vendor": "Okta",
            "product": "System Log",
            "description": "Authentication dataset",
            "source": "unit-test",
        },
    )

    # Intentionally written out of order; loader order must be filename-sorted.
    _write_json(
        cases_dir / "020-error.json",
        {
            "case_id": "error_case",
            "event": {"timestamp": "2025-01-01T00:00:02Z", "status": "failed"},
            "expected_behavior": "Should handle invalid login",
        },
    )
    _write_json(
        cases_dir / "010-happy.json",
        {
            "case_id": "happy_case",
            "event": {"timestamp": "2025-01-01T00:00:01Z", "status": "success"},
            "expected_behavior": "Should map successful login",
        },
    )

    dataset = HarnessDatasetLoader().load_from_dir(dataset_dir)

    assert dataset.metadata.dataset_id == "auth_login_dataset"
    assert dataset.metadata.parser_name == "okta_log_collector"
    assert dataset.ordered_case_ids() == ("happy_case", "error_case")

    events = list(iter_case_events(dataset))
    assert events[0]["status"] == "success"
    assert events[1]["status"] == "failed"


def test_requires_metadata_file(tmp_path):
    dataset_dir = tmp_path / "missing_metadata"
    (dataset_dir / "cases").mkdir(parents=True)

    _write_json(
        dataset_dir / "cases" / "010-case.json",
        {"case_id": "only_case", "event": {"message": "hello"}},
    )

    with pytest.raises(ValueError, match="Missing dataset metadata file"):
        HarnessDatasetLoader().load_from_dir(dataset_dir)


def test_rejects_duplicate_case_id(tmp_path):
    dataset_dir = tmp_path / "duplicate_cases"
    cases_dir = dataset_dir / "cases"
    cases_dir.mkdir(parents=True)

    _write_json(
        dataset_dir / "metadata.json",
        {"dataset_id": "dataset_x", "parser_name": "parser_x"},
    )

    _write_json(cases_dir / "010-a.json", {"case_id": "dup", "event": {"a": 1}})
    _write_json(cases_dir / "020-b.json", {"case_id": "dup", "event": {"b": 2}})

    with pytest.raises(ValueError, match="Duplicate case_id"):
        HarnessDatasetLoader().load_from_dir(dataset_dir)
