#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated RAG Population Script (Non-Interactive)

This script automatically populates the RAG knowledge base with all available
training data without requiring user interaction.
"""

import asyncio
import yaml
import logging
import sys
from pathlib import Path

# Fix Windows console encoding issues
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """Main function to populate RAG knowledge base automatically"""

    print("\n" + "=" * 70)
    print("RAG KNOWLEDGE BASE POPULATION (AUTOMATED)")
    print("=" * 70)
    print("\nThis script will automatically ingest:")
    print("  1. SentinelOne ai-siem parsers (165+ examples)")
    print("  2. OCSF schema definitions")
    print("  3. Existing generated LUA examples")
    print("=" * 70 + "\n")

    # Load configuration
    config_path = Path("../config.yaml")
    if not config_path.exists():
        config_path = Path("config.yaml")

    if not config_path.exists():
        print("ERROR: config.yaml not found!")
        print("\nPlease create config.yaml before running this script.")
        print("See config.yaml.example for template.\n")
        return 1

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Initialize components
    print("[1/4] Initializing RAG Knowledge Base...")
    from components.rag_knowledge import RAGKnowledgeBase

    knowledge_base = RAGKnowledgeBase(config=config)

    if not knowledge_base.enabled:
        print("ERROR: RAG Knowledge Base failed to initialize!")
        print("\nPossible causes:")
        print("  - Milvus not running (run: docker-compose up -d)")
        print("  - Missing packages (run: pip install pymilvus sentence-transformers)")
        print("  - Configuration issues in config.yaml\n")
        return 1

    print("SUCCESS: RAG Knowledge Base initialized")

    # Initialize GitHub scanner with async context manager
    print("\n[2/4] Initializing GitHub Scanner...")
    from components.github_scanner import GitHubParserScanner
    from components.data_ingestion_manager import DataIngestionManager

    # Use async context manager for GitHub scanner
    async with GitHubParserScanner(config=config) as scanner:
        print("SUCCESS: GitHub Scanner initialized")

        # Initialize Data Ingestion Manager
        print("\n[3/4] Initializing Data Ingestion Manager...")
        ingestion_manager = DataIngestionManager(
            config=config,
            knowledge_base=knowledge_base,
            github_scanner=scanner
        )
        print("SUCCESS: Data Ingestion Manager initialized")

        # Automatically ingest ALL sources
        print("\n[4/4] Starting automated data ingestion...")
        print("Ingesting ALL sources: SentinelOne parsers, OCSF schema, generated examples\n")

        sources_to_ingest = ['sentinelone_parsers', 'ocsf_schema', 'generated_examples']

        # Perform ingestion
        statistics = await ingestion_manager.ingest_all_sources(sources=sources_to_ingest)

    print("\n" + "=" * 70)
    print("INGESTION COMPLETE!")
    print("=" * 70)
    print("\nStatistics:")
    print(f"  SentinelOne parsers: {statistics['sentinelone_parsers']}")
    print(f"  OCSF classes: {statistics['ocsf_classes']}")
    print(f"  Generated examples: {statistics['generated_examples']}")
    print(f"  Total documents: {statistics['total_documents']}")
    print("=" * 70)

    print("\nSUCCESS: RAG knowledge base is now populated and ready for use!")
    print("\nThe system will now:")
    print("  - Use these examples when generating new LUA code")
    print("  - Learn from successful patterns")
    print("  - Avoid patterns that led to failures")
    print("  - Get better with each conversion\n")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
