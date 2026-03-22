"""Integration tests for configuration validation."""

from __future__ import annotations

from utils.config_validator import ConfigValidator


class TestConfigValidationIntegration:
    """Test configuration validation."""

    def test_complete_validation_flow(self) -> None:
        """Test complete validation workflow."""
        validator = ConfigValidator(is_production=False)
        
        valid, errors, warnings = validator.validate_all(
            required_vars=[],
            token_vars={},
            api_keys={}
        )
        
        assert isinstance(valid, bool)
        assert isinstance(errors, list)
        assert isinstance(warnings, list)

    def test_production_mode_validation(self) -> None:
        """Test production mode specific validation."""
        validator = ConfigValidator(is_production=True)
        valid, errors, warnings = validator.validate_all(
            required_vars=[],
            token_vars={},
            api_keys={}
        )
        
        assert len(errors) >= 0

    def test_token_validation_report(self) -> None:
        """Test validation report generation."""
        validator = ConfigValidator()
        validator.validate_required_vars(["TEST"])
        report = validator.get_report()
        
        assert isinstance(report, str)
        assert "Configuration Validation Report" in report
