#!/usr/bin/env python3
"""
Observo.ai Documentation RAG Ingestion Script
One-click ingestion of all Observo documentation into RAG knowledge base
"""
import asyncio
import logging
import sys
from pathlib import Path
import yaml

# Add components to path
sys.path.insert(0, str(Path(__file__).parent))

from components.observo_docs_processor import ObservoDocsManager
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
    print("Observo.ai Documentation RAG Ingestion")
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
    docs_dir = Path(__file__).parent / "observo docs"
    if not docs_dir.exists():
        logger.error(f"Documentation directory not found: {docs_dir}")
        return 1

    # Initialize documentation manager
    logger.info(f"Documentation directory: {docs_dir}")
    docs_manager = ObservoDocsManager(
        docs_directory=str(docs_dir),
        rag_knowledge_base=rag
    )

    # Get documentation summary
    print()
    print("Documentation Summary:")
    print("-" * 80)
    summary = docs_manager.get_document_summary()
    print(f"Total files: {summary['total_files']}")
    print(f"Total size: {summary['total_size_kb']} KB")
    print()
    print("Files:")
    for file_info in summary['files'][:10]:  # Show top 10
        print(f"  - {file_info['name']:30s} | {file_info['size_kb']:6.2f} KB | {file_info['lines']:5d} lines")
    if len(summary['files']) > 10:
        print(f"  ... and {len(summary['files']) - 10} more files")
    print()

    # Process and ingest
    print("Processing and ingesting documentation...")
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
        print(f"  Code examples: {results['summary']['code_examples']}")
        print(f"  API endpoints: {results['summary']['api_endpoints']}")
        print()
        print("Ingestion Statistics:")
        print(f"  Chunks ingested: {results['summary']['chunks_ingested']}")
        print(f"  Success rate: {(results['summary']['chunks_ingested'] / results['summary']['chunks_created'] * 100):.1f}%")
        print()

        # Show errors if any
        if results['summary']['errors']:
            print("[WARN] Errors encountered:")
            for error in results['summary']['errors'][:5]:
                print(f"  - {error}")
            if len(results['summary']['errors']) > 5:
                print(f"  ... and {len(results['summary']['errors']) - 5} more errors")
            print()

        print("=" * 80)
        print("[SUCCESS] RAG knowledge base populated successfully!")
        print("=" * 80)
        print()
        print("Next steps:")
        print("  1. Run the main application to use RAG-enhanced pipeline building")
        print("  2. Use observo_query_patterns.py for intelligent queries")
        print("  3. Check RAG performance with test queries")
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
