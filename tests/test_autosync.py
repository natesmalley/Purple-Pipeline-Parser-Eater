#!/usr/bin/env python3
"""Quick test of RAG auto-sync functionality.

Batch 5 Stream D fix — this file is a CLI harness that requires a live
`config.yaml` in the working directory and a populated RAG sync state
file. It was historically invoked as `python tests/test_autosync.py`.
Pytest used to fail collection entirely on this file because:

1. The async helper below was named `test_autosync` which pytest
   mis-collects as a test function.
2. More critically, `asyncio.run(test_autosync())` was called at
   module TOP LEVEL (not under `if __name__ == "__main__"`), so
   pytest's collection pass executed the whole script and hit a
   `FileNotFoundError: config.yaml` before any test could even load.

The fix moves the CLI invocation under an `if __name__ == "__main__"`
guard and marks the whole module as skipped under pytest. The
`python tests/test_autosync.py` entry point still works for operators
running the CLI harness directly.
"""

import asyncio
import yaml
import sys
from pathlib import Path
from datetime import datetime

import pytest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

pytestmark = pytest.mark.skip(
    reason="CLI harness: requires live config.yaml + RAG sync state. "
    "Run directly via `python tests/test_autosync.py`, not via pytest."
)


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


if __name__ == "__main__":
    asyncio.run(test_autosync())
