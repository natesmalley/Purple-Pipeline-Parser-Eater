#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Populate RAG Knowledge Base with Training Data

This script collects and ingests all available data sources into the
RAG knowledge base to enable machine learning and improvement
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
    """Main function to populate RAG knowledge base"""

    print("\n" + "=" * 70)
    print("RAG KNOWLEDGE BASE POPULATION")
    print("=" * 70)
    print("\nThis script will ingest training data from:")
    print("  1. SentinelOne ai-siem parsers (165+ examples)")
    print("  2. OCSF schema definitions")
    print("  3. Existing generated LUA examples")
    print("=" * 70 + "\n")

    # Load configuration
    config_path = Path("config.yaml")
    if not config_path.exists():
        print("[ERROR] ERROR: config.yaml not found!")
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
        print("[ERROR] ERROR: RAG Knowledge Base failed to initialize!")
        print("\nPossible causes:")
        print("  - Milvus not running (run: docker-compose up -d)")
        print("  - Missing packages (run: pip install pymilvus sentence-transformers)")
        print("  - Configuration issues in config.yaml\n")
        return 1

    print("[OK] RAG Knowledge Base initialized")

    # Initialize GitHub scanner
    print("\n[2/4] Initializing GitHub Scanner...")
    from components.github_scanner import GitHubParserScanner

    try:
        scanner = GitHubParserScanner(config=config)
        print("[OK] GitHub Scanner initialized")
    except Exception as e:
        logger.warning(f"GitHub Scanner initialization failed: {e}")
        scanner = None
        print("[WARN]  GitHub Scanner not available (will skip parser ingestion)")

    # Initialize Data Ingestion Manager
    print("\n[3/4] Initializing Data Ingestion Manager...")
    from components.data_ingestion_manager import DataIngestionManager

    ingestion_manager = DataIngestionManager(
        config=config,
        knowledge_base=knowledge_base,
        github_scanner=scanner
    )
    print("[OK] Data Ingestion Manager initialized")

    # Ingest all data sources
    print("\n[4/4] Starting data ingestion...\n")

    sources_to_ingest = []

    # Ask user what to ingest
    print("Select data sources to ingest:")
    print("  1. SentinelOne parsers (165+ examples, ~5-10 minutes)")
    print("  2. OCSF schema definitions (8 classes, ~30 seconds)")
    print("  3. Existing generated LUA examples (from output/ directory)")
    print("  4. ALL sources")
    print()

    choice = input("Enter your choice (1-4) or 'all': ").strip().lower()

    if choice in ['1', 'all']:
        sources_to_ingest.append('sentinelone_parsers')
    if choice in ['2', 'all']:
        sources_to_ingest.append('ocsf_schema')
    if choice in ['3', 'all']:
        sources_to_ingest.append('generated_examples')
    if choice == '4' or choice == 'all':
        sources_to_ingest = ['sentinelone_parsers', 'ocsf_schema', 'generated_examples']

    if not sources_to_ingest:
        print("\n[ERROR] No sources selected. Exiting.\n")
        return 0

    # Confirm before proceeding
    print(f"\nSelected sources: {', '.join(sources_to_ingest)}")
    confirm = input("\nProceed with ingestion? (y/n): ").strip().lower()

    if confirm != 'y':
        print("\n[ERROR] Ingestion cancelled.\n")
        return 0

    # Perform ingestion
    try:
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

        print("\n[OK] RAG knowledge base is now populated and ready for use!")
        print("\nThe system will now:")
        print("  - Use these examples when generating new LUA code")
        print("  - Learn from successful patterns")
        print("  - Avoid patterns that led to failures")
        print("  - Get better with each conversion\n")

        return 0

    except Exception as e:
        print(f"\n[ERROR] ERROR during ingestion: {e}")
        logger.exception("Ingestion failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
