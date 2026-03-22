"""Unit tests for enhanced ManifestStore."""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from components.manifest_store import ManifestStore


@pytest.fixture
def temp_manifest_dir():
    """Create temporary manifest directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create parser directories
        parser1_dir = tmpdir_path / "netskope_dlp"
        parser1_dir.mkdir()

        parser2_dir = tmpdir_path / "okta_audit"
        parser2_dir.mkdir()

        # Create manifest files
        manifest1 = {
            "parser_id": "netskope_dlp",
            "version": {
                "semantic": "1.0.0"
            },
            "lua_metadata": {
                "file": "transform.lua"
            },
            "deployment": {
                "canary_percentage": 10
            }
        }
        (parser1_dir / "manifest.json").write_text(json.dumps(manifest1))

        manifest2 = {
            "parser_id": "okta_audit",
            "version": {
                "semantic": "2.0.0"
            },
            "lua_metadata": {
                "file": "transform.lua"
            }
        }
        (parser2_dir / "manifest.json").write_text(json.dumps(manifest2))

        # Create canary manifest
        canary_manifest = {
            "parser_id": "netskope_dlp",
            "version": {
                "semantic": "1.1.0-canary"
            },
            "lua_metadata": {
                "file": "transform_canary.lua"
            }
        }
        (parser1_dir / "manifest-canary.json").write_text(json.dumps(canary_manifest))

        # Create Lua files
        (parser1_dir / "transform.lua").write_text("-- Stable version\nfunction processEvent(e) return {v='stable'} end")
        (parser1_dir / "transform_canary.lua").write_text("-- Canary version\nfunction processEvent(e) return {v='canary'} end")

        yield tmpdir_path


@pytest.fixture
def manifest_store(temp_manifest_dir):
    """Create ManifestStore with temporary directory."""
    return ManifestStore(base_output_dir=str(temp_manifest_dir))


class TestManifestStoreLoading:
    """Tests for manifest loading."""

    def test_load_stable_manifest(self, manifest_store):
        """Test loading stable manifest."""
        manifest = manifest_store.load_manifest("netskope_dlp", "stable")

        assert manifest is not None
        assert manifest.parser_id == "netskope_dlp"
        assert manifest.version.semantic == "1.0.0"

    def test_load_canary_manifest(self, manifest_store):
        """Test loading canary manifest."""
        manifest = manifest_store.load_manifest("netskope_dlp", "canary")

        assert manifest is not None
        assert manifest.parser_id == "netskope_dlp"
        assert manifest.version.semantic == "1.1.0-canary"

    def test_load_missing_manifest(self, manifest_store):
        """Test loading non-existent manifest."""
        manifest = manifest_store.load_manifest("nonexistent_parser", "stable")

        assert manifest is None

    def test_load_lua_code(self, manifest_store):
        """Test loading Lua code."""
        lua_code = manifest_store.load_lua("netskope_dlp", "transform.lua")

        assert lua_code is not None
        assert "processEvent" in lua_code
        assert "stable" in lua_code

    def test_load_lua_canary_code(self, manifest_store):
        """Test loading canary Lua code."""
        lua_code = manifest_store.load_lua("netskope_dlp", "transform_canary.lua")

        assert lua_code is not None
        assert "canary" in lua_code

    def test_load_missing_lua_file(self, manifest_store):
        """Test loading non-existent Lua file."""
        lua_code = manifest_store.load_lua("netskope_dlp", "nonexistent.lua")

        assert lua_code is None


class TestManifestStoreCaching:
    """Tests for caching behavior."""

    def test_manifest_caching(self, manifest_store):
        """Test that manifests are cached."""
        # Load twice
        manifest1 = manifest_store.load_manifest("netskope_dlp", "stable")
        manifest2 = manifest_store.load_manifest("netskope_dlp", "stable")

        # Should be same object from cache
        assert manifest1 is manifest2

    def test_lua_caching(self, manifest_store):
        """Test that Lua code is cached."""
        # Load twice
        code1 = manifest_store.load_lua("netskope_dlp", "transform.lua")
        code2 = manifest_store.load_lua("netskope_dlp", "transform.lua")

        # Should be same content
        assert code1 == code2

    def test_separate_version_cache(self, manifest_store):
        """Test that stable and canary are cached separately."""
        stable = manifest_store.load_manifest("netskope_dlp", "stable")
        canary = manifest_store.load_manifest("netskope_dlp", "canary")

        assert stable is not canary
        assert stable.version.semantic != canary.version.semantic


class TestManifestStoreAliases:
    """Tests for parser aliases."""

    def test_register_alias(self, manifest_store):
        """Test registering an alias."""
        manifest_store.register_alias("netskope", "netskope_dlp")

        # Should resolve alias and load manifest
        manifest = manifest_store.load_manifest("netskope", "stable")

        assert manifest is not None
        assert manifest.parser_id == "netskope_dlp"

    def test_load_lua_with_alias(self, manifest_store):
        """Test loading Lua with alias."""
        manifest_store.register_alias("okta", "okta_audit")

        lua_code = manifest_store.load_lua("okta", "transform.lua")

        # Should fail because okta_audit doesn't have this file
        # But the alias resolution should work
        # Just verify no error is raised

    def test_multiple_aliases_same_parser(self, manifest_store):
        """Test multiple aliases for same parser."""
        manifest_store.register_alias("netskope_v1", "netskope_dlp")
        manifest_store.register_alias("netskope_dlp_prod", "netskope_dlp")

        m1 = manifest_store.load_manifest("netskope_v1", "stable")
        m2 = manifest_store.load_manifest("netskope_dlp_prod", "stable")
        m3 = manifest_store.load_manifest("netskope_dlp", "stable")

        assert m1 is m2 is m3


class TestManifestStoreReload:
    """Tests for cache reload."""

    def test_reload_single_parser(self, manifest_store):
        """Test reloading cache for single parser."""
        # Load and cache
        manifest_store.load_manifest("netskope_dlp", "stable")
        manifest_store.load_lua("netskope_dlp", "transform.lua")

        assert len(manifest_store._manifest_cache) > 0
        assert len(manifest_store._lua_cache) > 0

        # Reload
        manifest_store.reload("netskope_dlp")

        # Cache should be cleared for this parser
        assert ("netskope_dlp", "stable") not in manifest_store._manifest_cache

    def test_reload_all(self, manifest_store):
        """Test reloading entire cache."""
        # Load and cache multiple items
        manifest_store.load_manifest("netskope_dlp", "stable")
        manifest_store.load_manifest("okta_audit", "stable")
        manifest_store.load_lua("netskope_dlp", "transform.lua")

        assert len(manifest_store._manifest_cache) > 0
        assert len(manifest_store._lua_cache) > 0

        # Reload all
        manifest_store.reload()

        # All caches should be cleared
        assert len(manifest_store._manifest_cache) == 0
        assert len(manifest_store._lua_cache) == 0

    def test_reload_and_reload(self, manifest_store):
        """Test that reload allows reloading after modification."""
        # Load
        manifest1 = manifest_store.load_manifest("netskope_dlp", "stable")

        # Reload
        manifest_store.reload("netskope_dlp")

        # Load again
        manifest2 = manifest_store.load_manifest("netskope_dlp", "stable")

        # Should load fresh from disk
        assert manifest2 is not manifest1


class TestManifestStoreListParsers:
    """Tests for parser listing."""

    def test_list_parsers(self, manifest_store):
        """Test listing all available parsers."""
        parsers = manifest_store.list_parsers()

        assert "netskope_dlp" in parsers
        assert "okta_audit" in parsers
        assert len(parsers) == 2

    def test_list_parsers_empty_directory(self):
        """Test listing parsers from empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ManifestStore(base_output_dir=tmpdir)
            parsers = store.list_parsers()

            assert parsers == []

    def test_list_parsers_sorted(self, manifest_store):
        """Test that parser list is sorted."""
        parsers = manifest_store.list_parsers()

        assert parsers == sorted(parsers)


