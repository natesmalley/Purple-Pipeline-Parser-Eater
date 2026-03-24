"""Helpers for runtime metrics and reload request persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class RuntimeIO:
    def __init__(self, runtime_config: Dict[str, Any]) -> None:
        self.metrics_path = Path(runtime_config.get("metrics_path", "data/runtime_metrics.json"))
        self.reload_path = Path(runtime_config.get("reload_path", "data/runtime_reload_requests.json"))
        self.metrics_path.parent.mkdir(parents=True, exist_ok=True)
        self.reload_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_json(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as handle:
            try:
                return json.load(handle)
            except json.JSONDecodeError:
                return {}

    def _write_json(self, path: Path, data: Dict[str, Any]) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)

    def load_metrics(self) -> Dict[str, Any]:
        return self._load_json(self.metrics_path)

    def update_metrics(self, update: Dict[str, Any]) -> None:
        metrics = self.load_metrics()
        metrics.update(update)
        self._write_json(self.metrics_path, metrics)

    def load_reload_requests(self) -> Dict[str, Any]:
        return self._load_json(self.reload_path)

    def add_reload_request(self, parser_id: str, status: str = "pending") -> None:
        requests = self.load_reload_requests()
        requests[parser_id] = status
        self._write_json(self.reload_path, requests)

    def consume_reload_requests(self) -> Dict[str, Any]:
        requests = self.load_reload_requests()
        if requests:
            self._write_json(self.reload_path, {})
        return requests

