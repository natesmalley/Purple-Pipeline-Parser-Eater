from pathlib import Path
import importlib

from components.testing_harness.jarvis_event_bridge import JarvisEventBridge


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
