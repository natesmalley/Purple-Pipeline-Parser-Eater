"""Lua linter - best practice rules and quality scoring for Observo.ai Lua scripts."""

import logging
import re
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase 1.B: Hard-reject primitives
# ---------------------------------------------------------------------------
#
# These patterns are rejected BEFORE harness scoring — any script containing
# them is unsafe to emit against the real (unsandboxed) Observo lv3 Lua runtime
# which loads the full PUC Lua 5.4 stdlib via `unsafe_new_with + luaL_openlibs`.
#
# `lv3` context applies to the v3 `type: lua` transform scripts (the primary
# generation target). `scol` context applies to scriptable-collector sources
# and adds the ExecBulk/ExecParams/ExecFetchArg RCE surface because those
# Rust types cross the Lua boundary via mlua::IntoLua/FromLua and let a SCOL
# script hand Rust a subprocess-spawn table as a first-class framework feature.

# Patterns that are always rejected in the lv3 transform context.
# Each entry: (regex, human-readable description).
#
# Phase 1.E hardening (Findings #1, #2, #3 from the Phase 1 DA pass):
#   - #1: whitespace around the dot (`os . execute`, `os\t.\texecute`) — Lua
#     allows arbitrary whitespace between an identifier, `.`, and the field
#     name, so the regex must accept `\s*\.\s*` instead of a literal `\.`.
#   - #2: subscript notation (`os["execute"]`) is identical to dot access and
#     bypasses the dot-form regex entirely. Each dangerous dot primitive now
#     has a sibling subscript pattern.
#   - #3: `require("os").execute(...)` dynamically resolves the stdlib module
#     and sidesteps both forms above. We reject `require` of the dangerous
#     stdlib modules by name while leaving `require("json")` / `require("log")`
#     allowed (they're the blessed lv3 helpers).
#
# Finding #4 (runtime string concat, `os["ex" .. "ecute"](...)`) is documented
# as a residual risk: the local lupa sandbox nils the dangerous globals, which
# is the compensating control. We deliberately do NOT add a regex for it.
_LV3_HARD_REJECT_PATTERNS: List[tuple] = [
    # Dot-notation (whitespace-tolerant) — Finding #1
    (r'\bos\s*\.\s*execute\s*\(', "os.execute() — system command execution"),
    (r'\bos\s*\.\s*remove\s*\(', "os.remove() — filesystem mutation"),
    (r'\bos\s*\.\s*rename\s*\(', "os.rename() — filesystem mutation"),
    (r'\bio\s*\.\s*popen\s*\(', "io.popen() — subprocess spawn"),
    (r'\bio\s*\.\s*open\s*\(', "io.open() — raw filesystem access"),
    (r'\bpackage\s*\.\s*loadlib\s*\(', "package.loadlib() — native library load (RCE)"),
    (r'\bdebug\s*\.\s*sethook\s*\(', "debug.sethook() — debug hook installation"),
    (r'\bloadstring\s*\(', "loadstring() — dynamic code loading"),
    (r'\bdofile\s*\(', "dofile() — file execution"),
    (r'\bloadfile\s*\(', "loadfile() — file loading"),
    # Subscript-notation variants — Finding #2
    (r'\bos\s*\[\s*["\']execute["\']\s*\]', "os[\"execute\"] — system command execution via subscript"),
    (r'\bos\s*\[\s*["\']remove["\']\s*\]', "os[\"remove\"] — filesystem mutation via subscript"),
    (r'\bos\s*\[\s*["\']rename["\']\s*\]', "os[\"rename\"] — filesystem mutation via subscript"),
    (r'\bio\s*\[\s*["\']popen["\']\s*\]', "io[\"popen\"] — subprocess spawn via subscript"),
    (r'\bio\s*\[\s*["\']open["\']\s*\]', "io[\"open\"] — raw filesystem access via subscript"),
    (r'\bpackage\s*\[\s*["\']loadlib["\']\s*\]', "package[\"loadlib\"] — native library load via subscript"),
    (r'\bdebug\s*\[\s*["\']sethook["\']\s*\]', "debug[\"sethook\"] — debug hook via subscript"),
    # require() of dangerous stdlib modules — Finding #3
    # (require("json") / require("log") are blessed lv3 helpers and stay allowed.)
    (r'\brequire\s*\(\s*["\']os["\']\s*\)', "require(\"os\") — stdlib module load bypass"),
    (r'\brequire\s*\(\s*["\']io["\']\s*\)', "require(\"io\") — stdlib module load bypass"),
    (r'\brequire\s*\(\s*["\']package["\']\s*\)', "require(\"package\") — stdlib module load bypass"),
    (r'\brequire\s*\(\s*["\']debug["\']\s*\)', "require(\"debug\") — stdlib module load bypass"),
    # Phase 2.C: reject `class_uid = 0` — latent bug from netskope_lua.lua:1842.
    # Class 0 is not a valid OCSF class — see CLAUDE.md "OCSF classes actually
    # used by production Lua" section. Valid classes include 2001 (Security
    # Finding), 2004 (Detection Finding), 6001 (Web Resources Activity). For
    # unknown alert types, emitters must map to 2004 with activity_id=0
    # (Unknown) OR return nil from processEvent to drop the event.
    #
    # Dot form: `event.class_uid = 0` / `foo.bar.class_uid = 0` with trailing
    # non-digit boundary (so `= 00` or `= 0001` does not match — those are not
    # the specific latent bug). The required leading `\.` ensures this matches
    # only table-field assignments — Phase 2.F tightens this to exclude bare
    # variable declarations like `local class_uid = 0` and global assignments
    # like `class_uid = 0`, which are not OCSF event field writes.
    # `(?![\d.])` on the right rejects `0.5` and `01`.
    (r'\.\s*class_uid\s*=\s*0(?![\d.])',
     "class_uid = 0 is not a valid OCSF class — see CLAUDE.md OCSF classes section"),
    # Subscript form: `event["class_uid"] = 0` / `result['class_uid'] = 0`
    (r'\[\s*["\']class_uid["\']\s*\]\s*=\s*0(?![\d.])',
     "class_uid = 0 via subscript is not a valid OCSF class — see CLAUDE.md OCSF classes section"),
]

