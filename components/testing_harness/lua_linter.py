"""Lua linter - best practice rules and quality scoring for Observo.ai Lua scripts."""

import logging
import re
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class LuaLinter:
    """Checks Lua transformation scripts against best-practice rules."""

    RULES = [
        {"name": "global_variables", "severity": "warning", "weight": 5},
        {"name": "string_concat_in_loop", "severity": "warning", "weight": 3},
        {"name": "nil_safety", "severity": "error", "weight": 8},
        {"name": "table_in_loop", "severity": "info", "weight": 2},
        {"name": "ocsf_required_fields", "severity": "error", "weight": 10},
        {"name": "helper_dependencies", "severity": "error", "weight": 12},
        {"name": "dangerous_functions", "severity": "error", "weight": 15},
        {"name": "unused_variables", "severity": "info", "weight": 1},
        {"name": "line_length", "severity": "info", "weight": 1},
        {"name": "comment_density", "severity": "info", "weight": 1},
        {"name": "return_or_emit", "severity": "error", "weight": 10},
    ]

    SEVERITY_MULTIPLIER = {"error": 3, "warning": 1.5, "info": 0.5}

    def lint(self, lua_code: str) -> Dict[str, Any]:
        """
        Run all lint rules against Lua code.

        Returns:
            {"score": float, "issues": [...], "rules_checked": int,
             "summary": {"errors": int, "warnings": int, "info": int}}
        """
        issues: List[Dict[str, Any]] = []
        lines = lua_code.splitlines()

        issues.extend(self._check_global_variables(lines))
        issues.extend(self._check_string_concat_in_loop(lua_code, lines))
        issues.extend(self._check_nil_safety(lua_code))
        issues.extend(self._check_table_in_loop(lua_code, lines))
        issues.extend(self._check_ocsf_required_fields(lua_code))
        issues.extend(self._check_helper_dependencies(lua_code))
        issues.extend(self._check_dangerous_functions(lua_code, lines))
        issues.extend(self._check_unused_variables(lua_code, lines))
        issues.extend(self._check_line_length(lines))
        issues.extend(self._check_comment_density(lines))
        issues.extend(self._check_return_or_emit(lua_code))

        # Compute score
        score = 100.0
        for issue in issues:
            rule_def = next((r for r in self.RULES if r["name"] == issue["rule"]), None)
            weight = rule_def["weight"] if rule_def else 1
            mult = self.SEVERITY_MULTIPLIER.get(issue["severity"], 1)
            score -= mult * weight
        score = max(0.0, round(score, 1))

        summary = {
            "errors": sum(1 for i in issues if i["severity"] == "error"),
            "warnings": sum(1 for i in issues if i["severity"] == "warning"),
            "info": sum(1 for i in issues if i["severity"] == "info"),
        }

        return {
            "score": score,
            "issues": issues,
            "rules_checked": len(self.RULES),
            "summary": summary,
        }

    def _issue(self, rule: str, severity: str, message: str, line: Optional[int] = None) -> Dict:
        return {"rule": rule, "severity": severity, "message": message, "line": line}

    def _check_global_variables(self, lines: List[str]) -> List[Dict]:
        issues = []
        in_function = 0
        in_table = 0
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("--"):
                continue
            # Track table depth (skip assignments inside table constructors)
            in_table += stripped.count("{") - stripped.count("}")
            if in_table > 0:
                continue
            if re.search(r'\bfunction\b', stripped) and not stripped.startswith("local "):
                if re.match(r'^function\s+\w', stripped):
                    in_function += 1
            if re.match(r'^end\s*$', stripped) and in_function > 0:
                in_function -= 1
            # Top-level assignment without 'local' (not inside a function or table)
            if in_function == 0 and re.match(r'^[a-zA-Z_]\w*\s*=\s*', stripped):
                if not stripped.startswith("local ") and not stripped.startswith("function "):
                    var_name = stripped.split("=")[0].strip()
                    # Skip ALL_CAPS constants (conventional Lua constant naming)
                    if re.match(r'^[A-Z_][A-Z_0-9]*$', var_name):
                        continue
                    issues.append(self._issue(
                        "global_variables", "warning",
                        f"Global variable '{var_name}' — consider using 'local'", i
                    ))
        return issues

    def _check_string_concat_in_loop(self, code: str, lines: List[str]) -> List[Dict]:
        issues = []
        in_loop = 0
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if re.search(r'\b(for|while)\b', stripped) and not stripped.startswith("--"):
                in_loop += 1
            if stripped == "end" and in_loop > 0:
                in_loop -= 1
            if in_loop > 0 and ".." in stripped and not stripped.startswith("--"):
                issues.append(self._issue(
                    "string_concat_in_loop", "warning",
                    "String concatenation (..) inside loop — consider table.concat", i
                ))
                break  # Report once
        return issues

    def _check_nil_safety(self, code: str) -> List[Dict]:
        issues = []
        # Look for nil check on the entry function parameter
        has_processEvent = bool(re.search(r'function\s+processEvent\s*\(', code))
        has_transform = bool(re.search(r'function\s+transform\s*\(', code))
        has_process = bool(re.search(r'function\s+process\s*\(', code))

        if has_processEvent or has_transform or has_process:
            # Check if there's any nil/type guard near the entry function
            func_pattern = r'function\s+(?:processEvent|transform|process)\s*\([^)]*\)\s*\n((?:.*\n){0,5})'
            match = re.search(func_pattern, code)
            if match:
                first_lines = match.group(1)
                has_guard = bool(re.search(
                    r'(if\s+.*\bnil\b|if\s+not\s+\w|type\s*\()', first_lines
                ))
                if not has_guard:
                    issues.append(self._issue(
                        "nil_safety", "error",
                        "Entry function lacks nil/type check on input parameter"
                    ))
        return issues

    def _check_table_in_loop(self, code: str, lines: List[str]) -> List[Dict]:
        issues = []
        in_loop = 0
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if re.search(r'\b(for|while)\b', stripped) and not stripped.startswith("--"):
                in_loop += 1
            if stripped == "end" and in_loop > 0:
                in_loop -= 1
            if in_loop > 0 and re.search(r'=\s*\{\s*\}', stripped) and not stripped.startswith("--"):
                issues.append(self._issue(
                    "table_in_loop", "info",
                    "Empty table creation inside loop — consider pre-allocation", i
                ))
                break
        return issues

    def _check_ocsf_required_fields(self, code: str) -> List[Dict]:
        issues = []
        required = ["class_uid", "category_uid", "time", "activity_id", "type_uid", "severity_id"]
        for field in required:
            # Check direct assignment, mapping tables, local constants, or computed patterns
            patterns = [
                rf'\b{field}\b\s*=',
                rf'target\s*=\s*["\'].*{field}',
                rf'OCSF_CLASS_UID|CLASS_UID' if field == "class_uid" else rf'_{field.upper()}',
            ]
            # type_uid is often computed: CLASS_UID * 100 + activity_id
            if field == "type_uid":
                patterns.append(r'TYPE_UID\s*=\s*')
                patterns.append(r'class_uid\s*\*\s*100')
                patterns.append(r'CLASS_UID\s*\*\s*100')
            # severity_id can be set via lookup table or conditional
            if field == "severity_id":
                patterns.append(r'SEVERITY_MAP|severity_map|SEVERITY_LOOKUP')
                patterns.append(r'severity_id\b')
            found = any(re.search(p, code) for p in patterns)
            if not found:
                issues.append(self._issue(
                    "ocsf_required_fields", "error",
                    f"OCSF required field '{field}' not found in output assignments"
                ))
        return issues

    def _check_dangerous_functions(self, code: str, lines: List[str]) -> List[Dict]:
        issues = []
        dangerous = [
            (r'os\.execute', "os.execute() — system command execution"),
            (r'io\.popen', "io.popen() — process creation"),
            (r'loadstring\s*\(', "loadstring() — dynamic code loading"),
            (r'loadfile\s*\(', "loadfile() — file loading"),
            (r'dofile\s*\(', "dofile() — file execution"),
            (r"require\s*\(\s*['\"]os['\"]", "require('os') — OS module import"),
            (r"require\s*\(\s*['\"]io['\"]", "require('io') — IO module import"),
        ]
        for pattern, desc in dangerous:
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append(self._issue(
                        "dangerous_functions", "error", f"Dangerous: {desc}", i
                    ))
        return issues

    def _check_helper_dependencies(self, code: str) -> List[Dict]:
        """
        Ensure helper functions referenced by processEvent are resolvable.

        Catch two runtime-risk patterns:
        1) Helper call with no helper definition in script.
        2) local helper declared after processEvent (out of lexical scope).
        """
        issues: List[Dict] = []
        process_match = re.search(
            r'function\s+processEvent\s*\([^)]*\)(.*?)(?=\nfunction\s+\w|\nlocal\s+function\s+\w|\Z)',
            code,
            re.DOTALL,
        )
        if not process_match:
            return issues

        process_body = process_match.group(1)
        process_start = process_match.start()
        helper_candidates = ["getValue", "copyUnmappedFields", "no_nulls", "getSeverityId"]

        for helper in helper_candidates:
            used = bool(re.search(rf'\b{re.escape(helper)}\s*\(', process_body))
            if not used:
                continue

            any_def = re.search(
                rf'(^|\n)\s*(?:local\s+)?function\s+{re.escape(helper)}\s*\(',
                code,
            )
            if not any_def:
                issues.append(self._issue(
                    "helper_dependencies",
                    "error",
                    f"Helper '{helper}()' is used but not defined in the Lua script",
                ))
                continue

            local_def = re.search(
                rf'(^|\n)\s*local\s+function\s+{re.escape(helper)}\s*\(',
                code,
            )
            if local_def and local_def.start() > process_start:
                issues.append(self._issue(
                    "helper_dependencies",
                    "error",
                    f"Local helper '{helper}()' is declared after processEvent(); move it above processEvent or make it global",
                ))

        return issues

    def _check_unused_variables(self, code: str, lines: List[str]) -> List[Dict]:
        issues = []
        # Find local variable declarations
        for i, line in enumerate(lines, 1):
            match = re.match(r'\s*local\s+(\w+)\s*=', line)
            if match:
                var = match.group(1)
                # Count references (excluding the declaration line)
                other_lines = lines[:i-1] + lines[i:]
                refs = sum(1 for l in other_lines if re.search(rf'\b{re.escape(var)}\b', l))
                if refs == 0:
                    issues.append(self._issue(
                        "unused_variables", "info",
                        f"Variable '{var}' declared but never referenced", i
                    ))
        return issues

    def _check_line_length(self, lines: List[str]) -> List[Dict]:
        issues = []
        count = 0
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                count += 1
                if count <= 3:  # Report first 3
                    issues.append(self._issue(
                        "line_length", "info",
                        f"Line exceeds 120 characters ({len(line)} chars)", i
                    ))
        if count > 3:
            issues.append(self._issue(
                "line_length", "info",
                f"... and {count - 3} more lines exceeding 120 characters"
            ))
        return issues

    def _check_comment_density(self, lines: List[str]) -> List[Dict]:
        issues = []
        non_blank = [l for l in lines if l.strip()]
        if not non_blank:
            return issues
        comments = sum(1 for l in non_blank if l.strip().startswith("--"))
        density = comments / len(non_blank)
        if density < 0.05 and len(non_blank) > 20:
            issues.append(self._issue(
                "comment_density", "info",
                f"Low comment density ({density:.0%}) — consider adding documentation"
            ))
        return issues

    def _check_return_or_emit(self, code: str) -> List[Dict]:
        issues = []
        has_processEvent = bool(re.search(r'function\s+processEvent\s*\(', code))
        has_transform = bool(re.search(r'function\s+transform\s*\(', code))
        has_process = bool(re.search(r'function\s+process\s*\(', code))

        if has_processEvent:
            match = re.search(
                r'function\s+processEvent\s*\([^)]*\)(.*?)(?=\nfunction\s+\w|\Z)',
                code, re.DOTALL
            )
            if match and "return" not in match.group(1):
                issues.append(self._issue(
                    "return_or_emit", "error",
                    "processEvent() must include a 'return' statement (return event or return nil)"
                ))

        if has_transform:
            match = re.search(
                r'function\s+transform\s*\([^)]*\)(.*?)(?=\nfunction\s+\w|\Z)',
                code, re.DOTALL
            )
            if match and "return" not in match.group(1):
                issues.append(self._issue(
                    "return_or_emit", "error",
                    "transform() must include a 'return' statement"
                ))

        if has_process:
            match = re.search(
                r'function\s+process\s*\([^)]*\)(.*?)(?=\nfunction\s+\w|\Z)',
                code, re.DOTALL
            )
            if match and "emit(" not in match.group(1):
                issues.append(self._issue(
                    "return_or_emit", "error",
                    "process() must call 'emit()' to output events"
                ))

        return issues
