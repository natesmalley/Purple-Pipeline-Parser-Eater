"""Phase 2.A regression test — every emit site must feed through wrap_for_observo.

If a new emit site is added without going through the wrapper, this test fails.
"""
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Files that are ALLOWED to write/build raw Lua without the wrapper:
# - The wrapper itself (defines it)
# - Run-time wrap sites: transform_executor / dataplane_validator compose the
#   outer 'process(event, emit)' wrapper in YAML source via dofile, so they
#   intentionally write the raw processEvent body to transform.lua.
# - Linter / harness core that consume lua as strings for parsing only
# - observo_lua_templates.py: dead code pending 3.G deletion
EXEMPT_FILES = {
    "components/lua_deploy_wrapper.py",
    "components/testing_harness/dual_execution_engine.py",
    "components/testing_harness/lua_linter.py",
    "components/testing_harness/harness_orchestrator.py",
    "components/observo_lua_templates.py",
    "components/dataplane_validator.py",  # run-time wrap, not deploy emit
    "components/transform_executor.py",   # run-time wrap, not deploy emit
    # web_ui/routes.py — consumes already-wrapped lua from generators and
    # forwards to deploy callers; wraps are performed upstream in the
    # generators. Exempted to avoid double-wrap.
    "components/web_ui/routes.py",
    # parser_workbench.py — delegates to build_lua_content (lua_exporter) which
    # is wrapped, or to the agentic generator which is wrapped. Does not author
    # raw Lua itself.
    "components/web_ui/parser_workbench.py",
    # rag_assistant.py — constructs LuaGenerationResult from ClaudeLuaGenerator
    # response; wraps upstream are enforced in lua_generator.py.
    "components/rag_assistant.py",
    # parser_output_manager.save_lua_transform — receives already-wrapped
    # lua_code from callers. Re-wrapping would trip idempotence.
    "components/parser_output_manager.py",
}


def test_emit_sites_import_wrap_for_observo():
    """Every file that builds/writes Lua (outside exempt list) MUST import wrap_for_observo."""
    candidates = []
    components_root = REPO_ROOT / "components"
    for root, _, files in os.walk(components_root):
        for f in files:
            if not f.endswith(".py"):
                continue
            p = Path(root) / f
            rel = p.relative_to(REPO_ROOT).as_posix()
            if rel in EXEMPT_FILES:
                continue
            src = p.read_text(encoding="utf-8", errors="replace")
            # Heuristic: files that assign/return a named lua_code or write .lua files
            if re.search(r'lua_code\s*=(?!=)|\.lua["\']\s*,?\s*["\']w', src):
                candidates.append(rel)

    missing = []
    for rel in candidates:
        src = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
        if "wrap_for_observo" not in src:
            missing.append(rel)

    assert not missing, (
        f"These emit sites build/write Lua but don't import wrap_for_observo: {missing}. "
        "Per Phase 2.A, every emit path must wrap through components.lua_deploy_wrapper."
    )