# scol context inherits everything above AND adds the SCOL exec RCE surface.
_SCOL_EXEC_PATTERNS: List[tuple] = [
    (r'\bExecBulk\b', "ExecBulk — SCOL subprocess-spawn table (RCE surface)"),
    (r'\bExecParams\b', "ExecParams — SCOL subprocess-spawn table (RCE surface)"),
    (r'\bExecFetchArg\b', "ExecFetchArg — SCOL subprocess-spawn table (RCE surface)"),
]


class LuaLintResult:
    """
    Result of `lint_script()`. Exposes `has_hard_reject` so callers can decide
    whether a script must be rejected outright (do not accept, do not score).

    `hard_reject_findings` is a list of `{pattern, description, line}` dicts.
    `findings` includes everything (informational + hard rejects) for logging.
    """

    __slots__ = ("has_hard_reject", "hard_reject_findings", "findings", "context")

    def __init__(
        self,
        has_hard_reject: bool,
        hard_reject_findings: List[Dict[str, Any]],
        findings: List[Dict[str, Any]],
        context: str,
    ) -> None:
        self.has_hard_reject = has_hard_reject
        self.hard_reject_findings = hard_reject_findings
        self.findings = findings
        self.context = context

    def rejection_reason(self) -> str:
        """Human-readable multi-line summary of why this script was rejected."""
        if not self.has_hard_reject:
            return ""
        lines = [
            f"Script rejected by security linter ({self.context} context):",
        ]
        for f in self.hard_reject_findings:
            line_info = f" (line {f['line']})" if f.get("line") else ""
            lines.append(f"  - {f['description']}{line_info}")
        lines.append(
            "These primitives are unsafe against the real Observo Lua runtime "
            "and must NOT appear anywhere in the generated script."
        )
        return "\n".join(lines)


