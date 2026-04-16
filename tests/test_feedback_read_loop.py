"""Phase 3.I feedback read-loop tests (Stream C).

Verifies that:
- FeedbackSystem.read_corrections_for_parser filters by parser_name /
  ocsf_class_uid / vendor, orders by recorded_at desc, caps at limit, and
  never raises.
- Failures in the reader path never propagate.
- record_lua_correction stamps recorded_at as timezone-aware UTC.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

import pytest

from components.feedback_system import FeedbackSystem


# ----- helpers -----


class _FakeKB:
    """Minimal knowledge-base double whose `search` returns canned records."""

    def __init__(self, records):
        self._records = list(records)
        self.calls: list = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return list(self._records)


def _make_fs(records) -> FeedbackSystem:
    return FeedbackSystem(config={}, knowledge_base=_FakeKB(records))


# ----- C1: reader unit tests -----


class TestReadCorrectionsForParser:
    def test_returns_empty_when_no_matches(self):
        fs = _make_fs([])
        out = fs.read_corrections_for_parser("foo")
        assert out == []

    def test_returns_records_for_matching_parser(self):
        records = [
            {
                "metadata": {
                    "doc_type": "correction_example",
                    "parser_name": "foo",
                    "recorded_at": "2026-04-14T00:00:00Z",
                },
                "before": "old", "after": "new", "reason": "field X missing",
            },
        ]
        fs = _make_fs(records)
        out = fs.read_corrections_for_parser("foo")
        assert len(out) == 1
        assert out[0]["before"] == "old"
        assert out[0]["after"] == "new"
        assert out[0]["reason"] == "field X missing"

    def test_filters_out_other_parser_names(self):
        records = [
            {
                "metadata": {
                    "doc_type": "correction_example",
                    "parser_name": "bar",
                    "recorded_at": "2026-04-14T00:00:00Z",
                },
                "before": "x", "after": "y", "reason": "z",
            },
        ]
        fs = _make_fs(records)
        out = fs.read_corrections_for_parser("foo")
        assert out == []

    def test_filters_out_non_correction_doc_types(self):
        records = [
            {
                "metadata": {
                    "doc_type": "deployment_result",
                    "parser_name": "foo",
                    "recorded_at": "2026-04-14T00:00:00Z",
                },
                "before": "x", "after": "y", "reason": "z",
            },
        ]
        fs = _make_fs(records)
        out = fs.read_corrections_for_parser("foo")
        assert out == []

    def test_respects_limit_and_orders_recent_first(self):
        records = [
            {
                "metadata": {
                    "doc_type": "correction_example",
                    "parser_name": "foo",
                    "recorded_at": f"2026-04-1{i}T00:00:00Z",
                },
                "before": f"b{i}", "after": f"a{i}", "reason": f"r{i}",
            }
            for i in range(5)
        ]
        fs = _make_fs(records)
        out = fs.read_corrections_for_parser("foo", limit=2)
        assert len(out) == 2
        # Most recent first: 2026-04-14, then 2026-04-13
        assert out[0]["reason"] == "r4"
        assert out[1]["reason"] == "r3"

    def test_filter_by_ocsf_class_uid(self):
        records = [
            {
                "metadata": {
                    "doc_type": "correction_example",
                    "parser_name": "foo",
                    "ocsf_class_uid": 2004,
                    "recorded_at": "2026-04-14T00:00:00Z",
                },
                "before": "b", "after": "a", "reason": "r",
            },
            {
                "metadata": {
                    "doc_type": "correction_example",
                    "parser_name": "foo",
                    "ocsf_class_uid": 6001,
                    "recorded_at": "2026-04-14T00:00:00Z",
                },
                "before": "b2", "after": "a2", "reason": "r2",
            },
        ]
        fs = _make_fs(records)
        out = fs.read_corrections_for_parser("foo", ocsf_class_uid=2004)
        assert len(out) == 1
        assert out[0]["reason"] == "r"

    def test_returns_empty_on_backend_error(self, caplog):
        class _BoomKB:
            def search(self, **kwargs):
                raise RuntimeError("boom")

        fs = FeedbackSystem(config={}, knowledge_base=_BoomKB())
        with caplog.at_level(logging.WARNING):
            out = fs.read_corrections_for_parser("foo")
        assert out == []

    def test_returns_empty_when_knowledge_base_is_none(self):
        fs = FeedbackSystem(config={}, knowledge_base=None)
        out = fs.read_corrections_for_parser("foo")
        assert out == []

    def test_maps_diff_style_record_fields(self):
        """Records using original_lua/corrected_lua/diff are mapped to
        before/after/reason."""
        records = [
            {
                "metadata": {
                    "doc_type": "correction_example",
                    "parser_name": "foo",
                    "recorded_at": "2026-04-14T00:00:00Z",
                },
                "original_lua": "OLD", "corrected_lua": "NEW", "diff": "DIFF",
            },
        ]
        fs = _make_fs(records)
        out = fs.read_corrections_for_parser("foo")
        assert len(out) == 1
        assert out[0]["before"] == "OLD"
        assert out[0]["after"] == "NEW"
        assert out[0]["reason"] == "DIFF"


class TestRecordedAtTimezoneAware:
    """Stream C DA regression gate.

    record_lua_correction must stamp recorded_at as timezone-aware UTC
    so lexical sort is chronological. This test reads back the JSONL
    written by _persist_record.
    """

    def test_recorded_at_is_timezone_aware_utc(self, tmp_path):
        fs = FeedbackSystem(config={}, knowledge_base=None)
        fs._corrections_path = tmp_path / "corrections.jsonl"

        asyncio.run(
            fs.record_lua_correction(
                parser_name="foo",
                original_lua="function processEvent(e) return e end",
                corrected_lua="function processEvent(e) e.ok=1 return e end",
                correction_reason="field fix",
                user_id="tester",
            )
        )

        assert fs._corrections_path.exists(), "JSONL not written"
        lines = fs._corrections_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) >= 1
        rec = json.loads(lines[0])
        recorded_at = rec.get("recorded_at", "")
        assert recorded_at, "recorded_at missing from record"
        parsed = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
        assert parsed.tzinfo is not None, (
            "recorded_at is naive: %r - must be UTC ISO-8601" % recorded_at
        )
        assert parsed.utcoffset().total_seconds() == 0, (
            "recorded_at is not UTC: %r" % recorded_at
        )
