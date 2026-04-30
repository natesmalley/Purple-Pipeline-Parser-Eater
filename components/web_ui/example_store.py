"""Persistence helpers for harness examples and run records."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from components.web_ui.lua_acceptance import is_acceptable_lua


logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _slug(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", name.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "unknown_parser"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass
class HarnessExampleStore:
    """Stores versioned examples and run outputs for the harness."""

    repo_root: Path

    def __post_init__(self) -> None:
        self.examples_root = self.repo_root / "data" / "harness_examples"
        self.examples_parsers_dir = self.examples_root / "parsers"
        self.examples_history_dir = self.examples_root / "history"
        self.index_path = self.examples_root / "index.json"
        self.generated_lua_root = self.repo_root / "output" / "generated_lua"
        self.harness_reports_root = self.repo_root / "output" / "harness_reports"
        self.examples_parsers_dir.mkdir(parents=True, exist_ok=True)
        self.examples_history_dir.mkdir(parents=True, exist_ok=True)
        self.generated_lua_root.mkdir(parents=True, exist_ok=True)
        self.harness_reports_root.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> Dict[str, Any]:
        if not self.index_path.exists():
            return {"version": 1, "parsers": {}, "updated_at": None}
        try:
            parsed = json.loads(self.index_path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        return {"version": 1, "parsers": {}, "updated_at": None}

    def _save_index(self, index: Dict[str, Any]) -> None:
        index["updated_at"] = _utc_now().isoformat()
        parsers = index.get("parsers", {})
        if isinstance(parsers, dict):
            index["parsers"] = dict(sorted(parsers.items(), key=lambda item: item[0]))
        self.index_path.write_text(
            json.dumps(index, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def get_parser_samples(self, parser_name: str, limit: int = 5) -> List[str]:
        """Return recent stored samples for a parser (deterministic order)."""
        parser_slug = _slug(parser_name)
        parser_path = self.examples_parsers_dir / f"{parser_slug}.jsonl"
        if not parser_path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        for line in parser_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                rows.append(item)
        rows.sort(key=lambda row: (str(row.get("created_at", "")), str(row.get("sample_id", ""))))
        samples = [str(row.get("sample_text", "")) for row in rows if row.get("sample_text")]
        if limit <= 0:
            return samples
        return samples[-limit:]

    def record_samples(
        self,
        parser_name: str,
        sample_texts: List[str],
        sample_provenance: Optional[Dict[str, Any]] = None,
        source_parser_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Append unique sample records and update parser index metadata."""
        parser_slug = _slug(parser_name)
        parser_path = self.examples_parsers_dir / f"{parser_slug}.jsonl"
        existing_hashes = set()
        if parser_path.exists():
            for line in parser_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                if isinstance(item, dict) and item.get("sample_hash"):
                    existing_hashes.add(str(item["sample_hash"]))

        created = _utc_now().isoformat()
        added_ids: List[str] = []
        rows_to_append: List[str] = []
        for sample_text in sample_texts:
            sample_hash = _sha256_text(sample_text.strip())
            if sample_hash in existing_hashes:
                continue
            sample_id = f"{created.replace(':', '').replace('-', '')[:15]}_{sample_hash[:12]}"
            payload = {
                "sample_id": sample_id,
                "sample_hash": sample_hash,
                "parser_name": parser_name,
                "source_parser_name": source_parser_name or parser_name,
                "sample_text": sample_text,
                "created_at": created,
                "sample_provenance": sample_provenance or {},
            }
            rows_to_append.append(json.dumps(payload, sort_keys=True))
            added_ids.append(sample_id)
            existing_hashes.add(sample_hash)

            history_file = self.examples_history_dir / f"{sample_id}.json"
            history_file.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

        if rows_to_append:
            with parser_path.open("a", encoding="utf-8") as handle:
                for row in rows_to_append:
                    handle.write(row + "\n")

        index = self._load_index()
        parsers = index.setdefault("parsers", {})
        parser_entry = parsers.get(parser_name, {})
        parser_entry.update(
            {
                "parser_name": parser_name,
                "source_parser_name": source_parser_name or parser_name,
                "slug": parser_slug,
                "samples_file": str(parser_path.relative_to(self.repo_root)),
                "sample_count": len(self.get_parser_samples(parser_name, limit=0)),
                "last_sample_at": created if added_ids else parser_entry.get("last_sample_at"),
                "sample_provenance": sample_provenance or parser_entry.get("sample_provenance", {}),
            }
        )
        parsers[parser_name] = parser_entry
        self._save_index(index)
        return {"sample_ids": added_ids, "sample_count": parser_entry["sample_count"]}

    def record_run(
        self,
        parser_name: str,
        lua_code: str,
        harness_report: Dict[str, Any],
        sample_provenance: Optional[Dict[str, Any]] = None,
        source_parser_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Persist generated Lua and harness report for traceability.

        Returns ``{run_id, lua_path, report_path, accepted, rejection_reason}``.
        On rejection (W2 acceptance gate), ``run_id`` / ``lua_path`` /
        ``report_path`` are ``None`` and ``rejection_reason`` carries the
        reason from :func:`is_acceptable_lua`. No file is written when
        rejected. Existing callers must read ``accepted`` first.
        """
        accepted, rejection_reason = is_acceptable_lua(lua_code, harness_report)
        if not accepted:
            try:
                score = int((harness_report or {}).get("confidence_score", 0) or 0)
            except (TypeError, ValueError):
                score = 0
            logger.warning(
                "lua_persist_rejected parser=%s reason=%s score=%s len=%d",
                parser_name,
                rejection_reason,
                score,
                len(lua_code or ""),
            )
            return {
                "run_id": None,
                "lua_path": None,
                "report_path": None,
                "accepted": False,
                "rejection_reason": rejection_reason,
            }

        parser_slug = _slug(parser_name)
        now = _utc_now()
        lua_hash = _sha256_text(lua_code)[:12]
        run_id = f"{now.strftime('%Y%m%dT%H%M%SZ')}_{lua_hash}"

        lua_dir = self.generated_lua_root / parser_slug
        report_dir = self.harness_reports_root / parser_slug
        lua_dir.mkdir(parents=True, exist_ok=True)
        report_dir.mkdir(parents=True, exist_ok=True)

        lua_path = lua_dir / f"{run_id}.lua"
        report_path = report_dir / f"{run_id}.json"
        lua_path.write_text(lua_code, encoding="utf-8")
        report_payload = {
            "run_id": run_id,
            "parser_name": parser_name,
            "source_parser_name": source_parser_name or parser_name,
            "created_at": now.isoformat(),
            "sample_provenance": sample_provenance or {},
            "harness_report": harness_report,
        }
        report_path.write_text(json.dumps(report_payload, indent=2, sort_keys=True), encoding="utf-8")
        return {
            "run_id": run_id,
            "lua_path": str(lua_path),
            "report_path": str(report_path),
            "accepted": True,
            "rejection_reason": None,
        }

