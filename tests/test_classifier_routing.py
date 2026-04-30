"""W3 (2026-04-29): regression test for OCSF classifier routing fixes.

Covers the keyword-table changes in components/agentic_lua_generator.py:
- Vuln scanners (snyk/tenable/qualys/nessus/inspector/rapid7) → 2002
- Account/audit parsers (manageengine_adauditplus, passwd_change_audit) → 3001
- Inventory parsers (cisco_asa_inventory, windows_endpoint_assets) → 5001
- EDR/Detection (crowdstrike_alerts, defender_finding, generic_finding) → 2004
- "finding" lives ONLY on 2004
- Negative case: unmatched parser names route to existing buckets, NOT
  silently to 2002/3001/5001 via stray keyword overlap

W3 DA round (2026-04-29) additions:
- Akamai SiteDefender (CDN/WAF, manifest 4002) MUST NOT route to 2004 —
  the bare `defender` keyword was replaced by `microsoft_defender` +
  `defender_for_endpoint` so SiteDefender no longer collides with EDR.
- Documented intentional reroutes: `axonius_asset_logs` (manifest 4001)
  → 5001, `managedengine_ad_audit_plus` (manifest 3002) → 3001. Both
  are accuracy improvements per OCSF-1.3 mapping conventions.
- Manifest-pinning sweep: every non-concern-flagged entry in both
  `observo_serializers/manifest.json` and
  `observo_serializers_agent/manifest.json` is checked against
  `classify_ocsf_class` so future keyword-table reorders fail loudly.

Plus: 4004 (DHCP Activity) and 4009 (Email Activity) load from the
schema registry — both back manifest `alternative_class_uid` references.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, Tuple

import pytest

from components.agentic_lua_generator import OCSF_CLASS_KEYWORDS, classify_ocsf_class
from components.testing_harness.ocsf_schema_registry import OCSFSchemaRegistry


REPO_ROOT = Path(__file__).resolve().parent.parent
UI_MANIFEST = REPO_ROOT / "data" / "harness_examples" / "observo_serializers" / "manifest.json"
AGENT_MANIFEST = REPO_ROOT / "data" / "harness_examples" / "observo_serializers_agent" / "manifest.json"

# Slugs whose classifier output is governed by per-test assertions elsewhere
# in this file. The manifest-pinning sweep skips them so explicit
# documented routing decisions don't show up twice (once as a documented
# reroute, once as a manifest mismatch).
_DOCUMENTED_REROUTES_TO_SKIP_FROM_PIN: set[str] = {
    # Manifest declares 4001 — W3 reroutes to 5001 (more specific OCSF
    # mapping for asset-inventory products). Locked below.
    "axonius_asset_logs",
    # Manifest declares 3002 — W3 reroutes to 3001 (Account Change is the
    # correct OCSF mapping for AD audit events). Locked below.
    "managedengine_ad_audit_plus",
}


# Pre-existing classifier limitations — these slugs were ALREADY mismatched
# before W3 because no keyword in `OCSF_CLASS_KEYWORDS` covers their
# vendor/product names. Listed explicitly so:
#   1. The manifest-pinning sweep does not fail on them (W3 did not cause
#      these mismatches; they predate the audit fix).
#   2. Future keyword additions that finally cover them are caught — once
#      a slug starts routing to its manifest class_uid, removing it from
#      this set will surface as a passing test.
# NOTE: this list is intentionally short. Do not add to it without
# confirming via `git log` / `git blame` that the mismatch predates W3.
_PRE_EXISTING_CLASSIFIER_GAPS: set[str] = {
    # Azure AD (manifest 3001 Account Change) — none of the 3001 keywords
    # match `azure_ad`. Pre-W3 routed to default 4001 too.
    "azure_ad",
    # Azure platform logs (manifest 6003 API Activity) — `azure_activity`
    # keyword in 6003 does not substring-match `azure_platform`. Pre-W3
    # routed to default 4001.
    "azure_platform",
    # Proofpoint (manifest 2004 Detection Finding, email security) — no
    # keyword matches. Pre-W3 routed to default 4001.
    "proofpoint",
    # Agent metrics (manifest 5001 Device Inventory Info) — `agent`
    # matches 1007 Process; no inventory keyword matches `agent_metrics`.
    # Pre-W3 also routed to 1007.
    "agent_metrics_logs",
}


# ---------------------------------------------------------------------------
# Vuln-scanner family → 2002 Vulnerability Finding
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "parser_name",
    ["snyk", "tenable", "qualys", "nessus", "inspector", "rapid7",
     "snyk_scan", "tenable_io", "qualys_vmdr"],
)
def test_vuln_scanners_route_to_2002(parser_name: str) -> None:
    uid, _name = classify_ocsf_class(parser_name)
    assert uid == 2002, f"{parser_name} should route to 2002; got {uid}"


# ---------------------------------------------------------------------------
# Account / audit family → 3001 Account Change
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "parser_name",
    ["manageengine_adauditplus", "passwd_change_audit",
     "manageengine_adauditplus_logs", "membership_change",
     "privilege_escalation_audit"],
)
def test_account_change_parsers_route_to_3001(parser_name: str) -> None:
    uid, _name = classify_ocsf_class(parser_name)
    assert uid == 3001, f"{parser_name} should route to 3001; got {uid}"


# ---------------------------------------------------------------------------
# Inventory / asset family → 5001 Device Inventory Info
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "parser_name",
    ["cisco_asa_inventory", "windows_endpoint_assets",
     "endpoint_inventory", "asset_inventory"],
)
def test_inventory_parsers_route_to_5001(parser_name: str) -> None:
    uid, _name = classify_ocsf_class(parser_name)
    assert uid == 5001, f"{parser_name} should route to 5001; got {uid}"


# ---------------------------------------------------------------------------
# Detection / finding family → 2004 Detection Finding
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "parser_name",
    ["crowdstrike_alerts", "defender_finding", "generic_finding",
     "sentinelone_edr", "darktrace_alert"],
)
def test_edr_and_finding_parsers_route_to_2004(parser_name: str) -> None:
    uid, _name = classify_ocsf_class(parser_name)
    assert uid == 2004, f"{parser_name} should route to 2004; got {uid}"


def test_finding_keyword_lives_only_on_2004() -> None:
    """`"finding"` was moved off 2001/2002 to 2004 only. A bare-bones
    `generic_finding` parser name (single matching keyword) must therefore
    route to 2004."""
    uid, _name = classify_ocsf_class("generic_finding")
    assert uid == 2004
    # And the keyword table itself: no other class lists "finding".
    finding_classes = [
        cls_uid for cls_uid, kws in OCSF_CLASS_KEYWORDS.items() if "finding" in kws
    ]
    assert finding_classes == [2004], (
        f"'finding' should appear only on 2004; found on {finding_classes}"
    )


# ---------------------------------------------------------------------------
# Negative cases — unmatched / orthogonal names must NOT pull stray buckets
# ---------------------------------------------------------------------------

def test_akamai_dns_still_routes_to_4003() -> None:
    """Pre-W3 routing for unaffected vendor families must not regress."""
    uid, _name = classify_ocsf_class("akamai_dns")
    assert uid == 4003


@pytest.mark.parametrize(
    "parser_name,not_uid",
    [
        ("akamai_dns", 2002),
        ("akamai_dns", 3001),
        ("akamai_dns", 5001),
        ("okta_logs", 2002),
        ("cisco_duo", 2002),
        ("palo_alto_firewall", 5001),
        ("cloudflare_http", 3001),
    ],
)
def test_unmatched_parsers_do_not_silently_route_to_w3_classes(
    parser_name: str, not_uid: int
) -> None:
    """Defense in depth: an unrelated parser must not get pulled into
    2002/3001/5001 by a stray substring match (e.g. `"asa"` in
    `palo_alto_firewall` would NOT be in 5001 but earlier audits found
    similar accidental overlaps)."""
    uid, _name = classify_ocsf_class(parser_name)
    assert uid != not_uid, (
        f"{parser_name} should NOT route to {not_uid}; got {uid}"
    )


# ---------------------------------------------------------------------------
# Insertion-order contract — strict-greater scoring documented in CLAUDE.md
# ---------------------------------------------------------------------------

def test_insertion_order_2004_before_2002_before_2001() -> None:
    """The classifier uses `score > best_score` (strict-greater); on
    keyword-count ties the first-declared class wins. 2004 must appear
    before 2002 must appear before 2001 so EDR/detection beats vuln-scan
    fallthrough beats the generic 'security' bucket."""
    keys = list(OCSF_CLASS_KEYWORDS.keys())
    assert keys.index(2004) < keys.index(2002) < keys.index(2001)


# ---------------------------------------------------------------------------
# Schema registry — 4004 and 4009 are loadable
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "class_uid,expected_name",
    [(4004, "DHCP Activity"), (4009, "Email Activity")],
)
def test_4004_and_4009_loadable_from_schema_registry(
    class_uid: int, expected_name: str
) -> None:
    registry = OCSFSchemaRegistry()
    assert registry.has_class(class_uid), f"class {class_uid} missing from registry"
    cls = registry.get_class(class_uid)
    assert cls is not None
    assert cls["class_name"] == expected_name
    assert cls["category_uid"] == 4
    # Required fields mirror 4001/4002/4003 shape (base required only).
    required = registry.get_required_fields(class_uid)
    for field in ["class_uid", "category_uid", "activity_id", "time",
                  "type_uid", "severity_id"]:
        assert field in required, f"{class_uid} missing required {field}"


def test_4004_and_4009_present_in_all_schema_versions() -> None:
    """Both classes live in the v1.0 base map; the v1.1 / v1.3 overlays
    extend optional_fields without dropping classes. Each version must
    therefore expose them."""
    registry = OCSFSchemaRegistry()
    for version in ["1.0.0", "1.1.0", "1.3.0"]:
        for class_uid in (4004, 4009):
            assert registry.has_class(class_uid, version=version), (
                f"class {class_uid} missing from registry version {version}"
            )


# ---------------------------------------------------------------------------
# W3 DA round (2026-04-29): SiteDefender / Defender disambiguation
# ---------------------------------------------------------------------------

def test_akamai_sitedefender_routes_to_4002_not_2004() -> None:
    """`akamai_sitedefender` is a CDN/WAF (manifest declares 4002 HTTP
    Activity), NOT EDR. The bare `defender` keyword on 2004 was
    pre-DA-fix routing it to 2004 because `akamai_site` (4002) and
    `defender` (2004) both scored 1 and 2004 was declared first.
    Replacing `defender` with `microsoft_defender` + `defender_for_endpoint`
    fixes it: SiteDefender now scores 1 on 4002 (`akamai_site`) and 0 on
    2004."""
    uid, _name = classify_ocsf_class("akamai_sitedefender")
    assert uid == 4002, f"akamai_sitedefender should be 4002 HTTP; got {uid}"


@pytest.mark.parametrize(
    "parser_name",
    [
        "microsoft_defender_logs",
        "microsoft_defender_for_endpoint",
        "microsoft_defender_for_cloud",
        "defender_for_endpoint",
    ],
)
def test_microsoft_defender_shapes_still_route_to_2004(parser_name: str) -> None:
    """The two replacement tokens (`microsoft_defender`,
    `defender_for_endpoint`) must continue covering Microsoft Defender's
    canonical product names so the 2004 routing is preserved."""
    uid, _name = classify_ocsf_class(parser_name)
    assert uid == 2004, (
        f"{parser_name} should still route to 2004; got {uid}"
    )


def test_defender_keyword_is_not_bare_token() -> None:
    """The bare `"defender"` token must not reappear in 2004's keyword
    list — it false-matches Akamai SiteDefender. Only the two
    product-specific tokens are allowed."""
    kws_2004 = OCSF_CLASS_KEYWORDS[2004]
    assert "defender" not in kws_2004, (
        "bare 'defender' is too generic — use 'microsoft_defender' or "
        "'defender_for_endpoint'"
    )
    assert "microsoft_defender" in kws_2004
    assert "defender_for_endpoint" in kws_2004


# ---------------------------------------------------------------------------
# W3 DA round: documented intentional reroutes — locked, not silently drifting
# ---------------------------------------------------------------------------

def test_axonius_asset_logs_routes_to_5001_not_4001() -> None:
    """Axonius is a CMDB/asset-inventory product. The manifest's pre-W3
    classification was 4001 (Network Activity), but the OCSF-1.3 mapping
    for asset inventory is 5001 (Device Inventory Info). W3 reclassifies
    this as a documented accuracy improvement; this test locks the new
    routing."""
    uid, _name = classify_ocsf_class("axonius_asset_logs")
    assert uid == 5001, f"axonius_asset_logs should be 5001; got {uid}"


def test_managedengine_ad_audit_plus_routes_to_3001_not_3002() -> None:
    """ManageEngine ADAuditPlus emits AD account-change audit events
    (group membership, privilege changes, password resets), which OCSF
    maps to 3001 Account Change rather than 3002 Authentication. W3
    moved `ad_audit` from 3002 to 3001 and added the explicit
    `manageengine_adauditplus` token to 3001. This is a deliberate
    accuracy improvement; this test locks the new routing."""
    uid, _name = classify_ocsf_class("managedengine_ad_audit_plus")
    assert uid == 3001, f"managedengine_ad_audit_plus should be 3001; got {uid}"


# ---------------------------------------------------------------------------
# W3 DA round: manifest-pinning sweep
# ---------------------------------------------------------------------------

def _iter_manifest_entries(
    path: Path,
) -> Iterator[Tuple[str, int, "int | None", bool]]:
    """Yield (slug, class_uid, alternative_class_uid, class_uid_concern)
    for every entry in the given manifest. The manifest may declare its
    canonical entries under either ``serializers`` (both files) plus an
    optional ``quarantined`` list (agent manifest only). Quarantined
    entries are excluded from the sweep — they are not in the active
    library and the classifier is not expected to align with them."""
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for entry in manifest.get("serializers", []):
        slug = entry.get("slug", "")
        class_uid = entry.get("class_uid")
        if not slug or class_uid is None:
            continue
        yield (
            slug,
            int(class_uid),
            entry.get("alternative_class_uid"),
            bool(entry.get("class_uid_concern", False)),
        )


def _manifest_pin_cases() -> list[tuple[str, str, int, "int | None"]]:
    """Build the parametrize matrix: (manifest_label, slug, expected_uid,
    alternative_uid). Skips concern-flagged entries (the manifest itself
    flags them as debatable) and skips the documented-reroute slugs that
    have explicit lock-in tests above."""
    cases: list[tuple[str, str, int, "int | None"]] = []
    for label, path in [("ui", UI_MANIFEST), ("agent", AGENT_MANIFEST)]:
        if not path.exists():
            continue
        for slug, class_uid, alt_uid, concern in _iter_manifest_entries(path):
            if concern:
                continue
            if slug in _DOCUMENTED_REROUTES_TO_SKIP_FROM_PIN:
                continue
            if slug in _PRE_EXISTING_CLASSIFIER_GAPS:
                continue
            cases.append((label, slug, class_uid, alt_uid))
    return cases


_MANIFEST_PIN_CASES = _manifest_pin_cases()


@pytest.mark.parametrize(
    "manifest_label,slug,expected_uid,alternative_uid",
    _MANIFEST_PIN_CASES,
    ids=[f"{label}:{slug}" for (label, slug, *_rest) in _MANIFEST_PIN_CASES],
)
def test_manifest_pinning_sweep(
    manifest_label: str,
    slug: str,
    expected_uid: int,
    alternative_uid: "int | None",
) -> None:
    """Lock down classifier output against every non-concern-flagged
    manifest entry. Either the manifest's `class_uid` OR (if present) its
    `alternative_class_uid` is acceptable — the alternative captures
    Orion-review cases where the original was suboptimal but still
    semantically valid. A future keyword-table reorder that drifts any of
    these decisions will fail this test loudly with a clear diff."""
    uid, _name = classify_ocsf_class(slug)
    acceptable = {expected_uid}
    if alternative_uid is not None:
        acceptable.add(int(alternative_uid))
    assert uid in acceptable, (
        f"[{manifest_label}] slug={slug!r}: classifier returned {uid}, "
        f"but manifest declares {expected_uid}"
        f"{f' (alternative {alternative_uid})' if alternative_uid is not None else ''}"
    )


def test_manifest_pin_count_is_nontrivial() -> None:
    """Sanity-check that the parametrize matrix actually loaded entries —
    a near-empty matrix would silently pass and give false coverage."""
    assert len(_MANIFEST_PIN_CASES) >= 50, (
        f"manifest-pinning sweep loaded only {len(_MANIFEST_PIN_CASES)} "
        f"entries; expected >=50 (UI ~21 + agent ~105 minus concerns)"
    )


def test_pre_existing_gap_list_is_still_accurate() -> None:
    """Each slug in `_PRE_EXISTING_CLASSIFIER_GAPS` must still mismatch
    its manifest class_uid. If a future keyword addition finally covers
    one of these, the test fails and the maintainer is forced to remove
    the slug from the gap list (so the manifest-pinning sweep starts
    enforcing it). This prevents the gap list from rotting into a stale
    coverage hole."""
    for label, path in [("ui", UI_MANIFEST), ("agent", AGENT_MANIFEST)]:
        if not path.exists():
            continue
        for slug, class_uid, alt_uid, _concern in _iter_manifest_entries(path):
            if slug not in _PRE_EXISTING_CLASSIFIER_GAPS:
                continue
            uid, _name = classify_ocsf_class(slug)
            acceptable = {class_uid}
            if alt_uid is not None:
                acceptable.add(int(alt_uid))
            assert uid not in acceptable, (
                f"[{label}] slug={slug!r} now routes to {uid}, which "
                f"matches the manifest. Remove it from "
                f"_PRE_EXISTING_CLASSIFIER_GAPS so the manifest-pinning "
                f"sweep enforces it going forward."
            )
