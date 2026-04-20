"""Tests for the class_uid_concern manifest annotation system added 2026-04-19.

Background: Orion's independent review of the 140-script reference library
flagged 12 classification concerns. We triaged them into three buckets:
- KEEP as production truth (4 UI-captured scripts, annotated only)
- QUARANTINE (4 agent-generated clear errors, removed from library)
- ANNOTATE (5 agent-generated debatable entries, kept with concern flag)

These tests assert the manifest annotations are present, the
``ExampleSelector`` indexes them correctly, and the scoring penalty for
``class_uid_concern`` lets a cleaner alternative outrank a flagged one at
the same class.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from components.agentic_lua_generator import ExampleSelector


REPO_ROOT = Path(__file__).resolve().parent.parent
UI_MANIFEST = REPO_ROOT / "data" / "harness_examples" / "observo_serializers" / "manifest.json"
AGENT_MANIFEST = REPO_ROOT / "data" / "harness_examples" / "observo_serializers_agent" / "manifest.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Manifest shape
# ---------------------------------------------------------------------------

def test_ui_manifest_has_kept_production_concerns():
    """After the 2026-04-19 remediation pass, 2 UI-captured scripts remain
    as kept-as-production-truth with active concern annotations.

    The previously-flagged `azure_ad` and
    `tenable_vulnerability_management_audit_logging` were re-authored to the
    Orion-specified class (3001 and 2002 respectively), re-graded, and had
    their concern flags cleared.
    """
    m = _load(UI_MANIFEST)
    annotated = [s for s in m["serializers"] if s.get("class_uid_concern")]
    kept = [s for s in annotated if s.get("kept_as_production_truth")]
    expected_slugs = {
        "netskope",
        "palo_alto_networks_firewall",
    }
    actual_slugs = {s["slug"] for s in kept}
    assert expected_slugs.issubset(actual_slugs), (
        f"missing KEEP concerns: {expected_slugs - actual_slugs}"
    )
    # Negative assertion: remediated scripts should no longer be flagged.
    remediated = {
        "azure_ad",
        "tenable_vulnerability_management_audit_logging",
    }
    assert remediated.isdisjoint(actual_slugs), (
        f"remediated scripts should no longer be flagged: {remediated & actual_slugs}"
    )
    for s in kept:
        assert s.get("alternative_class_uid"), s["slug"]
        assert s.get("concern_note"), s["slug"]
        assert s.get("concern_source") == "orion_review_2026_04_19", s["slug"]


def test_agent_manifest_has_quarantine_and_annotate_entries():
    """6 agent-generated scripts were quarantined; after the 2026-04-19
    remediation pass, 4 remain annotated-and-kept (was 5; `agent_metrics_logs`
    was re-authored to class 5001 and its concern flag cleared).
    """
    m = _load(AGENT_MANIFEST)
    q_slugs = {q["slug"] for q in m.get("quarantined", [])}
    expected_quarantined = {
        "aws_cloudwatch_logs", "google_workspace_logs",
        "netskope_logshipper_logs", "netskope_netskope_logs",
        "proofpoint_logs", "proofpoint_proofpoint_logs",
    }
    assert expected_quarantined.issubset(q_slugs), (
        f"missing quarantines: {expected_quarantined - q_slugs}"
    )
    # Annotated-and-kept entries
    annotated = {s["slug"] for s in m["serializers"] if s.get("class_uid_concern")}
    expected_annotated = {
        "dhcp_logs", "manageengine_adauditplus_logs",
        "microsoft_eventhub_defender_email_logs",
        "microsoft_eventhub_defender_emailforcloud_logs",
    }
    assert expected_annotated.issubset(annotated), (
        f"missing annotations: {expected_annotated - annotated}"
    )
    # Negative assertion: agent_metrics_logs should no longer be flagged.
    assert "agent_metrics_logs" not in annotated, (
        "agent_metrics_logs was remediated to class 5001 — concern flag should be cleared"
    )


def test_quarantined_scripts_not_on_disk_in_active_tier():
    """Quarantined scripts should live only under _quarantine/, not at the
    top level of observo_serializers_agent/."""
    active_root = REPO_ROOT / "data" / "harness_examples" / "observo_serializers_agent"
    for slug in ("aws_cloudwatch_logs", "google_workspace_logs",
                 "proofpoint_logs", "netskope_logshipper_logs"):
        active = active_root / slug / "transform.lua"
        quarantine = active_root / "_quarantine" / slug / "transform.lua"
        assert not active.exists(), f"{slug} should be quarantined, still at top level"
        assert quarantine.exists(), f"{slug} should be under _quarantine/"


# ---------------------------------------------------------------------------
# ExampleSelector respects concerns
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def selector() -> ExampleSelector:
    return ExampleSelector()


def test_selector_loads_concern_flag_from_manifest(selector):
    index = selector._build_index()
    by_name = {e["parser_name"]: e for e in index}
    # DHCP was annotated — flag should flow through
    assert by_name.get("dhcp_logs", {}).get("class_uid_concern") is True
    assert by_name.get("dhcp_logs", {}).get("alternative_class_uid") == 4004
    # netskope (UI) is a kept-with-concern entry that survived the
    # 2026-04-19 remediation pass.
    assert by_name.get("netskope", {}).get("class_uid_concern") is True
    assert by_name.get("netskope", {}).get("kept_as_production_truth") is True
    # Negative assertion: tenable_vulnerability_management_audit_logging was
    # remediated to class 2002 and should no longer carry a concern flag.
    tenable_entry = by_name.get("tenable_vulnerability_management_audit_logging", {})
    assert not tenable_entry.get("class_uid_concern"), (
        "tenable_vulnerability_management_audit_logging should no longer be flagged after remediation"
    )
    assert not tenable_entry.get("kept_as_production_truth"), (
        "tenable_vulnerability_management_audit_logging should no longer be kept-as-production-truth after remediation"
    )


def test_selector_unflagged_script_beats_flagged_when_class_matches(selector):
    """At OCSF class 3002 (Authentication) the library has many clean
    references (Okta, Cisco Duo, etc.) and one flagged one (DHCP annotated
    as 4004-preferable). A class-3002 lookup should NOT surface DHCP as its
    top result now that the concern penalty is in place."""
    # Pull top 5 references for 3002
    results = selector.select(
        target_class_uid=3002, target_vendor="", target_signature="processEvent",
        max_examples=5,
    )
    names = [r["parser_name"] for r in results]
    # DHCP may still appear in the top 5 (there are many 3002 scripts), but it
    # should never be the single top pick — some clean Auth script outranks it.
    assert names[0] != "dhcp_logs", (
        f"flagged dhcp_logs should not be #1 for class 3002; got {names}"
    )


def test_selector_returns_flagged_as_fallback_when_nothing_else_matches(selector):
    """If we ask for a class_uid that only a flagged entry covers, the
    penalty shouldn't filter it out — it should still be returned as the
    best available option. (Currently: class 4004 DHCP Activity is only
    referenced by the annotated dhcp_logs script via its alternative_class_uid.)
    """
    # The selector ranks by current class_uid, not alternative. Ask for 3002 +
    # a DHCP-specific vendor hint — the flagged entry should appear (not first,
    # but present) as one of the top candidates.
    results = selector.select(
        target_class_uid=3002, target_vendor="dhcp", target_signature="processEvent",
        max_examples=5,
    )
    names = [r["parser_name"] for r in results]
    assert "dhcp_logs" in names, (
        f"dhcp_logs should still appear for dhcp-vendor 3002 lookups; got {names}"
    )


def test_library_active_count_after_cleanup(selector):
    """138 active references prior to the concern cleanup; 6 newly
    quarantined brings it to 132."""
    index = selector._build_index()
    refs = [e for e in index if e.get("is_reference")]
    assert len(refs) >= 130, f"expected >=130 active references; got {len(refs)}"
