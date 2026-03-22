"""Security middleware and hardening utilities."""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SecurityValidator:
    """Validates input and output for security issues."""

    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(\bOR\b\s*\b1\b\s*=\s*\b1\b)",  # OR 1=1
        r"(\bUNION\b)",  # UNION-based injection
        r"(--\s*$|--\s+)",  # SQL comments
        r"(;\s*DROP\b)",  # DROP statements
        r"(;\s*DELETE\b)",  # DELETE statements
        r"(;\s*TRUNCATE\b)",  # TRUNCATE statements
        r"(EXEC\s*\()",  # EXEC statements
        r"(xp_cmdshell)",  # Extended stored procedures
    ]

    # Command injection patterns
    COMMAND_INJECTION_PATTERNS = [
        r"([;&|`$(){}])",  # Shell metacharacters
        r"(\$\(.*\))",  # Command substitution
        r"(`.*`)",  # Backtick command substitution
    ]

    # XSS patterns (basic)
    XSS_PATTERNS = [
        r"(<script[^>]*>)",  # Script tags
        r"(javascript:)",  # JavaScript protocol
        r"(on\w+\s*=)",  # Event handlers
        r"(<iframe[^>]*>)",  # IFrame tags
        r"(<object[^>]*>)",  # Object tags
    ]

    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        r"(\.\./)",  # Directory traversal
        r"(\.\.\\)",  # Windows directory traversal
        r"(%2e%2e/)",  # URL encoded traversal
        r"(\.\.%5c)",  # Mixed encoding traversal
    ]

    def __init__(self) -> None:
        """Initialize security validator."""
        pass

    def check_sql_injection(self, value: str) -> Tuple[bool, Optional[str]]:
        """Check for SQL injection patterns.

        Args:
            value: String to check.

        Returns:
            Tuple of (is_safe: bool, matched_pattern: Optional[str]).
        """
        if not value:
            return True, None

        for pattern in self.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return False, pattern
        return True, None

    def check_command_injection(self, value: str) -> Tuple[bool, Optional[str]]:
        """Check for command injection patterns.

        Args:
            value: String to check.

        Returns:
            Tuple of (is_safe: bool, matched_pattern: Optional[str]).
        """
        if not value:
            return True, None

        for pattern in self.COMMAND_INJECTION_PATTERNS:
            if re.search(pattern, value):
                return False, pattern
        return True, None

    def check_xss(self, value: str) -> Tuple[bool, Optional[str]]:
        """Check for XSS patterns.

        Args:
            value: String to check.

        Returns:
            Tuple of (is_safe: bool, matched_pattern: Optional[str]).
        """
        if not value:
            return True, None

        for pattern in self.XSS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return False, pattern
        return True, None

    def check_path_traversal(self, value: str) -> Tuple[bool, Optional[str]]:
        """Check for path traversal patterns.

        Args:
            value: String to check.

        Returns:
            Tuple of (is_safe: bool, matched_pattern: Optional[str]).
        """
        if not value:
            return True, None

        for pattern in self.PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return False, pattern
        return True, None

    def validate_input(
        self,
        value: str,
        check_sql: bool = True,
        check_command: bool = True,
        check_xss: bool = True,
        check_path: bool = True
    ) -> Tuple[bool, Dict[str, Optional[str]]]:
        """Validate input against multiple attack patterns.

        Args:
            value: Input to validate.
            check_sql: Check for SQL injection.
            check_command: Check for command injection.
            check_xss: Check for XSS.
            check_path: Check for path traversal.

        Returns:
            Tuple of (all_safe: bool, findings: Dict[str, Optional[str]]).
        """
        findings = {}

        if check_sql:
            safe, pattern = self.check_sql_injection(value)
            findings["sql_injection"] = pattern if not safe else None

        if check_command:
            safe, pattern = self.check_command_injection(value)
            findings["command_injection"] = pattern if not safe else None

        if check_xss:
            safe, pattern = self.check_xss(value)
            findings["xss"] = pattern if not safe else None

        if check_path:
            safe, pattern = self.check_path_traversal(value)
            findings["path_traversal"] = pattern if not safe else None

        all_safe = all(v is None for v in findings.values())
        return all_safe, findings


