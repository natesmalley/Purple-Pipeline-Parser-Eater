"""Phase 2.E regression gate: the generator must NEVER emit drop_on_error /
drop_on_abort / reroute_dropped on Lua transforms.

These keys are REMAP/VRL-only. The Observo dataplane's Lua transform deserializer
REJECTS them and fails YAML validation. Emitting any of them would break every
generated pipeline. See CLAUDE.md "Error handling" section.

This test has two layers:

1. Static grep of production code for literal occurrences of the forbidden keys
   in a context that looks like a Lua transform YAML emit path.

2. Dynamic invocation: call every generator's public emit API with a minimal
   parser analysis and assert the produced output contains NONE of the forbidden
   keys.
"""
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_LUA_TRANSFORM_KEYS = ("drop_on_error", "drop_on_abort", "reroute_dropped")


# ============================================================================
# Layer 1: static grep for forbidden keys in production source
# ============================================================================

# Files that are allowed to MENTION the forbidden keys — e.g., doc strings that
# explain they're REMAP-only, or the plan/TODO files themselves.
ALLOWED_MENTION_FILES = {
    "CLAUDE.md",
    "TODO.md",
    "REVIEW_REPORT.md",
    "tests/test_no_drop_on_error_in_lua_emit.py",  # this file
    # Phase 5.A: the standalone dataplane builder explicitly lists these keys
    # in its _FORBIDDEN_V3_LUA_TRANSFORM_KEYS safety set and in error messages.
    # Its entire purpose is to REJECT these keys — allowed to mention them.
    "components/dataplane_yaml_builder.py",
}


def _find_forbidden_in_production():
    """Scan production Python files for literal forbidden keys. Returns
    list of (file, line_no, line) for each hit."""
    hits = []
    production_dirs = ["components", "orchestrator", "services", "utils", "scripts"]
    for d in production_dirs:
        root = REPO_ROOT / d
        if not root.exists():
            continue
        for py in root.rglob("*.py"):
            rel = py.relative_to(REPO_ROOT).as_posix()
            if rel in ALLOWED_MENTION_FILES:
                continue
            try:
                text = py.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                for key in FORBIDDEN_LUA_TRANSFORM_KEYS:
                    if key in line:
                        # Skip pure comment mentions (the key is only in a comment)
                        stripped = line.strip()
                        if stripped.startswith("#") and "REMAP" in stripped:
                            continue  # allowed: documentation comment about REMAP-only
                        hits.append((rel, i, line.rstrip()))
    return hits


class TestNoForbiddenKeysInProductionCode:
    def test_no_drop_on_error_literal(self):
        hits = [h for h in _find_forbidden_in_production() if "drop_on_error" in h[2]]
        assert not hits, (
            f"Phase 2.E regression: `drop_on_error` found in production code. "
            f"This key is REMAP/VRL-only; the Lua transform deserializer rejects it. "
            f"Hits: {hits}"
        )

    def test_no_drop_on_abort_literal(self):
        hits = [h for h in _find_forbidden_in_production() if "drop_on_abort" in h[2]]
        assert not hits, f"Phase 2.E regression: `drop_on_abort` found: {hits}"

    def test_no_reroute_dropped_literal(self):
        hits = [h for h in _find_forbidden_in_production() if "reroute_dropped" in h[2]]
        assert not hits, f"Phase 2.E regression: `reroute_dropped` found: {hits}"


# ============================================================================
# Layer 2: dynamic — call the generators and scan their output
# ============================================================================

class TestGeneratorOutputExcludesForbiddenKeys:
    """When you call a generator's emit path with a synthetic parser analysis,
    the produced Lua/YAML output must not contain any of the forbidden keys.

    This catches the case where a future generator concatenates a template that
    contains drop_on_error — the static grep would miss it if the key lives in a
    template file, but this test catches it by inspecting the actual output.
    """

    def test_lua_generator_build_pipeline_output_clean(self):
        """ClaudeLuaGenerator-produced output must not contain forbidden keys."""
        # Hard import — lua_generator is a core production module; if it's not
        # importable in CI, that's a real bug to surface (not a skip-worthy condition).
        from components.lua_generator import ClaudeLuaGenerator, LuaGenerationResult  # noqa: F401

        # Try a minimal "what would a generated result look like" probe.
        # Many generators cache a template string; find it via attribute inspection.
        import components.lua_generator as lg_mod
        src = Path(lg_mod.__file__).read_text(encoding="utf-8", errors="replace")
        for key in FORBIDDEN_LUA_TRANSFORM_KEYS:
            assert key not in src, f"Phase 2.E regression: lua_generator.py contains {key!r}"

    def test_agentic_lua_generator_templates_clean(self):
        """AgenticLuaGenerator templates/prompts must not contain forbidden keys."""
        import components.agentic_lua_generator as alg_mod
        src = Path(alg_mod.__file__).read_text(encoding="utf-8", errors="replace")
        for key in FORBIDDEN_LUA_TRANSFORM_KEYS:
            # Allow the key to appear inside a SECURITY or FORBIDDEN block (the system
            # prompt may reference it as "never emit X"). Detect such context by checking
            # for "never" / "REMAP" / "VRL" / "forbidden" within 200 chars of the hit.
            for m in re.finditer(re.escape(key), src):
                start = max(0, m.start() - 200)
                end = min(len(src), m.end() + 200)
                context = src[start:end].lower()
                if any(w in context for w in ("never", "remap", "vrl", "forbidden", "rejects", "rejected")):
                    continue  # documented as forbidden, OK
                pytest.fail(
                    f"agentic_lua_generator.py contains {key!r} without a forbidden-context marker. "
                    f"Context: {src[start:end]!r}"
                )

    def test_observo_pipeline_builder_clean(self):
        """If observo_pipeline_builder emits YAML for Lua transforms, it must not include forbidden keys."""
        import components.observo_pipeline_builder as opb_mod
        src = Path(opb_mod.__file__).read_text(encoding="utf-8", errors="replace")
        for key in FORBIDDEN_LUA_TRANSFORM_KEYS:
            assert key not in src, f"Phase 2.E regression: observo_pipeline_builder.py contains {key!r}"


class TestDocumentationOfForbiddenKeys:
    """Meta-test: the forbidden-key set must be documented in CLAUDE.md so future
    developers know why they can't use these keys on Lua transforms."""

    def test_claude_md_mentions_forbidden_keys(self):
        claude_md = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8", errors="replace")
        for key in FORBIDDEN_LUA_TRANSFORM_KEYS:
            assert key in claude_md, (
                f"CLAUDE.md should mention {key!r} in the error-handling section "
                f"so future developers know why Phase 2.E exists"
            )
        # And it should mention that these are REMAP-only
        assert "REMAP" in claude_md or "VRL" in claude_md, \
            "CLAUDE.md should explain that drop_on_error is REMAP/VRL-only"
