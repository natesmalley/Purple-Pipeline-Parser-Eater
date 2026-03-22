"""Additional tests for PipelineValidator dataplane integration."""

import pytest

from components.pipeline_validator import PipelineValidator


def test_pipeline_validator_dataplane_disabled():
    validator = PipelineValidator(config={"dataplane": {"enabled": False}})
    result = validator.validate_complete_pipeline(
        parser_id="test",
        pipeline_json={
            "siteId": 1,
            "pipeline": {},
            "pipelineGraph": {},
            "source": {},
            "transforms": ["noop"],
            "metadata": {}
        },
        lua_code="function processEvent(e) return e end",
        original_parser_config=None,
        sample_events=[{"foo": "bar"}]
    )
    assert "dataplane_runtime" not in result["validations"]


def test_pipeline_validator_dataplane_enabled_without_binary(monkeypatch):
    class DummyValidator:
        def __init__(self, *args, **kwargs):
            raise FileNotFoundError("dataplane binary missing")

    monkeypatch.setattr("components.pipeline_validator.DataplaneValidator", DummyValidator)

    validator = PipelineValidator(config={"dataplane": {"enabled": True, "binary_path": "missing"}})
    result = validator.validate_complete_pipeline(
        parser_id="test",
        pipeline_json={
            "siteId": 1,
            "pipeline": {},
            "pipelineGraph": {},
            "source": {},
            "transforms": ["noop"],
            "metadata": {}
        },
        lua_code="function processEvent(e) return e end",
        original_parser_config=None,
        sample_events=[{"foo": "bar"}]
    )
    # Should gracefully skip dataplane stage when initialization fails
    assert "dataplane_runtime" not in result["validations"]


