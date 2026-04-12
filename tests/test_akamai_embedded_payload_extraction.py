from pathlib import Path

from components.testing_harness.harness_orchestrator import HarnessOrchestrator


def _run_single(lua_path: str, event: dict):
    lua_code = Path(lua_path).read_text(encoding="utf-8")
    report = HarnessOrchestrator().run_all_checks(
        lua_code=lua_code,
        parser_config={"parser_name": "akamai_test"},
        custom_test_events=[{"name": "sample", "event": event}],
    )
    results = report["checks"]["test_execution"]["results"]
    assert results and results[0]["status"] == "passed"
    return results[0]["output_event"]


def test_akamai_dns_extracts_embedded_message_kv_fields():
    event = {
        "message": '2026-04-08T06:38:10Z AkamaiDNS streamId="dns-423" cliIP="91.50.31.155" '
        'resolverIP="203.0.113.201" domain="mail.example.com" recordType="TXT" '
        'responseCode="NOERROR" answer="v=spf1 include:_spf.example.com ~all"',
        "timestamp": "2026-04-08T20:43:38.292855436Z",
    }
    out = _run_single("output/agent_lua_scripts/akamai_dns-latest.lua", event)
    assert out.get("class_uid") == 4003
    assert out.get("query", {}).get("hostname") == "mail.example.com"
    assert out.get("query", {}).get("type") == "TXT"
    assert out.get("src_endpoint", {}).get("ip") == "91.50.31.155"
    assert out.get("rcode") == "NOERROR"


def test_akamai_cdn_extracts_embedded_message_kv_fields():
    event = {
        "message": '2026-04-08T06:07:25Z AkamaiCDN streamId="stream-113" cp="16563" reqId="k8j6a2tq0l" '
        'statusCode=503 cliIP="105.223.85.182" reqHost="api.example.com" reqMethod="DELETE" '
        'reqPath="/favicon.ico" bytes=451919 cacheStatus="REFRESH_MISS" '
        'turnAroundTimeMSec=354 edgeIP="125.207.200.250"',
        "timestamp": "2026-04-08T20:07:02.359809636Z",
    }
    out = _run_single("output/agent_lua_scripts/akamai_cdn-latest.lua", event)
    assert out.get("class_uid") == 4002
    assert out.get("http_request", {}).get("http_method") == "DELETE"
    assert out.get("http_response", {}).get("code") in ("503", 503)
    assert out.get("src_endpoint", {}).get("ip") == "105.223.85.182"
    assert out.get("http_request", {}).get("url") == "https://api.example.com/favicon.ico"
