from components.testing_harness.source_parser_analyzer import SourceParserAnalyzer


def test_source_analyzer_extracts_fields_from_raw_example_message_kv():
    analyzer = SourceParserAnalyzer()
    parser_config = {
        "parser_name": "custom_parser",
        "raw_examples": [
            '{\n'
            '"message":"AkamaiCDN reqMethod=\\"DELETE\\" statusCode=503 cliIP=\\"105.223.85.182\\" reqHost=\\"api.example.com\\" reqPath=\\"/favicon.ico\\" turnAroundTimeMSec=354",\n'
            '"timestamp":"2026-04-08T20:07:02.359809636Z"\n'
            '}'
        ],
    }
    result = analyzer.analyze_parser(parser_config)
    names = {f["name"] for f in result.get("fields", [])}
    assert "message" in names
    assert "timestamp" in names
    assert "reqMethod" in names
    assert "statusCode" in names
    assert "cliIP" in names
    assert "turnAroundTimeMSec" in names


def test_lua_field_extraction_captures_set_nested_field_targets():
    analyzer = SourceParserAnalyzer()
    lua = """
function processEvent(event)
  local result = {}
  setNestedField(result, "http_request.url", "/x")
  setNestedField(result, "http_response.code", 503)
  result["status"] = "503"
  event["lua_error"] = nil
  return result
end
"""
    fields = analyzer._extract_lua_fields(lua)
    assert "http_request.url" in fields
    assert "http_response.code" in fields
    assert "status" in fields
    assert "lua_error" not in fields
