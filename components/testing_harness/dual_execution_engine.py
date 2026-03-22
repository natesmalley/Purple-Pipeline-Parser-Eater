"""Dual execution engine - runs Lua transformations against test events with tracing."""

import logging
import re
import time
from typing import Dict, List, Any, Optional

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

        results = []
        passed = 0
        failed = 0

        for test in test_events:
            test_name = test.get("name", "Unnamed")
            event_data = test.get("event", {})

            result = self._execute_single(lua_code, signature, event_data, test_name, ocsf_required)
            results.append(result)

            if result["status"] == "passed":
                passed += 1
            else:
                failed += 1

        return {
            "function_signature": signature,
            "total_events": len(test_events),
            "passed": passed,
            "failed": failed,
            "results": results,
            "lupa_available": True,
        }

    def _detect_signature(self, lua_code: str) -> str:
        has_processEvent = bool(re.search(r'function\s+processEvent\s*\(', lua_code))
        has_transform = bool(re.search(r'function\s+transform\s*\(', lua_code))
        has_process = bool(re.search(r'function\s+process\s*\(', lua_code))
        if has_processEvent:
            return "processEvent"
        if has_process:
            return "process"
        if has_transform:
            return "transform"
        return "unknown"

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
            lua = lupa.LuaRuntime(
                unpack_returned_tuples=True,
                register_eval=False,
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
                package = nil; debug = nil; collectgarbage = nil

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
            """)

            # Load the Lua code
            lua.execute(lua_code)

            output_event = None
            error_msg = None

            if signature == "processEvent":
                # processEvent(event) — Observo Lua API, returns event or nil
                pe_func = lua.globals().processEvent
                if pe_func is None:
                    error_msg = "processEvent() function not found after loading code"
                else:
                    result = pe_func(self._dict_to_lua(lua, event_data))
                    if result is not None:
                        output_event = self._lua_to_dict(result)
                        # Strip numeric string keys from Lua table conversion
                        if isinstance(output_event, dict):
                            output_event = {
                                k: v for k, v in output_event.items()
                                if not (isinstance(k, str) and k.isdigit())
                            }
                        # Handle log.-prefixed keys in OCSF validation
                        if isinstance(output_event, dict) and "log" in output_event and isinstance(output_event["log"], dict):
                            # Merge log sub-fields up if they contain OCSF fields
                            log_data = output_event["log"]
                            if any(k in log_data for k in ["class_uid", "category_uid", "activity_id"]):
                                output_event = log_data
                    else:
                        error_msg = "processEvent() returned nil"

            elif signature == "process":
                # process(event, emit) — wrap event in {log: data}
                wrapped = {"log": event_data}
                emitted = []

                def emit_callback(evt):
                    emitted.append(evt)

                process_func = lua.globals().process
                if process_func is None:
                    error_msg = "process() function not found after loading code"
                else:
                    process_func(self._dict_to_lua(lua, wrapped), emit_callback)
                    if emitted:
                        raw = emitted[0]
                        output_event = self._lua_to_dict(raw)
                        # Strip numeric string keys
                        if isinstance(output_event, dict):
                            output_event = {k: v for k, v in output_event.items() if not (isinstance(k, str) and k.isdigit())}
                        # Extract the log portion if present
                        if isinstance(output_event, dict) and "log" in output_event:
                            log_data = output_event["log"]
                            if isinstance(log_data, dict):
                                output_event = {k: v for k, v in log_data.items() if not (isinstance(k, str) and k.isdigit())}
                            else:
                                output_event = output_event
                    else:
                        error_msg = "process() did not emit any events"

            elif signature == "transform":
                transform_func = lua.globals().transform
                if transform_func is None:
                    error_msg = "transform() function not found after loading code"
                else:
                    result = transform_func(self._dict_to_lua(lua, event_data))
                    output_event = self._lua_to_dict(result)

            else:
                error_msg = f"Unknown function signature: {signature}"

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
        for out_field, out_value in output_flat.items():
            in_field = None
            in_value = None
            mapping_type = "computed"

            # Check if output value matches any input value
            for inf, inv in input_flat.items():
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
        for inf in input_flat:
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
            for k, v in d.items():
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
