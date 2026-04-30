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


class TestFinding1WhitespaceAroundDot:
    """Finding #1 regression gate — whitespace around `.` must still trigger hard-reject."""

    @pytest.mark.parametrize("bad_variant", [
        "os.execute('id')",              # baseline
        "os . execute('id')",            # spaces
        "os  .  execute('id')",          # multiple spaces
        "os\t.\texecute('id')",          # tabs
        "os\n.\nexecute('id')",          # newlines
        "os\t.  execute('id')",          # mixed
    ])
    def test_whitespace_variants_rejected(self, bad_variant):
        src = f"function processEvent(e) {bad_variant}; return e end"
        result = lint_script(src, context="lv3")
        assert result.has_hard_reject, f"Finding #1: lint passed whitespace variant: {bad_variant!r}"


class TestFinding2SubscriptNotation:
    """Finding #2 regression gate — os[\"execute\"] must be rejected."""

    @pytest.mark.parametrize("bad_variant", [
        'os["execute"]("id")',
        "os['execute']('id')",
        'os [ "execute" ] ( "id" )',
        'io["popen"]("ls")',
        'io["open"]("/etc/passwd")',
        'package["loadlib"]("x","y")',
        'debug["sethook"](function() end, "l")',
    ])
    def test_subscript_variants_rejected(self, bad_variant):
        src = f"function processEvent(e) {bad_variant}; return e end"
        result = lint_script(src, context="lv3")
        assert result.has_hard_reject, f"Finding #2: lint passed subscript variant: {bad_variant!r}"


class TestFinding3RequireBypass:
    """Finding #3 regression gate — require('os') / require('io') must be rejected,
    but require('json') / require('log') must NOT be."""

    @pytest.mark.parametrize("bad_variant", [
        'require("os").execute("id")',
        "require('os').execute('id')",
        'require( "io" ).popen("ls")',
        "require('package').loadlib('x','y')",
        "require('debug').sethook(function() end, 'l')",
    ])
    def test_require_dangerous_module_rejected(self, bad_variant):
        src = f"function processEvent(e) {bad_variant}; return e end"
        result = lint_script(src, context="lv3")
        assert result.has_hard_reject, f"Finding #3: lint passed require bypass: {bad_variant!r}"

    @pytest.mark.parametrize("safe_require", [
        'require("json")',
        "require('log')",
        'local j = require("json")',
        "local l = require( 'log' )",
    ])
    def test_require_safe_module_allowed(self, safe_require):
        """require('json') / require('log') must still be allowed — they're in the
        lv3 injected globals."""
        src = f"function processEvent(e) local _ = {safe_require}; return e end"
        result = lint_script(src, context="lv3")
        assert not result.has_hard_reject, f"Finding #3 false positive: blocked safe require: {safe_require!r}"


class TestW4LoadPrimitive:
    """W4: Lua 5.4 `load(...)` is the dynamic-code primitive that succeeds the
    deprecated `loadstring(...)`. It must be hard-rejected just like its
    predecessor."""

    @pytest.mark.parametrize("bad_variant", [
        'load("os.execute(\'id\')")()',
        'load([==[ os.execute(\'id\') ]==])()',
        'load("return 1+1")',
        'load (chunk)',
        'local f = load("print(1)")',
    ])
    def test_load_call_rejected(self, bad_variant):
        src = f"function processEvent(e) {bad_variant}; return e end"
        result = lint_script(src, context="lv3")
        assert result.has_hard_reject, f"W4: lint passed load() variant: {bad_variant!r}"

    @pytest.mark.parametrize("safe_variant", [
        "local function load_config(path) return path end",
        "local load_count = 0",
        "event.load_avg = 1.5",
        "out['load_pct'] = 99",
        "local loadable = true",
    ])
    def test_load_identifier_not_rejected(self, safe_variant):
        """W4: bare `load_*` identifiers / locals are not the primitive — only
        the call form `load(` is dangerous. Without this carve-out the regex
        would false-positive on any function/variable starting with `load`."""
        src = f"function processEvent(e) {safe_variant}; return e end"
        result = lint_script(src, context="lv3")
        assert not result.has_hard_reject, f"W4 false positive: blocked safe load_* identifier: {safe_variant!r}"


class TestW4StringDumpPrimitive:
    """W4: `string.dump` (and the subscript variant) leaks bytecode and is half
    of the load+dump round-trip sandbox bypass."""

    @pytest.mark.parametrize("bad_variant", [
        "string.dump(some_func)",
        "string . dump(fn)",
        'string["dump"](some_func)',
        "string['dump'](fn)",
        'local b = string.dump(fn)',
        'local b = string["dump"](fn)',
    ])
    def test_string_dump_rejected(self, bad_variant):
        src = f"function processEvent(e) {bad_variant}; return e end"
        result = lint_script(src, context="lv3")
        assert result.has_hard_reject, f"W4: lint passed string.dump variant: {bad_variant!r}"

    @pytest.mark.parametrize("safe_variant", [
        'local s = string.format("%d", 1)',
        'local up = string.upper(name)',
        'event.dump_count = 0',          # `dump` as a field name on a different table
        'local user_dump = data',        # identifier containing "dump"
    ])
    def test_other_string_methods_allowed(self, safe_variant):
        src = f"function processEvent(e) {safe_variant}; return e end"
        result = lint_script(src, context="lv3")
        assert not result.has_hard_reject, f"W4 false positive: blocked safe string usage: {safe_variant!r}"


class TestW4ChainedSubscriptBypass:
    """W4: `_G["os"]["execute"]` / `_ENV["io"]["popen"]` — chained-subscript
    bypass that sidesteps both `os.execute` and `os["execute"]`."""

    @pytest.mark.parametrize("bad_variant", [
        '_G["os"]["execute"]("rm -rf /")',
        "_G['os']['execute']('id')",
        '_ENV["os"]["execute"]("id")',
        'tbl["os"]["execute"]("id")',                # arbitrary leading table also bad
        '_G [ "os" ] [ "execute" ]("id")',           # whitespace
        '_G["io"]["popen"]("ls")',
        '_G["package"]["loadlib"]("/lib/evil.so", "evil")',
        '_G["debug"]["sethook"](fn, "c")',
        '_ENV["io"]["popen"]("nc 1.2.3.4 443")',
    ])
    def test_chained_subscript_rejected(self, bad_variant):
        src = f"function processEvent(e) {bad_variant}; return e end"
        result = lint_script(src, context="lv3")
        assert result.has_hard_reject, f"W4: lint passed chained-subscript bypass: {bad_variant!r}"

    @pytest.mark.parametrize("safe_variant", [
        'out.user.name = "alice"',
        'event["data"]["user"] = nil',
        'local v = event["log"]["host"]',
        'event["src"]["ip"] = "1.2.3.4"',
        'out["meta"]["execute_time"] = 0',           # `execute` only as identifier text, not paired with os/io/etc.
    ])
    def test_innocuous_chained_indexing_allowed(self, safe_variant):
        src = f"function processEvent(e) {safe_variant}; return e end"
        result = lint_script(src, context="lv3")
        assert not result.has_hard_reject, f"W4 false positive: blocked innocuous chained index: {safe_variant!r}"
