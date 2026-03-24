#!/usr/bin/env python3
"""
Tests for custom exception hierarchy
"""

import pytest
from utils.exceptions import (
    PPPEError, ConfigurationError, ValidationError,
    SecurityError, APIError, ProcessingError, ResourceError
)


class TestExceptionHierarchy:
    """Test exception inheritance and structure"""

    def test_exception_hierarchy(self):
        """Test exception inheritance"""
        assert issubclass(ConfigurationError, PPPEError)
        assert issubclass(ValidationError, PPPEError)
        assert issubclass(SecurityError, PPPEError)
        assert issubclass(APIError, PPPEError)
        assert issubclass(ProcessingError, PPPEError)
        assert issubclass(ResourceError, PPPEError)

    def test_base_exception_init(self):
        """Test base exception initialization"""
        error = PPPEError("Test error")
        assert error.message == "Test error"
        assert error.details == {}

    def test_exception_with_details(self):
        """Test exception with details"""
        details = {'field': 'value', 'code': 123}
        error = PPPEError("Test error", details=details)
        assert error.message == "Test error"
        assert error.details == details

    def test_exception_to_dict(self):
        """Test exception serialization"""
        error = ValidationError("Test error", details={'field': 'value'})
        error_dict = error.to_dict()

        assert error_dict['error'] == 'ValidationError'
        assert error_dict['message'] == 'Test error'
        assert error_dict['details']['field'] == 'value'

    def test_configuration_error(self):
        """Test ConfigurationError"""
        error = ConfigurationError("Invalid config", details={'key': 'dataplane_path'})
        assert isinstance(error, PPPEError)
        assert error.message == "Invalid config"
        assert error.details['key'] == 'dataplane_path'

    def test_validation_error(self):
        """Test ValidationError"""
        error = ValidationError("Invalid input")
        assert isinstance(error, PPPEError)
        assert error.message == "Invalid input"

    def test_security_error(self):
        """Test SecurityError"""
        error = SecurityError("Path traversal detected", details={'path': '../../etc/passwd'})
        assert isinstance(error, PPPEError)
        assert error.message == "Path traversal detected"

    def test_api_error_basic(self):
        """Test APIError basic"""
        error = APIError("API failed")
        assert isinstance(error, PPPEError)
        assert error.message == "API failed"
        assert error.status_code is None
        assert error.response is None

    def test_api_error_with_status(self):
        """Test APIError with status code and response"""
        response = {'error': 'internal_error'}
        error = APIError("API failed", status_code=500, response=response)

        assert error.status_code == 500
        assert error.response == response
        assert error.message == "API failed"

    def test_processing_error(self):
        """Test ProcessingError"""
        error = ProcessingError("Conversion failed", details={'parser': 'test.xml'})
        assert isinstance(error, PPPEError)
        assert error.message == "Conversion failed"
        assert error.details['parser'] == 'test.xml'

    def test_resource_error(self):
        """Test ResourceError"""
        error = ResourceError("File not found", details={'path': '/path/to/file'})
        assert isinstance(error, PPPEError)
        assert error.message == "File not found"
        assert error.details['path'] == '/path/to/file'

    def test_exception_str_representation(self):
        """Test exception string representation"""
        error = ValidationError("Test error")
        assert str(error) == "Test error"

    def test_api_error_to_dict(self):
        """Test APIError to_dict includes status and response"""
        response = {'error': 'server_error'}
        error = APIError("API failed", status_code=500, response=response, details={'endpoint': '/api/test'})
        error_dict = error.to_dict()

        assert error_dict['error'] == 'APIError'
        assert error_dict['message'] == 'API failed'
        assert error_dict['details']['endpoint'] == '/api/test'
        # Note: status_code and response are not in to_dict, but are attributes
        assert error.status_code == 500
        assert error.response == response
