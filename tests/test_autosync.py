#!/usr/bin/env python3
"""Quick test of RAG auto-sync functionality"""

import asyncio
import yaml
import sys
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

async def test_autosync():
    print("\nTesting RAG Auto-Sync Configuration...\n")

    # Load config
    config_path = Path("../config.yaml")
    if not config_path.exists():
        config_path = Path("config.yaml")

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Check configuration
    rag_config = config.get('rag_auto_update', {})
    print(f"Enabled: {rag_config.get('enabled', False)}")
    print(f"Interval: {rag_config.get('interval_minutes', 60)} minutes")
    print(f"Repo Path: {rag_config.get('local_repo_path')}")

    # Check if repo exists
    repo_path = Path(rag_config.get('local_repo_path', ''))
    if repo_path.exists():
        print(f"Repository: FOUND at {repo_path}")
        parsers_count = len(list((repo_path / "parsers" / "community").glob("*")))
        print(f"Community Parsers: {parsers_count}")
    else:
        print(f"Repository: NOT FOUND")

    # Check if state file exists
    state_file = Path("data/rag_sync_state.json")
    if state_file.exists():
        import json
        with open(state_file, 'r') as f:
            state = json.load(f)
        print(f"\nSync State:")
        print(f"  Tracked parsers: {len(state.get('known_parsers', {}))}")
        print(f"  Last update: {state.get('last_update', 'Never')}")
        print(f"  Total updates: {state.get('total_updates', 0)}")
    else:
        print(f"\nSync State: No state file (first run)")

    print("\nConfiguration OK [OK]\n")

asyncio.run(test_autosync())
