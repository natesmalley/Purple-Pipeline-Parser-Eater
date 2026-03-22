"""
Configuration expansion utilities for Purple Pipeline Parser Eater.

Provides centralized environment variable expansion to prevent code duplication
and ensure consistent behavior across all components.

SECURITY FIX: Implements proper environment variable expansion to prevent
hardcoded secrets and provide secure configuration management.
"""

import logging
import os
import re
from typing import Optional

from utils.error_handler import ConversionError

logger = logging.getLogger(__name__)


def expand_environment_variables(text: str, strict: bool = False) -> str:
    """
    Expand environment variables in text using ${VAR} or ${VAR:default} syntax.

    This function provides centralized environment variable expansion with
    support for multiple syntaxes and security best practices.

    Args:
        text: Raw text with environment variable placeholders
        strict: If True, raise error for undefined variables without defaults

    Returns:
        Text with environment variables expanded

    Raises:
        ConversionError: If strict=True and required variable is not set

    Syntax:
        ${VAR}          - Expands to value of VAR, keeps ${VAR} if not set (with warning)
        ${VAR:default}  - Expands to value of VAR, or 'default' if not set
        ${VAR:?error}   - Expands to value of VAR, or raises error if not set

    Examples:
        >>> os.environ['API_KEY'] = 'secret123'
        >>> expand_environment_variables('key=${API_KEY}')
        'key=secret123'

        >>> expand_environment_variables('url=${BASE_URL:https://api.example.com}')
        'url=https://api.example.com'

        >>> expand_environment_variables('${REQUIRED:?Must be set}')
        ConversionError: Required environment variable not set: REQUIRED
    """
    if not isinstance(text, str):
        return text

    def expand_var(match: re.Match) -> str:
        """Expand a single environment variable match."""
        var_expr = match.group(1)  # Content inside ${...}

        # Check for error syntax: ${VAR:?error message}
        if ':?' in var_expr:
            var_name, error_msg = var_expr.split(':?', 1)
            var_name = var_name.strip()
            value = os.environ.get(var_name)

            if value is None:
                raise ConversionError(
                    f"Required environment variable not set: {var_name}\n"
                    f"Error: {error_msg}\n"
                    f"Please set: export {var_name}=<value>"
                )

            logger.debug(f"Expanded required ${{{var_name}}} from environment")
            return value

        # Check for default syntax: ${VAR:default}
        elif ':' in var_expr:
            var_name, default = var_expr.split(':', 1)
            var_name = var_name.strip()
            value = os.environ.get(var_name, default)

            if value == default:
                logger.info(
                    f"Environment variable {var_name} not set, "
                    f"using default: {default[:20]}..."
                )
            else:
                logger.debug(f"Expanded ${{{var_name}}} from environment")

            return value

        # Simple syntax: ${VAR}
        else:
            var_name = var_expr.strip()
            value = os.environ.get(var_name)

            if value is None:
                if strict:
                    raise ConversionError(
                        f"Required environment variable not set: {var_name}\n"
                        f"Please set: export {var_name}=<value>\n"
                        f"Or use default syntax: ${{{var_name}:default_value}}"
                    )

                logger.warning(
                    f"[WARN] Environment variable {var_name} not set, keeping placeholder.\n"
                    f"   This will likely cause errors. Set the variable or use default syntax:\n"
                    f"   ${{{var_name}:default_value}}"
                )
                return match.group(0)  # Keep ${VAR} unchanged

            logger.debug(f"Expanded ${{{var_name}}} from environment")
            return value

    # Regex to match ${...} patterns
    # Matches: ${VAR}, ${VAR:default}, ${VAR:?error}
    pattern = r'\$\{([^}]+)\}'
    expanded = re.sub(pattern, expand_var, text)

    return expanded


def expand_dict_values(config: dict, strict: bool = False) -> dict:
    """
    Recursively expand environment variables in all string values of a dictionary.

    Args:
        config: Configuration dictionary with potential env var placeholders
        strict: If True, raise error for undefined variables

    Returns:
        Dictionary with all string values expanded

    Examples:
        >>> os.environ['PORT'] = '8080'
        >>> expand_dict_values({'server': {'port': '${PORT}'}})
        {'server': {'port': '8080'}}
    """
    if not isinstance(config, dict):
        return config

    expanded = {}
    for key, value in config.items():
        if isinstance(value, str):
            expanded[key] = expand_environment_variables(value, strict=strict)
        elif isinstance(value, dict):
            expanded[key] = expand_dict_values(value, strict=strict)
        elif isinstance(value, list):
            expanded[key] = [
                expand_environment_variables(item, strict=strict)
                if isinstance(item, str)
                else expand_dict_values(item, strict=strict)
                if isinstance(item, dict)
                else item
                for item in value
            ]
        else:
            expanded[key] = value

    return expanded


def validate_required_env_vars(*var_names: str) -> None:
    """
    Validate that required environment variables are set.

    Args:
        *var_names: Variable number of environment variable names to check

    Raises:
        ConversionError: If any required variable is not set

    Examples:
        >>> validate_required_env_vars('API_KEY', 'DATABASE_URL')
    """
    missing = [var for var in var_names if os.environ.get(var) is None]

    if missing:
        raise ConversionError(
            f"Required environment variables not set: {', '.join(missing)}\n"
            f"Please set the following:\n" +
            '\n'.join(f"  export {var}=<value>" for var in missing)
        )


def get_env_var(
    name: str,
    default: Optional[str] = None,
    required: bool = False,
    error_message: Optional[str] = None
) -> Optional[str]:
    """
    Get an environment variable with optional default and validation.

    Args:
        name: Environment variable name
        default: Default value if not set
        required: If True, raise error if not set and no default
        error_message: Custom error message if required and not set

    Returns:
        Environment variable value or default

    Raises:
        ConversionError: If required=True and variable not set

    Examples:
        >>> get_env_var('API_KEY', required=True)
        >>> get_env_var('PORT', default='8080')
        >>> get_env_var('DEBUG', default='false')
    """
    value = os.environ.get(name, default)

    if value is None and required:
        msg = error_message or f"Required environment variable not set: {name}"
        raise ConversionError(msg)

    return value
