"""Stream A2.a — FeedbackChannel file-backed cross-process bus."""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest


def test_append_and_drain_roundtrip(tmp_path):
    from components.feedback_channel import FeedbackChannel

    ch = FeedbackChannel(path=tmp_path / "actions.jsonl")
    ch.append({"action": "approve", "parser_name": "p1"})
    ch.append({"action": "reject", "parser_name": "p2"})

    records, new_offset = ch.drain_new(0)
    assert len(records) == 2
    assert records[0]["action"] == "approve"
    assert records[1]["parser_name"] == "p2"
    assert new_offset > 0


def test_drain_new_offset_advances(tmp_path):
    from components.feedback_channel import FeedbackChannel

    ch = FeedbackChannel(path=tmp_path / "actions.jsonl")
    ch.append({"action": "a"})
    rec1, off1 = ch.drain_new(0)
    assert len(rec1) == 1

    ch.append({"action": "b"})
    rec2, off2 = ch.drain_new(off1)
    assert len(rec2) == 1
    assert rec2[0]["action"] == "b"
    assert off2 > off1


def test_drain_from_zero_returns_full_history(tmp_path):
    from components.feedback_channel import FeedbackChannel

    ch = FeedbackChannel(path=tmp_path / "actions.jsonl")
    for i in range(5):
        ch.append({"action": "x", "i": i})

    records, _ = ch.drain_new(0)
    assert len(records) == 5
    assert [r["i"] for r in records] == [0, 1, 2, 3, 4]


def test_record_size_limit_rejects_oversize(tmp_path):
    from components.feedback_channel import FeedbackChannel

    ch = FeedbackChannel(path=tmp_path / "actions.jsonl")
    big = {"action": "x", "blob": "z" * 4096}
    with pytest.raises(ValueError):
        ch.append(big)


def test_concurrent_append_safety(tmp_path):
    from components.feedback_channel import FeedbackChannel

    ch = FeedbackChannel(path=tmp_path / "actions.jsonl")
    errors = []

    def worker(label):
        try:
            for i in range(50):
                ch.append({"action": "x", "label": label, "i": i})
        except Exception as exc:  # pragma: no cover - test diagnostic
            errors.append(exc)

    t1 = threading.Thread(target=worker, args=("A",))
    t2 = threading.Thread(target=worker, args=("B",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert not errors

    records, _ = ch.drain_new(0)
    assert len(records) == 100
    # All records must round-trip as parseable JSON dicts
    for rec in records:
        assert isinstance(rec, dict)
        assert rec["action"] == "x"


def test_drain_handles_missing_file_gracefully(tmp_path):
    from components.feedback_channel import FeedbackChannel

    ch = FeedbackChannel(path=tmp_path / "missing.jsonl")
    records, offset = ch.drain_new(0)
    assert records == []
    assert offset == 0
