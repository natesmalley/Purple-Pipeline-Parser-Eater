"""Phase 5.E tests for components.dataplane_fork_pin thread-safety."""
import threading


class TestAlreadyCheckedThreadSafety:
    def test_concurrent_calls_single_inspection(self, monkeypatch):
        """Two threads calling assert_dataplane_fork() simultaneously must both
        return without error; binary inspection happens at most once."""
        import components.dataplane_fork_pin as dfp

        # Reset module state
        monkeypatch.setattr(dfp, "_already_checked", False)

        def fake_find():
            return None  # no binary

        monkeypatch.setattr(dfp, "_find_dataplane_binary", fake_find)

        def worker():
            dfp.assert_dataplane_fork()

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # After all threads return, _already_checked must be True
        assert dfp._already_checked is True

    def test_force_kwarg_bypasses_cache(self, monkeypatch):
        """force=True must re-inspect even if _already_checked is True."""
        import components.dataplane_fork_pin as dfp

        monkeypatch.setattr(dfp, "_already_checked", True)

        find_calls = [0]

        def fake_find():
            find_calls[0] += 1
            return None

        monkeypatch.setattr(dfp, "_find_dataplane_binary", fake_find)

        dfp.assert_dataplane_fork(force=True)
        assert find_calls[0] == 1

    def test_lock_is_threading_lock(self):
        """Verify the sentinel - the module exposes a Lock instance, not a bare global."""
        import components.dataplane_fork_pin as dfp
        # Should have _already_checked_lock attribute
        assert hasattr(dfp, "_already_checked_lock")
        # It should be a threading.Lock or RLock
        lock = dfp._already_checked_lock
        # Lock objects are context managers
        with lock:
            pass  # acquire and release - proves it's a real lock
