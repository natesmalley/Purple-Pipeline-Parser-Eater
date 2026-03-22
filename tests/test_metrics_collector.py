"""Tests for metrics collector."""

from __future__ import annotations

import pytest

from components.metrics_collector import MetricsCollector, get_metrics_collector


class TestMetricsCollector:
    """Test metrics collector."""

    def test_initialization(self) -> None:
        """Test collector initialization."""
        collector = MetricsCollector()
        assert collector.conversions_total == 0
        assert collector.api_calls_total == 0
        assert collector.errors_total == 0

    def test_increment_conversions(self) -> None:
        """Test incrementing conversions."""
        collector = MetricsCollector()
        collector.increment_conversions(success=True)
        assert collector.conversions_total == 1
        assert collector.conversions_success == 1
        
        collector.increment_conversions(success=False)
        assert collector.conversions_total == 2
        assert collector.conversions_failed == 1

    def test_increment_api_calls(self) -> None:
        """Test incrementing API calls."""
        collector = MetricsCollector()
        collector.increment_api_calls(success=True)
        assert collector.api_calls_total == 1
        assert collector.api_calls_success == 1
        
        collector.increment_api_calls(success=False)
        assert collector.api_calls_total == 2
        assert collector.api_calls_failed == 1

    def test_increment_rag_queries(self) -> None:
        """Test incrementing RAG queries."""
        collector = MetricsCollector()
        collector.increment_rag_queries(success=True)
        assert collector.rag_queries_total == 1
        assert collector.rag_queries_success == 1

    def test_increment_web_ui_requests(self) -> None:
        """Test incrementing web UI requests."""
        collector = MetricsCollector()
        collector.increment_web_ui_requests()
        assert collector.web_ui_requests_total == 1

    def test_increment_errors(self) -> None:
        """Test incrementing errors."""
        collector = MetricsCollector()
        collector.increment_errors(error_type="validation")
        assert collector.errors_total == 1
        assert collector.operation_counts["validation"] == 1

    def test_record_durations(self) -> None:
        """Test recording durations."""
        collector = MetricsCollector()
        collector.record_conversion_duration(1.5)
        collector.record_api_call_duration(0.8)
        collector.record_rag_query_duration(2.3)
        
        assert len(collector.conversion_durations) == 1
        assert len(collector.api_call_durations) == 1
        assert len(collector.rag_query_durations) == 1

    def test_set_gauge_metrics(self) -> None:
        """Test setting gauge metrics."""
        collector = MetricsCollector()
        collector.set_pending_conversions(10)
        collector.set_active_conversions(5)
        
        assert collector.pending_conversions == 10
        assert collector.active_conversions == 5

    def test_get_summary(self) -> None:
        """Test getting metrics summary."""
        collector = MetricsCollector()
        collector.increment_conversions(success=True)
        collector.increment_conversions(success=False)
        
        summary = collector.get_summary()
        assert summary["conversions"]["total"] == 2
        assert summary["conversions"]["success"] == 1
        assert summary["conversions"]["failed"] == 1

    def test_prometheus_metrics(self) -> None:
        """Test Prometheus metrics output."""
        collector = MetricsCollector()
        collector.increment_conversions(success=True)
        collector.set_pending_conversions(5)
        
        metrics = collector.get_prometheus_metrics()
        assert "purple_pipeline_conversions_total 1" in metrics
        assert "purple_pipeline_pending_conversions 5" in metrics
        assert "# TYPE purple_pipeline_conversions_total counter" in metrics

    def test_reset(self) -> None:
        """Test resetting metrics."""
        collector = MetricsCollector()
        collector.increment_conversions()
        collector.increment_api_calls()
        collector.increment_errors()
        
        collector.reset()
        assert collector.conversions_total == 0
        assert collector.api_calls_total == 0
        assert collector.errors_total == 0

    def test_global_instance(self) -> None:
        """Test global metrics instance."""
        m1 = get_metrics_collector()
        m2 = get_metrics_collector()
        assert m1 is m2

    def test_multiple_errors(self) -> None:
        """Test tracking multiple error types."""
        collector = MetricsCollector()
        collector.increment_errors("validation")
        collector.increment_errors("timeout")
        collector.increment_errors("validation")
        
        assert collector.operation_counts["validation"] == 2
        assert collector.operation_counts["timeout"] == 1
        assert collector.errors_total == 3
