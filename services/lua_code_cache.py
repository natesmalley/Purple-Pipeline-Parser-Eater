"""In-memory cache for Lua transformation code.

Caches Lua code to avoid repeated disk reads during high-throughput
event processing. Tracks file modification times for cache invalidation.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class LuaCodeCache:
    """
    In-memory cache for Lua transformation code.

    Cache key format: f"{file_path}:{version}"
    Automatically invalidates entries when files change.
    """

    def __init__(self, max_size: int = 100) -> None:
        """
        Initialize the Lua code cache.

        Args:
            max_size: Maximum number of cache entries before LRU eviction
        """
        self.cache: Dict[str, Dict] = {}
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
        logger.debug(f"LuaCodeCache initialized with max_size={max_size}")

    def get(self, file_path: str, version: str = "stable") -> str:
        """
        Get Lua code from cache or load from disk.

        Args:
            file_path: Path to transform.lua file
            version: "stable" or "canary"

        Returns:
            Lua code as string

        Raises:
            FileNotFoundError: If Lua file doesn't exist
        """
        cache_key = f"{file_path}:{version}"

        # Check cache
        if cache_key in self.cache:
            cached = self.cache[cache_key]

            # Verify file hasn't changed
            file_path_obj = Path(file_path)
            if file_path_obj.exists():
                current_mtime = file_path_obj.stat().st_mtime
                if current_mtime == cached["mtime"]:
                    self.hits += 1
                    logger.debug(f"Cache hit: {cache_key}")
                    return cached["code"]

        # Cache miss - load from disk
        self.misses += 1
        logger.debug(f"Cache miss: {cache_key}")

        lua_code = self._load_from_disk(file_path)

        # Store in cache
        self._put(cache_key, lua_code, file_path)

        return lua_code

    def _load_from_disk(self, file_path: str) -> str:
        """Load Lua code from disk.

        Args:
            file_path: Path to Lua file

        Returns:
            File contents as string

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        file_path_obj = Path(file_path)

        if not file_path_obj.exists():
            raise FileNotFoundError(f"Lua file not found: {file_path}")

        with open(file_path_obj, "r", encoding="utf-8") as f:
            return f.read()

    def _put(self, cache_key: str, code: str, file_path: str) -> None:
        """Store Lua code in cache.

        Evicts oldest entry if cache exceeds max_size.

        Args:
            cache_key: Cache key (file_path:version)
            code: Lua source code
            file_path: Path to source file
        """
        # Evict oldest entry if cache is full
        if len(self.cache) >= self.max_size:
            oldest_key = min(
                self.cache.keys(),
                key=lambda k: self.cache[k]["accessed"]
            )
            del self.cache[oldest_key]
            logger.debug(f"Evicted from cache: {oldest_key}")

        file_path_obj = Path(file_path)
        mtime = file_path_obj.stat().st_mtime if file_path_obj.exists() else 0

        self.cache[cache_key] = {
            "code": code,
            "mtime": mtime,
            "accessed": datetime.utcnow()
        }

    def invalidate(self, file_path: Optional[str] = None) -> None:
        """
        Invalidate cache entries.

        Args:
            file_path: Specific file to invalidate, or None to clear all
        """
        if file_path:
            keys_to_remove = [
                k for k in self.cache.keys()
                if k.startswith(f"{file_path}:")
            ]
            for key in keys_to_remove:
                del self.cache[key]
            logger.info(f"Invalidated cache for: {file_path}")
        else:
            self.cache.clear()
            logger.info("Cache cleared")

    def get_stats(self) -> Dict:
        """Get cache statistics.

        Returns:
            Dictionary with size, max_size, hits, misses, hit_rate
        """
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(hit_rate, 3)
        }
