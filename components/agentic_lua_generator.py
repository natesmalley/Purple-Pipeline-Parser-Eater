"""
Agentic Lua Generator - LLM-powered Lua generation with harness feedback loop.

Workflow: CLASSIFY -> SELECT EXAMPLES -> GENERATE (Claude) -> VALIDATE (Harness) -> REFINE -> CACHE
"""

import json
import logging
import os
import re
import time
import hashlib
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from anthropic import Anthropic

from components.feedback_system import read_corrections_for_prompt
from components.testing_harness import (
    HarnessOrchestrator,
    OCSFSchemaRegistry,
    OCSFFieldAnalyzer,
    SourceParserAnalyzer,
)
from components.testing_harness.lua_helpers import get_helpers_for_prompt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OCSF Classifier
# ---------------------------------------------------------------------------

OCSF_CLASS_KEYWORDS: Dict[int, List[str]] = {
    4001: ["firewall", "fw", "asa", "paloalto", "fortigate", "fortinet",
           "network", "vpc", "flow", "netflow", "meraki", "barracuda",
           "juniper", "checkpoint", "sonicwall", "sophos_fw", "iptables"],
    4003: ["dns", "bind", "unbound", "dnsquery"],
    4002: ["http", "web", "waf", "proxy", "cdn", "nginx", "apache_http",
           "akamai_cdn", "akamai_site", "cloudflare", "squid", "loadbalancer"],
    3002: ["auth", "login", "sso", "duo", "okta", "ldap", "saml", "password",
           "mfa", "clearpass", "cyberark", "beyondtrust", "pingprotect",
           "radius", "kerberos", "active_directory", "ad_audit", "dhcp"],
    2004: ["edr", "alert", "detection", "threat", "malware", "finding",
           "crowdstrike", "sentinelone", "defender", "wiz", "darktrace",
           "abnormal", "guardduty", "security_event", "ids", "ips",
           "antivirus", "av_", "xdr"],
    1007: ["process", "endpoint", "agent", "sysmon", "execve", "audit"],
    1001: ["file", "dlp", "s3", "storage", "object"],
    2001: ["vulnerability", "finding", "scan", "compliance", "qualys", "tenable",
           "nessus", "rapid7", "inspector"],
    6001: ["web_resource", "web_app", "waf_event", "app_fw"],
    6003: ["api", "cloudtrail", "gcp_audit", "azure_activity", "api_gateway",
           "lambda", "cloud_functions"],
}


def classify_ocsf_class(
    parser_name: str,
    vendor: str = "",
    product: str = "",
    sample_text: str = "",
) -> Tuple[int, str]:
    """Classify a parser to its best OCSF event class."""
    combined = f"{parser_name} {vendor} {product} {sample_text}".lower().replace("-", "_")

    best_uid = 4001  # default: Network Activity
    best_score = 0

    for uid, keywords in OCSF_CLASS_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score > best_score:
            best_score = score
            best_uid = uid

    registry = OCSFSchemaRegistry()
    cls = registry.get_class(best_uid)
    class_name = cls["class_name"] if cls else "Network Activity"
    return best_uid, class_name


def _extract_kv_pairs(text: str) -> Dict[str, Any]:
    """Best-effort key=value extraction for embedded payloads."""
    if not isinstance(text, str) or not text:
        return {}
    out: Dict[str, Any] = {}
    for key, value in re.findall(r'([A-Za-z0-9_.-]+)\s*=\s*"((?:[^"\\]|\\.)*)"', text):
        out[key] = value
    for key, value in re.findall(r'([A-Za-z0-9_.-]+)\s*=\s*([^\s"]+)', text):
        if key not in out:
            out[key] = value
    return out


