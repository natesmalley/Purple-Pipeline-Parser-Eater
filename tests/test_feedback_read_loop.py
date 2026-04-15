"""Phase 3.I feedback read-loop tests (Stream C).

Verifies that:
- FeedbackSystem.read_corrections_for_parser filters by parser_name /
  ocsf_class_uid / vendor, orders by recorded_at desc, caps at limit, and
  never raises.
- LuaGenerator._read_feedback_corrections delegates into the reader and
  injects formatted corrections into the user prompt.
- Failures in the reader path never propagate into _build_user_prompt.
"""
from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from components.feedback_system import FeedbackSystem
from components.lua_generator import GenerationRequest, LuaGenerator, SourceField


# ----- helpers -----


def _make_request(
    parser_name: str = "foo",
    ocsf_class_uid: int | None = 2004,
    vendor: str | None = "acme",
) -> GenerationRequest:
    return GenerationRequest(
        parser_id=parser_name,
        parser_name=parser_name,
        parser_analysis={},
        source_fields=[SourceField(name="src_ip", type="string")],
        ocsf_class_uid=ocsf_class_uid,
        vendor=vendor,
        product="widget",
    )


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


# ----- C2: generator wiring tests -----


class TestLuaGeneratorReadFeedbackCorrections:
    def test_correction_appears_in_prompt_when_scope_matches(self):
        gen = LuaGenerator(config={"anthropic": {"api_key": "x"}})
        records = [
            {
                "before": "old", "after": "new",
                "reason": "field X missing",
                "recorded_at": "2026-04-14T00:00:00Z",
            },
        ]
        with patch.object(
            FeedbackSystem,
            "read_corrections_for_parser",
            return_value=records,
        ):
            request = _make_request(parser_name="foo", ocsf_class_uid=2004)
            prompt = gen._build_user_prompt(request)
        assert "old" in prompt
        assert "new" in prompt
        assert "field X missing" in prompt

    def test_correction_absent_when_parser_differs(self):
        gen = LuaGenerator(config={"anthropic": {"api_key": "x"}})

        def fake_reader(self, parser_name, **kwargs):
            if parser_name == "foo":
                return [{
                    "before": "old", "after": "new",
                    "reason": "scope test",
                    "recorded_at": "2026-04-14T00:00:00Z",
                }]
            return []

        with patch.object(FeedbackSystem, "read_corrections_for_parser", fake_reader):
            request = _make_request(parser_name="bar", ocsf_class_uid=2004)
            prompt = gen._build_user_prompt(request)
        assert "old" not in prompt
        assert "new" not in prompt

    def test_correction_absent_when_ocsf_class_differs(self):
        gen = LuaGenerator(config={"anthropic": {"api_key": "x"}})

        def fake_reader(self, parser_name, ocsf_class_uid=None, **kwargs):
            if ocsf_class_uid == 2004:
                return [{
                    "before": "old", "after": "new", "reason": "scoped",
                    "recorded_at": "2026-04-14T00:00:00Z",
                }]
            return []

        with patch.object(FeedbackSystem, "read_corrections_for_parser", fake_reader):
            request = _make_request(parser_name="foo", ocsf_class_uid=6001)
            prompt = gen._build_user_prompt(request)
        assert "old" not in prompt
        assert "new" not in prompt

    def test_reader_never_raises_into_generator(self):
        gen = LuaGenerator(config={"anthropic": {"api_key": "x"}})

        def boom(*args, **kwargs):
            raise RuntimeError("boom")

        with patch.object(FeedbackSystem, "read_corrections_for_parser", boom):
            request = _make_request()
            # Must not raise
            prompt = gen._build_user_prompt(request)
        assert isinstance(prompt, str)
        assert "Parser:" in prompt

    def test_format_correction_respects_max_sample_chars(self, monkeypatch):
        """Pathological correction must not blow the context budget."""
        monkeypatch.setenv("WORKBENCH_MAX_SAMPLE_CHARS", "400")
        gen = LuaGenerator(config={"anthropic": {"api_key": "x"}})
        big_record = {
            "before": "B" * 10_000,
            "after": "A" * 10_000,
            "reason": "R" * 10_000,
            "recorded_at": "2026-04-14T00:00:00Z",
        }
        formatted = gen._format_correction_for_prompt(big_record)
        # Bounded by WORKBENCH_MAX_SAMPLE_CHARS (400). The total will include
        # a bit of label scaffolding but must be far less than 30k.
        assert len(formatted) < 1000
