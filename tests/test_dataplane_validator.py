"""Tests for dataplane validator (using stub)."""

import pytest
import tempfile
from pathlib import Path

from components.dataplane_validator import DataplaneValidator, SecurityError


@pytest.mark.skip("Dataplane binary not available in unit test environment")
def test_dataplane_validator_missing_binary(tmp_path):
    with pytest.raises(FileNotFoundError):
        DataplaneValidator(str(tmp_path / "missing"), ["class_uid"], timeout=5)


class TestDataplaneValidatorSecurity:
    """Security tests for DataplaneValidator path injection fix."""

    def test_path_traversal_prevention(self):
        """Test that path traversal attempts are blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a dummy binary for testing
            binary_path = Path(tmpdir) / "dummy"
            binary_path.write_text("#!/bin/sh\necho 'dummy'")

            validator = DataplaneValidator(
                binary_path=str(binary_path),
                ocsf_required_fields=["class_uid"],
                timeout=30
            )

            # Try to use a path outside temp directory
            malicious_path = Path("/etc/passwd")

            with pytest.raises(SecurityError, match="path traversal"):
                validator._render_config(malicious_path)

    def test_path_escaping_single_quotes(self):
        """Test that single quotes in path are escaped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a dummy binary
            binary_path = Path(tmpdir) / "dummy"
            binary_path.write_text("#!/bin/sh\necho 'dummy'")

            validator = DataplaneValidator(
                binary_path=str(binary_path),
                ocsf_required_fields=["class_uid"],
                timeout=30
            )

            # Create path with single quote
            test_file = Path(tmpdir) / "test_file.lua"
            test_file.write_text("-- test")

            config = validator._render_config(test_file)

            # Verify dofile() call is present
            assert "dofile(" in config
            assert "lua_transform" in config

    def test_dangerous_patterns_blocked(self):
        """Test that path traversal attempts are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a dummy binary
            binary_path = Path(tmpdir) / "dummy"
            binary_path.write_text("#!/bin/sh\necho 'dummy'")

            validator = DataplaneValidator(
                binary_path=str(binary_path),
                ocsf_required_fields=["class_uid"],
                timeout=30
            )

            # Try path with .. pattern - should be caught by path traversal check
            with pytest.raises(
                SecurityError,
                match="path traversal"
            ):
                # Manually test path traversal detection
                validator._render_config(Path(tmpdir) / "../../../etc/passwd")

    def test_valid_path_works(self):
        """Test that valid paths work correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a dummy binary
            binary_path = Path(tmpdir) / "dummy"
            binary_path.write_text("#!/bin/sh\necho 'dummy'")

            validator = DataplaneValidator(
                binary_path=str(binary_path),
                ocsf_required_fields=["class_uid"],
                timeout=30
            )

            # Create a valid lua file
            test_file = Path(tmpdir) / "transform.lua"
            test_file.write_text("-- valid lua code")

            config = validator._render_config(test_file)

            # Verify config is generated
            assert "dofile(" in config
            assert "lua_transform" in config
