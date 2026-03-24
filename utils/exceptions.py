#!/usr/bin/env python3
"""
Custom Exception Hierarchy

Standardized exceptions for consistent error handling.
"""


class PPPEError(Exception):
    """Base exception for all PPPE errors"""

    def __init__(self, message: str, details: dict = None):
        """
        Initialize exception.

        Args:
            message: Human-readable error message
            details: Additional error details (dict)
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        """Convert exception to dictionary for JSON responses"""
        return {
            'error': self.__class__.__name__,
            'message': self.message,
            'details': self.details
        }


class ConfigurationError(PPPEError):
    """Configuration-related errors"""
    pass


class ValidationError(PPPEError):
    """Validation errors (input validation, schema validation)"""
    pass


class SecurityError(PPPEError):
    """Security-related errors (path traversal, injection attempts)"""
    pass


class APIError(PPPEError):
    """External API errors"""

    def __init__(self, message: str, status_code: int = None, response: dict = None, details: dict = None):
        super().__init__(message, details)
        self.status_code = status_code
        self.response = response


class ProcessingError(PPPEError):
    """Processing errors (conversion, transformation failures)"""
    pass


class ResourceError(PPPEError):
    """Resource errors (file not found, connection failed)"""
    pass
