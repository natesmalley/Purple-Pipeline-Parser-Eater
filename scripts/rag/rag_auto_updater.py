#!/usr/bin/env python3
"""
RAG Auto-Updater Service
Continuously monitors and updates RAG knowledge base from external sources
Runs as a background service checking for updates at configured intervals
"""
import asyncio
import logging
import sys
import signal
from pathlib import Path
from datetime import datetime, timedelta
import yaml
from typing import Dict, Optional

# Add components to path
sys.path.insert(0, str(Path(__file__).parent))

from components.rag_knowledge import RAGKnowledgeBase
from components.rag_sources import ExternalSourceScraper, AutoUpdateManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rag_auto_updater.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class RAGAutoUpdateService:
    """
    Background service for automatic RAG updates from external sources
    """

    def __init__(self, config: Dict):
        """
        Initialize auto-update service

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.rag: Optional[RAGKnowledgeBase] = None
        self.scraper: Optional[ExternalSourceScraper] = None
        self.update_manager: Optional[AutoUpdateManager] = None
        self.running = False
        self.update_count = 0
        self.last_update: Optional[datetime] = None

        # Parse update interval
        rag_sources_config = config.get('rag_sources', {})
        self.update_interval = self._parse_interval(
            rag_sources_config.get('update_interval', '24h')
        )
        self.enabled = rag_sources_config.get('enabled', False)
        self.auto_update = rag_sources_config.get('auto_update', False)

    def _parse_interval(self, interval: str) -> int:
        """Parse interval string to seconds"""
        if interval.endswith("h"):
            return int(interval[:-1]) * 3600
        elif interval.endswith("d"):
            return int(interval[:-1]) * 86400
        elif interval.endswith("w"):
            return int(interval[:-1]) * 604800
        elif interval.endswith("m"):
            return int(interval[:-1]) * 60
        else:
            return 86400  # Default: 24 hours

    async def start(self):
        """Start the auto-update service"""
        logger.info("=" * 80)
        logger.info("RAG Auto-Update Service Starting")
        logger.info("=" * 80)

        # Check if enabled
        if not self.enabled:
            logger.warning("RAG external sources disabled in config")
            logger.info("Set 'rag_sources.enabled: true' to enable")
            return

        if not self.auto_update:
            logger.warning("Auto-update disabled in config")
            logger.info("Set 'rag_sources.auto_update: true' to enable")
            return

        # Initialize RAG
        try:
            self.rag = RAGKnowledgeBase(self.config)
            if not self.rag.enabled:
                logger.error("RAG knowledge base failed to initialize")
                return
            logger.info("[OK] RAG knowledge base initialized")
        except Exception as e:
            logger.error(f"Failed to initialize RAG: {e}")
            return

        # Get enabled sources
        sources = self.config.get('rag_sources', {}).get('sources', [])
        enabled_sources = [s for s in sources if s.get('enabled', False)]

        if not enabled_sources:
            logger.warning("No external sources enabled")
            return

        logger.info(f"Monitoring {len(enabled_sources)} external sources")
        for source in enabled_sources:
            logger.info(f"  - {source.get('name', 'Unnamed')}: {source.get('type')} "
                       f"(interval: {source.get('update_interval', self.config['rag_sources']['update_interval'])})")

        # Initialize scraper and update manager
        self.scraper = ExternalSourceScraper(self.config)
        await self.scraper.__aenter__()
        self.update_manager = AutoUpdateManager(self.rag, self.scraper)

        # Start update loop
        self.running = True
        logger.info(f"Service started - checking for updates every {self.update_interval}s")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 80)

        try:
            await self._update_loop(enabled_sources)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            await self.shutdown()

    async def _update_loop(self, sources):
        """Main update loop"""
        while self.running:
            try:
                # Perform update
                logger.info("")
                logger.info("=" * 80)
                logger.info(f"Update Check #{self.update_count + 1} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info("=" * 80)

                results = await self.update_manager.update_from_sources(sources)

                # Log results
                logger.info("Update Results:")
                logger.info(f"  Sources processed: {results['sources_processed']}")
                logger.info(f"  New documents: {results['total_added']}")
                logger.info(f"  Updated documents: {results['total_updated']}")
                logger.info(f"  Unchanged documents: {results['total_unchanged']}")

                # Update statistics
                self.update_count += 1
                self.last_update = datetime.now()
                next_update = self.last_update + timedelta(seconds=self.update_interval)

                logger.info(f"Next update: {next_update.strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info("=" * 80)

                # Wait for next update
                await asyncio.sleep(self.update_interval)

            except Exception as e:
                logger.error(f"Update failed: {e}")
                import traceback
                traceback.print_exc()
                # Wait before retrying
                logger.info("Waiting 60s before retry...")
                await asyncio.sleep(60)

    async def shutdown(self):
        """Shutdown the service gracefully"""
        logger.info("")
        logger.info("=" * 80)
        logger.info("Shutting down RAG Auto-Update Service")
        logger.info("=" * 80)

        self.running = False

        if self.scraper:
            await self.scraper.__aexit__(None, None, None)

        logger.info(f"Total updates performed: {self.update_count}")
        if self.last_update:
            logger.info(f"Last update: {self.last_update.strftime('%Y-%m-%d %H:%M:%S')}")

        logger.info("Service stopped")
        logger.info("=" * 80)


async def main():
    """Main entry point"""
    # Load configuration
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        return 1

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Create and start service
    service = RAGAutoUpdateService(config)

    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info("Received interrupt signal")
        service.running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start service
    await service.start()

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
