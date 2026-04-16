"""Transform execution strategies for runtime processing."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from components.dataplane_validator import SecurityError


logger = logging.getLogger(__name__)


# DEFENSE-IN-DEPTH: the real Observo dataplane Lua runtime is fully unsandboxed
# (verified by binary symbol audit: mlua::state::Lua::unsafe_new_with + luaL_openlibs).
# We are being STRICTER than production on purpose. Do NOT relax this sandbox to
# "match Observo" — it protects the local harness + workbench execution paths
# from RCE via an LLM-generated script. See plan Phase 1.A.
_SANDBOX_PRELUDE = """
    -- Preserve safe os functions before sandboxing
    local safe_os = {
        time = os.time,
        date = os.date,
        clock = os.clock,
        difftime = os.difftime,
    }

    -- Disable dangerous modules
    io = nil; load = nil; loadfile = nil
    loadstring = nil; dofile = nil
    package = nil; collectgarbage = nil

    -- Expanded blocklist: prevent metatable/raw access and coroutines
    rawget = nil
    rawset = nil
    rawequal = nil
    rawlen = nil
    getmetatable = nil
    setmetatable = nil
    coroutine = nil

    -- Prevent string.dump bytecode leakage
    string.dump = nil

    -- Safe wrapper for string.rep to prevent memory DoS
    local _original_string_rep = string.rep
    string.rep = function(s, n)
        if n > 1000000 then return nil end
        return _original_string_rep(s, n)
    end

    -- Execution timeout via instruction count hook
    local _instruction_count = 0
    local _max_instructions = 10000000
    debug.sethook(function()
        _instruction_count = _instruction_count + 1
        if _instruction_count > _max_instructions then
            error("execution timeout: exceeded maximum instruction count")
        end
    end, "", 10000)

    -- Now safe to nil debug (hook survives)
    debug = nil

    -- Replace os with safe subset (no execute, remove, rename, etc.)
    os = safe_os

    -- Stub require() to return safe modules (matches harness sandbox)
    require = function(mod)
        if mod == 'json' then
            return { encode = function(v) return tostring(v) end,
                     decode = function(s) return s end }
        elseif mod == 'log' then
            return { info = function() end, warn = function() end,
                     error = function() end, debug = function() end }
        end
        return nil
    end
