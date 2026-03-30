from components.testing_harness.dual_execution_engine import DualExecutionEngine


def test_process_event_can_use_get_nested_field_helper():
    engine = DualExecutionEngine()
    lua_code = """
function processEvent(event)
  local out = {}
  out.class_uid = 4001
  out.category_uid = 4
  out.activity_id = 1
  out.type_uid = 400101
  out.severity_id = 2
  out.time = 1700000000000
  out.src = getNestedField(event, "client.ip_address")
  return out
end
"""

    result = engine.execute(
        lua_code,
        [{"name": "case", "event": {"client": {"ip_address": "203.0.113.45"}}}],
    )

    assert result["failed"] == 0
    assert result["passed"] == 1
    row = result["results"][0]
    assert row["status"] == "passed"
    assert row["error"] is None
    assert row["output_event"]["src"] == "203.0.113.45"