class ErrorSanitizer:
    """Sanitize error messages for production."""

    SENSITIVE_INFO_PATTERNS = [
        r"(/[\w/]+\.py)",  # File paths
        r"(line \d+)",  # Line numbers
        r"(sqlalchemy|django|flask)",  # Framework names
        r"(postgresql|mysql|mongodb)",  # Database names
        r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})",  # IP addresses
    ]

    @staticmethod
    def sanitize_error_message(
        error_msg: str,
        is_production: bool = False
    ) -> str:
        """Sanitize error message for output.

        Args:
            error_msg: Original error message.
            is_production: Whether in production environment.

        Returns:
            Sanitized error message.
        """
        if not error_msg:
            return "An error occurred"

        if not is_production:
            return error_msg

        # In production, hide implementation details
        sanitized = error_msg

        for pattern in ErrorSanitizer.SENSITIVE_INFO_PATTERNS:
            sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)

        # If message is too technical, replace entirely
        if any(
            keyword in sanitized.lower()
            for keyword in ["exception", "traceback", "file ", "line "]
        ):
            return "An error occurred. Please contact support if the problem persists."

        return sanitized

    @staticmethod
    def get_user_safe_error(
        error_type: str,
        details: Optional[str] = None,
        is_production: bool = False
    ) -> Dict[str, str]:
        """Get user-safe error response.

        Args:
            error_type: Type of error.
            details: Additional details.
            is_production: Whether in production.

        Returns:
            Safe error dict for response.
        """
        default_messages = {
            "validation": "Invalid input provided",
            "authentication": "Authentication failed",
            "authorization": "Not authorized",
            "not_found": "Resource not found",
            "conflict": "Resource conflict",
            "server_error": "An error occurred",
            "rate_limit": "Rate limit exceeded",
            "timeout": "Request timed out",
        }

        message = default_messages.get(error_type, "An error occurred")

        if is_production or not details:
            return {
                "error": error_type,
                "message": message
            }

        # In development, include sanitized details
        sanitized_details = ErrorSanitizer.sanitize_error_message(
            details,
            is_production=False
        )

        return {
            "error": error_type,
            "message": message,
            "details": sanitized_details
        }


class SecurityHeaders:
    """Security headers for HTTP responses."""

    # Standard security headers
    HEADERS = {
        "X-Content-Type-Options": "nosniff",  # Prevent MIME sniffing
        "X-Frame-Options": "DENY",  # Prevent clickjacking
        "X-XSS-Protection": "1; mode=block",  # XSS protection
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",  # HSTS
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "  # Required for some inline scripts
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        ),
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(),microphone=(),camera=()",
    }

    @staticmethod
    def get_headers(include_hsts: bool = True) -> Dict[str, str]:
        """Get security headers.

        Args:
            include_hsts: Include HSTS header.

        Returns:
            Dict of security headers.
        """
        headers = SecurityHeaders.HEADERS.copy()

        if not include_hsts and "Strict-Transport-Security" in headers:
            del headers["Strict-Transport-Security"]

        return headers


def add_security_headers(app) -> None:
    """Add security headers to Flask app responses.

    Args:
        app: Flask application.
    """
    @app.after_request
    def set_security_headers(response):
        for header, value in SecurityHeaders.get_headers().items():
            response.headers[header] = value
        return response

    logger.info("Security headers registered")


# Global validator instance
_global_validator = SecurityValidator()


def get_security_validator() -> SecurityValidator:
    """Get global security validator instance.

    Returns:
        Global SecurityValidator.
    """
    return _global_validator
