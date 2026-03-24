"""Standalone harness CLI for dataset-first workflows.

PR-6 scope: lightweight operator UX for local dataset inspection and smoke usage.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .harness_dataset import HarnessDatasetLoader


def _build_summary(dataset_dir: Path) -> Dict[str, Any]:
    loader = HarnessDatasetLoader()
    dataset = loader.load_from_dir(dataset_dir)

    return {
        "dataset_id": dataset.metadata.dataset_id,
        "parser_name": dataset.metadata.parser_name,
        "vendor": dataset.metadata.vendor,
        "product": dataset.metadata.product,
        "source": dataset.metadata.source,
        "case_count": len(dataset.cases),
        "case_ids": list(dataset.ordered_case_ids()),
    }


def _build_case_rows(dataset_dir: Path) -> List[Dict[str, Any]]:
    loader = HarnessDatasetLoader()
    dataset = loader.load_from_dir(dataset_dir)

    rows: List[Dict[str, Any]] = []
    for case in dataset.cases:
        rows.append(
            {
                "case_id": case.case_id,
                "name": case.name,
                "description": case.description,
                "expected_behavior": case.expected_behavior,
                "tags": list(case.tags),
            }
        )
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Standalone testing harness dataset CLI")
    parser.add_argument("--dataset-dir", required=True, help="Path to harness dataset directory")
    parser.add_argument(
        "--list-cases",
        action="store_true",
        help="Emit deterministic JSON array of case metadata",
    )

    args = parser.parse_args(argv)

    dataset_dir = Path(args.dataset_dir)

    try:
        if args.list_cases:
            payload: Any = _build_case_rows(dataset_dir)
        else:
            payload = _build_summary(dataset_dir)

        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    except ValueError as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
