"""W2 — gate tests for the three parser_workbench Lua persistence sites.

Sites covered:
- ParserLuaWorkbench.build_parser (deterministic build_lua_content path) —
  invoked with a build_lua_content stub that returns a 45-byte identity
  passthrough.
- ParserLuaWorkbench.build_parser_with_agent (agent write site) — invoked
  with a fake agent returning a 45-byte body and a low harness score.
- ParserLuaWorkbench.build_from_raw_examples (sibling agent write site) —
  same fake agent shape.

Each test asserts:
- accepted == False
- rejection_reason matches the expected helper reason
- no Lua file landed in tmp_path / output / parser_lua_serializers
"""

from __future__ import annotations

from pathlib import Path

import pytest

from components.web_ui.parser_workbench import ParserLuaWorkbench


_IDENTITY_PASSTHROUGH = "function processEvent(event) return event end"


def _no_lua_files_written(tmp_path: Path) -> None:
    lua_root = tmp_path / "output" / "parser_lua_serializers"
    if lua_root.exists():
        files = list(lua_root.rglob("*.lua"))
        assert not files, f"No Lua file should have landed; found: {files}"


def test_build_parser_rejects_identity_passthrough(monkeypatch, tmp_path: Path):
    """Deterministic build_parser path: harness_report=None gate must still
    reject the 45-byte identity passthrough on length / identity grounds."""
    wb = ParserLuaWorkbench(repo_root=tmp_path)

    monkeypatch.setattr(
        wb,
        "_find_entry",
        lambda parser_name: {"parser_name": parser_name, "ingestion_mode": "push"},
    )
    monkeypatch.setattr(
        wb,
        "_example_log_with_provenance",
        lambda entry: {
            "example_log": "{}",
            "sample_provenance": {"source": "fallback"},
        },
    )
    monkeypatch.setattr(
        "components.web_ui.parser_workbench.build_lua_content",
        lambda entry: {
            "content": _IDENTITY_PASSTHROUGH,
            "source_kind": "generated",
        },
    )

    result = wb.build_parser("example_parser")

    assert result is not None
    assert result.get("accepted") is False
    # The size gate fires first because the body is 45 bytes.
    assert result.get("rejection_reason") in (
        "too_short",
        "identity_passthrough",
    )
    assert result.get("lua_file") is None
    assert result.get("lua_code") is None
    _no_lua_files_written(tmp_path)


def test_build_parser_with_agent_rejects_identity_passthrough(monkeypatch, tmp_path: Path):
    """Agent write site (line 406-ish): 45-byte body must be rejected."""
    wb = ParserLuaWorkbench(repo_root=tmp_path)

    monkeypatch.setattr(
        wb,
        "_find_entry",
        lambda parser_name: {"parser_name": parser_name, "ingestion_mode": "push"},
    )
    monkeypatch.setattr(
        wb,
        "_example_log_with_provenance",
        lambda entry: {
            "example_log": "{}",
            "sample_provenance": {"source": "fallback"},
        },
    )

    class FakeAgent:
        def generate(self, entry, force_regenerate=False):
            return {
                "lua_code": _IDENTITY_PASSTHROUGH,
                "ingestion_mode": "push",
                "confidence_score": 30,
                "confidence_grade": "F",
                "harness_report": {"confidence_score": 30},
            }

    monkeypatch.setattr(wb, "_get_agent", lambda: FakeAgent())

    result = wb.build_parser_with_agent("example_parser")

    assert result is not None
    assert result.get("accepted") is False
    assert result.get("rejection_reason") in (
        "too_short",
        "identity_passthrough",
        "low_confidence_score",
    )
    assert result.get("lua_file") is None
    assert result.get("lua_code") is None
    _no_lua_files_written(tmp_path)


def test_build_from_raw_examples_rejects_identity_passthrough(monkeypatch, tmp_path: Path):
    """Sibling agent write site (line 499-ish): same rejection contract."""
    wb = ParserLuaWorkbench(repo_root=tmp_path)

    class FakeAgent:
        def generate(self, entry, force_regenerate=False):
            return {
                "lua_code": _IDENTITY_PASSTHROUGH,
                "ingestion_mode": "push",
                "confidence_score": 30,
                "confidence_grade": "F",
                "harness_report": {"confidence_score": 30},
            }

    monkeypatch.setattr(wb, "_get_agent", lambda: FakeAgent())

    result = wb.build_from_raw_examples(
        parser_name="brand_new_parser",
        raw_examples=['{"message":"a"}'],
    )

    assert result.get("accepted") is False
    assert result.get("rejection_reason") in (
        "too_short",
        "identity_passthrough",
        "low_confidence_score",
    )
    assert result.get("lua_file") is None
    assert result.get("lua_code") is None
    _no_lua_files_written(tmp_path)
