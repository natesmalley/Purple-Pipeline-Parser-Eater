"""Comprehensive health check system for service monitoring."""

from __future__ import annotations

import asyncio
import logging
import psutil
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ServiceHealthCheck:
    """Individual service health check."""

    def __init__(self, name: str, check_func) -> None:
        """Initialize service health check.

        Args:
            name: Service name.
            check_func: Async callable that returns (healthy: bool, message: str).
        """
        self.name = name
        self.check_func = check_func
        self.last_status: Optional[bool] = None
        self.last_check: Optional[float] = None
        self.last_message: str = ""

    async def check(self) -> Dict[str, Any]:
        """Run health check.

        Returns:
            Dict with status, message, last_check time.
        """
        try:
            self.last_check = time.time()
            healthy, message = await self.check_func()
            self.last_status = healthy
            self.last_message = message

            return {
                "status": "healthy" if healthy else "unhealthy",
                "message": message,
                "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
        except Exception as e:
            logger.error("Health check failed for %s: %s", self.name, e)
            self.last_status = False
            self.last_message = str(e)

            return {
                "status": "unhealthy",
                "message": f"Check failed: {str(e)}",
                "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }


class SystemMetrics:
    """System resource metrics."""

    @staticmethod
    def get_cpu_percent(interval: float = 0.1) -> float:
        """Get CPU usage percentage.

        Args:
            interval: Sampling interval in seconds.

        Returns:
            CPU usage percentage (0-100).
        """
        try:
            return psutil.cpu_percent(interval=interval)
        except Exception as e:
            logger.warning("Failed to get CPU metrics: %s", e)
            return 0.0

    @staticmethod
    def get_memory_info() -> Dict[str, Any]:
        """Get memory usage information.

        Returns:
            Dict with memory usage stats.
        """
        try:
            memory = psutil.virtual_memory()
            return {
                "total_mb": memory.total / (1024 * 1024),
                "available_mb": memory.available / (1024 * 1024),
                "used_mb": memory.used / (1024 * 1024),
                "percent": memory.percent,
            }
        except Exception as e:
            logger.warning("Failed to get memory metrics: %s", e)
            return {
                "total_mb": 0,
                "available_mb": 0,
                "used_mb": 0,
                "percent": 0,
            }

    @staticmethod
    def get_disk_info(path: str = "/") -> Dict[str, Any]:
        """Get disk usage information.

        Args:
            path: Path to check disk usage for.

        Returns:
            Dict with disk usage stats.
        """
        try:
            disk = psutil.disk_usage(path)
            return {
                "total_gb": disk.total / (1024 * 1024 * 1024),
                "used_gb": disk.used / (1024 * 1024 * 1024),
                "free_gb": disk.free / (1024 * 1024 * 1024),
                "percent": disk.percent,
            }
        except Exception as e:
            logger.warning("Failed to get disk metrics: %s", e)
            return {
                "total_gb": 0,
                "used_gb": 0,
                "free_gb": 0,
                "percent": 0,
            }

    @staticmethod
    def get_process_count() -> int:
        """Get total process count.

        Returns:
            Number of running processes.
        """
        try:
            return len(psutil.pids())
        except Exception as e:
            logger.warning("Failed to get process count: %s", e)
            return 0

    @staticmethod
    def get_uptime() -> float:
        """Get system uptime in seconds.

        Returns:
            Uptime in seconds since last boot.
        """
        try:
            return time.time() - psutil.boot_time()
        except Exception as e:
            logger.warning("Failed to get uptime: %s", e)
            return 0.0


class HealthChecker:
    """Comprehensive health check system."""

    def __init__(self) -> None:
        """Initialize health checker."""
        self.services: Dict[str, ServiceHealthCheck] = {}
        self.start_time = time.time()

    def register_service(
        self, name: str, check_func
    ) -> None:
        """Register a service health check.

        Args:
            name: Service name.
            check_func: Async callable returning (healthy: bool, message: str).
        """
        self.services[name] = ServiceHealthCheck(name, check_func)
        logger.info("Registered health check for service: %s", name)

    async def check_all_services(self) -> Dict[str, Dict[str, Any]]:
        """Check all registered services.

        Returns:
            Dict mapping service names to their health status.
        """
        tasks = [
            (name, service.check())
            for name, service in self.services.items()
        ]

        results = {}
        for name, task in tasks:
            try:
                results[name] = await task
            except Exception as e:
                logger.error("Error checking service %s: %s", name, e)
                results[name] = {
                    "status": "unhealthy",
                    "message": str(e),
                }

        return results

    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status.

        Returns:
            Complete health report with service status and system metrics.
        """
        service_checks = await self.check_all_services()

        # Determine overall status
        all_healthy = all(
            check.get("status") == "healthy"
            for check in service_checks.values()
        )

        # Get system metrics
        metrics = {
            "cpu_percent": SystemMetrics.get_cpu_percent(),
            "memory": SystemMetrics.get_memory_info(),
            "disk": SystemMetrics.get_disk_info(),
            "process_count": SystemMetrics.get_process_count(),
            "uptime_seconds": time.time() - self.start_time,
            "system_uptime_seconds": SystemMetrics.get_uptime(),
        }

        # Check resource health
        resources_healthy = True
        if metrics["memory"]["percent"] > 90:
            resources_healthy = False
        if metrics["disk"]["percent"] > 95:
            resources_healthy = False

        return {
            "status": "healthy" if (all_healthy and resources_healthy) else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "services": service_checks,
            "system_metrics": metrics,
            "service_count": len(self.services),
            "healthy_services": sum(
                1 for check in service_checks.values()
                if check.get("status") == "healthy"
            ),
            "resources_healthy": resources_healthy,
            "version": "1.0.0",
        }

    def get_health_summary(self) -> str:
        """Get health status summary.

        Returns:
            Brief health summary.
        """
        healthy_count = sum(
            1 for service in self.services.values()
            if service.last_status is True
        )
        total_count = len(self.services)

        return f"{healthy_count}/{total_count} services healthy"


# Default health checker instance
_default_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """Get or create default health checker.

    Returns:
        Default HealthChecker instance.
    """
    global _default_checker
    if _default_checker is None:
        _default_checker = HealthChecker()
    return _default_checker
