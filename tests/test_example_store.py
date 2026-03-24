from pathlib import Path

from components.web_ui.example_store import HarnessExampleStore


def test_example_store_records_samples_and_runs(tmp_path: Path):
    store = HarnessExampleStore(repo_root=tmp_path)

    sample_result = store.record_samples(
        parser_name="okta_logs-latest",
        sample_texts=['{"eventType":"user.session.start"}'],
        sample_provenance={"source": "user_raw_examples"},
    )
    assert sample_result["sample_count"] == 1
    assert sample_result["sample_ids"]

    loaded = store.get_parser_samples("okta_logs-latest", limit=5)
    assert len(loaded) == 1
    assert "user.session.start" in loaded[0]

    run_result = store.record_run(
        parser_name="okta_logs-latest",
        lua_code="function processEvent(event) return event end",
        harness_report={"confidence_score": 80},
        sample_provenance={"source": "user_raw_examples"},
    )
    assert run_result["run_id"]
    assert Path(run_result["lua_path"]).exists()
    assert Path(run_result["report_path"]).exists()

