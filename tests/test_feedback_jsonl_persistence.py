"""Tests for the JSONL persistence layer in FeedbackSystem.

Covers:
- _persist_record with a small payload (direct JSONL append)
- _persist_record with a large payload (> 4096 bytes, sibling file + pointer)
- read_corrections_for_parser reading from the JSONL source with no KB
- Deduplication between JSONL and knowledge_base sources
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from components.feedback_system import FeedbackSystem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fs(tmp_path: Path, kb=None) -> FeedbackSystem:
    """Build a FeedbackSystem pointing at a temp JSONL path."""
    fs = FeedbackSystem(config={}, knowledge_base=kb)
    fs._corrections_path = tmp_path / "corrections.jsonl"
    return fs


class _FakeKB:
    """KB double that returns canned records from search()."""

    def __init__(self, records):
        self._records = list(records)

    def search(self, **kwargs):
        return list(self._records)


# ---------------------------------------------------------------------------
# Small-payload persistence (fits in PIPE_BUF)
# ---------------------------------------------------------------------------


class TestPersistRecordSmall:
    def test_small_record_appended_to_jsonl(self, tmp_path):
        fs = _make_fs(tmp_path)
        cid = fs._persist_record(
            doc_type="correction_example",
            content="small content",
            metadata={"parser_name": "foo"},
        )
        assert len(cid) == 12
        jsonl = fs._corrections_path.read_text(encoding="utf-8")
        lines = [l for l in jsonl.strip().splitlines() if l.strip()]
        assert len(lines) == 1
        rec = json.loads(lines[0])
        assert rec["correction_id"] == cid
        assert rec["doc_type"] == "correction_example"
        assert rec["parser_name"] == "foo"
        assert rec["content"] == "small content"
        assert "recorded_at" in rec

    def test_multiple_records_appended(self, tmp_path):
        fs = _make_fs(tmp_path)
        cid1 = fs._persist_record("t1", "c1", {"parser_name": "a"})
        cid2 = fs._persist_record("t2", "c2", {"parser_name": "b"})
        lines = fs._corrections_path.read_text(
            encoding="utf-8"
        ).strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["correction_id"] == cid1
        assert json.loads(lines[1])["correction_id"] == cid2


# ---------------------------------------------------------------------------
# Large-payload persistence (> 4096 bytes -> sibling file + pointer)
# ---------------------------------------------------------------------------


class TestPersistRecordLarge:
    def test_large_record_uses_sibling_file(self, tmp_path):
        fs = _make_fs(tmp_path)
        big_content = "X" * 5000
        cid = fs._persist_record(
            doc_type="correction_example",
            content=big_content,
            metadata={"parser_name": "big"},
        )
        # JSONL should contain a pointer, not the full record
        jsonl = fs._corrections_path.read_text(encoding="utf-8")
        lines = [l for l in jsonl.strip().splitlines() if l.strip()]
        assert len(lines) == 1
        pointer = json.loads(lines[0])
        assert "_ref" in pointer
        assert pointer["correction_id"] == cid
        assert pointer["doc_type"] == "correction_example"
        assert pointer["parser_name"] == "big"
        # The pointer itself must be small
        assert len(lines[0].encode("utf-8")) <= 4096

        # Sibling file must contain the full record
        sibling = tmp_path / pointer["_ref"]
        assert sibling.exists()
        full = json.loads(sibling.read_text(encoding="utf-8"))
        assert full["content"] == big_content
        assert full["correction_id"] == cid


# ---------------------------------------------------------------------------
# read_corrections_for_parser from JSONL (no KB)
# ---------------------------------------------------------------------------


class TestReadFromJSONL:
    def test_reads_corrections_from_jsonl(self, tmp_path):
        fs = _make_fs(tmp_path)
        fs._persist_record(
            doc_type="correction_example",
            content="correction body",
            metadata={
                "parser_name": "myparser",
                "before": "old_lua",
                "after": "new_lua",
                "reason": "field missing",
            },
        )
        out = fs.read_corrections_for_parser("myparser")
        assert len(out) == 1
        assert out[0]["before"] == "old_lua"
        assert out[0]["after"] == "new_lua"
        assert out[0]["reason"] == "field missing"

    def test_filters_by_parser_name_in_jsonl(self, tmp_path):
        fs = _make_fs(tmp_path)
        fs._persist_record(
            doc_type="correction_example",
            content="c1",
            metadata={"parser_name": "aaa", "before": "a"},
        )
        fs._persist_record(
            doc_type="correction_example",
            content="c2",
            metadata={"parser_name": "bbb", "before": "b"},
        )
        out = fs.read_corrections_for_parser("aaa")
        assert len(out) == 1
        assert out[0]["before"] == "a"

    def test_resolves_ref_pointers(self, tmp_path):
        fs = _make_fs(tmp_path)
        big_content = "Z" * 5000
        fs._persist_record(
            doc_type="correction_example",
            content=big_content,
            metadata={
                "parser_name": "refparser",
                "before": "ref_old",
                "after": "ref_new",
                "reason": "ref_reason",
            },
        )
        out = fs.read_corrections_for_parser("refparser")
        assert len(out) == 1
        assert out[0]["before"] == "ref_old"

    def test_returns_empty_when_no_jsonl_file(self, tmp_path):
        fs = _make_fs(tmp_path)
        out = fs.read_corrections_for_parser("nope")
        assert out == []


# ---------------------------------------------------------------------------
# Deduplication between JSONL and KB sources
# ---------------------------------------------------------------------------


class TestDeduplication:
    def test_deduplicates_by_correction_id(self, tmp_path):
        fs = _make_fs(tmp_path)
        # Write a record to JSONL
        cid = fs._persist_record(
            doc_type="correction_example",
            content="dup body",
            metadata={
                "parser_name": "dupparser",
                "before": "old",
                "after": "new",
                "reason": "dup test",
            },
        )

        # Create a KB that returns the same correction_id
        kb_records = [
            {
                "metadata": {
                    "doc_type": "correction_example",
                    "parser_name": "dupparser",
                    "correction_id": cid,
                    "recorded_at": "2026-04-14T00:00:00Z",
                },
                "before": "old_kb",
                "after": "new_kb",
                "reason": "dup test kb",
                "correction_id": cid,
            },
        ]
        fs.knowledge_base = _FakeKB(kb_records)

        out = fs.read_corrections_for_parser("dupparser", limit=10)
        # Should have only 1 result (deduplicated by correction_id)
        assert len(out) == 1

    def test_combines_distinct_records_from_both_sources(self, tmp_path):
        fs = _make_fs(tmp_path)
        fs._persist_record(
            doc_type="correction_example",
            content="jsonl body",
            metadata={
                "parser_name": "combo",
                "before": "jsonl_old",
                "after": "jsonl_new",
                "reason": "from jsonl",
            },
        )

        kb_records = [
            {
                "metadata": {
                    "doc_type": "correction_example",
                    "parser_name": "combo",
                    "correction_id": "kb_unique_id",
                    "recorded_at": "2026-04-15T00:00:00Z",
                },
                "before": "kb_old",
                "after": "kb_new",
                "reason": "from kb",
                "correction_id": "kb_unique_id",
            },
        ]
        fs.knowledge_base = _FakeKB(kb_records)

        out = fs.read_corrections_for_parser("combo", limit=10)
        assert len(out) == 2
        reasons = {r["reason"] for r in out}
        assert "from jsonl" in reasons
        assert "from kb" in reasons
