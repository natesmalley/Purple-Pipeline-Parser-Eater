"""Tests for security middleware."""

from __future__ import annotations

import pytest

from components.security_middleware import (
    SecurityValidator,
    ErrorSanitizer,
    SecurityHeaders,
    get_security_validator,
)


class TestSecurityValidator:
    """Test security validator."""

    def test_validator_initialization(self) -> None:
        """Test validator initialization."""
        validator = SecurityValidator()
        assert validator is not None

    def test_check_sql_injection_safe(self) -> None:
        """Test SQL injection check with safe input."""
        validator = SecurityValidator()
        safe, pattern = validator.check_sql_injection("SELECT * FROM users WHERE id = 123")
        assert safe is True
        assert pattern is None

    def test_check_sql_injection_or_1_1(self) -> None:
        """Test SQL injection check detects OR 1=1."""
        validator = SecurityValidator()
        safe, pattern = validator.check_sql_injection("admin' OR 1=1--")
        assert safe is False
        assert pattern is not None

    def test_check_sql_injection_union(self) -> None:
        """Test SQL injection check detects UNION."""
        validator = SecurityValidator()
        safe, pattern = validator.check_sql_injection("' UNION SELECT * FROM users--")
        assert safe is False

    def test_check_command_injection_safe(self) -> None:
        """Test command injection check with safe input."""
        validator = SecurityValidator()
        safe, pattern = validator.check_command_injection("normal_text_123")
        assert safe is True

    def test_check_command_injection_semicolon(self) -> None:
        """Test command injection check detects metacharacters."""
        validator = SecurityValidator()
        safe, pattern = validator.check_command_injection("ls; rm -rf /")
        assert safe is False

    def test_check_command_injection_pipe(self) -> None:
        """Test command injection check detects pipe."""
        validator = SecurityValidator()
        safe, pattern = validator.check_command_injection("cat file | grep pattern")
        assert safe is False

    def test_check_xss_safe(self) -> None:
        """Test XSS check with safe input."""
        validator = SecurityValidator()
        safe, pattern = validator.check_xss("Normal text content")
        assert safe is True

    def test_check_xss_script_tag(self) -> None:
        """Test XSS check detects script tags."""
        validator = SecurityValidator()
        safe, pattern = validator.check_xss("<script>alert('xss')</script>")
        assert safe is False

    def test_check_xss_event_handler(self) -> None:
        """Test XSS check detects event handlers."""
        validator = SecurityValidator()
        safe, pattern = validator.check_xss("<img src=x onerror='alert(1)'>")
        assert safe is False

    def test_check_path_traversal_safe(self) -> None:
        """Test path traversal check with safe path."""
        validator = SecurityValidator()
        safe, pattern = validator.check_path_traversal("/uploads/image.png")
        assert safe is True

    def test_check_path_traversal_dots(self) -> None:
        """Test path traversal check detects ../."""
        validator = SecurityValidator()
        safe, pattern = validator.check_path_traversal("../../etc/passwd")
        assert safe is False

    def test_check_path_traversal_encoded(self) -> None:
        """Test path traversal check detects encoded traversal."""
        validator = SecurityValidator()
        safe, pattern = validator.check_path_traversal("%2e%2e/etc/passwd")
        assert safe is False

    def test_validate_input_all_safe(self) -> None:
        """Test validate_input with safe data."""
        validator = SecurityValidator()
        safe, findings = validator.validate_input("normal_user_input")

        assert safe is True
        assert all(v is None for v in findings.values())

    def test_validate_input_multiple_attacks(self) -> None:
        """Test validate_input detects multiple attack patterns."""
        validator = SecurityValidator()
        payload = "admin' OR 1=1; <script>alert('xss')</script>"
        safe, findings = validator.validate_input(payload)

        assert safe is False
        assert findings["sql_injection"] is not None

    def test_validate_input_selective_checks(self) -> None:
        """Test validate_input with selective checks."""
        validator = SecurityValidator()
        xss_payload = "<script>alert(1)</script>"

        # Only check XSS
        safe, findings = validator.validate_input(
            xss_payload,
            check_sql=False,
            check_command=False,
            check_path=False
        )

        assert safe is False
        assert findings["xss"] is not None


