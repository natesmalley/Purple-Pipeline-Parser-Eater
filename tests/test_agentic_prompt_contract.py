from components.agentic_lua_generator import (
    GPT5_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    _build_gpt5_known_options,
    build_gpt5_lua_scaffold,
    build_gpt5_code_prompt,
    build_gpt5_plan_prompt,
    build_generation_prompt,
    classify_ocsf_class,
    _infer_sample_preflight,
)
from components.source_family_registry import list_supported_source_family_keys


def test_system_prompt_contains_observo_runtime_safety_rules():
    assert "function processEvent(event)" in SYSTEM_PROMPT
    assert "Do NOT use `event:get(...)" in SYSTEM_PROMPT
    assert "Do NOT rely on external modules or `require(...)` calls" in SYSTEM_PROMPT
    assert "Wrap transformation logic in `pcall`" in SYSTEM_PROMPT
    assert "Define every helper you call ABOVE `processEvent`" in SYSTEM_PROMPT
    assert "Guard `os.time({...})` / `os.date(...)` with `pcall`" in SYSTEM_PROMPT
    assert "result.time = os.time(" not in SYSTEM_PROMPT


def test_gpt5_system_prompt_is_compact_and_contract_focused():
    assert "function processEvent(event)" in GPT5_SYSTEM_PROMPT
    assert "Prefer the smallest correct script" in GPT5_SYSTEM_PROMPT
    assert "Do not invent placeholder values" in GPT5_SYSTEM_PROMPT
    assert "Parse embedded payloads in `message` or `raw` fields" in GPT5_SYSTEM_PROMPT


def test_generation_prompt_repeats_critical_compatibility_requirements():
    prompt = build_generation_prompt(
        parser_name="test_parser",
        vendor="acme",
        product="widget",
        declared_log_type="authentication",
        declared_log_detail="okta",
        class_uid=3002,
        class_name="Authentication",
        ocsf_fields={
            "category_uid": 3,
            "category_name": "Identity & Access Management",
            "required_fields": ["class_uid", "category_uid", "activity_id", "time", "type_uid", "severity_id"],
            "optional_fields": ["actor.user.name"],
        },
        source_fields=[{"name": "timestamp", "type": "string"}],
        ingestion_mode="push",
        examples=[{"timestamp": "2026-01-01T00:00:00Z"}],
    )
    assert "Never use `event:get(...)` or `event:set(...)`" in prompt
    assert "Define all helper functions above `processEvent`" in prompt
    assert "Wrap main transform logic in `pcall`" in prompt
    assert "USER DECLARED LOG TYPE: authentication" in prompt
    assert "USER DECLARED SOURCE DETAIL: okta" in prompt
    assert "os.time({..." in prompt
    assert "os.date(...)" in prompt
    assert "`pcall`" in prompt
    assert "Always evaluate embedded payloads in `message`/`raw` fields regardless of data type" in prompt


def test_generation_prompt_adds_duo_source_specific_guidance():
    prompt = build_generation_prompt(
        parser_name="cisco_duo_logs",
        vendor="Cisco",
        product="Duo",
        declared_log_type="authentication",
        declared_log_detail="cisco duo authentication",
        class_uid=3002,
        class_name="Authentication",
        ocsf_fields={"category_uid": 3, "category_name": "Identity & Access Management"},
        source_fields=[{"name": "user", "type": "string"}],
        ingestion_mode="push",
        examples=[],
    )
    assert "Source-specific guidance (Cisco Duo)" in prompt
    assert "Enforce `class_uid=3002`" in prompt


def test_generation_prompt_adds_akamai_dns_guidance():
    prompt = build_generation_prompt(
        parser_name="akamai_dns-latest",
        vendor="Akamai",
        product="DNS",
        declared_log_type="dns_activity",
        declared_log_detail="akamai dns",
        class_uid=4003,
        class_name="DNS Activity",
        ocsf_fields={"category_uid": 4, "category_name": "Network Activity"},
        source_fields=[{"name": "message", "type": "string"}],
        ingestion_mode="push",
        examples=[],
    )
    assert "Source-specific guidance (Akamai DNS)" in prompt
    assert "Enforce `class_uid=4003`" in prompt
    assert "`cliIP`->`src_endpoint.ip`" in prompt
    assert "`domain`->`query.hostname`" in prompt


