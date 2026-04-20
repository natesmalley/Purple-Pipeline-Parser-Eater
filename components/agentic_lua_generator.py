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

from components.testing_harness import (
    HarnessOrchestrator,
    OCSFSchemaRegistry,
    OCSFFieldAnalyzer,
    SourceParserAnalyzer,
)
from components.source_family_registry import (
    apply_source_family_defaults,
    find_source_family_guidance_profiles,
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
    """Finds the best matching Lua scripts as few-shot examples.

    Indexes scripts from one or more source directories. Canonical reference
    directories (e.g. ``data/harness_examples/observo_serializers``) are
    prioritized over historical generations so that production Observo style
    outranks older harness outputs.
    """

    # Default canonical reference directories. Scripts here are treated as
    # reference patterns for single-shot generation. Ordered by authority:
    #
    # 1. ``observo_serializers/`` — captured from the Observo platform UI
    #    (OCSF Serializer + OCSF Serializer Extended dropdowns). Highest
    #    authority, production-shipping Lua.
    # 2. ``observo_serializers_agent/`` — generated by this repo's
    #    AgenticLuaGenerator over previous runs. Large coverage (~110+
    #    parsers across 7 OCSF classes), processEvent contract, graded
    #    B on sampled assessment.
    # 3. ``observo_serializers_orion/`` — generated by Observo's built-in
    #    Orion AI on demand (2026-04-19 session). Correct structure,
    #    typically C-grade with some placeholder issues.
    DEFAULT_REFERENCE_DIRS: List[Path] = [
        Path("data/harness_examples/observo_serializers"),
        Path("data/harness_examples/observo_serializers_agent"),
        Path("data/harness_examples/observo_serializers_orion"),
    ]

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        reference_dirs: Optional[List[Path]] = None,
    ):
        self.output_dir = output_dir or Path("output")
        if reference_dirs is None:
            self.reference_dirs = [
                p for p in self.DEFAULT_REFERENCE_DIRS if Path(p).exists()
            ]
        else:
            self.reference_dirs = [Path(p) for p in reference_dirs]
        self._index: Optional[List[Dict]] = None

    def _index_dir(self, base: Path, is_reference: bool) -> List[Dict]:
        """Scan a directory for ``*/transform.lua`` and build index entries.

        If a ``manifest.json`` sits next to the per-parser subdirs, entries
        carrying ``class_uid_concern: true`` are loaded with that flag so
        the selector can de-prioritize them when a cleaner alternative is
        available at the same class.
        """
        entries: List[Dict] = []
        if not base.exists():
            return entries

        # Load manifest concerns keyed by slug, if present.
        concerns_by_slug: Dict[str, Dict[str, Any]] = {}
        manifest_path = base / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                for entry in (manifest.get("serializers") or []):
                    if entry.get("class_uid_concern"):
                        concerns_by_slug[entry["slug"]] = {
                            "alternative_class_uid": entry.get("alternative_class_uid"),
                            "concern_note": entry.get("concern_note"),
                            "concern_source": entry.get("concern_source"),
                            "kept_as_production_truth": entry.get("kept_as_production_truth", False),
                        }
            except Exception:  # pragma: no cover — defensive
                pass

        for lua_path in sorted(base.glob("*/transform.lua")):
            try:
                code = lua_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
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

            entry = {
                "parser_name": parser_name,
                "path": str(lua_path),
                "class_uid": class_uid,
                "signature": sig,
                "vendor": vendor,
                "line_count": line_count,
                "code": code,
                "is_reference": is_reference,
                "class_uid_concern": False,
            }
            # Merge manifest concern flags if any.
            concern = concerns_by_slug.get(parser_name)
            if concern:
                entry["class_uid_concern"] = True
                entry["alternative_class_uid"] = concern.get("alternative_class_uid")
                entry["concern_note"] = concern.get("concern_note")
                entry["concern_source"] = concern.get("concern_source")
                entry["kept_as_production_truth"] = concern.get("kept_as_production_truth", False)
            entries.append(entry)
        return entries

    def _build_index(self) -> List[Dict]:
        """Index canonical references first, then historical ``output/``."""
        if self._index is not None:
            return self._index

        self._index = []
        for ref_dir in self.reference_dirs:
            self._index.extend(self._index_dir(Path(ref_dir), is_reference=True))
        self._index.extend(self._index_dir(self.output_dir, is_reference=False))
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
            # Canonical Observo references always outrank historical output/
            if entry.get("is_reference"):
                score += 35
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

            # De-prioritize scripts whose OCSF classification was flagged
            # in the manifest (e.g. by the 2026-04-19 Orion review). The
            # penalty is small enough that the script still appears when
            # no better reference exists at the same class, but a clean
            # alternative at the same class outranks it.
            if entry.get("class_uid_concern"):
                score -= 15

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

