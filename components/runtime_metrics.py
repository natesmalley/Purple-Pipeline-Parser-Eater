"""Runtime metrics tracking for transform worker and canary routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ParserRuntimeMetrics:
    total_events: int = 0
    successes: int = 0
    failures: int = 0
    canary_events: int = 0
    stable_events: int = 0
    last_error: Optional[str] = None

    def record(self, success: bool, canary: bool, error: Optional[str] = None) -> None:
        self.total_events += 1
        if success:
            self.successes += 1
        else:
            self.failures += 1
            self.last_error = error

        if canary:
            self.canary_events += 1
        else:
            self.stable_events += 1

    def error_rate(self) -> float:
        return self.failures / self.total_events if self.total_events else 0.0

    def to_dict(self) -> Dict[str, int | str | None]:
        return {
            "total_events": self.total_events,
            "successes": self.successes,
            "failures": self.failures,
            "canary_events": self.canary_events,
            "stable_events": self.stable_events,
            "last_error": self.last_error,
            "error_rate": self.error_rate(),
        }


class RuntimeMetricsStore:
    def __init__(self) -> None:
        self.metrics: Dict[str, ParserRuntimeMetrics] = {}

    def for_parser(self, parser_id: str) -> ParserRuntimeMetrics:
        if parser_id not in self.metrics:
            self.metrics[parser_id] = ParserRuntimeMetrics()
        return self.metrics[parser_id]

    def to_dict(self) -> Dict[str, Dict[str, int | str | None]]:
        return {
            parser_id: m.to_dict()
            for parser_id, m in self.metrics.items()
        }