"""


def _build_sandboxed_runtime():
    """Construct a fresh sandboxed LuaRuntime.

    DEFENSE-IN-DEPTH: mirrors components/testing_harness/dual_execution_engine.py
    exactly. See plan Phase 1.A. Do NOT relax this sandbox.
    """
    from lupa import LuaRuntime  # type: ignore

    lua = LuaRuntime(
        unpack_returned_tuples=True,
        register_eval=False,
        register_builtins=False,
    )
    lua.execute(_SANDBOX_PRELUDE)
    return lua


# Wall-clock timeout (seconds) for a single LupaExecutor.execute call.
# Belt-and-suspenders with the instruction-count hook inside _SANDBOX_PRELUDE.
# TODO: lupa does not expose cancellation; the thread-based guard here only
# limits how long the caller waits. The instruction-count hook is the actual
# hard stop — a tight infinite loop will trip it in ~10M instructions.
_LUPA_WALL_CLOCK_SECONDS = 5.0


class TransformExecutor(ABC):
    """Abstract executor interface."""

    @abstractmethod
    async def execute(self, lua_code: str, event: Dict[str, Any], parser_id: str) -> Tuple[bool, Dict[str, Any]]:
        """Execute Lua transform against event."""

    async def close(self) -> None:
        """Release resources if any (optional)."""


class LupaExecutor(TransformExecutor):
    """Fast in-process executor using lupa.

    Phase 1.A: per-parser_id sandboxed LuaRuntime. Each parser_id gets its own
    fresh runtime (loaded once, cached) so parser A cannot read or mutate
    parser B's globals, metatables, or package state. The sandbox mirrors
    components/testing_harness/dual_execution_engine.py — see _SANDBOX_PRELUDE
    above and plan Phase 1.A.
    """

    def __init__(self) -> None:
        # Per-parser_id cache of (LuaRuntime, processEvent_callable).
        # Dropped the shared self._lua + single cache — that allowed cross-parser
        # state leakage via globals / metatables. Plan Phase 1.A.
        self._runtimes: Dict[str, Tuple[Any, Any]] = {}
        self._lock = threading.Lock()

    def _get_or_build(self, lua_code: str, parser_id: str):
        with self._lock:
            cached = self._runtimes.get(parser_id)
            if cached is not None:
                return cached

            lua = _build_sandboxed_runtime()
            lua.execute(lua_code)
            # lupa _LuaTable does not have dict-style .get; index with [].
            process_event = lua.globals()["processEvent"]
            if process_event is None:
                raise ValueError("Lua transform must define processEvent")
            self._runtimes[parser_id] = (lua, process_event)
            return self._runtimes[parser_id]

    async def execute(self, lua_code: str, event: Dict[str, Any], parser_id: str) -> Tuple[bool, Dict[str, Any]]:
        try:
            _lua, process_event = self._get_or_build(lua_code, parser_id)

            # Wall-clock guard: run the invocation in a worker thread so a
            # runaway script cannot hang the caller forever. The in-Lua
            # instruction-count hook from _SANDBOX_PRELUDE is the hard stop;
            # this thread-join timeout just bounds the caller's wait.
            result_box: Dict[str, Any] = {}

            def _invoke():
                try:
                    result_box["result"] = process_event(event)
                except Exception as inner_exc:  # pylint: disable=broad-except
                    result_box["error"] = inner_exc

            worker = threading.Thread(target=_invoke, daemon=True)
            worker.start()
            worker.join(_LUPA_WALL_CLOCK_SECONDS)
            if worker.is_alive():
                logger.error("Lupa execution wall-clock timeout for %s", parser_id)
                # Evict so next call gets a fresh runtime.
                with self._lock:
                    self._runtimes.pop(parser_id, None)
                return False, {"error": "execution timeout"}

            if "error" in result_box:
                raise result_box["error"]

            result = result_box.get("result")
            return True, result if result is not None else {}
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Lupa execution failed for %s", parser_id)
            return False, {"error": str(exc)}


class DataplaneExecutor(TransformExecutor):
    """Execute transform via dataplane binary (parity with production)."""

    DEFAULT_TIMEOUT = 10

    def __init__(self, binary_path: str, timeout: Optional[int] = None) -> None:
        self._binary_path = Path(binary_path)
        if not self._binary_path.exists():
            raise FileNotFoundError(f"Dataplane binary not found: {self._binary_path}")

        # Configurable timeout from environment or parameter
        if timeout is not None:
            self._timeout = timeout
        else:
            env_timeout = os.getenv('DATAPLANE_EXECUTION_TIMEOUT')
            if env_timeout:
                try:
                    self._timeout = int(env_timeout)
                except ValueError:
                    logger.warning(
                        f"Invalid DATAPLANE_EXECUTION_TIMEOUT value: {env_timeout}, "
                        f"using default: {self.DEFAULT_TIMEOUT}"
                    )
                    self._timeout = self.DEFAULT_TIMEOUT
            else:
                self._timeout = self.DEFAULT_TIMEOUT

        # Validate timeout
        if self._timeout < 1 or self._timeout > 60:
            raise ValueError(
                f"Timeout must be between 1 and 60 seconds, got: {self._timeout}"
            )

    async def execute(self, lua_code: str, event: Dict[str, Any], parser_id: str) -> Tuple[bool, Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._run_sync, lua_code, event, parser_id)

    def _run_sync(
        self,
        lua_code: str,
        event: Dict[str, Any],
        parser_id: str
    ) -> Tuple[bool, Dict[str, Any]]:
        with tempfile.TemporaryDirectory(
            prefix=f"pppe-{parser_id}-"
        ) as tmpdir:
            tmp_path = Path(tmpdir)
            lua_file = tmp_path / "transform.lua"
            lua_file.write_text(lua_code, encoding="utf-8")

            config_file = tmp_path / "config.yaml"
            config_file.write_text(
                self._render_config(lua_file),
                encoding="utf-8"
            )

            event_file = tmp_path / "event.json"
            event_file.write_text(json.dumps(event), encoding="utf-8")

            # SECURITY FIX: Use context manager to ensure file is closed
            try:
                # SECURITY FIX: Validate binary path is within allowed directory
                binary_path_resolved = Path(self._binary_path).resolve()
                allowed_binary_dir = Path("/opt/dataplane")
                if not str(binary_path_resolved).startswith(str(allowed_binary_dir.resolve())):
                    raise SecurityError(
                        f"Binary path {self._binary_path} is outside allowed directory {allowed_binary_dir}"
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
                
                with open(event_file, "rb") as stdin_file:
                    result = subprocess.run(  # nosec B603
                        [
                            str(self._binary_path),
                            "--config",
                            str(config_file)
                        ],
                        stdin=stdin_file,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                        timeout=self._timeout,
                    )
            except subprocess.TimeoutExpired:
                logger.error("Dataplane execution timed out")
                return False, {"error": "timeout"}
            except Exception as e:
                logger.error("Dataplane execution error: %s", e)
                return False, {"error": str(e)}

            if result.returncode != 0:
                stderr_msg = result.stderr.decode("utf-8", "ignore")
                logger.error("Dataplane executor failed: %s", stderr_msg)
                return False, {"error": stderr_msg}

            # SECURITY FIX: Limit JSON parsing size to prevent DoS
            stdout_decoded = result.stdout.decode("utf-8")
            MAX_JSON_SIZE = 10 * 1024 * 1024  # 10MB max
            if len(stdout_decoded) > MAX_JSON_SIZE:
                logger.error(f"Dataplane output too large ({len(stdout_decoded)} bytes)")
                return False, {"error": "output_too_large"}
            
            try:
                output = json.loads(stdout_decoded)
            except json.JSONDecodeError as exc:
                logger.error("Failed to decode dataplane output: %s", exc)
                return False, {"error": "invalid_output"}

            return True, output

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
  stdout:
    type: console
    inputs: ["lua_transform"]
    encoding:
      codec: json
"""


def create_executor(config: Dict[str, Any]) -> TransformExecutor:
    """Factory for transform executor selection."""

    executor_type = (config.get("transform_worker", {}).get("executor") or "lupa").lower()
    if executor_type == "dataplane":
        binary = config.get("dataplane", {}).get("binary_path", "/opt/dataplane/dataplane")
        logger.info("Using DataplaneExecutor (binary=%s)", binary)
        return DataplaneExecutor(binary)

    logger.info("Using LupaExecutor")
    return LupaExecutor()