def lint_script(
    source: str,
    context: str = "lv3",
    allow_exec: bool = False,
) -> LuaLintResult:
    """
    Run hard-reject security lint against a Lua script.

    Args:
        source: Lua source code to scan.
        context: "lv3" (v3 type:lua transform — default) or "scol" (scol source).
        allow_exec: scol-only opt-in for ExecBulk/ExecParams/ExecFetchArg tables.
                    Operator escape hatch; default False. Ignored for lv3.

    Returns:
        LuaLintResult with `has_hard_reject` and `hard_reject_findings`.
    """
    if context not in ("lv3", "scol"):
        raise ValueError(f"lint_script: context must be 'lv3' or 'scol', got {context!r}")

    patterns: List[tuple] = list(_LV3_HARD_REJECT_PATTERNS)
    if context == "scol" and not allow_exec:
        patterns.extend(_SCOL_EXEC_PATTERNS)

    hard_findings: List[Dict[str, Any]] = []
    lines = source.splitlines()
    for pattern, description in patterns:
        rx = re.compile(pattern)
        # First try line-level so we can report a line number.
        matched_any = False
        for i, line in enumerate(lines, 1):
            # Strip line comments to avoid false positives inside `-- os.execute("id")`.
            code_part = line.split("--", 1)[0] if "--" in line else line
            if rx.search(code_part):
                hard_findings.append({
                    "pattern": pattern,
                    "description": description,
                    "line": i,
                })
                matched_any = True
        if not matched_any:
            # Fallback whole-source scan (catches multi-line constructs, though rare).
            stripped = re.sub(r'--\[\[.*?\]\]', '', source, flags=re.DOTALL)
            stripped = re.sub(r'--[^\n]*', '', stripped)
            if rx.search(stripped):
                hard_findings.append({
                    "pattern": pattern,
                    "description": description,
                    "line": None,
                })

    return LuaLintResult(
        has_hard_reject=bool(hard_findings),
        hard_reject_findings=hard_findings,
        findings=list(hard_findings),
        context=context,
    )


