#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test GitHub Cloud Sync - Single Update Cycle

Tests the GitHub cloud-based RAG auto-sync without running continuous service.
"""

import asyncio
import yaml
import logging
import sys
from pathlib import Path

import pytest

# Batch 1 Stream D fix — this file is a CLI harness that requires a live
# Milvus instance + a populated config.yaml. The async helper below is
# named test_github_sync only for the CLI entry point; pytest historically
# mis-collected it as a test function without fixtures, producing a hard
# failure in the full-tree run. Mark the whole module as skipped under
# pytest so it surfaces as a clean skip. The `if __name__ == "__main__"`
# entrypoint at the bottom of this file still runs the real cycle when
# invoked directly via `python tests/test_github_sync.py`.
pytestmark = pytest.mark.skip(
    reason="CLI harness: requires live Milvus + config.yaml. Run directly, "
    "not via pytest."
)

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_github_sync():
    """Test single update cycle from GitHub cloud"""

    print("\n" + "=" * 70)
    print("TESTING RAG GITHUB CLOUD SYNC")
    print("=" * 70 + "\n")

    # Load configuration
    config_path = Path("../config.yaml")
    if not config_path.exists():
        config_path = Path("config.yaml")

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    print("Configuration loaded [OK]")

    # Check GitHub token
    github_token = config.get('github', {}).get('token')
    if github_token:
        print(f"GitHub token: Configured (first 10 chars: {github_token[:10]}...)")
    else:
        print("GitHub token: Not configured (60 requests/hour limit)")

    # Initialize RAG Knowledge Base
    print("\n[1/4] Initializing RAG Knowledge Base...")
    from components.rag_knowledge import RAGKnowledgeBase

    knowledge_base = RAGKnowledgeBase(config=config)

    if not knowledge_base.enabled:
        print("ERROR: RAG Knowledge Base failed to initialize!")
        print("Check that Milvus is running: docker ps | grep milvus")
        return 1

    # Get current document count
    knowledge_base.collection.load()
    initial_count = knowledge_base.collection.num_entities
    print(f"[OK] RAG initialized (current documents: {initial_count})")

    # Initialize GitHub Scanner
    print("\n[2/4] Initializing GitHub Scanner...")
    from components.github_scanner import GitHubParserScanner

    # Initialize Auto-Updater
    print("\n[3/4] Initializing Auto-Updater...")
    from components.rag_auto_updater_github import RAGAutoUpdaterGitHub

    updater = RAGAutoUpdaterGitHub(config=config)
    print(f"[OK] Auto-Updater initialized")
    print(f"  - Tracked parsers: {len(updater.known_parsers)}")
    print(f"  - Last update: {updater.last_update or 'Never'}")
    print(f"  - Total updates: {updater.total_updates}")

    # Run single update cycle
    print("\n[4/4] Running single update cycle from GitHub...")
    print("This will:")
    print("  - Fetch parsers from GitHub API")
    print("  - Compare with known parsers")
    print("  - Ingest only new/changed parsers")
    print("\nStarting...\n")

    # Use async context manager for GitHub scanner
    async with GitHubParserScanner(github_token=github_token, config=config) as scanner:
        print("[OK] GitHub Scanner session created")

        try:
            # Run update cycle
            await updater.run_update_cycle(scanner, knowledge_base)

            # Get final counts
            knowledge_base.collection.load()
            final_count = knowledge_base.collection.num_entities
            added = final_count - initial_count

            print("\n" + "=" * 70)
            print("TEST COMPLETE")
            print("=" * 70)
            print(f"\nInitial documents: {initial_count}")
            print(f"Final documents: {final_count}")
            print(f"Documents added: {added}")
            print(f"\nStatus: {updater.get_status()}")
            print("\n[OK] GitHub cloud sync is working!\n")

            return 0

        except Exception as e:
            logger.error(f"Update cycle failed: {e}", exc_info=True)
            return 1


if __name__ == "__main__":
    exit_code = asyncio.run(test_github_sync())
    sys.exit(exit_code)
