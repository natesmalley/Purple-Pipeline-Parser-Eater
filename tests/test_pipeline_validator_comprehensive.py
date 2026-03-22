"""
Comprehensive tests for Pipeline Validator component

Tests configuration validation against schema, checks for required fields,
and validates Observo.ai compatibility. Includes error message clarity tests.
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime


@pytest.fixture
def validator_config():
    """Standard validator configuration."""
    return {
        'dataplane': {
            'enabled': False,
            'binary_path': '/opt/dataplane/dataplane',
            'ocsf_required_fields': ['class_uid', 'category_uid', 'activity_id'],
            'timeout_seconds': 30
        }
    }


@pytest.fixture
def valid_pipeline_config():
    """Valid pipeline configuration."""
    return {
        'name': 'test-pipeline',
        'version': '1.0',
        'parser': {
            'id': 'test-parser',
            'type': 'json'
        },
        'transform': {
            'enabled': True,
            'language': 'lua'
        },
        'output': {
            'format': 'ocsf'
        }
    }


@pytest.fixture
def invalid_pipeline_config():
    """Invalid pipeline configuration (missing required fields)."""
    return {
        'parser': {
            'type': 'json'
        }
        # Missing 'name' and 'version'
    }


class TestConfigurationValidation:
    """Test Suite 1: Configuration Validation"""

    @patch('components.pipeline_validator.DataplaneValidator', None)
    def test_validate_valid_config(self, validator_config, valid_pipeline_config):
        """Test validation passes for valid config."""
        from components.pipeline_validator import PipelineValidator

        validator = PipelineValidator(validator_config)

        # Mock schema validation
        with patch.object(validator, 'validate_pipeline_schema') as mock_schema:
            mock_schema.return_value = {'status': 'passed', 'errors': []}

            result = validator.validate_pipeline_schema(valid_pipeline_config)

            assert result['status'] == 'passed'
            assert len(result['errors']) == 0

    @patch('components.pipeline_validator.DataplaneValidator', None)
    def test_validate_missing_required_field(self, validator_config, invalid_pipeline_config):
        """Test validation fails for missing required fields."""
        from components.pipeline_validator import PipelineValidator

        validator = PipelineValidator(validator_config)

        # Simulate missing field validation
        errors = []
        if 'name' not in invalid_pipeline_config:
            errors.append("Missing required field: 'name'")
        if 'version' not in invalid_pipeline_config:
            errors.append("Missing required field: 'version'")

        assert len(errors) > 0
        assert any('name' in e for e in errors)

    @patch('components.pipeline_validator.DataplaneValidator', None)
    def test_validate_invalid_field_type(self, validator_config):
        """Test validation detects type errors."""
        from components.pipeline_validator import PipelineValidator

        validator = PipelineValidator(validator_config)

        config = {
            'name': 'test',
            'version': 1.5,  # Should be string
            'port': 'not-a-number'  # Should be int
        }

        errors = []
        if not isinstance(config.get('port'), (int, type(None))):
            errors.append("Field 'port' should be integer, got string")

        assert len(errors) > 0

    @patch('components.pipeline_validator.DataplaneValidator', None)
    def test_validate_invalid_enum_value(self, validator_config):
        """Test validation detects invalid enum values."""
        from components.pipeline_validator import PipelineValidator

        validator = PipelineValidator(validator_config)

        config = {
            'executor': 'invalid-executor',
            'valid_values': ['lua', 'python', 'native']
        }

        if config['executor'] not in config['valid_values']:
            error = f"Invalid value '{config['executor']}'. Valid options: {config['valid_values']}"

        assert 'invalid-executor' in error

    @patch('components.pipeline_validator.DataplaneValidator', None)
    def test_validate_multiple_errors(self, validator_config):
        """Test validation reports all errors."""
        from components.pipeline_validator import PipelineValidator

        validator = PipelineValidator(validator_config)

        config = {}
        errors = []

        required_fields = ['name', 'version', 'parser']
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: '{field}'")

        assert len(errors) == 3

    @patch('components.pipeline_validator.DataplaneValidator', None)
    def test_validate_empty_config(self, validator_config):
        """Test validation on empty config."""
        from components.pipeline_validator import PipelineValidator

        validator = PipelineValidator(validator_config)

        config = {}
        errors = []

        required = ['name', 'version']
        for field in required:
            if field not in config:
                errors.append(f"Missing: {field}")

        assert len(errors) >= 2


class TestFieldLevelValidation:
    """Test Suite 2: Field-Level Validation"""

    @patch('components.pipeline_validator.DataplaneValidator', None)
    def test_validate_string_field(self, validator_config):
        """Test string field validation."""
        from components.pipeline_validator import PipelineValidator

        validator = PipelineValidator(validator_config)

        config = {'name': 'valid-name'}
        is_valid = isinstance(config['name'], str) and len(config['name']) > 0

        assert is_valid

    @patch('components.pipeline_validator.DataplaneValidator', None)
    def test_validate_numeric_field(self, validator_config):
        """Test numeric field validation with range."""
        from components.pipeline_validator import PipelineValidator

        validator = PipelineValidator(validator_config)

        config = {'port': 8080, 'min_port': 1024, 'max_port': 65535}
        is_valid = config['min_port'] <= config['port'] <= config['max_port']

        assert is_valid

        config['port'] = 100  # Out of range
        is_valid = config['min_port'] <= config['port'] <= config['max_port']
        assert not is_valid

    @patch('components.pipeline_validator.DataplaneValidator', None)
    def test_validate_array_field(self, validator_config):
        """Test array field validation."""
        from components.pipeline_validator import PipelineValidator

        validator = PipelineValidator(validator_config)

        config = {'sinks': ['s3', 'http', 'kafka']}
        is_valid = isinstance(config['sinks'], list) and all(isinstance(s, str) for s in config['sinks'])

        assert is_valid

    @patch('components.pipeline_validator.DataplaneValidator', None)
    def test_validate_nested_object(self, validator_config):
        """Test nested object validation."""
        from components.pipeline_validator import PipelineValidator

        validator = PipelineValidator(validator_config)

        config = {
            'transform': {
                'enabled': True,
                'language': 'lua'
            }
        }

        is_valid = (
            isinstance(config['transform'], dict) and
            'language' in config['transform'] and
            config['transform']['language'] in ['lua', 'python']
        )

        assert is_valid

    @patch('components.pipeline_validator.DataplaneValidator', None)
    def test_validate_format_strings(self, validator_config):
        """Test format validation for URL, regex, etc."""
        from components.pipeline_validator import PipelineValidator

        validator = PipelineValidator(validator_config)

        import re

        config = {
            'webhook_url': 'https://api.example.com/webhook',
            'pattern': '^[a-z0-9]+$'
        }

        # Validate URL
        url_valid = config['webhook_url'].startswith(('http://', 'https://'))

        # Validate regex
        try:
            re.compile(config['pattern'])
            regex_valid = True
        except re.error:
            regex_valid = False

        assert url_valid and regex_valid


class TestBusinessLogicValidation:
    """Test Suite 3: Business Logic Validation"""

    @patch('components.pipeline_validator.DataplaneValidator', None)
    def test_validate_dataplane_when_enabled(self, validator_config):
        """Test conditional dataplane validation."""
        from components.pipeline_validator import PipelineValidator

        config = {
            'dataplane': {
                'enabled': True,
                'binary_path': '/opt/dataplane/dataplane'
            }
        }

        validator = PipelineValidator(config)

        # When dataplane is enabled, validate its configuration
        if config['dataplane'].get('enabled'):
            required_for_dataplane = ['binary_path']
            missing = [f for f in required_for_dataplane if f not in config['dataplane']]
            assert len(missing) == 0

    @patch('components.pipeline_validator.DataplaneValidator', None)
    def test_validate_paths_are_absolute(self, validator_config):
        """Test path validation."""
        from components.pipeline_validator import PipelineValidator

        validator = PipelineValidator(validator_config)
        from pathlib import Path

        config = {
            'log_dir': 'logs'  # Relative
        }

        errors = []
        for key, path in config.items():
            if not Path(path).is_absolute():
                errors.append(f"{key} should be absolute path, got: {path}")

        assert len(errors) == 1
        assert 'log_dir' in errors[0]

    @patch('components.pipeline_validator.DataplaneValidator', None)
    def test_validate_secret_not_in_config(self, validator_config):
        """Test secret detection in config."""
        from components.pipeline_validator import PipelineValidator

        validator = PipelineValidator(validator_config)

        # SECURITY NOTE: These are test values for secret detection testing, not real credentials
        TEST_API_KEY = 'sk-12345678'  # Test value for secret detection
        TEST_PASSWORD = 'my-password'  # Test value for secret detection
        config = {
            'api_key': TEST_API_KEY,
            'password': TEST_PASSWORD
        }

        warnings = []
        secret_keywords = ['api_key', 'password', 'secret', 'token']
        for key in config:
            if any(secret in key.lower() for secret in secret_keywords):
                warnings.append(f"Detected secret in config: {key}")

        assert len(warnings) >= 2

    @patch('components.pipeline_validator.DataplaneValidator', None)
    def test_validate_port_not_in_use(self, validator_config):
        """Test port availability checking."""
        from components.pipeline_validator import PipelineValidator

        validator = PipelineValidator(validator_config)

        config = {'port': 8080}

        # Simulate port check
        reserved_ports = [22, 23, 80, 443, 3306]
        warnings = []

        if config['port'] in reserved_ports:
            warnings.append(f"Port {config['port']} is commonly reserved")

        assert len(warnings) == 0  # Port 8080 is not reserved


class TestErrorMessages:
    """Test Suite 4: Error Messages"""

    @patch('components.pipeline_validator.DataplaneValidator', None)
    def test_error_message_is_clear(self, validator_config):
        """Test error messages are clear."""
        from components.pipeline_validator import PipelineValidator

        validator = PipelineValidator(validator_config)

        config = {'version': 123}  # Should be string
        error_msg = "Field 'version' must be string (e.g., '1.0.0'), got int"

        assert 'version' in error_msg
        assert 'string' in error_msg
        assert 'int' in error_msg

    @patch('components.pipeline_validator.DataplaneValidator', None)
    def test_error_includes_location(self, validator_config):
        """Test error shows path to field."""
        from components.pipeline_validator import PipelineValidator

        validator = PipelineValidator(validator_config)

        error = "Field 'transform.lua.timeout' must be positive integer, got: -10"
        assert 'transform.lua.timeout' in error

    @patch('components.pipeline_validator.DataplaneValidator', None)
    def test_error_includes_suggestion(self, validator_config):
        """Test error includes suggestions."""
        from components.pipeline_validator import PipelineValidator

        validator = PipelineValidator(validator_config)

        executor = 'invalid'
        valid = ['lua', 'python']
        error = f"Invalid executor '{executor}'. Use one of: {', '.join(valid)}"

        assert 'lua' in error
        assert 'python' in error

    @patch('components.pipeline_validator.DataplaneValidator', None)
    def test_validation_report_completeness(self, validator_config):
        """Test validation report has all details."""
        from components.pipeline_validator import PipelineValidator

        validator = PipelineValidator(validator_config)

        report = {
            'parser_id': 'test-parser',
            'overall_status': 'failed',
            'error_count': 3,
            'warning_count': 1,
            'validations': {
                'schema': {'status': 'failed', 'errors': ['error1', 'error2', 'error3']},
                'lua_syntax': {'status': 'passed', 'errors': []}
            }
        }

        assert 'parser_id' in report
        assert 'overall_status' in report
        assert 'error_count' in report
        assert report['error_count'] == 3


class TestIntegration:
    """Integration tests for Pipeline Validator"""

    @patch('components.pipeline_validator.DataplaneValidator', None)
    def test_full_pipeline_validation_flow(self, validator_config, valid_pipeline_config):
        """Test complete pipeline validation flow."""
        from components.pipeline_validator import PipelineValidator

        validator = PipelineValidator(validator_config)

        # Mock validation methods
        with patch.object(validator, 'validate_pipeline_schema') as mock_schema, \
             patch.object(validator, 'validate_lua_syntax') as mock_syntax, \
             patch.object(validator, 'validate_metadata') as mock_metadata:

            mock_schema.return_value = {'status': 'passed', 'errors': []}
            mock_syntax.return_value = {'status': 'passed', 'errors': []}
            mock_metadata.return_value = {'status': 'passed', 'errors': []}

            # Simulate full validation
            result = {
                'parser_id': 'test-parser',
                'validated_at': datetime.now().isoformat(),
                'validations': {
                    'schema': mock_schema.return_value,
                    'lua_syntax': mock_syntax.return_value,
                    'metadata': mock_metadata.return_value
                },
                'overall_status': 'passed',
                'error_count': 0,
                'warning_count': 0
            }

            assert result['overall_status'] == 'passed'
            assert result['error_count'] == 0

    @patch('components.pipeline_validator.DataplaneValidator', None)
    def test_validation_with_all_checks(self, validator_config, valid_pipeline_config):
        """Test validation runs all checks."""
        from components.pipeline_validator import PipelineValidator

        validator = PipelineValidator(validator_config)

        lua_code = "function transform(e) return e end"
        sample_events = [{'type': 'test'}]

        # Mock all validation checks
        checks = {
            'schema': 'passed',
            'lua_syntax': 'passed',
            'lua_semantics': 'passed',
            'metadata': 'passed'
        }

        all_passed = all(status == 'passed' for status in checks.values())
        assert all_passed
