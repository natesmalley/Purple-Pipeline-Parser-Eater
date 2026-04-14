"""Phase 6.D tests for components.state_store.StateStore."""
import asyncio
import threading

import pytest


class TestStateStoreSyncAPI:
    def test_put_and_get_pending(self):
        from components.state_store import StateStore
        s = StateStore()
        s.put_pending("p1", {"lua": "x"})
        assert s.get_pending("p1") == {"lua": "x"}

    def test_pop_pending(self):
        from components.state_store import StateStore
        s = StateStore()
        s.put_pending("p1", {"lua": "x"})
        popped = s.pop_pending("p1")
        assert popped == {"lua": "x"}
        assert s.get_pending("p1") is None

    def test_list_pending(self):
        from components.state_store import StateStore
        s = StateStore()
        s.put_pending("a", 1)
        s.put_pending("b", 2)
        items = dict(s.list_pending())
        assert items == {"a": 1, "b": 2}

    def test_pending_count(self):
        from components.state_store import StateStore
        s = StateStore()
        assert s.pending_count() == 0
        s.put_pending("a", 1)
        s.put_pending("b", 2)
        assert s.pending_count() == 2

    def test_move_pending_to_approved(self):
        from components.state_store import StateStore
        s = StateStore()
        s.put_pending("p1", {"lua": "x"})
        result = s.move_pending_to_approved("p1", overrides={"approved_by": "alice"})
        assert result["approved_by"] == "alice"
        assert s.get_pending("p1") is None
        assert dict(s.list_approved()) == {"p1": {"lua": "x", "approved_by": "alice"}}

    def test_move_pending_to_approved_missing_returns_none(self):
        from components.state_store import StateStore
        s = StateStore()
        assert s.move_pending_to_approved("nope") is None

    def test_move_pending_to_rejected(self):
        from components.state_store import StateStore
        s = StateStore()
        s.put_pending("p1", {"lua": "x"})
        s.move_pending_to_rejected("p1", reason="invalid OCSF")
        assert s.get_pending("p1") is None
        rejected = dict(s.list_rejected())
        assert rejected["p1"]["rejection_reason"] == "invalid OCSF"

    def test_move_pending_to_modified(self):
        from components.state_store import StateStore
        s = StateStore()
        s.put_pending("p1", {"lua": "x"})
        s.move_pending_to_modified("p1", modifications={"lua": "y", "reason": "fix"})
        assert s.get_pending("p1") is None
        modified = dict(s.list_modified())
        assert modified["p1"]["lua"] == "y"
        assert modified["p1"]["reason"] == "fix"

    def test_put_approved_rejected_modified_counts(self):
        from components.state_store import StateStore
        s = StateStore()
        s.put_approved("a", 1)
        s.put_rejected("b", 2)
        s.put_modified("c", 3)
        assert s.approved_count() == 1
        assert s.rejected_count() == 1
        assert s.modified_count() == 1


class TestStateStoreAsyncAPI:
    def test_aput_and_aget(self):
        from components.state_store import StateStore

        async def main():
            s = StateStore()
            await s.aput_pending("p1", {"lua": "x"})
            got = await s.aget_pending("p1")
            assert got == {"lua": "x"}

        asyncio.run(main())

    def test_apop(self):
        from components.state_store import StateStore

        async def main():
            s = StateStore()
            await s.aput_pending("p1", {"lua": "x"})
            popped = await s.apop_pending("p1")
            assert popped == {"lua": "x"}
            assert await s.aget_pending("p1") is None

        asyncio.run(main())

    def test_alist_pending(self):
        from components.state_store import StateStore

        async def main():
            s = StateStore()
            await s.aput_pending("a", 1)
            await s.aput_pending("b", 2)
            items = dict(await s.alist_pending())
            assert items == {"a": 1, "b": 2}

        asyncio.run(main())

    def test_apending_count(self):
        from components.state_store import StateStore

        async def main():
            s = StateStore()
            await s.aput_pending("a", 1)
            assert await s.apending_count() == 1

        asyncio.run(main())

    def test_aput_approved_rejected_modified(self):
        from components.state_store import StateStore

        async def main():
            s = StateStore()
            await s.aput_approved("a", 1)
            await s.aput_rejected("b", 2)
            await s.aput_modified("c", 3)
            assert s.approved_count() == 1
            assert s.rejected_count() == 1
            assert s.modified_count() == 1

        asyncio.run(main())