def test_generation_prompt_adds_netskope_guidance():
    prompt = build_generation_prompt(
        parser_name="netskope_alerts-latest",
        vendor="Netskope",
        product="Netskope",
        declared_log_type="security_finding",
        declared_log_detail="netskope malware",
        class_uid=2001,
        class_name="Security Finding",
        ocsf_fields={"category_uid": 2, "category_name": "Findings"},
        source_fields=[{"name": "alert_type", "type": "string"}],
        ingestion_mode="push",
        examples=[],
    )
    assert "Source-specific guidance (Netskope)" in prompt
    assert "determine the subtype from `alert_type`" in prompt
    assert "`Policy` -> Web Resources Activity (6001)" in prompt


def test_generation_prompt_adds_microsoft_365_guidance():
    prompt = build_generation_prompt(
        parser_name="microsoft_365_audit-latest",
        vendor="Microsoft",
        product="O365",
        declared_log_type="authentication",
        declared_log_detail="microsoft 365 management activity",
        class_uid=3002,
        class_name="Authentication",
        ocsf_fields={"category_uid": 3, "category_name": "Identity & Access Management"},
        source_fields=[{"name": "Operation", "type": "string"}],
        ingestion_mode="push",
        examples=[],
    )
    assert "Source-specific guidance (Microsoft 365/O365)" in prompt
    assert "distinguish Graph-style alerts from Management Activity records" in prompt
    assert "derive class and activity from the normalized operation name" in prompt


def test_generation_prompt_adds_gcp_audit_guidance():
    prompt = build_generation_prompt(
        parser_name="gcp_audit_logs-latest",
        vendor="GCP",
        product="Audit",
        declared_log_type="authentication",
        declared_log_detail="gcp audit",
        class_uid=3004,
        class_name="Entity Management",
        ocsf_fields={"category_uid": 3, "category_name": "Identity & Access Management"},
        source_fields=[{"name": "logName", "type": "string"}],
        ingestion_mode="push",
        examples=[],
    )
    assert "Source-specific guidance (GCP Audit)" in prompt
    assert "infer the event family from `logName`" in prompt
    assert "`policy_denied`" in prompt


def test_generation_prompt_adds_darktrace_guidance():
    prompt = build_generation_prompt(
        parser_name="darktrace-latest",
        vendor="Darktrace",
        product="Darktrace",
        declared_log_type="detection_finding",
        declared_log_detail="darktrace incidents",
        class_uid=2004,
        class_name="Detection Finding",
        ocsf_fields={"category_uid": 2, "category_name": "Findings"},
        source_fields=[{"name": "relatedBreaches", "type": "array"}],
        ingestion_mode="push",
        examples=[],
    )
    assert "Source-specific guidance (Darktrace)" in prompt
    assert "determine the subtype from the record shape" in prompt
    assert "`modelbreaches`" in prompt


def test_source_family_registry_tracks_supported_high_value_sources():
    keys = set(list_supported_source_family_keys())
    assert "cisco_duo" in keys
    assert "microsoft_defender" in keys
    assert "netskope" in keys
    assert "microsoft_365" in keys
    assert "gcp_audit" in keys
    assert "darktrace" in keys


def test_gpt5_plan_prompt_requests_json_planning_first():
    known = _build_gpt5_known_options(
        parser_name="akamai_dns-latest",
        vendor="Akamai",
        product="DNS",
        declared_log_type="dns_activity",
        declared_log_detail="akamai dns",
        class_uid=4003,
    )
    prompt = build_gpt5_plan_prompt(
        parser_name="akamai_dns-latest",
        vendor="Akamai",
        product="DNS",
        declared_log_type="dns_activity",
        declared_log_detail="akamai dns",
        class_uid=4003,
        class_name="DNS Activity",
        ocsf_fields={"category_uid": 4, "category_name": "Network Activity"},
        source_fields=[{"name": "message", "type": "string"}],
        ingestion_mode="push",
        examples=[{"message": 'AkamaiDNS cliIP="1.2.3.4" domain="example.com"'}],
        deterministic_preflight={"formats": ["json"], "record_hints": ["akamai_dns"], "embedded_payload_detected": True, "extracted_fields": ["cliIP", "domain"]},
        known_options=known,
    )
    assert "Return only a JSON plan" in prompt
    assert "exact numeric activity_id" in prompt
    assert "Known source-family defaults" in prompt
    assert "activity_id: 1" in prompt
    assert "cliIP -> src_endpoint.ip" in prompt
    assert "Embedded payload detected: True" in prompt
    assert "Candidate extracted fields: cliIP, domain" in prompt


