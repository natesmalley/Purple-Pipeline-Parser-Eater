"""Tests for health check system."""

from __future__ import annotations

import asyncio
import pytest

from components.health_check import (
    HealthChecker,
    ServiceHealthCheck,
    SystemMetrics,
    get_health_checker,
)


class TestServiceHealthCheck:
    """Test individual service health checks."""

    @pytest.mark.asyncio
    async def test_service_check_healthy(self) -> None:
        """Test healthy service check."""
        async def healthy_check():
            return True, "Service is running"

        check = ServiceHealthCheck("test_service", healthy_check)
        result = await check.check()

        assert result["status"] == "healthy"
        assert "running" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_service_check_unhealthy(self) -> None:
        """Test unhealthy service check."""
        async def unhealthy_check():
            return False, "Service is down"

        check = ServiceHealthCheck("test_service", unhealthy_check)
        result = await check.check()

        assert result["status"] == "unhealthy"
        assert "down" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_service_check_exception(self) -> None:
        """Test service check with exception."""
        async def failing_check():
            raise RuntimeError("Connection failed")

        check = ServiceHealthCheck("test_service", failing_check)
        result = await check.check()

        assert result["status"] == "unhealthy"
        assert "failed" in result["message"].lower()

    def test_service_health_check_initialization(self) -> None:
        """Test service health check initialization."""
        async def dummy_check():
            return True, "ok"

        check = ServiceHealthCheck("test", dummy_check)
        assert check.name == "test"
        assert check.last_status is None
        assert check.last_check is None


class TestSystemMetrics:
    """Test system metrics collection."""

    def test_get_cpu_percent(self) -> None:
        """Test CPU usage retrieval."""
        cpu_percent = SystemMetrics.get_cpu_percent(interval=0.01)

        assert isinstance(cpu_percent, float)
        assert 0 <= cpu_percent <= 100

    def test_get_memory_info(self) -> None:
        """Test memory info retrieval."""
        memory = SystemMetrics.get_memory_info()

        assert "total_mb" in memory
        assert "used_mb" in memory
        assert "available_mb" in memory
        assert "percent" in memory

        assert memory["total_mb"] > 0
        assert memory["percent"] >= 0
        assert memory["percent"] <= 100

    def test_get_disk_info(self) -> None:
        """Test disk info retrieval."""
        disk = SystemMetrics.get_disk_info()

        assert "total_gb" in disk
        assert "used_gb" in disk
        assert "free_gb" in disk
        assert "percent" in disk

        assert disk["total_gb"] > 0
        assert disk["percent"] >= 0
        assert disk["percent"] <= 100

    def test_get_process_count(self) -> None:
        """Test process count retrieval."""
        count = SystemMetrics.get_process_count()

        assert isinstance(count, int)
        assert count > 0

    def test_get_uptime(self) -> None:
        """Test system uptime retrieval."""
        uptime = SystemMetrics.get_uptime()

        assert isinstance(uptime, float)
        assert uptime > 0


class TestHealthChecker:
    """Test health checker system."""

    def test_health_checker_initialization(self) -> None:
        """Test health checker initialization."""
        checker = HealthChecker()

        assert len(checker.services) == 0
        assert checker.start_time > 0

    def test_register_service(self) -> None:
        """Test service registration."""
        checker = HealthChecker()

        async def dummy_check():
            return True, "ok"

        checker.register_service("test_service", dummy_check)

        assert "test_service" in checker.services

    @pytest.mark.asyncio
    async def test_check_all_services_empty(self) -> None:
        """Test checking when no services registered."""
        checker = HealthChecker()
        results = await checker.check_all_services()

        assert results == {}

    @pytest.mark.asyncio
    async def test_check_all_services_single(self) -> None:
        """Test checking single service."""
        checker = HealthChecker()

        async def healthy_check():
            return True, "Running"

        checker.register_service("test_service", healthy_check)
        results = await checker.check_all_services()

        assert "test_service" in results
        assert results["test_service"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_check_all_services_multiple(self) -> None:
        """Test checking multiple services."""
        checker = HealthChecker()

        async def check1():
            return True, "Service 1 OK"

        async def check2():
            return False, "Service 2 Failed"

        checker.register_service("service1", check1)
        checker.register_service("service2", check2)
        results = await checker.check_all_services()

        assert len(results) == 2
        assert results["service1"]["status"] == "healthy"
        assert results["service2"]["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_get_health_status(self) -> None:
        """Test getting comprehensive health status."""
        checker = HealthChecker()

        async def check_service():
            return True, "OK"

        checker.register_service("test_service", check_service)
        status = await checker.get_health_status()

        assert "status" in status
        assert "timestamp" in status
        assert "services" in status
        assert "system_metrics" in status
        assert "service_count" in status
        assert "healthy_services" in status
        assert "resources_healthy" in status
        assert "version" in status

        assert status["service_count"] == 1
        assert status["healthy_services"] == 1

    @pytest.mark.asyncio
    async def test_get_health_status_metrics(self) -> None:
        """Test health status includes system metrics."""
        checker = HealthChecker()

        async def dummy_check():
            return True, "ok"

        checker.register_service("test", dummy_check)
        status = await checker.get_health_status()

        metrics = status["system_metrics"]
        assert "cpu_percent" in metrics
        assert "memory" in metrics
        assert "disk" in metrics
        assert "process_count" in metrics
        assert "uptime_seconds" in metrics
        assert "system_uptime_seconds" in metrics

    @pytest.mark.asyncio
    async def test_get_health_status_degraded(self) -> None:
        """Test health status shows degraded when service unhealthy."""
        checker = HealthChecker()

        async def failing_check():
            return False, "Service down"

        checker.register_service("failing", failing_check)
        status = await checker.get_health_status()

        assert status["status"] == "degraded"

    def test_get_health_summary(self) -> None:
        """Test health summary generation."""
        checker = HealthChecker()

        async def check1():
            return True, "ok"

        async def check2():
            return False, "fail"

        checker.register_service("s1", check1)
        checker.register_service("s2", check2)

        # Run checks first
        asyncio.run(checker.check_all_services())
        summary = checker.get_health_summary()

        assert "healthy" in summary.lower()
        assert "/" in summary  # Format: X/Y

    def test_get_default_health_checker(self) -> None:
        """Test getting default health checker instance."""
        checker1 = get_health_checker()
        checker2 = get_health_checker()

        assert checker1 is checker2


class TestHealthCheckIntegration:
    """Integration tests for health checking."""

    @pytest.mark.asyncio
    async def test_full_health_check_workflow(self) -> None:
        """Test complete health check workflow."""
        checker = HealthChecker()

        # Register services
        async def api_check():
            return True, "API responding"

        async def db_check():
            return True, "Database connected"

        checker.register_service("api", api_check)
        checker.register_service("database", db_check)

        # Get health status
        status = await checker.get_health_status()

        assert status["status"] in ["healthy", "degraded"]
        assert status["healthy_services"] == 2
        assert len(status["system_metrics"]) > 0

    @pytest.mark.asyncio
    async def test_health_check_with_timeout(self) -> None:
        """Test health check with slow service."""
        checker = HealthChecker()

        async def slow_check():
            await asyncio.sleep(0.01)
            return True, "Slow but working"

        checker.register_service("slow_service", slow_check)
        status = await checker.get_health_status()

        assert status["healthy_services"] == 1
