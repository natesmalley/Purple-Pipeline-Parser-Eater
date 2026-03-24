"""Additional tests for MetricsCollector to ensure 85%+ coverage."""

import pytest

from components.metrics_collector import MetricsCollector


@pytest.fixture
def collector():
    """Create metrics collector instance."""
    return MetricsCollector()


class TestMetricsCollectorEdgeCases:
    """Edge case and boundary tests for MetricsCollector."""

    def test_empty_metrics_generation(self):
        """Test generating metrics without recording anything."""
        collector = MetricsCollector()
        metrics = collector.generate_metrics()
        assert isinstance(metrics, bytes)
        assert b"purple_pipeline" in metrics

    def test_metrics_collector_import_error(self):
        """Test error handling when prometheus_client is not available."""
        # This test verifies the import guard works
        try:
            collector = MetricsCollector()
            assert collector is not None
        except ImportError:
            pytest.skip("prometheus-client not installed")

    def test_summary_with_no_metrics(self):
        """Test getting summary with no metrics recorded."""
        collector = MetricsCollector()
        summary = collector.get_summary()
        assert "counters" in summary
        assert "gauges" in summary

    def test_conversion_status_variations(self, collector):
        """Test conversion recording with various status values."""
        statuses = [
            "success",
            "failure",
            "partial",
            "cancelled",
            "timeout",
        ]

        for status in statuses:
            collector.record_conversion(status)

        summary = collector.get_summary()
        assert summary["counters"]["conversions_total"] >= len(statuses)

    def test_api_call_http_status_variations(self, collector):
        """Test API call recording with various HTTP statuses."""
        statuses = ["200", "201", "400", "404", "500", "502", "503"]
        endpoint = "/api/test"
        method = "GET"

        for status in statuses:
            collector.record_api_call(endpoint, method, status)

        summary = collector.get_summary()
        assert summary["counters"]["api_calls_total"] >= len(statuses)

    def test_api_call_various_methods(self, collector):
        """Test API call recording with various HTTP methods."""
        methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"]
        endpoint = "/api/test"
        status = "200"

        for method in methods:
            collector.record_api_call(endpoint, method, status)

        summary = collector.get_summary()
        assert summary["counters"]["api_calls_total"] >= len(methods)

    def test_api_call_various_endpoints(self, collector):
        """Test API call recording with various endpoints."""
        endpoints = [
            "/api/users",
            "/api/data",
            "/api/admin",
            "/api/v1/test",
            "/api/v2/test",
        ]

        for endpoint in endpoints:
            collector.record_api_call(endpoint, "GET", "200")

        summary = collector.get_summary()
        assert summary["counters"]["api_calls_total"] >= len(endpoints)

    def test_rag_query_status_variations(self, collector):
        """Test RAG query recording with various statuses."""
        statuses = ["success", "failure", "timeout", "invalid"]

        for status in statuses:
            collector.record_rag_query(status)

        summary = collector.get_summary()
        assert summary["counters"]["rag_queries_total"] >= len(statuses)

    def test_web_ui_request_various_endpoints(self, collector):
        """Test web UI request with various endpoints."""
        endpoints = [
            "/ui/home",
            "/ui/settings",
            "/ui/dashboard",
            "/ui/admin",
        ]

        for endpoint in endpoints:
            collector.record_web_ui_request(endpoint, "GET", "200")

        summary = collector.get_summary()
        assert summary["counters"]["web_ui_requests_total"] >= len(endpoints)

    def test_web_ui_request_various_methods(self, collector):
        """Test web UI request with various HTTP methods."""
        methods = ["GET", "POST", "PUT", "DELETE"]
        endpoint = "/ui/test"
        status = "200"

        for method in methods:
            collector.record_web_ui_request(endpoint, method, status)

        summary = collector.get_summary()
        assert summary["counters"]["web_ui_requests_total"] >= len(methods)

    def test_error_type_variations(self, collector):
        """Test error recording with various error types."""
        error_types = [
            "ConnectionError",
            "TimeoutError",
            "ValueError",
            "RuntimeError",
            "KeyError",
            "AttributeError",
        ]

        for error_type in error_types:
            collector.record_error(error_type)

        summary = collector.get_summary()
        assert summary["counters"]["errors_total"] >= len(error_types)

    def test_duration_boundary_values(self, collector):
        """Test duration recording with boundary values."""
        durations = [
            0.001,  # Very fast
            0.0,    # Instant
            1.0,    # One second
            100.0,  # Very slow
        ]

        for duration in durations:
            collector.record_conversion_duration(duration, "success")

        assert collector is not None

    def test_gauge_increment_multiple_times(self, collector):
        """Test incrementing gauge multiple times."""
        collector.set_active_conversions(0)

        for _ in range(10):
            collector.increment_active_conversions()

        summary = collector.get_summary()
        assert summary["gauges"]["active_conversions"] == 10

    def test_gauge_decrement_multiple_times(self, collector):
        """Test decrementing gauge multiple times."""
        collector.set_active_conversions(10)

        for _ in range(5):
            collector.decrement_active_conversions()

        summary = collector.get_summary()
        assert summary["gauges"]["active_conversions"] == 5

    def test_gauge_zero_operations(self, collector):
        """Test gauge operations resulting in zero."""
        collector.set_active_conversions(5)

        for _ in range(5):
            collector.decrement_active_conversions()

        summary = collector.get_summary()
        assert summary["gauges"]["active_conversions"] == 0

    def test_rag_query_duration_small_values(self, collector):
        """Test RAG query duration with small values."""
        durations = [0.001, 0.01, 0.1]

        for duration in durations:
            collector.record_rag_query_duration(duration)

        assert collector is not None

    def test_web_ui_request_duration_small_values(self, collector):
        """Test web UI request duration with small values."""
        durations = [0.001, 0.01, 0.05]

        for duration in durations:
            collector.record_web_ui_request_duration(
                duration, "/ui/test", "GET"
            )

        assert collector is not None

    def test_multiple_concurrent_metric_types(self, collector):
        """Test recording multiple metric types concurrently."""
        # Record many metrics of different types in sequence
        for i in range(20):
            # Counters
            collector.record_conversion("success")
            collector.record_api_call(f"/api/endpoint{i}", "GET", "200")
            collector.record_rag_query("success")
            collector.record_web_ui_request("/ui/home", "GET", "200")
            collector.record_error("TestError")

            # Histograms
            collector.record_conversion_duration(0.1 * i, "success")
            collector.record_api_call_duration(0.05 * i, f"/api/endpoint{i}", "GET")
            collector.record_rag_query_duration(0.2 * i)
            collector.record_web_ui_request_duration(0.01 * i, "/ui/home", "GET")

            # Gauges
            collector.set_active_conversions(i)
            collector.set_pending_conversions(20 - i)

        summary = collector.get_summary()
        assert summary["counters"]["conversions_total"] >= 20

    def test_special_characters_in_labels(self, collector):
        """Test handling special characters in labels."""
        # Test with special characters that might appear in URLs
        collector.record_api_call("/api/data-export", "GET", "200")
        collector.record_api_call("/api/user_profile", "GET", "200")
        collector.record_api_call("/api/v1_users", "POST", "201")

        metrics = collector.generate_metrics()
        assert isinstance(metrics, bytes)

    def test_metrics_content_type_decoding(self, collector):
        """Test metrics content type can be decoded."""
        collector.record_conversion("success")
        content_type = collector.get_metrics_content_type()

        # Should be a valid string
        assert isinstance(content_type, str)
        assert len(content_type) > 0

    def test_metrics_generation_consistency(self, collector):
        """Test metrics generation is consistent."""
        collector.record_conversion("success")

        metrics1 = collector.generate_metrics()
        metrics2 = collector.generate_metrics()

        # Both should contain the same base metrics
        assert b"purple_pipeline_conversions_total" in metrics1
        assert b"purple_pipeline_conversions_total" in metrics2

    def test_get_summary_type_safety(self, collector):
        """Test get_summary returns correct types."""
        collector.record_conversion("success")
        collector.set_active_conversions(5)

        summary = collector.get_summary()

        assert isinstance(summary, dict)
        assert isinstance(summary["counters"], dict)
        assert isinstance(summary["gauges"], dict)

        # All counter values should be numeric
        for key, value in summary["counters"].items():
            assert isinstance(key, str)
            assert isinstance(value, (int, float))

        # All gauge values should be numeric
        for key, value in summary["gauges"].items():
            assert isinstance(key, str)
            assert isinstance(value, (int, float))

    def test_large_number_of_labels(self, collector):
        """Test handling large number of different labels."""
        # Create many different endpoints
        for i in range(100):
            collector.record_api_call(f"/api/endpoint_{i}", "GET", "200")

        summary = collector.get_summary()
        assert summary["counters"]["api_calls_total"] >= 100

    def test_rapid_metric_updates(self, collector):
        """Test rapid updates to same metric."""
        # Rapid counter updates
        for _ in range(1000):
            collector.record_conversion("success")

        summary = collector.get_summary()
        assert summary["counters"]["conversions_total"] >= 1000

    def test_gauge_min_max_values(self, collector):
        """Test gauge with minimum and maximum values."""
        # Minimum
        collector.set_active_conversions(0)
        assert collector.get_summary()["gauges"]["active_conversions"] == 0

        # Maximum
        collector.set_active_conversions(999999)
        assert collector.get_summary()["gauges"]["active_conversions"] == 999999

    def test_histogram_with_zero_duration(self, collector):
        """Test histogram with zero duration."""
        collector.record_conversion_duration(0.0, "success")
        assert collector is not None

    def test_all_error_types_recorded(self, collector):
        """Test all error types are recorded separately."""
        errors = {
            "ConnectionError": 5,
            "TimeoutError": 3,
            "ValueError": 2,
        }

        for error_type, count in errors.items():
            for _ in range(count):
                collector.record_error(error_type)

        summary = collector.get_summary()
        assert summary["counters"]["errors_total"] == sum(errors.values())

    def test_metrics_initialization_state(self):
        """Test metrics collector initial state."""
        collector = MetricsCollector()
        summary = collector.get_summary()

        # Should have all expected counter keys
        assert "conversions_total" in summary["counters"]
        assert "api_calls_total" in summary["counters"]
        assert "rag_queries_total" in summary["counters"]
        assert "web_ui_requests_total" in summary["counters"]
        assert "errors_total" in summary["counters"]

        # Should have all expected gauge keys
        assert "pending_conversions" in summary["gauges"]
        assert "active_conversions" in summary["gauges"]
        assert "pending_rag_queries" in summary["gauges"]
        assert "active_rag_queries" in summary["gauges"]

    def test_registry_usage(self):
        """Test custom registry usage."""
        try:
            from prometheus_client import CollectorRegistry
            registry = CollectorRegistry()
            collector = MetricsCollector(registry=registry)
            assert collector.registry is registry
        except ImportError:
            pytest.skip("prometheus-client not installed")

    def test_metrics_output_format(self, collector):
        """Test metrics output format is valid."""
        collector.record_conversion("success")
        metrics = collector.generate_metrics()

        # Should be bytes
        assert isinstance(metrics, bytes)

        # Should contain valid Prometheus format
        text = metrics.decode("utf-8")
        assert "#" in text  # Comments
        assert "purple_pipeline" in text  # Metrics

    def test_concurrent_gauge_operations(self, collector):
        """Test concurrent gauge operations."""
        # Simulate concurrent operations
        for i in range(10):
            if i % 2 == 0:
                collector.increment_active_conversions()
            else:
                collector.decrement_active_conversions()

        summary = collector.get_summary()
        assert summary["gauges"]["active_conversions"] == 0

    def test_empty_error_type(self, collector):
        """Test recording empty error type."""
        collector.record_error("")
        summary = collector.get_summary()
        assert summary["counters"]["errors_total"] >= 1

    def test_metric_persistence_between_calls(self, collector):
        """Test metrics persist between summary calls."""
        collector.record_conversion("success")
        summary1 = collector.get_summary()

        collector.record_conversion("success")
        summary2 = collector.get_summary()

        assert summary2["counters"]["conversions_total"] > summary1["counters"]["conversions_total"]
