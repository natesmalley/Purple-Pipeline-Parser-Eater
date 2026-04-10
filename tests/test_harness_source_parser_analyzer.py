"""Unit tests for SourceParserAnalyzer — field extraction and coverage comparison."""

import pytest

from components.testing_harness.source_parser_analyzer import SourceParserAnalyzer


@pytest.fixture
def analyzer():
    return SourceParserAnalyzer()


# ---------------------------------------------------------------------------
# analyze_parser
# ---------------------------------------------------------------------------

class TestAnalyzeParser:

    def test_extracts_from_mappings(self, analyzer):
        config = {
            "parser_name": "test_parser",
            "config": {
                "attributes": {"dataSource": {"vendor": "Acme", "product": "FW"}},
                "mappings": {
                    "mappings": [
                        {"name": "src_ip", "type": "string"},
                        {"name": "dst_ip", "type": "string"},
                    ]
                },
                "formats": [],
            },
        }
        result = analyzer.analyze_parser(config)
        assert result["parser_name"] == "test_parser"
        assert result["vendor"] == "Acme"
        assert result["total_fields"] == 2
        names = [f["name"] for f in result["fields"]]
        assert "src_ip" in names
        assert "dst_ip" in names

    def test_empty_config(self, analyzer):
        result = analyzer.analyze_parser({})
        assert result["total_fields"] == 0
        assert result["fields"] == []


# ---------------------------------------------------------------------------
# compare_with_lua
# ---------------------------------------------------------------------------

class TestCompareWithLua:

    def test_full_coverage(self, analyzer):
        parser_fields = {
            "fields": [{"name": "src_ip"}, {"name": "dst_ip"}],
        }
        lua_code = 'event.src_ip\nevent.dst_ip\nresult.out = event.src_ip\n'
        result = analyzer.compare_with_lua(parser_fields, lua_code)
        assert result["coverage_pct"] == 100

    def test_zero_coverage(self, analyzer):
        parser_fields = {
            "fields": [{"name": "src_ip"}, {"name": "dst_ip"}],
        }
        lua_code = 'result.class_uid = 4001\n'
        result = analyzer.compare_with_lua(parser_fields, lua_code)
        assert result["coverage_pct"] == 0
        assert len(result["unmapped_source_fields"]) == 2

    def test_partial_coverage(self, analyzer):
        parser_fields = {
            "fields": [{"name": "src_ip"}, {"name": "dst_ip"}, {"name": "action"}],
        }
        lua_code = 'event.src_ip\nresult.x = event.src_ip\n'
        result = analyzer.compare_with_lua(parser_fields, lua_code)
        assert 0 < result["coverage_pct"] < 100

    def test_empty_source_fields(self, analyzer):
        parser_fields = {"fields": []}
        lua_code = 'result.class_uid = 4001\n'
        result = analyzer.compare_with_lua(parser_fields, lua_code)
        assert result["coverage_pct"] == 100  # nothing to map = 100%

    def test_unmapped_reported(self, analyzer):
        parser_fields = {
            "fields": [{"name": "src_ip"}, {"name": "missing_field"}],
        }
        lua_code = 'event.src_ip\n'
        result = analyzer.compare_with_lua(parser_fields, lua_code)
        assert "missing_field" in result["unmapped_source_fields"]
