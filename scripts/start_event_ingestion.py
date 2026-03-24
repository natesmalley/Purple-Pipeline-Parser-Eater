#!/usr/bin/env python3
"""Event Ingestion Service Entrypoint.

Starts all enabled event sources and routes events to message bus.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import yaml
from pathlib import Path

from services.event_ingest_manager import EventIngestManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file.

    Args:
        config_path: Path to event_sources.yaml configuration file.

    Returns:
        Parsed configuration dictionary.

    Raises:
        FileNotFoundError: If configuration file doesn't exist.
        yaml.YAMLError: If configuration is invalid YAML.
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_file) as f:
        config = yaml.safe_load(f)

    if not config:
        raise ValueError("Configuration file is empty")

    return config


async def main() -> None:
    """Main event ingestion service loop.

    Initializes and starts all enabled event sources,
    routes events to message bus, handles graceful shutdown.
    """
    config_path = "config/event_sources.yaml"

    try:
        # Load configuration
        logger.info("Loading configuration from %s", config_path)
        config = load_config(config_path)

        # Create manager
        manager = EventIngestManager(config)

        # Initialize all sources
        logger.info("Initializing event sources...")
        await manager.initialize()

        # Start all sources
        logger.info("Starting event ingestion...")
        await manager.start()

        logger.info(
            "Event ingestion running with %d sources",
            len(manager.sources),
        )

        # Print metrics periodically
        async def print_metrics() -> None:
            """Print metrics every 60 seconds."""
            while True:
                await asyncio.sleep(60)
                stats = manager.get_metrics()
                logger.info(
                    "Ingestion metrics - Processed: %d, Errors: %d, Sources: %s",
                    stats["events_processed"],
                    stats["errors"],
                    stats["events_by_source"],
                )

        metrics_task = asyncio.create_task(print_metrics())

        # Handle shutdown signals
        def signal_handler(sig, frame) -> None:
            logger.info("Received shutdown signal")
            raise KeyboardInterrupt

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Run forever until interrupted
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down event ingestion...")
            metrics_task.cancel()
            await manager.stop()
            logger.info("Event ingestion stopped")

    except FileNotFoundError as e:
        logger.error("Configuration error: %s", e)
        sys.exit(1)
    except yaml.YAMLError as e:
        logger.error("YAML parsing error: %s", e)
        sys.exit(1)
    except ValueError as e:
        logger.error("Configuration validation error: %s", e)
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
