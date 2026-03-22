"""Lua validity checker - structural and syntax validation."""

import logging
import re
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

try:
    import lupa
    LUPA_AVAILABLE = True
except ImportError:
    LUPA_AVAILABLE = False
    logger.warning("lupa not available - validity checking will use regex fallback")


class LuaValidityChecker:
    """Validates Lua code for structural correctness and syntax."""

    def check(self, lua_code: str) -> Dict[str, Any]:
        """
        Check Lua code validity.

        Returns:
            {"valid": bool, "errors": [], "warnings": [], "function_signature": str,
             "line_count": int, "method": str}
        """
        errors: List[str] = []
        warnings: List[str] = []
        lines = lua_code.strip().splitlines()
        line_count = len(lines)

        # Detect function signature
        has_processEvent = bool(re.search(r'function\s+processEvent\s*\(', lua_code))
        has_transform = bool(re.search(r'function\s+transform\s*\(', lua_code))
        has_process = bool(re.search(r'function\s+process\s*\(', lua_code))

        sig_count = sum([has_processEvent, has_transform, has_process])
        if sig_count > 1:
            signature = "processEvent" if has_processEvent else "both"
            warnings.append("Code defines multiple entry functions — only one entry point expected")
        elif has_processEvent:
            signature = "processEvent"
        elif has_transform:
            signature = "transform"
        elif has_process:
            signature = "process"
        else:
            signature = "unknown"
            errors.append("No entry function found (expected 'function processEvent(event)', 'function transform(event)', or 'function process(event, emit)')")

        # Structural checks
        structural_errors = self._check_structure(lua_code, signature)
        errors.extend(structural_errors)

        # Balanced block keywords
        balance_errors = self._check_balance(lua_code)
        errors.extend(balance_errors)

        # Syntax check via lupa
        if LUPA_AVAILABLE and not errors:
            syntax_result = self._check_syntax_lupa(lua_code)
            errors.extend(syntax_result.get("errors", []))
            method = "lupa"
        else:
            method = "regex"

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "function_signature": signature,
            "line_count": line_count,
            "method": method,
        }

    def _check_structure(self, lua_code: str, signature: str) -> List[str]:
        errors = []

        # Check return/emit based on signature
        if signature == "processEvent":
            match = re.search(
                r'function\s+processEvent\s*\([^)]*\)(.*?)(?=\nfunction\s+\w|\Z)',
                lua_code, re.DOTALL
            )
            if match and "return" not in match.group(1):
                errors.append("processEvent() function missing 'return' statement")

        elif signature == "transform":
            match = re.search(
                r'function\s+transform\s*\([^)]*\)(.*?)(?=\nfunction\s+\w|\Z)',
                lua_code, re.DOTALL
            )
            if match and "return" not in match.group(1):
                errors.append("transform() function missing 'return' statement")

        elif signature == "process":
            match = re.search(
                r'function\s+process\s*\([^)]*\)(.*?)(?=\nfunction\s+\w|\Z)',
                lua_code, re.DOTALL
            )
            if match and "emit(" not in match.group(1) and "emit (" not in match.group(1):
                errors.append("process() function missing 'emit()' call")

        # Check balanced brackets (on stripped code to ignore comments/strings)
        stripped = self._strip_comments_and_strings(lua_code)
        if stripped.count("{") != stripped.count("}"):
            errors.append(f"Unbalanced curly braces: {stripped.count('{')} open vs {stripped.count('}')} close")
        if stripped.count("(") != stripped.count(")"):
            errors.append(f"Unbalanced parentheses: {stripped.count('(')} open vs {stripped.count(')')} close")

        return errors

    def _check_balance(self, lua_code: str) -> List[str]:
        """Check that block-opening keywords match 'end' keywords."""
        errors = []

        # Strip comments and strings for accurate counting
        stripped = self._strip_comments_and_strings(lua_code)

        openers = len(re.findall(r'\b(function|if|for|while|repeat)\b', stripped))
        # 'repeat' closes with 'until', not 'end'
        repeats = len(re.findall(r'\brepeat\b', stripped))
        untils = len(re.findall(r'\buntil\b', stripped))
        ends = len(re.findall(r'\bend\b', stripped))

        expected_ends = openers - repeats
        if expected_ends != ends:
            errors.append(
                f"Block keyword mismatch: {expected_ends} expected 'end' keywords but found {ends}"
            )
        if repeats != untils:
            errors.append(
                f"repeat/until mismatch: {repeats} 'repeat' but {untils} 'until'"
            )

        return errors

    def _strip_comments_and_strings(self, lua_code: str) -> str:
        """Remove Lua comments and string literals for keyword counting."""
        # Remove multi-line comments --[[ ... ]]
        result = re.sub(r'--\[\[.*?\]\]', '', lua_code, flags=re.DOTALL)
        # Remove single-line comments
        result = re.sub(r'--[^\n]*', '', result)
        # Remove multi-line strings [[ ... ]]
        result = re.sub(r'\[\[.*?\]\]', '""', result, flags=re.DOTALL)
        # Remove double-quoted strings
        result = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', result)
        # Remove single-quoted strings
        result = re.sub(r"'[^'\\]*(?:\\.[^'\\]*)*'", "''", result)
        return result

    def _check_syntax_lupa(self, lua_code: str) -> Dict[str, Any]:
        """Use lupa to validate Lua syntax."""
        errors = []
        try:
            lua = lupa.LuaRuntime(
                unpack_returned_tuples=True,
                register_eval=False,
                register_builtins=False,
            )
            lua.execute(lua_code)
        except lupa.LuaSyntaxError as e:
            errors.append(f"Lua syntax error: {e}")
        except Exception as e:
            errors.append(f"Lua validation error: {e}")
        return {"errors": errors}
