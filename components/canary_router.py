"""Canary routing helper for transform worker."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from components.manifest_schema import ParserManifest
from components.runtime_metrics import RuntimeMetricsStore


@dataclass
class VersionMetrics:
    success: int = 0
    error: int = 0

    def record(self, success: bool) -> None:
        if success:
            self.success += 1
        else:
            self.error += 1

    def total(self) -> int:
        return self.success + self.error

    def error_rate(self) -> float:
        total = self.total()
        return self.error / total if total else 0.0


class CanaryRouter:
    """Routes events between stable and canary transforms."""

    def __init__(self, promotion_threshold: int = 1000, error_tolerance: float = 0.01) -> None:
        self.versions: Dict[str, Dict[str, ParserManifest]] = {}
        self.metrics: Dict[Tuple[str, str], VersionMetrics] = {}
        self.runtime_metrics = RuntimeMetricsStore()
        self.promotion_threshold = promotion_threshold
        self.error_tolerance = error_tolerance

    def register(self, parser_id: str, manifest: Optional[ParserManifest], mode: str) -> None:
        if manifest is None:
            return
        self.versions.setdefault(parser_id, {})[mode] = manifest
        key = (parser_id, manifest.version.semantic)
        self.metrics.setdefault(key, VersionMetrics())

    def select(self, parser_id: str, event_hash: int) -> Tuple[str, ParserManifest]:
        versions = self.versions.get(parser_id)
        if not versions:
            raise KeyError(f"No versions registered for {parser_id}")

        stable_manifest = versions.get("stable")
        if stable_manifest is None:
            raise ValueError(f"Stable manifest missing for {parser_id}")

        canary_manifest = versions.get("canary")
        if not canary_manifest:
            return "stable", stable_manifest

        canary_pct = canary_manifest.deployment.canary_percentage if canary_manifest.deployment else 0
        if event_hash % 100 < canary_pct:
            return "canary", canary_manifest
        return "stable", stable_manifest

    def record(
        self,
        parser_id: str,
        semantic_version: str,
        success: bool,
        canary: bool,
        error: Optional[str] = None,
    ) -> None:
        key = (parser_id, semantic_version)
        metrics = self.metrics.setdefault(key, VersionMetrics())
        metrics.record(success)
        self.runtime_metrics.for_parser(parser_id).record(success, canary, error)

    def should_promote_canary(self, parser_id: str) -> bool:
        versions = self.versions.get(parser_id)
        if not versions:
            return False

        stable_manifest = versions.get("stable")
        canary_manifest = versions.get("canary")
        if not stable_manifest or not canary_manifest:
            return False

        stable_key = (parser_id, stable_manifest.version.semantic)
        canary_key = (parser_id, canary_manifest.version.semantic)

        stable_metrics = self.metrics.get(stable_key)
        canary_metrics = self.metrics.get(canary_key)
        if not canary_metrics or canary_metrics.total() < self.promotion_threshold:
            return False

        stable_error_rate = stable_metrics.error_rate() if stable_metrics else 0.0
        canary_error_rate = canary_metrics.error_rate()

        return canary_error_rate <= stable_error_rate + self.error_tolerance

    def runtime_status(self) -> Dict[str, Dict[str, int | str | None]]:
        return self.runtime_metrics.to_dict()