def test_gpt5_code_prompt_uses_approved_plan():
    plan = {
        "class_uid": 3002,
        "class_name": "Authentication",
        "category_uid": 3,
        "category_name": "Identity & Access Management",
        "activity_id": 1,
        "activity_name": "Logon",
        "timestamp_sources": ["timestamp"],
        "severity_strategy": "default 0",
        "embedded_payload_strategy": "none",
        "mappings": [{"target": "actor.user.name", "source_candidates": ["user.name"], "transform": "direct", "required": False}],
        "notes": ["keep script compact"],
    }
    scaffold = build_gpt5_lua_scaffold(plan)
    prompt = build_gpt5_code_prompt(
        parser_name="test_parser",
        class_uid=3002,
        class_name="Authentication",
        category_uid=3,
        category_name="Identity & Access Management",
        plan=plan,
        scaffold=scaffold,
    )
    assert "Approved mapping plan" in prompt
    assert "Output only Lua code" in prompt
    assert "activity_id" in prompt
    assert "explicit assignments for all six required OCSF fields" in prompt
    assert "Scaffold to complete" in prompt
    assert scaffold in prompt


def test_gpt5_known_options_provide_dns_defaults():
    known = _build_gpt5_known_options(
        parser_name="akamai_dns-latest",
        vendor="Akamai",
        product="DNS",
        declared_log_type="dns_activity",
        declared_log_detail="akamai dns",
        class_uid=4003,
    )
    assert known["activity_id"] == 1
    assert known["activity_name"] == "DNS Query"
    assert "cliIP -> src_endpoint.ip" in known["field_aliases"]


def test_gpt5_known_options_provide_okta_auth_defaults():
    known = _build_gpt5_known_options(
        parser_name="okta_logs-latest",
        vendor="Okta",
        product="Okta",
        declared_log_type="authentication",
        declared_log_detail="okta authentication",
        class_uid=3002,
    )
    assert known["activity_id"] == 1
    assert known["activity_name"] == "Logon"
    assert "eventType -> activity_name or status_detail context" in known["field_aliases"]


def test_gpt5_known_options_provide_netskope_family_defaults():
    known = _build_gpt5_known_options(
        parser_name="netskope_alerts-latest",
        vendor="Netskope",
        product="Netskope",
        declared_log_type="security_finding",
        declared_log_detail="netskope malware",
        class_uid=2001,
    )
    assert "alert_type -> subtype router before mapping" in known["field_aliases"]
    assert "policy -> analytic.name or actor.authorizations.policy.name" in known["field_aliases"]
    assert "Netskope records should route on alert_type before final class/activity selection" in known["notes"]


def test_gpt5_known_options_provide_microsoft_defender_finding_aliases():
    known = _build_gpt5_known_options(
        parser_name="microsoft_defender_for_cloud-latest",
        vendor="Microsoft",
        product="Defender",
        declared_log_type="detection_finding",
        declared_log_detail="microsoft defender for cloud",
        class_uid=2004,
    )
    assert "id -> metadata.uid or finding_info.uid" in known["field_aliases"]
    assert "title -> finding_info.title" in known["field_aliases"]
    assert "recommendedActions -> remediation.desc" in known["field_aliases"]


def test_gpt5_known_options_provide_microsoft_365_aliases():
    known = _build_gpt5_known_options(
        parser_name="microsoft_365_audit-latest",
        vendor="Microsoft",
        product="O365",
        declared_log_type="authentication",
        declared_log_detail="microsoft 365 management activity",
        class_uid=3002,
    )
    assert "Operation -> subtype router before mapping" in known["field_aliases"]
    assert "PolicyDetails.PolicyId -> analytic.uid" in known["field_aliases"]
    assert "Microsoft 365 inputs should first route to Graph alerts vs Management Activity logs" in known["notes"]


def test_gpt5_known_options_provide_gcp_audit_aliases():
    known = _build_gpt5_known_options(
        parser_name="gcp_audit_logs-latest",
        vendor="GCP",
        product="Audit",
        declared_log_type="authentication",
        declared_log_detail="gcp audit",
        class_uid=3004,
    )
    assert "logName -> subtype router before mapping" in known["field_aliases"]
    assert "protoPayload.status.code -> status_code" in known["field_aliases"]
    assert "GCP Audit logs should route on logName-derived family: admin_activity, data_access, system_event, or policy_denied" in known["notes"]


