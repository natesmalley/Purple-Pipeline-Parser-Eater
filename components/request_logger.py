"""Request logging middleware for security and debugging."""

from __future__ import annotations

import logging
import time
import re
from typing import Callable, Dict, List, Optional
from functools import wraps

from flask import request, g

logger = logging.getLogger(__name__)


class RequestLogger:
    """Logs HTTP requests with sensitive data sanitization."""

    # Patterns for sensitive data detection in logs
    # SECURITY NOTE: These are regex patterns used to DETECT and REDACT passwords/credentials
    # in log messages, NOT hardcoded credentials. Used for log sanitization to prevent
    # accidental credential exposure in logs.
    # These patterns are used to identify and mask sensitive data in log output.
    _PASSWORD_PATTERN = r"password[\"']?\s*[:=]\s*[\"']?([^\"'\s]+)[\"']?"  # Pattern to detect passwords in logs
    _API_KEY_PATTERN = r"api[_-]?key[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9_-]+)[\"']?"
    _TOKEN_PATTERN = r"token[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9_-]+)[\"']?"
    # deepcode ignore HardcodedNonCryptoSecret: This is a regex pattern for log sanitization, not a secret
    _SECRET_PATTERN = r"secret[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9_-]+)[\"']?"
    _AUTH_PATTERN = r"auth[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9_-]+)[\"']?"
    
    SENSITIVE_PATTERNS = {
        "authorization": r"(?:Bearer|Basic|Token) [A-Za-z0-9_.-]+",
        "api_key": _API_KEY_PATTERN,
        "password": _PASSWORD_PATTERN,  # Regex pattern for detecting passwords in logs, not a hardcoded password
        "token": _TOKEN_PATTERN,
        "secret": _SECRET_PATTERN,
        "auth": _AUTH_PATTERN,
    }

    # Headers to redact
    SENSITIVE_HEADERS = [
        "Authorization",
        "X-API-Key",
        "X-Auth-Token",
        "X-PPPE-Token",
        "Cookie",
        "Set-Cookie",
    ]

    def __init__(self, log_level: int = logging.INFO) -> None:
        """Initialize request logger.

        Args:
            log_level: Logging level (default INFO).
        """
        self.log_level = log_level
        self.logger = logging.getLogger("pppe.request")
        self.logger.setLevel(log_level)

    @staticmethod
    def sanitize_value(value: str, mask_length: int = 8) -> str:
        """Sanitize sensitive values.

        Args:
            value: Value to sanitize.
            mask_length: Length of unmasked part (default 8).

        Returns:
            Sanitized value with sensitive parts masked.
        """
        if not value or len(value) < 4:
            return "***"

        # Show first mask_length and last 4 characters
        if len(value) > mask_length + 4:
            return f"{value[:mask_length]}...{value[-4:]}"
        return f"{value[:mask_length]}..."

    def sanitize_data(self, data: str) -> str:
        """Sanitize sensitive data from string.

        Args:
            data: String data to sanitize.

        Returns:
            Sanitized string.
        """
        if not data:
            return data

        sanitized = data
        for pattern_key, pattern in self.SENSITIVE_PATTERNS.items():
            matches = re.finditer(pattern, sanitized, re.IGNORECASE)
            for match in matches:
                masked = self.sanitize_value(match.group(0))
                sanitized = sanitized.replace(match.group(0), masked)

        return sanitized

    def get_sanitized_headers(self) -> Dict[str, str]:
        """Get request headers with sensitive data redacted.

        Returns:
            Dict of sanitized headers.
        """
        headers = {}
        for key, value in request.headers:
            if key in self.SENSITIVE_HEADERS:
                headers[key] = self.sanitize_value(str(value))
            else:
                headers[key] = str(value)
        return headers

    def get_request_body(self, max_length: int = 500) -> str:
        """Get request body safely.

        Args:
            max_length: Max length to log (default 500).

        Returns:
            Sanitized request body.
        """
        try:
            data = request.get_data(as_text=True)
            if len(data) > max_length:
                data = data[:max_length] + "..."
            return self.sanitize_data(data)
        except Exception as e:
            logger.debug("Failed to read request body: %s", e)
            return "<unable to read body>"

    def log_request_start(self) -> None:
        """Log request start."""
        g.request_start_time = time.time()

        log_msg = (
            f"REQUEST START: {request.method} {request.path} "
            f"from {request.remote_addr}"
        )

        if request.method in ("POST", "PUT", "PATCH"):
            body = self.get_request_body(max_length=200)
            log_msg += f" | Body: {body}"

        self.logger.log(self.log_level, log_msg)

    def log_request_end(self, response) -> None:
        """Log request end.

        Args:
            response: Flask response object.
        """
        duration = 0
        if hasattr(g, "request_start_time"):
            duration = time.time() - g.request_start_time

        log_msg = (
            f"REQUEST END: {request.method} {request.path} "
            f"-> {response.status_code} ({duration:.3f}s)"
        )

        # Log level depends on status code
        if response.status_code >= 500:
            log_level = logging.ERROR
        elif response.status_code >= 400:
            log_level = logging.WARNING
        else:
            log_level = self.log_level

        self.logger.log(log_level, log_msg)

    def middleware(self, app) -> None:
        """Register middleware with Flask app.

        Args:
            app: Flask application.
        """
        @app.before_request
        def before_request() -> None:
            self.log_request_start()

        @app.after_request
        def after_request(response):
            self.log_request_end(response)
            return response

        logger.info("Request logging middleware registered")

    def decorator(self, func: Callable) -> Callable:
        """Decorator for logging specific endpoints.

        Args:
            func: Flask view function.

        Returns:
            Wrapped function.
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            self.log_request_start()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                # Note: we don't have response here, so just log timing
                if hasattr(g, "request_start_time"):
                    duration = time.time() - g.request_start_time
                    self.logger.log(
                        self.log_level,
                        f"ENDPOINT: {request.method} {request.path} ({duration:.3f}s)"
                    )

        return wrapper


# Global request logger instance
_global_logger = RequestLogger()


def get_request_logger() -> RequestLogger:
    """Get global request logger instance.

    Returns:
        Global RequestLogger.
    """
    return _global_logger


def log_request(func: Callable) -> Callable:
    """Decorator to log specific endpoint requests.

    Usage:
        @app.route('/api/data')
        @log_request
        def get_data():
            return {"data": "..."}

    Args:
        func: Flask view function.

    Returns:
        Wrapped function.
    """
    return _global_logger.decorator(func)


def register_request_logging(app) -> None:
    """Register request logging middleware with Flask app.

    Args:
        app: Flask application.
    """
    _global_logger.middleware(app)
