"""Dual execution engine - runs Lua transformations against test events with tracing."""

import json
import logging
import re
import time
import copy
from typing import Dict, List, Any, Optional

from components.testing_harness.lua_helpers import get_canonical_helpers

logger = logging.getLogger(__name__)

try:
    import lupa
    LUPA_AVAILABLE = True
except ImportError:
    LUPA_AVAILABLE = False
    logger.warning("lupa not available - test execution will be skipped")


class DualExecutionEngine:
    """Executes Lua transformation code against test events and traces field mappings."""

    def execute(
        self,
        lua_code: str,
        test_events: List[Dict[str, Any]],
        ocsf_required_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute Lua against test events and produce detailed results.

        Args:
            lua_code: Lua transformation code
            test_events: List of test event dicts (each has name, event, etc.)
            ocsf_required_fields: Required OCSF fields to validate in output
        """
        if not LUPA_AVAILABLE:
            return {
                "function_signature": "unknown",
                "total_events": len(test_events),
                "passed": 0,
                "failed": 0,
                "results": [],
                "lupa_available": False,
            }

        ocsf_required = ocsf_required_fields or [
            "class_uid", "category_uid", "activity_id", "time", "type_uid", "severity_id"
        ]

        # Detect signature
        signature = self._detect_signature(lua_code)

        ordered_events = self._order_test_events(test_events)

        results = []
        passed = 0
        failed = 0

        for test in ordered_events:
            test_name = test.get("name", "Unnamed")
            event_data = test.get("event", {})

            result = self._execute_single(lua_code, signature, event_data, test_name, ocsf_required)
            results.append(result)

            if result["status"] == "passed":
                passed += 1
            else:
                failed += 1

        # Timestamp-type fuzz pass. Rerun every event with the ``timestamp`` /
        # ``Timestamp`` field coerced to a numeric epoch and to nil. This
        # catches scripts that call ``timestamp:match(...)`` without a
        # type-guard — the class of failure Marco hit in production on
        # Akamai DNS (2026-04-08). Variants run in a deterministic order.
        fuzz_results: List[Dict[str, Any]] = []
        for test in ordered_events:
            base_event = test.get("event", {}) or {}
            ts_keys = [k for k in ("timestamp", "Timestamp", "time") if k in base_event]
            if not ts_keys:
                continue
            for variant_label, variant_value in (
                ("timestamp_numeric", 1775681018000),
                ("timestamp_missing", None),
            ):
                fuzzed_event = dict(base_event)
                for tk in ts_keys:
                    if variant_value is None:
                        fuzzed_event.pop(tk, None)
                    else:
                        fuzzed_event[tk] = variant_value
                fuzz_name = f"{test.get('name', 'Unnamed')}#fuzz_{variant_label}"
                fuzz_result = self._execute_single(
                    lua_code, signature, fuzzed_event, fuzz_name, ocsf_required
                )
                fuzz_result["fuzz_variant"] = variant_label
                fuzz_results.append(fuzz_result)

        # A fuzz variant is only "passed" if it both ran cleanly AND its output
        # doesn't carry a ``lua_error`` field — scripts commonly wrap their
        # body in pcall and write the error to the event, which the base
        # executor marks as passed.
        def _fuzz_ok(r: Dict[str, Any]) -> bool:
            if r.get("status") != "passed":
                return False
            out = r.get("output_event") or {}
            return not out.get("lua_error")

        fuzz_passed = sum(1 for r in fuzz_results if _fuzz_ok(r))
        fuzz_failed = len(fuzz_results) - fuzz_passed

        return {
            "function_signature": signature,
            "total_events": len(ordered_events),
            "passed": passed,
            "failed": failed,
            "results": results,
            "lupa_available": True,
            "timestamp_fuzz": {
                "total": len(fuzz_results),
                "passed": fuzz_passed,
                "failed": fuzz_failed,
                "results": fuzz_results,
            },
        }

    def _order_test_events(self, test_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return test events in stable deterministic order."""

        def sort_key(test: Dict[str, Any]) -> tuple:
            return (
                str(test.get("name", "")),
                str(test.get("description", "")),
                str(test.get("expected_behavior", "")),
                json.dumps(test.get("event", {}), sort_keys=True, default=str),
            )

        return sorted(test_events, key=sort_key)

    def _detect_signature(self, lua_code: str) -> str:
        from components.testing_harness.lua_signature import detect_entry_signature
        sig = detect_entry_signature(lua_code)
        return sig.name or "unknown"

    def _execute_single(
        self,
        lua_code: str,
        signature: str,
        event_data: Dict[str, Any],
        test_name: str,
        ocsf_required: List[str],
    ) -> Dict[str, Any]:
        """Execute a single test event."""
        start = time.time()
        try:
            normalized_event = self._enrich_event_with_embedded_payload(event_data)

            lua = lupa.LuaRuntime(
                unpack_returned_tuples=True,
                register_eval=False,
                register_builtins=False,
            )

            # Sandbox: keep safe os.time/os.date, disable everything dangerous
            lua.execute("""
                -- Preserve safe os functions before sandboxing
                local safe_os = {
                    time = os.time,
                    date = os.date,
                    clock = os.clock,
                    difftime = os.difftime,
                }
                -- Preserve safe string functions
                local safe_string = string
                local safe_math = math
                local safe_table = table
                local safe_tonumber = tonumber
                local safe_tostring = tostring
                local safe_type = type
                local safe_pairs = pairs
                local safe_ipairs = ipairs
                local safe_pcall = pcall
                local safe_xpcall = xpcall
                local safe_select = select
                local safe_unpack = unpack or table.unpack

                -- Disable dangerous modules
                io = nil; load = nil; loadfile = nil
                loadstring = nil; dofile = nil
                package = nil; collectgarbage = nil

                -- Expanded blocklist: prevent metatable/raw access and coroutines
                rawget = nil
                rawset = nil
                rawequal = nil
                rawlen = nil
                getmetatable = nil
                setmetatable = nil
                coroutine = nil

                -- Prevent string.dump bytecode leakage
                string.dump = nil

                -- Safe wrapper for string.rep to prevent memory DoS
                local _original_string_rep = string.rep
                string.rep = function(s, n)
                    if n > 1000000 then return nil end
                    return _original_string_rep(s, n)
                end

                -- Execution timeout via instruction count hook
                local _instruction_count = 0
                local _max_instructions = 10000000
                debug.sethook(function()
                    _instruction_count = _instruction_count + 1
                    if _instruction_count > _max_instructions then
                        error("execution timeout: exceeded maximum instruction count")
                    end
                end, "", 10000)

                -- Now safe to nil debug (hook survives)
                debug = nil

                -- Replace os with safe subset (no execute, remove, rename, etc.)
                os = safe_os

                -- Stub require() to return safe modules (matches Observo sandbox)
                require = function(mod)
                    if mod == 'json' then
                        return { encode = function(v) return tostring(v) end,
                                 decode = function(s) return s end }
                    elseif mod == 'log' then
                        return { info = function() end, warn = function() end,
                                 error = function() end, debug = function() end }
                    elseif mod == 'hmac' then
                        return { sha256 = function(k,d) return 'stub' end }
                    elseif mod == 'codec' then
                        return { base64_encode = function(s) return s end,
                                 base64_decode = function(s) return s end }
                    end
                    return nil
                end

                -- Compatibility helpers loaded from canonical source.
                -- These ensure tests pass when LLM omits inlined helpers.
            """ + get_canonical_helpers() + """
            """)

            # Load the Lua code
            lua.execute(lua_code)

            output_event, error_msg = self._invoke_signature_adapter(
                lua=lua,
                signature=signature,
                event_data=normalized_event,
            )

            elapsed = (time.time() - start) * 1000

            # Build field trace
            field_trace = self._build_field_trace(event_data, output_event) if output_event else []

            # OCSF validation
            ocsf_validation = self._validate_ocsf(output_event, ocsf_required)

            status = "passed" if output_event and not error_msg else "failed"

            return {
                "test_name": test_name,
                "status": "error" if error_msg else status,
                "input_event": event_data,
                "output_event": output_event,
                "error": error_msg,
                "execution_time_ms": round(elapsed, 2),
                "field_trace": field_trace,
                "ocsf_validation": ocsf_validation,
            }

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return {
                "test_name": test_name,
                "status": "error",
                "input_event": event_data,
                "output_event": None,
                "error": str(e),
                "execution_time_ms": round(elapsed, 2),
                "field_trace": [],
                "ocsf_validation": {
                    "required_present": [],
                    "required_missing": ocsf_required,
                    "coverage_pct": 0,
                },
            }

    def _enrich_event_with_embedded_payload(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Promote fields from embedded payloads in message/raw for deterministic runtime access."""
        if not isinstance(event_data, dict):
            return event_data

        enriched = copy.deepcopy(event_data)
        candidates: List[str] = []
        for key in ("message", "raw"):
            value = enriched.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value)

        for payload in candidates:
            kv_fields = self._extract_kv_pairs(payload)
            self._merge_missing_fields(enriched, kv_fields)

            embedded_json = self._extract_json_object(payload)
            if embedded_json:
                self._merge_missing_fields(enriched, embedded_json)

        self._apply_alias_paths(enriched)
        return enriched

    @staticmethod
    def _extract_kv_pairs(text: str) -> Dict[str, Any]:
        extracted: Dict[str, Any] = {}
        if not isinstance(text, str) or not text.strip():
            return extracted
        for match in re.finditer(
            r'([A-Za-z_][A-Za-z0-9_.-]*)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s,]+))',
            text,
        ):
            key = match.group(1)
            value = match.group(2) or match.group(3) or match.group(4)
            if key and value is not None and key not in extracted:
                extracted[key] = value
        return extracted

    @staticmethod
    def _extract_json_object(text: str) -> Dict[str, Any]:
        if not isinstance(text, str):
            return {}
        candidate = text.strip()
        if not candidate:
            return {}

        if candidate.startswith("{") and candidate.endswith("}"):
            try:
                parsed = json.loads(candidate)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}

        # Best effort: parse substring that looks like JSON object.
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            fragment = candidate[start : end + 1]
            try:
                parsed = json.loads(fragment)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}

    def _merge_missing_fields(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        if not isinstance(target, dict) or not isinstance(source, dict):
            return
        for key, value in source.items():
            if key not in target or target.get(key) in (None, ""):
                target[key] = value

    def _apply_alias_paths(self, event: Dict[str, Any]) -> None:
        alias_map = {
            "cliIP": "src_endpoint.ip",
            "source_ip": "src_endpoint.ip",
            "src_ip": "src_endpoint.ip",
            "domain": "query.hostname",
            "recordType": "query.type",
            "queryType": "query.type",
            "responseCode": "rcode",
            "statusCode": "http_response.code",
            "reqMethod": "http_request.http_method",
            "reqPath": "http_request.url",
        }
        for source_key, target_path in alias_map.items():
            value = event.get(source_key)
            if value in (None, ""):
                continue
            self._set_nested_path_if_missing(event, target_path, value)

    def _set_nested_path_if_missing(self, event: Dict[str, Any], dotted_path: str, value: Any) -> None:
        current = event
        keys = dotted_path.split(".")
        for key in keys[:-1]:
            child = current.get(key)
            if not isinstance(child, dict):
                child = {}
                current[key] = child
            current = child
        leaf = keys[-1]
        if current.get(leaf) in (None, ""):
            current[leaf] = value

    def _invoke_signature_adapter(
        self,
        lua,
        signature: str,
        event_data: Dict[str, Any],
    ) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Execute through explicit signature adapters.

        This isolates compatibility entrypoints from core execution flow:
        - `processEvent(event)` is canonical
        - `transform(record)` and `process(event, emit)` are compatibility adapters
        """
        if signature == "processEvent":
            return self._execute_process_event(lua, event_data)
        if signature == "transform":
            return self._execute_transform_compat(lua, event_data)
        if signature == "process":
            return self._execute_process_compat(lua, event_data)
        return None, f"Unknown function signature: {signature}"

    def _execute_process_event(
        self,
        lua,
        event_data: Dict[str, Any],
    ) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Canonical Observo contract: processEvent(event) -> event|nil."""
        pe_func = lua.globals().processEvent
        if pe_func is None:
            return None, "processEvent() function not found after loading code"

        result = pe_func(self._dict_to_lua(lua, event_data))
        if result is None:
            return None, "processEvent() returned nil"

        output_event = self._lua_to_dict(result)
        output_event = self._strip_numeric_string_keys(output_event)
        output_event = self._extract_embedded_log_event(output_event)
        return output_event, None

    def _execute_transform_compat(
        self,
        lua,
        event_data: Dict[str, Any],
    ) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Compatibility adapter: transform(record) -> record."""
        transform_func = lua.globals().transform
        if transform_func is None:
            return None, "transform() function not found after loading code"

        result = transform_func(self._dict_to_lua(lua, event_data))
        output_event = self._lua_to_dict(result)
        return output_event, None

    def _execute_process_compat(
        self,
        lua,
        event_data: Dict[str, Any],
    ) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Compatibility adapter: process(event, emit)."""
        wrapped = {"log": event_data}
        emitted = []

        def emit_callback(evt):
            emitted.append(evt)

        process_func = lua.globals().process
        if process_func is None:
            return None, "process() function not found after loading code"

        process_func(self._dict_to_lua(lua, wrapped), emit_callback)
        if not emitted:
            return None, "process() did not emit any events"

        output_event = self._lua_to_dict(emitted[0])
        output_event = self._strip_numeric_string_keys(output_event)
        if isinstance(output_event, dict) and "log" in output_event:
            log_data = output_event["log"]
            if isinstance(log_data, dict):
                output_event = self._strip_numeric_string_keys(log_data)
        return output_event, None

    @staticmethod
    def _strip_numeric_string_keys(output_event: Any) -> Any:
        if not isinstance(output_event, dict):
            return output_event
        return {
            k: v for k, v in output_event.items()
            if not (isinstance(k, str) and k.isdigit())
        }

    @staticmethod
    def _extract_embedded_log_event(output_event: Any) -> Any:
        # Some compatibility payloads place OCSF fields under log.*
        if isinstance(output_event, dict) and "log" in output_event and isinstance(output_event["log"], dict):
            log_data = output_event["log"]
            if any(k in log_data for k in ["class_uid", "category_uid", "activity_id"]):
                return log_data
        return output_event

    def _dict_to_lua(self, lua, data: Any) -> Any:
        """Convert Python dict to Lua table."""
        if isinstance(data, dict):
            table = lua.table_from({})
            for k, v in data.items():
                table[k] = self._dict_to_lua(lua, v)
            return table
        elif isinstance(data, (list, tuple)):
            table = lua.table_from({})
            for i, v in enumerate(data, 1):
                table[i] = self._dict_to_lua(lua, v)
            return table
        elif isinstance(data, bool):
            return data
        elif data is None:
            return None
        else:
            return data

    def _lua_to_dict(self, obj: Any) -> Any:
        """Convert Lua table back to Python dict."""
        if obj is None:
            return None

        # Check if it's a Lua table
        try:
            if hasattr(obj, 'keys') or hasattr(obj, 'items'):
                result = {}
                try:
                    items = obj.items() if hasattr(obj, 'items') else []
                    for k, v in items:
                        key = str(k) if not isinstance(k, (str, int, float)) else k
                        result[key] = self._lua_to_dict(v)
                except (TypeError, RuntimeError):
                    pass
                return result if result else str(obj)
        except Exception:
            pass

        if isinstance(obj, (str, int, float, bool)):
            return obj

        # Try iterating as table
        try:
            result = {}
            for k in obj:
                result[str(k)] = self._lua_to_dict(obj[k])
            return result
        except (TypeError, RuntimeError):
            return str(obj)

    def _build_field_trace(
        self, input_event: Dict, output_event: Optional[Dict]
    ) -> List[Dict[str, Any]]:
        """Build field-by-field transformation trace."""
        if not output_event or not isinstance(output_event, dict):
            return []

        trace = []
        input_flat = self._flatten(input_event, "")
        output_flat = self._flatten(output_event, "")

        # Map output fields back to input
        for out_field in sorted(output_flat.keys()):
            out_value = output_flat[out_field]
            in_field = None
            in_value = None
            mapping_type = "computed"

            # Check if output value matches any input value
            for inf in sorted(input_flat.keys()):
                inv = input_flat[inf]
                if str(inv) == str(out_value) and inv is not None:
                    in_field = inf
                    in_value = inv
                    mapping_type = "direct"
                    break

            trace.append({
                "input_field": in_field,
                "output_field": out_field,
                "input_value": in_value,
                "output_value": out_value,
                "mapping_type": mapping_type,
            })

        # Check for dropped input fields
        mapped_inputs = {t["input_field"] for t in trace if t["input_field"]}
        for inf in sorted(input_flat.keys()):
            if inf not in mapped_inputs:
                trace.append({
                    "input_field": inf,
                    "output_field": None,
                    "input_value": input_flat[inf],
                    "output_value": None,
                    "mapping_type": "dropped",
                })

        return trace

    def _flatten(self, d: Any, prefix: str) -> Dict[str, Any]:
        """Flatten a nested dict to dot-notation keys."""
        items = {}
        if isinstance(d, dict):
            for k in sorted(d.keys(), key=lambda x: str(x)):
                v = d[k]
                new_key = f"{prefix}.{k}" if prefix else str(k)
                if isinstance(v, dict):
                    items.update(self._flatten(v, new_key))
                else:
                    items[new_key] = v
        return items

    def _validate_ocsf(
        self, output: Optional[Dict], required: List[str]
    ) -> Dict[str, Any]:
        """Validate OCSF required fields in output."""
        if not output or not isinstance(output, dict):
            return {
                "required_present": [],
                "required_missing": required,
                "coverage_pct": 0,
            }

        output_flat = self._flatten(output, "")
        present = [f for f in required if f in output_flat]
        missing = [f for f in required if f not in output_flat]
        coverage = (len(present) / len(required) * 100) if required else 100

        return {
            "required_present": present,
            "required_missing": missing,
            "coverage_pct": round(coverage, 1),
        }
