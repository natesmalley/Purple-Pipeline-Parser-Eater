"""
Comprehensive Pipeline Validation Framework

DIRECTOR REQUIREMENT 4: Validate JSON via upload/testing
Implements:
- Schema validation for pipeline.json
- LUA syntax validation (sandbox checks)
- Automated dry-run tests with sample events
- Field extraction verification
- Results recorded in validation_report.json
"""
import json
import logging
import re
from typing import Dict, List, Any, Tuple, Optional
from pathlib import Path
from datetime import datetime

# Import SecurityError from dataplane_validator
try:
    from .dataplane_validator import SecurityError
except ImportError:
    # Fallback if relative import fails
    class SecurityError(Exception):  # type: ignore
        """Security-related error (path traversal, injection attempt, etc.)"""
        pass

logger = logging.getLogger(__name__)

# Try to import lupa for LUA syntax validation
try:
    import lupa
    LUPA_AVAILABLE = True
except ImportError:
    LUPA_AVAILABLE = False
    logger.warning("lupa not available - LUA syntax validation will be limited")

try:
    from .dataplane_validator import DataplaneValidator
except (ImportError, AttributeError, ModuleNotFoundError) as e:
    logger.warning(f"DataplaneValidator unavailable: {e}")
    DataplaneValidator = None  # type: ignore


