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


def test_linter_flags_missing_get_nested_field_helper():
    code = """
function processEvent(event)
  local out = {}
  out.class_uid = 2004
  out.category_uid = 2
  out.activity_id = 1
  out.type_uid = 200401
  out.severity_id = 1
  out.time = 1
  out.title = getNestedField(event, "ActionType")
  return out
end
"""
    report = LuaLinter().lint(code)
    msgs = _messages(report)
    assert any("Helper 'getNestedField()' is used but not defined" in m for m in msgs)


def test_linter_flags_observo_contract_parameter_name_mismatch():
    code = """
function processEvent(record)
  record.class_uid = 4001
  record.category_uid = 4
  record.time = 1
  record.activity_id = 1
  record.type_uid = 400101
  record.severity_id = 1
  return record
end
"""
    report = LuaLinter().lint(code)
    msgs = _messages(report)
    assert any("Observo contract requires signature `processEvent(event)`" in m for m in msgs)


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


def test_linter_accepts_observo_contract_signature():
    code = """
function processEvent(event)
  event.class_uid = 4001
  event.category_uid = 4
  event.time = 1
  event.activity_id = 1
  event.type_uid = 400101
  event.severity_id = 1
  return event
end
"""
    report = LuaLinter().lint(code)
    contract_issues = [i for i in report.get("issues", []) if i.get("rule") == "observo_contract"]
    assert contract_issues == []


def test_linter_flags_nil_unsafe_string_concat():
    code = """
function processEvent(event)
  local uri = event["RemoteUrl"]
  local out = {}
  out.class_uid = 2004
  out.category_uid = 2
  out.activity_id = 1
  out.type_uid = 200401
  out.severity_id = 1
  out.time = 1
  out.url = "prefix:" .. uri
  return out
end
"""
    report = LuaLinter().lint(code)
    concat_issues = [i for i in report.get("issues", []) if i.get("rule") == "unsafe_string_concat"]
    assert concat_issues != []
