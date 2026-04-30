"""
W6 — preflight format detection regression tests.

Verifies the fix to `_infer_sample_preflight` in components/agentic_lua_generator.py:
- RFC3164 syslog regex was broken (literal `\\w` / `\\s` / `\\d` in raw strings) and
  is now corrected.
- New detections added for RFC5424 syslog, CEF, and LEEF — each surfaced under a
  distinct entry in the returned `formats` list so downstream prompt builders can
  branch on the specific variant rather than a generic "syslog" bucket.
- Existing JSON / KV / CSV detection must remain unchanged.
"""

from __future__ import annotations

import pytest

from components.agentic_lua_generator import _infer_sample_preflight


RFC3164_SAMPLE = "<134>Apr 28 12:34:56 host1 daemon: message body"
RFC5424_SAMPLE = "<134>1 2026-04-28T12:34:56.000Z host1 app1 1234 ID47 - body"
CEF_SAMPLE = "CEF:0|Vendor|Product|1.0|100|signature|10|src=10.0.0.1 dst=10.0.0.2"
LEEF_SAMPLE = "LEEF:1.0|Vendor|Product|1.0|action=allow|src=10.0.0.1"
JSON_SAMPLE = '{"timestamp":"2026-04-28T12:34:56Z","src":"10.0.0.1"}'
KV_SAMPLE = "src=10.0.0.1 dst=10.0.0.2 action=allow"
CSV_SAMPLE = "a,b,c\n1,2,3\n4,5,6"


def _formats(sample: str) -> set[str]:
    """Run preflight on a single sample and return the formats set."""
    result = _infer_sample_preflight([sample])
    assert isinstance(result, dict)
    assert "formats" in result
    return set(result["formats"])


def test_rfc3164_syslog_detected() -> None:
    """The fixed regex must match a classic RFC3164 syslog line."""
    formats = _formats(RFC3164_SAMPLE)
    assert "syslog" in formats, (
        f"RFC3164 syslog must be detected as 'syslog'; got {formats}"
    )
    # Should NOT misfire as RFC5424.
    assert "syslog_rfc5424" not in formats
    # Should NOT misfire as CEF / LEEF.
    assert "cef" not in formats
    assert "leef" not in formats


def test_rfc5424_syslog_detected() -> None:
    """RFC5424 (`<PRI>1 ISO8601 ...`) must surface as a distinct bucket."""
    formats = _formats(RFC5424_SAMPLE)
    assert "syslog_rfc5424" in formats, (
        f"RFC5424 syslog must be detected as 'syslog_rfc5424'; got {formats}"
    )
    # Must NOT collapse into the generic 'syslog' bucket.
    assert "syslog" not in formats
    assert "cef" not in formats
    assert "leef" not in formats


def test_cef_detected() -> None:
    """CEF lines must surface under their own bucket, not 'syslog'."""
    formats = _formats(CEF_SAMPLE)
    assert "cef" in formats, f"CEF must be detected as 'cef'; got {formats}"
    assert "syslog" not in formats
    assert "syslog_rfc5424" not in formats
    assert "leef" not in formats


def test_leef_detected() -> None:
    """LEEF lines must surface under their own bucket, not 'syslog' or 'cef'."""
    formats = _formats(LEEF_SAMPLE)
    assert "leef" in formats, f"LEEF must be detected as 'leef'; got {formats}"
    assert "syslog" not in formats
    assert "syslog_rfc5424" not in formats
    assert "cef" not in formats


def test_json_detection_unchanged() -> None:
    """JSON detection must be unaffected by the syslog/CEF/LEEF additions."""
    formats = _formats(JSON_SAMPLE)
    assert "json" in formats
    # Should not pick up any syslog-family false positives.
    assert "syslog" not in formats
    assert "syslog_rfc5424" not in formats
    assert "cef" not in formats
    assert "leef" not in formats


def test_kv_detection_unchanged() -> None:
    """Bare KV detection must continue to return 'kv'."""
    formats = _formats(KV_SAMPLE)
    assert "kv" in formats
    assert "syslog" not in formats
    assert "syslog_rfc5424" not in formats
    assert "cef" not in formats
    assert "leef" not in formats


def test_csv_detection_unchanged() -> None:
    """Multi-row CSV detection must continue to return 'csv'."""
    formats = _formats(CSV_SAMPLE)
    assert "csv" in formats
    assert "syslog" not in formats
    assert "syslog_rfc5424" not in formats
    assert "cef" not in formats
    assert "leef" not in formats


@pytest.mark.parametrize(
    "sample,expected",
    [
        (RFC3164_SAMPLE, "syslog"),
        (RFC5424_SAMPLE, "syslog_rfc5424"),
        (CEF_SAMPLE, "cef"),
        (LEEF_SAMPLE, "leef"),
    ],
)
def test_preflight_buckets_are_distinct(sample: str, expected: str) -> None:
    """Each format variant lands in its own bucket — never collapsed."""
    formats = _formats(sample)
    assert expected in formats
    distinct_buckets = {"syslog", "syslog_rfc5424", "cef", "leef"}
    other_buckets = distinct_buckets - {expected}
    assert not (other_buckets & formats), (
        f"sample {sample!r} should match only {expected!r}, "
        f"also matched {other_buckets & formats}"
    )