def _infer_sample_preflight(examples: List[Any]) -> Dict[str, Any]:
    """
    Deterministic preflight over mixed samples (json/raw/xml/csv/syslog/kv).
    Produces record-type hints and extracted field names BEFORE model inference.
    """
    if not examples:
        return {
            "formats": [],
            "embedded_payload_detected": False,
            "extracted_fields": [],
            "record_hints": [],
        }

    formats = set()
    hints = set()
    fields = set()
    embedded_payload_detected = False

    for sample in examples[:8]:
        text = sample if isinstance(sample, str) else json.dumps(sample, ensure_ascii=False)
        text = (text or "").strip()
        if not text:
            continue

        parsed_obj: Optional[Dict[str, Any]] = None
        if text[:1] in "{[":
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    parsed_obj = parsed
                    formats.add("json")
                    fields.update(str(k) for k in parsed.keys())
                elif isinstance(parsed, list):
                    formats.add("json_array")
            except Exception:
                pass

        if parsed_obj is None:
            if "," in text and text.count(",") >= 2 and "\n" in text:
                formats.add("csv")
            if "<" in text and ">" in text and re.search(r"<[^>]+>", text):
                formats.add("xml")
            if re.match(r"^<\d+>\\w{3}\\s+\\d{1,2}\\s+\\d{2}:\\d{2}:\\d{2}", text):
                formats.add("syslog")
            if "=" in text:
                kv = _extract_kv_pairs(text)
                if kv:
                    formats.add("kv")
                    fields.update(kv.keys())
                    # Malformed JSON is common in pasted samples when message contains quotes.
                    # If we can see a JSON-like message key plus KV payload, treat as embedded payload.
                    if re.search(r'["\']message["\']\s*:', text) or re.search(r'\bmessage\s*=', text):
                        embedded_payload_detected = True

        # Embedded payload inspection for JSON-like events
        if isinstance(parsed_obj, dict):
            msg = parsed_obj.get("message")
            raw = parsed_obj.get("raw")
            for payload in (msg, raw):
                if payload is None:
                    continue
                if isinstance(payload, dict):
                    embedded_payload_detected = True
                    fields.update(str(k) for k in payload.keys())
                    continue
                if not isinstance(payload, str):
                    continue
                payload_s = payload.strip()
                if not payload_s:
                    continue
                embedded_payload_detected = True
                if payload_s[:1] in "{[":
                    try:
                        parsed_payload = json.loads(payload_s)
                        if isinstance(parsed_payload, dict):
                            fields.update(str(k) for k in parsed_payload.keys())
                            continue
                    except Exception:
                        pass
                kv = _extract_kv_pairs(payload_s)
                fields.update(kv.keys())

        combined = f"{text}".lower()
        if "akamai" in combined and "dns" in combined:
            hints.add("akamai_dns")
        elif "akamai" in combined and ("cdn" in combined or "reqmethod" in combined or "statuscode" in combined):
            hints.add("akamai_http")
        if "defender" in combined or "actiontype" in combined or "processcommandline" in combined:
            hints.add("ms_defender")
        if "duo" in combined or "auth_protocol" in combined or "mfa" in combined:
            hints.add("authentication")

    return {
        "formats": sorted(formats),
        "embedded_payload_detected": embedded_payload_detected,
        "extracted_fields": sorted(fields),
        "record_hints": sorted(hints),
    }


# ---------------------------------------------------------------------------
# Example Selector
# ---------------------------------------------------------------------------

class ExampleSelector:
    """Finds the best matching Lua scripts as few-shot examples."""

    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path("output")
        self._index: Optional[List[Dict]] = None

    def _build_index(self) -> List[Dict]:
        """Index all transform.lua files by metadata."""
        if self._index is not None:
            return self._index

        self._index = []
        for lua_path in self.output_dir.glob("*/transform.lua"):
            code = lua_path.read_text(encoding="utf-8", errors="replace")
            if len(code) < 50:
                continue

            # Extract class_uid
            class_uid = None
            m = re.search(r'class_uid\s*=\s*(\d+)', code)
            if m:
                class_uid = int(m.group(1))
            m2 = re.search(r'OCSF_CLASS_UID\s*=\s*(\d+)', code)
            if m2:
                class_uid = int(m2.group(1))

            # Detect signature
            from components.testing_harness.lua_signature import detect_entry_signature
            sig_info = detect_entry_signature(code)
            sig = sig_info.name or "unknown"

            # Extract vendor from header comments
            vendor = ""
            vm = re.search(r'Vendor:\s*(\w+)', code)
            if vm:
                vendor = vm.group(1).lower()

            parser_name = lua_path.parent.name
            line_count = len(code.splitlines())

            self._index.append({
                "parser_name": parser_name,
                "path": str(lua_path),
                "class_uid": class_uid,
                "signature": sig,
                "vendor": vendor,
                "line_count": line_count,
                "code": code,
            })

        return self._index

    def select(
        self,
        target_class_uid: int,
        target_vendor: str = "",
        target_signature: str = "process",
        max_examples: int = 2,
    ) -> List[Dict]:
        """Select best matching examples by OCSF class, vendor, and signature."""
        index = self._build_index()
        if not index:
            return []

        target_vendor_lower = target_vendor.lower()

        scored = []
        for entry in index:
            score = 0
            # Same OCSF class: highest priority
            if entry["class_uid"] == target_class_uid:
                score += 50
            # Same category_uid (secondary signal)
            elif entry["class_uid"] and target_class_uid:
                entry_cat = entry["class_uid"] // 1000
                target_cat = target_class_uid // 1000
                if entry_cat == target_cat:
                    score += 20
            # Same vendor family
            if target_vendor_lower and entry["vendor"] and target_vendor_lower in entry["vendor"]:
                score += 40
            elif target_vendor_lower and entry["parser_name"] and target_vendor_lower in entry["parser_name"]:
                score += 25
            # Matching signature (prefer processEvent)
            if entry["signature"] == target_signature:
                score += 15
            # Prefer scripts with more content (likely more complete)
            if entry["line_count"] > 50:
                score += 10
            # Penalize very large scripts (harder to use as examples)
            if entry["line_count"] > 300:
                score -= 5

            scored.append((score, entry))

        scored.sort(key=lambda x: -x[0])

        # Take top N, truncating each to ~150 lines
        results = []
        for _score, entry in scored[:max_examples]:
            code = entry["code"]
            lines = code.splitlines()
            if len(lines) > 150:
                code = "\n".join(lines[:150]) + "\n-- ... (truncated)"
            results.append({**entry, "code": code})

        return results


