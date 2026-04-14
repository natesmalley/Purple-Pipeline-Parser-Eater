"""Phase 1.B hard-reject lint tests for lua_linter."""
import pytest

from components.testing_harness.lua_linter import lint_script, LuaLintResult


class TestLv3HardRejects:
    @pytest.mark.parametrize("bad_pattern", [
        'os.execute("id")',
        'os.remove("/tmp/x")',
        'os.rename("/a", "/b")',
        'io.popen("ls")',
        'io.open("/etc/passwd", "r")',
        'package.loadlib("mylib.so", "fn")',
        'debug.sethook(function() end, "l")',
        'loadstring("return 1")()',
        'dofile("script.lua")',
        'loadfile("script.lua")',
    ])
    def test_lv3_rejects_dangerous_pattern(self, bad_pattern):
        """Each dangerous primitive must trigger a hard rejection in lv3 context."""
        src = f"function processEvent(event) {bad_pattern}; return event end"
        result = lint_script(src, context="lv3")
        assert isinstance(result, LuaLintResult)
        assert result.has_hard_reject, f"Expected hard-reject for: {bad_pattern}"
        assert len(result.hard_reject_findings) >= 1
        assert result.rejection_reason(), "rejection_reason() must be non-empty on reject"

    def test_lv3_clean_script_passes(self):
        """A plain OCSF mapping script must NOT trigger a rejection."""
        src = '''
        function processEvent(event)
            event.class_uid = 2001
            event.activity_id = 1
            local ok, t = pcall(os.time)
            if ok then event.time = t * 1000 end
            return event
        end
        '''
        result = lint_script(src, context="lv3")
        assert not result.has_hard_reject
        assert result.rejection_reason() == ""

    def test_lv3_ignores_pattern_in_comment(self):
        """A dangerous primitive mentioned inside a Lua line comment must not reject."""
        src = "function processEvent(event)\n    -- NOTE: never call os.execute here\n    return event\nend\n"
        result = lint_script(src, context="lv3")
        assert not result.has_hard_reject


class TestScolHardRejects:
    @pytest.mark.parametrize("bad_pattern", ["ExecBulk", "ExecParams", "ExecFetchArg"])
    def test_scol_rejects_exec_tables(self, bad_pattern):
        src = f'function start(config) local job = {{ {bad_pattern} = {{}} }}; return job end'
        result = lint_script(src, context="scol", allow_exec=False)
        assert result.has_hard_reject
        assert any(
            bad_pattern in f["description"] or bad_pattern in f["pattern"]
            for f in result.hard_reject_findings
        )

    def test_scol_allow_exec_opt_in(self):
        """With allow_exec=True, ExecBulk is permitted (operator escape hatch)."""
        src = 'function start(config) local job = { ExecBulk = {} }; return job end'
        result = lint_script(src, context="scol", allow_exec=True)
        assert not result.has_hard_reject

    def test_scol_still_rejects_stdlib_primitive_even_with_allow_exec(self):
        """allow_exec only whitelists the scol exec tables, not stdlib primitives."""
        src = 'function start(config) io.popen("ls"); return {} end'
        result = lint_script(src, context="scol", allow_exec=True)
        assert result.has_hard_reject


class TestContextDefault:
    def test_default_context_is_lv3(self):
        """Existing callers that don't pass context must default to lv3."""
        src = 'function processEvent(e) io.popen("ls"); return e end'
        result = lint_script(src)  # no context kwarg
        assert result.has_hard_reject
        assert result.context == "lv3"

    def test_invalid_context_raises(self):
        with pytest.raises(ValueError):
            lint_script("return 1", context="bogus")