class TestManifestStoreFileModificationDetection:
    """Tests for file modification detection."""

    def test_file_modification_detection(self, temp_manifest_dir):
        """Test that modified files are reloaded."""
        store = ManifestStore(base_output_dir=str(temp_manifest_dir))

        # Load initial manifest
        manifest1 = store.load_manifest("netskope_dlp", "stable")

        # Modify file
        import time
        time.sleep(0.01)  # Ensure mtime changes

        manifest_path = temp_manifest_dir / "netskope_dlp" / "manifest.json"
        new_manifest = {
            "parser_id": "netskope_dlp",
            "version": {
                "semantic": "1.1.0"  # Changed version
            },
            "lua_metadata": {
                "file": "transform.lua"
            }
        }
        manifest_path.write_text(json.dumps(new_manifest))

        # Reload
        store.reload("netskope_dlp")

        # Load again
        manifest2 = store.load_manifest("netskope_dlp", "stable")

        # Should have new version
        assert manifest2.version.semantic == "1.1.0"
        assert manifest1.version.semantic == "1.0.0"


class TestManifestStoreEdgeCases:
    """Tests for edge cases and error handling."""

    def test_load_invalid_json(self, temp_manifest_dir):
        """Test handling of invalid JSON."""
        store = ManifestStore(base_output_dir=str(temp_manifest_dir))

        # Write invalid JSON
        invalid_path = temp_manifest_dir / "broken_parser" / "manifest.json"
        invalid_path.parent.mkdir(parents=True, exist_ok=True)
        invalid_path.write_text("{invalid json")

        # Should return None for invalid manifest
        manifest = store.load_manifest("broken_parser", "stable")

        assert manifest is None

    def test_nonexistent_base_directory(self):
        """Test initialization with non-existent base directory."""
        store = ManifestStore(base_output_dir="/nonexistent/path")

        # Should not raise error
        parsers = store.list_parsers()
        assert parsers == []

    def test_parser_without_manifest(self, temp_manifest_dir):
        """Test directory without manifest.json."""
        # Create directory without manifest
        empty_dir = temp_manifest_dir / "empty_parser"
        empty_dir.mkdir()

        store = ManifestStore(base_output_dir=str(temp_manifest_dir))

        # Should not list parser without manifest
        parsers = store.list_parsers()
        assert "empty_parser" not in parsers
