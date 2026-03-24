"""Dataplane-backed Lua validation for PPPE."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Security-related error (path traversal, injection attempt, etc.)"""
    pass


@dataclass
class DataplaneValidationResult:
    success: bool
    output_events: List[Dict[str, Any]]
    stderr: str
    ocsf_missing_fields: List[str]
    error: str | None = None


class DataplaneValidator:
    """Validates generated Lua via dataplane binary."""

    DEFAULT_TIMEOUT = 30

    # SECURITY FIX: Phase 7 - Input size limits
    MAX_LUA_CODE_SIZE = 1 * 1024 * 1024  # 1MB
    MAX_EVENTS_COUNT = 10000
    MAX_EVENT_SIZE = 100 * 1024  # 100KB per event
    MAX_TOTAL_EVENTS_SIZE = 10 * 1024 * 1024  # 10MB total

    def __init__(self, binary_path: str, ocsf_required_fields: List[str], timeout: Optional[int] = None) -> None:
        self.binary_path = Path(binary_path)
        if not self.binary_path.exists():
            raise FileNotFoundError(f"Dataplane binary not found: {self.binary_path}")
        self.ocsf_required_fields = ocsf_required_fields

        # SECURITY FIX: Configurable timeout from environment or parameter
        if timeout is not None:
            self.timeout = timeout
        else:
            env_timeout = os.getenv('DATAPLANE_VALIDATION_TIMEOUT')
            if env_timeout:
                try:
                    self.timeout = int(env_timeout)
                except ValueError:
                    logger.warning(
                        f"Invalid DATAPLANE_VALIDATION_TIMEOUT value: {env_timeout}, "
                        f"using default: {self.DEFAULT_TIMEOUT}"
                    )
                    self.timeout = self.DEFAULT_TIMEOUT
            else:
                self.timeout = self.DEFAULT_TIMEOUT

        # Validate timeout is reasonable
        if self.timeout < 1 or self.timeout > 300:
            raise ValueError(
                f"Timeout must be between 1 and 300 seconds, got: {self.timeout}"
            )

    def _validate_input_sizes(
        self,
        lua_code: str,
        events: List[Dict[str, Any]],
        parser_id: str
    ) -> Optional[str]:
        """
        Validate input sizes are within limits.

        SECURITY FIX: Phase 7 - Prevent DoS attacks via oversized inputs

        Returns:
            Error message if validation fails, None if valid
        """
        # Check Lua code size
        lua_size = len(lua_code.encode('utf-8'))
        if lua_size > self.MAX_LUA_CODE_SIZE:
            return (
                f"Lua code too large: {lua_size} bytes "
                f"(maximum: {self.MAX_LUA_CODE_SIZE} bytes)"
            )

        # Check event count
        if len(events) > self.MAX_EVENTS_COUNT:
            return (
                f"Too many events: {len(events)} "
                f"(maximum: {self.MAX_EVENTS_COUNT})"
            )

        # Check individual event sizes and total size
        total_size = 0
        for i, event in enumerate(events):
            try:
                event_json = json.dumps(event)
                event_size = len(event_json.encode('utf-8'))

                if event_size > self.MAX_EVENT_SIZE:
                    return (
                        f"Event {i} too large: {event_size} bytes "
                        f"(maximum: {self.MAX_EVENT_SIZE} bytes per event)"
                    )

                total_size += event_size

            except Exception as e:
                return f"Error serializing event {i}: {str(e)}"

        if total_size > self.MAX_TOTAL_EVENTS_SIZE:
            return (
                f"Total events size too large: {total_size} bytes "
                f"(maximum: {self.MAX_TOTAL_EVENTS_SIZE} bytes)"
            )

        return None  # All validations passed

    def validate(
        self,
        lua_code: str,
        events: List[Dict[str, Any]],
        parser_id: str
    ) -> DataplaneValidationResult:
        # SECURITY FIX: Phase 7 - Validate input sizes before processing
        validation_error = self._validate_input_sizes(lua_code, events, parser_id)
        if validation_error:
            logger.error("Input size validation failed for %s: %s", parser_id, validation_error)
            return DataplaneValidationResult(
                success=False,
                output_events=[],
                stderr=validation_error,
                ocsf_missing_fields=[],
                error="input_size_exceeded",
            )

        with tempfile.TemporaryDirectory(
            prefix=f"pppe-validate-{parser_id}-"
        ) as tmpdir:
            tmp_path = Path(tmpdir)
            lua_file = tmp_path / "transform.lua"
            lua_file.write_text(lua_code, encoding="utf-8")

            config_file = tmp_path / "config.yaml"
            config_file.write_text(
                self._render_config(lua_file),
                encoding="utf-8"
            )

            events_file = tmp_path / "events.jsonl"
            events_file.write_text(
                "\n".join(json.dumps(e) for e in events),
                encoding="utf-8"
            )

            # SECURITY FIX: Use context manager to ensure file is closed
            try:
                # SECURITY FIX: Validate binary path is within allowed directory
                binary_path_resolved = Path(self.binary_path).resolve()
                allowed_binary_dir = Path("/opt/dataplane")
                if not str(binary_path_resolved).startswith(str(allowed_binary_dir.resolve())):
                    raise SecurityError(
                        f"Binary path {self.binary_path} is outside allowed directory {allowed_binary_dir}"
                    )
                
                # SECURITY FIX: Validate config file is within temp directory
                config_path_resolved = Path(config_file).resolve()
                temp_base = Path(tempfile.gettempdir())
                try:
                    config_path_resolved.relative_to(temp_base)
                except ValueError:
                    raise SecurityError(
                        f"Config file {config_file} is outside temp directory {temp_base}"
                    )
                
                with open(events_file, "rb") as stdin_file:
                    process = subprocess.run(  # nosec B603
                        [str(self.binary_path), "--config", str(config_file)],
                        stdin=stdin_file,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                        timeout=self.timeout,
                    )
            except subprocess.TimeoutExpired:
                logger.error(
                    "Dataplane validation timed out for %s",
                    parser_id
                )
                return DataplaneValidationResult(
                    success=False,
                    output_events=[],
                    stderr="Validation timeout",
                    ocsf_missing_fields=[],
                    error="timeout",
                )
            except Exception as e:
                logger.error(
                    "Dataplane validation error for %s: %s",
                    parser_id,
                    e
                )
                return DataplaneValidationResult(
                    success=False,
                    output_events=[],
                    stderr=str(e),
                    ocsf_missing_fields=[],
                    error="subprocess_error",
                )

        stdout = process.stdout.decode("utf-8", "ignore")
        stderr = process.stderr.decode("utf-8", "ignore")

        if process.returncode != 0:
            logger.error("Dataplane validation failed for %s: %s", parser_id, stderr)
            return DataplaneValidationResult(
                success=False,
                output_events=[],
                stderr=stderr,
                ocsf_missing_fields=[],
                error="dataplane_error",
            )

        # SECURITY FIX: Limit JSON parsing size to prevent DoS
        MAX_JSON_LINE_SIZE = 10 * 1024 * 1024  # 10MB per line
        output_events = []
        for line in stdout.splitlines():
            if line.strip():
                # Check line size before parsing
                if len(line) > MAX_JSON_LINE_SIZE:
                    logger.warning(f"JSON line too large ({len(line)} bytes), skipping")
                    continue
                try:
                    output_events.append(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON line: {e}")
                    continue
        
        ocsf_missing = self._check_ocsf_fields(output_events)

        return DataplaneValidationResult(
            success=len(ocsf_missing) == 0,
            output_events=output_events,
            stderr=stderr,
            ocsf_missing_fields=ocsf_missing,
            error=None if len(ocsf_missing) == 0 else "ocsf_missing_fields",
        )

    def _render_config(self, lua_file: Path) -> str:
        """
        Render dataplane configuration with Lua transform.

        SECURITY: Validates path is within temp directory and escapes special
        characters for Lua string context.

        Args:
            lua_file: Path to Lua transform file (must be within temp directory)

        Returns:
            YAML configuration string for dataplane

        Raises:
            SecurityError: If path is outside temp directory or contains
                dangerous patterns
        """
        # SECURITY FIX: Validate path is within temp directory
        lua_path_abs = lua_file.resolve()  # Get absolute path

        # Get the temp directory base
        temp_base = Path(tempfile.gettempdir())

        # Ensure path is within temp directory (prevent path traversal)
        try:
            lua_path_abs.relative_to(temp_base)
        except ValueError:
            # Path is outside temp directory - security violation
            raise SecurityError(
                f"Invalid lua_file path - potential path traversal detected. "
                f"Path: {lua_path_abs}, Temp base: {temp_base}"
            )

        # SECURITY FIX: Escape special characters for Lua string context
        lua_path_str = lua_file.as_posix()  # Use forward slashes

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

    def _check_ocsf_fields(self, events: List[Dict[str, Any]]) -> List[str]:
        missing_fields: Dict[str, int] = {field: 0 for field in self.ocsf_required_fields}

        for event in events:
            log_body = event.get("log", {})
            for field in self.ocsf_required_fields:
                if field not in log_body:
                    missing_fields[field] += 1

        return [field for field, count in missing_fields.items() if count > 0]

