from __future__ import annotations
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class MetricsCollector:
    """Prometheus metrics collector."""
    def __init__(self) -> None:
        self.conversions_total = 0
        self.conversions_success = 0
        self.conversions_failed = 0
        self.api_calls_total = 0
        self.api_calls_success = 0
        self.api_calls_failed = 0
        self.rag_queries_total = 0
        self.rag_queries_success = 0
        self.rag_queries_failed = 0
        self.web_ui_requests_total = 0
        self.errors_total = 0
        self.pending_conversions = 0
        self.active_conversions = 0
        self.conversion_durations = []
        self.api_call_durations = []
        self.rag_query_durations = []
        self.operation_counts = {}

    def increment_conversions(self, success=True) -> None:
        self.conversions_total += 1
        if success:
            self.conversions_success += 1
        else:
            self.conversions_failed += 1

    def increment_api_calls(self, success=True) -> None:
        self.api_calls_total += 1
        if success:
            self.api_calls_success += 1
        else:
            self.api_calls_failed += 1

    def increment_rag_queries(self, success=True) -> None:
        self.rag_queries_total += 1
        if success:
            self.rag_queries_success += 1
        else:
            self.rag_queries_failed += 1

    def increment_web_ui_requests(self) -> None:
        self.web_ui_requests_total += 1

    def increment_errors(self, error_type='general') -> None:
        self.errors_total += 1
        if error_type not in self.operation_counts:
            self.operation_counts[error_type] = 0
        self.operation_counts[error_type] += 1

    def record_conversion_duration(self, duration_seconds: float) -> None:
        if duration_seconds >= 0:
            self.conversion_durations.append(duration_seconds)

    def record_api_call_duration(self, duration_seconds: float) -> None:
        if duration_seconds >= 0:
            self.api_call_durations.append(duration_seconds)

    def record_rag_query_duration(self, duration_seconds: float) -> None:
        if duration_seconds >= 0:
            self.rag_query_durations.append(duration_seconds)

    def set_pending_conversions(self, count: int) -> None:
        if count >= 0:
            self.pending_conversions = count

    def set_active_conversions(self, count: int) -> None:
        if count >= 0:
            self.active_conversions = count

    def get_prometheus_metrics(self) -> str:
        lines = []
        lines.append('# HELP purple_pipeline_conversions_total Total conversions')
        lines.append('# TYPE purple_pipeline_conversions_total counter')
        lines.append(f'purple_pipeline_conversions_total {self.conversions_total}')
        lines.append('')
        lines.append('# HELP purple_pipeline_api_calls_total Total API calls')
        lines.append('# TYPE purple_pipeline_api_calls_total counter')
        lines.append(f'purple_pipeline_api_calls_total {self.api_calls_total}')
        lines.append('')
        lines.append('# HELP purple_pipeline_errors_total Total errors')
        lines.append('# TYPE purple_pipeline_errors_total counter')
        lines.append(f'purple_pipeline_errors_total {self.errors_total}')
        lines.append('')
        lines.append('# HELP purple_pipeline_pending_conversions Pending conversions')
        lines.append('# TYPE purple_pipeline_pending_conversions gauge')
        lines.append(f'purple_pipeline_pending_conversions {self.pending_conversions}')
        lines.append('')
        lines.append('# HELP purple_pipeline_active_conversions Active conversions')
        lines.append('# TYPE purple_pipeline_active_conversions gauge')
        lines.append(f'purple_pipeline_active_conversions {self.active_conversions}')
        return '\n'.join(lines) + '\n'

    def get_summary(self) -> Dict[str, Any]:
        return {
            'conversions': {'total': self.conversions_total, 'success': self.conversions_success},
            'api_calls': {'total': self.api_calls_total, 'success': self.api_calls_success},
            'errors': {'total': self.errors_total},
            'pending': self.pending_conversions,
            'active': self.active_conversions,
        }

    def reset(self) -> None:
        self.conversions_total = 0
        self.conversions_success = 0
        self.conversions_failed = 0
        self.api_calls_total = 0
        self.api_calls_success = 0
        self.api_calls_failed = 0
        self.rag_queries_total = 0
        self.errors_total = 0
        self.pending_conversions = 0
        self.active_conversions = 0

_global_metrics = MetricsCollector()

def get_metrics_collector() -> MetricsCollector:
    return _global_metrics