# ---------------------------------------------------------------------------
# Agent Lua Cache
# ---------------------------------------------------------------------------

class AgentLuaCache:
    """Disk-based cache for agent-generated Lua scripts."""

    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or Path("output/agent_lua_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _slug(self, parser_name: str) -> str:
        return re.sub(r'[^a-zA-Z0-9_-]', '_', parser_name)

    def get(self, parser_name: str) -> Optional[Dict]:
        path = self.cache_dir / f"{self._slug(parser_name)}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def put(self, parser_name: str, data: Dict) -> None:
        path = self.cache_dir / f"{self._slug(parser_name)}.json"
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def delete(self, parser_name: str) -> None:
        path = self.cache_dir / f"{self._slug(parser_name)}.json"
        path.unlink(missing_ok=True)

    def stats(self) -> Dict:
        cached = list(self.cache_dir.glob("*.json"))
        scores = []
        for p in cached:
            try:
                d = json.loads(p.read_text())
                scores.append(d.get("confidence_score", 0))
            except Exception:
                pass
        return {
            "cached_count": len(cached),
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "min_score": min(scores) if scores else 0,
            "max_score": max(scores) if scores else 0,
        }


# ---------------------------------------------------------------------------
# Prompt Builder
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert Observo.ai Lua transformation engineer. You write production-quality \
Lua scripts that transform security log events into OCSF (Open Cybersecurity Schema Framework) format.

IMPORTANT — Observo Lua API:
- Entry function MUST be `function processEvent(event)` — this is the ONLY valid signature
- Events are Lua tables; access via dot notation: `event.field`, `event.nested.field`
- Fields with dots in names must be quoted: `event["user.name"]`
- Return the result table to pass downstream, return `nil` to discard
- Do NOT use `event:get(...)` or `event:set(...)` (unsupported and will crash)
- Do NOT rely on external modules or `require(...)` calls; script must be self-contained

Your scripts must:
- Use `function processEvent(event)` as the ONLY entry point
- Set ALL required OCSF fields: class_uid, category_uid, activity_id, time, type_uid, severity_id
- Compute type_uid as: class_uid * 100 + activity_id
- Set severity_id (0=Unknown, 1=Informational, 2=Low, 3=Medium, 4=High, 5=Critical, 6=Fatal, 99=Other)
- Set time as milliseconds since epoch (numeric)
- Include class_name, category_name, activity_name as descriptive strings
- Use local variables exclusively (no globals except the entry function and top-level constants)
- Handle nil/missing fields gracefully with type checks
- Put unmapped fields in an `unmapped` table to preserve data
- Define every helper you call ABOVE `processEvent` (e.g., `getNestedField`, `setNestedField`)
- Wrap transformation logic in `pcall` and set `event["lua_error"] = tostring(err)` on failure
- Use `tostring(...)` for string concatenation and `tonumber(...) or 0` for arithmetic inputs
- Guard `os.time({...})` / `os.date(...)` with `pcall` and use safe fallback
- If random is used, call `math.randomseed(...)` once at top-level, never per event
- Be optimized for 10,000+ events/sec throughput

""" + get_helpers_for_prompt() + """

=== PATTERN A: Table-Driven Mapping (RECOMMENDED) ===

Use this for most parsers. Define all mappings as data, iterate once:

```lua
local fieldMappings = {
    {type = "direct", source = "sourceIPAddress", target = "src_endpoint.ip"},
    {type = "direct", source = "userName", target = "actor.user.name"},
    {type = "priority", source1 = "userIdentity.userName", source2 = "userIdentity.arn", target = "actor.user.name"},
    {type = "computed", target = "class_uid", value = 6003},
}

function processEvent(event)
    if type(event) ~= "table" then return nil end

    local result = {}
    local mappedPaths = {}

    for _, mapping in ipairs(fieldMappings) do
        if mapping.type == "direct" then
            local value = getNestedField(event, mapping.source)
            if value ~= nil then setNestedField(result, mapping.target, value) end
            mappedPaths[mapping.source] = true
        elseif mapping.type == "priority" then
            local value = getNestedField(event, mapping.source1)
            if value == nil and mapping.source2 then value = getNestedField(event, mapping.source2) end
            if value ~= nil then setNestedField(result, mapping.target, value) end
            mappedPaths[mapping.source1] = true
            if mapping.source2 then mappedPaths[mapping.source2] = true end
        elseif mapping.type == "computed" then
            setNestedField(result, mapping.target, mapping.value)
        end
    end

    -- Set OCSF required defaults
    local function setDefault(path, val)
        if getNestedField(result, path) == nil then setNestedField(result, path, val) end
    end
    setDefault('class_uid', CLASS_UID)
    setDefault('category_uid', CATEGORY_UID)
    setDefault('activity_id', 99)
    setDefault('type_uid', CLASS_UID * 100 + 99)
    setDefault('severity_id', 0)
    setDefault('class_name', 'API Activity')
    setDefault('category_name', 'Application Activity')
    setDefault('activity_name', event.eventName or '')

    -- Time: convert ISO to ms (guarded for Observo runtime compatibility)
    local eventTime = getNestedField(event, 'eventTime') or getNestedField(event, 'timestamp')
    if eventTime then
        local yr,mo,dy,hr,mn,sc = eventTime:match("(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)")
        if yr then
            local okTime, ts = pcall(function()
                return os.time({year=tonumber(yr),month=tonumber(mo),day=tonumber(dy),
                                hour=tonumber(hr),min=tonumber(mn),sec=tonumber(sc),isdst=false})
            end)
            if okTime and ts then result.time = ts * 1000 end
        end
    end
    if not result.time then
        local okNow, nowTs = pcall(function() return os.time() end)
        result.time = ((okNow and nowTs) and nowTs or 0) * 1000
    end

    -- Unmapped fields
    copyUnmappedFields(event, mappedPaths, result)

    return result
end
```

=== PATTERN B: Event-Type Dispatch (for multi-format parsers) ===

When one parser handles multiple event types (e.g., Azure AD has signin, audit, provisioning):

```lua
function processEvent(event)
    if not event then return nil end
    local eventType = detect_event_type(event)
    local mappings = EVENT_TYPE_MAPPINGS[eventType]
    if not mappings then
        -- Unknown type: pass through with minimal OCSF
        return getDefaultMapping(event)
    end
    for _, mapping in ipairs(mappings) do ... end
    return result
end
```

=== PATTERN C: Safety Wrapper with pcall ===

Wrap all logic in pcall so errors don't drop events:

```lua
function processEvent(event)
    local function execute_transform(e)
        -- ... all transformation logic ...
        return result
    end
    local status, res = pcall(execute_transform, event)
    if status then return res
    else
        event["_error_msg"] = "LUA_ERR: " .. tostring(res)
        return event
    end
end
```

=== PATTERN D: Severity Mapping (lookup table) ===

```lua
local function getSeverityId(level)
    if level == nil then return 0 end
    local severityMap = {Critical=5, High=4, Medium=3, Warning=99, Low=2, Information=1, Informational=1, Error=6}
    return severityMap[level] or 0
end
```

=== PATTERN E: Observables (OCSF enrichment) ===

```lua
local observables = {}
if event.sourceIPAddress then
    table.insert(observables, {type_id=2, type="IP Address", name="src_endpoint.ip", value=event.sourceIPAddress})
end
if event.userName then
    table.insert(observables, {type_id=4, type="User Name", name="actor.user.name", value=event.userName})
end
result.observables = observables
```

Output ONLY the Lua code. No markdown fences, no explanations outside comments."""


def build_generation_prompt(
    parser_name: str,
    vendor: str,
    product: str,
    class_uid: int,
    class_name: str,
    ocsf_fields: Dict,
    source_fields: List[Dict],
    ingestion_mode: str,
    examples: Optional[List[Dict]] = None,
    deterministic_preflight: Optional[Dict[str, Any]] = None,
) -> str:
    """Build the generation prompt. Production patterns are in SYSTEM_PROMPT, not here."""

    signature = "processEvent(event)"
    emit_or_return = "return result"

    # Format source fields
    field_list = "\n".join(
        f"  - {f['name']} ({f.get('type', 'string')})" for f in source_fields[:40]
    ) if source_fields else "  (no specific fields known - extract from event data)"

    # Format OCSF required/optional fields
    required = ocsf_fields.get("required_fields", [])
    if not required:
        required = ["class_uid", "category_uid", "activity_id", "time", "type_uid", "severity_id"]
    optional = ocsf_fields.get("optional_fields", [])[:25]
    category_uid = ocsf_fields.get("category_uid", 1)
    category_name = ocsf_fields.get("category_name", "Unknown")
    ocsf_section = (
        f"Required OCSF fields: {', '.join(required)}\n"
        f"Common optional fields: {', '.join(optional[:20])}\n"
        f"class_name = \"{class_name}\", category_name = \"{category_name}\"\n"
        f"type_uid formula: class_uid * 100 + activity_id\n"
        f"severity_id: 0=Unknown, 1=Informational, 2=Low, 3=Medium, 4=High, 5=Critical\n"
        f"time: milliseconds since epoch (numeric)"
    )

    sample_section = ""
    if examples:
        rendered = []
        for idx, ex in enumerate(examples[:3], 1):
            if isinstance(ex, (dict, list)):
                text = json.dumps(ex, ensure_ascii=False)[:1500]
            else:
                text = str(ex)[:1500]
            rendered.append(f"  Example {idx}: {text}")
        sample_section = "\nSAMPLE INPUT EXAMPLES:\n" + "\n".join(rendered) + "\n"

    preflight_section = ""
    if deterministic_preflight:
        preflight_section = (
            "\nDETERMINISTIC PREFLIGHT (must honor these before coding):\n"
            f"- Detected formats: {', '.join(deterministic_preflight.get('formats') or ['unknown'])}\n"
            f"- Record hints: {', '.join(deterministic_preflight.get('record_hints') or ['none'])}\n"
            f"- Embedded payload detected: {bool(deterministic_preflight.get('embedded_payload_detected'))}\n"
            f"- Extracted candidate fields: {', '.join((deterministic_preflight.get('extracted_fields') or [])[:40])}\n"
        )

    source_guidance = _build_source_specific_guidance(
        parser_name=parser_name,
        vendor=vendor,
        product=product,
        class_uid=class_uid,
        class_name=class_name,
    )

    prompt = f"""Generate a Lua transformation script for the following parser:

PARSER: {parser_name}
VENDOR: {vendor or 'Unknown'}
PRODUCT: {product or 'Unknown'}
FUNCTION SIGNATURE: {signature}

TARGET OCSF CLASS: {class_name} (class_uid={class_uid})
{ocsf_section}

SOURCE FIELDS AVAILABLE:
{field_list}
{sample_section}
{preflight_section}

REQUIREMENTS:
1. Use `function {signature}` as the ONLY entry point (Observo Lua API)
2. Set class_uid = {class_uid}, category_uid = {category_uid}
3. Set class_name = "{class_name}", category_name = "{category_name}"
4. Map source fields to OCSF fields listed above
5. Compute type_uid = class_uid * 100 + activity_id
6. Set severity_id based on event severity/priority (0-6 range)
7. Set `time` as milliseconds since epoch from the event timestamp
8. Set activity_name as a descriptive string for the activity
9. Put unmapped fields in an `unmapped` table
10. Clean empty tables and nil values before returning
11. End with `{emit_or_return}`
12. Use local variables, handle nil checks, add comments
13. Never use `event:get(...)` or `event:set(...)`; use table access only
14. Define all helper functions above `processEvent` (no undefined globals)
15. Wrap main transform logic in `pcall`; on error set `event["lua_error"]`
16. Guard `os.time({{...}})` and `os.date(...)` calls with `pcall`
17. Use `tostring(...)` for concatenation and `tonumber(...) or 0` for numeric math
18. Avoid placeholder output values like "Unknown Process"/"Unknown UID" when source fields exist
19. Always evaluate embedded payloads in `message`/`raw` fields regardless of data type:
    - if string: parse JSON first, then key=value tokens
    - if table/object: read nested fields directly
    - if scalar: preserve as evidence and continue mapping from other fields
{source_guidance}

Generate the complete Lua script now."""

    return prompt


def _build_source_specific_guidance(
    parser_name: str,
    vendor: str,
    product: str,
    class_uid: int,
    class_name: str,
) -> str:
    """Build source-aware mapping guidance for high-value parser families."""
    combined = f"{parser_name} {vendor} {product}".lower()
    directives: List[str] = []

    if "duo" in combined:
        directives.extend([
            "- Source-specific guidance (Cisco Duo): prioritize authentication semantics",
            "- Enforce `class_uid=3002` and authentication activity naming based on auth outcome",
            "- Map `actor.user.name` from user/account fields and `src_endpoint.ip` from client/source IP",
            "- Map status/auth method/MFA details when present (do not collapse into generic finding output)",
        ])

    if "defender" in combined or "mdatp" in combined or "microsoft_365_defender" in combined:
        directives.extend([
            "- Source-specific guidance (Microsoft Defender): use ActionType/ProcessName/Device* fields directly",
            "- Derive `activity_name` from ActionType and prefer concrete finding title/uid over placeholders",
            "- Preserve process/device/network evidence as mapped OCSF fields before fallback to `unmapped`",
        ])

    if "akamai" in combined and "dns" in combined:
        directives.extend([
            "- Source-specific guidance (Akamai DNS): target DNS Activity semantics",
            "- Enforce `class_uid=4003` and map DNS query/answer/rcode/src fields when available",
            "- Parse key/value pairs embedded in message text when structured fields are missing",
            "- Treat Akamai DNS aliases explicitly: `cliIP`->`src_endpoint.ip`, `domain`->`query.hostname`, `recordType`->`query.type`, `responseCode`->`rcode`/`rcode_id`",
            "- If `cliIP` is present in message payload, `src_endpoint.ip` must not be left blank",
        ])
    elif "akamai" in combined and ("cdn" in combined or "http" in combined):
        directives.extend([
            "- Source-specific guidance (Akamai CDN/HTTP): target HTTP Activity semantics",
            "- Enforce `class_uid=4002` and map method/host/path/status/src_ip/user_agent where available",
            "- Parse key/value pairs embedded in message text when structured fields are missing",
            "- Treat Akamai HTTP aliases explicitly: `cliIP`->`src_endpoint.ip`, `reqMethod`->`http_request.http_method`, `reqHost`/`domain`->`http_request.url` or host context, `responseCode`->`http_response.code`",
        ])

    if not directives:
        directives.append(
            f"- Source-specific guidance: align mappings with class `{class_name}` (class_uid={class_uid}) and avoid generic catch-all output"
        )

    return "\n".join(directives)


def build_refinement_prompt(
    lua_code: str,
    score: int,
    harness_errors: Dict,
) -> str:
    """Build a refinement prompt from harness feedback."""

    issues = []

    # Validity errors
    validity = harness_errors.get("lua_validity", {})
    for err in validity.get("errors", []):
        issues.append(f"SYNTAX ERROR: {err}")

    # Lint issues (errors only)
    linting = harness_errors.get("lua_linting", {})
    for issue in linting.get("issues", []):
        if issue.get("severity") == "error":
            issues.append(f"LINT ERROR (line {issue.get('line', '?')}): {issue['message']}")

    # Missing OCSF fields
    ocsf = harness_errors.get("ocsf_mapping", {})
    missing = ocsf.get("missing_required", [])
    if missing:
        issues.append(f"MISSING REQUIRED OCSF FIELDS: {', '.join(missing)}")

    # Test execution failures
    test_exec = harness_errors.get("test_execution", {})
    for result in test_exec.get("results", []):
        if result.get("status") != "passed" and result.get("error"):
            issues.append(f"TEST FAILURE ({result.get('test_name', '?')}): {result['error']}")

    issue_text = "\n".join(f"  - {i}" for i in issues) if issues else "  (no specific errors)"

    return f"""The Lua script you generated scored {score}/100. Fix the following issues:

ISSUES FOUND:
{issue_text}

ORIGINAL SCRIPT:
```lua
{lua_code}
```

Generate the FIXED Lua script. Keep the same function signature and structure. \
Output ONLY the Lua code, no markdown fences."""


# ---------------------------------------------------------------------------
# Agentic Lua Generator
# ---------------------------------------------------------------------------

class AgenticLuaGenerator:
    """
    LLM agent that generates OCSF-compliant Lua with iterative refinement.

    Uses Claude to generate Lua, validates with the testing harness,
    and iterates on failures up to max_iterations times.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-haiku-20240307",
        provider: str = "anthropic",
        max_output_tokens: int = 3000,
        max_iterations: int = 3,
        score_threshold: int = 70,
        output_dir: Path = None,
    ):
        self.provider = provider
        self.api_key = api_key
        self.client = Anthropic(api_key=api_key) if provider == "anthropic" else None
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.max_iterations = max_iterations
        self.score_threshold = score_threshold

        self.output_dir = output_dir or Path("output")
        self.harness = HarnessOrchestrator()
        self.cache = AgentLuaCache(self.output_dir / "agent_lua_cache")
        self.source_analyzer = SourceParserAnalyzer()

    def generate(
        self,
        parser_entry: Dict[str, Any],
        force_regenerate: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate OCSF-compliant Lua for a parser entry.

        Args:
            parser_entry: Parser data from ai_siem_parser_source_components.json
            force_regenerate: Bust cache and regenerate

        Returns:
            Dict with lua_code, confidence_score, harness_report, iterations, etc.
        """
        parser_name = parser_entry.get("parser_name", "unknown")

        # Check cache first (auto-bust if below threshold or missing processEvent)
        if not force_regenerate:
            cached = self.cache.get(parser_name)
            if cached:
                cached_score = cached.get("confidence_score", 0)
                cached_lua = cached.get("lua_code", "")
                has_processEvent = "function processEvent" in cached_lua
                if cached_score >= self.score_threshold and has_processEvent:
                    logger.info(f"Cache hit for {parser_name} (score={cached_score})")
                    return cached
                else:
                    logger.info(
                        f"Cache bust for {parser_name}: score={cached_score} "
                        f"(threshold={self.score_threshold}), processEvent={has_processEvent}"
                    )
                    self.cache.delete(parser_name)

        logger.info(f"Starting agentic Lua generation for {parser_name}")
        start = time.time()

        # 1. Classify OCSF class
        vendor = ""
        product = ""
        config = parser_entry.get("config", parser_entry)
        attrs = config.get("attributes", {})
        ds = attrs.get("dataSource", {})
        vendor = ds.get("vendor", "")
        product = ds.get("product", "")

        ingestion_mode = parser_entry.get("ingestion_mode", "push")

        # 3. Analyze source fields
        source_info = self.source_analyzer.analyze_parser(parser_entry)
        source_fields = source_info.get("fields", [])
        prompt_examples: List[Any] = []
        prompt_examples.extend(parser_entry.get("raw_examples", []) or [])
        prompt_examples.extend(parser_entry.get("historical_examples", []) or [])
        preflight = _infer_sample_preflight(prompt_examples)

        # Merge deterministic preflight fields into source-field inventory.
        known_names = {str(f.get("name")) for f in source_fields if isinstance(f, dict) and f.get("name")}
        for fname in preflight.get("extracted_fields", []):
            if fname not in known_names:
                source_fields.append({"name": fname, "type": "string", "source": "deterministic_preflight"})
                known_names.add(fname)

        sample_hint_text = " ".join(str(x)[:1500] for x in prompt_examples[:3])
        class_uid, class_name = classify_ocsf_class(
            parser_name,
            vendor,
            product,
            sample_text=sample_hint_text,
        )
        logger.info(
            "Classified %s with sample hints: class=%s(%s), mode=%s",
            parser_name, class_name, class_uid, ingestion_mode
        )
        # 2. Get OCSF schema for final target class
        registry = OCSFSchemaRegistry()
        ocsf_class = registry.get_class(class_uid) or {}
        # 4. Build prompt (production patterns are baked into SYSTEM_PROMPT)
        prompt = build_generation_prompt(
            parser_name=parser_name,
            vendor=vendor,
            product=product,
            class_uid=class_uid,
            class_name=class_name,
            ocsf_fields=ocsf_class,
            source_fields=source_fields,
            ingestion_mode=ingestion_mode,
            examples=prompt_examples,
            deterministic_preflight=preflight,
        )

        # 5. Inject prior user corrections into the prompt (if any)
        corrections_applied = 0
        try:
            corrections = read_corrections_for_prompt(
                parser_name=parser_name,
                ocsf_class_uid=class_uid,
                vendor=vendor,
            )
            if corrections:
                corrections_applied = len(corrections)
                prompt += "\n\nPrior corrections to honor:"
                for idx, c in enumerate(corrections, 1):
                    prompt += "\n  (%d) %s" % (idx, c)
                logger.info(
                    "Injected %d prior corrections for %s",
                    corrections_applied, parser_name,
                )
        except Exception:
            pass

        # Iterative generation loop (with optional model escalation)
        best_result = None
        best_score = -1
        iteration_history = []
        model_candidates = self._get_model_candidates()
        accepted = False
        total_iterations = 0

        for model_index, active_model in enumerate(model_candidates, start=1):
            logger.info(
                "Using model tier %d/%d for %s: %s",
                model_index,
                len(model_candidates),
                parser_name,
                active_model,
            )
            messages = [{"role": "user", "content": prompt}]

            for _ in range(self.max_iterations):
                total_iterations += 1
                logger.info(
                    "Iteration %d for %s using model %s",
                    total_iterations,
                    parser_name,
                    active_model,
                )

                # Call configured LLM provider
                lua_code = self._call_llm(messages, model_override=active_model)
                if not lua_code:
                    logger.error(
                        "LLM returned no code on iteration %d with model %s",
                        total_iterations,
                        active_model,
                    )
                    break

                # Clean the response
                lua_code = self._clean_lua_response(lua_code)

                # Validate with harness
                report = self.harness.run_all_checks(
                    lua_code=lua_code,
                    parser_config=parser_entry,
                    ocsf_version="1.3.0",
                )
                score = report.get("confidence_score", 0)
                grade = report.get("confidence_grade", "F")
                field_cmp = report.get("checks", {}).get("field_comparison", {}) or {}
                source_cov = float(field_cmp.get("coverage_pct", 100) or 100)
                has_embedded = bool(preflight.get("embedded_payload_detected"))
                low_cov_for_embedded = has_embedded and source_cov < 40

                logger.info("Iteration %d: score=%s%% grade=%s", total_iterations, score, grade)

                # Track iteration history
                missing_fields = report.get("checks", {}).get("ocsf_mapping", {}).get("missing_required", [])
                lint_errors = [i["message"] for i in report.get("checks", {}).get("lua_linting", {}).get("issues", []) if i.get("severity") == "error"]
                iteration_history.append({
                    "iteration": total_iterations,
                    "score": score,
                    "model": active_model,
                    "issues_remaining": missing_fields + lint_errors,
                })

                # Track best result
                if score > best_score:
                    best_score = score
                    best_result = {
                        "parser_name": parser_name,
                        "lua_code": lua_code,
                        "confidence_score": score,
                        "confidence_grade": grade,
                        "ocsf_class_uid": class_uid,
                        "ocsf_class_name": class_name,
                        "ingestion_mode": ingestion_mode,
                        "vendor": vendor,
                        "product": product,
                        "iterations": total_iterations,
                        "corrections_applied": corrections_applied,
                        "generation_method": "agentic_llm",
                        "model": active_model,
                        "generated_at": datetime.utcnow().isoformat() + "Z",
                        "harness_report": report,
                    }

                # Check if good enough
                if score >= self.score_threshold and not low_cov_for_embedded:
                    logger.info(
                        "Score %s%% >= threshold %s%% - accepting",
                        score,
                        self.score_threshold,
                    )
                    accepted = True
                    break
                if score >= self.score_threshold and low_cov_for_embedded:
                    logger.info(
                        "Score passed threshold but rejected due to low source coverage %.1f%% with embedded payload present",
                        source_cov,
                    )

                # Build refinement prompt for next iteration
                refinement = build_refinement_prompt(lua_code, score, report.get("checks", {}))
                if low_cov_for_embedded:
                    refinement += (
                        "\n\nCRITICAL COVERAGE ISSUE:\n"
                        f"- Embedded message/raw payload detected in samples, but source coverage is only {source_cov:.1f}%.\n"
                        "- You MUST parse embedded payload fields (JSON and key=value) and map concrete source fields.\n"
                        "- Do not rely on default-only required OCSF fields with broad unmapped fallback.\n"
                    )
                # Add iteration history so the model doesn't re-introduce fixed issues
                if len(iteration_history) > 1:
                    history_text = "\n".join(
                        f"  Iteration {h['iteration']} ({h['model']}): score={h['score']}%, issues: {h['issues_remaining'][:5]}"
                        for h in iteration_history[-4:]
                    )
                    refinement += f"\n\nITERATION HISTORY (do not re-introduce previously fixed issues):\n{history_text}"
                messages.append({"role": "assistant", "content": lua_code})
                messages.append({"role": "user", "content": refinement})

            if accepted:
                break

            if model_index < len(model_candidates):
                logger.info(
                    "Escalating model for %s after best score %s%% with model %s",
                    parser_name,
                    max([h["score"] for h in iteration_history if h["model"] == active_model], default=-1),
                    active_model,
                )

        elapsed = time.time() - start

        if best_result:
            best_result["elapsed_seconds"] = round(elapsed, 2)
            best_result["quality"] = "accepted" if best_score >= self.score_threshold else "below_threshold"

            # Cache the result
            self.cache.put(parser_name, best_result)
            logger.info(
                f"Completed {parser_name}: score={best_score}%, "
                f"iterations={best_result['iterations']}, time={elapsed:.1f}s"
            )
        else:
            best_result = {
                "parser_name": parser_name,
                "error": "Failed to generate Lua code",
                "confidence_score": 0,
                "elapsed_seconds": round(elapsed, 2),
            }

        return best_result

    def _call_llm(self, messages: List[Dict], model_override: Optional[str] = None) -> Optional[str]:
        """Call configured provider and return response text."""
        active_model = model_override or self.model
        if self.provider == "openai":
            return self._call_openai(messages, active_model)
        return self._call_anthropic(messages, active_model)

    def _call_anthropic(self, messages: List[Dict], model: str) -> Optional[str]:
        """Call Anthropic API and return response text."""
        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=self.max_output_tokens,
                system=SYSTEM_PROMPT,
                messages=messages,
            )
            if response.content:
                return response.content[0].text
            return None
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            return None

    def _call_openai(self, messages: List[Dict], model: str) -> Optional[str]:
        """Call OpenAI chat completions API and return response text."""
        try:
            openai_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": openai_messages,
                    "max_tokens": self.max_output_tokens,
                    "temperature": 0.1,
                },
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                return None
            message = choices[0].get("message", {})
            content = message.get("content")
            if isinstance(content, str):
                return content
            return None
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return None

    def _get_model_candidates(self) -> List[str]:
        """Return cheap-first model candidates.

        Stronger fallback models are opt-in via environment variables so cost
        does not spike implicitly during routine workbench usage.
        """
        candidates: List[str] = []
        if self.model:
            candidates.append(self.model)

        if self.provider == "anthropic":
            strong = (os.environ.get("ANTHROPIC_STRONG_MODEL") or "").strip()
        else:
            strong = (os.environ.get("OPENAI_STRONG_MODEL") or "").strip()

        if strong and strong not in candidates:
            candidates.append(strong)
        return candidates

    def _clean_lua_response(self, text: str) -> str:
        """Strip markdown fences and non-Lua content from Claude's response."""
        # Remove markdown code fences
        text = re.sub(r'^```\w*\s*\n?', '', text, flags=re.MULTILINE)
        text = re.sub(r'\n?```\s*$', '', text, flags=re.MULTILINE)

        # If there's JSON metrics after the Lua, strip it
        json_start = text.find('\n{')
        if json_start > 0 and '"performance_metrics"' in text[json_start:]:
            text = text[:json_start]

        return text.strip()

    def get_cache_stats(self) -> Dict:
        return self.cache.stats()

    def bust_cache(self, parser_name: str) -> None:
        self.cache.delete(parser_name)
