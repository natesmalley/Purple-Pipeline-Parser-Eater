"""Template-runtime helper parity tests.

Validates that the canonical Lua helpers loaded by both the LLM prompt
template and the sandbox runtime produce identical behavior. Catches the
class of bug where setNestedField was missing a nil guard in one copy.
"""

import pytest

try:
    import lupa
    HAS_LUPA = True
except ImportError:
    HAS_LUPA = False

pytestmark = pytest.mark.skipif(not HAS_LUPA, reason="lupa not installed")

from components.testing_harness.lua_helpers import get_canonical_helpers


@pytest.fixture
def lua():
    """LuaRuntime loaded with canonical helpers."""
    rt = lupa.LuaRuntime(unpack_returned_tuples=True)
    rt.execute(get_canonical_helpers())
    return rt


# ---------------------------------------------------------------------------
# getNestedField
# ---------------------------------------------------------------------------

class TestGetNestedField:

    def test_nil_obj(self, lua):
        assert lua.globals().getNestedField(None, "a.b") is None

    def test_nil_path(self, lua):
        tbl = lua.table_from({})
        assert lua.globals().getNestedField(tbl, None) is None

    def test_empty_path(self, lua):
        tbl = lua.table_from({})
        assert lua.globals().getNestedField(tbl, "") is None

    def test_nested_hit(self, lua):
        inner = lua.table_from({"b": 42})
        outer = lua.table_from({"a": inner})
        assert lua.globals().getNestedField(outer, "a.b") == 42

    def test_nested_miss(self, lua):
        inner = lua.table_from({"b": 42})
        outer = lua.table_from({"a": inner})
        assert lua.globals().getNestedField(outer, "a.c") is None

    def test_non_table_intermediate(self, lua):
        outer = lua.table_from({"a": "string"})
        assert lua.globals().getNestedField(outer, "a.b") is None

    def test_single_key(self, lua):
        tbl = lua.table_from({"x": 99})
        assert lua.globals().getNestedField(tbl, "x") == 99


# ---------------------------------------------------------------------------
# setNestedField
# ---------------------------------------------------------------------------

class TestSetNestedField:

    def test_nil_obj_no_crash(self, lua):
        lua.globals().setNestedField(None, "a.b", 1)

    def test_nil_path_no_crash(self, lua):
        tbl = lua.table_from({})
        lua.globals().setNestedField(tbl, None, 1)

    def test_empty_path_no_crash(self, lua):
        tbl = lua.table_from({})
        lua.globals().setNestedField(tbl, "", 1)

    def test_nil_value_no_crash(self, lua):
        tbl = lua.table_from({})
        lua.globals().setNestedField(tbl, "a.b", None)

    def test_creates_nested_structure(self, lua):
        tbl = lua.table_from({})
        lua.globals().setNestedField(tbl, "a.b.c", 42)
        assert lua.globals().getNestedField(tbl, "a.b.c") == 42

    def test_non_table_intermediate_no_crash(self, lua):
        tbl = lua.table_from({"a": "string"})
        lua.globals().setNestedField(tbl, "a.b", 1)

    def test_single_key(self, lua):
        tbl = lua.table_from({})
        lua.globals().setNestedField(tbl, "x", 7)
        assert lua.globals().getNestedField(tbl, "x") == 7


# ---------------------------------------------------------------------------
# getValue
# ---------------------------------------------------------------------------

class TestGetValue:

    def test_nil_table_returns_default(self, lua):
        result = lua.globals().getValue(None, "key", "default")
        assert result == "default"

    def test_key_present(self, lua):
        tbl = lua.table_from({"key": 42})
        assert lua.globals().getValue(tbl, "key", 0) == 42

    def test_key_missing(self, lua):
        tbl = lua.table_from({})
        assert lua.globals().getValue(tbl, "missing", "fallback") == "fallback"


# ---------------------------------------------------------------------------
# copyUnmappedFields
# ---------------------------------------------------------------------------

class TestCopyUnmappedFields:

    def test_empty_event_no_crash(self, lua):
        event = lua.table_from({})
        mapped = lua.table_from({})
        result = lua.table_from({})
        lua.globals().copyUnmappedFields(event, mapped, result)

    def test_nil_event_no_crash(self, lua):
        mapped = lua.table_from({})
        result = lua.table_from({})
        lua.globals().copyUnmappedFields(None, mapped, result)

    def test_unmapped_preserved(self, lua):
        event = lua.table_from({"src_ip": "10.0.0.1", "extra": "data"})
        mapped = lua.table_from({"src_ip": True})
        result = lua.table_from({})
        lua.globals().copyUnmappedFields(event, mapped, result)
        assert lua.globals().getNestedField(result, "unmapped.extra") == "data"

    def test_mapped_fields_excluded(self, lua):
        event = lua.table_from({"src_ip": "10.0.0.1", "extra": "data"})
        mapped = lua.table_from({"src_ip": True})
        result = lua.table_from({})
        lua.globals().copyUnmappedFields(event, mapped, result)
        assert lua.globals().getNestedField(result, "unmapped.src_ip") is None


# ---------------------------------------------------------------------------
# flattenObject
# ---------------------------------------------------------------------------

class TestFlattenObject:

    def test_nil_table_no_crash(self, lua):
        result = lua.globals().flattenObject(None, "", None)
        assert result is not None

    def test_flat_table(self, lua):
        tbl = lua.table_from({"a": 1, "b": 2})
        result = lua.globals().flattenObject(tbl, "", None)
        assert result["a"] == 1
        assert result["b"] == 2

    def test_nested_table(self, lua):
        inner = lua.table_from({"y": 99})
        tbl = lua.table_from({"x": inner})
        result = lua.globals().flattenObject(tbl, "", None)
        assert result["x.y"] == 99
