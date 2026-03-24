#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Populate RAG from Local SentinelOne Parser Repository

This script reads parsers from a local clone of the SentinelOne ai-siem repository
instead of using the GitHub API, avoiding rate limits.
"""

import asyncio
import yaml
import logging
import os
import sys
import json
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
    """Main function to populate RAG from local parsers"""

    print("\n" + "=" * 70)
    print("RAG POPULATION FROM LOCAL SENTINELONE REPOSITORY")
    print("=" * 70)
    print()

    # Load configuration
    config_path = Path("../config.yaml")
    if not config_path.exists():
        config_path = Path("config.yaml")

    if not config_path.exists():
        print("ERROR: config.yaml not found!")
        return 1

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Ask for local repository path
    print("Please provide the path to your local SentinelOne ai-siem repository")
    print("Example: C:\\Users\\username\\github\\ai-siem")
    print()

    repo_path_input = input("Repository path: ").strip().strip('"')
    
    # SECURITY FIX: Validate repository path to prevent path traversal
    # Note: For this script, we allow absolute paths since users may provide
    # paths to external repositories. However, we still validate the path exists
    # and is a directory. We also normalize the path to prevent traversal attacks.
    try:
        # Normalize the path to prevent traversal sequences
        normalized_input = os.path.normpath(repo_path_input)
        # Resolve to absolute path
        repo_path = Path(normalized_input).resolve()
        
        # Additional security: Check for path traversal sequences in the original input
        if '..' in repo_path_input or repo_path_input.startswith('/') and not os.path.isabs(normalized_input):
            print(f"\nERROR: Invalid path format: {repo_path_input}")
            return 1
        
        if not repo_path.exists():
            print(f"\nERROR: Directory not found: {repo_path}")
            print("\nPlease clone the repository first:")
            print("  git clone https://github.com/Sentinel-One/ai-siem.git")
            return 1
        
        if not repo_path.is_dir():
            print(f"\nERROR: Path is not a directory: {repo_path}")
            return 1
        
        # Additional validation: Ensure it's a real directory (not a symlink to outside)
        if repo_path.is_symlink():
            real_path = repo_path.resolve()
            if not real_path.exists() or not real_path.is_dir():
                print(f"\nERROR: Invalid symlink: {repo_path}")
                return 1
    except (OSError, ValueError) as e:
        print(f"\nERROR: Invalid path: {e}")
        return 1

    parsers_path = repo_path / "parsers"
    if not parsers_path.exists():
        print(f"\nERROR: Parsers directory not found: {parsers_path}")
        return 1

    # Initialize RAG Knowledge Base
    print("\n[1/3] Initializing RAG Knowledge Base...")
    from components.rag_knowledge import RAGKnowledgeBase

    knowledge_base = RAGKnowledgeBase(config=config)

    if not knowledge_base.enabled:
        print("ERROR: RAG Knowledge Base failed to initialize!")
        return 1

    print("SUCCESS: RAG Knowledge Base initialized")

    # Scan local parsers
    print(f"\n[2/3] Scanning local parsers from: {parsers_path}")

    parser_files = []

    # Scan community parsers
    community_path = parsers_path / "community"
    if community_path.exists():
        for parser_dir in community_path.iterdir():
            if parser_dir.is_dir():
                config_file = parser_dir / "config.json"
                if config_file.exists():
                    parser_files.append(config_file)

    # Scan sentinelone parsers
    s1_path = parsers_path / "sentinelone"
    if s1_path.exists():
        for parser_dir in s1_path.iterdir():
            if parser_dir.is_dir():
                config_file = parser_dir / "config.json"
                if config_file.exists():
                    parser_files.append(config_file)

    print(f"Found {len(parser_files)} parser configurations")

    if len(parser_files) == 0:
        print("\nERROR: No parser files found!")
        return 1

    # Ingest parsers
    print("\n[3/3] Ingesting parsers into RAG knowledge base...")

    ingested_count = 0
    error_count = 0

    for i, config_file in enumerate(parser_files, 1):
        try:
            # Read parser configuration
            with open(config_file, 'r', encoding='utf-8') as f:
                parser_config = json.load(f)

            parser_name = parser_config.get('name', config_file.parent.name)

            # Read parser.lua if it exists
            lua_file = config_file.parent / "parser.lua"
            lua_content = ""
            if lua_file.exists():
                with open(lua_file, 'r', encoding='utf-8') as f:
                    lua_content = f.read()

            # Build comprehensive document
            document_content = f"""
SentinelOne Parser Example: {parser_name}

Description: {parser_config.get('description', 'N/A')}
Author: {parser_config.get('author', 'Unknown')}
Version: {parser_config.get('version', 'Unknown')}

Configuration:
{json.dumps(parser_config, indent=2)}

LUA Parser Code:
```lua
{lua_content[:2000]}
```

This parser demonstrates:
- Configuration structure for {parser_name}
- Parser implementation patterns
- Field mappings and transformations
"""

            # Add to knowledge base
            await knowledge_base.add_document(
                content=document_content,
                metadata={
                    "doc_type": "parser_example",
                    "source": "sentinelone_local",
                    "parser_name": parser_name,
                    "timestamp": "local_scan"
                }
            )

            ingested_count += 1

            if i % 10 == 0:
                print(f"  Progress: {i}/{len(parser_files)} parsers processed ({ingested_count} ingested, {error_count} errors)")

        except Exception as e:
            error_count += 1
            logger.warning(f"Failed to ingest {config_file.name}: {e}")
            continue

    print("\n" + "=" * 70)
    print("INGESTION COMPLETE!")
    print("=" * 70)
    print(f"\nSuccessfully ingested: {ingested_count} parsers")
    print(f"Errors: {error_count}")
    print(f"Total in RAG knowledge base: {ingested_count}")
    print("=" * 70)

    print("\nSUCCESS: RAG knowledge base is now populated!")
    print("\nThe system will now:")
    print("  - Use these examples when generating new LUA code")
    print("  - Learn from successful patterns")
    print("  - Get better with each conversion\n")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
