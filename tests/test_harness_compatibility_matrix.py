import pytest

from components.testing_harness.dual_execution_engine import DualExecutionEngine
from components.testing_harness.lua_validity_checker import LuaValidityChecker


@pytest.mark.parametrize(
    "name,lua_code,expected_signature",
    [
        (
            "canonical_process_event",
            "function processEvent(event) return event end",
            "processEvent",
        ),
        (
            "legacy_transform_record",
            "function transform(record) return record end",
            "transform",
        ),
        (
            "legacy_process_emit",
            "function process(event, emit) emit(event) end",
            "process",
        ),
        (
            "mixed_process_event_and_transform",
            """
function processEvent(event)
  return event
end
function transform(record)
  return record
end
""",
            "processEvent",
        ),
        (
            "mixed_process_and_transform",
            """
function process(event, emit)
  emit(event)
end
function transform(record)
  return record
end
""",
            "process",
        ),
    ],
)
def test_signature_detection_matrix(name, lua_code, expected_signature):
    engine = DualExecutionEngine()
    assert engine._detect_signature(lua_code) == expected_signature


@pytest.mark.parametrize(
    "lua_code,expected_signature,expect_legacy_warning",
    [
        ("function processEvent(event) return event end", "processEvent", False),
        ("function transform(record) return record end", "transform", True),
        ("function process(event, emit) emit(event) end", "process", False),
    ],
)
def test_validity_checker_compatibility_contract_matrix(
    lua_code, expected_signature, expect_legacy_warning
):
    checker = LuaValidityChecker()

    result = checker.check(lua_code)

    assert result["valid"] is True
    assert result["function_signature"] == expected_signature

    has_legacy_warning = any("compatibility-only" in warning for warning in result["warnings"])
    assert has_legacy_warning is expect_legacy_warning


def test_execute_uses_detected_signature_for_legacy_and_mixed_paths(monkeypatch):
    from components.testing_harness import dual_execution_engine as engine_module

    engine = DualExecutionEngine()
    observed_signatures = []

    def fake_execute_single(lua_code, signature, event_data, test_name, ocsf_required):
        observed_signatures.append(signature)
        return {
            "test_name": test_name,
            "status": "passed",
            "input_event": event_data,
            "output_event": event_data,
            "error": None,
            "execution_time_ms": 0.0,
            "field_trace": [],
            "ocsf_validation": {
                "required_present": [],
                "required_missing": [],
                "coverage_pct": 100,
            },
        }

    monkeypatch.setattr(engine_module, "LUPA_AVAILABLE", True)
    monkeypatch.setattr(engine, "_execute_single", fake_execute_single)

    matrix = [
        ("function transform(record) return record end", "transform"),
        ("function process(event, emit) emit(event) end", "process"),
        (
            "function processEvent(event) return event end\nfunction transform(record) return record end",
            "processEvent",
        ),
    ]

    for lua_code, expected in matrix:
        result = engine.execute(lua_code, [{"name": "case", "event": {"k": "v"}}])
        assert result["function_signature"] == expected

    assert observed_signatures == ["transform", "process", "processEvent"]
