#!/usr/bin/env python3
"""
Log Sanitization Utility

Removes sensitive data from logs before writing.

SECURITY FIX: Phase 7 - Log Sanitization
- Detects and redacts API keys
- Redacts authentication tokens
- Redacts passwords and credentials
- Prevents secret leakage in logs
"""

import re
import logging
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)


class LogSanitizer:
    """
    Sanitizes log data to prevent secret leakage.

    Detects and redacts:
    - API keys (Anthropic, GitHub, etc.)
    - Authentication tokens
    - Passwords
    - Other sensitive patterns
    """

    # Patterns for detecting secrets
    SECRET_PATTERNS = [
        # Anthropic API keys: sk-ant-api03-...
        (r'sk-ant-[a-zA-Z0-9-]{20,}', '***ANTHROPIC_API_KEY_REDACTED***'),

        # GitHub tokens: ghp_... or github_pat_...
        (r'ghp_[a-zA-Z0-9]{36}', '***GITHUB_TOKEN_REDACTED***'),
        (r'github_pat_[a-zA-Z0-9_]{82}', '***GITHUB_TOKEN_REDACTED***'),

        # Generic API keys
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_-]{20,})', r'api_key="***REDACTED***"'),
        (r'token["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_-]{20,})', r'token="***REDACTED***"'),

        # Passwords
        (r'password["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'password="***REDACTED***"'),
        (r'passwd["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'passwd="***REDACTED***"'),

        # AWS credentials
        (r'AKIA[0-9A-Z]{16}', '***AWS_ACCESS_KEY_REDACTED***'),
        (r'aws[_-]?secret[_-]?access[_-]?key["\']?\s*[:=]\s*["\']?([^"\'\s]+)', r'aws_secret_access_key="***REDACTED***"'),

        # MinIO credentials (if default)
        (r'minioadmin', '***MINIO_CREDENTIAL_REDACTED***'),
    ]

    # Keys that should always be redacted
    SENSITIVE_KEYS = [
        'api_key', 'api-key', 'apikey',
        'token', 'auth_token', 'auth-token',
        'password', 'passwd', 'pwd',
        'secret', 'secret_key', 'secret-key',
        'credential', 'credentials',
        'access_key', 'access-key',
        'private_key', 'private-key',
    ]

    @classmethod
    def sanitize_string(cls, text: str) -> str:
        """
        Sanitize a string by redacting secrets.

        Args:
            text: String that may contain secrets

        Returns:
            Sanitized string with secrets redacted
        """
        if not isinstance(text, str):
            return text

        sanitized = text

        # Apply pattern-based redaction
        for pattern, replacement in cls.SECRET_PATTERNS:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

        return sanitized

    @classmethod
    def sanitize_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize a dictionary by redacting sensitive values.

        Args:
            data: Dictionary that may contain secrets

        Returns:
            Sanitized dictionary with secrets redacted
        """
        if not isinstance(data, dict):
            return data

        sanitized = {}

        for key, value in data.items():
            # Check if key indicates sensitive data
            key_lower = key.lower()
            is_sensitive_key = any(
                sensitive in key_lower
                for sensitive in cls.SENSITIVE_KEYS
            )

            if is_sensitive_key and isinstance(value, str):
                # Redact sensitive values
                sanitized[key] = '***REDACTED***'
            elif isinstance(value, dict):
                # Recursively sanitize nested dicts
                sanitized[key] = cls.sanitize_dict(value)
            elif isinstance(value, list):
                # Sanitize list items
                sanitized[key] = [
                    cls.sanitize_dict(item) if isinstance(item, dict)
                    else cls.sanitize_string(item) if isinstance(item, str)
                    else item
                    for item in value
                ]
            elif isinstance(value, str):
                # Sanitize string values
                sanitized[key] = cls.sanitize_string(value)
            else:
                sanitized[key] = value

        return sanitized

    @classmethod
    def sanitize_log_data(cls, data: Union[str, Dict, List]) -> Union[str, Dict, List]:
        """
        Sanitize log data (handles multiple types).

        Args:
            data: Data to sanitize (string, dict, or list)

        Returns:
            Sanitized data
        """
        if isinstance(data, str):
            return cls.sanitize_string(data)
        elif isinstance(data, dict):
            return cls.sanitize_dict(data)
        elif isinstance(data, list):
            return [
                cls.sanitize_log_data(item)
                for item in data
            ]
        else:
            return data
