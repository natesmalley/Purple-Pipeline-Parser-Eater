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


def test_source_analyzer_extracts_fields_from_ms_defender_sample():
    analyzer = SourceParserAnalyzer()
    parser_config = {
        "parser_name": "microsoft_365_defender-latest",
        "raw_examples": [
            '{"AccountDomain":"STARFLEET","AccountName":"william.riker","ActionType":"PowerShellCommand",'
            '"DeviceId":"0020796EEFABA232","DeviceName":"ENTERPRISE-ENG-01",'
            '"ProcessName":"powershell.exe","Timestamp":"2026-04-08T10:02:59Z",'
            '"scenario.trace_id":"7e0e9f27-76d5-4d06-9bdb-d2b358928219",'
            '"splunk_sourcetype":"microsoft_365_defender-latest","timestamp":"2026-04-08T10:06:59Z"}'
        ],
    }
    result = analyzer.analyze_parser(parser_config)
    names = {f["name"] for f in result.get("fields", [])}
    assert "AccountDomain" in names
    assert "ActionType" in names
    assert "ProcessName" in names
    assert "scenario.trace_id" in names
    assert "timestamp" in names


def test_source_analyzer_extracts_fields_from_akamai_dns_embedded_message_kv():
    analyzer = SourceParserAnalyzer()
    parser_config = {
        "parser_name": "akamai_dns-latest",
        "raw_examples": [
            '{'
            '"message":"2026-04-08T06:38:10Z AkamaiDNS streamId=\\"dns-423\\" cliIP=\\"91.50.31.155\\" '
            'resolverIP=\\"203.0.113.201\\" domain=\\"mail.example.com\\" recordType=\\"TXT\\" '
            'responseCode=\\"NOERROR\\" answer=\\"v=spf1 include:_spf.example.com ~all\\" bytes=256",'
            '"timestamp":"2026-04-08T20:43:38.292855436Z"'
            '}'
        ],
    }
    result = analyzer.analyze_parser(parser_config)
    names = {f["name"] for f in result.get("fields", [])}
    assert "message" in names
    assert "timestamp" in names
    assert "domain" in names
    assert "recordType" in names
    assert "responseCode" in names
    assert "cliIP" in names
