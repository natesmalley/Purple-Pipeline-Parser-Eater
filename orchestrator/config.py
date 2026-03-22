"""Configuration loading and management for orchestrator."""

import logging
import yaml
from pathlib import Path
from typing import Dict

from utils.error_handler import ConversionError
from utils.config_expansion import expand_environment_variables

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> Dict:
    """
    Load configuration from YAML file with environment variable expansion.

    SECURITY FIX: Implements ${VAR} environment variable expansion
    Supports:
        ${VAR}          - Expands to value of VAR, keeps ${VAR} if not set (with warning)
        ${VAR:default}  - Expands to value of VAR, or 'default' if not set
        ${VAR:?error}   - Expands to value of VAR, or raises error if not set

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Configuration dictionary

    Raises:
        ConversionError: If configuration cannot be loaded
    """
    config_file = Path(config_path)

    # Check if file exists
    if not config_file.exists():
        raise ConversionError(
            f"Configuration file not found: {config_path}\n"
            f"Please create config.yaml from config.yaml.example\n"
            f"See SETUP.md for instructions"
        )

    try:
        # Read raw YAML content
        with open(config_file, 'r', encoding='utf-8') as f:
            config_text = f.read()

        # SECURITY FIX: Expand environment variables before parsing YAML
        expanded_text = expand_environment_variables(config_text, strict=False)

        # Parse expanded YAML
        config = yaml.safe_load(expanded_text)

        if not config:
            raise ConversionError("Configuration file is empty")

        # Validate required sections
        required_sections = ['anthropic', 'observo', 'processing']
        missing = [s for s in required_sections if s not in config]
        if missing:
            raise ConversionError(
                f"Missing required config sections: {missing}\n"
                f"Check config.yaml.example for complete structure"
            )

        logger.info(f"[OK] Loaded configuration from {config_path}")
        logger.info(f"[OK] Environment variable expansion enabled")
        return config

    except yaml.YAMLError as e:
        raise ConversionError(f"Invalid YAML syntax in config file: {e}")
    except ConversionError:
        raise  # Re-raise our custom errors
    except Exception as e:
        raise ConversionError(f"Failed to load configuration: {e}")
