#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated RAG Population from Local SentinelOne Repository
"""

import asyncio
import yaml
import logging
import sys
import json
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def main():
    print("\n" + "=" * 70)
    print("RAG POPULATION FROM LOCAL SENTINELONE REPOSITORY (AUTO)")
    print("=" * 70 + "\n")

    # Load config
    config_path = Path("../config.yaml")
    if not config_path.exists():
        config_path = Path("config.yaml")

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Auto-detect repository path
    repo_path = Path("C:/Users/hexideciml/Documents/GitHub/ai-siem")

    print(f"Using repository: {repo_path}")

    if not repo_path.exists():
        print(f"\nERROR: Repository not found at {repo_path}")
        return 1

    parsers_path = repo_path / "parsers"
    if not parsers_path.exists():
        print(f"\nERROR: Parsers directory not found: {parsers_path}")
        return 1

    # Initialize RAG
    print("\n[1/3] Initializing RAG Knowledge Base...")
    from components.rag_knowledge import RAGKnowledgeBase
    knowledge_base = RAGKnowledgeBase(config=config)

    if not knowledge_base.enabled:
        print("ERROR: RAG Knowledge Base failed to initialize!")
        return 1

    print("SUCCESS: RAG initialized")

    # Scan parsers
    print(f"\n[2/3] Scanning parsers from: {parsers_path}")
    parser_dirs = []

    # Community parsers
    community_path = parsers_path / "community"
    if community_path.exists():
        for parser_dir in community_path.iterdir():
            if parser_dir.is_dir():
                parser_dirs.append(parser_dir)

    # SentinelOne parsers
    s1_path = parsers_path / "sentinelone"
    if s1_path.exists():
        for parser_dir in s1_path.iterdir():
            if parser_dir.is_dir():
                parser_dirs.append(parser_dir)

    print(f"Found {len(parser_dirs)} parser directories")

    # Ingest parsers
    print("\n[3/3] Ingesting parsers...")
    ingested = 0
    errors = 0

    for i, parser_dir in enumerate(parser_dirs, 1):
        try:
            parser_name = parser_dir.name

            # Read metadata.yaml
            metadata_file = parser_dir / "metadata.yaml"
            metadata = {}
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = yaml.safe_load(f) or {}

            # Read .conf file (parser configuration)
            conf_content = ""
            for conf_file in parser_dir.glob("*.conf"):
                with open(conf_file, 'r', encoding='utf-8') as f:
                    conf_content = f.read()
                break

            if not conf_content:
                continue

            # Build document
            document_content = f"""
SentinelOne Parser: {parser_name}

Description: {metadata.get('description', 'N/A')}
Author: {metadata.get('author', 'Unknown')}
Version: {metadata.get('version', 'Unknown')}
Purpose: {metadata.get('purpose', 'N/A')}

Metadata:
{yaml.dump(metadata, default_flow_style=False)}

Parser Configuration:
```
{conf_content[:4000]}
```

This parser demonstrates real-world patterns for parsing {parser_name} logs.
"""

            # Generate embedding and insert
            embedding = knowledge_base.embedding_model.encode(document_content).tolist()

            knowledge_base.collection.insert([
                [embedding],
                [document_content],
                [f"Parser: {parser_name}"],
                ["sentinelone_local"],
                ["parser_example"],
                [datetime.now().isoformat()]
            ])

            ingested += 1

            if i % 25 == 0:
                print(f"  Progress: {i}/{len(parser_dirs)} ({ingested} ingested, {errors} errors)")

        except Exception as e:
            errors += 1
            if errors < 10:
                logger.warning(f"Failed: {parser_dir.name}: {e}")
            continue

    # Flush collection to ensure all data is persisted
    if ingested > 0:
        knowledge_base.collection.flush()
        logger.info("Flushed collection to persist data")

    print("\n" + "=" * 70)
    print("INGESTION COMPLETE!")
    print("=" * 70)
    print(f"\nIngested: {ingested} parsers")
    print(f"Errors: {errors}")
    print("=" * 70)

    # Verify final count
    knowledge_base.collection.load()
    total_entities = knowledge_base.collection.num_entities
    print(f"\nTotal documents in RAG: {total_entities}")

    print("\nSUCCESS! RAG knowledge base populated with training data")
    print("The system will now use these examples to improve LUA generation\n")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
