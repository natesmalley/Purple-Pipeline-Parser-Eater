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

from components.agentic_lua_generator import (
    OCSF_CLASS_KEYWORDS,
    _classifier_kw_matches,
    _classifier_segments,
    classify_ocsf_class,
)
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

# FU7 (2026-04-30): under segment-aligned matching, plural `assets` is
# NOT an exact match for keyword `asset`, and FU7 forbids adding the
# plural to keep the no-plural-augmentation rule. The test name
# `windows_endpoint_assets` therefore relied on a substring artefact
# (`asset` ⊂ `assets`); we replace it with the singular form
# `windows_endpoint_asset` which segment-matches cleanly. The
# plural-form regression is locked separately by the FU7 negative cases
# below.
@pytest.mark.parametrize(
    "parser_name",
    ["cisco_asa_inventory", "windows_endpoint_asset",
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
# FU6 (2026-04-30): Azure Event Hub → Defender ingest restoration
# ---------------------------------------------------------------------------
#
# W3 replaced bare `defender` with `microsoft_defender` +
# `defender_for_endpoint` to fix SiteDefender. Side effect: the manifest
# entries `microsoft_eventhub_defender_email_logs` and
# `microsoft_eventhub_defender_emailforcloud_logs` (both declared
# class_uid=2004, class_uid_concern=True so already skipped by the
# manifest-pinning sweep) silently dropped to default 4001 because their
# slugs contain neither `microsoft_defender` (the `_eventhub_` infix
# breaks the substring match) nor `_for_endpoint`. FU6 adds the
# discriminating `eventhub_defender` token to the 2004 row to restore
# 2004 routing for the Azure Event Hub → Defender ingest path.

@pytest.mark.parametrize(
    "parser_name",
    [
        "microsoft_eventhub_defender_email_logs",
        "microsoft_eventhub_defender_emailforcloud_logs",
    ],
)
def test_microsoft_eventhub_defender_routes_to_2004(parser_name: str) -> None:
    """Both manifest entries declare class_uid=2004 (Detection Finding).
    Pre-FU6 they routed to 4001 default because none of the W3
    replacement tokens substring-matched them. The `eventhub_defender`
    token added in FU6 restores 2004 routing."""
    uid, _name = classify_ocsf_class(parser_name)
    assert uid == 2004, (
        f"{parser_name} should route to 2004 (manifest declared); got {uid}"
    )


def test_azure_eventhub_logs_without_defender_stays_at_4001() -> None:
    """Negative case: a generic Event Hub parser without `defender` in
    the slug must NOT be pulled into 2004 by the new keyword. The
    `eventhub_defender` token requires `defender` adjacency, so plain
    `azure_eventhub_logs` keeps its pre-FU6 routing (default 4001
    Network Activity, captured pre-FU6 to lock the negative path)."""
    uid, _name = classify_ocsf_class("azure_eventhub_logs")
    assert uid == 4001, (
        f"azure_eventhub_logs should stay at default 4001 (no defender "
        f"keyword should pull it into 2004); got {uid}"
    )


def test_eventhub_defender_keyword_is_present_on_2004() -> None:
    """Lock the FU6 keyword in place. Removing it would silently
    re-break manifest entries microsoft_eventhub_defender_email_logs
    and microsoft_eventhub_defender_emailforcloud_logs."""
    assert "eventhub_defender" in OCSF_CLASS_KEYWORDS[2004], (
        "FU6: 'eventhub_defender' must be on 2004's keyword list"
    )


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


# ---------------------------------------------------------------------------
# FU7 (2026-04-30): segment-aligned matching replaces substring scoring
# ---------------------------------------------------------------------------
#
# Under the prior substring matcher, `kw in combined` ran a literal
# character-sequence containment check. That meant `finding` substring-
# matched `findings` and routed `tenable_findings` to 2004 (1-1 tie with
# 2002, lost to insertion order). Segment-aligned matching splits
# `combined` on `[_.\-\s]+` and requires single-segment keywords to be
# EXACT segment elements (multi-segment keywords match as contiguous
# subsequences). `findings` is no longer treated as `finding`, so
# `tenable_findings` cleanly scores 2002=1, 2004=0.
#
# This packet explicitly forbids:
#   - plural augmentation (adding `findings`, `alerts`, etc. to keyword
#     rows — that re-introduces the same 1-1 tie this fix exists to
#     resolve)
#   - tie-break changes (strict-greater + insertion-order behaviour
#     remains intact; documented design ties like `tenable_alert_summary`
#     keep resolving to 2004)


def test_classifier_segments_helper_basic() -> None:
    """The local segment splitter mirrors W7's `_segments` (in
    `source_parser_analyzer.compare_with_lua`): split on `[_.\\-\\s]+`,
    lowercase, drop empties."""
    assert _classifier_segments("tenable_findings") == ["tenable", "findings"]
    assert _classifier_segments("Microsoft.Defender_For-Endpoint") == [
        "microsoft", "defender", "for", "endpoint",
    ]
    assert _classifier_segments("") == []
    assert _classifier_segments("   ") == []


def test_classifier_kw_matches_single_segment() -> None:
    """Single-segment keyword: exact membership in segment list. NO
    substring containment. This is the load-bearing behaviour change for
    FU7."""
    assert _classifier_kw_matches("finding", ["tenable", "finding"]) is True
    assert _classifier_kw_matches("finding", ["tenable", "findings"]) is False
    assert _classifier_kw_matches("finding", ["find", "user"]) is False
    assert _classifier_kw_matches("alert", ["crowdstrike", "alerts"]) is False
    assert _classifier_kw_matches("alert", ["darktrace", "alert"]) is True


def test_classifier_kw_matches_multi_segment_contiguous() -> None:
    """Multi-segment keyword: must appear as a contiguous subsequence."""
    # eventhub_defender (segments [eventhub, defender]) within
    # microsoft_eventhub_defender_email_logs
    segs = ["microsoft", "eventhub", "defender", "email", "logs"]
    assert _classifier_kw_matches("eventhub_defender", segs) is True
    # Non-contiguous: keyword segments split by another segment must NOT
    # match.
    segs_split = ["microsoft", "eventhub", "email", "defender"]
    assert _classifier_kw_matches("eventhub_defender", segs_split) is False
    # Out-of-order must NOT match.
    segs_reversed = ["microsoft", "defender", "eventhub"]
    assert _classifier_kw_matches("eventhub_defender", segs_reversed) is False


def test_tenable_findings_routes_to_2002_not_2004() -> None:
    """The flagship FU7 case. `tenable_findings` segments are
    `[tenable, findings]`. Under substring scoring, `finding` matched
    `findings` by character-sequence containment, so 2002 (via
    `tenable`) and 2004 (via substring-`finding`) tied 1-1 and 2004 won
    by insertion order. Under segment matching, `finding != findings`,
    so 2002 wins 1-0 cleanly. Per FU7 we MUST NOT add `findings` to
    2004 — that re-introduces the tie."""
    uid, _name = classify_ocsf_class("tenable_findings")
    assert uid == 2002, f"tenable_findings should route to 2002; got {uid}"


def test_snyk_findings_report_routes_to_2002() -> None:
    """Same shape as `tenable_findings`: segments `[snyk, findings,
    report]`. 2002 hits via `snyk`; 2004 cannot match (no
    `findings`-as-segment keyword, and FU7 forbids adding one)."""
    uid, _name = classify_ocsf_class("snyk_findings_report")
    assert uid == 2002, f"snyk_findings_report should route to 2002; got {uid}"


def test_defender_finding_still_routes_to_2004() -> None:
    """Singular `finding` IS an exact segment in `[defender, finding]`,
    so 2004 still matches via `finding`. (2004's
    `microsoft_defender`/`defender_for_endpoint` multi-segment keywords
    do NOT match `[defender, finding]` — a contiguous subsequence
    requires both keyword segments to appear in the slug. `finding` alone
    carries the 2004 routing here.)"""
    uid, _name = classify_ocsf_class("defender_finding")
    assert uid == 2004, f"defender_finding should route to 2004; got {uid}"


def test_crowdstrike_alerts_still_routes_to_2004() -> None:
    """Plural `alerts` is NOT an exact match for keyword `alert`, so the
    `alert` keyword does NOT contribute. Routing is carried by the
    `crowdstrike` keyword on 2004. This locks the no-plural-
    augmentation rule — if a future maintainer adds `alerts` to 2004,
    this test still passes (overconstrained on intent), but FU7's
    rationale demands the routing flow through the vendor keyword, not
    through plural augmentation."""
    uid, _name = classify_ocsf_class("crowdstrike_alerts")
    assert uid == 2004, f"crowdstrike_alerts should route to 2004; got {uid}"


def test_generic_finding_still_routes_to_2004() -> None:
    """Singular `finding` is on 2004 only and IS an exact segment in
    `[generic, finding]`, so 2004 wins 1-0."""
    uid, _name = classify_ocsf_class("generic_finding")
    assert uid == 2004, f"generic_finding should route to 2004; got {uid}"


def test_negative_find_user_does_not_match_finding() -> None:
    """Negative case: `find_user` segments are `[find, user]`. Under
    segment matching, neither `find` nor `user` matches the `finding`
    keyword (segment != keyword). Default 4001 routing must hold."""
    uid, _name = classify_ocsf_class("find_user")
    # The exact non-2004 routing isn't load-bearing — the contract is
    # that `finding` does NOT pull this into 2004 via stray substring.
    assert uid != 2004, (
        f"find_user must NOT route to 2004 via substring-'finding'; got {uid}"
    )


def test_tenable_alert_summary_documented_design_tie() -> None:
    """Documented design tie: segments `[tenable, alert, summary]` give
    2002=1 (via `tenable`) and 2004=1 (via `alert`). Strict-greater +
    insertion-order resolves to 2004 (declared first). FU7 explicitly
    preserves this tie-break behaviour — adding `findings`/`alerts` to
    2004 OR moving 2002 above 2004 in declaration order would
    "fix" this in isolation but violate the FU7 no-plural-augmentation /
    no-tie-break-change scope. Anyone tempted to flip this should open
    a new packet, not patch FU7."""
    uid, _name = classify_ocsf_class("tenable_alert_summary")
    assert uid == 2004, f"tenable_alert_summary documented tie expects 2004; got {uid}"


def test_qualys_finding_documented_design_tie() -> None:
    """Same shape as `tenable_alert_summary`: segments `[qualys,
    finding]` give 2002=1 (via `qualys`) and 2004=1 (via `finding`).
    Insertion-order resolves to 2004. The FU7 plan listed this slug as
    expected → 2002, but that contradicts the no-plural / no-tie-break
    constraints — moving it to 2002 would require either adding
    `findings`-equivalent boosts to 2002 or reordering the keyword
    table. Locked at 2004 with this comment so the structural
    consistency with `tenable_alert_summary` is auditable."""
    uid, _name = classify_ocsf_class("qualys_finding")
    assert uid == 2004, (
        f"qualys_finding documented tie expects 2004 (consistent with "
        f"tenable_alert_summary structural shape); got {uid}"
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