GPT5_SYSTEM_PROMPT = """You generate Observo-compatible Lua transformation scripts.

Hard requirements:
- Only valid entry point: `function processEvent(event)`
- Return the transformed result table, or `nil` to drop
- Output only the requested format for the current step
- Prefer the smallest correct script over broad helper-heavy templates
- Do not invent placeholder values when source data exists
- Every final Lua script must set required OCSF fields: class_uid, category_uid, activity_id, time, type_uid, severity_id
- `type_uid = class_uid * 100 + activity_id`
- Parse embedded payloads in `message` or `raw` fields when they contain JSON or key=value data
- Keep Observo runtime compatibility: no `event:get`, no external modules, nil-safe logic, guarded `os.time`
"""

GPT5_PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "class_uid",
        "class_name",
        "category_uid",
        "category_name",
        "activity_id",
        "activity_name",
        "timestamp_sources",
        "severity_strategy",
        "embedded_payload_strategy",
        "mappings",
        "notes",
    ],
    "properties": {
        "class_uid": {"type": "integer"},
        "class_name": {"type": "string"},
        "category_uid": {"type": "integer"},
        "category_name": {"type": "string"},
        "activity_id": {"type": "integer"},
        "activity_name": {"type": "string"},
        "timestamp_sources": {
            "type": "array",
            "items": {"type": "string"},
        },
        "severity_strategy": {"type": "string"},
        "embedded_payload_strategy": {"type": "string"},
        "mappings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["target", "source_candidates", "transform", "required"],
                "properties": {
                    "target": {"type": "string"},
                    "source_candidates": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "transform": {"type": "string"},
                    "required": {"type": "boolean"},
                },
            },
        },
        "notes": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
}


def _normalize_openai_reasoning_effort(model: str, effort: str) -> Tuple[Optional[str], Optional[str]]:
    """Normalize reasoning effort to a value supported by the target GPT-5 family model."""
    normalized_model = (model or "").strip().lower()
    normalized_effort = (effort or "").strip().lower()
    if not normalized_effort:
        return None, None

    supported_efforts = {"minimal", "low", "medium", "high", "xhigh"}
    if normalized_model.startswith("gpt-5.1"):
        supported_efforts.add("none")

    if normalized_effort in supported_efforts:
        return normalized_effort, None

    if normalized_effort == "none" and normalized_model.startswith("gpt-5"):
        return "minimal", (
            f"OPENAI_REASONING_EFFORT=none is unsupported for {model}; "
            "using minimal instead"
        )

    return None, f"Ignoring unsupported OPENAI_REASONING_EFFORT={effort!r} for {model}"


def build_generation_prompt(
    parser_name: str,
    vendor: str,
    product: str,
    declared_log_type: str,
    declared_log_detail: str,
    class_uid: int,
    class_name: str,
    ocsf_fields: Dict,
    source_fields: List[Dict],
    ingestion_mode: str,
    examples: Optional[List[Dict]] = None,
    deterministic_preflight: Optional[Dict[str, Any]] = None,
    reference_implementations: Optional[List[Dict]] = None,
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

    reference_section = ""
    if reference_implementations:
        ref_blocks = []
        # Only include the top reference; larger blocks crowd out task-specific guidance.
        for ref in reference_implementations[:1]:
            ref_name = ref.get("parser_name") or "reference"
            ref_class = ref.get("class_uid") or "?"
            ref_sig = ref.get("signature") or "processEvent"
            ref_code = str(ref.get("code") or "")
            ref_blocks.append(
                f"Reference parser: {ref_name} (class_uid={ref_class}, signature={ref_sig})\n"
                f"```lua\n{ref_code}\n```"
            )
        reference_section = (
            "\nREFERENCE IMPLEMENTATION (production Observo serializer — match style, "
            "not content):\n"
            + "\n".join(ref_blocks)
            + "\nFollow the structural patterns above (FEATURES table, FIELD_ORDERS, "
              "helper placement, pcall guards, OCSF field naming) but derive all mappings "
              "from THIS parser's source fields — do not copy values from the reference.\n"
        )

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
        declared_log_type=declared_log_type,
        declared_log_detail=declared_log_detail,
        class_uid=class_uid,
        class_name=class_name,
    )

    prompt = f"""Generate a Lua transformation script for the following parser:

PARSER: {parser_name}
VENDOR: {vendor or 'Unknown'}
PRODUCT: {product or 'Unknown'}
USER DECLARED LOG TYPE: {declared_log_type or 'Unknown'}
USER DECLARED SOURCE DETAIL: {declared_log_detail or 'None'}
FUNCTION SIGNATURE: {signature}

TARGET OCSF CLASS: {class_name} (class_uid={class_uid})
{ocsf_section}

SOURCE FIELDS AVAILABLE:
{field_list}
{sample_section}
{preflight_section}
{reference_section}

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


def build_gpt5_plan_prompt(
    parser_name: str,
    vendor: str,
    product: str,
    declared_log_type: str,
    declared_log_detail: str,
    class_uid: int,
    class_name: str,
    ocsf_fields: Dict,
    source_fields: List[Dict],
    ingestion_mode: str,
    examples: Optional[List[Dict]] = None,
    deterministic_preflight: Optional[Dict[str, Any]] = None,
    known_options: Optional[Dict[str, Any]] = None,
) -> str:
    """Build a compact planning prompt for GPT-5 family models."""
    required = ocsf_fields.get("required_fields", []) or [
        "class_uid", "category_uid", "activity_id", "time", "type_uid", "severity_id"
    ]
    optional = ocsf_fields.get("optional_fields", [])[:15]
    field_list = ", ".join(f["name"] for f in source_fields[:30] if isinstance(f, dict) and f.get("name")) or "unknown"
    sample_section = ""
    if examples:
        rendered = []
        for idx, ex in enumerate(examples[:2], 1):
            text = json.dumps(ex, ensure_ascii=False)[:1200] if isinstance(ex, (dict, list)) else str(ex)[:1200]
            rendered.append(f"Example {idx}: {text}")
        sample_section = "\n".join(rendered)
    preflight = deterministic_preflight or {}
    known = known_options or {}
    alias_lines = "\n".join(f"- {item}" for item in (known.get("field_aliases") or [])) or "- none"
    note_lines = "\n".join(f"- {item}" for item in (known.get("notes") or [])) or "- none"
    return f"""Plan a Lua transformation before writing code.

