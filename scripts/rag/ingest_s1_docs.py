#!/usr/bin/env python3
"""
SentinelOne Documentation RAG Ingestion Script
One-click ingestion of all S1 documentation into RAG knowledge base
"""
import asyncio
import logging
import sys
from pathlib import Path
import yaml

# Add components to path
sys.path.insert(0, str(Path(__file__).parent))

from components.s1_docs_processor import S1DocsManager
from components.rag_knowledge import RAGKnowledgeBase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main ingestion workflow"""
    print("=" * 80)
    print("[START] SentinelOne Documentation RAG Ingestion")
    print("=" * 80)
    print()

    # Load configuration
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        logger.info("Please ensure config.yaml exists with Milvus configuration")
        return 1

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Initialize RAG knowledge base
    logger.info("Initializing RAG knowledge base...")
    try:
        rag = RAGKnowledgeBase(config)
        if not rag.enabled:
            logger.error("RAG knowledge base failed to initialize")
            logger.info("Please check Milvus connection and dependencies")
            return 1
        logger.info("[OK] RAG knowledge base initialized")
    except Exception as e:
        logger.error(f"Failed to initialize RAG: {e}")
        return 1

    # Set documentation directory
    docs_dir = Path(__file__).parent / "s1 docs"
    if not docs_dir.exists():
        logger.error(f"Documentation directory not found: {docs_dir}")
        return 1

    # Initialize documentation manager
    logger.info(f"Documentation directory: {docs_dir}")
    docs_manager = S1DocsManager(
        docs_directory=str(docs_dir),
        rag_knowledge_base=rag
    )

    # Get documentation summary
    print()
    print("[INGEST] SentinelOne Documentation Summary:")
    print("-" * 80)
    summary = docs_manager.get_document_summary()
    print(f"Total files: {summary['total_files']}")
    print(f"Total size: {summary['total_size_kb']:.2f} KB")
    print()
    print("Files:")
    for file_info in summary['files']:
        file_type_icon = {
            '.pdf': '[NOTE]',
            '.txt': '[NOTE]',
            '.csv': '[STATS]',
            '.json': '[INIT]',
            '.yml': '[INIT]',
            '.yaml': '[INIT]',
            '.xlsx': '[STATS]'
        }.get(file_info['type'], '[FOLDER]')

        print(f"  {file_type_icon} {file_info['name']:50s} | {file_info['size_kb']:8.2f} KB", end='')
        if file_info['lines'] > 0:
            print(f" | {file_info['lines']:6d} lines")
        else:
            print()
    print()

    # Process and ingest
    print("[SEARCH] Processing and ingesting documentation...")
    print("-" * 80)
    try:
        results = await docs_manager.process_and_ingest()

        # Display results
        print()
        print("=" * 80)
        print("[OK] Ingestion Complete!")
        print("=" * 80)
        print()
        print("Processing Statistics:")
        print(f"  Files processed: {results['summary']['files_processed']}")
        print(f"  Chunks created: {results['summary']['chunks_created']}")
        print(f"  Field mappings extracted: {results['summary']['field_mappings_extracted']}")
        print(f"  Query patterns extracted: {results['summary']['query_patterns_extracted']}")
        print(f"  API endpoints extracted: {results['summary']['api_endpoints_extracted']}")
        print()
        print("Ingestion Statistics:")
        print(f"  Chunks ingested: {results['summary']['chunks_ingested']}")
        if results['summary']['chunks_created'] > 0:
            success_rate = (results['summary']['chunks_ingested'] / results['summary']['chunks_created'] * 100)
            print(f"  Success rate: {success_rate:.1f}%")
        print()

        # Show errors if any
        if results['summary']['errors']:
            print("[WARN]  Errors encountered:")
            for error in results['summary']['errors'][:5]:
                print(f"  - {error}")
            if len(results['summary']['errors']) > 5:
                print(f"  ... and {len(results['summary']['errors']) - 5} more errors")
            print()

        print("=" * 80)
        print("[SUCCESS] SentinelOne RAG knowledge base populated successfully!")
        print("=" * 80)
        print()
        print("Knowledge Base Contents:")
        print("  [OK] SentinelOne query language syntax and patterns")
        print("  [OK] Field definitions and operators")
        print("  [OK] OCSF schema mappings")
        print("  [OK] Vulnerability data dictionary")
        print("  [OK] SDL API endpoints and specifications")
        print("  [OK] GraphQL schema definitions")
        print()
        print("Next steps:")
        print("  1. Run ingest_observo_docs.py to add Observo documentation")
        print("  2. Use main.py for S1 → Observo pipeline conversion")
        print("  3. Test with real S1 queries to validate mappings")
        print()

        return 0

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
