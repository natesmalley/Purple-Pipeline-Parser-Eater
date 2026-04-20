"""Milestone A: canonical Observo reference library.

These tests lock in the behavior added for milestone A:

1. The ``data/harness_examples/observo_serializers/`` fixtures are present and
   every script uses the canonical ``processEvent(event)`` contract.
2. ``ExampleSelector`` indexes them with ``is_reference=True`` and prioritizes
   them over historical ``output/*/transform.lua`` entries.
3. ``build_generation_prompt`` renders a ``REFERENCE IMPLEMENTATION`` block
   when given reference implementations, and omits it otherwise.

These are deterministic, offline tests — no LLM calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from components.agentic_lua_generator import (
    ExampleSelector,
    build_generation_prompt,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = REPO_ROOT / "data" / "harness_examples" / "observo_serializers"
MANIFEST_PATH = FIXTURE_ROOT / "manifest.json"


# ---------------------------------------------------------------------------
# Fixture presence and shape
# ---------------------------------------------------------------------------

def _load_manifest() -> dict:
    assert MANIFEST_PATH.exists(), f"missing manifest at {MANIFEST_PATH}"
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_present_and_well_formed():
    manifest = _load_manifest()
    assert manifest.get("contract") == "processEvent(event)"
    entries = manifest.get("serializers") or []
    assert len(entries) >= 18, "expected at least 18 serializer entries"
    # Every entry has the keys we rely on.
    required_keys = {"display_name", "slug", "has_lua"}
    for entry in entries:
        missing = required_keys - set(entry)
        assert not missing, f"entry {entry.get('display_name')!r} missing {missing}"


def test_every_lua_fixture_on_disk_and_uses_process_event():
    manifest = _load_manifest()
    lua_entries = [e for e in manifest["serializers"] if e.get("has_lua")]
    # 18 from standard OCSF Serializer + 1 new from OCSF Serializer Extended
    # (Palo Alto Networks Firewall). The remaining Lua-named entries in the
    # Extended template are byte-identical duplicates of the standard set.
    assert len(lua_entries) >= 18, (
        f"expected at least 18 scripts with Lua; got {len(lua_entries)}"
    )
    for entry in lua_entries:
        lua_path = FIXTURE_ROOT / entry["slug"] / "transform.lua"
        assert lua_path.exists(), f"missing fixture: {lua_path}"
        code = lua_path.read_text(encoding="utf-8")
        assert "function processEvent" in code, (
            f"fixture {entry['slug']} does not use processEvent contract"
        )
        assert len(code) > 500, (
            f"fixture {entry['slug']} suspiciously short: {len(code)} chars"
        )


# ---------------------------------------------------------------------------
# ExampleSelector: reference indexing and prioritization
# ---------------------------------------------------------------------------

def test_selector_indexes_observo_references_as_reference():
    selector = ExampleSelector()
    index = selector._build_index()
    reference_entries = [e for e in index if e.get("is_reference")]
    # 18 from standard OCSF Serializer + 1 from OCSF Serializer Extended.
    assert len(reference_entries) >= 19, (
        f"expected >=19 reference entries, got {len(reference_entries)}"
    )
    # All references should be from the canonical fixture directory.
    for entry in reference_entries:
        assert "observo_serializers" in entry["path"], entry["path"]


def test_selector_picks_palo_alto_firewall_reference():
    """The PAN Firewall script was imported from the Extended template on
    2026-04-19. Its class_uid is 99602001 (SentinelOne extended OCSF)."""
    selector = ExampleSelector()
    results = selector.select(
        target_class_uid=99602001,
        target_vendor="palo_alto",
        target_signature="processEvent",
        max_examples=1,
    )
    assert results, "expected PAN Firewall to be selectable"
    assert results[0]["parser_name"] == "palo_alto_networks_firewall"
    assert results[0]["class_uid"] == 99602001


def test_selector_picks_authentication_reference_for_cisco_duo():
    selector = ExampleSelector()
    results = selector.select(
        target_class_uid=3002,
        target_vendor="cisco",
        target_signature="processEvent",
        max_examples=1,
    )
    assert results, "expected at least one reference for 3002/cisco"
    top = results[0]
    assert top["parser_name"] == "cisco_duo"
    assert top.get("is_reference") is True


def test_selector_picks_api_activity_reference_for_azure():
    selector = ExampleSelector()
    results = selector.select(
        target_class_uid=6003,
        target_vendor="azure",
        target_signature="processEvent",
        max_examples=1,
    )
    assert results, "expected at least one reference for 6003/azure"
    assert results[0]["parser_name"] == "azure_platform"


def test_selector_truncates_long_reference_code():
    selector = ExampleSelector()
    results = selector.select(
        target_class_uid=3002,
        target_vendor="okta",
        target_signature="processEvent",
        max_examples=1,
    )
    assert results
    # Okta is ~1500 lines — selector truncates to 150.
    lines = results[0]["code"].splitlines()
    assert len(lines) <= 151  # 150 + one truncation marker line


def test_selector_returns_empty_when_no_references_and_no_output(tmp_path: Path):
    selector = ExampleSelector(output_dir=tmp_path, reference_dirs=[])
    assert selector.select(target_class_uid=3002) == []


# ---------------------------------------------------------------------------
# build_generation_prompt: reference section rendering
# ---------------------------------------------------------------------------

_DUMMY_REF = {
    "parser_name": "example_ref",
    "class_uid": 3002,
    "signature": "processEvent",
    "code": "-- dummy reference\nfunction processEvent(event)\n  return event\nend",
}


def _make_prompt(**overrides):
    kwargs = dict(
        parser_name="my_test",
        vendor="acme",
        product="widget",
        declared_log_type="",
        declared_log_detail="",
        class_uid=3002,
        class_name="Authentication",
        ocsf_fields={"required_fields": ["class_uid", "time"], "optional_fields": []},
        source_fields=[],
        ingestion_mode="log",
        examples=[],
        reference_implementations=None,
    )
    kwargs.update(overrides)
    return build_generation_prompt(**kwargs)


def test_prompt_includes_reference_section_when_refs_given():
    prompt = _make_prompt(reference_implementations=[_DUMMY_REF])
    assert "REFERENCE IMPLEMENTATION" in prompt
    assert "Reference parser: example_ref" in prompt
    assert "-- dummy reference" in prompt
    # Guard against accidental "copy the reference verbatim" behavior.
    assert "match style, not content" in prompt


def test_prompt_omits_reference_section_when_no_refs():
    prompt = _make_prompt(reference_implementations=None)
    assert "REFERENCE IMPLEMENTATION" not in prompt

    prompt_empty = _make_prompt(reference_implementations=[])
    assert "REFERENCE IMPLEMENTATION" not in prompt_empty


def test_prompt_only_includes_top_reference_even_if_many_supplied():
    refs = [
        {**_DUMMY_REF, "parser_name": "first", "code": "-- FIRST_REF"},
        {**_DUMMY_REF, "parser_name": "second", "code": "-- SECOND_REF"},
        {**_DUMMY_REF, "parser_name": "third", "code": "-- THIRD_REF"},
    ]
    prompt = _make_prompt(reference_implementations=refs)
    assert "FIRST_REF" in prompt
    assert "SECOND_REF" not in prompt
    assert "THIRD_REF" not in prompt
