#!/usr/bin/env python3
"""
Phase 5.3: Python Syntax & Import Validation Test Suite

Tests all Python files for:
1. Syntax errors (compilation)
2. Import resolution
3. Module loading
4. Circular dependencies

Usage:
    python tests/test_syntax_validation.py
"""

import os
import sys
import py_compile
import importlib
import traceback
from pathlib import Path
from typing import List, Tuple, Dict

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

class Colors:
    """Terminal colors for output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def find_all_python_files() -> List[Path]:
    """Find all Python files in the project"""
    python_files = []

    # Directories to scan
    directories = [
        PROJECT_ROOT / "components",
        PROJECT_ROOT / "utils",
        PROJECT_ROOT / "tests",
        PROJECT_ROOT
    ]

    for directory in directories:
        if directory.exists():
            for file in directory.rglob("*.py"):
                # Skip __pycache__ and .venv
                if "__pycache__" not in str(file) and ".venv" not in str(file):
                    python_files.append(file)

    return sorted(python_files)

def check_syntax(file_path: Path) -> Tuple[bool, str]:
    """
    Check if Python file has valid syntax.

    Renamed from test_syntax so pytest does not mis-collect this helper
    as a test function. The file is a standalone validation script
    (`python tests/test_syntax_validation.py`), not a pytest suite.
    Batch 1 fix: resolved the `fixture 'file_path' not found` collection
    errors at tests/test_syntax_validation.py:test_syntax/test_import.

    Args:
        file_path: Path to Python file

    Returns:
        Tuple of (success, error_message)
    """
    try:
        py_compile.compile(str(file_path), doraise=True)
        return (True, "")
    except py_compile.PyCompileError as e:
        return (False, str(e))
    except Exception as e:
        return (False, f"Unexpected error: {str(e)}")

def check_import(file_path: Path) -> Tuple[bool, str]:
    """
    Check if Python module can be imported.

    Renamed from test_import so pytest does not mis-collect this helper.
    See the docstring on check_syntax for rationale.

    Args:
        file_path: Path to Python file

    Returns:
        Tuple of (success, error_message)
    """
    # Skip test files and scripts that require specific setup
    skip_import_test = [
        "test_",  # Test files
        "populate_",  # Population scripts
        "ingest_",  # Ingestion scripts
        "start_",  # Startup scripts
        "main.py",  # Entry point (requires full setup)
        "continuous_conversion_service.py",  # Service (requires full setup)
        "fix_imports.py",  # Utility script
    ]

    file_name = file_path.name
    if any(skip in file_name for skip in skip_import_test):
        return (True, "Skipped (script/test file)")

    # Convert file path to module name
    try:
        relative_path = file_path.relative_to(PROJECT_ROOT)
        module_name = str(relative_path.with_suffix('')).replace(os.sep, '.')

        # Skip __init__ files
        if module_name.endswith('.__init__'):
            module_name = module_name[:-9]

        # Try to import the module
        importlib.import_module(module_name)
        return (True, "")

    except ImportError as e:
        # Check if it's a missing optional dependency
        optional_deps = ['torch', 'sentence_transformers', 'pymilvus', 'lupa', 'flask_limiter']
        error_str = str(e).lower()
        if any(dep in error_str for dep in optional_deps):
            return (True, f"Optional dependency missing: {e}")
        return (False, f"Import error: {e}")

    except Exception as e:
        return (False, f"Unexpected error: {e}")

def check_critical_imports() -> Dict[str, Tuple[bool, str]]:
    """
    Check if critical project imports work

    Returns:
        Dictionary of {module: (success, message)}
    """
    critical_modules = {
        "utils.logger": "Logger utility",
        "utils.error_handler": "Error handler utility",
        "components.github_scanner": "GitHub scanner component",
        "components.observo_client": "Observo client component",
        "components.pipeline_validator": "Pipeline validator component",
        "components.web_feedback_ui": "Web feedback UI component",
        "orchestrator": "Main orchestrator",
    }

    results = {}
    for module_name, description in critical_modules.items():
        try:
            importlib.import_module(module_name)
            results[module_name] = (True, f"{description} - OK")
        except ImportError as e:
            # Check for optional dependencies
            optional_deps = ['torch', 'sentence_transformers', 'pymilvus', 'lupa', 'flask_limiter']
            error_str = str(e).lower()
            if any(dep in error_str for dep in optional_deps):
                results[module_name] = (True, f"{description} - Optional dependency missing")
            else:
                results[module_name] = (False, f"{description} - Import failed: {e}")
        except Exception as e:
            results[module_name] = (False, f"{description} - Error: {e}")

    return results

def run_validation() -> bool:
    """
    Run complete validation suite

    Returns:
        True if all tests pass, False otherwise
    """
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}Phase 5.3: Python Syntax & Import Validation{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.ENDC}\n")

    # Find all Python files
    print(f"{Colors.BOLD}Finding Python files...{Colors.ENDC}")
    python_files = find_all_python_files()
    print(f"Found {len(python_files)} Python files\n")

    # Test syntax
    print(f"{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.BOLD}Test 1: Syntax Validation (py_compile){Colors.ENDC}")
    print(f"{Colors.BOLD}{'='*80}{Colors.ENDC}\n")

    syntax_results = []
    for file_path in python_files:
        success, error = check_syntax(file_path)
        syntax_results.append((file_path, success, error))

        relative_path = file_path.relative_to(PROJECT_ROOT)
        if success:
            print(f"{Colors.GREEN}[OK]{Colors.ENDC} {relative_path}")
        else:
            print(f"{Colors.RED}[FAIL]{Colors.ENDC} {relative_path}")
            print(f"  {Colors.RED}Error: {error}{Colors.ENDC}")

    syntax_pass = sum(1 for _, success, _ in syntax_results if success)
    syntax_fail = len(syntax_results) - syntax_pass

    print(f"\n{Colors.BOLD}Syntax Test Results:{Colors.ENDC}")
    print(f"  {Colors.GREEN}Passed: {syntax_pass}/{len(syntax_results)}{Colors.ENDC}")
    if syntax_fail > 0:
        print(f"  {Colors.RED}Failed: {syntax_fail}/{len(syntax_results)}{Colors.ENDC}")

    # Test imports
    print(f"\n{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.BOLD}Test 2: Import Resolution{Colors.ENDC}")
    print(f"{Colors.BOLD}{'='*80}{Colors.ENDC}\n")

    import_results = []
    for file_path in python_files:
        success, error = check_import(file_path)
        import_results.append((file_path, success, error))

        relative_path = file_path.relative_to(PROJECT_ROOT)
        if success:
            if "Skipped" in error:
                print(f"{Colors.YELLOW}[SKIP]{Colors.ENDC} {relative_path} - {error}")
            elif "Optional" in error:
                print(f"{Colors.YELLOW}[WARN]{Colors.ENDC} {relative_path} - {error}")
            else:
                print(f"{Colors.GREEN}[OK]{Colors.ENDC} {relative_path}")
        else:
            print(f"{Colors.RED}[FAIL]{Colors.ENDC} {relative_path}")
            print(f"  {Colors.RED}Error: {error}{Colors.ENDC}")

    import_pass = sum(1 for _, success, _ in import_results if success)
    import_fail = len(import_results) - import_pass

    print(f"\n{Colors.BOLD}Import Test Results:{Colors.ENDC}")
    print(f"  {Colors.GREEN}Passed: {import_pass}/{len(import_results)}{Colors.ENDC}")
    if import_fail > 0:
        print(f"  {Colors.RED}Failed: {import_fail}/{len(import_results)}{Colors.ENDC}")

    # Test critical imports
    print(f"\n{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.BOLD}Test 3: Critical Module Imports{Colors.ENDC}")
    print(f"{Colors.BOLD}{'='*80}{Colors.ENDC}\n")

    critical_results = check_critical_imports()
    critical_pass = 0
    critical_fail = 0

    for module_name, (success, message) in critical_results.items():
        if success:
            print(f"{Colors.GREEN}[OK]{Colors.ENDC} {module_name}")
            print(f"  {message}")
            critical_pass += 1
        else:
            print(f"{Colors.RED}[FAIL]{Colors.ENDC} {module_name}")
            print(f"  {Colors.RED}{message}{Colors.ENDC}")
            critical_fail += 1

    print(f"\n{Colors.BOLD}Critical Import Results:{Colors.ENDC}")
    print(f"  {Colors.GREEN}Passed: {critical_pass}/{len(critical_results)}{Colors.ENDC}")
    if critical_fail > 0:
        print(f"  {Colors.RED}Failed: {critical_fail}/{len(critical_results)}{Colors.ENDC}")

    # Final summary
    print(f"\n{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.BOLD}FINAL SUMMARY{Colors.ENDC}")
    print(f"{Colors.BOLD}{'='*80}{Colors.ENDC}\n")

    all_pass = (syntax_fail == 0 and import_fail == 0 and critical_fail == 0)

    print(f"Total Python Files: {len(python_files)}")
    print(f"Syntax Validation: {Colors.GREEN if syntax_fail == 0 else Colors.RED}{syntax_pass}/{len(syntax_results)} passed{Colors.ENDC}")
    print(f"Import Resolution: {Colors.GREEN if import_fail == 0 else Colors.RED}{import_pass}/{len(import_results)} passed{Colors.ENDC}")
    print(f"Critical Modules: {Colors.GREEN if critical_fail == 0 else Colors.RED}{critical_pass}/{len(critical_results)} passed{Colors.ENDC}")

    print(f"\n{Colors.BOLD}Overall Status: {Colors.GREEN if all_pass else Colors.RED}{'PASS [OK]' if all_pass else 'FAIL [X]'}{Colors.ENDC}\n")

    return all_pass

# -----------------------------------------------------------------------
# Pytest wrappers. The helper functions above are named `check_*` so they
# are NOT collected by pytest; the two wrappers below are the real tests.
# -----------------------------------------------------------------------


def test_all_python_files_syntactically_valid():
    """Every Python file under the project parses cleanly via py_compile."""
    failures = []
    for file_path in find_all_python_files():
        ok, err = check_syntax(file_path)
        if not ok:
            failures.append((str(file_path.relative_to(PROJECT_ROOT)), err))
    assert not failures, (
        f"Syntax errors in {len(failures)} file(s): "
        + ", ".join(f"{p} ({e[:80]})" for p, e in failures[:5])
    )


def test_critical_imports_resolve():
    """The plan-blessed critical modules must import (or fail only due to
    optional-dependency absence, which the helper already tolerates)."""
    results = check_critical_imports()
    failures = [
        (name, msg) for name, (ok, msg) in results.items() if not ok
    ]
    assert not failures, (
        "Critical module imports failed: "
        + ", ".join(f"{n}: {m}" for n, m in failures)
    )


if __name__ == "__main__":
    try:
        success = run_validation()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Validation interrupted by user{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error during validation:{Colors.ENDC}")
        print(f"{Colors.RED}{traceback.format_exc()}{Colors.ENDC}")
        sys.exit(1)
