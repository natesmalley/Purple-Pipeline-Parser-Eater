"""Tests for the expanded helper-name families added 2026-04-19.

Motivated by Orion-generated Lua that uses ``deepGet(e, "path")`` / ``deepSet(ocsf, "class_uid", N)``
instead of the ``getNestedField`` / ``setNestedField`` names our analyzer
originally recognized. These tests lock in recognition of the extended
helper-name families.
"""

from __future__ import annotations

import pytest

from components.testing_harness.ocsf_field_analyzer import OCSFFieldAnalyzer
from components.testing_harness.ocsf_schema_registry import OCSFSchemaRegistry
from components.testing_harness.source_parser_analyzer import SourceParserAnalyzer


@pytest.fixture(scope="module")
def source_analyzer() -> SourceParserAnalyzer:
    return SourceParserAnalyzer()


@pytest.fixture(scope="module")
def ocsf_analyzer() -> OCSFFieldAnalyzer:
    return OCSFFieldAnalyzer(OCSFSchemaRegistry())


# ---------------------------------------------------------------------------
# Source analyzer — deepGet family
# ---------------------------------------------------------------------------

DEEP_GET_LUA = """
function processEvent(event)
    local result = {}
    local action = deepGet(event, "action")
    local actor  = deepGet(e, "actor.id")
    local repo   = safeGet(event, "repo")
    local org    = getNested(event, "org.name")
    return result
end
"""

GETVALUE_LUA = """
function processEvent(event)
    local x = getValue(event, "ActionType", "")
    local y = getNestedField(event, "scenario.trace_id")
    return { x = x, y = y }
end
"""


def test_source_analyzer_recognizes_deepget_family(source_analyzer):
    fields = source_analyzer._extract_lua_fields(DEEP_GET_LUA)
    assert "action" in fields
    assert "actor.id" in fields
    assert "repo" in fields
    assert "org.name" in fields


def test_source_analyzer_still_recognizes_original_helpers(source_analyzer):
    fields = source_analyzer._extract_lua_fields(GETVALUE_LUA)
    assert "ActionType" in fields
    assert "scenario.trace_id" in fields


def test_source_analyzer_ignores_non_event_first_arg(source_analyzer):
    """Helpers invoked with something other than a known event alias should
    not false-match. This protects against capturing every string literal in
    every function call."""
    code = 'local x = deepGet(myLocalTable, "name")\n'
    fields = source_analyzer._extract_lua_fields(code)
    # "name" should NOT appear because myLocalTable isn't in the event alias list.
    assert "name" not in fields


# ---------------------------------------------------------------------------
# OCSF analyzer — deepSet family
# ---------------------------------------------------------------------------

DEEP_SET_CLASS_UID = """
function processEvent(event)
    local ocsf = {}
    deepSet(ocsf, "class_uid", 2004)
    deepSet(ocsf, "category_uid", 2)
    return ocsf
end
"""

WRITEFIELD_CLASS_UID = """
function processEvent(event)
    local result = {}
    writeField(result, "class_uid", 6003)
    writeField(result, "time", event.timestamp or 0)
    return result
end
"""

SETNESTED_CLASS_UID = """
function processEvent(event)
    local r = {}
    setNested(r, "class_uid", 4003)
    return r
end
"""

DEEP_SET_IDENT_RESOLVES = """
local CLASS_UID = 4001
function processEvent(event)
    local r = {}
    deepSet(r, "class_uid", CLASS_UID)
    return r
end
"""


@pytest.mark.parametrize("lua,expected_uid", [
    (DEEP_SET_CLASS_UID, 2004),
    (WRITEFIELD_CLASS_UID, 6003),
    (SETNESTED_CLASS_UID, 4003),
    (DEEP_SET_IDENT_RESOLVES, 4001),
])
def test_class_uid_via_deepset_family(ocsf_analyzer, lua, expected_uid):
    assert ocsf_analyzer._detect_class_uid(lua) == expected_uid


def test_ocsf_extract_fields_via_deepset_family(ocsf_analyzer):
    fields = ocsf_analyzer._extract_fields(DEEP_SET_CLASS_UID)
    names = [f["field"] for f in fields]
    assert "class_uid" in names
    assert "category_uid" in names


def test_ocsf_writefield_still_considered_a_field_assignment(ocsf_analyzer):
    """writeField writes to output like setNestedField — its target paths
    should be collected so OCSF alignment works."""
    fields = ocsf_analyzer._extract_fields(WRITEFIELD_CLASS_UID)
    names = [f["field"] for f in fields]
    assert "class_uid" in names
    assert "time" in names


# ---------------------------------------------------------------------------
# FIELD_MAP-style inline mapping tables
# ---------------------------------------------------------------------------

FIELD_MAP_LUA = """
local FIELD_MAP = {
    ["timestamp"]        = "time",
    ["ProcessStartTime"] = "start_time",
    ["UserName"]         = "actor.user.name",
    ["SeverityName"]     = "severity",
}

-- Lookup tables with table-literal values should NOT be treated as field mappings.
local SEVERITY_MAP = {
    ["0"] = { id = 1, label = "Informational" },
    ["1"] = { id = 2, label = "Low" },
}

function processEvent(event) return {} end
"""


def test_source_analyzer_recognizes_field_map_table(source_analyzer):
    """Orion emits FIELD_MAP-style mapping tables ([source] = "target.path").
    Both keys and values should be captured as referenced field names."""
    fields = source_analyzer._extract_lua_fields(FIELD_MAP_LUA)
    # Source-side keys
    assert "timestamp" in fields
    assert "ProcessStartTime" in fields
    assert "UserName" in fields
    # Target-side values
    assert "time" in fields
    assert "actor.user.name" in fields
    # Lookup table entries (values are table literals) should NOT be captured
    assert "Informational" not in fields
    assert "Low" not in fields


# ---------------------------------------------------------------------------
# Mapping source/target key variants
# ---------------------------------------------------------------------------

MAPPING_KEYS_LUA = """
local mappings = {
    { src = "ActionType",        dst = "activity_name" },
    { source = "Timestamp",      target = "time" },
    { from = "UserId",           to = "actor.user.uid" },
    { dest_path = "finding_info.title" },
    { input = "DetectName",      output = "finding_info.title" },
}
"""


def test_source_analyzer_recognizes_all_mapping_key_variants(source_analyzer):
    fields = source_analyzer._extract_lua_fields(MAPPING_KEYS_LUA)
    for expected in (
        "ActionType", "activity_name",
        "Timestamp", "time",
        "UserId", "actor.user.uid",
        "finding_info.title",
        "DetectName",
    ):
        assert expected in fields, f"missing {expected} in {fields}"
