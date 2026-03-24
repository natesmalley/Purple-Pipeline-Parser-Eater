import json

from components.testing_harness.harness_cli import main


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _make_dataset(tmp_path):
    dataset_dir = tmp_path / "sample_dataset"
    cases_dir = dataset_dir / "cases"
    cases_dir.mkdir(parents=True)

    _write_json(
        dataset_dir / "metadata.json",
        {
            "dataset_id": "dataset_1",
            "parser_name": "okta_log_collector",
            "vendor": "Okta",
            "product": "System Log",
            "source": "smoke-test",
        },
    )

    _write_json(
        cases_dir / "020-error.json",
        {
            "case_id": "error_case",
            "name": "Error",
            "event": {"status": "failed"},
            "expected_behavior": "Handle error",
        },
    )
    _write_json(
        cases_dir / "010-happy.json",
        {
            "case_id": "happy_case",
            "name": "Happy",
            "event": {"status": "ok"},
            "expected_behavior": "Handle success",
        },
    )

    return dataset_dir


def test_cli_summary_smoke(tmp_path, capsys):
    dataset_dir = _make_dataset(tmp_path)

    rc = main(["--dataset-dir", str(dataset_dir)])
    out = capsys.readouterr().out

    assert rc == 0
    payload = json.loads(out)
    assert payload["dataset_id"] == "dataset_1"
    assert payload["case_count"] == 2
    assert payload["case_ids"] == ["happy_case", "error_case"]


def test_cli_list_cases_smoke(tmp_path, capsys):
    dataset_dir = _make_dataset(tmp_path)

    rc = main(["--dataset-dir", str(dataset_dir), "--list-cases"])
    out = capsys.readouterr().out

    assert rc == 0
    rows = json.loads(out)
    assert [row["case_id"] for row in rows] == ["happy_case", "error_case"]


def test_cli_returns_error_code_for_invalid_dataset(tmp_path, capsys):
    missing = tmp_path / "missing_dataset"

    rc = main(["--dataset-dir", str(missing)])
    out = capsys.readouterr().out

    assert rc == 2
    assert "Missing dataset metadata file" in out
