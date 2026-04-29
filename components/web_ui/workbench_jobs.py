"""Async job helpers for workbench generation/validation workflows."""

from __future__ import annotations

import json
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkbenchJobStore:
    """In-memory async job store for workbench operations."""

    def __init__(self, max_workers: int = 2):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def submit(self, job_type: str, payload: Dict[str, Any], runner: Callable[[Dict[str, Any]], Dict[str, Any]]) -> str:
        job_id = uuid.uuid4().hex
        record = {
            "job_id": job_id,
            "job_type": job_type,
            "status": "queued",
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "payload": payload,
            "result": None,
            "error": None,
        }
        with self._lock:
            self._jobs[job_id] = record

        self._executor.submit(self._run_job, job_id, runner)
        return job_id

    def _run_job(self, job_id: str, runner: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        with self._lock:
            record = self._jobs[job_id]
            record["status"] = "running"
            record["updated_at"] = _utc_now()
            payload = dict(record.get("payload") or {})

        try:
            result = runner(payload)
            with self._lock:
                record = self._jobs[job_id]
                record["status"] = "completed"
                record["result"] = result
                record["updated_at"] = _utc_now()
        except Exception as exc:  # pragma: no cover
            with self._lock:
                record = self._jobs[job_id]
                record["status"] = "failed"
                record["error"] = str(exc)
                record["updated_at"] = _utc_now()

    def get(self, job_id: str) -> Dict[str, Any] | None:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None
            return {
                "job_id": record["job_id"],
                "job_type": record["job_type"],
                "status": record["status"],
                "created_at": record["created_at"],
                "updated_at": record["updated_at"],
                "result": record["result"],
                "error": record["error"],
            }


def normalize_raw_examples(raw_examples: Any) -> List[Any]:
    if isinstance(raw_examples, list):
        return raw_examples
    if isinstance(raw_examples, str):
        return [raw_examples]
    if isinstance(raw_examples, dict):
        return [raw_examples]
    return []


def normalize_text_samples(raw_samples: Any) -> List[str]:
    """Normalize user-provided pasted samples as text-only list."""
    raw_items: List[str] = []
    if isinstance(raw_samples, str):
        raw_items = [raw_samples]
    elif isinstance(raw_samples, list):
        for sample in raw_samples:
            if isinstance(sample, str):
                raw_items.append(sample)
    else:
        return []

    normalized: List[str] = []
    for item in raw_items:
        text = _strip_markdown_fences(_normalize_quotes(item))
        parts = _split_samples_text(text)
        for part in parts:
            cleaned = part.strip()
            if cleaned:
                normalized.append(cleaned)
    return normalized


def parse_sample_to_event(sample_text: str) -> Any:
    """Best-effort parse for JSON sample payloads; falls back to raw string."""
    text = (sample_text or "").strip()
    if not text:
        return ""
    if text[0] not in "{[":
        return text
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return text


def normalize_test_events(raw_examples: Any) -> List[Dict[str, Any]]:
    """Convert raw user samples into harness-compatible test events.

    Returns the shape `[{"name": "user_example_{i}", "event": {...}}]` that
    `HarnessOrchestrator.run_all_checks(custom_test_events=...)` expects.
    Both the workbench iteration loop (via parser_workbench._iter_test_events)
    and the post-generation route re-score (routes._normalize_test_events)
    flow through this helper so the two paths agree on event shape.

    Round-2 review fold-back (DA NF-1): every input dict is shallow-copied
    before being placed in the returned list. Without this, a dict that
    came from ``parser_entry["raw_examples"]`` would be reference-shared
    between ``raw_examples[i]`` and ``_iter_test_events[i]["event"]``,
    so any later mutation in one view silently corrupts the other. The
    harness's ``dual_execution_engine`` already deep-copies before
    executing, so the contained-mutation contract holds today, but
    defensive-copying here closes the latent alias risk.
    """
    normalized: List[Dict[str, Any]] = []
    for idx, item in enumerate(normalize_raw_examples(raw_examples), 1):
        if isinstance(item, dict):
            event = dict(item)  # NF-1: break the alias with the source list
            raw_blob = event.get("raw")
            if isinstance(raw_blob, str) and raw_blob and "message" not in event:
                event["message"] = raw_blob
        elif isinstance(item, str):
            parsed = parse_sample_to_event(item)
            if isinstance(parsed, dict):
                event = dict(parsed)  # NF-1: defensive copy
                raw_blob = event.get("raw")
                if isinstance(raw_blob, str) and raw_blob and "message" not in event:
                    event["message"] = raw_blob
            else:
                text = str(item)
                event = {"raw": text, "message": text}
        else:
            text = str(item)
            event = {"raw": text, "message": text}
        normalized.append({"name": f"user_example_{idx}", "event": event})
    return normalized


def _normalize_quotes(text: str) -> str:
    return (
        text.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )


def _strip_markdown_fences(text: str) -> str:
    lines = text.splitlines()
    filtered = [line for line in lines if not line.strip().startswith("```")]
    return "\n".join(filtered).strip()


def _split_samples_text(text: str) -> List[str]:
    if not text.strip():
        return []

    parts = _split_by_separator(text)
    if len(parts) > 1:
        return parts

    parts = _split_json_stream(text)
    if len(parts) > 1:
        return parts

    parts = _split_on_blank_lines_if_jsonish(text)
    if len(parts) > 1:
        return parts

    return [text]


def _split_by_separator(text: str) -> List[str]:
    lines = text.splitlines()
    chunks: List[str] = []
    current: List[str] = []
    for line in lines:
        if line.strip() == "---":
            chunk = "\n".join(current).strip()
            if chunk:
                chunks.append(chunk)
            current = []
            continue
        current.append(line)
    tail = "\n".join(current).strip()
    if tail:
        chunks.append(tail)
    return chunks


def _split_json_stream(text: str) -> List[str]:
    chunks: List[str] = []
    depth = 0
    in_string = False
    escape = False
    start = -1
    for idx, ch in enumerate(text):
        if start == -1 and ch in "{[":
            start = idx
        if start == -1:
            continue
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                chunk = text[start:idx + 1].strip()
                if chunk:
                    chunks.append(chunk)
                start = -1
    return chunks


def _split_on_blank_lines_if_jsonish(text: str) -> List[str]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n+", text) if b.strip()]
    if len(blocks) <= 1:
        return blocks
    json_like_count = sum(1 for b in blocks if b[:1] in "{[")
    if json_like_count == len(blocks):
        return blocks
    return [text]
