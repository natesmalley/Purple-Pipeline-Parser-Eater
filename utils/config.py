"""Configuration loader utility."""

from __future__ import annotations

import os
from pathlib import Path
import yaml

# Import security validation function to prevent path traversal
from utils.security import validate_file_path, SecurityError


def load_config(path: str | None = None) -> dict:
    """
    Load configuration file with path traversal protection.
    
    SECURITY: Validates that the config path is within the allowed directory
    to prevent path traversal attacks using the security module's validation.
    """
    # Get base directory (parent of utils directory)
    base_dir = Path(__file__).parent.parent.resolve()
    config_dir = base_dir / "config"
    
    # Get config path from parameter or environment variable
    config_path = path or os.environ.get("PPPE_CONFIG", "config.yaml")
    
    # SECURITY FIX: Use validate_file_path which validates before resolving
    # This prevents path traversal attacks by ensuring the path is within base_dir
    if os.path.isabs(config_path):
        # For absolute paths, validate against base_dir
        validated_path = validate_file_path(config_path, base_dir, allow_absolute=True)
    else:
        # For relative paths, validate against config_dir
        # First construct the full path, then validate it
        full_path = str(config_dir / config_path)
        validated_path = validate_file_path(full_path, base_dir, allow_absolute=False)
    
    # Use the validated path directly - it's guaranteed to be safe
    with open(validated_path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}

