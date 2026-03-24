#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Start RAG Auto-Sync Service

Background service that automatically keeps RAG knowledge base
in sync with SentinelOne GitHub repository.
"""

import asyncio
import yaml
import logging
import sys
import signal
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/rag_autosync.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class RAGAutoSyncService:
    """Background service for RAG auto-synchronization"""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = None
        self.knowledge_base = None
        self.updater = None
        self.update_task = None
        self.running = False

    async def initialize(self):
        """Initialize all components"""
        logger.info("=" * 70)
        logger.info("RAG AUTO-SYNC SERVICE INITIALIZATION")
        logger.info("=" * 70)

        # Load configuration
        logger.info(f"Loading configuration from: {self.config_path}")
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Check if auto-update is enabled
        rag_config = self.config.get('rag_auto_update', {})
        if not rag_config.get('enabled', True):
            logger.warning("RAG auto-update is disabled in config.yaml")
            return False

        interval = rag_config.get('interval_minutes', 60)
        repo_path = rag_config.get('local_repo_path')

        logger.info(f"Auto-update enabled: interval={interval} minutes")
        logger.info(f"Repository path: {repo_path}")

        # Verify repository exists
        if not repo_path or not Path(repo_path).exists():
            logger.error(f"Repository not found: {repo_path}")
            logger.error("Please clone the repository or update config.yaml")
            return False

        # Initialize RAG Knowledge Base
        logger.info("Initializing RAG Knowledge Base...")
        from components.rag_knowledge import RAGKnowledgeBase
        self.knowledge_base = RAGKnowledgeBase(config=self.config)

        if not self.knowledge_base.enabled:
            logger.error("RAG Knowledge Base failed to initialize")
            return False

        logger.info("RAG Knowledge Base initialized successfully")

        # Initialize Auto-Updater
        logger.info("Initializing RAG Auto-Updater...")
        from components.rag_auto_updater import RAGAutoUpdater
        self.updater = RAGAutoUpdater(config=self.config)

        logger.info("=" * 70)
        logger.info("INITIALIZATION COMPLETE")
        logger.info("=" * 70)

        return True

    async def start(self):
        """Start the auto-sync service"""
        if not await self.initialize():
            logger.error("Initialization failed, cannot start service")
            return

        self.running = True
        logger.info("Starting RAG Auto-Sync Service...")

        # Get repository path
        repo_path = Path(self.config['rag_auto_update']['local_repo_path'])

        # Start auto-update loop
        try:
            await self.updater.start_auto_update_loop(repo_path, self.knowledge_base)
        except asyncio.CancelledError:
            logger.info("Service cancelled")
        except Exception as e:
            logger.error(f"Service error: {e}", exc_info=True)
        finally:
            self.running = False

    async def stop(self):
        """Stop the auto-sync service"""
        logger.info("Stopping RAG Auto-Sync Service...")
        self.running = False
        if self.updater:
            self.updater.stop()
        logger.info("Service stopped")

    def get_status(self):
        """Get service status"""
        if self.updater:
            return self.updater.get_status()
        return {'running': self.running}


async def main():
    """Main entry point"""
    print("\n" + "=" * 70)
    print("RAG AUTO-SYNC SERVICE")
    print("=" * 70)
    print("\nThis service automatically keeps your RAG knowledge base")
    print("synchronized with the SentinelOne ai-siem GitHub repository.")
    print("\nPress Ctrl+C to stop the service.")
    print("=" * 70 + "\n")

    # Find config file
    config_path = Path("../config.yaml")
    if not config_path.exists():
        config_path = Path("config.yaml")

    if not config_path.exists():
        print("ERROR: config.yaml not found!")
        return 1

    # Create service
    service = RAGAutoSyncService(config_path)

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(service.stop())

    if sys.platform != "win32":
        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)

    # Start service
    try:
        await service.start()
    except KeyboardInterrupt:
        print("\nShutdown requested...")
        await service.stop()

    print("\nRAG Auto-Sync Service stopped.\n")
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nService interrupted by user")
        sys.exit(0)