class LuaLinter:
    """Checks Lua transformation scripts against best-practice rules."""

    RULES = [
        {"name": "observo_contract", "severity": "error", "weight": 10},
        {"name": "global_variables", "severity": "warning", "weight": 5},
        {"name": "string_concat_in_loop", "severity": "warning", "weight": 3},
        {"name": "unsafe_string_concat", "severity": "error", "weight": 10},
        {"name": "nil_safety", "severity": "error", "weight": 8},
        {"name": "table_in_loop", "severity": "info", "weight": 2},
        {"name": "ocsf_required_fields", "severity": "error", "weight": 10},
        {"name": "helper_dependencies", "severity": "error", "weight": 12},
        {"name": "dangerous_functions", "severity": "error", "weight": 15},
        {"name": "unguarded_time_date", "severity": "error", "weight": 10},
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

        issues.extend(self._check_observo_contract(lua_code))
        issues.extend(self._check_global_variables(lines))
        issues.extend(self._check_string_concat_in_loop(lua_code, lines))
        issues.extend(self._check_unsafe_string_concat(lines))
        issues.extend(self._check_nil_safety(lua_code))
        issues.extend(self._check_table_in_loop(lua_code, lines))
        issues.extend(self._check_ocsf_required_fields(lua_code))
        issues.extend(self._check_helper_dependencies(lua_code))
        issues.extend(self._check_dangerous_functions(lua_code, lines))
        issues.extend(self._check_unguarded_time_date(lines))
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

    def _check_observo_contract(self, code: str) -> List[Dict]:
        """
        Observo Lua Script docs contract:
        - Script entry point is processEvent(event)
        - Function/parameter names for this entry should remain unchanged
        """
        issues: List[Dict] = []
        from components.testing_harness.lua_signature import detect_entry_signature
        sig_info = detect_entry_signature(code)
        if sig_info.name != "processEvent":
            return issues

        # Validate first processEvent signature parameter exactly equals `event`
        param_text = sig_info.parameter or ""
        if param_text != "event":
            issues.append(self._issue(
                "observo_contract",
                "error",
                "Observo contract requires signature `processEvent(event)`; parameter name must be `event`",
            ))
        if re.search(r'\bevent\s*:\s*(get|set)\s*\(', code):
            issues.append(self._issue(
                "observo_contract",
                "error",
                "Observo runtime does not support event:get(...) or event:set(...); use table access",
            ))
        return issues

    def _check_unsafe_string_concat(self, lines: List[str]) -> List[Dict]:
        """
        Flag likely nil-unsafe concatenation patterns like:
          "prefix" .. uri
          uri .. "/path"
        where variable is not guarded via tostring(...) / explicit default.
        """
        issues: List[Dict] = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("--"):
                continue
            if ".." not in stripped:
                continue
            # Safe patterns:
            # - tostring(...)
            # - explicit fallback using `or` on same line
            if "tostring(" in stripped or re.search(r"\bor\b", stripped):
                continue
            # Likely unsafe: concatenating bare identifier(s)
            left_var = re.search(r"\b([a-zA-Z_]\w*)\s*\.\.", stripped)
            right_var = re.search(r"\.\.\s*([a-zA-Z_]\w*)\b", stripped)
            if left_var or right_var:
                issues.append(self._issue(
                    "unsafe_string_concat",
                    "error",
                    "Potential nil-unsafe string concatenation; wrap values with tostring(...) or default with `or`",
                    i,
                ))
        return issues

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
        from components.testing_harness.lua_signature import detect_entry_signature
        sig_info = detect_entry_signature(code)

        if sig_info.name is not None:
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

        # Check setNestedField for missing obj nil guard
        set_match = re.search(
            r'function\s+setNestedField\s*\([^)]*\)\s*\n((?:.*\n){0,3})',
            code,
        )
        if set_match:
            guard_lines = set_match.group(1)
            if 'obj == nil' not in guard_lines and 'obj==nil' not in guard_lines:
                issues.append(self._issue(
                    "nil_safety", "error",
                    "setNestedField missing nil guard on obj parameter — will crash on nil input"
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
                # setNestedField(result, "field", value) — canonical helper pattern
                rf'setNestedField\s*\([^,]+,\s*["\'](?:[^"\']*\.)?{field}["\']',
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
            (r"require\s*\(", "require(...) — external module import not supported in Observo sandbox"),
        ]
        for pattern, desc in dangerous:
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append(self._issue(
                        "dangerous_functions", "error", f"Dangerous: {desc}", i
                    ))
        return issues

    def _check_unguarded_time_date(self, lines: List[str]) -> List[Dict]:
        """
        Flag os.time/os.date calls that are not guarded via pcall.
        Observo runtime has platform-specific failures around these calls.
        """
        issues: List[Dict] = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("--"):
                continue
            has_time_or_date = bool(re.search(r'\bos\.(time|date)\s*\(', stripped))
            if not has_time_or_date:
                continue
            if "pcall(" in stripped:
                continue
            nearby = "\n".join(lines[max(0, i - 3): min(len(lines), i + 2)])
            if "pcall(" in nearby:
                continue
            issues.append(self._issue(
                "unguarded_time_date",
                "error",
                "Guard os.time/os.date with pcall and safe fallback to avoid Observo runtime crashes",
                i,
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
        helper_candidates = [
            "getValue",
            "copyUnmappedFields",
            "no_nulls",
            "getSeverityId",
            "getNestedField",
            "setNestedField",
            "flattenObject",
        ]

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
        from components.testing_harness.lua_signature import has_signature
        has_processEvent = has_signature(code, "processEvent")
        has_transform = has_signature(code, "transform")
        has_process = has_signature(code, "process")

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
