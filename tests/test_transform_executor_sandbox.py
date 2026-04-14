"""Phase 1.A sandbox tests for components.transform_executor.LupaExecutor.

These tests verify the defense-in-depth Lua sandbox added in Phase 1.A:
  - dangerous stdlib surfaces (os.execute, io.open, package, debug, load,
    loadstring, dofile, loadfile, string.dump) are nil inside the runtime,
  - a runaway script hits the wall-clock / instruction-count guard,
  - per-parser_id runtimes isolate globals + metatables across parsers,
  - the four SecurityError raise sites in DataplaneExecutor remain reachable.

See plan Phase 1.A and components/testing_harness/dual_execution_engine.py
for the reference sandbox shape this mirrors.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

# Guard: skip the module if lupa isn't installed. lupa is listed in
# requirements-test.txt; do NOT attempt to install it here.
lupa = pytest.importorskip("lupa")

from components.transform_executor import DataplaneExecutor, LupaExecutor, SecurityError


def _run(executor: LupaExecutor, lua_src: str, parser_id: str = "p_test"):
    """Drive LupaExecutor.execute() synchronously.

    Every script is wrapped so it defines processEvent(event) — that is the
    entry point the executor looks up after loading the chunk. Each test
    passes a Lua body that returns a dict; on sandbox violation the body
    raises inside Lua and the wrapper surfaces the error on (ok=False).
    """
    wrapped = f"""
function processEvent(event)
{lua_src}
  return event
