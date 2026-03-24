# Agent 1: Critical Security Fixes - Complete Prompt
**Claude Haiku Agent Assignment**

**Your Mission:** Fix 4 CRITICAL security vulnerabilities that pose immediate risks to the application.

---

## 🎯 CONTEXT & OVERVIEW

You are working on **Purple Pipeline Parser Eater v9.0.0**, an enterprise-grade AI system that converts SentinelOne parsers to Observo.ai pipelines. The system uses:
- Python 3.11+
- Flask for web UI
- Docker for containerization
- Kubernetes for orchestration
- Lua code validation and execution
- Subprocess calls to external binaries

**Project Structure:**
```
purple-pipeline-parser-eater/
├── components/
│   ├── dataplane_validator.py      # ← YOU WILL FIX THIS
│   ├── transform_executor.py       # ← YOU WILL FIX THIS
│   ├── pipeline_validator.py       # ← YOU WILL FIX THIS
│   └── web_feedback_ui.py
├── docker-compose.yml               # ← YOU WILL FIX THIS
├── Dockerfile
├── tests/
│   └── test_dataplane_validator.py # ← YOU WILL CREATE/UPDATE THIS
└── requirements.txt
```

**Your Working Directory:** `C:\Users\hexideciml\Documents\GitHub\Purple-Pipline-Parser-Eater`

---

## 🔴 YOUR TASKS (4 CRITICAL ISSUES)

### **TASK 1: Fix Path Injection Risk in Lua dofile() Call**

**File:** `components/dataplane_validator.py`  
**Lines:** 84-117 (specifically line 102)  
**Priority:** 🔴 CRITICAL  
**Estimated Time:** 2 hours

**Current Code (PROBLEMATIC):**
```python
def _render_config(self, lua_file: Path) -> str:
    lua_path = lua_file.as_posix()
    return f"""
api:
  enabled: false

sources:
  stdin_input:
    type: stdin
    decoding:
      codec: json

transforms:
  lua_transform:
    inputs: ["stdin_input"]
    type: lua
    version: "3"
    source: |
      dofile('{lua_path}')  # ← SECURITY ISSUE: Path not escaped
      function process(event, emit)
        local out = processEvent(event["log"])
        if out ~= nil then
          event["log"] = out
          emit(event)
        end
      end

sinks:
  console_output:
    type: console
    inputs: ["lua_transform"]
    encoding:
      codec: json
"""
```

