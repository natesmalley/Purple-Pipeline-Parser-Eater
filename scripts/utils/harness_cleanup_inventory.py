#!/usr/bin/env python3
"""Build keep/delete manifests for harness-only repository cleanup."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


KEEP_TOP_LEVEL = {
    "AGENTS.md",
    "README.md",
    "config.yaml",
    "config.yaml.example",
    "requirements.txt",
    "requirements.in",
    "requirements-minimal.txt",
    "continuous_conversion_service.py",
    "components",
    "services",
    "utils",
    "config",
    "tests",
    "scripts",
    "data",
    "output",
    "docs",
    ".codex",
}

KEEP_DOCS_SUBDIRS = {"harness", "reference", "archive_legacy"}
DELETE_TOP_LEVEL_RECOMMENDED = {"deployment", "systemd"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _relative_entries(root: Path) -> List[str]:
    entries = []
    for entry in root.iterdir():
        if entry.name in {".git", ".venv", ".pytest_cache"}:
            continue
        entries.append(entry.name)
    return sorted(entries)


def build_manifests(repo_root: Path) -> Dict[str, List[str]]:
    keep: List[str] = []
    delete: List[str] = []
    review: List[str] = []

    for name in _relative_entries(repo_root):
        if name in KEEP_TOP_LEVEL:
            keep.append(name)
            continue
        if name in DELETE_TOP_LEVEL_RECOMMENDED:
            delete.append(name)
            continue
        if name.startswith("."):
            keep.append(name)
            continue
        review.append(name)

    docs_root = repo_root / "docs"
    keep_docs = []
    delete_docs = []
    if docs_root.exists():
        for entry in sorted(docs_root.iterdir(), key=lambda p: p.name):
            rel = f"docs/{entry.name}"
            if entry.name in KEEP_DOCS_SUBDIRS:
                keep_docs.append(rel)
            else:
                delete_docs.append(rel)

    return {
        "keep": sorted(keep),
        "delete": sorted(delete),
        "review": sorted(review),
        "keep_docs": keep_docs,
        "delete_docs": delete_docs,
    }


def write_manifests(repo_root: Path, manifests: Dict[str, List[str]]) -> None:
    out_dir = repo_root / "data" / "cleanup_manifests"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamped = {
        "generated_at": _utc_now(),
        "mode": "harness_only",
        **manifests,
    }
    keep_payload = {
        "generated_at": stamped["generated_at"],
        "mode": stamped["mode"],
        "keep": manifests["keep"],
        "keep_docs": manifests["keep_docs"],
    }
    delete_payload = {
        "generated_at": stamped["generated_at"],
        "mode": stamped["mode"],
        "delete": manifests["delete"],
        "delete_docs": manifests["delete_docs"],
        "review": manifests["review"],
    }
    (out_dir / "keep_manifest.json").write_text(
        json.dumps(keep_payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    (out_dir / "delete_manifest.json").write_text(
        json.dumps(delete_payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    manifests = build_manifests(repo_root)
    write_manifests(repo_root, manifests)
    print("Wrote cleanup manifests to data/cleanup_manifests/")
    print(f"Keep entries: {len(manifests['keep'])}, delete entries: {len(manifests['delete'])}, review entries: {len(manifests['review'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

