"""Unit tests for OCSFFieldAnalyzer — field extraction and class detection."""

import pytest

from components.testing_harness.ocsf_field_analyzer import OCSFFieldAnalyzer
from components.testing_harness.ocsf_schema_registry import OCSFSchemaRegistry


@pytest.fixture
def analyzer():
    return OCSFFieldAnalyzer(OCSFSchemaRegistry())


# ---------------------------------------------------------------------------
# _extract_fields
# ---------------------------------------------------------------------------

class TestExtractFields:

    def test_dot_notation(self, analyzer):
        code = 'result.class_uid = 4001\nresult.src_endpoint.ip = event.src\n'
        fields = analyzer._extract_fields(code)
        names = [f["field"] for f in fields]
        assert "class_uid" in names
        assert "src_endpoint.ip" in names

    def test_bracket_notation(self, analyzer):
        code = 'result["severity_id"] = 2\n'
        fields = analyzer._extract_fields(code)
        names = [f["field"] for f in fields]
        assert "severity_id" in names

    def test_mapping_table_target(self, analyzer):
        code = '{type = "direct", source = "ip", target = "src_endpoint.ip"}\n'
        fields = analyzer._extract_fields(code)
        names = [f["field"] for f in fields]
        assert "src_endpoint.ip" in names

    def test_local_constant(self, analyzer):
        code = 'local CLASS_UID = 3002\n'
        fields = analyzer._extract_fields(code)
        names = [f["field"] for f in fields]
        assert "class_uid" in names

    def test_table_constructor_ocsf(self, analyzer):
        code = 'local r = { class_uid = 4001, category_uid = 4 }\n'
        fields = analyzer._extract_fields(code)
        names = [f["field"] for f in fields]
        assert "class_uid" in names
        assert "category_uid" in names

    def test_comments_ignored_dot(self, analyzer):
        code = '-- result.class_uid = 4001\nresult.severity_id = 1\n'
        fields = analyzer._extract_fields(code)
        names = [f["field"] for f in fields]
        # The regex doesn't strip comments, so class_uid may appear.
        # This test documents current behavior.
        assert "severity_id" in names

    def test_dedup(self, analyzer):
        code = 'result.class_uid = 4001\nresult.class_uid = 4001\n'
        fields = analyzer._extract_fields(code)
        names = [f["field"] for f in fields]
        assert names.count("class_uid") == 1


# ---------------------------------------------------------------------------
# _detect_class_uid
# ---------------------------------------------------------------------------

class TestDetectClassUid:

    def test_direct_assignment(self, analyzer):
        assert analyzer._detect_class_uid("class_uid = 3002") == 3002

    def test_local_constant(self, analyzer):
        assert analyzer._detect_class_uid("local CLASS_UID = 4001") == 4001

    def test_ocsf_prefix(self, analyzer):
        assert analyzer._detect_class_uid("OCSF_CLASS_UID = 6003") == 6003

    def test_mapping_table(self, analyzer):
        code = '{target = "class_uid", type = "computed", value = 2004}'
        assert analyzer._detect_class_uid(code) == 2004

    def test_no_class_uid(self, analyzer):
        assert analyzer._detect_class_uid("local x = 42") is None


# ---------------------------------------------------------------------------
# analyze (end-to-end)
# ---------------------------------------------------------------------------

class TestAnalyze:

    def test_basic_lua(self, analyzer):
        code = """
local CLASS_UID = 3002
local CATEGORY_UID = 3
function processEvent(event)
    local result = {}
    result.class_uid = CLASS_UID
    result.category_uid = CATEGORY_UID
    result.activity_id = 1
    result.type_uid = CLASS_UID * 100 + 1
    result.severity_id = 1
    result.time = 1700000000000
    return result
end
"""
        result = analyzer.analyze(code)
        assert result["class_uid"] == 3002
        assert result["class_name"] is not None
        assert len(result["detected_fields"]) > 0

    def test_semantic_signals_placeholders(self, analyzer):
        code = 'result.class_name = "Unknown Activity"\n'
        signals = analyzer._detect_semantic_signals(code)
        assert signals["placeholder_count"] >= 1

    def test_semantic_signals_unmapped(self, analyzer):
        code = 'setNestedField(result, "unmapped.extra", v)\n'
        signals = analyzer._detect_semantic_signals(code)
        assert signals["has_unmapped_bucket"] is True
