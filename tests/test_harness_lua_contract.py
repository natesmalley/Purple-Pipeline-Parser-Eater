from components.testing_harness.dual_execution_engine import DualExecutionEngine
from components.testing_harness.lua_validity_checker import LuaValidityChecker


def test_dual_engine_prefers_process_event_when_both_defined(monkeypatch):
    from components.testing_harness import dual_execution_engine as engine_module

    engine = DualExecutionEngine()
    calls = []

    def fake_execute_single(lua_code, signature, event_data, test_name, ocsf_required):
        calls.append(signature)
        return {
            "test_name": test_name,
            "status": "passed",
            "input_event": event_data,
            "output_event": event_data,
            "error": None,
            "execution_time_ms": 0.0,
            "field_trace": [],
            "ocsf_validation": {"required_present": [], "required_missing": [], "coverage_pct": 100},
        }

    monkeypatch.setattr(engine_module, "LUPA_AVAILABLE", True)
    monkeypatch.setattr(engine, "_execute_single", fake_execute_single)

    lua_code = """
function processEvent(event)
  return event
end

function transform(record)
  return record
end
"""

    result = engine.execute(lua_code, [{"name": "case-1", "event": {"value": 1}}])

    assert result["function_signature"] == "processEvent"
    assert calls == ["processEvent"]
    assert result["passed"] == 1
    assert result["failed"] == 0


def test_dual_engine_supports_transform_compatibility_path(monkeypatch):
    from components.testing_harness import dual_execution_engine as engine_module

    engine = DualExecutionEngine()
    calls = []

    def fake_execute_single(lua_code, signature, event_data, test_name, ocsf_required):
        calls.append(signature)
        return {
            "test_name": test_name,
            "status": "passed",
            "input_event": event_data,
            "output_event": event_data,
            "error": None,
            "execution_time_ms": 0.0,
            "field_trace": [],
            "ocsf_validation": {"required_present": [], "required_missing": [], "coverage_pct": 100},
        }

    monkeypatch.setattr(engine_module, "LUPA_AVAILABLE", True)
    monkeypatch.setattr(engine, "_execute_single", fake_execute_single)

    lua_code = """
function transform(record)
  return record
end
"""

    result = engine.execute(lua_code, [{"name": "case-1", "event": {"value": 1}}])

    assert result["function_signature"] == "transform"
    assert calls == ["transform"]
    assert result["passed"] == 1


def test_validity_checker_warns_on_legacy_transform_signature():
    checker = LuaValidityChecker()
    lua_code = """
function transform(record)
  return record
end
"""

    result = checker.check(lua_code)

    assert result["valid"] is True
    assert result["function_signature"] == "transform"
    assert any("compatibility-only" in warning for warning in result["warnings"])


def test_validity_checker_deprecation_gate_rejects_legacy_only_transform():
    checker = LuaValidityChecker()
    lua_code = """
function transform(record)
  return record
end
"""

    result = checker.check(lua_code, enforce_deprecation_gate=True)

    assert result["valid"] is False
    assert result["function_signature"] == "transform"
    assert any("deprecated by gate policy" in error for error in result["errors"])


def test_validity_checker_deprecation_gate_allows_process_event():
    checker = LuaValidityChecker()
    lua_code = """
function processEvent(event)
  return event
end
"""

    result = checker.check(lua_code, enforce_deprecation_gate=True)

    assert result["valid"] is True
    assert result["function_signature"] == "processEvent"
    assert not any("deprecated by gate policy" in error for error in result["errors"])


def test_validity_checker_mixed_signatures_keep_migration_fallback_warning():
    checker = LuaValidityChecker()
    lua_code = """
function processEvent(event)
  return event
end
function transform(record)
  return record
end
"""

    result = checker.check(lua_code, enforce_deprecation_gate=True)

    assert result["valid"] is True
    assert result["function_signature"] == "processEvent"
    assert any("fallback detected alongside processEvent(event)" in w for w in result["warnings"])
