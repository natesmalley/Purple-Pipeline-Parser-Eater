#!/usr/bin/env python3
"""
Complete RAG Ingestion Script - Local + External Sources
Ingests documentation from local files and external sources (websites, GitHub, S3)
with auto-update support
"""
import asyncio
import logging
import sys
from pathlib import Path
import yaml
from typing import Dict, List, Any

# Add components to path
sys.path.insert(0, str(Path(__file__).parent))

from components.observo_docs_processor import ObservoDocsManager
from components.s1_docs_processor import S1DocsManager
from components.rag_knowledge import RAGKnowledgeBase
from components.rag_sources import ExternalSourceScraper, AutoUpdateManager
from components.github_scanner import GitHubParserScanner
from components.data_ingestion_manager import DataIngestionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def ingest_local_docs(config: Dict, rag: RAGKnowledgeBase) -> Dict[str, Any]:
    """
    Ingest local documentation files (both Observo and SentinelOne)

    Args:
        config: Configuration dictionary
        rag: RAG knowledge base instance

    Returns:
        Ingestion statistics
    """
    print()
    print("=" * 80)
    print("[INGEST] LOCAL DOCUMENTATION INGESTION")
    print("=" * 80)
    print()

    total_stats = {
        "files_processed": 0,
        "chunks_created": 0,
        "chunks_ingested": 0,
        "errors": []
    }

    # Ingest Observo documentation
    observo_docs_dir = Path(__file__).parent / "observo docs"
    if observo_docs_dir.exists():
        print("[DOCS] Processing Observo.ai documentation...")
        print("-" * 80)
        observo_manager = ObservoDocsManager(
            docs_directory=str(observo_docs_dir),
            rag_knowledge_base=rag
        )

        try:
            observo_results = await observo_manager.process_and_ingest()
            total_stats["files_processed"] += observo_results['summary']['files_processed']
            total_stats["chunks_created"] += observo_results['summary']['chunks_created']
            total_stats["chunks_ingested"] += observo_results['summary']['chunks_ingested']
            total_stats["errors"].extend(observo_results['summary']['errors'])

            print("[OK] Observo Documentation Ingested:")
            print(f"   Files: {observo_results['summary']['files_processed']}")
            print(f"   Chunks: {observo_results['summary']['chunks_ingested']}")
            print(f"   Code Examples: {observo_results['summary']['code_examples']}")
            print(f"   API Endpoints: {observo_results['summary']['api_endpoints']}")
            print()
        except Exception as e:
            logger.error(f"Observo documentation ingestion failed: {e}")
            total_stats["errors"].append(str(e))
    else:
        logger.warning(f"Observo docs directory not found: {observo_docs_dir}")

    # Ingest SentinelOne documentation
    s1_docs_dir = Path(__file__).parent / "s1 docs"
    if s1_docs_dir.exists():
        print("[DOCS] Processing SentinelOne documentation...")
        print("-" * 80)
        s1_manager = S1DocsManager(
            docs_directory=str(s1_docs_dir),
            rag_knowledge_base=rag
        )

        try:
            s1_results = await s1_manager.process_and_ingest()
            total_stats["files_processed"] += s1_results['summary']['files_processed']
            total_stats["chunks_created"] += s1_results['summary']['chunks_created']
            total_stats["chunks_ingested"] += s1_results['summary']['chunks_ingested']
            total_stats["errors"].extend(s1_results['summary']['errors'])

            print("[OK] S1 Documentation Ingested:")
            print(f"   Files: {s1_results['summary']['files_processed']}")
            print(f"   Chunks: {s1_results['summary']['chunks_ingested']}")
            print(f"   Field Mappings: {s1_results['summary']['field_mappings_extracted']}")
            print(f"   Query Patterns: {s1_results['summary']['query_patterns_extracted']}")
            print(f"   API Endpoints: {s1_results['summary']['api_endpoints_extracted']}")
            print()
        except Exception as e:
            logger.error(f"S1 documentation ingestion failed: {e}")
            total_stats["errors"].append(str(e))
    else:
        logger.warning(f"S1 docs directory not found: {s1_docs_dir}")

    # Display combined results
    print()
    print("[OK] Local Documentation Ingestion Complete!")
    print("-" * 80)
    print("Combined Statistics:")
    print(f"  Files processed: {total_stats['files_processed']}")
    print(f"  Chunks created: {total_stats['chunks_created']}")
    print(f"  Chunks ingested: {total_stats['chunks_ingested']}")
    if total_stats['chunks_created'] > 0:
        success_rate = (total_stats['chunks_ingested'] / total_stats['chunks_created'] * 100)
        print(f"  Success rate: {success_rate:.1f}%")
    print()

    # Show errors if any
    if total_stats['errors']:
        print("[WARN]  Errors encountered:")
        for error in total_stats['errors'][:5]:
            print(f"  - {error}")
        if len(total_stats['errors']) > 5:
            print(f"  ... and {len(total_stats['errors']) - 5} more errors")
        print()

    return {"summary": total_stats}


