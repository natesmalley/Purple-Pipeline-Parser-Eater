"""Integration tests for metrics."""

from __future__ import annotations

from components.metrics_collector import get_metrics_collector


class TestMetricsIntegration:
    """Test metrics integration."""

    def test_metrics_workflow(self) -> None:
        """Test complete metrics workflow."""
        collector = get_metrics_collector()
        
        collector.increment_conversions(success=True)
        collector.increment_api_calls(success=True)
        collector.record_conversion_duration(1.5)
        
        summary = collector.get_summary()
        assert summary["conversions"]["total"] >= 1
        assert summary["api_calls"]["total"] >= 1

    def test_prometheus_output_format(self) -> None:
        """Test Prometheus output format."""
        collector = get_metrics_collector()
        metrics = collector.get_prometheus_metrics()
        
        assert "# TYPE" in metrics
        assert "# HELP" in metrics
        assert "purple_pipeline" in metrics
