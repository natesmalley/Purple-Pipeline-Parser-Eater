from pathlib import Path
import importlib
import sys

import pytest

from components.testing_harness.jarvis_event_bridge import JarvisEventBridge


# Batch 1 Stream D fix — when any test in this module instantiates a
# JarvisEventBridge against a pytest tmp_path, the bridge inserts that
# path into sys.path and (indirectly, via _load_dynamic_events) may
# register `jarvis_event_generators*` packages in sys.modules. After
# pytest cleans up tmp_path, those sys.modules entries point at a
# deleted directory. The next unrelated test that constructs a real
# JarvisEventBridge (against docs/reference/jarvis_event_generators)
# then mis-resolves imports, silently returning the wrong event shape.
#
# test_parser_workbench.py::test_example_log_cloudflare_waf_is_domain_
# specific was the reproducer: it expected RayID/WAFAction in the
# cloudflare_waf sample but got an unrelated event because Python's
# import machinery resolved the stale package cache first.
#
# This autouse fixture snapshots sys.path and sys.modules before every
# test in this module and restores them afterward. Strict enough to
# prevent the specific pollution, narrow enough not to slow the suite.
@pytest.fixture(autouse=True)
def _restore_import_state():
    path_snapshot = list(sys.path)
    module_snapshot = set(sys.modules.keys())
    try:
        yield
    finally:
        # Restore sys.path exactly.
        sys.path[:] = path_snapshot
        # Purge any modules added during the test. This catches the
        # stale jarvis_event_generators.* entries registered by
        # _load_dynamic_events against tmp_path.
        added = set(sys.modules.keys()) - module_snapshot
        for name in added:
            sys.modules.pop(name, None)


def test_resolve_generator_exact_for_latest_suffix(tmp_path: Path):
    bridge = JarvisEventBridge(jarvis_root=tmp_path)

    resolved = bridge.resolve_generator("cisco_asa_logs-latest")

    assert resolved["match_type"] == "exact"
    assert resolved["source"] == "static"
    assert resolved["generator_key"] == "cisco_asa"


def test_resolve_generator_alias_from_parser_family(tmp_path: Path):
    bridge = JarvisEventBridge(jarvis_root=tmp_path)

    resolved = bridge.resolve_generator("okta_logs-latest")

    assert resolved["match_type"] == "alias"
    assert resolved["generator_key"]


def test_resolve_generator_none_for_unknown_parser(tmp_path: Path):
    bridge = JarvisEventBridge(jarvis_root=tmp_path)

    resolved = bridge.resolve_generator("nonexistent_vendor_super_parser")

    assert resolved["match_type"] == "none"
    assert resolved["generator_key"] == ""


def test_dynamic_import_compat_for_pep604_annotations(tmp_path: Path, monkeypatch):
    jarvis_root = tmp_path / "jarvis_event_generators"
    mod_dir = jarvis_root / "web_security"
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / "cloudflare_waf.py").write_text(
        "def cloudflare_waf_log(overrides: dict | None = None) -> str:\n"
        "    return 'compat-ok'\n",
        encoding="utf-8",
    )

    bridge = JarvisEventBridge(jarvis_root=jarvis_root)

    original_import = importlib.import_module

    def fake_import(module_name: str):
        if module_name.endswith("web_security.cloudflare_waf"):
            raise TypeError("unsupported operand type(s) for |: 'type' and 'NoneType'")
        return original_import(module_name)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    events = bridge._load_dynamic_events("web_security.cloudflare_waf", "cloudflare_waf", 1)

    assert events == ["compat-ok"]
