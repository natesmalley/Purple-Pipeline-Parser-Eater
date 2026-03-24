#!/usr/bin/env python3
"""
Start the RuntimeService for live event transformation.

This script starts the Agent 2 transform pipeline that:
1. Consumes raw security events from Agent 1
2. Routes to appropriate Lua parser based on manifest
3. Executes transformations with canary A/B testing
4. Publishes OCSF-compliant events for Agent 3

Usage:
    python scripts/start_runtime_service.py [--config path/to/config.yaml]

Environment Variables:
    LOG_LEVEL: Override logging level (DEBUG, INFO, WARNING, ERROR)
    MANIFEST_DIR: Override manifest directory path
"""

import asyncio
import argparse
import logging
import logging.handlers
import sys
import os
import yaml
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.runtime_service import RuntimeService


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file with path traversal protection.

    Args:
        config_path: Path to config.yaml file

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file not found
        yaml.YAMLError: If YAML is invalid
        SecurityError: If path traversal is detected
    """
    # SECURITY FIX: Validate path to prevent path traversal
    from utils.security import validate_file_path
    
    base_dir = Path(__file__).parent.parent
    config_file = validate_file_path(config_path, base_dir, allow_absolute=True)

    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

    if not config:
        raise ValueError(f"Configuration file is empty: {config_path}")

    return config


def setup_logging(config: dict) -> None:
    """Setup logging based on configuration.

    Args:
        config: Configuration dictionary
    """
    log_config = config.get("logging", {})

    # Get log level from config or environment
    level_name = os.getenv("LOG_LEVEL", log_config.get("level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    log_format = log_config.get(
        "format",
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Configure root logger
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=[
            logging.StreamHandler()
        ]
    )

    # Add file handler if configured
    log_file = log_config.get("file")
    if log_file:
        # SECURITY FIX: Validate log file path to prevent path traversal
        from utils.security import safe_create_dir
        
        base_dir = Path(__file__).parent.parent
        log_path = Path(log_file)
        safe_create_dir(str(log_path.parent), base_dir, allow_absolute=True)

        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(log_format))

        logging.getLogger().addHandler(file_handler)


def resolve_config(config: dict) -> dict:
    """Resolve environment variable overrides in config.

    Args:
        config: Configuration dictionary

    Returns:
        Updated configuration
    """
    # Allow environment override for manifest directory
    manifest_dir = os.getenv("MANIFEST_DIR")
    if manifest_dir:
        config["manifest_directory"] = manifest_dir
        logging.info(f"Using manifest directory from env: {manifest_dir}")

    return config


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Purple Pipeline - Agent 2: Transform Runtime Service",
        epilog="""
Examples:
  python scripts/start_runtime_service.py
  python scripts/start_runtime_service.py --config config/runtime_service.yaml
  LOG_LEVEL=DEBUG python scripts/start_runtime_service.py
        """
    )

    parser.add_argument(
        "--config",
        default="config/runtime_service.yaml",
        help="Path to configuration YAML file (default: config/runtime_service.yaml)"
    )

    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Validate configuration and exit"
    )

    args = parser.parse_args()

    try:
        # Load configuration
        config = load_config(args.config)

        # Setup logging
        setup_logging(config)

        # Resolve environment overrides
        config = resolve_config(config)

        logger = logging.getLogger(__name__)

        # Check config mode
        if args.check_config:
            logger.info("Configuration validation passed")
            logger.info(f"  Input topic: {config.get('transform_worker', {}).get('input_topic', 'raw-security-events')}")
            logger.info(f"  Output topic: {config.get('transform_worker', {}).get('output_topic', 'ocsf-events')}")
            logger.info(f"  Manifest dir: {config.get('manifest_directory', 'output')}")
            logger.info(f"  Executor: {config.get('executor', {}).get('type', 'lupa')}")
            return

        # Log startup
        logger.info("=" * 70)
        logger.info("🔄 Purple Pipeline - Agent 2: Transform Runtime Service")
        logger.info("=" * 70)
        logger.info("")
        logger.info("📊 Configuration:")
        logger.info(f"  Input topic: {config.get('transform_worker', {}).get('input_topic', 'raw-security-events')}")
        logger.info(f"  Output topic: {config.get('transform_worker', {}).get('output_topic', 'ocsf-events')}")
        logger.info(f"  Manifest directory: {config.get('manifest_directory', 'output')}")
        logger.info(f"  Executor: {config.get('executor', {}).get('type', 'lupa')}")
        logger.info(f"  Canary routing: {'enabled' if config.get('canary', {}).get('enabled') else 'disabled'}")
        logger.info(f"  Error DLQ: {'enabled' if config.get('error_handling', {}).get('dlq_enabled') else 'disabled'}")
        logger.info("")
        logger.info("Starting service... Press Ctrl+C to stop")
        logger.info("=" * 70)
        logger.info("")

        # Create and start service
        service = RuntimeService(config)

        try:
            await service.start()

        except KeyboardInterrupt:
            logger.info("")
            logger.info("Shutdown requested by user")

        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print(f"Please check the configuration file path", file=sys.stderr)
        sys.exit(1)

    except yaml.YAMLError as e:
        print(f"Error: Invalid YAML configuration: {e}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
