"""Unit tests for LuaCodeCache service."""

import pytest
import tempfile
from pathlib import Path

from services.lua_code_cache import LuaCodeCache


@pytest.fixture
def temp_lua_files():
    """Create temporary Lua files for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create test Lua files
        stable_code = """
function processEvent(event)
    return {status = "processed", version = "stable"}
end
"""
        canary_code = """
function processEvent(event)
    return {status = "processed", version = "canary"}
end
"""

        stable_file = tmpdir_path / "transform.lua"
        stable_file.write_text(stable_code, encoding="utf-8")

        canary_file = tmpdir_path / "transform_canary.lua"
        canary_file.write_text(canary_code, encoding="utf-8")

        yield {
            "tmpdir": tmpdir_path,
            "stable_file": str(stable_file),
            "canary_file": str(canary_file)
        }


class TestLuaCodeCache:
    """Tests for LuaCodeCache."""

    def test_cache_initialization(self):
        """Test cache initializes correctly."""
        cache = LuaCodeCache(max_size=50)

        assert cache.max_size == 50
        assert len(cache.cache) == 0
        assert cache.hits == 0
        assert cache.misses == 0

    def test_load_from_disk(self, temp_lua_files):
        """Test loading Lua code from disk."""
        cache = LuaCodeCache()
        stable_file = temp_lua_files["stable_file"]

        code = cache.get(stable_file, "stable")

        assert code is not None
        assert "processEvent" in code
        assert "stable" in code
        assert cache.misses == 1

    def test_cache_hit(self, temp_lua_files):
        """Test cache hit on subsequent access."""
        cache = LuaCodeCache()
        stable_file = temp_lua_files["stable_file"]

        # First access - cache miss
        code1 = cache.get(stable_file, "stable")
        assert cache.misses == 1
        assert cache.hits == 0

        # Second access - cache hit
        code2 = cache.get(stable_file, "stable")
        assert cache.misses == 1
        assert cache.hits == 1
        assert code1 == code2

    def test_cache_different_versions(self, temp_lua_files):
        """Test caching different versions separately."""
        cache = LuaCodeCache()
        stable_file = temp_lua_files["stable_file"]
        canary_file = temp_lua_files["canary_file"]

        stable_code = cache.get(stable_file, "stable")
        canary_code = cache.get(canary_file, "canary")

        assert stable_code != canary_code
        assert "stable" in stable_code
        assert "canary" in canary_code

    def test_file_not_found(self):
        """Test handling of missing files."""
        cache = LuaCodeCache()

        with pytest.raises(FileNotFoundError):
            cache.get("/nonexistent/file.lua", "stable")

    def test_cache_statistics(self, temp_lua_files):
        """Test cache statistics."""
        cache = LuaCodeCache(max_size=100)
        stable_file = temp_lua_files["stable_file"]

        # Load twice
        cache.get(stable_file, "stable")
        cache.get(stable_file, "stable")

        stats = cache.get_stats()

        assert stats["size"] == 1
        assert stats["max_size"] == 100
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_cache_eviction(self, temp_lua_files):
        """Test LRU eviction when cache is full."""
        cache = LuaCodeCache(max_size=2)
        tmpdir = temp_lua_files["tmpdir"]

        # Create three files
        files = []
        for i in range(3):
            f = tmpdir / f"file{i}.lua"
            f.write_text(f"-- File {i}\nfunction processEvent(e) return {{}} end")
            files.append(str(f))

        # Load all three
        cache.get(files[0], "stable")
        cache.get(files[1], "stable")

        assert len(cache.cache) == 2

        # Loading third should evict first
        cache.get(files[2], "stable")

        assert len(cache.cache) == 2
        assert f"{files[0]}:stable" not in cache.cache
        assert f"{files[1]}:stable" in cache.cache
        assert f"{files[2]}:stable" in cache.cache

    def test_cache_invalidation_single(self, temp_lua_files):
        """Test invalidating single cache entry."""
        cache = LuaCodeCache()
        stable_file = temp_lua_files["stable_file"]

        cache.get(stable_file, "stable")
        cache.get(stable_file, "canary")

        assert len(cache.cache) == 2

        # Invalidate one version
        cache.invalidate(stable_file)

        # Both entries should be gone (file-based)
        assert len(cache.cache) == 0

    def test_cache_invalidation_all(self, temp_lua_files):
        """Test invalidating entire cache."""
        cache = LuaCodeCache()
        stable_file = temp_lua_files["stable_file"]
        canary_file = temp_lua_files["canary_file"]

        cache.get(stable_file, "stable")
        cache.get(canary_file, "canary")

        assert len(cache.cache) == 2

        cache.invalidate()

        assert len(cache.cache) == 0
        assert cache.hits == 0
        assert cache.misses == 2

    def test_file_modification_detection(self, temp_lua_files):
        """Test that modified files are reloaded."""
        cache = LuaCodeCache()
        tmpdir = temp_lua_files["tmpdir"]
        test_file = tmpdir / "test.lua"

        # Write initial content
        test_file.write_text("-- Version 1\nfunction processEvent(e) return {v=1} end")

        code1 = cache.get(str(test_file), "stable")
        assert "v=1" in code1

        # Modify file
        import time
        time.sleep(0.01)  # Ensure mtime changes
        test_file.write_text("-- Version 2\nfunction processEvent(e) return {v=2} end")

        # Should load new content despite cache
        code2 = cache.get(str(test_file), "stable")
        assert "v=2" in code2
        assert code1 != code2

    def test_cache_hit_rate_calculation(self, temp_lua_files):
        """Test hit rate calculation."""
        cache = LuaCodeCache()
        stable_file = temp_lua_files["stable_file"]

        # Access file multiple times
        for _ in range(4):
            cache.get(stable_file, "stable")

        stats = cache.get_stats()

        # 1 miss, 3 hits
        assert stats["misses"] == 1
        assert stats["hits"] == 3
        assert stats["hit_rate"] == 0.75

    def test_zero_hit_rate(self):
        """Test hit rate with no requests."""
        cache = LuaCodeCache()

        stats = cache.get_stats()

        assert stats["hit_rate"] == 0