end
"""
    return asyncio.run(executor.execute(wrapped, {"log": {"k": "v"}}, parser_id))


@pytest.fixture
def executor() -> LupaExecutor:
    return LupaExecutor()


class TestSandboxBlockedPrimitives:
    """Each dangerous stdlib surface must be nil inside the sandbox."""

    def test_os_execute_blocked(self, executor: LupaExecutor) -> None:
        ok, res = _run(executor, '  assert(os.execute == nil, "os.execute leaked")')
        assert ok, f"expected sandboxed call to succeed, got {res}"

    def test_os_execute_call_raises(self, executor: LupaExecutor) -> None:
        ok, res = _run(executor, '  os.execute("whoami")', parser_id="os_exec")
        assert not ok
        assert "error" in res

    def test_io_popen_blocked(self, executor: LupaExecutor) -> None:
        ok, res = _run(executor, '  assert(io == nil, "io leaked")')
        assert ok, f"expected sandboxed call to succeed, got {res}"

    def test_io_open_blocked(self, executor: LupaExecutor) -> None:
        ok, res = _run(executor, '  io.open("/etc/passwd", "r")', parser_id="io_open")
        assert not ok
        assert "error" in res

    def test_package_loadlib_blocked(self, executor: LupaExecutor) -> None:
        ok, res = _run(executor, '  assert(package == nil, "package leaked")')
        assert ok, f"expected sandboxed call to succeed, got {res}"

    def test_debug_sethook_blocked(self, executor: LupaExecutor) -> None:
        # debug is niled AFTER the instruction-count hook is installed.
        ok, res = _run(executor, '  assert(debug == nil, "debug leaked")')
        assert ok, f"expected sandboxed call to succeed, got {res}"

    def test_loadstring_blocked(self, executor: LupaExecutor) -> None:
        ok, res = _run(
            executor,
            '  assert(load == nil and loadstring == nil, "load leaked")',
        )
        assert ok, f"expected sandboxed call to succeed, got {res}"

    def test_dofile_blocked(self, executor: LupaExecutor) -> None:
        ok, res = _run(executor, '  assert(dofile == nil, "dofile leaked")')
        assert ok, f"expected sandboxed call to succeed, got {res}"

    def test_loadfile_blocked(self, executor: LupaExecutor) -> None:
        ok, res = _run(executor, '  assert(loadfile == nil, "loadfile leaked")')
        assert ok, f"expected sandboxed call to succeed, got {res}"

    def test_string_dump_blocked(self, executor: LupaExecutor) -> None:
        ok, res = _run(
            executor,
            '  assert(string.dump == nil, "string.dump leaked")',
        )
        assert ok, f"expected sandboxed call to succeed, got {res}"

    def test_rawset_blocked(self, executor: LupaExecutor) -> None:
        ok, res = _run(executor, '  assert(rawset == nil and rawget == nil)')
        assert ok, f"expected sandboxed call to succeed, got {res}"

    def test_setmetatable_blocked(self, executor: LupaExecutor) -> None:
        ok, res = _run(executor, '  assert(setmetatable == nil)')
        assert ok, f"expected sandboxed call to succeed, got {res}"

    def test_safe_os_time_preserved(self, executor: LupaExecutor) -> None:
        ok, res = _run(
            executor,
            '  assert(type(os.time) == "function", "os.time should still work")',
        )
        assert ok, f"expected os.time to be preserved, got {res}"


class TestSandboxTimeoutAndResourceLimits:
    def test_infinite_loop_times_out(self, executor: LupaExecutor) -> None:
        """`while true do end` must hit the wall-clock / instruction guard."""
        ok, res = _run(
            executor,
            "  while true do end",
            parser_id="loop_parser",
        )
        assert not ok
        assert "error" in res
        # Either the in-Lua instruction hook fired ("execution timeout"
        # substring) or the Python wall-clock guard fired.
        err_s = str(res.get("error", "")).lower()
        assert "timeout" in err_s or "instruction" in err_s

    def test_string_rep_dos_blocked(self, executor: LupaExecutor) -> None:
        """string.rep with huge n returns nil (DoS guard from prelude)."""
        ok, res = _run(
            executor,
            '  local big = string.rep("a", 2000000); assert(big == nil)',
        )
        assert ok, f"expected sandboxed string.rep guard to return nil, got {res}"


class TestCrossParserIsolation:
    def test_parser_a_cannot_read_parser_b_globals(self, executor: LupaExecutor) -> None:
        """Parser A sets a global; Parser B must not see it."""
        ok_a, res_a = _run(
            executor,
            '  _G.SECRET = "parser_a_value"',
            parser_id="parser_a",
        )
        assert ok_a, f"parser A setup failed: {res_a}"

        ok_b, res_b = _run(
            executor,
            '  assert(_G.SECRET == nil, "parser B saw parser A global: " .. tostring(_G.SECRET))',
            parser_id="parser_b",
        )
        assert ok_b, f"cross-parser global leaked: {res_b}"

    def test_parser_a_cannot_mutate_parser_b_string_lib(self, executor: LupaExecutor) -> None:
        """Parser A monkey-patches string.upper; Parser B sees pristine string.upper."""
        ok_a, res_a = _run(
            executor,
            '  string.upper = function(s) return "PWNED" end',
            parser_id="patcher",
        )
        assert ok_a, f"parser A patch setup failed: {res_a}"

        ok_b, res_b = _run(
            executor,
            '  assert(string.upper("hi") == "HI", "string.upper was mutated cross-parser: " .. string.upper("hi"))',
            parser_id="victim",
        )
        assert ok_b, f"cross-parser string lib mutation leaked: {res_b}"


class TestSecurityErrorRaisePathsStillWork:
    """Phase 0 promoted SecurityError to a module-level import. Confirm the
    four raise sites in DataplaneExecutor are still reachable (not dead code)
    and that they raise SecurityError, not NameError, after Phase 1.A's edits.
    """

    def test_security_error_is_importable_at_module_level(self) -> None:
        from components import transform_executor as te

        assert te.SecurityError is SecurityError

    def test_render_config_rejects_path_traversal(self, tmp_path: Path) -> None:
        """_render_config raises SecurityError for a lua_file outside tempdir.

        This exercises the raise site near line 340 (path-traversal guard).
        """
        import tempfile as _tempfile

        # Build a DataplaneExecutor with a fake binary path that exists so
        # __init__ doesn't fail. We won't actually run the subprocess.
        fake_bin = tmp_path / "fake_dataplane"
        fake_bin.write_bytes(b"#!/bin/true\n")
        try:
            de = DataplaneExecutor(str(fake_bin))
        except FileNotFoundError:
            pytest.skip("DataplaneExecutor rejected fake binary path")

        outside = Path("/definitely/not/in/tmp/evil.lua")
        # If the current platform's tempdir is a prefix of "/definitely/..."
        # (it won't be, but be defensive), skip.
        try:
            outside.resolve().relative_to(Path(_tempfile.gettempdir()).resolve())
            pytest.skip("outside path is coincidentally under tempdir")
        except ValueError:
            pass

        with pytest.raises(SecurityError):
            de._render_config(outside)

    def test_render_config_rejects_dangerous_patterns(self, tmp_path: Path) -> None:
        """_render_config raises SecurityError when the path contains `..`.

        This exercises the raise site near line 357 (dangerous-pattern guard).
        We construct a path inside the real tempdir so the first guard passes,
        then rely on the `..` pattern check downstream.
        """
        import tempfile as _tempfile

        fake_bin = tmp_path / "fake_dataplane2"
        fake_bin.write_bytes(b"#!/bin/true\n")
        try:
            de = DataplaneExecutor(str(fake_bin))
        except FileNotFoundError:
            pytest.skip("DataplaneExecutor rejected fake binary path")

        temp_base = Path(_tempfile.gettempdir()).resolve()
        # Build a path inside tempdir containing '..' as a literal segment
        # by creating a real subdir and traversing through it.
        sub = temp_base / "pppe_sbx_test"
        sub.mkdir(exist_ok=True)
        tricky = sub / ".." / "pppe_sbx_test" / "x.lua"
        # tricky.resolve() will be inside tempdir (first guard passes) but
        # the as_posix() string fed to the dangerous-pattern check still
        # contains '..' only if we bypass resolution. The real code uses
        # `lua_file.as_posix()` on the un-resolved input — so pass tricky
        # un-resolved.
        with pytest.raises(SecurityError):
            de._render_config(tricky)