Parser: {parser_name}
Vendor: {vendor or 'Unknown'}
Product: {product or 'Unknown'}
User-declared log type: {declared_log_type or 'Unknown'}
User-declared source detail: {declared_log_detail or 'None'}
Ingestion mode: {ingestion_mode}
Target class: {class_name} ({class_uid})
Required OCSF fields: {", ".join(required)}
Optional OCSF fields: {", ".join(optional) if optional else "none"}
Known source fields: {field_list}
Detected formats: {", ".join(preflight.get("formats") or ["unknown"])}
Record hints: {", ".join(preflight.get("record_hints") or ["none"])}
Embedded payload detected: {bool(preflight.get("embedded_payload_detected"))}
Candidate extracted fields: {", ".join((preflight.get("extracted_fields") or [])[:30])}

Known source-family defaults you should prefer unless the sample clearly contradicts them:
- activity_id: {known.get("activity_id", 99)}
- activity_name: {known.get("activity_name", "Unknown")}
Known field aliases:
{alias_lines}
Known notes:
{note_lines}

Samples:
{sample_section or "No example bodies available"}

Return only a JSON plan describing:
- exact OCSF mapping decisions
- exact numeric activity_id
- explicit use of the known defaults above when they fit
- which source fields or embedded payload keys to use
- timestamp strategy
- severity strategy
- embedded payload parsing strategy
- minimal notes needed for Lua generation
"""


def build_gpt5_code_prompt(
    parser_name: str,
    class_uid: int,
    class_name: str,
    category_uid: int,
    category_name: str,
    plan: Dict[str, Any],
    scaffold: str,
) -> str:
    """Build a compact code-generation prompt for GPT-5 family models."""
    plan_json = json.dumps(plan, ensure_ascii=False, indent=2)
    return f"""Generate the final Lua script from the approved mapping plan.

Parser: {parser_name}
Target class: {class_name} ({class_uid})
Target category: {category_name} ({category_uid})

Constraints:
- Output only Lua code
- Keep the script compact
- Define only helpers you actually use
- Must be valid Observo Lua with `function processEvent(event)`
- Must set required OCSF fields explicitly on the output table: class_uid, category_uid, activity_id, time, type_uid, severity_id
- Must also set descriptive fields: class_name, category_name, activity_name
- Use the exact numeric values from the approved plan for class_uid, category_uid, and activity_id
- Compute `type_uid = class_uid * 100 + activity_id`
- Provide a real numeric `time` in milliseconds since epoch
- Provide a real numeric `severity_id`; use 0 only when the plan has no stronger mapping
- Must parse embedded `message`/`raw` payloads when the plan requires it
- Must be nil-safe and runtime-safe
- Before finishing, verify the final script contains explicit assignments for all six required OCSF fields

Recommended shape:
- top-level constants for class/category/activity identifiers
- one compact `processEvent(event)` function
- `pcall` around transformation logic
- `result` initialized with required OCSF fields before optional mappings
- Start from the provided scaffold and preserve its structure
- Only replace TODO blocks and complete direct mappings needed by the approved plan
- Do not rewrite helpers unless a harness failure specifically requires it