def test_gpt5_known_options_provide_darktrace_aliases():
    known = _build_gpt5_known_options(
        parser_name="darktrace-latest",
        vendor="Darktrace",
        product="Darktrace",
        declared_log_type="detection_finding",
        declared_log_detail="darktrace incidents",
        class_uid=2004,
    )
    assert "incidentEvents[].uuid -> finding_info.uid" in known["field_aliases"]
    assert "model.then/model.now -> resources/resources_result" in known["field_aliases"]
    assert "Darktrace records should route on record shape: groups, incidentevents, modelbreaches, or status" in known["notes"]


def test_gpt5_known_options_provide_apache_http_aliases():
    known = _build_gpt5_known_options(
        parser_name="apache_http_logs-latest",
        vendor="Apache",
        product="HTTP",
        declared_log_type="http_activity",
        declared_log_detail="apache http",
        class_uid=4002,
    )
    assert known["activity_id"] == 1
    assert known["activity_name"] == "HTTP Request"
    # W2 backfill (2026-04-29): the apache_http alias was tightened from
    # "uri -> http_request.url" to "uri -> http_request.url.path" because
    # OCSF 1.3 http_request.url is an object whose path lives at .path.
    # Tolerate future precision changes by matching on the prefix.
    assert any(
        a.startswith("uri -> http_request.url") for a in known["field_aliases"]
    )


def test_gpt5_known_options_provide_cloudflare_aliases():
    known = _build_gpt5_known_options(
        parser_name="cloudflare_inc_waf-lastest",
        vendor="Cloudflare",
        product="inc_waf",
        declared_log_type="waf_activity",
        declared_log_detail="cloudflare waf",
        class_uid=4002,
    )
    assert known["activity_id"] == 1
    assert "client.ipAddress -> src_endpoint.ip" in known["field_aliases"]


def test_gpt5_scaffold_initializes_required_ocsf_fields():
    scaffold = build_gpt5_lua_scaffold(
        {
            "class_uid": 4003,
            "class_name": "DNS Activity",
            "category_uid": 4,
            "category_name": "Network Activity",
            "activity_id": 1,
            "activity_name": "DNS Query",
            "timestamp_sources": ["timestamp", "Timestamp"],
            "severity_strategy": "default 0",
            "embedded_payload_strategy": "parse message kv",
            "mappings": [{"target": "query.hostname", "source_candidates": ["domain"], "transform": "direct", "required": False}],
            "notes": ["dns scaffold"],
        }
    )
    assert "local CLASS_UID = 4003" in scaffold
    assert "local CATEGORY_UID = 4" in scaffold
    assert "local ACTIVITY_ID = 1" in scaffold
    assert 'class_uid = CLASS_UID' in scaffold
    assert 'type_uid = CLASS_UID * 100 + ACTIVITY_ID' in scaffold
    assert 'event["lua_error"] = tostring(transformed)' in scaffold
    assert '-- TODO map query.hostname from [domain] using direct' in scaffold


def test_classifier_uses_sample_content_for_custom_parser():
    class_uid, class_name = classify_ocsf_class(
        "custom_parser_custom_parser_04120333",
        "",
        "",
        sample_text='AkamaiCDN reqMethod="DELETE" statusCode=503 reqHost="api.example.com"',
    )
    assert class_uid == 4002
    assert "HTTP" in class_name


def test_deterministic_preflight_detects_embedded_message_kv_fields():
    preflight = _infer_sample_preflight([
        '{"message":"AkamaiCDN reqMethod=\\"DELETE\\" statusCode=503 reqHost=\\"api.example.com\\" reqPath=\\"/favicon.ico\\"","timestamp":"2026-04-08T20:07:02Z"}'
    ])
    fields = set(preflight.get("extracted_fields") or [])
    assert preflight.get("embedded_payload_detected") is True
    assert "json" in (preflight.get("formats") or [])
    assert "reqMethod" in fields
    assert "statusCode" in fields
    assert "reqPath" in fields


def test_deterministic_preflight_flags_embedded_message_for_malformed_json():
    sample = (
        '{"message":"2026-04-08T06:07:25Z AkamaiCDN reqMethod="DELETE" statusCode=503 '
        'reqHost="api.example.com" reqPath="/favicon.ico"", "timestamp":"2026-04-08T20:07:02Z"}'
    )
    preflight = _infer_sample_preflight([sample])
    fields = set(preflight.get("extracted_fields") or [])
    assert preflight.get("embedded_payload_detected") is True
    assert "reqMethod" in fields
    assert "statusCode" in fields
