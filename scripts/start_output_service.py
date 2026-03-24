#!/usr/bin/env python3
"""
Start the Output Service for event delivery.

Usage:
    python scripts/start_output_service.py [--config path/to/config.yaml]
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.output_service import OutputService


def load_config(config_path: str) -> dict:
    """Load YAML configuration file with path traversal protection."""
    if yaml is None:
        raise ImportError(
            "PyYAML is required. Install it with: pip install pyyaml"
        )
    
    # SECURITY FIX: Validate path to prevent path traversal
    from utils.security import validate_file_path
    
    base_dir = Path(__file__).parent.parent
    validated_path = validate_file_path(config_path, base_dir, allow_absolute=True)
    
    with open(validated_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_logging(config: dict) -> None:
    """Setup logging from configuration."""
    logging_config = config.get("logging", {})
    level = logging_config.get("level", "INFO")
    log_file = logging_config.get("file", None)
    log_format = logging_config.get(
        "format",
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    handlers = [logging.StreamHandler()]

    if log_file:
        # SECURITY FIX: Validate log file path to prevent path traversal
        from utils.security import safe_create_dir
        
        base_dir = Path(__file__).parent.parent
        log_path = Path(log_file)
        log_dir = safe_create_dir(str(log_path.parent), base_dir, allow_absolute=True)
        handlers.append(logging.FileHandler(log_path))

    logging.basicConfig(
        level=getattr(logging, level),
        format=log_format,
        handlers=handlers,
    )


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Start Output Service")
    parser.add_argument(
        "--config",
        default="./config/output_service.yaml",
        help="Path to configuration file",
    )
    args = parser.parse_args()

    # SECURITY FIX: Validate path before using it
    # load_config will validate the path, but we check existence first for better error messages
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)

    setup_logging(config)

    logger = logging.getLogger(__name__)
    logger.info("=" * 70)
    logger.info("Purple Pipeline Output Service Starting")
    logger.info("=" * 70)

    service = OutputService(config)

    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
