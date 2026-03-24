"""Integration tests for system components."""

from __future__ import annotations

import pytest

from components.health_check import HealthChecker, SystemMetrics
from components.http_rate_limiter import get_rate_limiter
from components.request_logger import get_request_logger
from components.security_middleware import SecurityValidator, ErrorSanitizer, SecurityHeaders
from components.metrics_collector import get_metrics_collector
from utils.config_validator import ConfigValidator


class TestHealthCheckIntegration:
    """Test health check system."""

    @pytest.mark.asyncio
    async def test_health_checker_initialization(self) -> None:
        """Test health checker initialization."""
        checker = HealthChecker()
        assert checker is not None
        assert len(checker.services) == 0

    @pytest.mark.asyncio
    async def test_register_and_check_service(self) -> None:
        """Test registering and checking a service."""
        async def mock_check():
            return True, "Service OK"

        checker = HealthChecker()
        checker.register_service("test_service", mock_check)
        status = await checker.check_all_services()
        
        assert "test_service" in status
        assert status["test_service"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_system_metrics(self) -> None:
        """Test system metrics collection."""
        metrics = {
            "cpu": SystemMetrics.get_cpu_percent(),
            "memory": SystemMetrics.get_memory_info(),
            "process_count": SystemMetrics.get_process_count(),
            "uptime": SystemMetrics.get_uptime(),
        }
        
        assert metrics["cpu"] >= 0
        assert "percent" in metrics["memory"]
        assert metrics["process_count"] > 0
        assert metrics["uptime"] >= 0


class TestRateLimitingIntegration:
    """Test rate limiting functionality."""

    def test_rate_limiter_initialization(self) -> None:
        """Test rate limiter initialization."""
        limiter = get_rate_limiter()
        assert limiter is not None

    def test_rate_limit_check(self) -> None:
        """Test rate limit checking."""
        limiter = get_rate_limiter()
        allowed, remaining, retry = limiter.check_rate_limit("test_endpoint", 5, 60)
        assert allowed is True
        assert remaining >= 0


class TestSecurityValidation:
    """Test security validation."""

    def test_sql_injection_detection(self) -> None:
        """Test SQL injection detection."""
        validator = SecurityValidator()
        safe, pattern = validator.check_sql_injection("admin' OR 1=1--")
        assert safe is False

    def test_xss_detection(self) -> None:
        """Test XSS detection."""
        validator = SecurityValidator()
        safe, pattern = validator.check_xss("<script>alert('xss')</script>")
        assert safe is False

    def test_safe_input(self) -> None:
        """Test safe input passes validation."""
        validator = SecurityValidator()
        safe, pattern = validator.check_sql_injection("normal_input")
        assert safe is True

    def test_error_sanitization(self) -> None:
        """Test error message sanitization."""
        error_msg = "Error at /home/user/app.py line 42"
        sanitized = ErrorSanitizer.sanitize_error_message(error_msg, is_production=True)
        assert "REDACTED" in sanitized or "app.py" not in sanitized

    def test_security_headers(self) -> None:
        """Test security headers."""
        headers = SecurityHeaders.get_headers()
        assert "X-Content-Type-Options" in headers
        assert "Content-Security-Policy" in headers


class TestMetricsCollection:
    """Test metrics collection."""

    def test_metrics_initialization(self) -> None:
        """Test metrics collector initialization."""
        collector = get_metrics_collector()
        assert collector is not None

    def test_metrics_tracking(self) -> None:
        """Test metrics tracking."""
        collector = get_metrics_collector()
        initial_count = collector.conversions_total
        
        collector.increment_conversions(success=True)
        assert collector.conversions_total == initial_count + 1

    def test_prometheus_format(self) -> None:
        """Test Prometheus format output."""
        collector = get_metrics_collector()
        metrics = collector.get_prometheus_metrics()
        
        assert isinstance(metrics, str)
        assert "purple_pipeline" in metrics


class TestConfigValidation:
    """Test configuration validation."""

    def test_config_validator_initialization(self) -> None:
        """Test config validator initialization."""
        validator = ConfigValidator()
        assert validator is not None

    def test_required_variables_check(self) -> None:
        """Test required variables validation."""
        validator = ConfigValidator()
        result = validator.validate_required_vars(["NONEXISTENT_VAR_XYZ"])
        assert result is False

    def test_token_strength(self) -> None:
        """Test token strength checking."""
        validator = ConfigValidator()
        result = validator.check_token_strength("TEST_TOKEN", "changeme")
        assert result is False


class TestRequestLogger:
    """Test request logging."""

    def test_logger_initialization(self) -> None:
        """Test request logger initialization."""
        logger = get_request_logger()
        assert logger is not None

    def test_value_sanitization(self) -> None:
        """Test value sanitization."""
        from components.request_logger import RequestLogger
        sanitized = RequestLogger.sanitize_value("my_secret_key_12345")
        assert "***" in sanitized or "..." in sanitized
        assert len(sanitized) < len("my_secret_key_12345")
