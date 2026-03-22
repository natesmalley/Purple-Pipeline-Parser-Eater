#!/usr/bin/env python3
"""
Tests for configurable timeout values
"""

import os
import pytest
from components.dataplane_validator import DataplaneValidator
from components.transform_executor import DataplaneExecutor


class TestDataplaneValidatorTimeout:
    """Test DataplaneValidator timeout configuration"""

    def test_timeout_default(self, tmp_path):
        """Test default timeout value"""
        # Create a fake binary path
        fake_binary = tmp_path / "fake_dataplane"
        fake_binary.write_text("#!/bin/bash\necho 'fake'")

        validator = DataplaneValidator(
            binary_path=str(fake_binary),
            ocsf_required_fields=["class_uid"]
        )

        assert validator.timeout == 30  # DEFAULT_TIMEOUT

    def test_timeout_from_parameter(self, tmp_path):
        """Test timeout can be set via parameter"""
        fake_binary = tmp_path / "fake_dataplane"
        fake_binary.write_text("#!/bin/bash\necho 'fake'")

        validator = DataplaneValidator(
            binary_path=str(fake_binary),
            ocsf_required_fields=["class_uid"],
            timeout=45
        )

        assert validator.timeout == 45

    def test_timeout_from_environment(self, tmp_path, monkeypatch):
        """Test timeout can be set via environment variable"""
        fake_binary = tmp_path / "fake_dataplane"
        fake_binary.write_text("#!/bin/bash\necho 'fake'")

        monkeypatch.setenv('DATAPLANE_VALIDATION_TIMEOUT', '60')

        validator = DataplaneValidator(
            binary_path=str(fake_binary),
            ocsf_required_fields=["class_uid"]
        )

        assert validator.timeout == 60

    def test_timeout_parameter_overrides_environment(self, tmp_path, monkeypatch):
        """Test parameter overrides environment variable"""
        fake_binary = tmp_path / "fake_dataplane"
        fake_binary.write_text("#!/bin/bash\necho 'fake'")

        monkeypatch.setenv('DATAPLANE_VALIDATION_TIMEOUT', '60')

        validator = DataplaneValidator(
            binary_path=str(fake_binary),
            ocsf_required_fields=["class_uid"],
            timeout=45
        )

        assert validator.timeout == 45  # Parameter takes precedence

    def test_timeout_validation_too_small(self, tmp_path):
        """Test timeout validation for values too small"""
        fake_binary = tmp_path / "fake_dataplane"
        fake_binary.write_text("#!/bin/bash\necho 'fake'")

        with pytest.raises(ValueError, match="Timeout must be between"):
            DataplaneValidator(
                binary_path=str(fake_binary),
                ocsf_required_fields=["class_uid"],
                timeout=0  # Too small
            )

    def test_timeout_validation_too_large(self, tmp_path):
        """Test timeout validation for values too large"""
        fake_binary = tmp_path / "fake_dataplane"
        fake_binary.write_text("#!/bin/bash\necho 'fake'")

        with pytest.raises(ValueError, match="Timeout must be between"):
            DataplaneValidator(
                binary_path=str(fake_binary),
                ocsf_required_fields=["class_uid"],
                timeout=500  # Too large
            )

    def test_timeout_invalid_environment(self, tmp_path, monkeypatch, caplog):
        """Test invalid environment variable falls back to default"""
        fake_binary = tmp_path / "fake_dataplane"
        fake_binary.write_text("#!/bin/bash\necho 'fake'")

        monkeypatch.setenv('DATAPLANE_VALIDATION_TIMEOUT', 'invalid')

        validator = DataplaneValidator(
            binary_path=str(fake_binary),
            ocsf_required_fields=["class_uid"]
        )

        assert validator.timeout == 30  # Falls back to default
        assert "Invalid DATAPLANE_VALIDATION_TIMEOUT" in caplog.text


class TestDataplaneExecutorTimeout:
    """Test DataplaneExecutor timeout configuration"""

    def test_timeout_default(self, tmp_path):
        """Test default timeout value"""
        fake_binary = tmp_path / "fake_dataplane"
        fake_binary.write_text("#!/bin/bash\necho 'fake'")

        executor = DataplaneExecutor(binary_path=str(fake_binary))

        assert executor._timeout == 10  # DEFAULT_TIMEOUT

    def test_timeout_from_parameter(self, tmp_path):
        """Test timeout can be set via parameter"""
        fake_binary = tmp_path / "fake_dataplane"
        fake_binary.write_text("#!/bin/bash\necho 'fake'")

        executor = DataplaneExecutor(
            binary_path=str(fake_binary),
            timeout=20
        )

        assert executor._timeout == 20

    def test_timeout_from_environment(self, tmp_path, monkeypatch):
        """Test timeout can be set via environment variable"""
        fake_binary = tmp_path / "fake_dataplane"
        fake_binary.write_text("#!/bin/bash\necho 'fake'")

        monkeypatch.setenv('DATAPLANE_EXECUTION_TIMEOUT', '30')

        executor = DataplaneExecutor(binary_path=str(fake_binary))

        assert executor._timeout == 30

    def test_timeout_parameter_overrides_environment(self, tmp_path, monkeypatch):
        """Test parameter overrides environment variable"""
        fake_binary = tmp_path / "fake_dataplane"
        fake_binary.write_text("#!/bin/bash\necho 'fake'")

        monkeypatch.setenv('DATAPLANE_EXECUTION_TIMEOUT', '30')

        executor = DataplaneExecutor(
            binary_path=str(fake_binary),
            timeout=20
        )

        assert executor._timeout == 20  # Parameter takes precedence

    def test_timeout_validation_too_small(self, tmp_path):
        """Test timeout validation for values too small"""
        fake_binary = tmp_path / "fake_dataplane"
        fake_binary.write_text("#!/bin/bash\necho 'fake'")

        with pytest.raises(ValueError, match="Timeout must be between"):
            DataplaneExecutor(
                binary_path=str(fake_binary),
                timeout=0  # Too small
            )

    def test_timeout_validation_too_large(self, tmp_path):
        """Test timeout validation for values too large"""
        fake_binary = tmp_path / "fake_dataplane"
        fake_binary.write_text("#!/bin/bash\necho 'fake'")

        with pytest.raises(ValueError, match="Timeout must be between"):
            DataplaneExecutor(
                binary_path=str(fake_binary),
                timeout=120  # Too large
            )

    def test_timeout_invalid_environment(self, tmp_path, monkeypatch, caplog):
        """Test invalid environment variable falls back to default"""
        fake_binary = tmp_path / "fake_dataplane"
        fake_binary.write_text("#!/bin/bash\necho 'fake'")

        monkeypatch.setenv('DATAPLANE_EXECUTION_TIMEOUT', 'not_a_number')

        executor = DataplaneExecutor(binary_path=str(fake_binary))

        assert executor._timeout == 10  # Falls back to default
        assert "Invalid DATAPLANE_EXECUTION_TIMEOUT" in caplog.text