class TestErrorSanitizer:
    """Test error sanitizer."""

    def test_sanitize_error_development(self) -> None:
        """Test error sanitization in development."""
        error_msg = "Error in /home/user/app.py line 42"
        sanitized = ErrorSanitizer.sanitize_error_message(
            error_msg,
            is_production=False
        )

        # In development, errors are not sanitized
        assert error_msg in sanitized or sanitized == error_msg

    def test_sanitize_error_production(self) -> None:
        """Test error sanitization in production."""
        error_msg = "Error in /home/user/app.py line 42: Database connection failed"
        sanitized = ErrorSanitizer.sanitize_error_message(
            error_msg,
            is_production=True
        )

        # In production, file paths and line numbers are redacted
        assert "[REDACTED]" in sanitized
        assert "/home/user/app.py" not in sanitized

    def test_sanitize_error_empty(self) -> None:
        """Test sanitizing empty error message."""
        sanitized = ErrorSanitizer.sanitize_error_message("")
        assert sanitized == "An error occurred"

    def test_sanitize_error_ip_address(self) -> None:
        """Test sanitizing error with IP address."""
        error_msg = "Connection refused from 192.168.1.1"
        sanitized = ErrorSanitizer.sanitize_error_message(
            error_msg,
            is_production=True
        )

        assert "[REDACTED]" in sanitized
        assert "192.168.1.1" not in sanitized

    def test_get_user_safe_error_production(self) -> None:
        """Test user-safe error in production."""
        error_dict = ErrorSanitizer.get_user_safe_error(
            "server_error",
            "Database connection failed at /app/db.py:123",
            is_production=True
        )

        assert error_dict["error"] == "server_error"
        assert "An error occurred" in error_dict["message"]
        assert "database" not in error_dict.get("details", "").lower()

    def test_get_user_safe_error_development(self) -> None:
        """Test user-safe error in development."""
        error_dict = ErrorSanitizer.get_user_safe_error(
            "validation",
            "Invalid email format",
            is_production=False
        )

        assert error_dict["error"] == "validation"
        assert "Invalid email format" in error_dict["details"]

    def test_get_user_safe_error_all_types(self) -> None:
        """Test all error types."""
        error_types = [
            "validation",
            "authentication",
            "authorization",
            "not_found",
            "conflict",
            "server_error",
            "rate_limit",
            "timeout",
        ]

        for error_type in error_types:
            error_dict = ErrorSanitizer.get_user_safe_error(error_type)
            assert error_dict["error"] == error_type
            assert "message" in error_dict


class TestSecurityHeaders:
    """Test security headers."""

    def test_get_headers_all(self) -> None:
        """Test getting all security headers."""
        headers = SecurityHeaders.get_headers()

        assert "X-Content-Type-Options" in headers
        assert "X-Frame-Options" in headers
        assert "X-XSS-Protection" in headers
        assert "Content-Security-Policy" in headers
        assert "Referrer-Policy" in headers

    def test_get_headers_without_hsts(self) -> None:
        """Test getting headers without HSTS."""
        headers = SecurityHeaders.get_headers(include_hsts=False)

        assert "Strict-Transport-Security" not in headers
        assert "X-Content-Type-Options" in headers

    def test_security_headers_values(self) -> None:
        """Test security header values are correct."""
        headers = SecurityHeaders.get_headers()

        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert "1; mode=block" in headers["X-XSS-Protection"]
        assert "max-age=" in headers["Strict-Transport-Security"]

    def test_csp_header_content(self) -> None:
        """Test CSP header contains expected directives."""
        headers = SecurityHeaders.get_headers()
        csp = headers["Content-Security-Policy"]

        assert "default-src" in csp
        assert "script-src" in csp
        assert "style-src" in csp
        assert "frame-ancestors" in csp


class TestGlobalValidator:
    """Test global validator instance."""

    def test_get_global_validator(self) -> None:
        """Test getting global validator."""
        validator1 = get_security_validator()
        validator2 = get_security_validator()

        assert validator1 is validator2