class PipelineValidator:
    """
    Comprehensive validation for generated pipelines

    TRACEABILITY:
    - Requirement 4: Automated validation pipeline
    - Schema validation, syntax checks, dry-run tests
    - Records all results in validation_report.json
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize validator

        Args:
            config: Optional configuration
        """
        self.config = config or {}
        self.validation_errors = []
        self.validation_warnings = []
        self.dataplane_validator = None

        dataplane_cfg = self.config.get("dataplane", {})
        enabled = dataplane_cfg.get("enabled", False)
        if enabled and DataplaneValidator is not None:
            binary_path = dataplane_cfg.get("binary_path", "/opt/dataplane/dataplane")
            ocsf_fields = dataplane_cfg.get("ocsf_required_fields", [])
            try:
                self.dataplane_validator = DataplaneValidator(
                    binary_path=binary_path,
                    ocsf_required_fields=ocsf_fields,
                    timeout=dataplane_cfg.get("timeout_seconds", 30),
                )
                logger.info("Dataplane validator initialised (binary=%s)", binary_path)
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("Failed to initialise DataplaneValidator: %s", exc)
                self.dataplane_validator = None
        elif enabled:
            logger.warning("Dataplane validation requested but DataplaneValidator unavailable")

    def _validate_lua_code_safety(self, lua_code: str) -> Tuple[bool, List[str]]:
        """
        Validate Lua code doesn't contain dangerous patterns.

        SECURITY: Checks for code injection patterns, system calls, and
        dangerous functions.

        Args:
            lua_code: Lua code to validate

        Returns:
            Tuple of (is_safe, list_of_errors)
        """
        errors = []

        # Dangerous patterns that could lead to code injection or system access
        dangerous_patterns = [
            # System execution
            (r'os\.execute\s*\(', 'os.execute() - system command execution'),
            (r'io\.popen\s*\(', 'io.popen() - process creation'),
            (r'os\.getenv\s*\(', 'os.getenv() - environment variable access'),
            (r'os\.remove\s*\(', 'os.remove() - file deletion'),
            (r'os\.rename\s*\(', 'os.rename() - file manipulation'),

            # Dangerous require statements
            (
                r"require\s*\(\s*['\"]os['\"]",
                "require('os') - OS module import"
            ),
            (
                r"require\s*\(\s*['\"]io['\"]",
                "require('io') - IO module import"
            ),
            (
                r"require\s*\(\s*['\"]package['\"]",
                "require('package') - package module import"
            ),

            # Code loading functions
            (r'loadstring\s*\(', 'loadstring() - dynamic code loading'),
            (r'loadfile\s*\(', 'loadfile() - file loading'),
            (r'dofile\s*\([^)]*\.\.', 'dofile() with path traversal'),

            # Python/Lua bridge attacks (if sandbox allows)
            (r'__import__', '__import__ - Python import attempt'),
            (r'__builtins__', '__builtins__ - builtin access'),
            (r'__globals__', '__globals__ - global access'),
            (r'__code__', '__code__ - code object access'),

            # File system operations
            (
                r'io\.open\s*\([^)]*[\'"]w[\'"]',
                'io.open() with write mode'
            ),
            (
                r'io\.open\s*\([^)]*[\'"]a[\'"]',
                'io.open() with append mode'
            ),

            # Network operations (if not needed)
            (r'socket\.', 'socket.* - network operations'),
            (r'http\.', 'http.* - HTTP operations'),
        ]

        # Check each pattern
        for pattern, description in dangerous_patterns:
            matches = re.finditer(
                pattern,
                lua_code,
                re.IGNORECASE | re.MULTILINE
            )
            for match in matches:
                # Get context (20 chars before and after)
                start = max(0, match.start() - 20)
                end = min(len(lua_code), match.end() + 20)
                context = lua_code[start:end].replace('\n', '\\n')

                error_msg = (
                    f"Dangerous pattern detected: {description}\n"
                    f"Location: character {match.start()}\n"
                    f"Context: ...{context}..."
                )
                errors.append(error_msg)
                logger.warning(
                    "Dangerous Lua pattern detected: %s at position %d",
                    description,
                    match.start()
                )

        # Additional check: Look for suspicious string concatenation patterns
        # that might be used to bypass pattern matching
        suspicious_concat = re.search(
            r'["\']\s*\.\.\s*[^"\']+\s*\.\.\s*["\']',
            lua_code
        )
        if suspicious_concat:
            errors.append(
                "Suspicious string concatenation pattern detected - "
                "possible attempt to bypass validation"
            )

        is_safe = len(errors) == 0
        return is_safe, errors

    def validate_complete_pipeline(
        self,
        parser_id: str,
        pipeline_json: Dict[str, Any],
        lua_code: str,
        original_parser_config: Optional[Dict] = None,
        sample_events: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Run complete validation suite

        Args:
            parser_id: Parser identifier
            pipeline_json: Complete pipeline JSON
            lua_code: Generated LUA transformation code
            original_parser_config: Original S1 parser config (for field comparison)
            sample_events: Sample events for dry-run testing

        Returns:
            Complete validation report

        REQUIREMENT 4: Comprehensive validation
        """
        logger.info(f"Running complete validation for: {parser_id}")

        validation_results = {
            "parser_id": parser_id,
            "validated_at": datetime.now().isoformat(),
            "validations": {}
        }

        # 1. Schema Validation
        schema_result = self.validate_pipeline_schema(pipeline_json)
        validation_results["validations"]["schema"] = schema_result

        # 2. LUA Syntax Validation
        syntax_result = self.validate_lua_syntax(lua_code)
        validation_results["validations"]["lua_syntax"] = syntax_result

        # 3. LUA Semantic Validation
        semantic_result = self.validate_lua_semantics(lua_code)
        validation_results["validations"]["lua_semantics"] = semantic_result

        # 4. Field Extraction Verification (if original parser available)
        if original_parser_config:
            field_result = self.validate_field_extraction(
                lua_code,
                original_parser_config
            )
            validation_results["validations"]["field_extraction"] = field_result

        # 5. Dry-Run Tests (if sample events available)
        if sample_events:
            dryrun_result = self.run_dryrun_tests(lua_code, sample_events)
            validation_results["validations"]["dry_run_tests"] = dryrun_result

        # 6. Metadata Completeness
        metadata_result = self.validate_metadata(pipeline_json)
        validation_results["validations"]["metadata"] = metadata_result

        # 7. Dataplane runtime validation (optional)
        if self.dataplane_validator and sample_events:
            dataplane_result = self._validate_with_dataplane(parser_id, lua_code, sample_events)
            validation_results["validations"]["dataplane_runtime"] = dataplane_result

        # Overall status
        all_validations = validation_results["validations"].values()
        validation_results["overall_status"] = (
            "passed" if all(v.get("status") == "passed" for v in all_validations)
            else "failed"
        )

        validation_results["error_count"] = sum(len(v.get("errors", [])) for v in all_validations)
        validation_results["warning_count"] = sum(len(v.get("warnings", [])) for v in all_validations)

        logger.info(f"Validation complete: {validation_results['overall_status']}")
        return validation_results

    def _validate_with_dataplane(
        self,
        parser_id: str,
        lua_code: str,
        sample_events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Run dataplane runtime validation, returning structured result."""

        wrapped_events = [{"log": event} for event in sample_events]

        try:
            result = self.dataplane_validator.validate(lua_code, wrapped_events, parser_id)  # type: ignore[attr-defined]
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Dataplane validation exception for %s: %s", parser_id, exc)
            return {
                "status": "failed",
                "errors": [str(exc)],
                "warnings": [],
                "ocsf_missing_fields": [],
                "stderr": "",
                "sample_events": len(sample_events),
            }

        status = "passed" if result.success else "failed"
        errors = []
        if not result.success:
            if result.error:
                errors.append(result.error)
            if result.ocsf_missing_fields:
                errors.append(
                    f"missing OCSF fields: {', '.join(result.ocsf_missing_fields)}"
                )

        return {
            "status": status,
            "errors": errors,
            "warnings": [],
            "ocsf_missing_fields": result.ocsf_missing_fields,
            "stderr": result.stderr,
            "output_event_count": len(result.output_events),
        }

    def validate_pipeline_schema(self, pipeline_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate pipeline.json schema

        REQUIREMENT 4: Schema validation for pipeline.json
        Ensures all required fields are present and correctly typed
        """
        errors = []
        warnings = []

        # Required top-level fields
        required_fields = {
            "siteId": (int, "Site ID"),
            "pipeline": (dict, "Pipeline definition"),
            "pipelineGraph": (dict, "Pipeline graph"),
            "source": (dict, "Source configuration"),
            "transforms": (list, "Transform list"),
            "metadata": (dict, "Metadata")
        }

        for field, (expected_type, description) in required_fields.items():
            if field not in pipeline_json:
                errors.append(f"Missing required field: {field} ({description})")
            elif not isinstance(pipeline_json[field], expected_type):
                errors.append(f"Invalid type for {field}: expected {expected_type.__name__}, got {type(pipeline_json[field]).__name__}")

        # Validate transforms structure
        if "transforms" in pipeline_json and isinstance(pipeline_json["transforms"], list):
            if len(pipeline_json["transforms"]) == 0:
                errors.append("Transforms list is empty")
            else:
                for idx, transform in enumerate(pipeline_json["transforms"]):
                    if not isinstance(transform, dict):
                        errors.append(f"Transform[{idx}] is not a dictionary")
                    elif "type" not in transform:
                        errors.append(f"Transform[{idx}] missing 'type' field")
                    elif "lua_code" not in transform and transform.get("type") == "lua":
                        errors.append(f"LUA transform[{idx}] missing 'lua_code' field")

        # Validate metadata structure
        if "metadata" in pipeline_json and isinstance(pipeline_json["metadata"], dict):
            recommended_metadata = ["source", "parser_id", "converted_at", "fields_extracted"]
            for field in recommended_metadata:
                if field not in pipeline_json["metadata"]:
                    warnings.append(f"Recommended metadata field missing: {field}")

        return {
            "status": "passed" if len(errors) == 0 else "failed",
            "errors": errors,
            "warnings": warnings,
            "checks_performed": len(required_fields) + 1  # +1 for transforms validation
        }

    def validate_lua_syntax(self, lua_code: str) -> Dict[str, Any]:
        """
        Validate LUA syntax using lupa sandbox

        REQUIREMENT 4: Sandbox syntax check
        Uses lupa (if available) to parse and validate LUA syntax
        """
        errors = []
        warnings = []

        # SECURITY FIX: Validate code safety BEFORE execution
        is_safe, safety_errors = self._validate_lua_code_safety(lua_code)
        if not is_safe:
            errors.extend(safety_errors)
            return {
                "status": "failed",
                "errors": errors,
                "warnings": warnings,
                "method": "pattern_validation",
                "blocked": True
            }

        if not LUPA_AVAILABLE:
            warnings.append("lupa not available - syntax validation is limited")
            # Fall back to basic pattern checks
            basic_result = self._basic_lua_syntax_check(lua_code)
            return basic_result

        try:
            # Create LUA runtime with security restrictions
            lua = lupa.LuaRuntime(
                unpack_returned_tuples=True,
                register_eval=False,  # Disable eval() for security
                register_builtins=False  # Don't register all builtins
            )

            # Execute the Lua code directly (wrapping in temp function breaks
            # multi-function scripts with string literals spanning lines)
            lua.execute(lua_code)

            # If we got here, syntax is valid
            return {
                "status": "passed",
                "errors": [],
                "warnings": warnings,
                "method": "lupa_sandbox"
            }

        except lupa.LuaSyntaxError as e:
            errors.append(f"LUA syntax error: {str(e)}")
            return {
                "status": "failed",
                "errors": errors,
                "warnings": warnings,
                "method": "lupa_sandbox"
            }
        except Exception as e:
            errors.append(f"Unexpected error during LUA validation: {str(e)}")
            return {
                "status": "failed",
                "errors": errors,
                "warnings": warnings,
                "method": "lupa_sandbox"
            }

    def _basic_lua_syntax_check(self, lua_code: str) -> Dict[str, Any]:
        """
        Basic LUA syntax checks without lupa

        Fallback validation when lupa is not available
        """
        errors = []
        warnings = []

        # Check for entry function (processEvent, transform, or process)
        if "function processEvent" not in lua_code and "function transform" not in lua_code and "function process" not in lua_code:
            errors.append("Missing entry function ('function processEvent', 'function transform', or 'function process')")
        if "end" not in lua_code:
            errors.append("Missing 'end' keyword")

        # Check for balanced brackets
        if lua_code.count("{") != lua_code.count("}"):
            errors.append("Unbalanced curly braces")

        if lua_code.count("(") != lua_code.count(")"):
            errors.append("Unbalanced parentheses")

        # Check for common syntax mistakes
        if re.search(r'function\s+\w+\s*\(.*\)\s*$', lua_code, re.MULTILINE):
            warnings.append("Function declaration not followed by code block")

        return {
            "status": "passed" if len(errors) == 0 else "failed",
            "errors": errors,
            "warnings": warnings,
            "method": "basic_pattern_check"
        }

    def validate_lua_semantics(self, lua_code: str) -> Dict[str, Any]:
        """
        Validate LUA semantic patterns (Observo best practices)

        REQUIREMENT 4: Semantic validation
        Checks for Observo-recommended patterns
        """
        errors = []
        warnings = []

        # Check for processEvent, transform, or process function (all are valid)
        has_processEvent = bool(re.search(r'function\s+processEvent\s*\(', lua_code))
        has_transform = bool(re.search(r'function\s+transform\s*\(', lua_code))
        has_process = bool(re.search(r'function\s+process\s*\(', lua_code))
        if not has_processEvent and not has_transform and not has_process:
            errors.append("Missing entry function (expected 'function processEvent(event)', 'function transform(event)', or 'function process(event, emit)')")

        # Check for return/emit in the main function
        if has_processEvent:
            pe_match = re.search(r'function\s+processEvent\s*\([^)]*\)(.*?)(?:function\s+\w|$)', lua_code, re.DOTALL)
            if pe_match and 'return' not in pe_match.group(1):
                errors.append("processEvent function missing 'return' statement")
        if has_transform:
            transform_match = re.search(r'function\s+transform\s*\([^)]*\)(.*?)(?:function\s+\w|$)', lua_code, re.DOTALL)
            if transform_match and 'return' not in transform_match.group(1):
                errors.append("Transform function missing 'return' statement")
        if has_process:
            process_match = re.search(r'function\s+process\s*\([^)]*\)(.*?)(?:function\s+\w|$)', lua_code, re.DOTALL)
            if process_match and 'emit(' not in process_match.group(1) and 'emit (' not in process_match.group(1):
                errors.append("Process function missing 'emit()' call")

        # Check for nil safety patterns (recommended)
        if lua_code.count('if') > 0 and lua_code.count('nil') == 0:
            warnings.append("No nil checks found - consider adding defensive nil checks")

        # Check for OCSF fields (if applicable)
        ocsf_fields = ['class_uid', 'category_uid', 'activity_id', 'time', 'type_uid', 'severity_id']
        has_ocsf = any(field in lua_code for field in ocsf_fields)

        if has_ocsf:
            # Validate OCSF structure
            if 'class_uid' in lua_code and not re.search(r'class_uid\s*=\s*\d+', lua_code):
                warnings.append("class_uid should be assigned a numeric value")

        return {
            "status": "passed" if len(errors) == 0 else "failed",
            "errors": errors,
            "warnings": warnings,
            "checks_performed": 4
        }

    def validate_field_extraction(
        self,
        lua_code: str,
        original_parser_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Verify that generated LUA extracts same fields as original parser

        REQUIREMENT 5: Field-level equivalence verification
        Compares expected fields from S1 parser with fields in generated LUA
        """
        errors = []
        warnings = []

        # Extract expected fields from original parser
        expected_fields = self._extract_fields_from_parser(original_parser_config)

        # Extract fields referenced in LUA code
        lua_fields = self._extract_fields_from_lua(lua_code)

        # Compare
        missing_fields = expected_fields - lua_fields
        extra_fields = lua_fields - expected_fields

        if missing_fields:
            errors.append(f"Missing fields in LUA: {sorted(missing_fields)}")

        if extra_fields:
            warnings.append(f"Additional fields in LUA (not in original): {sorted(extra_fields)}")

        coverage_percentage = (
            len(expected_fields & lua_fields) / len(expected_fields) * 100
            if expected_fields else 100
        )

        return {
            "status": "passed" if len(errors) == 0 else "failed",
            "errors": errors,
            "warnings": warnings,
            "expected_fields": sorted(expected_fields),
            "extracted_fields": sorted(lua_fields),
            "missing_fields": sorted(missing_fields),
            "extra_fields": sorted(extra_fields),
            "coverage_percentage": round(coverage_percentage, 2)
        }

    def _extract_fields_from_parser(self, parser_config: Dict[str, Any]) -> set:
        """Extract field names from S1 parser configuration"""
        fields = set()

        # Different parser formats store fields in different places
        if "fields" in parser_config:
            for field_config in parser_config["fields"]:
                if isinstance(field_config, dict) and "name" in field_config:
                    fields.add(field_config["name"])
                elif isinstance(field_config, str):
                    fields.add(field_config)

        if "mappings" in parser_config:
            for mapping in parser_config["mappings"]:
                if isinstance(mapping, dict):
                    if "source" in mapping:
                        fields.add(mapping["source"])
                    if "target" in mapping:
                        fields.add(mapping["target"])

        # Look for field references in patterns
        if "patterns" in parser_config:
            for pattern in parser_config["patterns"]:
                if isinstance(pattern, str):
                    # Extract field names from grok patterns: %{PATTERN:field_name}
                    field_matches = re.findall(r'%\{[^:]+:(\w+)\}', pattern)
                    fields.update(field_matches)

        return fields

    def _extract_fields_from_lua(self, lua_code: str) -> set:
        """Extract field references from LUA code"""
        fields = set()

        # Pattern 1: event["field_name"] or event['field_name']
        field_matches = re.findall(r'event\[["\']([\w.]+)["\']\]', lua_code)
        fields.update(field_matches)

        # Pattern 2: event.field_name
        field_matches = re.findall(r'event\.([\w]+)', lua_code)
        fields.update(field_matches)

        # Pattern 3: output.field_name = ...
        field_matches = re.findall(r'output\.([\w.]+)\s*=', lua_code)
        fields.update(field_matches)

        return fields

    def run_dryrun_tests(self, lua_code: str, sample_events: List[Dict]) -> Dict[str, Any]:
        """
        Execute LUA against sample events (dry-run)

        REQUIREMENT 4: Automated dry-run tests
        Runs LUA transformation against sample data to verify it works

        SECURITY: Sandboxed execution with restricted libraries
        """
        errors = []
        warnings = []
        test_results = []

        if not LUPA_AVAILABLE:
            warnings.append("lupa not available - cannot execute dry-run tests")
            return {
                "status": "skipped",
                "errors": [],
                "warnings": warnings,
                "tests_run": 0
            }

        try:
            # SECURITY FIX: Create sandboxed Lua runtime with restricted libraries
            lua = lupa.LuaRuntime(
                unpack_returned_tuples=True,
                register_eval=False,  # Disable eval() for security
                attribute_filter=self._lua_attribute_filter  # Restrict attribute access
            )

            # SECURITY: Sandbox - keep safe os.time/os.date, disable dangerous functions
            lua.execute("""
                local safe_os = { time = os.time, date = os.date, clock = os.clock, difftime = os.difftime }
                io = nil
                load = nil
                loadfile = nil
                loadstring = nil
                dofile = nil
                package = nil
                debug = nil
                collectgarbage = nil
                os = safe_os
                require = function(mod) return nil end

                -- Allow only safe string/math/table operations
            """)

            # Load the transformation function in sandboxed environment
            lua.execute(lua_code)
            transform_func = lua.globals().transform

            # Run tests
            for idx, event in enumerate(sample_events):
                try:
                    result = transform_func(event)

                    test_results.append({
                        "test_index": idx,
                        "status": "passed",
                        "input_fields": list(event.keys()),
                        "output_fields": list(result.keys()) if result else [],
                        "output_is_null": result is None
                    })

                except Exception as e:
                    errors.append(f"Test {idx} failed: {str(e)}")
                    test_results.append({
                        "test_index": idx,
                        "status": "failed",
                        "error": str(e)
                    })

        except Exception as e:
            errors.append(f"Failed to execute LUA: {str(e)}")
            return {
                "status": "failed",
                "errors": errors,
                "warnings": warnings,
                "tests_run": 0
            }

        passed_tests = sum(1 for t in test_results if t.get("status") == "passed")

        return {
            "status": "passed" if len(errors) == 0 else "failed",
            "errors": errors,
            "warnings": warnings,
            "tests_run": len(sample_events),
            "tests_passed": passed_tests,
            "test_results": test_results
        }

    def _lua_attribute_filter(self, obj, attr, is_setting):
        """
        SECURITY: Lua attribute filter to prevent access to dangerous Python attributes

        Args:
            obj: The object being accessed
            attr: The attribute name
            is_setting: True if setting, False if getting

        Returns:
            True to allow, False to deny
        """
        # Block access to private/dunder methods
        if attr.startswith('_'):
            logger.warning(f"Blocked Lua access to private attribute: {attr}")
            return False

        # Block access to dangerous attributes
        dangerous_attrs = [
            'import', 'eval', 'exec', 'compile', 'open', 'file',
            '__import__', '__builtins__', '__globals__', '__code__'
        ]

        if attr in dangerous_attrs:
            logger.warning(f"Blocked Lua access to dangerous attribute: {attr}")
            return False

        return True

    def validate_metadata(self, pipeline_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate completeness of AI-SIEM metadata

        REQUIREMENT 6: AI-SIEM metadata validation
        Ensures all required metadata fields are present
        """
        errors = []
        warnings = []

        metadata = pipeline_json.get("metadata", {})

        # Required metadata fields (REQUIREMENT 6)
        required_fields = {
            "source": "Source system",
            "parser_id": "Parser identifier",
            "converted_at": "Conversion timestamp",
            "fields_extracted": "List of extracted fields"
        }

        for field, description in required_fields.items():
            if field not in metadata:
                errors.append(f"Missing required metadata: {field} ({description})")

        # Recommended AI-SIEM fields
        recommended_fields = {
            "ai_siem": {
                "category": "AI-SIEM category",
                "subcategory": "AI-SIEM subcategory",
                "vendor": "Vendor name",
                "product": "Product name",
                "log_type": "Log type"
            }
        }

        if "ai_siem" not in metadata:
            warnings.append("Missing ai_siem metadata block (recommended)")
        else:
            ai_siem = metadata["ai_siem"]
            for field, description in recommended_fields["ai_siem"].items():
                if field not in ai_siem:
                    warnings.append(f"Missing AI-SIEM metadata: {field} ({description})")

        return {
            "status": "passed" if len(errors) == 0 else "failed",
            "errors": errors,
            "warnings": warnings,
            "metadata_fields_present": len(metadata),
            "required_fields_present": sum(1 for f in required_fields if f in metadata)
        }