Approved mapping plan:
{plan_json}

Scaffold to complete:
```lua
{scaffold}
```
"""


def build_gpt5_refinement_prompt(
    lua_code: str,
    score: int,
    harness_errors: Dict[str, Any],
    plan: Dict[str, Any],
    scaffold: str,
) -> str:
    """Build a compact refinement prompt for GPT-5 family models."""
    ocsf = harness_errors.get("ocsf_mapping", {}) or {}
    linting = harness_errors.get("lua_linting", {}) or {}
    missing = ocsf.get("missing_required", []) or []
    lint_errors = [
        issue["message"]
        for issue in linting.get("issues", []) or []
        if issue.get("severity") == "error"
    ]
    problems = missing + lint_errors
    problem_text = "\n".join(f"- {item}" for item in problems[:12]) or "- improve required-field coverage and Lua validity"
    return f"""Revise the Lua script. Preserve the overall structure and change only what is needed.

Current score: {score}
Problems to fix:
{problem_text}

Re-use the approved mapping plan. Do not add broad helper scaffolding unless required.
Preserve the scaffold structure and edit only the smallest set of lines needed to fix the reported problems.

Approved plan:
{json.dumps(plan, ensure_ascii=False, indent=2)}

Reference scaffold:
```lua
{scaffold}
```

Current Lua:
```lua
{lua_code}
```

Output only the corrected Lua code.
"""


def _build_source_specific_guidance(
    parser_name: str,
    vendor: str,
    product: str,
    declared_log_type: str,
    declared_log_detail: str,
    class_uid: int,
    class_name: str,
) -> str:
    """Build source-aware mapping guidance for high-value parser families."""
    directives: List[str] = []
    for profile in find_source_family_guidance_profiles(
        parser_name, vendor, product, declared_log_type, declared_log_detail
    ):
        directives.extend(profile.guidance_directives)

    if not directives:
        directives.append(
            f"- Source-specific guidance: align mappings with class `{class_name}` (class_uid={class_uid}) and avoid generic catch-all output"
        )

    return "\n".join(directives)


def _build_gpt5_known_options(
    parser_name: str,
    vendor: str,
    product: str,
    declared_log_type: str,
    declared_log_detail: str,
    class_uid: int,
) -> Dict[str, Any]:
    """Return deterministic source-family defaults that the model should prefer."""
    defaults: Dict[str, Any] = {
        "activity_id": 99,
        "activity_name": "Unknown",
        "field_aliases": [],
        "notes": [],
    }

    if class_uid == 4003:
        defaults.update({
            "activity_id": 1,
            "activity_name": "DNS Query",
            "field_aliases": [
                "cliIP -> src_endpoint.ip",
                "resolverIP -> dst_endpoint.ip",
                "domain -> query.hostname",
                "recordType -> query.type",
                "responseCode -> rcode or rcode_id",
                "answer -> answers",
            ],
            "notes": [
                "Prefer DNS query semantics over generic network activity",
                "When DNS request/response fields are present, do not leave query.* or rcode blank",
            ],
        })
    elif class_uid == 4002:
        defaults.update({
            "activity_id": 1,
            "activity_name": "HTTP Request",
            "field_aliases": [
                "cliIP -> src_endpoint.ip",
                "edgeIP -> dst_endpoint.ip",
                "reqMethod -> http_request.http_method",
                "reqHost -> http_request.url host context",
                "reqPath -> http_request.url path context",
                "statusCode -> http_response.code",
                "turnAroundTimeMSec -> duration",
                "bytes -> http_response.length",
            ],
            "notes": [
                "Prefer HTTP request semantics over generic network activity",
                "When reqHost and reqPath both exist, construct a useful URL if feasible",
            ],
        })
    elif class_uid == 3002:
        defaults.update({
            "activity_id": 1,
            "activity_name": "Logon",
            "field_aliases": [
                "user.name -> actor.user.name",
                "user.account_uid -> actor.user.uid",
                "src.ip -> src_endpoint.ip",
                "auth_protocol -> auth_protocol",
                "mfa_factors or mfa_required -> is_mfa",
            ],
            "notes": [
                "Prefer authentication semantics over findings semantics",
                "For login/auth success or failure events, activity_id should usually be 1",
            ],
        })
    elif class_uid == 2004:
        defaults.update({
            "activity_id": 1,
            "activity_name": "Create",
            "field_aliases": [
                "ActionType -> finding_info.title",
                "scenario.trace_id -> finding_info.uid",
                "DeviceName -> device.hostname or src_endpoint.hostname context",
                "ProcessName -> process.name",
                "ProcessCommandLine -> process.cmd_line",
            ],
            "notes": [
                "Prefer concrete finding creation semantics over generic process activity",
            "Use ActionType and trace or detection identifiers for finding title and uid",
            ],
        })
    return apply_source_family_defaults(
        defaults,
        parser_name,
        vendor,
        product,
        declared_log_type,
        declared_log_detail,
    )


def _lua_quote(value: Any) -> str:
    if value is None:
        return '""'
    return json.dumps(str(value), ensure_ascii=False)


def build_gpt5_lua_scaffold(plan: Dict[str, Any]) -> str:
    """Create a deterministic Observo-safe Lua scaffold from an approved mapping plan."""
    class_uid = int(plan.get("class_uid") or 0)
    category_uid = int(plan.get("category_uid") or max(1, class_uid // 1000))
    activity_id = int(plan.get("activity_id") or 99)
    class_name = _lua_quote(plan.get("class_name") or "Unknown")
    category_name = _lua_quote(plan.get("category_name") or "Unknown")
    activity_name = _lua_quote(plan.get("activity_name") or "Unknown")
    timestamp_sources = [str(item) for item in (plan.get("timestamp_sources") or []) if item]
    timestamp_candidates = ", ".join(_lua_quote(item) for item in timestamp_sources) or '""'
    severity_strategy = str(plan.get("severity_strategy") or "default 0")
    embedded_strategy = str(plan.get("embedded_payload_strategy") or "none")

    mapping_comments = []
    for mapping in plan.get("mappings") or []:
        if not isinstance(mapping, dict):
            continue
        target = mapping.get("target") or "unknown"
        candidates = ", ".join(mapping.get("source_candidates") or [])
        transform = mapping.get("transform") or "direct"
        mapping_comments.append(
            f"    -- TODO map {target} from [{candidates}] using {transform}"
        )
    mapping_comment_block = "\n".join(mapping_comments) or "    -- TODO add mapped fields from the approved plan"

    parse_embedded = embedded_strategy.lower() != "none"
    embedded_comment = (
        "    -- TODO parse message/raw payload according to the approved embedded payload strategy"
        if parse_embedded else
        "    -- Embedded payload parsing not required by the approved plan"
    )

    return f"""local CLASS_UID = {class_uid}
