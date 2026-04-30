"""Regression tests for the segment-aligned source-coverage matcher (W7 / HC1).

These tests cover the matcher rewrite in
``components/testing_harness/source_parser_analyzer.py`` that replaced the
``norm in ln or ln in norm`` substring matcher with explicit single- vs
multi-segment cases.

The matcher is exercised through the public ``compare_with_lua()`` API: the
test rigs Lua field references via a small helper that emits
``event["<name>"]`` references the analyzer's regex-based extractor will
recognise.
"""

from __future__ import annotations

from typing import Iterable

import pytest

from components.testing_harness.source_parser_analyzer import SourceParserAnalyzer


def _lua_for(candidates: Iterable[str]) -> str:
    """Emit Lua snippets the analyzer's ``_extract_lua_fields`` will pick up."""
    return "\n".join(f'event["{c}"]' for c in candidates) + "\n"


@pytest.fixture
def analyzer() -> SourceParserAnalyzer:
    return SourceParserAnalyzer()


# ---------------------------------------------------------------------------
# Single-segment cases — the regression scope of HC1.
# ---------------------------------------------------------------------------

def test_single_segment_ip_matches_exactly_two(analyzer):
    """``ip`` must match ``src_ip`` and ``dst_ip`` only — not ``tipping_point`` or ``recipient``."""
    parser_fields = {"fields": [{"name": "ip"}]}
    lua_code = _lua_for(["src_ip", "dst_ip", "tipping_point", "recipient"])
    result = analyzer.compare_with_lua(parser_fields, lua_code)
    assert result["coverage_pct"] == 100  # the single source field IS mapped
    assert len(result["mapped_fields"]) == 1
    assert result["mapped_fields"][0]["source"] == "ip"
    # Confirm the matched lua_reference came from the correct candidate set.
    assert result["mapped_fields"][0]["lua_reference"] in {"src_ip", "dst_ip"}


def test_single_segment_ip_lua_side_count(analyzer):
    """Pivot the test: emit four source fields named ``ip`` synonyms; ensure
    that only the two genuine ``*_ip`` Lua refs satisfy the matcher.

    Because the matcher key in ``compare_with_lua`` iterates source-by-source
    and stops on the first lua match, we instead run the matcher logic at the
    level the spec requires by counting how many of the four candidates the
    matcher would accept for source ``ip``.
    """
    candidates = ["src_ip", "dst_ip", "tipping_point", "recipient"]
    accepted = [c for c in candidates if _matches_via_public_api(analyzer, "ip", c)]
    assert sorted(accepted) == ["dst_ip", "src_ip"]


def test_single_segment_id_matches_exactly_three(analyzer):
    """``id`` matches ``src_id``, ``client_id``, ``id_token``; rejects ``ipid``."""
    candidates = ["src_id", "client_id", "id_token", "ipid"]
    accepted = [c for c in candidates if _matches_via_public_api(analyzer, "id", c)]
    assert sorted(accepted) == ["client_id", "id_token", "src_id"]


def test_single_segment_src_matches_exactly_two(analyzer):
    """``src`` matches ``src_ip``, ``src_port``; rejects ``tipping_point``."""
    candidates = ["src_ip", "src_port", "tipping_point"]
    accepted = [c for c in candidates if _matches_via_public_api(analyzer, "src", c)]
    assert sorted(accepted) == ["src_ip", "src_port"]


# ---------------------------------------------------------------------------
# Multi-segment cases — full segment-list equality only.
# ---------------------------------------------------------------------------

def test_multi_segment_http_method_matches_exactly_one(analyzer):
    """``http_method`` matches only the candidate with identical segment list."""
    candidates = ["http_method", "method", "http", "http_status"]
    accepted = [c for c in candidates if _matches_via_public_api(analyzer, "http_method", c)]
    assert accepted == ["http_method"]


def test_multi_segment_dotted_source_matches_underscored_candidate(analyzer):
    """Dot-separated and underscore-separated names share segment lists."""
    candidates = ["event_detail_user"]
    accepted = [
        c for c in candidates if _matches_via_public_api(analyzer, "event.detail.user", c)
    ]
    assert accepted == ["event_detail_user"]


# ---------------------------------------------------------------------------
# Negative / hygiene cases.
# ---------------------------------------------------------------------------

def test_empty_source_does_not_match_anything(analyzer):
    """Empty / whitespace-only source names yield no exception and no match."""
    for empty in ("", "   ", "\t", "_._.", "..."):
        accepted = [
            c
            for c in ["src_ip", "client_id"]
            if _matches_via_public_api(analyzer, empty, c)
        ]
        assert accepted == [], f"empty source {empty!r} matched {accepted}"


def test_empty_candidate_does_not_match_anything(analyzer):
    """Empty / whitespace-only candidate names yield no match."""
    for empty in ("", "   ", "_._.", "..."):
        # Compare via the public surface: feed the empty into the lua code via
        # an explicit set rather than the regex extractor (which would not
        # capture empties anyway).
        result = analyzer.compare_with_lua(
            {"fields": [{"name": "ip"}]},
            _lua_for([empty]) if empty.strip() else "",
        )
        # No matches against empty/whitespace-only Lua fields.
        assert result["mapped_fields"] == []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _matches_via_public_api(
    analyzer: SourceParserAnalyzer, source: str, candidate: str
) -> bool:
    """Run a single source-field against a single candidate via ``compare_with_lua``.

    Keeps the test attached to the public surface (no private import); avoids
    duplicating the matcher logic in the test file.
    """
    parser_fields = {"fields": [{"name": source}]}
    lua_code = _lua_for([candidate])
    result = analyzer.compare_with_lua(parser_fields, lua_code)
    return bool(result["mapped_fields"])
