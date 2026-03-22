#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG Auto-Updater - Automatic SentinelOne Parser Synchronization

Monitors the SentinelOne ai-siem GitHub repository for new/updated parsers
and automatically ingests them into the RAG knowledge base.
"""

import asyncio
import yaml
import logging
import hashlib
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Set, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class RAGAutoUpdater:
    """
    Automatically syncs RAG knowledge base with SentinelOne GitHub repository

    Features:
    - Periodic scanning for new/updated parsers
    - Differential updates (only new/changed parsers)
    - Configurable update interval
    - Persistent state tracking
    - Graceful error handling
    """

    def __init__(self, config: Dict):
        self.config = config
        self.update_interval = config.get('rag_auto_update', {}).get('interval_minutes', 60)
        self.enabled = config.get('rag_auto_update', {}).get('enabled', True)
        self.state_file = Path("data/rag_sync_state.json")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        self.known_parsers: Dict[str, str] = {}  # parser_name -> content_hash
        self.last_update: Optional[datetime] = None
        self.total_updates = 0
        self.is_running = False

        self._load_state()

        logger.info(f"RAG Auto-Updater initialized (enabled={self.enabled}, interval={self.update_interval}min)")

    def _load_state(self):
        """Load persistent state from disk"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.known_parsers = state.get('known_parsers', {})
                    last_update_str = state.get('last_update')
                    if last_update_str:
                        self.last_update = datetime.fromisoformat(last_update_str)
                    self.total_updates = state.get('total_updates', 0)

                logger.info(f"Loaded state: {len(self.known_parsers)} tracked parsers, last update: {self.last_update}")
            except Exception as e:
                logger.warning(f"Failed to load state: {e}, starting fresh")

    def _save_state(self):
        """Save persistent state to disk"""
        try:
            state = {
                'known_parsers': self.known_parsers,
                'last_update': self.last_update.isoformat() if self.last_update else None,
                'total_updates': self.total_updates,
                'saved_at': datetime.now().isoformat()
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _compute_parser_hash(self, parser_content: str, metadata: Dict) -> str:
        """Compute hash of parser content and metadata for change detection"""
        combined = f"{parser_content}||{json.dumps(metadata, sort_keys=True)}"
        return hashlib.sha256(combined.encode()).hexdigest()

    async def check_for_updates(self, repo_path: Path) -> Dict:
        """
        Check local repository for new/updated parsers

        Returns dict with update statistics
        """
        logger.info(f"Checking for parser updates in: {repo_path}")

        stats = {
            'scanned': 0,
            'new': 0,
            'updated': 0,
            'unchanged': 0,
            'errors': 0
        }

        parsers_to_update = []

        parsers_path = repo_path / "parsers"
        if not parsers_path.exists():
            logger.error(f"Parsers directory not found: {parsers_path}")
            return stats

        # Scan all parser directories
        for source_dir in ['community', 'sentinelone']:
            source_path = parsers_path / source_dir
            if not source_path.exists():
                continue

            for parser_dir in source_path.iterdir():
                if not parser_dir.is_dir():
                    continue

                stats['scanned'] += 1
                parser_name = parser_dir.name

                try:
                    # Read metadata
                    metadata_file = parser_dir / "metadata.yaml"
                    metadata = {}
                    if metadata_file.exists():
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = yaml.safe_load(f) or {}

                    # Read parser config
                    conf_content = ""
                    for conf_file in parser_dir.glob("*.conf"):
                        with open(conf_file, 'r', encoding='utf-8') as f:
                            conf_content = f.read()
                        break

                    if not conf_content:
                        continue

                    # Compute hash for change detection
                    current_hash = self._compute_parser_hash(conf_content, metadata)
                    previous_hash = self.known_parsers.get(parser_name)

                    if previous_hash is None:
                        # New parser
                        stats['new'] += 1
                        parsers_to_update.append({
                            'name': parser_name,
                            'path': parser_dir,
                            'content': conf_content,
                            'metadata': metadata,
                            'hash': current_hash,
                            'status': 'new'
                        })
                        logger.info(f"New parser detected: {parser_name}")

                    elif previous_hash != current_hash:
                        # Updated parser
                        stats['updated'] += 1
                        parsers_to_update.append({
                            'name': parser_name,
                            'path': parser_dir,
                            'content': conf_content,
                            'metadata': metadata,
                            'hash': current_hash,
                            'status': 'updated'
                        })
                        logger.info(f"Updated parser detected: {parser_name}")

                    else:
                        # Unchanged
                        stats['unchanged'] += 1

                except Exception as e:
                    stats['errors'] += 1
                    logger.warning(f"Failed to process {parser_name}: {e}")
                    continue

        logger.info(f"Scan complete: {stats['new']} new, {stats['updated']} updated, {stats['unchanged']} unchanged")

        return {
            'stats': stats,
            'parsers_to_update': parsers_to_update
        }

    async def apply_updates(self, updates: Dict, knowledge_base):
        """Apply updates to RAG knowledge base"""
        parsers_to_update = updates['parsers_to_update']

        if not parsers_to_update:
            logger.info("No updates to apply")
            return

        logger.info(f"Applying {len(parsers_to_update)} updates to RAG knowledge base...")

        ingested = 0
        errors = 0

        for parser_info in parsers_to_update:
            try:
                parser_name = parser_info['name']
                content = parser_info['content']
                metadata = parser_info['metadata']
                status = parser_info['status']

                # Build document
                document_content = f"""
SentinelOne Parser: {parser_name}

Status: {status.upper()}
Last Updated: {datetime.now().isoformat()}

Description: {metadata.get('description', 'N/A')}
Author: {metadata.get('author', 'Unknown')}
Version: {metadata.get('version', 'Unknown')}
Purpose: {metadata.get('purpose', 'N/A')}

Metadata:
{yaml.dump(metadata, default_flow_style=False)}

Parser Configuration:
```
{content[:4000]}
```

This parser demonstrates real-world patterns for parsing {parser_name} logs.
Auto-synced from SentinelOne ai-siem repository.
"""

                # Generate embedding and insert
                embedding = knowledge_base.embedding_model.encode(document_content).tolist()

                knowledge_base.collection.insert([
                    [embedding],
                    [document_content],
                    [f"Parser: {parser_name}"],
                    ["sentinelone_autosync"],
                    ["parser_example"],
                    [datetime.now().isoformat()]
                ])

                # Update known parsers
                self.known_parsers[parser_name] = parser_info['hash']
                ingested += 1

            except Exception as e:
                errors += 1
                logger.error(f"Failed to ingest {parser_info['name']}: {e}")
                continue

        # Flush to persist
        if ingested > 0:
            knowledge_base.collection.flush()
            logger.info(f"Flushed {ingested} updates to vector database")

        self.last_update = datetime.now()
        self.total_updates += ingested
        self._save_state()

        logger.info(f"Update complete: {ingested} ingested, {errors} errors")

    async def run_update_cycle(self, repo_path: Path, knowledge_base):
        """Execute one complete update cycle"""
        try:
            logger.info("=" * 70)
            logger.info(f"RAG AUTO-UPDATE CYCLE STARTED - {datetime.now().isoformat()}")
            logger.info("=" * 70)

            # Check for updates
            update_info = await self.check_for_updates(repo_path)

            # Apply updates if any
            await self.apply_updates(update_info, knowledge_base)

            stats = update_info['stats']
            logger.info("=" * 70)
            logger.info("UPDATE CYCLE COMPLETE")
            logger.info(f"New: {stats['new']}, Updated: {stats['updated']}, Total Updates: {self.total_updates}")
            logger.info("=" * 70)

        except Exception as e:
            logger.error(f"Update cycle failed: {e}", exc_info=True)

    async def start_auto_update_loop(self, repo_path: Path, knowledge_base):
        """Start the automatic update loop (runs in background)"""
        if not self.enabled:
            logger.info("RAG auto-update is disabled")
            return

        if self.is_running:
            logger.warning("Auto-update loop already running")
            return

        self.is_running = True
        logger.info(f"Starting RAG auto-update loop (interval: {self.update_interval} minutes)")

        # Run first update immediately
        await self.run_update_cycle(repo_path, knowledge_base)

        # Then run on schedule
        while self.is_running:
            try:
                # Wait for configured interval
                await asyncio.sleep(self.update_interval * 60)

                # Run update cycle
                await self.run_update_cycle(repo_path, knowledge_base)

            except asyncio.CancelledError:
                logger.info("Auto-update loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in auto-update loop: {e}")
                # Continue running despite errors
                await asyncio.sleep(60)  # Wait 1 minute before retry

        self.is_running = False
        logger.info("Auto-update loop stopped")

    def stop(self):
        """Stop the auto-update loop"""
        if self.is_running:
            logger.info("Stopping RAG auto-update loop...")
            self.is_running = False
            self._save_state()

    def get_status(self) -> Dict:
        """Get current status information"""
        return {
            'enabled': self.enabled,
            'is_running': self.is_running,
            'update_interval_minutes': self.update_interval,
            'tracked_parsers': len(self.known_parsers),
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'total_updates': self.total_updates,
            'next_update': (self.last_update + timedelta(minutes=self.update_interval)).isoformat()
                          if self.last_update else "pending"
        }


async def main():
    """Standalone test/demo of auto-updater"""
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Load config
    config_path = Path("../config.yaml")
    if not config_path.exists():
        config_path = Path("config.yaml")

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Initialize components
    from components.rag_knowledge import RAGKnowledgeBase

    knowledge_base = RAGKnowledgeBase(config=config)
    if not knowledge_base.enabled:
        print("ERROR: RAG Knowledge Base not initialized")
        return 1

    # Create auto-updater
    updater = RAGAutoUpdater(config)

    # Local repository path
    repo_path = Path("C:/Users/hexideciml/Documents/GitHub/ai-siem")

    if not repo_path.exists():
        print(f"ERROR: Repository not found: {repo_path}")
        return 1

    # Run single update cycle
    await updater.run_update_cycle(repo_path, knowledge_base)

    print("\nStatus:", json.dumps(updater.get_status(), indent=2))

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
