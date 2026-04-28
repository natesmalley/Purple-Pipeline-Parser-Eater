"""Tests for the lint rules added 2026-04-19 from Marco PDF regression findings.

- ``pcall_return_scope``: catches ``local status, err = pcall(function()
  local result = {} ... return result end) ... return result`` — the outer
  return is nil because result is out of scope. Cisco DUO pattern.

- ``string_method_type_guard``: catches ``<ident>:match(...)`` and similar
  string-method calls on a value that hasn't been proven to be a string.
  Akamai DNS pattern where ``timestamp:match(...)`` blew up in production
  when the dataplane passed a numeric timestamp.
"""

from __future__ import annotations

import pytest

from components.testing_harness.lua_linter import LuaLinter


@pytest.fixture(scope="module")
def linter() -> LuaLinter:
    return LuaLinter()


def _rules_firing(result: dict) -> set:
    return {issue["rule"] for issue in result["issues"]}


# ---------------------------------------------------------------------------
# pcall_return_scope
# ---------------------------------------------------------------------------

PCALL_SCOPE_BUG = """
function processEvent(event)
    local status, err = pcall(function()
        if type(event) ~= "table" then return nil end
        local result = {}
        result.class_uid = 3002
        return result
    end)
    if not status then
        event["lua_error"] = tostring(err)
        return event
    end
    return result
end
"""

PCALL_SCOPE_OK_BOUND_TO_RESULT = """
function processEvent(event)
    local status, result = pcall(function()
        if type(event) ~= "table" then return nil end
        result = {}
        result.class_uid = 3002
        return result
    end)
    if not status then return event end
    return result
end
"""

PCALL_SCOPE_OK_OUTER_LOCAL_RESULT = """
function processEvent(event)
    local result = {}
    local status, err = pcall(function()
        result.class_uid = 3002
        return result
    end)
    if not status then return event end
    return result
end
"""

NO_PCALL_AT_ALL = """
function processEvent(event)
    local result = { class_uid = 3002 }
    return result
end
"""


def test_pcall_return_scope_fires_on_duo_pattern(linter):
    result = linter.lint(PCALL_SCOPE_BUG)
    assert "pcall_return_scope" in _rules_firing(result)


def test_pcall_return_scope_silent_when_pcall_bound_to_result(linter):
    result = linter.lint(PCALL_SCOPE_OK_BOUND_TO_RESULT)
    assert "pcall_return_scope" not in _rules_firing(result)


def test_pcall_return_scope_silent_when_outer_local_result(linter):
    result = linter.lint(PCALL_SCOPE_OK_OUTER_LOCAL_RESULT)
    assert "pcall_return_scope" not in _rules_firing(result)


def test_pcall_return_scope_silent_with_no_pcall(linter):
    result = linter.lint(NO_PCALL_AT_ALL)
    assert "pcall_return_scope" not in _rules_firing(result)


# ---------------------------------------------------------------------------
# string_method_type_guard
# ---------------------------------------------------------------------------

UNGUARDED_MATCH = """
function processEvent(event)
    local eventTime = getNestedField(event, "timestamp")
    if eventTime then
        local yr, mo = eventTime:match("(%d+)-(%d+)")
    end
    return event
end
"""

GUARDED_MATCH_BY_TYPE = """
function processEvent(event)
    local eventTime = getNestedField(event, "timestamp")
    if type(eventTime) == "string" then
        local yr, mo = eventTime:match("(%d+)-(%d+)")
    end
    return event
end
"""

GUARDED_MATCH_BY_TOSTRING = """
function processEvent(event)
    local eventTime = tostring(getNestedField(event, "timestamp") or "")
    local yr, mo = eventTime:match("(%d+)-(%d+)")
    return event
end
"""

STRING_LITERAL_ASSIGN = """
function processEvent(event)
    local prefix = "err-"
    local n, _ = prefix:gsub("err%-", "")
    return event
end
"""

STRING_LIB_NAMESPACE_CALL_IGNORED = """
function processEvent(event)
    local x = string.match(event.raw or "", "foo")
    local y = table.concat({"a", "b"}, ",")
    return event
end
"""


def test_string_method_type_guard_fires_on_dns_pattern(linter):
    result = linter.lint(UNGUARDED_MATCH)
    assert "string_method_type_guard" in _rules_firing(result)
    # Message should reference the offending identifier.
    issue = next(i for i in result["issues"] if i["rule"] == "string_method_type_guard")
    assert "eventTime" in issue["message"]


def test_string_method_type_guard_silent_with_type_guard(linter):
    result = linter.lint(GUARDED_MATCH_BY_TYPE)
    assert "string_method_type_guard" not in _rules_firing(result)


def test_string_method_type_guard_silent_with_tostring_coercion(linter):
    result = linter.lint(GUARDED_MATCH_BY_TOSTRING)
    assert "string_method_type_guard" not in _rules_firing(result)


def test_string_method_type_guard_silent_on_literal_string_assign(linter):
    result = linter.lint(STRING_LITERAL_ASSIGN)
    assert "string_method_type_guard" not in _rules_firing(result)


def test_string_method_type_guard_ignores_library_namespaces(linter):
    result = linter.lint(STRING_LIB_NAMESPACE_CALL_IGNORED)
    assert "string_method_type_guard" not in _rules_firing(result)
