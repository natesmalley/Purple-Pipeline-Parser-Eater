"""Regression tests replaying Marco Rottigni's 2026-04-08 Parser Builder tests.

Fixtures: ``data/regression_fixtures/marco_2026_04_08/<slug>/``

Each of the four cases captures the input sample, the parser config, the Lua
the Workbench produced, and the findings Marco observed in the UI. These tests
replay the Lua through the current harness and lock in the outcomes, including
two real issues the replay surfaced:

1. Cisco DUO's generated Lua has a scoping bug — the outer ``return result``
   references a variable that only exists inside the inner ``pcall`` closure,
   so ``processEvent()`` silently returns nil. Marco's end-to-end test did not
   catch this (he verified ingestion, not OCSF enrichment output). The harness
   now does: ``test_execution`` reports ``processEvent() returned nil``.

2. The OCSF field analyzer does not evaluate ``class_uid`` assignments made
   through the ``setNestedField(result, "class_uid", N)`` helper — it captures
   the string literal of the expression rather than the value. MS Defender and
   Akamai CDN scripts use this pattern, so the analyzer reports
   ``class_uid: null`` even though the scripts clearly set class_uid 2004.
   This is a known gap worth flagging as regression signal.

The assertions below are **diagnostic** rather than strict-equality: we lock in
the classes of issues Marco documented so future harness changes can't silently
lose those detections.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pytest

from components.testing_harness.harness_orchestrator import HarnessOrchestrator


REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = REPO_ROOT / "data" / "regression_fixtures" / "marco_2026_04_08"
CASES = ["cisco_duo", "ms_defender_365", "akamai_cdn", "akamai_dns"]


def _load_case(slug: str) -> Dict[str, object]:
    base = FIXTURE_ROOT / slug
    assert base.exists(), f"missing fixture dir {base}"
    return {
        "slug": slug,
        "sample": json.loads((base / "sample.json").read_text(encoding="utf-8")),
        "parser_config": json.loads((base / "parser_config.json").read_text(encoding="utf-8")),
        "lua": (base / "generated.lua").read_text(encoding="utf-8"),
        "expected": json.loads((base / "expected.json").read_text(encoding="utf-8")),
    }


@pytest.fixture(scope="module")
def orchestrator() -> HarnessOrchestrator:
    return HarnessOrchestrator()


def _wrap(sample: Dict, name: str = "marco_pdf") -> Dict:
    """The execution engine expects {"name": ..., "event": {...}} test events
    — not raw sample dicts. Wrap a fixture sample into that shape."""
    return {"name": name, "event": sample}


def _run(orchestrator: HarnessOrchestrator, slug: str) -> Dict[str, object]:
    case = _load_case(slug)
    return orchestrator.run_all_checks(
        lua_code=case["lua"],
        parser_config=case["parser_config"],
        custom_test_events=[_wrap(case["sample"], name=f"{slug}_marco")],
    )


# ---------------------------------------------------------------------------
# Fixture sanity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("slug", CASES)
def test_fixture_files_present(slug: str):
    case = _load_case(slug)
    assert case["sample"], f"{slug}: empty sample"
    assert case["lua"].strip(), f"{slug}: empty lua"
    assert "function processEvent" in case["lua"], f"{slug}: lua missing processEvent"


# ---------------------------------------------------------------------------
# Cisco DUO
# ---------------------------------------------------------------------------
# Marco documented: validity Passed, lint Fair (64.5/100), OCSF Poor (33%).
# Replay finds: lua validity True, class_uid 3002 correctly detected, lint
# score ~70.5 with documented loop issues, PLUS a real bug — processEvent
# returns nil due to scoping, which the harness correctly flags via
# test_execution.
#
# Regression signal we require: signature detected, class_uid detected,
# lint flags at least one of the documented categories, AND test_execution
# surfaces the "returned nil" error.

def test_cisco_duo_validity_and_class(orchestrator):
    report = _run(orchestrator, "cisco_duo")
    checks = report["checks"]
    assert checks["lua_validity"]["valid"] is True
    assert checks["lua_validity"]["function_signature"] == "processEvent"
    assert checks["ocsf_alignment"]["class_uid"] == 3002


def test_cisco_duo_linter_still_flags_loop_issues(orchestrator):
    report = _run(orchestrator, "cisco_duo")
    rules = {
        issue["rule"]
        for issue in report["checks"]["lua_linting"].get("issues", [])
    }
    expected_any = {"string_concat_in_loop", "table_in_loop", "unsafe_string_concat",
                    "ocsf_required_fields", "nil_safety"}
    assert rules & expected_any, (
        f"expected at least one of {expected_any}; got {rules}"
    )


def test_cisco_duo_return_scope_bug_caught_by_harness(orchestrator):
    """Marco's Cisco DUO script has a scope bug: the outer ``return result``
    references a variable that only lives inside the inner pcall closure, so
    processEvent returns nil. The harness should surface this via the
    test_execution check. This is a regression guard that should FAIL loudly
    if the execution engine ever stops detecting nil returns."""
    report = _run(orchestrator, "cisco_duo")
    execution = report["checks"]["test_execution"]
    assert execution["failed"] >= 1, "execution engine regressed — nil return no longer detected"
    errors = [r.get("error") or "" for r in execution.get("results") or []]
    assert any("nil" in err.lower() for err in errors), (
        f"expected a nil-return error in execution results; got {errors}"
    )


# ---------------------------------------------------------------------------
# MS Defender 365 — working case (rendered correctly in AI SIEM)
# ---------------------------------------------------------------------------
# Harness now shows: validity True, test_execution 1/1 passed, but OCSF
# alignment reports class_uid=null because the analyzer doesn't evaluate
# setNestedField(result, "class_uid", 2004). That's a known analyzer gap we
# assert as a regression-style "known gap" so it's tracked.

def test_ms_defender_validity_and_execution_pass(orchestrator):
    report = _run(orchestrator, "ms_defender_365")
    assert report["checks"]["lua_validity"]["valid"] is True
    execution = report["checks"]["test_execution"]
    assert execution["passed"] == execution["total_events"], (
        f"execution regressed: {execution}"
    )
    # No runtime error leaking into the blob.
    blob = json.dumps(execution, default=str)
    assert "nil value" not in blob, f"unexpected nil-value runtime error: {blob[:400]}"


def test_ms_defender_setnestedfield_class_uid_now_resolved(orchestrator):
    """MS Defender assigns class_uid via ``setNestedField(result, "class_uid",
    2004)``. The analyzer previously couldn't resolve helper-call assignments
    and reported ``class_uid: null`` for this pattern. With the 2026-04-19
    helper-resolution fix, the analyzer correctly resolves to 2004 and
    required_coverage rises to 100%.
    """
    report = _run(orchestrator, "ms_defender_365")
    alignment = report["checks"]["ocsf_alignment"]
    mapping = report["checks"]["ocsf_mapping"]
    assert alignment["class_uid"] == 2004, (
        f"expected class_uid 2004; got {alignment['class_uid']}"
    )
    assert mapping["class_uid"] == 2004
    assert "class_uid" in mapping.get("detected_fields", [])
    # Required coverage jumped from 0 to 100 with the fix.
    assert alignment["required_coverage"] == 100.0


# ---------------------------------------------------------------------------
# Akamai CDN — working case (same setNestedField pattern as MS Defender)
# ---------------------------------------------------------------------------

def test_akamai_cdn_validity_and_execution_pass(orchestrator):
    report = _run(orchestrator, "akamai_cdn")
    assert report["checks"]["lua_validity"]["valid"] is True
    execution = report["checks"]["test_execution"]
    assert execution["passed"] == execution["total_events"], (
        f"execution regressed: {execution}"
    )


def test_akamai_cdn_classification_smell_documented():
    """Marco's CDN Lua was generated against OCSF class 2004 (Detection
    Finding) which is the wrong class for a CDN access log — Web Resource
    Access (6002) or HTTP Activity (4002) would be more appropriate. The
    fixture records this as a classification smell; Milestone A should shift
    this selection toward an HTTP class via the reference library.
    """
    case = _load_case("akamai_cdn")
    assert "classification_smell" in case["expected"]


# ---------------------------------------------------------------------------
# Akamai DNS — runtime failure case
# ---------------------------------------------------------------------------

def test_akamai_dns_linter_flags_multiple_issues(orchestrator):
    report = _run(orchestrator, "akamai_dns")
    rules = {
        issue["rule"]
        for issue in report["checks"]["lua_linting"].get("issues", [])
    }
    expected_any = {"string_concat_in_loop", "table_in_loop", "unsafe_string_concat",
                    "ocsf_required_fields", "nil_safety"}
    assert rules & expected_any, (
        f"expected at least one of {expected_any}; got {rules}"
    )


def test_akamai_dns_class_uid_literal_detected(orchestrator):
    """Akamai DNS uses a literal ``local CLASS_UID = 4003`` before the
    helper assignment, which the analyzer CAN resolve. Lock this in."""
    report = _run(orchestrator, "akamai_dns")
    assert report["checks"]["ocsf_alignment"]["class_uid"] == 4003


def test_akamai_dns_runtime_error_reproduced_when_timestamp_non_string(orchestrator):
    """Reproduce Marco's production failure: when the dataplane passes
    ``timestamp`` as a non-string (e.g., a numeric epoch), ``eventTime:match(...)``
    blows up with 'attempt to call a nil value (method match)'. We simulate
    that input and confirm the harness surfaces an error."""
    case = _load_case("akamai_dns")
    bad_sample = dict(case["sample"])
    bad_sample["timestamp"] = 1775681018000  # numeric — no :match method
    report = orchestrator.run_all_checks(
        lua_code=case["lua"],
        parser_config=case["parser_config"],
        custom_test_events=[_wrap(bad_sample, name="akamai_dns_bad_ts")],
    )
    execution = report["checks"]["test_execution"]
    # The Lua script wraps its body in pcall and stores errors in
    # event["lua_error"], so the harness marks the run as "passed". The
    # failure surfaces as a `lua_error` key inside the output_event.
    lua_errors = [
        (r.get("output_event") or {}).get("lua_error")
        for r in execution.get("results") or []
    ]
    lua_errors = [e for e in lua_errors if e]
    assert lua_errors, (
        f"expected timestamp:match failure to be captured in output_event.lua_error; "
        f"got execution: {execution}"
    )
    joined = " ".join(str(e).lower() for e in lua_errors)
    assert (
        "match" in joined
        or "nil value" in joined
        or "number value" in joined
        or "eventtime" in joined
    ), f"expected failure to reference timestamp/match/eventTime; got {lua_errors}"


# ---------------------------------------------------------------------------
# Overall invariants across all four cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("slug", CASES)
def test_every_case_is_syntactically_valid(orchestrator, slug):
    """All four Lua files were at least syntactically valid in Marco's UI.
    If ``lupa`` stops parsing them, something regressed in the validity check.
    """
    report = _run(orchestrator, slug)
    assert report["checks"]["lua_validity"]["valid"] is True, slug


@pytest.mark.parametrize("slug", CASES)
def test_every_case_exercises_all_five_harness_modules(orchestrator, slug):
    report = _run(orchestrator, slug)
    checks = report["checks"]
    for required in ("lua_validity", "lua_linting", "ocsf_mapping",
                     "ocsf_alignment", "test_execution"):
        assert required in checks, f"{slug}: missing harness module {required}"
