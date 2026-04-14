"""Phase 6 Dispatch 1 — regression gates for cleanup fixes.

Covers:
- Fix 1: observo_client module load must not pull aiohttp/anthropic.
- Fix 2: four dead methods have been deleted from ObservoAPIClient.
- Fix 3: wrap_for_observo long-bracket string/comment tolerance.
- Fix 4: lua_linter dangerous-function whitespace tolerance + require allowlist.
"""
import sys

import pytest


class TestFix1ObservoClientLightImport:
    def test_observo_client_imports_without_aiohttp_in_minimal_venv(self):
        """observo_client must be importable without aiohttp in sys.modules."""
        for name in list(sys.modules):
            if name.startswith(("components.observo_client", "aiohttp", "anthropic")):
                del sys.modules[name]

        before = set(sys.modules.keys())
        import components.observo_client  # noqa: F401
        after = set(sys.modules.keys())

        pulled_in = after - before
        heavy_pulled = sorted(
            {
                m
                for m in pulled_in
                if m in ("aiohttp", "anthropic", "openai", "google.generativeai")
            }
        )
        assert heavy_pulled == [], (
            f"observo_client pulled in heavy deps at module load: {heavy_pulled}. "
            f"Phase 6.1 requires aiohttp + anthropic to be lazy-imported."
        )


class TestFix2DeadCodeDeleted:
    @pytest.mark.parametrize(
        "dead_name",
        [
            "_generate_optimized_config",
            "_default_pipeline_config",
            "create_optimized_pipeline",
            "batch_deploy_pipelines",
        ],
    )
    def test_dead_method_removed(self, dead_name):
        from components.observo_client import ObservoAPIClient

        assert not hasattr(ObservoAPIClient, dead_name), (
            f"Phase 6.2: {dead_name} should have been deleted as dead code"
        )


class TestFix3LongBracketStrip:
    def test_wrap_for_observo_tolerates_long_bracket_string_with_wrapper_text(self):
        from components.lua_deploy_wrapper import wrap_for_observo

        body = (
            "function processEvent(event)\n"
            "    local doc = [[function process(event, emit)]]\n"
            "    return event\n"
            "end"
        )
        wrapped = wrap_for_observo(body)
        assert "function process(event, emit)" in wrapped

    def test_wrap_for_observo_tolerates_nested_long_bracket(self):
        from components.lua_deploy_wrapper import wrap_for_observo

        body = (
            "function processEvent(event)\n"
            "    local doc = [==[function process(event, emit)]==]\n"
            "    return event\n"
            "end"
        )
        wrapped = wrap_for_observo(body)
        assert "function process(event, emit)" in wrapped

    def test_wrap_for_observo_tolerates_long_block_comment(self):
        from components.lua_deploy_wrapper import wrap_for_observo

        body = (
            "function processEvent(event)\n"
            "    --[==[ function process(event, emit) is added later ]==]\n"
            "    return event\n"
            "end"
        )
        wrapped = wrap_for_observo(body)
        assert "function process(event, emit)" in wrapped


def _dangerous_issues(result):
    return [i for i in result.get("issues", []) if i.get("rule") == "dangerous_functions"]


class TestFix4LintWhitespaceAndRequireAllowlist:
    @pytest.mark.parametrize(
        "dangerous",
        [
            "os.execute('id')",
            "os . execute('id')",
            "os  .  execute('id')",
            "io.popen('ls')",
            "io . popen('ls')",
        ],
    )
    def test_soft_lint_catches_whitespace_dot(self, dangerous):
        from components.testing_harness.lua_linter import LuaLinter

        linter = LuaLinter()
        src = f"function processEvent(event) {dangerous}; return event end"
        result = linter.lint(src)
        issues = _dangerous_issues(result)
        assert issues, (
            f"soft-lint missed dangerous call: {dangerous!r}; issues={result.get('issues')}"
        )

    @pytest.mark.parametrize(
        "safe_require",
        [
            'require("json")',
            "require('log')",
            'require( "json" )',
        ],
    )
    def test_soft_lint_allows_safe_require(self, safe_require):
        from components.testing_harness.lua_linter import LuaLinter

        linter = LuaLinter()
        src = f"function processEvent(event) local m = {safe_require}; return event end"
        result = linter.lint(src)
        bad = [
            i
            for i in _dangerous_issues(result)
            if "require" in i.get("message", "").lower()
        ]
        assert not bad, (
            f"soft-lint incorrectly flagged safe require: {safe_require!r}; bad={bad}"
        )

    @pytest.mark.parametrize(
        "dangerous_require",
        [
            'require("os")',
            "require('io')",
            'require("package")',
            "require('debug')",
        ],
    )
    def test_soft_lint_blocks_dangerous_require(self, dangerous_require):
        from components.testing_harness.lua_linter import LuaLinter

        linter = LuaLinter()
        src = f"function processEvent(event) local m = {dangerous_require}; return event end"
        result = linter.lint(src)
        bad = [
            i
            for i in _dangerous_issues(result)
            if "require" in i.get("message", "").lower()
        ]
        assert bad, (
            f"soft-lint missed dangerous require: {dangerous_require!r}"
        )
