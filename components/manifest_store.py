"""Manifest store for accessing per-parser artifacts.

Loads and caches parser manifests and Lua code with support for
parser aliases, versioning, and cache invalidation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from components.manifest_schema import ParserManifest, validate_manifest

logger = logging.getLogger(__name__)


class ManifestStore:
    """
    Loads manifest and Lua artifacts from the output directory.

    Features:
    - Parser aliases support
    - Manifest caching with version modes (stable/canary)
    - Lua code caching
    - Cache invalidation
    """

    def __init__(self, base_output_dir: str = "output") -> None:
        """
        Initialize manifest store.

        Args:
            base_output_dir: Base directory containing parser output
        """
        self.base_dir = Path(base_output_dir)
        self._manifest_cache: Dict[Tuple[str, str], ParserManifest] = {}
        self._lua_cache: Dict[Tuple[str, str], str] = {}
        self._aliases: Dict[str, str] = {}  # alias -> canonical_id
        self._file_mtimes: Dict[str, float] = {}  # Track file modification times

        logger.info(f"ManifestStore initialized with base_dir={self.base_dir}")

    def _parser_dir(self, parser_id: str) -> Path:
        """Get directory for a parser."""
        # Resolve aliases
        canonical_id = self._aliases.get(parser_id, parser_id)
        return self.base_dir / canonical_id

    def load_manifest(
        self, parser_id: str, mode: str = "stable"
    ) -> Optional[ParserManifest]:
        """
        Load manifest for a parser.

        Args:
            parser_id: Parser ID or alias
            mode: "stable" or "canary"

        Returns:
            ParserManifest or None if not found
        """
        # Resolve aliases
        canonical_id = self._aliases.get(parser_id, parser_id)
        cache_key = (canonical_id, mode)

        # Check cache with file mtime validation
        if cache_key in self._manifest_cache:
            cached = self._manifest_cache[cache_key]
            base_dir = self._parser_dir(canonical_id)

            # Verify file hasn't changed
            candidates = [
                base_dir / f"manifest-{mode}.json",
                base_dir / "manifest.json",
            ]
            manifest_path = next((p for p in candidates if p.exists()), None)

            if manifest_path:
                current_mtime = manifest_path.stat().st_mtime
                if current_mtime == self._file_mtimes.get(str(manifest_path)):
                    logger.debug(f"Manifest cache hit: {cache_key}")
                    return cached

        # Cache miss - load from disk
        base_dir = self._parser_dir(canonical_id)
        candidates = [
            base_dir / f"manifest-{mode}.json",
            base_dir / "manifest.json",
        ]
        manifest_path = next((p for p in candidates if p.exists()), None)

        if not manifest_path:
            logger.warning(f"Manifest not found for {parser_id} (mode={mode})")
            return None

        try:
            with open(manifest_path, "r", encoding="utf-8") as handle:
                manifest_data = json.load(handle)

            manifest = validate_manifest(manifest_data)
            self._manifest_cache[cache_key] = manifest
            self._file_mtimes[str(manifest_path)] = manifest_path.stat().st_mtime

            logger.debug(f"Loaded manifest: {cache_key}")
            return manifest

        except Exception as e:
            logger.error(f"Failed to load manifest from {manifest_path}: {e}")
            return None

    def load_lua(self, parser_id: str, lua_file: str = "transform.lua") -> Optional[str]:
        """
        Load Lua code for a parser.

        Args:
            parser_id: Parser ID or alias
            lua_file: Lua file name

        Returns:
            Lua code as string or None if not found
        """
        # Resolve aliases
        canonical_id = self._aliases.get(parser_id, parser_id)
        cache_key = (canonical_id, lua_file)

        # Check cache with mtime validation
        if cache_key in self._lua_cache:
            lua_path = self._parser_dir(canonical_id) / lua_file

            if lua_path.exists():
                current_mtime = lua_path.stat().st_mtime
                if current_mtime == self._file_mtimes.get(str(lua_path)):
                    logger.debug(f"Lua cache hit: {cache_key}")
                    return self._lua_cache[cache_key]

        # Cache miss - load from disk
        lua_path = self._parser_dir(canonical_id) / lua_file

        if not lua_path.exists():
            logger.warning(f"Lua file not found: {lua_path}")
            return None

        try:
            code = lua_path.read_text(encoding="utf-8")
            self._lua_cache[cache_key] = code
            self._file_mtimes[str(lua_path)] = lua_path.stat().st_mtime

            logger.debug(f"Loaded Lua code: {cache_key}")
            return code

        except Exception as e:
            logger.error(f"Failed to load Lua file {lua_path}: {e}")
            return None

    def register_alias(self, alias: str, canonical_id: str) -> None:
        """
        Register an alias for a parser ID.

        Args:
            alias: Alias name
            canonical_id: Actual parser ID
        """
        self._aliases[alias] = canonical_id
        logger.info(f"Registered alias: {alias} -> {canonical_id}")

    def list_parsers(self) -> List[str]:
        """
        List all available parser IDs.

        Returns:
            List of canonical parser IDs
        """
        if not self.base_dir.exists():
            return []

        parsers = [
            d.name for d in self.base_dir.iterdir()
            if d.is_dir() and (d / "manifest.json").exists()
        ]
        return sorted(parsers)

    def reload(self, parser_id: Optional[str] = None) -> None:
        """
        Reload manifest/Lua cache.

        Args:
            parser_id: Specific parser to reload, or None to reload all
        """
        if parser_id:
            # Resolve aliases
            canonical_id = self._aliases.get(parser_id, parser_id)

            # Clear cache entries for this parser
            keys_to_remove = [
                k for k in self._manifest_cache.keys()
                if k[0] == canonical_id
            ]
            for key in keys_to_remove:
                del self._manifest_cache[key]

            keys_to_remove = [
                k for k in self._lua_cache.keys()
                if k[0] == canonical_id
            ]
            for key in keys_to_remove:
                del self._lua_cache[key]

            logger.info(f"Reloaded cache for parser: {parser_id}")
        else:
            # Clear all caches
            self._manifest_cache.clear()
            self._lua_cache.clear()
            self._file_mtimes.clear()

            logger.info("Cleared all manifest and Lua caches")

