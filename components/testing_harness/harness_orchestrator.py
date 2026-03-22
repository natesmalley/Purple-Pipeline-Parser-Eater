"""
Harness Orchestrator - Facade for the 5-point testing harness.

Runs all validation checks and aggregates results into a single
confidence report for display in the web UI.
"""

import logging
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

        if not test_events and parser_config:
            # Try Jarvis realistic events first
            parser_name = parser_config.get("parser_name", "")
            if parser_name and self.jarvis_bridge.has_generator(parser_name):
                jarvis_events = self.jarvis_bridge.get_events(parser_name, count=4)
                if jarvis_events:
                    test_events = jarvis_events
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

            # Final fallback: generate minimal test events
            if not test_events:
                test_events = self._generate_fallback_test_events()

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
        overall_score = round(weighted_sum / total_weight)

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
        }