local CATEGORY_UID = {category_uid}
local ACTIVITY_ID = {activity_id}
local CLASS_NAME = {class_name}
local CATEGORY_NAME = {category_name}
local ACTIVITY_NAME = {activity_name}

local function safe_get(tbl, key)
  if type(tbl) ~= "table" then return nil end
  return tbl[key]
end

local function first_present(tbl, keys)
  if type(keys) ~= "table" then return nil end
  for _, key in ipairs(keys) do
    local value = safe_get(tbl, key)
    if value ~= nil and value ~= "" then
      return value
    end
  end
  return nil
end

local function parse_embedded_kv(text)
  if type(text) ~= "string" or not text:find("=", 1, true) then return nil end
  local out = {{}}
  for key, value in text:gmatch('([%w_%.:-]+)%s*=%s*"([^"]*)"') do
    out[key] = value
  end
  for key, value in text:gmatch('([%w_%.:-]+)%s*=%s*([^%s"]+)') do
    if out[key] == nil then
      out[key] = value
    end
  end
  return next(out) and out or nil
end

local function parse_embedded_json(text)
  if type(text) ~= "string" then return nil end
  local trimmed = text:match("^%s*(.-)%s*$")
  if not trimmed or (trimmed:sub(1, 1) ~= "{{" and trimmed:sub(1, 1) ~= "[") then
    return nil
  end
  if type(_G.json) == "table" and type(_G.json.decode) == "function" then
    local ok, parsed = pcall(_G.json.decode, trimmed)
    if ok and type(parsed) == "table" then
      return parsed
    end
  end
  return nil
end

local function coalesce_payload(event)
  local payload = event
  {embedded_comment}
  local message_value = safe_get(event, "message") or safe_get(event, "raw")
  local parsed = parse_embedded_json(message_value) or parse_embedded_kv(message_value)
  if type(parsed) == "table" then
    payload = {{}}
    for key, value in pairs(event) do payload[key] = value end
    for key, value in pairs(parsed) do
      if payload[key] == nil then
        payload[key] = value
      end
    end
  end
  return payload
end

local function parse_time_ms(value)
  if type(value) == "number" then
    return value > 9999999999 and value or (value * 1000)
  end
  if type(value) ~= "string" or value == "" then return nil end
  local y, mo, d, hh, mm, ss, frac = value:match("^(%d%d%d%d)%-(%d%d)%-(%d%d)[T ](%d%d):(%d%d):(%d%d)%.?(%d*)")
  if not y then return nil end
  local ok, epoch = pcall(os.time, {{
    year = tonumber(y),
    month = tonumber(mo),
    day = tonumber(d),
    hour = tonumber(hh),
    min = tonumber(mm),
    sec = tonumber(ss),
    isdst = false,
  }})
  if not ok or not epoch then return nil end
  local ms = 0
  if frac and frac ~= "" then
    ms = tonumber((frac .. "000"):sub(1, 3)) or 0
  end
  return epoch * 1000 + ms
