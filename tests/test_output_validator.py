"""Unit tests for OutputValidator."""

import pytest

from components.output_validator import OutputValidator


@pytest.fixture
def validator():
    """Create validator instance."""
    return OutputValidator(strict_mode=False)


@pytest.fixture
def valid_ocsf_event():
    """Create a valid OCSF event."""
    return {
        "class_uid": 2004,
        "class_name": "Detection Finding",
        "category_uid": 2,
        "severity_id": 4,
        "time": 1699363200000,
        "metadata": {
            "version": "1.5.0",
            "product": {
                "name": "Netskope",
                "vendor_name": "Netskope"
            }
        }
    }


class TestOutputValidator:
    """Test OutputValidator class."""

    def test_initialization(self, validator):
        """Test validator initializes correctly."""
        assert validator is not None
        assert validator.strict_mode is False
        assert validator.stats["total_validated"] == 0

    def test_valid_event(self, validator, valid_ocsf_event):
        """Test validation of valid OCSF event."""
        result = validator.validate_ocsf(valid_ocsf_event)
        assert result is True
        assert validator.stats["passed"] == 1
        assert validator.stats["failed"] == 0

    def test_missing_class_uid(self, validator, valid_ocsf_event):
        """Test validation fails when class_uid is missing."""
        del valid_ocsf_event["class_uid"]
        result = validator.validate_ocsf(valid_ocsf_event)
        assert result is False
        assert validator.stats["failed"] == 1

    def test_missing_category_uid(self, validator, valid_ocsf_event):
        """Test validation fails when category_uid is missing."""
        del valid_ocsf_event["category_uid"]
        result = validator.validate_ocsf(valid_ocsf_event)
        assert result is False

    def test_missing_severity_id(self, validator, valid_ocsf_event):
        """Test validation fails when severity_id is missing."""
        del valid_ocsf_event["severity_id"]
        result = validator.validate_ocsf(valid_ocsf_event)
        assert result is False

    def test_missing_time(self, validator, valid_ocsf_event):
        """Test validation fails when time is missing."""
        del valid_ocsf_event["time"]
        result = validator.validate_ocsf(valid_ocsf_event)
        assert result is False

    def test_missing_metadata(self, validator, valid_ocsf_event):
        """Test validation fails when metadata is missing."""
        del valid_ocsf_event["metadata"]
        result = validator.validate_ocsf(valid_ocsf_event)
        assert result is False

    def test_missing_metadata_version(self, validator, valid_ocsf_event):
        """Test validation fails when metadata.version is missing."""
        del valid_ocsf_event["metadata"]["version"]
        result = validator.validate_ocsf(valid_ocsf_event)
        assert result is False

    def test_missing_metadata_product(self, validator, valid_ocsf_event):
        """Test validation fails when metadata.product is missing."""
        del valid_ocsf_event["metadata"]["product"]
        result = validator.validate_ocsf(valid_ocsf_event)
        assert result is False

    def test_invalid_class_uid_type(self, validator, valid_ocsf_event):
        """Test validation fails when class_uid is not integer."""
        valid_ocsf_event["class_uid"] = "2004"
        result = validator.validate_ocsf(valid_ocsf_event)
        assert result is False

    def test_invalid_category_uid_type(self, validator, valid_ocsf_event):
        """Test validation fails when category_uid is not integer."""
        valid_ocsf_event["category_uid"] = "2"
        result = validator.validate_ocsf(valid_ocsf_event)
        assert result is False

    def test_invalid_severity_id_type(self, validator, valid_ocsf_event):
        """Test validation fails when severity_id is not integer."""
        valid_ocsf_event["severity_id"] = "4"
        result = validator.validate_ocsf(valid_ocsf_event)
        assert result is False

    def test_invalid_time_type(self, validator, valid_ocsf_event):
        """Test validation fails when time is not numeric."""
        valid_ocsf_event["time"] = "2025-11-07T12:00:00Z"
        result = validator.validate_ocsf(valid_ocsf_event)
        assert result is False

    def test_severity_id_out_of_range_low(self, validator, valid_ocsf_event):
        """Test validation fails when severity_id is below range."""
        valid_ocsf_event["severity_id"] = -1
        result = validator.validate_ocsf(valid_ocsf_event)
        assert result is False

    def test_severity_id_out_of_range_high(self, validator, valid_ocsf_event):
        """Test validation fails when severity_id is above range."""
        valid_ocsf_event["severity_id"] = 7
        result = validator.validate_ocsf(valid_ocsf_event)
        assert result is False

    def test_severity_id_boundary_low(self, validator, valid_ocsf_event):
        """Test validation passes at severity_id boundary low."""
        valid_ocsf_event["severity_id"] = 0
        result = validator.validate_ocsf(valid_ocsf_event)
        assert result is True

    def test_severity_id_boundary_high(self, validator, valid_ocsf_event):
        """Test validation passes at severity_id boundary high."""
        valid_ocsf_event["severity_id"] = 6
        result = validator.validate_ocsf(valid_ocsf_event)
        assert result is True

    def test_get_statistics(self, validator, valid_ocsf_event):
        """Test statistics collection."""
        validator.validate_ocsf(valid_ocsf_event)
        validator.validate_ocsf({})  # Invalid

        stats = validator.get_statistics()
        assert stats["total_validated"] == 2
        assert stats["passed"] == 1
        assert stats["failed"] == 1
        assert stats["pass_rate"] == 0.5

    def test_strict_mode_raises(self):
        """Test strict mode raises on validation failure."""
        validator = OutputValidator(strict_mode=True)
        invalid_event = {"class_uid": "invalid"}

        with pytest.raises(ValueError):
            validator.validate_ocsf(invalid_event)

    def test_multiple_validations(self, validator, valid_ocsf_event):
        """Test multiple validations update stats correctly."""
        for _ in range(5):
            validator.validate_ocsf(valid_ocsf_event)

        assert validator.stats["total_validated"] == 5
        assert validator.stats["passed"] == 5
        assert validator.stats["failed"] == 0
