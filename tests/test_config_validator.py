"""Tests for configuration validator."""

from __future__ import annotations

import os
import pytest

from utils.config_validator import ConfigValidator


class TestConfigValidator:
    """Test configuration validator."""

    def test_validator_initialization(self) -> None:
        """Test validator initialization."""
        validator = ConfigValidator(is_production=False)
        assert validator.is_production is False
        assert validator.errors == []
        assert validator.warnings == []

    def test_validator_production_flag(self) -> None:
        """Test production flag."""
        validator = ConfigValidator(is_production=True)
        assert validator.is_production is True

    def test_validate_required_vars_present(self) -> None:
        """Test validation passes when required vars present."""
        os.environ["TEST_VAR_1"] = "value1"
        os.environ["TEST_VAR_2"] = "value2"

        validator = ConfigValidator()
        result = validator.validate_required_vars(["TEST_VAR_1", "TEST_VAR_2"])

        assert result is True
        assert len(validator.errors) == 0

        # Cleanup
        del os.environ["TEST_VAR_1"]
        del os.environ["TEST_VAR_2"]

    def test_validate_required_vars_missing(self) -> None:
        """Test validation fails when required vars missing."""
        validator = ConfigValidator()
        result = validator.validate_required_vars(["NONEXISTENT_VAR_1"])

        assert result is False
        assert len(validator.errors) > 0
        assert "NONEXISTENT_VAR_1" in validator.errors[0]

    def test_check_token_strength_valid(self) -> None:
        """Test token strength check with valid token."""
        validator = ConfigValidator()
        result = validator.check_token_strength(
            "TEST_TOKEN",
            "sk-ant-valid-token-12345678901234567890"
        )

        assert result is True
        assert len(validator.errors) == 0

    def test_check_token_strength_weak_changeme(self) -> None:
        """Test token strength detects 'changeme' pattern."""
        validator = ConfigValidator()
        result = validator.check_token_strength("TEST_TOKEN", "changeme123456")

        assert result is False
        assert len(validator.errors) > 0
        assert "weak pattern" in validator.errors[0].lower()

    def test_check_token_strength_weak_test(self) -> None:
        """Test token strength detects 'test' pattern."""
        validator = ConfigValidator()
        result = validator.check_token_strength("TEST_TOKEN", "test12345678")

        assert result is False
        assert "weak pattern" in validator.errors[0].lower()

    def test_check_token_strength_weak_demo(self) -> None:
        """Test token strength detects 'demo' pattern."""
        validator = ConfigValidator()
        result = validator.check_token_strength("TEST_TOKEN", "demo12345678")

        assert result is False

    def test_check_token_strength_too_short(self) -> None:
        """Test token strength detects short tokens."""
        validator = ConfigValidator()
        result = validator.check_token_strength("TEST_TOKEN", "short")

        assert result is False
        assert "too short" in validator.errors[0].lower()

    def test_check_token_strength_empty(self) -> None:
        """Test token strength detects empty tokens."""
        validator = ConfigValidator()
        result = validator.check_token_strength("TEST_TOKEN", "")

        assert result is False

    def test_check_token_strength_none(self) -> None:
        """Test token strength detects None tokens."""
        validator = ConfigValidator()
        result = validator.check_token_strength("TEST_TOKEN", None)

        assert result is False

    def test_validate_api_key_format_github(self) -> None:
        """Test GitHub API key format validation."""
        validator = ConfigValidator()
        # SECURITY NOTE: This is a test token value for format validation, not a real credential
        # Valid GitHub token format (test value)
        valid_token = "ghp_1234567890abcdefghij1234567890abcdef"  # Test token for format validation
        result = validator.validate_api_key_format(
            "GITHUB_TOKEN",
            valid_token,
            "github_token"
        )

        assert result is True

    def test_validate_api_key_format_github_invalid(self) -> None:
        """Test invalid GitHub API key format."""
        validator = ConfigValidator()
        invalid_token = "not-a-github-token"
        result = validator.validate_api_key_format(
            "GITHUB_TOKEN",
            invalid_token,
            "github_token"
        )

        assert result is True  # Warning, not error
        assert len(validator.warnings) > 0

    def test_validate_api_key_format_unknown_type(self) -> None:
        """Test unknown key type defaults to token strength check."""
        validator = ConfigValidator()
        result = validator.validate_api_key_format(
            "UNKNOWN_KEY",
            "validtoken123456789",
            "unknown_type"
        )

        assert result is True

    def test_validate_api_key_format_missing(self) -> None:
        """Test missing API key."""
        validator = ConfigValidator()
        result = validator.validate_api_key_format(
            "GITHUB_TOKEN",
            None,
            "github_token"
        )

        assert result is False

    def test_check_production_requirements_development(self) -> None:
        """Test production checks skip in development."""
        validator = ConfigValidator(is_production=False)
        result = validator.check_production_requirements()

        assert result is True
        assert len(validator.errors) == 0

    def test_check_production_requirements_debug_enabled(self) -> None:
        """Test production check detects debug mode."""
        os.environ["DEBUG"] = "true"

        validator = ConfigValidator(is_production=True)
        result = validator.check_production_requirements()

        assert result is False
        assert any("DEBUG" in e for e in validator.errors)

        del os.environ["DEBUG"]

    def test_check_production_requirements_missing_allowed_hosts(self) -> None:
        """Test production check for ALLOWED_HOSTS."""
        # Remove ALLOWED_HOSTS if present
        if "ALLOWED_HOSTS" in os.environ:
            del os.environ["ALLOWED_HOSTS"]

        validator = ConfigValidator(is_production=True)
        result = validator.check_production_requirements()

        assert result is False
        assert any("ALLOWED_HOSTS" in e for e in validator.errors)

    def test_check_production_requirements_wildcard_allowed_hosts(self) -> None:
        """Test production check rejects wildcard ALLOWED_HOSTS."""
        os.environ["ALLOWED_HOSTS"] = "*"

        validator = ConfigValidator(is_production=True)
        result = validator.check_production_requirements()

        assert result is False
        assert any("ALLOWED_HOSTS" in e for e in validator.errors)

        del os.environ["ALLOWED_HOSTS"]

    def test_check_production_requirements_https_required(self) -> None:
        """Test production check requires HTTPS."""
        os.environ["ALLOWED_HOSTS"] = "example.com"
        if "USE_HTTPS" in os.environ:
            del os.environ["USE_HTTPS"]

        validator = ConfigValidator(is_production=True)
        result = validator.check_production_requirements()

        assert result is False
        assert any("HTTPS" in e for e in validator.errors)

        del os.environ["ALLOWED_HOSTS"]

    def test_validate_all_success(self) -> None:
        """Test complete validation succeeds."""
        os.environ["REQUIRED_VAR"] = "value"
        os.environ["TOKEN_VAR"] = "validtoken123456789"

        validator = ConfigValidator(is_production=False)
        valid, errors, warnings = validator.validate_all(
            required_vars=["REQUIRED_VAR"],
            token_vars={"TEST_TOKEN": "TOKEN_VAR"}
        )

        assert valid is True
        assert len(errors) == 0

        del os.environ["REQUIRED_VAR"]
        del os.environ["TOKEN_VAR"]

    def test_validate_all_missing_required(self) -> None:
        """Test complete validation fails with missing required vars."""
        validator = ConfigValidator()
        valid, errors, warnings = validator.validate_all(
            required_vars=["NONEXISTENT_VAR"]
        )

        assert valid is False
        assert len(errors) > 0

    def test_validate_all_weak_token(self) -> None:
        """Test complete validation fails with weak token."""
        os.environ["REQUIRED_VAR"] = "value"
        os.environ["TOKEN_VAR"] = "test123456"

        validator = ConfigValidator()
        valid, errors, warnings = validator.validate_all(
            required_vars=["REQUIRED_VAR"],
            token_vars={"TEST_TOKEN": "TOKEN_VAR"}
        )

        assert valid is False
        assert len(errors) > 0

        del os.environ["REQUIRED_VAR"]
        del os.environ["TOKEN_VAR"]

    def test_get_report_no_errors(self) -> None:
        """Test report generation with no errors."""
        validator = ConfigValidator()
        report = validator.get_report()

        assert "Configuration Validation Report" in report
        assert "PASS" in report

    def test_get_report_with_errors(self) -> None:
        """Test report generation with errors."""
        validator = ConfigValidator()
        validator.errors.append("Test error 1")
        validator.errors.append("Test error 2")

        report = validator.get_report()

        assert "Test error 1" in report
        assert "Test error 2" in report
        assert "FAIL" in report

    def test_get_report_with_warnings(self) -> None:
        """Test report generation with warnings."""
        validator = ConfigValidator()
        validator.warnings.append("Test warning")

        report = validator.get_report()

        assert "Test warning" in report