end

local function severity_from_payload(payload)
  -- TODO implement severity strategy: {severity_strategy}
  return 0
end

function processEvent(event)
  local ok, transformed = pcall(function()
    if type(event) ~= "table" then return nil end
    local payload = coalesce_payload(event)
    local result = {{
      class_uid = CLASS_UID,
      category_uid = CATEGORY_UID,
      activity_id = ACTIVITY_ID,
      class_name = CLASS_NAME,
      category_name = CATEGORY_NAME,
      activity_name = ACTIVITY_NAME,
      type_uid = CLASS_UID * 100 + ACTIVITY_ID,
      severity_id = 0,
      time = 0,
    }}

    local timestamp_value = first_present(payload, {{{timestamp_candidates}}}) or safe_get(payload, "timestamp") or safe_get(payload, "Timestamp")
    result.time = parse_time_ms(timestamp_value) or (os.time() * 1000)
    result.severity_id = severity_from_payload(payload)

{mapping_comment_block}

    return result
  end)

  if not ok then
    event["lua_error"] = tostring(transformed)
    return event
  end

  return transformed
end
"""


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
        declared_log_type = str(
            parser_entry.get("declared_log_type")
            or config.get("declared_log_type")
            or config.get("log_type")
            or ""
        ).strip()
        declared_log_detail = str(
            parser_entry.get("declared_log_detail")
            or config.get("declared_log_detail")
            or ""
        ).strip()
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
        if declared_log_type:
            sample_hint_text = f"{declared_log_type} {sample_hint_text}".strip()
        if declared_log_detail:
            sample_hint_text = f"{declared_log_detail} {sample_hint_text}".strip()
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

        if self.provider == "openai" and self._is_gpt5_family(self.model):
            return self._generate_with_gpt5_strategy(
                parser_entry=parser_entry,
                parser_name=parser_name,
                vendor=vendor,
                product=product,
                declared_log_type=declared_log_type,
                declared_log_detail=declared_log_detail,
                ingestion_mode=ingestion_mode,
                class_uid=class_uid,
                class_name=class_name,
                ocsf_class=ocsf_class,
                source_fields=source_fields,
                prompt_examples=prompt_examples,
                preflight=preflight,
                start=start,
            )

        # 3b. Pull a matching production Observo serializer as a reference implementation.
        # Controlled by HARNESS_REFERENCE_LIBRARY env flag (default on; set to 0/false to disable).
        ref_flag = os.environ.get("HARNESS_REFERENCE_LIBRARY", "1").strip().lower()
        reference_impls: List[Dict[str, Any]] = []
        if ref_flag not in ("0", "false", "no", "off"):
            try:
                reference_impls = ExampleSelector().select(
                    target_class_uid=class_uid,
                    target_vendor=vendor,
                    target_signature="processEvent",
                    max_examples=1,
                )
            except Exception as exc:  # pragma: no cover — defensive
                logger.warning("Reference library lookup failed for %s: %s", parser_name, exc)

        # 4. Build prompt (production patterns are baked into SYSTEM_PROMPT)
        prompt = build_generation_prompt(
            parser_name=parser_name,
            vendor=vendor,
            product=product,
            declared_log_type=declared_log_type,
            declared_log_detail=declared_log_detail,
            class_uid=class_uid,
            class_name=class_name,
            ocsf_fields=ocsf_class,
            source_fields=source_fields,
            ingestion_mode=ingestion_mode,
            examples=prompt_examples,
            deterministic_preflight=preflight,
            reference_implementations=reference_impls,
        )

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

    @staticmethod
    def _is_gpt5_family(model: str) -> bool:
        normalized = (model or "").strip().lower()
        return normalized.startswith("gpt-5")

    def _generate_with_gpt5_strategy(
        self,
        parser_entry: Dict[str, Any],
        parser_name: str,
        vendor: str,
        product: str,
        declared_log_type: str,
        declared_log_detail: str,
        ingestion_mode: str,
        class_uid: int,
        class_name: str,
        ocsf_class: Dict[str, Any],
        source_fields: List[Dict[str, Any]],
        prompt_examples: List[Any],
        preflight: Dict[str, Any],
        start: float,
    ) -> Dict[str, Any]:
        """GPT-5-specific generation path using planning + turn chaining."""
        category_uid = ocsf_class.get("category_uid", max(1, class_uid // 1000))
        category_name = ocsf_class.get("category_name", "Unknown")

        plan_prompt = build_gpt5_plan_prompt(
            parser_name=parser_name,
            vendor=vendor,
            product=product,
            declared_log_type=declared_log_type,
            declared_log_detail=declared_log_detail,
            class_uid=class_uid,
            class_name=class_name,
            ocsf_fields=ocsf_class,
            source_fields=source_fields,
            ingestion_mode=ingestion_mode,
            examples=prompt_examples,
            deterministic_preflight=preflight,
            known_options=_build_gpt5_known_options(
                parser_name=parser_name,
                vendor=vendor,
                product=product,
                declared_log_type=declared_log_type,
                declared_log_detail=declared_log_detail,
                class_uid=class_uid,
            ),
        )
        plan_response = self._call_openai_responses_raw(
            model=self.model,
            instructions=GPT5_SYSTEM_PROMPT,
            input_items=[{"role": "user", "content": plan_prompt}],
            response_format={
                "type": "json_schema",
                "name": "lua_mapping_plan",
                "schema": GPT5_PLAN_SCHEMA,
                "strict": True,
            },
        )
        plan_text = plan_response.get("text")
        response_id = plan_response.get("response_id")
        if not plan_text:
            elapsed = time.time() - start
            return {
                "parser_name": parser_name,
                "error": "Failed to generate planning step",
                "confidence_score": 0,
                "elapsed_seconds": round(elapsed, 2),
            }

        try:
            plan = json.loads(plan_text)
        except Exception:
            logger.error("GPT-5 planner returned invalid JSON for %s", parser_name)
            elapsed = time.time() - start
            return {
                "parser_name": parser_name,
                "error": "Failed to parse planning step",
                "confidence_score": 0,
                "elapsed_seconds": round(elapsed, 2),
            }

        code_prompt = build_gpt5_code_prompt(
            parser_name=parser_name,
            class_uid=class_uid,
            class_name=class_name,
            category_uid=category_uid,
            category_name=category_name,
            plan=plan,
            scaffold=build_gpt5_lua_scaffold(plan),
        )
        best_result = None
        best_score = -1
        active_previous_response_id = response_id

        for iteration in range(1, self.max_iterations + 1):
            logger.info("GPT-5 iteration %d for %s using model %s", iteration, parser_name, self.model)
            response = self._call_openai_responses_raw(
                model=self.model,
                instructions=GPT5_SYSTEM_PROMPT,
                input_items=[{"role": "user", "content": code_prompt}],
                previous_response_id=active_previous_response_id,
            )
            lua_code = response.get("text")
            active_previous_response_id = response.get("response_id") or active_previous_response_id
            if not lua_code:
                logger.error("GPT-5 returned no code on iteration %d for %s", iteration, parser_name)
                break

            lua_code = self._clean_lua_response(lua_code)
            report = self.harness.run_all_checks(
                lua_code=lua_code,
                parser_config=parser_entry,
                ocsf_version="1.3.0",
            )
            score = report.get("confidence_score", 0)
            grade = report.get("confidence_grade", "F")

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
                    "iterations": iteration,
                    "generation_method": "agentic_llm_gpt5_plan",
                    "model": self.model,
                    "generated_at": datetime.utcnow().isoformat() + "Z",
                    "harness_report": report,
                    "mapping_plan": plan,
                }

            field_cmp = report.get("checks", {}).get("field_comparison", {}) or {}
            source_cov = float(field_cmp.get("coverage_pct", 100) or 100)
            has_embedded = bool(preflight.get("embedded_payload_detected"))
            low_cov_for_embedded = has_embedded and source_cov < 40
            if score >= self.score_threshold and not low_cov_for_embedded:
                break

            code_prompt = build_gpt5_refinement_prompt(
                lua_code=lua_code,
                score=score,
                harness_errors=report.get("checks", {}) or {},
                plan=plan,
                scaffold=build_gpt5_lua_scaffold(plan),
            )

        elapsed = time.time() - start
        if best_result:
            best_result["elapsed_seconds"] = round(elapsed, 2)
            best_result["quality"] = "accepted" if best_score >= self.score_threshold else "below_threshold"
            self.cache.put(parser_name, best_result)
            return best_result
        return {
            "parser_name": parser_name,
            "error": "Failed to generate Lua code",
            "confidence_score": 0,
            "elapsed_seconds": round(elapsed, 2),
        }

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

    def _use_openai_responses_api(self, model: str) -> bool:
        """Select the OpenAI API mode for the requested model.

        GPT-5 family models work best with the Responses API. Keep
        compatibility fallback for older chat-completions workflows.
        """
        api_mode = (os.environ.get("OPENAI_API_MODE") or "auto").strip().lower()
        if api_mode == "responses":
            return True
        if api_mode in {"chat", "chat_completions"}:
            return False

        normalized = (model or "").strip().lower()
        return normalized.startswith("gpt-5") or normalized.startswith("o3") or normalized.startswith("o4")

    def _build_openai_responses_payload(self, messages: List[Dict], model: str) -> Dict[str, Any]:
        """Build a Responses API payload from the internal chat message format."""
        payload: Dict[str, Any] = {
            "model": model,
            "instructions": SYSTEM_PROMPT,
            "input": [
                {
                    "role": message.get("role", "user"),
                    "content": message.get("content", ""),
                }
                for message in messages
            ],
            "max_output_tokens": self.max_output_tokens,
        }

        normalized = (model or "").strip().lower()
        if normalized.startswith("gpt-5"):
            reasoning_effort = (os.environ.get("OPENAI_REASONING_EFFORT") or "").strip().lower()
            text_verbosity = (os.environ.get("OPENAI_TEXT_VERBOSITY") or "").strip().lower()
            if reasoning_effort:
                normalized_effort, warning = _normalize_openai_reasoning_effort(model, reasoning_effort)
                if warning:
                    logger.warning(warning)
                if normalized_effort:
                    payload["reasoning"] = {"effort": normalized_effort}
            if text_verbosity:
                payload["text"] = {"verbosity": text_verbosity}

        return payload

    def _build_openai_responses_request(
        self,
        model: str,
        instructions: str,
        input_items: List[Dict[str, Any]],
        previous_response_id: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model,
            "instructions": instructions,
            "input": input_items,
            "max_output_tokens": self.max_output_tokens,
        }
        if previous_response_id:
            payload["previous_response_id"] = previous_response_id

        text_cfg: Dict[str, Any] = {}
        normalized = (model or "").strip().lower()
        if normalized.startswith("gpt-5"):
            reasoning_effort = (os.environ.get("OPENAI_REASONING_EFFORT") or "").strip().lower()
            text_verbosity = (os.environ.get("OPENAI_TEXT_VERBOSITY") or "").strip().lower()
            if reasoning_effort:
                normalized_effort, warning = _normalize_openai_reasoning_effort(model, reasoning_effort)
                if warning:
                    logger.warning(warning)
                if normalized_effort:
                    payload["reasoning"] = {"effort": normalized_effort}
            if text_verbosity and not response_format:
                text_cfg["verbosity"] = text_verbosity

        if response_format:
            text_cfg["format"] = response_format
        if text_cfg:
            payload["text"] = text_cfg
        return payload

    @staticmethod
    def _extract_openai_responses_text(data: Dict[str, Any]) -> Optional[str]:
        """Extract text from a Responses API payload."""
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        output = data.get("output", [])
        if not isinstance(output, list):
            return None

        chunks: List[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []) or []:
                if not isinstance(content, dict):
                    continue
                text = content.get("text")
                if isinstance(text, str) and text:
                    chunks.append(text)
        if chunks:
            return "\n".join(chunks)
        return None

    def _call_openai_responses(self, messages: List[Dict], model: str) -> Optional[str]:
        """Call OpenAI Responses API and return response text."""
        try:
            response = requests.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=self._build_openai_responses_payload(messages, model),
                timeout=120,
            )
            response.raise_for_status()
            return self._extract_openai_responses_text(response.json())
        except Exception as e:
            response_obj = getattr(e, "response", None)
            if response_obj is not None:
                logger.error("OpenAI Responses API error body: %s", response_obj.text)
            logger.error(f"OpenAI Responses API error: {e}")
            return None

    def _call_openai_responses_raw(
        self,
        model: str,
        instructions: str,
        input_items: List[Dict[str, Any]],
        previous_response_id: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Call OpenAI Responses API and return text plus response metadata."""
        try:
            payload = self._build_openai_responses_request(
                model=model,
                instructions=instructions,
                input_items=input_items,
                previous_response_id=previous_response_id,
                response_format=response_format,
            )
            response = requests.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
            return {
                "text": self._extract_openai_responses_text(data),
                "response_id": data.get("id"),
                "data": data,
            }
        except Exception as e:
            response_obj = getattr(e, "response", None)
            if response_obj is not None:
                logger.error("OpenAI Responses API error body: %s", response_obj.text)
            logger.error(f"OpenAI Responses API error: {e}")
            return {"text": None, "response_id": None, "data": None}

    def _call_openai_chat_completions(self, messages: List[Dict], model: str) -> Optional[str]:
        """Call OpenAI Chat Completions API and return response text."""
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

    def _call_openai(self, messages: List[Dict], model: str) -> Optional[str]:
        """Call OpenAI API and return response text."""
        if self._use_openai_responses_api(model):
            return self._call_openai_responses(messages, model)
        return self._call_openai_chat_completions(messages, model)

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