async def ingest_external_sources(config: Dict, rag: RAGKnowledgeBase) -> Dict[str, Any]:
    """
    Ingest documentation from external sources

    Args:
        config: Configuration dictionary
        rag: RAG knowledge base instance

    Returns:
        Ingestion statistics
    """
    print()
    print("=" * 80)
    print("[WEB] EXTERNAL SOURCES INGESTION")
    print("=" * 80)
    print()

    # Check if external sources enabled
    rag_sources_config = config.get('rag_sources', {})
    if not rag_sources_config.get('enabled', False):
        logger.info("External sources disabled in config")
        print("[WARN]  External sources disabled in config.yaml")
        print("   Set 'rag_sources.enabled: true' to enable")
        print()
        return {"status": "disabled"}

    sources = rag_sources_config.get('sources', [])
    enabled_sources = [s for s in sources if s.get('enabled', False)]

    if not enabled_sources:
        logger.info("No external sources enabled")
        print("[WARN]  No external sources enabled in config.yaml")
        print("   Set 'enabled: true' for desired sources")
        print()
        return {"status": "no_sources"}

    print(f"[WEB] Enabled Sources: {len(enabled_sources)}")
    for source in enabled_sources:
        print(f"  - {source.get('name', 'Unnamed')}: {source.get('type')} ({source.get('url', source.get('bucket', source.get('path')))})")
    print()

    # Initialize scraper
    async with ExternalSourceScraper(config) as scraper:
        # Initialize auto-update manager
        update_manager = AutoUpdateManager(rag, scraper)

        # Update from all sources
        print("[SYNC] Scraping and ingesting external sources...")
        print("-" * 80)
        results = await update_manager.update_from_sources(enabled_sources)

        # Display results
        print()
        print("[OK] External Sources Ingestion Complete!")
        print("-" * 80)
        print("Statistics:")
        print(f"  Sources processed: {results['sources_processed']}")
        print(f"  New documents added: {results['total_added']}")
        print(f"  Documents updated: {results['total_updated']}")
        print(f"  Documents unchanged: {results['total_unchanged']}")
        print()

        # Show scraper statistics
        scraper_stats = scraper.get_statistics()
        print("Scraping Statistics:")
        print(f"  Sources scraped: {scraper_stats['sources_scraped']}")
        print(f"  Documents fetched: {scraper_stats['documents_fetched']}")
        print()

        # Show errors if any
        if scraper_stats['errors']:
            print("[WARN]  Errors encountered:")
            for error in scraper_stats['errors'][:5]:
                print(f"  - {error}")
            if len(scraper_stats['errors']) > 5:
                print(f"  ... and {len(scraper_stats['errors']) - 5} more errors")
            print()

        # Show update log
        update_log = update_manager.get_update_log()
        if update_log:
            print("Update Log:")
            for entry in update_log:
                status_icon = "[OK]" if entry["status"] == "success" else "[ERROR]"
                print(f"  {status_icon} {entry.get('source', 'unknown')} ({entry.get('type', 'unknown')}): "
                      f"{entry.get('documents', 0)} docs")
            print()

        return results