class TestStateStoreConcurrency:
    def test_sync_threads_and_async_coroutine_dont_race(self):
        """50 sync threads + 50 async coroutines all mutate pending; final
        count must equal total operations. Without the lock, dict mutations
        would race and we'd see lost updates or KeyErrors."""
        from components.state_store import StateStore
        s = StateStore()

        N_THREADS = 50
        N_COROS = 50

        errors = []

        def sync_worker(i: int):
            try:
                s.put_pending(f"sync_{i}", i)
                _ = s.get_pending(f"sync_{i}")
                s.pop_pending(f"sync_{i}")
            except Exception as e:
                errors.append(("sync", i, e))

        async def async_worker(i: int):
            try:
                await s.aput_pending(f"async_{i}", i)
                _ = await s.aget_pending(f"async_{i}")
                await s.apop_pending(f"async_{i}")
            except Exception as e:
                errors.append(("async", i, e))

        threads = [threading.Thread(target=sync_worker, args=(i,)) for i in range(N_THREADS)]
        for t in threads:
            t.start()

        async def run_all_async():
            await asyncio.gather(*(async_worker(i) for i in range(N_COROS)))

        asyncio.run(run_all_async())

        for t in threads:
            t.join()

        assert not errors, f"concurrent ops raised: {errors[:5]}"
        assert s.pending_count() == 0

    def test_snapshot_returns_independent_copy(self):
        from components.state_store import StateStore
        s = StateStore()
        s.put_pending("a", 1)
        snap = s.snapshot()
        # Mutating the snapshot must not affect the store
        snap["pending"]["b"] = 2
        assert s.get_pending("b") is None
        assert set(snap.keys()) == {"pending", "approved", "rejected", "modified"}

    def test_list_returns_snapshot_safe_for_iteration(self):
        """list_pending must be a snapshot — iterating while another thread
        mutates should not raise RuntimeError: dictionary changed size."""
        from components.state_store import StateStore
        s = StateStore()
        for i in range(100):
            s.put_pending(f"k{i}", i)

        stop = threading.Event()
        mutator_errors = []

        def mutator():
            i = 100
            while not stop.is_set():
                try:
                    s.put_pending(f"k{i}", i)
                    s.pop_pending(f"k{i}")
                    i += 1
                except Exception as e:
                    mutator_errors.append(e)
                    return

        t = threading.Thread(target=mutator)
        t.start()
        try:
            for _ in range(50):
                items = s.list_pending()
                # iterate safely
                for k, v in items:
                    _ = (k, v)
        finally:
            stop.set()
            t.join()

        assert not mutator_errors


class TestBackwardCompatProperty:
    def test_service_pending_conversions_attribute(self):
        """Legacy external readers that peek at self.pending_conversions must
        still work via the property shim."""
        try:
            from continuous_conversion_service import ContinuousConversionService
        except Exception as e:
            pytest.skip(f"cannot import service in this venv: {e}")

        # Construct without calling initialize() (avoids heavy deps)
        from pathlib import Path
        svc = ContinuousConversionService(Path("/nonexistent.yaml"))
        assert isinstance(svc.pending_conversions, dict)
        assert isinstance(svc.approved_conversions, dict)
        assert isinstance(svc.rejected_conversions, dict)
        assert isinstance(svc.modified_conversions, dict)
        assert svc.pending_conversions == {}

    def test_state_store_module_has_no_heavy_imports(self):
        """Heavy-loaded check — importing state_store must not drag in flask,
        anthropic, aiohttp, numpy, yaml."""
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, "-c",
             "import components.state_store; import sys; "
             "bad=[m for m in ('aiohttp','anthropic','flask','numpy','yaml') if m in sys.modules]; "
             "print('heavy:', bad); sys.exit(1 if bad else 0)"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"heavy imports: {result.stdout} {result.stderr}"
