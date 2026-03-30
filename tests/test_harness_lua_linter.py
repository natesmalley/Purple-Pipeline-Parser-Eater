from components.testing_harness.lua_linter import LuaLinter


def _messages(report):
    return [issue.get("message", "") for issue in report.get("issues", [])]


def test_linter_flags_missing_helpers_used_by_process_event():
    code = """
function processEvent(event)
  local out = {}
  out.time = getValue(event, "time", 0)
  out.class_uid = 4001
  out.category_uid = 4
  out.activity_id = 1
  out.type_uid = 400101
  out.severity_id = 1
  return no_nulls(out, "")
end
"""
    report = LuaLinter().lint(code)
    msgs = _messages(report)
    assert any("Helper 'getValue()' is used but not defined" in m for m in msgs)
    assert any("Helper 'no_nulls()' is used but not defined" in m for m in msgs)


def test_linter_flags_local_helper_declared_after_process_event():
    code = """
function processEvent(event)
  local out = {}
  out.class_uid = 4001
  out.category_uid = 4
  out.time = getValue(event, "time", 0)
  out.activity_id = 1
  out.type_uid = 400101
  out.severity_id = getSeverityId("Critical")
  return out
end

local function getSeverityId(level)
  if level == "Critical" then return 5 end
  return 1
end

function getValue(tbl, key, default)
  return default
end
"""
    report = LuaLinter().lint(code)
    msgs = _messages(report)
    assert any("Local helper 'getSeverityId()' is declared after processEvent()" in m for m in msgs)


def test_linter_accepts_helpers_defined_before_process_event():
    code = """
function getValue(tbl, key, default)
  return default
end

function no_nulls(tbl, default)
  return tbl
end

function processEvent(event)
  local out = {}
  out.class_uid = 4001
  out.category_uid = 4
  out.time = getValue(event, "time", 0)
  out.activity_id = 1
  out.type_uid = 400101
  out.severity_id = 1
  return no_nulls(out, "")
end
"""
    report = LuaLinter().lint(code)
    helper_issues = [i for i in report.get("issues", []) if i.get("rule") == "helper_dependencies"]
    assert helper_issues == []
