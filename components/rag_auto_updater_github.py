#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG Auto-Updater - GitHub Cloud Synchronization

Monitors the SentinelOne ai-siem GitHub repository (cloud) for new/updated parsers
and automatically ingests them into the RAG knowledge base.
"""

import asyncio
import yaml
import logging
import hashlib
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class RAGAutoUpdaterGitHub:
    """
    Automatically syncs RAG knowledge base with SentinelOne GitHub repository (cloud)

    Features:
    - Periodic scanning via GitHub API
    - Differential updates (only new/changed parsers)
    - Configurable update interval
    - Persistent state tracking
    - Graceful error handling with rate limit awareness
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

        logger.info(f"RAG Auto-Updater (GitHub) initialized (enabled={self.enabled}, interval={self.update_interval}min)")

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
                'saved_at': datetime.now().isoformat(),
                'source': 'github_api'
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _compute_parser_hash(self, parser_content: str, metadata: Dict) -> str:
        """Compute hash of parser content and metadata for change detection"""
        combined = f"{parser_content}||{json.dumps(metadata, sort_keys=True)}"
        return hashlib.sha256(combined.encode()).hexdigest()

    async def check_for_updates(self, github_scanner) -> Dict:
        """
        Check GitHub repository for new/updated parsers using GitHub API

        Args:
            github_scanner: GitHubParserScanner instance (with async context)

        Returns dict with update statistics
        """
        logger.info("Checking for parser updates from GitHub cloud repository...")

        stats = {
            'scanned': 0,
            'new': 0,
            'updated': 0,
            'unchanged': 0,
            'errors': 0
        }

        parsers_to_update = []

        try:
            # Fetch all parsers from GitHub
            logger.info("Fetching parsers from SentinelOne GitHub repository...")
            parsers = await github_scanner.scan_parsers()

            logger.info(f"Fetched {len(parsers)} parsers from GitHub")

            for parser in parsers:
                stats['scanned'] += 1
                # FIXED: Handle both old (name/content) and new (parser_id/config) formats
                parser_name = parser.get('parser_id') or parser.get('parser_name') or parser.get('name') or 'unknown'

                try:
                    # Get parser content (handle both dict/list and string formats)
                    content = parser.get('config') or parser.get('content') or {}

                    # Serialize dict/list content to string
                    if isinstance(content, (dict, list)):
                        import json
                        serialized_content = json.dumps(content, indent=2)
                    else:
                        serialized_content = str(content)

                    metadata = parser.get('metadata', {})

                    if not serialized_content or serialized_content == '{}':
                        continue

                    # Compute hash for change detection
                    current_hash = self._compute_parser_hash(serialized_content, metadata)
                    previous_hash = self.known_parsers.get(parser_name)

                    if previous_hash is None:
                        # New parser
                        stats['new'] += 1
                        parsers_to_update.append({
                            'name': parser_name,
                            'content': serialized_content,
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
                            'content': serialized_content,
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

        except Exception as e:
            logger.error(f"Failed to fetch parsers from GitHub: {e}")
            stats['errors'] += 1

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
Source: GitHub Cloud (api.github.com)

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
Auto-synced from SentinelOne ai-siem GitHub repository.
"""

                # Generate embedding and insert
                embedding = knowledge_base.embedding_model.encode(document_content).tolist()

                knowledge_base.collection.insert([
                    [embedding],
                    [document_content],
                    [f"Parser: {parser_name}"],
                    ["sentinelone_github_sync"],
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

    async def run_update_cycle(self, github_scanner, knowledge_base):
        """Execute one complete update cycle"""
        try:
            logger.info("=" * 70)
            logger.info(f"RAG AUTO-UPDATE CYCLE STARTED (GitHub Cloud) - {datetime.now().isoformat()}")
            logger.info("=" * 70)

            # Check for updates
            update_info = await self.check_for_updates(github_scanner)

            # Apply updates if any
            await self.apply_updates(update_info, knowledge_base)

            stats = update_info['stats']
            logger.info("=" * 70)
            logger.info("UPDATE CYCLE COMPLETE")
            logger.info(f"New: {stats['new']}, Updated: {stats['updated']}, Total Updates: {self.total_updates}")
            logger.info("=" * 70)

        except Exception as e:
            logger.error(f"Update cycle failed: {e}", exc_info=True)

    async def start_auto_update_loop(self, github_scanner, knowledge_base):
        """Start the automatic update loop (runs in background)"""
        if not self.enabled:
            logger.info("RAG auto-update is disabled")
            return

        if self.is_running:
            logger.warning("Auto-update loop already running")
            return

        self.is_running = True
        logger.info(f"Starting RAG auto-update loop (GitHub Cloud, interval: {self.update_interval} minutes)")

        # Run first update immediately
        await self.run_update_cycle(github_scanner, knowledge_base)

        # Then run on schedule
        while self.is_running:
            try:
                # Wait for configured interval
                logger.info(f"Next update in {self.update_interval} minutes...")
                await asyncio.sleep(self.update_interval * 60)

                # Run update cycle
                await self.run_update_cycle(github_scanner, knowledge_base)

            except asyncio.CancelledError:
                logger.info("Auto-update loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in auto-update loop: {e}")
                # Continue running despite errors
                logger.info("Retrying in 5 minutes...")
                await asyncio.sleep(300)  # Wait 5 minutes before retry

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
                          if self.last_update else "pending",
            'source': 'github_cloud_api'
        }
