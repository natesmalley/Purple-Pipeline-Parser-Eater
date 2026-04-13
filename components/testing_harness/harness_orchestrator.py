"""
Harness Orchestrator - Facade for the 5-point testing harness.

Runs all validation checks and aggregates results into a single
confidence report for display in the web UI.
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional

from .lua_validity_checker import LuaValidityChecker
from .lua_linter import LuaLinter
from .ocsf_schema_registry import OCSFSchemaRegistry
from .ocsf_field_analyzer import OCSFFieldAnalyzer
from .source_parser_analyzer import SourceParserAnalyzer
from .test_event_builder import TestEventBuilder
from .dual_execution_engine import DualExecutionEngine
from .jarvis_event_bridge import JarvisEventBridge

logger = logging.getLogger(__name__)


class HarnessOrchestrator:
    """Runs all 5 testing harness checks and produces a confidence report."""

    def __init__(self):
        self.validity_checker = LuaValidityChecker()
        self.linter = LuaLinter()
        self.ocsf_registry = OCSFSchemaRegistry()
        self.ocsf_analyzer = OCSFFieldAnalyzer(self.ocsf_registry)
        self.source_analyzer = SourceParserAnalyzer()
        self.event_builder = TestEventBuilder()
        self.execution_engine = DualExecutionEngine()
        self.jarvis_bridge = JarvisEventBridge()

    def run_all_checks(
        self,
        lua_code: str,
        parser_config: Optional[Dict[str, Any]] = None,
        ocsf_version: str = "1.3.0",
        custom_test_events: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Run the complete 5-point testing harness.

        Args:
            lua_code: Generated Lua transformation code
            parser_config: Original parser configuration (for field analysis)
            ocsf_version: OCSF schema version to validate against
            custom_test_events: Optional user-provided test events

        Returns:
            Complete harness report with confidence score
        """
        start = time.time()
        results = {}

        # 1. Lua Validity
        results["lua_validity"] = self._run_check(
            "lua_validity",
            lambda: self.validity_checker.check(lua_code),
        )

        # 2. Lua Linting
        results["lua_linting"] = self._run_check(
            "lua_linting",
            lambda: self.linter.lint(lua_code),
        )

        # 3. OCSF Field Mapping
        results["ocsf_mapping"] = self._run_check(
            "ocsf_mapping",
            lambda: self.ocsf_analyzer.analyze(lua_code, ocsf_version),
        )

        # 4. Source Parser Field Analysis
        if parser_config:
            parser_fields = self._run_check(
                "source_fields",
                lambda: self.source_analyzer.analyze_parser(parser_config),
            )
            results["source_fields"] = parser_fields

            # Cross-reference source fields with Lua
            if parser_fields and not parser_fields.get("error"):
                results["field_comparison"] = self._run_check(
                    "field_comparison",
                    lambda: self.source_analyzer.compare_with_lua(
                        parser_fields, lua_code
                    ),
                )
        else:
            results["source_fields"] = {"skipped": True, "reason": "No parser config provided"}
            results["field_comparison"] = {"skipped": True, "reason": "No parser config provided"}

        # 5. Test Event Execution
        test_events = custom_test_events
        test_event_source = "custom" if custom_test_events else "fallback"
        jarvis_match_type = "none"
        jarvis_generator_key = ""

        if not test_events and parser_config:
            # Try Jarvis realistic events first
            parser_name = parser_config.get("parser_name", "")
            resolved = self.jarvis_bridge.resolve_generator(parser_name) if parser_name else {
                "match_type": "none",
                "generator_key": "",
            }
            if parser_name and resolved.get("match_type") != "none":
                jarvis_events = self.jarvis_bridge.get_events(parser_name, count=4)
                if jarvis_events:
                    test_events = jarvis_events
                    test_event_source = "jarvis"
                    jarvis_match_type = resolved.get("match_type", "none")
                    jarvis_generator_key = resolved.get("generator_key", "")
                    logger.info("Using Jarvis events for %s (%d events)", parser_name, len(test_events))

            # Fall through to TestEventBuilder
            if not test_events:
                parser_info = results.get("source_fields", {})
                if not parser_info.get("skipped") and not parser_info.get("error"):
                    test_events_raw = self._run_check(
                        "test_event_build",
                        lambda: self.event_builder.build_events(parser_info),
                    )
                    if isinstance(test_events_raw, list):
                        test_events = test_events_raw
                        test_event_source = "builder"

            # Final fallback: generate minimal test events
            if not test_events:
                test_events = self._generate_fallback_test_events()
                test_event_source = "fallback"

        if test_events:
            ocsf_required = self.ocsf_registry.get_required_fields(
                results.get("ocsf_mapping", {}).get("class_uid"),
                ocsf_version,
            )
            results["test_execution"] = self._run_check(
                "test_execution",
                lambda: self.execution_engine.execute(
                    lua_code, test_events, ocsf_required
                ),
            )
        else:
            results["test_execution"] = {
                "skipped": True,
                "reason": "No test events available",
            }
        results["test_event_source"] = {
            "source": test_event_source,
            "jarvis_match_type": jarvis_match_type,
            "jarvis_generator_key": jarvis_generator_key,
        }

        ocsf_alignment = self._build_ocsf_alignment_report(results.get("ocsf_mapping", {}))
        results["ocsf_alignment"] = ocsf_alignment

        # Compute overall confidence score
        confidence = self._compute_confidence(results)
        elapsed = time.time() - start

        return {
            "confidence_score": confidence["score"],
            "confidence_grade": confidence["grade"],
            "check_summary": confidence["summary"],
            "ocsf_version": ocsf_version,
            "available_versions": self.ocsf_registry.list_versions(),
            "checks": results,
            "ocsf_alignment": ocsf_alignment,
            "elapsed_seconds": round(elapsed, 2),
        }

    def run_single_check(
        self,
        check_name: str,
        lua_code: str,
        parser_config: Optional[Dict] = None,
        ocsf_version: str = "1.3.0",
        test_events: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Run a single named check."""
        if check_name == "lua_validity":
            return self.validity_checker.check(lua_code)
        elif check_name == "lua_linting":
            return self.linter.lint(lua_code)
        elif check_name == "ocsf_mapping":
            return self.ocsf_analyzer.analyze(lua_code, ocsf_version)
        elif check_name == "source_fields" and parser_config:
            return self.source_analyzer.analyze_parser(parser_config)
        elif check_name == "field_comparison" and parser_config:
            fields = self.source_analyzer.analyze_parser(parser_config)
            return self.source_analyzer.compare_with_lua(fields, lua_code)
        elif check_name == "test_execution" and test_events:
            ocsf_required = self.ocsf_registry.get_required_fields(None, ocsf_version)
            return self.execution_engine.execute(lua_code, test_events, ocsf_required)
        else:
            return {"error": f"Unknown or invalid check: {check_name}"}

    def _generate_fallback_test_events(self) -> List[Dict[str, Any]]:
        """Generate minimal fallback test events when source field analysis fails."""
        return [
            {
                "name": "fallback_happy_path",
                "event": {
                    "timestamp": "2024-01-15T10:30:00Z",
                    "event_id": "evt-001",
                    "source_ip": "192.168.1.100",
                    "dest_ip": "10.0.0.1",
                    "user": "admin@example.com",
                    "action": "login",
                    "status": "success",
                    "severity": "info",
                    "message": "User authentication successful",
                },
                "expected_behavior": "Should produce valid OCSF event with required fields",
            },
            {
                "name": "fallback_minimal",
                "event": {
                    "timestamp": "2024-01-15T10:31:00Z",
                    "message": "minimal event",
                },
                "expected_behavior": "Should handle minimal input gracefully",
            },
            {
                "name": "fallback_edge_case",
                "event": {
                    "timestamp": "",
                    "source_ip": "::ffff:192.168.1.1",
                    "user": "test\u00e9@example.com",
                    "message": "A" * 500,
                    "port": -1,
                },
                "expected_behavior": "Should handle edge cases without crashing",
            },
        ]

    def _run_check(self, name: str, fn) -> Dict[str, Any]:
        """Run a check with error handling."""
        try:
            result = fn()
            return result if isinstance(result, dict) else {"result": result}
        except Exception as e:
            logger.error("Harness check '%s' failed: %s", name, e)
            return {"error": str(e), "status": "error"}

    def _build_ocsf_alignment_report(self, mapping: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize OCSF alignment attempt and coverage details."""
        if not isinstance(mapping, dict) or mapping.get("error"):
            return {
                "status": "none",
                "attempted": False,
                "class_uid": None,
                "required_total": 0,
                "required_mapped": 0,
                "required_missing": [],
                "required_coverage": 0,
            }

        class_uid = mapping.get("class_uid")
        missing = mapping.get("missing_required", []) or []
        required_coverage = mapping.get("required_coverage", 0) or 0
        field_details = mapping.get("field_details", []) or []
        required_present = [
            item.get("field")
            for item in field_details
            if isinstance(item, dict) and item.get("status") == "required_present"
        ]
        required_total = len(required_present) + len(missing)

        status = "none"
        if class_uid:
            if required_coverage >= 80:
                status = "strong"
            elif required_coverage > 0:
                status = "partial"
            else:
                status = "attempted"

        return {
            "status": status,
            "attempted": bool(class_uid),
            "class_uid": class_uid,
            "required_total": required_total,
            "required_mapped": len(required_present),
            "required_missing": missing,
            "required_coverage": required_coverage,
        }

    def _compute_confidence(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute overall confidence score from individual check results.

        Weighting:
        - Lua validity: 25% (must pass for any confidence)
        - Lua linting: 15% (quality indicator)
        - OCSF mapping: 25% (correctness of field mapping)
        - Source field coverage: 15% (completeness)
        - Test execution: 20% (runtime correctness)
        """
        weights = {
            "lua_validity": 25,
            "lua_linting": 15,
            "ocsf_mapping": 25,
            "field_comparison": 15,
            "test_execution": 20,
        }

        scores = {}
        summary = {}

        # Lua validity: binary pass/fail
        validity = results.get("lua_validity", {})
        if validity.get("error") or validity.get("skipped"):
            scores["lua_validity"] = 0
            summary["lua_validity"] = "error"
        elif validity.get("valid", False):
            scores["lua_validity"] = 100
            summary["lua_validity"] = "passed"
        else:
            scores["lua_validity"] = 0
            summary["lua_validity"] = "failed"

        # Lua linting: use the score directly
        linting = results.get("lua_linting", {})
        if linting.get("error") or linting.get("skipped"):
            scores["lua_linting"] = 50  # neutral if unavailable
            summary["lua_linting"] = "skipped"
        else:
            scores["lua_linting"] = linting.get("score", 50)
            lint_score = scores["lua_linting"]
            if lint_score >= 80:
                summary["lua_linting"] = "good"
            elif lint_score >= 50:
                summary["lua_linting"] = "fair"
            else:
                summary["lua_linting"] = "poor"

        # OCSF mapping: use required coverage percentage
        ocsf = results.get("ocsf_mapping", {})
        if ocsf.get("error") or ocsf.get("skipped"):
            scores["ocsf_mapping"] = 50
            summary["ocsf_mapping"] = "skipped"
        else:
            scores["ocsf_mapping"] = ocsf.get("required_coverage", 0)
            coverage = scores["ocsf_mapping"]
            if coverage >= 90:
                summary["ocsf_mapping"] = "excellent"
            elif coverage >= 70:
                summary["ocsf_mapping"] = "good"
            elif coverage >= 50:
                summary["ocsf_mapping"] = "fair"
            else:
                summary["ocsf_mapping"] = "poor"

        # Field comparison: use coverage percentage
        fields = results.get("field_comparison", {})
        if fields.get("error") or fields.get("skipped"):
            scores["field_comparison"] = 50
            summary["field_comparison"] = "skipped"
        else:
            scores["field_comparison"] = fields.get("coverage_pct", 50)
            summary["field_comparison"] = (
                "good" if scores["field_comparison"] >= 70 else "needs_review"
            )

        # Test execution: pass rate
        execution = results.get("test_execution", {})
        if execution.get("error") or execution.get("skipped"):
            scores["test_execution"] = 50
            summary["test_execution"] = "skipped"
        else:
            total = execution.get("total_events", 0)
            passed = execution.get("passed", 0)
            if total > 0:
                scores["test_execution"] = round((passed / total) * 100)
            else:
                scores["test_execution"] = 50
            summary["test_execution"] = (
                "passed" if scores["test_execution"] >= 75 else "needs_review"
            )

        # Weighted average
        total_weight = sum(weights.values())
        weighted_sum = sum(
            scores.get(check, 50) * weight for check, weight in weights.items()
        )
        baseline_score = round(weighted_sum / total_weight)
        semantic_penalties = self._compute_semantic_penalties(results)
        overall_score = max(0, baseline_score - semantic_penalties["total"])

        # Grade
        if overall_score >= 90:
            grade = "A"
        elif overall_score >= 80:
            grade = "B"
        elif overall_score >= 70:
            grade = "C"
        elif overall_score >= 60:
            grade = "D"
        else:
            grade = "F"

        return {
            "score": overall_score,
            "grade": grade,
            "summary": summary,
            "component_scores": scores,
            "baseline_score": baseline_score,
            "semantic_penalties": semantic_penalties,
        }

    def _compute_semantic_penalties(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Penalize scripts that are syntactically valid but semantically shallow.
        This improves quality for source-specific mappings.
        """
        penalties: List[Dict[str, Any]] = []

        mapping = results.get("ocsf_mapping", {}) or {}
        field_cmp = results.get("field_comparison", {}) or {}
        source_info = results.get("source_fields", {}) or {}

        semantic = mapping.get("semantic_signals", {}) if isinstance(mapping, dict) else {}
        placeholder_count = int(semantic.get("placeholder_count") or 0)
        has_unmapped_bucket = bool(semantic.get("has_unmapped_bucket"))

        if placeholder_count > 0:
            amount = min(15, placeholder_count * 3)
            penalties.append({
                "id": "placeholder_values",
                "amount": amount,
                "reason": f"Found {placeholder_count} placeholder value literal(s) (e.g., Unknown*)",
            })

        coverage = float(field_cmp.get("coverage_pct", 100) or 100)
        if has_unmapped_bucket and coverage < 40:
            penalties.append({
                "id": "excessive_unmapped",
                "amount": 8,
                "reason": f"Low source-field coverage ({coverage:.1f}%) with heavy fallback to `unmapped`",
            })

        source_family = self._infer_source_family(source_info)
        class_uid = mapping.get("class_uid")
        expected_uid = {
            "cisco_duo": 3002,
            "akamai_dns": 4003,
            "akamai_cdn_http": 4002,
        }.get(source_family)
        if expected_uid and class_uid and class_uid != expected_uid:
            penalties.append({
                "id": "source_class_mismatch",
                "amount": 10,
                "reason": f"Source family `{source_family}` expected class_uid {expected_uid}, got {class_uid}",
            })

        # Missing helper definitions: script calls helpers it doesn't define.
        # The sandbox backfills them so tests pass, but production will crash.
        linting = results.get("lua_linting", {}) or {}
        lint_issues = linting.get("issues", []) if isinstance(linting, dict) else []
        missing_helpers = [
            i for i in lint_issues
            if i.get("rule") == "helper_dependencies"
            and "not defined" in i.get("message", "")
        ]
        if missing_helpers:
            penalties.append({
                "id": "missing_helper_definitions",
                "amount": 25,
                "reason": f"{len(missing_helpers)} helper(s) called but not defined — will crash in production",
            })

        msg_penalty = self._compute_embedded_payload_penalty(
            class_uid=class_uid,
            execution=results.get("test_execution", {}) or {},
        )
        if msg_penalty:
            penalties.append(msg_penalty)

        total = sum(int(p["amount"]) for p in penalties)
        return {"total": total, "details": penalties}

    def _compute_embedded_payload_penalty(
        self,
        class_uid: Optional[int],
        execution: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if not class_uid or not isinstance(execution, dict):
            return None
        run_results = execution.get("results") or []
        if not isinstance(run_results, list) or not run_results:
            return None

        expected_by_class = {
            4003: ["query.hostname", "query.type", "rcode", "rcode_id", "src_endpoint.ip", "answers"],
            4002: ["http_request.url", "http_request.http_method", "http_response.code", "src_endpoint.ip"],
            3002: ["actor.user.name", "src_endpoint.ip", "auth_protocol", "mfa_factors"],
            2004: ["finding_info.title", "finding_info.uid", "activity_name"],
        }
        expected = expected_by_class.get(class_uid, [])
        if not expected:
            return None

        message_present = False
        extracted_any = False
        hinted_missing_fields: set[str] = set()
        for item in run_results:
            if not isinstance(item, dict):
                continue
            input_event = item.get("input_event") or {}
            output_event = item.get("output_event") or {}
            if not isinstance(input_event, dict) or not isinstance(output_event, dict):
                continue
            if "message" in input_event and input_event.get("message") not in (None, ""):
                message_present = True
                if any(self._has_path(output_event, field_path) for field_path in expected):
                    extracted_any = True
                missing_with_hints = self._missing_expected_with_input_hints(
                    input_event=input_event,
                    output_event=output_event,
                    expected_fields=expected,
                )
                hinted_missing_fields.update(missing_with_hints)

        if message_present and hinted_missing_fields:
            preview = ", ".join(sorted(hinted_missing_fields)[:4])
            return {
                "id": "embedded_expected_fields_missing",
                "amount": 8,
                "reason": f"Embedded payload contains source hints but mapped output left expected field(s) blank: {preview}",
            }

        if message_present and not extracted_any:
            return {
                "id": "embedded_message_not_parsed",
                "amount": 10,
                "reason": "Message payload present but class-semantic fields were not extracted from embedded data",
            }
        return None

    def _missing_expected_with_input_hints(
        self,
        input_event: Dict[str, Any],
        output_event: Dict[str, Any],
        expected_fields: List[str],
    ) -> List[str]:
        flat_input = self._flatten_dict(input_event)
        kv_fields = self._extract_embedded_kv_fields(input_event)
        hinted_missing: List[str] = []
        aliases = self._expected_field_aliases()
        for field in expected_fields:
            if self._has_path(output_event, field):
                continue
            candidate_keys = aliases.get(field, [field])
            if any(
                (k in flat_input and flat_input.get(k) not in (None, ""))
                or (k in kv_fields and kv_fields.get(k) not in (None, ""))
                for k in candidate_keys
            ):
                hinted_missing.append(field)
        return hinted_missing

    def _extract_embedded_kv_fields(self, input_event: Dict[str, Any]) -> Dict[str, str]:
        kv: Dict[str, str] = {}
        for key in ("message", "raw"):
            raw = input_event.get(key)
            if not isinstance(raw, str) or not raw.strip():
                continue
            for match in re.finditer(
                r'([A-Za-z_][A-Za-z0-9_.-]*)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s,]+))',
                raw,
            ):
                field = match.group(1)
                value = match.group(2) or match.group(3) or match.group(4) or ""
                if field and value:
                    kv[field] = value
        return kv

    def _flatten_dict(self, obj: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        flat: Dict[str, Any] = {}
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, dict):
                flat.update(self._flatten_dict(value, path))
            else:
                flat[path] = value
        return flat

    def _expected_field_aliases(self) -> Dict[str, List[str]]:
        return {
            "src_endpoint.ip": [
                "src_endpoint.ip", "source_ip", "src_ip", "ip", "client.ip", "client_ip",
                "clientIP", "cliIP", "sourceIPAddress",
            ],
            "query.hostname": ["query.hostname", "domain", "host", "hostname", "reqHost", "qname"],
            "query.type": ["query.type", "recordType", "queryType", "qtype", "type"],
            "rcode": ["rcode", "responseCode", "statusCode", "status"],
            "rcode_id": ["rcode_id", "responseCode", "statusCode", "rcode"],
            "http_request.url": ["http_request.url", "url", "request", "reqPath", "path", "uri"],
            "http_request.http_method": ["http_request.http_method", "method", "reqMethod"],
            "http_response.code": ["http_response.code", "responseCode", "statusCode"],
            "actor.user.name": ["actor.user.name", "user", "username", "AccountName", "name"],
            "auth_protocol": ["auth_protocol", "method", "protocol", "authProtocol"],
            "mfa_factors": ["mfa_factors", "mfa", "mfaRequired", "mfa_required"],
        }

    def _has_path(self, obj: Dict[str, Any], dotted_path: str) -> bool:
        current: Any = obj
        for part in dotted_path.split("."):
            if not isinstance(current, dict) or part not in current:
                return False
            current = current.get(part)
        return current not in (None, "")

    def _infer_source_family(self, source_info: Dict[str, Any]) -> str:
        parser_name = (source_info.get("parser_name") or "").lower()
        vendor = (source_info.get("vendor") or "").lower()
        product = (source_info.get("product") or "").lower()
        combined = f"{parser_name} {vendor} {product}"

        if "duo" in combined:
            return "cisco_duo"
        if "akamai" in combined and "dns" in combined:
            return "akamai_dns"
        if "akamai" in combined and re.search(r"\b(cdn|http|waf)\b", combined):
            return "akamai_cdn_http"
        if "defender" in combined or "mdatp" in combined:
            return "ms_defender"
        return "generic"