**The Problem:**
1. The `lua_path` is inserted directly into Lua code via f-string
2. If the path contains special Lua characters (single quotes `'`, backslashes `\`), it could break out of the string context
3. Example attack: If path is `/tmp/test'/); os.execute('rm -rf /'); --`, it could inject malicious code
4. While `tempfile.TemporaryDirectory()` provides some security, we must still escape the path

**What You Must Do:**

1. **Add path validation** to ensure the path is within the temp directory
2. **Escape special characters** for Lua string context (quotes, backslashes)
3. **Add comprehensive tests** to verify the fix works

**Implementation Steps:**

**Step 1:** Update `_render_config` method in `components/dataplane_validator.py`:

```python
import tempfile
from pathlib import Path
from typing import Dict, List, Any

def _render_config(self, lua_file: Path) -> str:
    """
    Render dataplane configuration with Lua transform.
    
    SECURITY: Validates path is within temp directory and escapes special characters.
    
    Args:
        lua_file: Path to Lua transform file (must be within temp directory)
        
    Returns:
        YAML configuration string for dataplane
        
    Raises:
        SecurityError: If path is outside temp directory or contains dangerous patterns
    """
    # SECURITY FIX: Validate path is within temp directory
    lua_path_abs = lua_file.resolve()  # Get absolute path
    
    # Get the temp directory base (where TemporaryDirectory creates subdirs)
    # Since we're called from within a TemporaryDirectory context, get its parent
    import os
    temp_base = Path(tempfile.gettempdir())
    
    # Ensure path is within temp directory (prevent path traversal)
    # Check if resolved path starts with temp directory
    try:
        lua_path_abs.relative_to(temp_base)
    except ValueError:
        # Path is outside temp directory - security violation
        raise SecurityError(
            f"Invalid lua_file path - potential path traversal detected. "
            f"Path: {lua_path_abs}, Temp base: {temp_base}"
        )
    
    # SECURITY FIX: Escape special characters for Lua string context
    # Lua uses single quotes for strings, so we need to escape:
    # - Single quotes: ' becomes \'
    # - Backslashes: \ becomes \\
    lua_path_str = lua_file.as_posix()  # Use forward slashes (works on Windows too)
    
    # Escape backslashes first (order matters!)
    lua_path_str = lua_path_str.replace("\\", "\\\\")
    # Then escape single quotes
    lua_path_str = lua_path_str.replace("'", "\\'")
    
    # Additional security: Validate no dangerous patterns
    dangerous_patterns = ['..', '${', '`', '$(']
    for pattern in dangerous_patterns:
        if pattern in lua_path_str:
            raise SecurityError(
                f"Dangerous pattern detected in path: {pattern}. "
                f"This could indicate an injection attempt."
            )
    
    return f"""
api:
  enabled: false

sources:
  stdin_input:
    type: stdin
    decoding:
      codec: json

transforms:
  lua_transform:
    inputs: ["stdin_input"]
    type: lua
    version: "3"
    source: |
      dofile('{lua_path_str}')
      function process(event, emit)
        local out = processEvent(event["log"])
        if out ~= nil then
          event["log"] = out
          emit(event)
        end
      end

sinks:
  console_output:
    type: console
    inputs: ["lua_transform"]
    encoding:
      codec: json
"""
```

**Step 2:** Add SecurityError exception class at the top of the file:

```python
class SecurityError(Exception):
    """Security-related error (path traversal, injection attempt, etc.)"""
    pass
```

**Step 3:** Update imports at the top:

```python
import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple
```

**Step 4:** Create comprehensive tests in `tests/test_dataplane_validator.py`:

```python
import pytest
import tempfile
from pathlib import Path
from components.dataplane_validator import DataplaneValidator, SecurityError

class TestDataplaneValidatorSecurity:
    """Security tests for DataplaneValidator"""
    
    def test_path_traversal_prevention(self):
        """Test that path traversal attempts are blocked"""
        validator = DataplaneValidator(
            binary_path="/fake/path",
            ocsf_required_fields=["class_uid"],
            timeout=30
        )
        
        # Try to use a path outside temp directory
        malicious_path = Path("/etc/passwd")
        
        with pytest.raises(SecurityError, match="path traversal"):
            validator._render_config(malicious_path)
    
    def test_path_escaping_single_quotes(self):
        """Test that single quotes in path are escaped"""
        validator = DataplaneValidator(
            binary_path="/fake/path",
            ocsf_required_fields=["class_uid"],
            timeout=30
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create path with single quote
            test_file = Path(tmpdir) / "test'file.lua"
            test_file.write_text("-- test")
            
            config = validator._render_config(test_file)
            
            # Verify single quote is escaped
            assert "test\\'file" in config or "test\\\\'file" in config
            # Verify dofile() call is valid Lua syntax
            assert "dofile(" in config
    
    def test_path_escaping_backslashes(self):
        """Test that backslashes in path are escaped"""
        validator = DataplaneValidator(
            binary_path="/fake/path",
            ocsf_required_fields=["class_uid"],
            timeout=30
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create path (Windows-style with backslashes)
            test_file = Path(tmpdir) / "test\\file.lua"
            test_file.write_text("-- test")
            
            config = validator._render_config(test_file)
            
            # Verify backslashes are escaped (doubled)
            # Path should be converted to forward slashes by as_posix()
            # But if backslashes remain, they should be escaped
            assert "\\\\" not in config or config.count("\\") == 0  # Either escaped or converted
    
    def test_dangerous_patterns_blocked(self):
        """Test that dangerous patterns are detected"""
        validator = DataplaneValidator(
            binary_path="/fake/path",
            ocsf_required_fields=["class_uid"],
            timeout=30
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Try path with .. pattern
            test_file = Path(tmpdir) / "test../file.lua"
            test_file.write_text("-- test")
            
            with pytest.raises(SecurityError, match="Dangerous pattern"):
                validator._render_config(test_file)
    
    def test_valid_path_works(self):
        """Test that valid paths work correctly"""
        validator = DataplaneValidator(
            binary_path="/fake/path",
            ocsf_required_fields=["class_uid"],
            timeout=30
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "transform.lua"
            test_file.write_text("-- valid lua code")
            
            config = validator._render_config(test_file)
            
            # Verify config is generated
            assert "dofile(" in config
            assert "lua_transform" in config
            assert "transform.lua" in config or str(test_file.name) in config
```

**Verification Checklist:**
- [ ] Path validation prevents traversal outside temp directory
- [ ] Single quotes are escaped in Lua string
- [ ] Backslashes are escaped in Lua string
- [ ] Dangerous patterns are detected and blocked
- [ ] All tests pass
- [ ] No regressions in existing functionality

---

### **TASK 2: Fix File Handle Leaks in Subprocess Calls**

**Files:** 
- `components/dataplane_validator.py` (line 51)
- `components/transform_executor.py` (line 81)

**Priority:** 🔴 CRITICAL  
**Estimated Time:** 1 hour

**Current Code (PROBLEMATIC):**

**File 1:** `components/dataplane_validator.py:48-58`
```python
try:
    process = subprocess.run(  # nosec B603
        [str(self.binary_path), "--config", str(config_file)],
        stdin=open(events_file, "rb"),  # ← PROBLEM: File not properly closed
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=self.timeout,
    )
finally:
    events_file.close()  # ← PROBLEM: events_file is Path object, not file handle
```

**File 2:** `components/transform_executor.py:78-88`
```python
try:
    result = subprocess.run(  # nosec B603
        [str(self._binary_path), "--config", str(config_file)],
        stdin=open(event_file, "rb"),  # ← PROBLEM: Same issue
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=10,
    )
finally:
    event_file.close()  # ← PROBLEM: Same issue
```

**The Problem:**
1. `open()` creates a file handle that must be closed
2. If subprocess fails or raises exception, file handle may not be closed
3. `events_file.close()` is called on a `Path` object, not a file handle (does nothing)
4. Multiple concurrent validations could exhaust file descriptors

**What You Must Do:**

Fix both files to use proper context managers for file handling.

**Implementation Steps:**

**Step 1:** Fix `components/dataplane_validator.py`:

```python
def validate(self, lua_code: str, events: List[Dict[str, Any]], parser_id: str) -> DataplaneValidationResult:
    with tempfile.TemporaryDirectory(prefix=f"pppe-validate-{parser_id}-") as tmpdir:
        tmp_path = Path(tmpdir)
        lua_file = tmp_path / "transform.lua"
        lua_file.write_text(lua_code, encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        config_file.write_text(self._render_config(lua_file), encoding="utf-8")

        events_file = tmp_path / "events.jsonl"
        events_file.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")

        # SECURITY FIX: Use context manager to ensure file is closed
        try:
            with open(events_file, "rb") as stdin_file:
                process = subprocess.run(
                    [str(self.binary_path), "--config", str(config_file)],
                    stdin=stdin_file,  # File handle automatically closed after subprocess
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=self.timeout,
                )
        except subprocess.TimeoutExpired:
            logger.error("Dataplane validation timed out for %s", parser_id)
            return DataplaneValidationResult(
                success=False,
                output_events=[],
                stderr="Validation timeout",
                ocsf_missing_fields=[],
                error="timeout",
            )
        except Exception as e:
            logger.error("Dataplane validation error for %s: %s", parser_id, e)
            return DataplaneValidationResult(
                success=False,
                output_events=[],
                stderr=str(e),
                ocsf_missing_fields=[],
                error="subprocess_error",
            )

    stdout = process.stdout.decode("utf-8", "ignore")
    stderr = process.stderr.decode("utf-8", "ignore")
    # ... rest of method unchanged
```

**Step 2:** Fix `components/transform_executor.py`:

```python
def execute_dataplane(self, event: Dict[str, Any], lua_code: str) -> Tuple[bool, Dict[str, Any]]:
    """Execute transformation using dataplane binary in subprocess."""
    with tempfile.TemporaryDirectory(prefix=f"pppe-exec-{id(event)}-") as tmpdir:
        tmp_path = Path(tmpdir)
        lua_file = tmp_path / "transform.lua"
        lua_file.write_text(lua_code, encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        config_file.write_text(self._render_config(lua_file), encoding="utf-8")

        event_file = tmp_path / "event.json"
        event_file.write_text(json.dumps(event), encoding="utf-8")

        # SECURITY FIX: Use context manager to ensure file is closed
        try:
            with open(event_file, "rb") as stdin_file:
                result = subprocess.run(
                    [str(self._binary_path), "--config", str(config_file)],
                    stdin=stdin_file,  # File handle automatically closed
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=10,
                )
        except subprocess.TimeoutExpired:
            logger.error("Dataplane execution timed out")
            return False, {"error": "timeout"}
        except Exception as e:
            logger.error("Dataplane execution error: %s", e)
            return False, {"error": str(e)}

        if result.returncode != 0:
            logger.error("Dataplane executor failed: %s", result.stderr.decode("utf-8", "ignore"))
            return False, {"error": result.stderr.decode("utf-8", "ignore")}

        try:
            output = json.loads(result.stdout.decode("utf-8"))
        except json.JSONDecodeError as exc:
            logger.error("Failed to decode dataplane output: %s", exc)
            return False, {"error": "invalid_output"}
        
        # ... rest of method unchanged
```

**Step 3:** Add tests for file handle cleanup:

```python
# In tests/test_dataplane_validator.py
import resource
import os

class TestFileHandleManagement:
    """Test file handle management and resource cleanup"""
    
    def test_no_file_handle_leaks(self):
        """Test that file handles are properly closed"""
        # Get initial file descriptor count
        initial_fds = len(os.listdir('/proc/self/fd')) if os.path.exists('/proc/self/fd') else None
        
        validator = DataplaneValidator(
            binary_path="/bin/echo",  # Use simple binary for test
            ocsf_required_fields=["class_uid"],
            timeout=5
        )
        
        # Run multiple validations
        for i in range(10):
            validator.validate(
                lua_code="-- test",
                events=[{"test": "data"}],
                parser_id=f"test_{i}"
            )
        
        # Check file descriptor count hasn't increased significantly
        if initial_fds:
            final_fds = len(os.listdir('/proc/self/fd'))
            # Allow small increase (2-3 FDs) but not 10+
            assert final_fds - initial_fds < 5, "File handle leak detected"
    
    def test_file_closed_on_exception(self):
        """Test that file is closed even if subprocess raises exception"""
        validator = DataplaneValidator(
            binary_path="/nonexistent/binary",  # Will fail
            ocsf_required_fields=["class_uid"],
            timeout=5
        )
        
        # Should not raise exception about unclosed file
        result = validator.validate(
            lua_code="-- test",
            events=[{"test": "data"}],
            parser_id="test"
        )
        
        assert not result.success
        assert result.error is not None
```

**Verification Checklist:**
- [ ] File handles are closed using context managers
- [ ] Exception handling doesn't leak file handles
- [ ] Tests verify no file descriptor leaks
- [ ] Both files fixed consistently
- [ ] No regressions in functionality

---

### **TASK 3: Add Lua Code Validation for Dangerous Patterns**

**File:** `components/pipeline_validator.py`  
**Lines:** 260-297  
**Priority:** 🔴 CRITICAL  
**Estimated Time:** 3 hours

**Current Code (PROBLEMATIC):**

```python
def _validate_lua_syntax_with_lupa(self, lua_code: str) -> Dict[str, Any]:
    """Validate LUA syntax using lupa sandbox"""
    errors = []
    warnings = []
    
    # ... existing code ...
    
    try:
        # Create LUA runtime
        lua = lupa.LuaRuntime(unpack_returned_tuples=True)

        # SECURITY FIX: Phase 4 - Avoid f-string for code injection
        validation_wrapper = "function temp_validate() " + lua_code + " end"
        lua.execute(validation_wrapper)  # ← PROBLEM: No validation before execution
        
        # ... rest of method
```

**The Problem:**
1. Lua code is executed without checking for dangerous patterns
2. Even with sandboxing, certain patterns could be dangerous
3. No validation for `os.execute`, `io.popen`, `require('os')`, etc.
4. Sandbox might be misconfigured or bypassed

**What You Must Do:**

Add pattern-based validation before executing Lua code.

**Implementation Steps:**

**Step 1:** Add validation method to `components/pipeline_validator.py`:

```python
import re
import logging

logger = logging.getLogger(__name__)

class PipelineValidator:
    # ... existing code ...
    
    def _validate_lua_code_safety(self, lua_code: str) -> Tuple[bool, List[str]]:
        """
        Validate Lua code doesn't contain dangerous patterns.
        
        SECURITY: Checks for code injection patterns, system calls, and dangerous functions.
        
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
            (r"require\s*\(\s*['\"]os['\"]", "require('os') - OS module import"),
            (r"require\s*\(\s*['\"]io['\"]", "require('io') - IO module import"),
            (r"require\s*\(\s*['\"]package['\"]", "require('package') - package module import"),
            
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
            (r'io\.open\s*\([^)]*[\'"]w[\'"]', 'io.open() with write mode'),
            (r'io\.open\s*\([^)]*[\'"]a[\'"]', 'io.open() with append mode'),
            
            # Network operations (if not needed)
            (r'socket\.', 'socket.* - network operations'),
            (r'http\.', 'http.* - HTTP operations'),
        ]
        
        # Check each pattern
        for pattern, description in dangerous_patterns:
            matches = re.finditer(pattern, lua_code, re.IGNORECASE | re.MULTILINE)
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
    
    def _validate_lua_syntax_with_lupa(self, lua_code: str) -> Dict[str, Any]:
        """Validate LUA syntax using lupa sandbox"""
        errors = []
        warnings = []
        
        # SECURITY FIX: Validate code safety before execution
        is_safe, safety_errors = self._validate_lua_code_safety(lua_code)
        if not is_safe:
            errors.extend(safety_errors)
            return {
                "status": "failed",
                "errors": errors,
                "warnings": warnings,
                "method": "pattern_validation"
            }
        
        # ... rest of existing validation code ...
```

**Step 2:** Update the method to use validation:

```python
def _validate_lua_syntax_with_lupa(self, lua_code: str) -> Dict[str, Any]:
    """
    Validate LUA syntax using lupa sandbox.
    
    SECURITY: Validates code safety before execution.
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
            "blocked": True  # Indicate this was blocked by security check
        }
    
    # Only proceed if code passed safety checks
    try:
        import lupa
    except ImportError:
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

        # SECURITY FIX: Use string concatenation (already validated)
        validation_wrapper = "function temp_validate() " + lua_code + " end"
        lua.execute(validation_wrapper)

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
```

**Step 3:** Add comprehensive tests:

```python
# In tests/test_pipeline_validator.py
import pytest
from components.pipeline_validator import PipelineValidator

class TestLuaCodeSafetyValidation:
    """Test Lua code safety validation"""
    
    def test_os_execute_blocked(self):
        """Test that os.execute() is blocked"""
        validator = PipelineValidator(config={})
        
        malicious_code = "os.execute('rm -rf /')"
        is_safe, errors = validator._validate_lua_code_safety(malicious_code)
        
        assert not is_safe
        assert any('os.execute' in e for e in errors)
    
    def test_io_popen_blocked(self):
        """Test that io.popen() is blocked"""
        validator = PipelineValidator(config={})
        
        malicious_code = "io.popen('cat /etc/passwd')"
        is_safe, errors = validator._validate_lua_code_safety(malicious_code)
        
        assert not is_safe
        assert any('io.popen' in e for e in errors)
    
    def test_require_os_blocked(self):
        """Test that require('os') is blocked"""
        validator = PipelineValidator(config={})
        
        malicious_code = "local os = require('os'); os.execute('ls')"
        is_safe, errors = validator._validate_lua_code_safety(malicious_code)
        
        assert not is_safe
        assert any("require('os')" in e for e in errors)
    
    def test_loadstring_blocked(self):
        """Test that loadstring() is blocked"""
        validator = PipelineValidator(config={})
        
        malicious_code = "loadstring('os.execute(\"ls\")')()"
        is_safe, errors = validator._validate_lua_code_safety(malicious_code)
        
        assert not is_safe
        assert any('loadstring' in e for e in errors)
    
    def test_path_traversal_in_dofile_blocked(self):
        """Test that dofile() with path traversal is blocked"""
        validator = PipelineValidator(config={})
        
        malicious_code = "dofile('../../../etc/passwd')"
        is_safe, errors = validator._validate_lua_code_safety(malicious_code)
        
        assert not is_safe
        assert any('dofile' in e or 'path traversal' in e.lower() for e in errors)
    
    def test_valid_code_passes(self):
        """Test that valid Lua code passes validation"""
        validator = PipelineValidator(config={})
        
        valid_code = """
        function processEvent(event)
            local result = {}
            result.message = event.message
            result.timestamp = event.timestamp
            return result
        end
        """
        
        is_safe, errors = validator._validate_lua_code_safety(valid_code)
        
        assert is_safe
        assert len(errors) == 0
    
    def test_case_insensitive_detection(self):
        """Test that patterns are detected case-insensitively"""
        validator = PipelineValidator(config={})
        
        malicious_code = "OS.EXECUTE('ls')"  # Uppercase
        is_safe, errors = validator._validate_lua_code_safety(malicious_code)
        
        assert not is_safe
        assert any('os.execute' in e.lower() for e in errors)
```

**Verification Checklist:**
- [ ] All dangerous patterns are detected
- [ ] Case-insensitive matching works
- [ ] Valid code passes validation
- [ ] Error messages are descriptive
- [ ] Tests cover all dangerous patterns
- [ ] No false positives on legitimate code

---

### **TASK 4: Enable Read-Only Root Filesystem in Docker**

**File:** `docker-compose.yml`  
**Lines:** 50-125  
**Priority:** 🔴 CRITICAL  
**Estimated Time:** 4 hours

**Current Code (PROBLEMATIC):**

```yaml
parser-eater:
  # ... other config ...
  
  # Security: Read-only root filesystem (STIG V-230285)
  # TEMPORARILY DISABLED FOR TESTING: torch requires writable filesystem for temp files
  # TODO: Re-enable after finding proper tmpfs configuration for torch
  read_only: false  # ← PROBLEM: Security weakened
  
  volumes:
    # ... existing volumes ...
    - type: tmpfs
      target: /tmp
      tmpfs:
        size: 4294967296  # 4GB for torch temp files
        mode: 1777  # Temporarily world-writable for torch compatibility
```

**The Problem:**
1. Read-only filesystem is disabled, allowing file system tampering
2. tmpfs mode is 1777 (world-writable), which is insecure
3. Need to ensure all writable locations use tmpfs
4. Must verify torch/sentence-transformers work with read-only root

**What You Must Do:**

1. Enable read-only filesystem
2. Configure proper tmpfs mounts for writable directories
3. Change tmpfs mode from 1777 to 1770 (group-writable, not world-writable)
4. Test that application works correctly

**Implementation Steps:**

**Step 1:** Update `docker-compose.yml`:

```yaml
parser-eater:
  build:
    context: .
    dockerfile: Dockerfile
    args:
      - BUILDKIT_INLINE_CACHE=1
  image: purple-pipeline-parser-eater:9.0.0
  container_name: purple-parser-eater
  hostname: parser-eater

  # Security: Run as non-root user
  user: "999:999"

  # SECURITY FIX: Enable read-only root filesystem (STIG V-230285)
  read_only: true  # ← FIXED: Re-enabled for security

  # Security: Restrict capabilities (STIG V-230286)
  cap_drop:
    - ALL

  # Security: No new privileges (STIG V-230287)
  security_opt:
    - no-new-privileges:true

  # Resource Limits (STIG V-230290)
  deploy:
    resources:
      limits:
        cpus: '4'
        memory: 16G
      reservations:
        cpus: '2'
        memory: 8G

  # Environment Variables
  environment:
    # Python Configuration
    - PYTHONUNBUFFERED=1
    - PYTHONDONTWRITEBYTECODE=1
    - PYTHONHASHSEED=0
    - PYTHONSAFEPATH=1

    # Milvus Connection
    - MILVUS_HOST=milvus
    - MILVUS_PORT=19530

    # Application Configuration
    - APP_ENV=production
    - LOG_LEVEL=INFO
    - WEB_UI_HOST=0.0.0.0
    - WEB_UI_PORT=8080

    # SECURITY: API Keys from .env file
    - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    - GITHUB_TOKEN=${GITHUB_TOKEN}
    - SDL_API_KEY=${SDL_API_KEY}
    - WEB_UI_AUTH_TOKEN=${WEB_UI_AUTH_TOKEN}

  # Configuration (mounted as read-only)
  volumes:
    - type: bind
      source: ./config.yaml
      target: /app/config.yaml
      read_only: true
    - type: volume
      source: app-output
      target: /app/output
    - type: volume
      source: app-logs
      target: /app/logs
    - type: volume
      source: app-data
      target: /app/data
    
    # SECURITY FIX: Writable temp directories with proper permissions
    # Use tmpfs for temporary files (required for read-only root)
    - type: tmpfs
      target: /tmp
      tmpfs:
        size: 4294967296  # 4GB for torch temp files
        mode: 1770  # SECURITY FIX: Group-writable only (not world-writable)
        uid: 999  # Match appuser UID
        gid: 999  # Match appuser GID
    
    # Cache directory for sentence-transformers (pre-downloaded in image)
    # Note: Model is pre-downloaded in Dockerfile, but runtime may need write access
    - type: tmpfs
      target: /home/appuser/.cache
      tmpfs:
        size: 2147483648  # 2GB for model cache
        mode: 1770  # SECURITY FIX: Group-writable only
        uid: 999
        gid: 999
    
    # Additional writable locations if needed
    - type: tmpfs
      target: /var/tmp
      tmpfs:
        size: 1073741824  # 1GB
        mode: 1770
        uid: 999
        gid: 999

  # Port Mapping (Web UI only)
  ports:
    - "8080:8080"

  # Networking
  networks:
    - parser-network

  # Dependencies
  depends_on:
    milvus:
      condition: service_healthy

  # Health Check
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8080/api/status"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 120s

  # Restart Policy
  restart: unless-stopped

  # Logging Configuration (STIG V-230289)
  logging:
    driver: "json-file"
    options:
      max-size: "100m"
      max-file: "5"
      compress: "true"
```

**Step 2:** Verify Dockerfile pre-downloads models correctly:

Check that `Dockerfile` lines 90-96 properly download the model:

```dockerfile
# Pre-download sentence-transformers model to avoid runtime download
# Set HF_HOME before download so model goes to correct location
ENV HF_HOME=/home/appuser/.cache/huggingface
ENV TRANSFORMERS_CACHE=/home/appuser/.cache/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/home/appuser/.cache/sentence-transformers
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" && \
    chown -R appuser:appuser /home/appuser/.cache
```

**Note:** The model is pre-downloaded, but the tmpfs mount will overlay this. We need to ensure the model can be accessed. If there are issues, we may need to:
- Mount model directory as a volume instead of tmpfs
- Or ensure model is loaded from a different location

**Step 3:** Create test script to verify read-only filesystem:

```bash
#!/bin/bash
# tests/docker/test_readonly_fs.sh

echo "Testing read-only filesystem configuration..."

# Build and start container
docker-compose up -d parser-eater

# Wait for container to be ready
sleep 10

# Test 1: Verify root filesystem is read-only
echo "Test 1: Checking root filesystem is read-only..."
docker exec purple-parser-eater touch /test_write 2>&1 | grep -q "Read-only file system" && echo "✓ Root FS is read-only" || echo "✗ Root FS is writable (FAIL)"

# Test 2: Verify /tmp is writable
echo "Test 2: Checking /tmp is writable..."
docker exec purple-parser-eater touch /tmp/test_write && echo "✓ /tmp is writable" || echo "✗ /tmp is not writable (FAIL)"

# Test 3: Verify /tmp permissions
echo "Test 3: Checking /tmp permissions..."
PERMS=$(docker exec purple-parser-eater stat -c "%a" /tmp)
if [ "$PERMS" = "1770" ] || [ "$PERMS" = "1777" ]; then
    echo "✓ /tmp has correct permissions: $PERMS"
else
    echo "✗ /tmp has incorrect permissions: $PERMS (expected 1770)"
fi

# Test 4: Verify application works
echo "Test 4: Checking application functionality..."
STATUS=$(docker exec purple-parser-eater curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/status || echo "000")
if [ "$STATUS" = "200" ] || [ "$STATUS" = "401" ]; then
    echo "✓ Application is responding (status: $STATUS)"
else
    echo "✗ Application is not responding (status: $STATUS)"
fi

# Test 5: Verify torch/sentence-transformers work
echo "Test 5: Testing sentence-transformers model loading..."
docker exec purple-parser-eater python -c "
from sentence_transformers import SentenceTransformer
try:
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print('✓ Model loaded successfully')
except Exception as e:
    print(f'✗ Model loading failed: {e}')
"

echo "Tests complete!"
```

**Step 4:** Update documentation:

Add note in `docker-compose.yml` comments:

```yaml
# ============================================================================
# Security Notes
# ============================================================================
# Read-only root filesystem is ENABLED for security (STIG V-230285)
#
# Writable locations via tmpfs:
# - /tmp: 4GB for temporary files (torch, subprocess temp files)
# - /home/appuser/.cache: 2GB for model cache (sentence-transformers)
# - /var/tmp: 1GB for additional temp files
#
# All tmpfs mounts use mode 1770 (group-writable, not world-writable)
# and are owned by appuser (UID 999, GID 999)
#
# If you encounter permission errors:
# 1. Check tmpfs mounts are created correctly
# 2. Verify UID/GID match appuser (999:999)
# 3. Check application logs for specific errors
# ============================================================================
```

**Verification Checklist:**
- [ ] Read-only filesystem is enabled (`read_only: true`)
- [ ] All tmpfs mounts have mode 1770 (not 1777)
- [ ] tmpfs mounts have correct UID/GID (999:999)
- [ ] Application starts successfully
- [ ] Health check passes
- [ ] Sentence-transformers model loads correctly
- [ ] No permission errors in logs
- [ ] Test script passes all checks

---

## 📋 COMPLETE DELIVERABLES CHECKLIST

After completing all 4 tasks, verify:

### **Code Changes:**
- [ ] `components/dataplane_validator.py` - Path escaping added
- [ ] `components/dataplane_validator.py` - File handle leaks fixed
- [ ] `components/transform_executor.py` - File handle leaks fixed
- [ ] `components/pipeline_validator.py` - Lua code validation added
- [ ] `docker-compose.yml` - Read-only filesystem enabled

### **Tests:**
- [ ] `tests/test_dataplane_validator.py` - Security tests added
- [ ] `tests/test_pipeline_validator.py` - Safety validation tests added
- [ ] `tests/docker/test_readonly_fs.sh` - Docker test script created
- [ ] All existing tests still pass

### **Documentation:**
- [ ] Code comments explain security fixes
- [ ] Docker-compose comments updated
- [ ] SecurityError exception documented

### **Verification:**
- [ ] Run all tests: `pytest tests/ -v`
- [ ] Run security tests: `pytest tests/test_dataplane_validator.py tests/test_pipeline_validator.py -v`
- [ ] Test Docker: `docker-compose up -d && ./tests/docker/test_readonly_fs.sh`
- [ ] Verify no regressions in application functionality

---

## 🚨 IMPORTANT NOTES

1. **Don't Break Existing Functionality:** All fixes must maintain backward compatibility
2. **Test Thoroughly:** Write tests for each fix before implementing
3. **Follow Python Best Practices:** Use type hints, docstrings, proper error handling
4. **Security First:** When in doubt, err on the side of security
5. **Document Changes:** Add comments explaining why security measures are in place

---

## 📞 IF YOU GET STUCK

**Common Issues:**

1. **Path validation fails:** Check that you're comparing absolute paths correctly
2. **File handle tests fail on Windows:** Use platform-specific file descriptor checking
3. **Lua validation has false positives:** Refine regex patterns, add more context
4. **Docker read-only issues:** Check tmpfs mounts are created before container starts

**Resources:**
- Python `pathlib` documentation: https://docs.python.org/3/library/pathlib.html
- Docker tmpfs documentation: https://docs.docker.com/storage/tmpfs/
- Lua pattern matching: https://www.lua.org/manual/5.4/manual.html#6.4.1

---

## ✅ SUCCESS CRITERIA

Your work is complete when:

1. ✅ All 4 critical issues are fixed
2. ✅ All tests pass (new and existing)
3. ✅ No security vulnerabilities remain in your assigned files
4. ✅ Code follows best practices (type hints, error handling, documentation)
5. ✅ Docker container runs successfully with read-only filesystem
6. ✅ No regressions in application functionality

---

**START WORKING NOW. Good luck! 🚀**

