"""Dataset-first harness models and fixture loading.

This module defines stable dataset input contracts for the harness without
coupling them to Lua execution mechanics.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


@dataclass(frozen=True)
class HarnessDatasetMetadata:
    """Dataset-level metadata, separate from per-event execution inputs."""

    dataset_id: str
    parser_name: str
    vendor: str = ""
    product: str = ""
    description: str = ""
    source: str = ""


@dataclass(frozen=True)
class HarnessDatasetCase:
    """Single dataset case with event input and expected behavior metadata."""

    case_id: str
    event: Dict[str, Any]
    name: str = ""
    description: str = ""
    expected_behavior: str = ""
    tags: Tuple[str, ...] = ()


@dataclass(frozen=True)
class HarnessDataset:
    """Complete harness dataset with deterministic case ordering."""

    metadata: HarnessDatasetMetadata
    cases: Tuple[HarnessDatasetCase, ...]

    def ordered_case_ids(self) -> Tuple[str, ...]:
        """Return case identifiers in deterministic traversal order."""
        return tuple(case.case_id for case in self.cases)


class HarnessDatasetLoader:
    """Load dataset fixtures from a stable on-disk layout."""

    METADATA_FILE = "metadata.json"
    CASES_DIR = "cases"

    def load_from_dir(self, dataset_dir: str | Path) -> HarnessDataset:
        """Load a dataset from ``metadata.json`` and ``cases/*.json``."""
        root = Path(dataset_dir)
        metadata = self._load_metadata(root / self.METADATA_FILE)
        cases = self._load_cases(root / self.CASES_DIR)

        if not cases:
            raise ValueError("Dataset must contain at least one case JSON file")

        return HarnessDataset(metadata=metadata, cases=tuple(cases))

    def _load_metadata(self, metadata_path: Path) -> HarnessDatasetMetadata:
        if not metadata_path.exists():
            raise ValueError(f"Missing dataset metadata file: {metadata_path}")

        payload = self._load_json(metadata_path)
        dataset_id = self._require_str(payload, "dataset_id", metadata_path)
        parser_name = self._require_str(payload, "parser_name", metadata_path)

        return HarnessDatasetMetadata(
            dataset_id=dataset_id,
            parser_name=parser_name,
            vendor=str(payload.get("vendor", "")),
            product=str(payload.get("product", "")),
            description=str(payload.get("description", "")),
            source=str(payload.get("source", "")),
        )

    def _load_cases(self, cases_dir: Path) -> List[HarnessDatasetCase]:
        if not cases_dir.exists() or not cases_dir.is_dir():
            raise ValueError(f"Missing dataset cases directory: {cases_dir}")

        case_files = sorted(cases_dir.glob("*.json"), key=lambda path: path.name)
        cases: List[HarnessDatasetCase] = []
        seen_case_ids = set()

        for case_file in case_files:
            payload = self._load_json(case_file)
            case_id = self._require_str(payload, "case_id", case_file)
            if case_id in seen_case_ids:
                raise ValueError(f"Duplicate case_id '{case_id}' in {case_file}")
            seen_case_ids.add(case_id)

            event = payload.get("event")
            if not isinstance(event, dict):
                raise ValueError(f"Case 'event' must be an object in {case_file}")

            tags = payload.get("tags", [])
            if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
                raise ValueError(f"Case 'tags' must be a list of strings in {case_file}")

            cases.append(
                HarnessDatasetCase(
                    case_id=case_id,
                    name=str(payload.get("name", "")),
                    description=str(payload.get("description", "")),
                    event=event,
                    expected_behavior=str(payload.get("expected_behavior", "")),
                    tags=tuple(tags),
                )
            )

        return cases

    @staticmethod
    def _load_json(path: Path) -> Dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    @staticmethod
    def _require_str(payload: Dict[str, Any], key: str, path: Path) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Missing required string '{key}' in {path}")
        return value.strip()


def iter_case_events(dataset: HarnessDataset) -> Iterable[Dict[str, Any]]:
    """Yield event payloads in deterministic dataset order.

    This helper intentionally exposes only execution inputs (events), while
    keeping dataset metadata separate.
    """
    for case in dataset.cases:
        yield case.event
