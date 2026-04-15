"""Configuration validation system for production deployment."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple


class ConfigValidator:
    """Validates configuration and environment variables.

    Checks for:
    - Required environment variables
    - Weak tokens and API keys
    - API key format validity
    - Production-specific requirements
    """

    # Weak token patterns to detect
    WEAK_PATTERNS = [
        r"changeme",
        r"test",
        r"demo",
        r"example",
        r"password",
        r"12345",
        r"qwerty",
        r"admin",
        r"user",
        r"root",
        r"placeholder",
        r"xxx",
        r"todo",
    ]

    # Placeholder patterns to detect (values that need to be replaced)
    PLACEHOLDER_PATTERNS = [
        r"your-.*",
        r"your_.*",
        r"YOUR-.*",
        r"YOUR_.*",
        r"your-.*-here",
        r"your-.*-key",
        r"your-.*-token",
        r"example\.com",
        r"example\.org",
        r"your-domain",
        r"your-team",
        r"your-username",
        r"your-email",
        r"sk-ant-your-key",
        r"ghp-your-token",
        r"your-s1-sdl-key",
        r"AKIA\.\.\.",
        r"vpc-xxxxxxxx",
    ]

    # API key format patterns
    API_KEY_PATTERNS = {
        "github_token": r"^ghp_[A-Za-z0-9_]{36}$",  # GitHub Personal Access Token
        "slack_token": r"^xox[baprs]-[A-Za-z0-9]{10,48}$",  # Slack token
        "aws_access_key": r"^AKIA[0-9A-Z]{16}$",  # AWS Access Key
        "anthropic_api_key": r"^sk-ant-[A-Za-z0-9_\-]{20,}$",  # Anthropic API key
    }

    def __init__(self, is_production: bool = False) -> None:
        """Initialize validator.

        Args:
            is_production: Whether validating for production environment.
        """
        self.is_production = is_production
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_required_vars(self, required_vars: List[str]) -> bool:
        """Validate that required environment variables are set.

        Args:
            required_vars: List of required variable names.

        Returns:
            True if all required variables are present.
        """
        missing = []
        for var in required_vars:
            if not os.getenv(var):
                missing.append(var)

        if missing:
            self.errors.append(f"Missing required environment variables: {', '.join(missing)}")
            return False

        return True

    def check_token_strength(self, token_name: str, token_value: Optional[str]) -> bool:
        """Check if a token has weak patterns.

        Args:
            token_name: Name of the token (for error messages).
            token_value: The token value to check.

        Returns:
            True if token is strong (no weak patterns detected).
        """
        if not token_value:
            self.errors.append(f"{token_name} is not set")
            return False

        # Check for placeholder values first (most critical)
        for pattern in self.PLACEHOLDER_PATTERNS:
            if re.search(pattern, token_value, re.IGNORECASE):
                self.errors.append(
                    f"{token_name} contains placeholder value (must be replaced): {pattern}"
                )
                return False

        # Check for weak patterns BEFORE length. Batch 3 Stream D fix —
        # a weak pattern like "changeme" or "test" is a more informative
        # error than "too short" even when the token is also short, and
        # the security posture is strictly stronger because both short
        # AND weak tokens now surface the weak-pattern reason instead of
        # silently masking it behind the length check.
        token_lower = token_value.lower()
        for pattern in self.WEAK_PATTERNS:
            if re.search(pattern, token_lower, re.IGNORECASE):
                self.errors.append(
                    f"{token_name} contains weak pattern: {pattern}"
                )
                return False

        # Check length last (short non-weak tokens still fail here).
        if len(token_value) < 16:
            self.errors.append(f"{token_name} is too short (< 16 chars)")
            return False

        return True

    def check_placeholder_values(self, config_dict: Dict) -> bool:
        """Check configuration dictionary for placeholder values.

        Args:
            config_dict: Configuration dictionary to check.

        Returns:
            True if no placeholder values found.
        """
        found_placeholders = []
        
        def check_value(key_path: str, value: Any) -> None:
            """Recursively check values for placeholders."""
            if isinstance(value, str):
                for pattern in self.PLACEHOLDER_PATTERNS:
                    if re.search(pattern, value, re.IGNORECASE):
                        found_placeholders.append(f"{key_path}: '{value}' matches pattern '{pattern}'")
            elif isinstance(value, dict):
                for k, v in value.items():
                    check_value(f"{key_path}.{k}" if key_path else k, v)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    check_value(f"{key_path}[{i}]", item)

        check_value("", config_dict)
        
        if found_placeholders:
            for placeholder in found_placeholders:
                self.errors.append(f"Placeholder value detected: {placeholder}")
            return False
        
        return True

    def validate_api_key_format(
        self, key_name: str, key_value: Optional[str], key_type: str
    ) -> bool:
        """Validate API key format against known patterns.

        Args:
            key_name: Name of the key (for error messages).
            key_value: The key value to validate.
            key_type: Type of key (github_token, slack_token, etc).

        Returns:
            True if key matches expected format or is not validated.
        """
        if not key_value:
            self.errors.append(f"{key_name} is not set")
            return False

        if key_type not in self.API_KEY_PATTERNS:
            # Unknown key type - just check it's not weak
            return self.check_token_strength(key_name, key_value)

        pattern = self.API_KEY_PATTERNS[key_type]
        if not re.match(pattern, key_value):
            self.warnings.append(
                f"{key_name} does not match expected {key_type} format"
            )
            return True  # Warning, not error

        return True

    def check_production_requirements(self) -> bool:
        """Check production-specific requirements.

        Returns:
            True if all production requirements met.
        """
        if not self.is_production:
            return True

        all_valid = True

        # Check for debug mode
        debug_mode = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
        if debug_mode:
            self.errors.append("DEBUG mode enabled in production")
            all_valid = False

        # Check for secure connection
        secure = os.getenv("SECURE_CONNECTIONS", "false").lower() in ("true", "1", "yes")
        if not secure:
            self.warnings.append(
                "SECURE_CONNECTIONS not enabled in production"
            )

        # Check log level
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        if log_level == "DEBUG":
            self.warnings.append("LOG_LEVEL set to DEBUG in production")

        # Check for allowed hosts
        allowed_hosts = os.getenv("ALLOWED_HOSTS", "")
        if not allowed_hosts or allowed_hosts == "*":
            self.errors.append(
                "ALLOWED_HOSTS not properly configured in production"
            )
            all_valid = False

        # Require HTTPS
        use_https = os.getenv("USE_HTTPS", "false").lower() in ("true", "1", "yes")
        if not use_https:
            self.errors.append("HTTPS required in production")
            all_valid = False

        return all_valid

    def validate_all(
        self,
        required_vars: List[str],
        token_vars: Optional[Dict[str, str]] = None,
        api_keys: Optional[Dict[str, Tuple[str, str]]] = None,
    ) -> Tuple[bool, List[str], List[str]]:
        """Perform complete validation.

        Args:
            required_vars: List of required environment variables.
            token_vars: Dict of token name -> env var name.
            api_keys: Dict of key name -> (env var name, key type).

        Returns:
            Tuple of (all_valid, errors, warnings).
        """
        self.errors = []
        self.warnings = []
        api_keys = api_keys or {}
        # Batch 3 Stream D fix — token_vars is optional; default to {}
        # so callers that only validate required vars don't have to
        # pass an empty dict explicitly.
        token_vars = token_vars or {}

        # Check required variables
        if not self.validate_required_vars(required_vars):
            return False, self.errors, self.warnings

        # Check token strength
        for token_name, env_var in token_vars.items():
            token_value = os.getenv(env_var)
            self.check_token_strength(token_name, token_value)

        # Check API key formats
        for key_name, (env_var, key_type) in api_keys.items():
            key_value = os.getenv(env_var)
            self.validate_api_key_format(key_name, key_value, key_type)

        # Check production requirements
        if self.is_production:
            self.check_production_requirements()

        all_valid = len(self.errors) == 0
        return all_valid, self.errors, self.warnings

    def get_report(self) -> str:
        """Get validation report as formatted string.

        Returns:
            Formatted validation report.
        """
        lines = ["Configuration Validation Report", "=" * 40]

        if self.errors:
            lines.append("\n❌ ERRORS:")
            for error in self.errors:
                lines.append(f"  - {error}")
        else:
            lines.append("\n✅ No errors")

        if self.warnings:
            lines.append("\n⚠️  WARNINGS:")
            for warning in self.warnings:
                lines.append(f"  - {warning}")
        else:
            lines.append("\n✅ No warnings")

        lines.append("\n" + "=" * 40)
        if not self.errors:
            lines.append("Status: PASS ✅")
        else:
            lines.append("Status: FAIL ❌")

        return "\n".join(lines)