async def main():
    """Main ingestion workflow"""
    print()
    print("=" * 80)
    print("[START] PURPLE PIPELINE PARSER EATER - COMPREHENSIVE RAG INGESTION")
    print("   SentinelOne ↔ Observo.ai Complete Knowledge Base")
    print("=" * 80)
    print()
    print("Documentation Sources:")
    print("  [DOCS] SentinelOne: Query Language, OCSF, SDL API, GraphQL, Vulnerabilities")
    print("  [DOCS] Observo.ai: Pipeline Specs, Lua Examples, API Documentation")
    print("  [WEB] External: GitHub parsers, websites, S3 buckets")
    print("=" * 80)
    print()

    # Load configuration
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        logger.info("Please ensure config.yaml exists")
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
            print()
            print("[ERROR] RAG knowledge base initialization failed")
            print("   Please ensure Milvus is running:")
            print("   - Check that Milvus is accessible at configured host:port")
            print("   - Verify network connectivity")
            print("   - Review Milvus logs for errors")
            print()
            return 1
        logger.info("[OK] RAG knowledge base initialized")
        print("[OK] RAG knowledge base connected and ready")
        print()
    except Exception as e:
        logger.error(f"Failed to initialize RAG: {e}")
        return 1

    # Track overall statistics
    total_stats = {
        "local_ingested": 0,
        "external_added": 0,
        "external_updated": 0,
        "total_documents": 0
    }

    # Phase 1: Ingest local documentation
    try:
        local_results = await ingest_local_docs(config, rag)
        if local_results.get("status") != "skipped":
            total_stats["local_ingested"] = local_results.get("summary", {}).get("chunks_ingested", 0)
    except Exception as e:
        logger.error(f"Local ingestion failed: {e}")
        import traceback
        traceback.print_exc()

    # Phase 2: Ingest external sources
    try:
        external_results = await ingest_external_sources(config, rag)
        if external_results.get("status") not in ["disabled", "no_sources"]:
            total_stats["external_added"] = external_results.get("total_added", 0)
            total_stats["external_updated"] = external_results.get("total_updated", 0)
    except Exception as e:
        logger.error(f"External source ingestion failed: {e}")
        import traceback
        traceback.print_exc()

    # Calculate totals
    total_stats["total_documents"] = (
        total_stats["local_ingested"] +
        total_stats["external_added"]
    )

    # Final summary
    print()
    print("=" * 80)
    print("[SUCCESS] COMPLETE INGESTION FINISHED!")
    print("=" * 80)
    print()
    print("Overall Statistics:")
    print(f"  Local documents ingested: {total_stats['local_ingested']}")
    print(f"  External documents added: {total_stats['external_added']}")
    print(f"  External documents updated: {total_stats['external_updated']}")
    print(f"  Total documents in RAG: {total_stats['total_documents']}")
    print()
    print("=" * 80)
    print("[INGEST] Knowledge Base Now Contains:")
    print("=" * 80)
    print("  [OK] SentinelOne query language syntax and operators")
    print("  [OK] SentinelOne field definitions and GraphQL schemas")
    print("  [OK] OCSF event mappings (S1 ↔ OCSF ↔ Observo)")
    print("  [OK] SDL API endpoints and specifications")
    print("  [OK] Vulnerability data dictionary")
    print("  [OK] Observo pipeline specifications and patterns")
    print("  [OK] Lua transformation examples")
    print("  [OK] 165+ SentinelOne parser examples from GitHub")
    print()
    print("=" * 80)
    print("[START] Next Steps:")
    print("=" * 80)
    print("  1. Run 'python main.py' for intelligent S1 → Observo conversion")
    print("  2. System will leverage RAG for accurate field mappings")
    print("  3. Continuous learning from successful/failed conversions")
    print("  4. Configure auto-update intervals in config.yaml")
    print("  5. Enable additional external sources as needed")
    print()
    print("Auto-Update Configuration:")
    if config.get('rag_sources', {}).get('auto_update', False):
        update_interval = config.get('rag_sources', {}).get('update_interval', '24h')
        print(f"  [OK] Auto-update enabled (interval: {update_interval})")
        print("     External sources will be checked for updates automatically")
    else:
        print("  [WARN]  Auto-update disabled")
        print("     Set 'rag_sources.auto_update: true' in config.yaml to enable")
    print()
    print("=" * 80)

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
