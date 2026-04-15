"""Stream A2.f — StateStore follower mode hot-reload."""
from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest import mock

import pytest


def test_portalocker_dependency_available():
    import portalocker  # noqa: F401


def test_follower_hot_reloads_on_external_write(tmp_path):
    from components.state_store import StateStore

    path = tmp_path / "state.json"
    writer = StateStore(persist_path=path, follower=False)
    follower = StateStore(persist_path=path, follower=True)

    writer.put_pending("x", {"v": 1})
    # ensure mtime advances on coarse-grained filesystems
    time.sleep(0.01)

    items = dict(follower.list_pending())
    assert items == {"x": {"v": 1}}


def test_follower_reload_only_when_mtime_newer(tmp_path):
    from components.state_store import StateStore

    path = tmp_path / "state.json"
    writer = StateStore(persist_path=path)
    writer.put_pending("x", {"v": 1})

    follower = StateStore(persist_path=path, follower=True)
    # First read primes
    follower.list_pending()

    with mock.patch.object(
        StateStore, "_load_from_disk", autospec=True, side_effect=StateStore._load_from_disk
    ) as spy:
        # No external write -> no reload
        follower.list_pending()
        follower.list_pending()
        assert spy.call_count == 0


def test_non_follower_does_not_reload(tmp_path):
    from components.state_store import StateStore

    path = tmp_path / "state.json"
    writer = StateStore(persist_path=path)
    writer.put_pending("x", {"v": 1})

    reader = StateStore(persist_path=path, follower=False)
    # External writer adds something
    writer.put_pending("y", {"v": 2})
    time.sleep(0.01)
    items = dict(reader.list_pending())
    # Non-follower should NOT see external write
    assert "y" not in items


def test_follower_write_bounded_residual_race(tmp_path):
    """Bounded invariants for the documented residual race window."""
    from components.state_store import StateStore

    path = tmp_path / "state.json"
    seed = StateStore(persist_path=path)
    seed.put_pending("untouched", {"v": "original"})
    time.sleep(0.01)

    worker = StateStore(persist_path=path, follower=False)
    web = StateStore(persist_path=path, follower=True)

    barrier = threading.Barrier(2)

    def worker_write():
        barrier.wait()
        worker.put_pending("worker_only", {"by": "worker"})

    def web_write():
        barrier.wait()
        web.put_pending("web_only", {"by": "web"})

    t1 = threading.Thread(target=worker_write)
    t2 = threading.Thread(target=web_write)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # 1. Snapshot parses successfully (atomic-rename guarantee)
    import json
    raw = path.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    assert "pending" in parsed

    # 2. The on-disk snapshot contains the dict shape of at least one writer
    pending = parsed["pending"]
    assert ("worker_only" in pending) or ("web_only" in pending)

    # 3. The untouched key is still present in final snapshot
    assert "untouched" in pending
    assert pending["untouched"] == {"v": "original"}

    # 4. Fresh follower load matches disk exactly
    fresh = StateStore(persist_path=path, follower=True)
    snapshot = fresh.snapshot()
    assert snapshot["pending"] == pending

    # 5. Web's next list_pending hot-reloads to disk truth
    web_view = dict(web.list_pending())
    assert web_view == pending
