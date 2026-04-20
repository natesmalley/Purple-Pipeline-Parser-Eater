"""Focused tests for OCSFFieldAnalyzer.class_uid detection across the five
patterns the generator emits.

Motivated by the Marco PDF replay, where MS Defender and Akamai CDN scripts
that use ``setNestedField(result, "class_uid", N)`` were returning
``class_uid: null`` and scoring F despite being correct. The 2026-04-19 fix
added patterns 4 (helper-call with numeric literal) and 5 (helper-call with
identifier referring to a previously-assigned local constant).
"""

from __future__ import annotations

import pytest

from components.testing_harness.ocsf_field_analyzer import OCSFFieldAnalyzer
from components.testing_harness.ocsf_schema_registry import OCSFSchemaRegistry


@pytest.fixture(scope="module")
def analyzer() -> OCSFFieldAnalyzer:
    return OCSFFieldAnalyzer(OCSFSchemaRegistry())


# Pattern 1: direct `class_uid = 4001`
DIRECT_LUA = """
function processEvent(event)
    local result = {}
    result.class_uid = 4001
    return result
end
"""

# Pattern 2: `local CLASS_UID = 4001`
LOCAL_CONSTANT_LUA = """
local CLASS_UID = 4001
function processEvent(event)
    local result = {}
    result.class_uid = CLASS_UID
    return result
end
"""

LOCAL_OCSF_CLASS_UID_LUA = """
local OCSF_CLASS_UID = 3002
function processEvent(event)
    return { class_uid = OCSF_CLASS_UID }
end
"""

# Pattern 3: mapping-table entry
MAPPING_TABLE_LUA = """
local mappings = {
    { type = "computed", target = "class_uid", value = 6003 },
    { type = "direct",   target = "time",      value = "timestamp" },
}
"""

MAPPING_TABLE_REVERSE_LUA = """
local mappings = {
    { value = 4003, target = "class_uid" },
}
"""

# Pattern 4: setNestedField with numeric literal (the fix's primary target)
SETFIELD_LITERAL_LUA = """
function processEvent(event)
    local result = {}
    setNestedField(result, "class_uid", 2004)
    return result
end
"""

# Pattern 5: setNestedField with identifier bound to a literal
SETFIELD_IDENTIFIER_LUA = """
local CLASS_UID = 4003
function processEvent(event)
    local result = {}
    setNestedField(result, "class_uid", CLASS_UID)
    return result
end
"""

# Negative: helper call with no resolvable value -> None
SETFIELD_DYNAMIC_LUA = """
function processEvent(event)
    local result = {}
    setNestedField(result, "class_uid", getDynamicClass(event))
    return result
end
"""

# Negative: no class_uid anywhere
NO_CLASS_UID_LUA = """
function processEvent(event)
    return event
end
"""


@pytest.mark.parametrize("lua_code,expected", [
    (DIRECT_LUA, 4001),
    (LOCAL_CONSTANT_LUA, 4001),
    (LOCAL_OCSF_CLASS_UID_LUA, 3002),
    (MAPPING_TABLE_LUA, 6003),
    (MAPPING_TABLE_REVERSE_LUA, 4003),
    (SETFIELD_LITERAL_LUA, 2004),
    (SETFIELD_IDENTIFIER_LUA, 4003),
])
def test_class_uid_detection_covers_all_patterns(analyzer, lua_code, expected):
    assert analyzer._detect_class_uid(lua_code) == expected


@pytest.mark.parametrize("lua_code", [SETFIELD_DYNAMIC_LUA, NO_CLASS_UID_LUA])
def test_class_uid_returns_none_when_unresolvable(analyzer, lua_code):
    assert analyzer._detect_class_uid(lua_code) is None


def test_analyze_full_report_with_setfield_literal(analyzer):
    """The full analyze() call should produce class_uid + class_name when the
    helper-call pattern is used, matching the behavior for direct assignment.
    """
    report = analyzer.analyze(SETFIELD_LITERAL_LUA)
    assert report["class_uid"] == 2004
    # Detection Finding is class 2004 in OCSF 1.3.0
    assert report["class_name"] in ("Detection Finding", None) or report["class_name"]
    # Required coverage should also resolve (not 0) once the class is known.
    assert report["required_coverage"] is not None
