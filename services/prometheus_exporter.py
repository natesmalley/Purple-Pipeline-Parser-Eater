"""
Prometheus Metrics Exporter Service

Exposes system and application metrics via HTTP /metrics endpoint in Prometheus format.
Supports both standalone HTTP server and integration with Flask application.

Metrics Collected:
- Event processing counters (total, success, failed)
- Parser performance metrics (by parser_id)
- API call metrics (Claude, Observo, etc.)
- Error tracking and categorization
- System resource usage (CPU, memory, disk)
- Request latency distributions
- Cache hit rates
- Database performance

Usage:
    # Standalone server
    exporter = PrometheusExporter(port=9090)
    exporter.start()

    # Integrated with Flask
    from prometheus_client import make_wsgi_app
    app = Flask(__name__)
    metrics_app = make_wsgi_app()
    app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {'/metrics': metrics_app})

Configuration:
    prometheus_port: 9090 (default)
    prometheus_host: 0.0.0.0 (default)
    metrics_path: /metrics (default)
    update_interval: 15 (seconds, default)

Type hints:
    All functions have type hints for better IDE support

Examples:
    >>> from services.prometheus_exporter import PrometheusExporter
    >>> exporter = PrometheusExporter()
    >>> exporter.start()
    >>> # Metrics available at http://localhost:9090/metrics
"""

import os
import sys
import time
import logging
import threading
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        Summary,
        generate_latest,
        CollectorRegistry,
        CONTENT_TYPE_LATEST
    )
except ImportError:
    print("WARNING: prometheus_client not installed. Install with: pip install prometheus-client")
    sys.exit(1)

logger = logging.getLogger(__name__)


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Prometheus metrics endpoint."""

    # Class variable to hold registry
    registry = None

    def do_GET(self) -> None:
        """
        Handle GET requests for metrics.

        Endpoints:
            /metrics - Prometheus metrics in text format
            /health  - Health check
            /        - Redirect to /metrics

        Args:
            None (uses self.path from BaseHTTPRequestHandler)

        Returns:
            None (writes response to socket)
        """
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-Type', CONTENT_TYPE_LATEST.decode('utf-8'))
            self.end_headers()
            self.wfile.write(generate_latest(self.registry))

        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"healthy"}')

        elif self.path == '/':
            self.send_response(302)
            self.send_header('Location', '/metrics')
            self.end_headers()

        else:
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not Found')

    def log_message(self, format, *args) -> None:
        """Suppress request logging to avoid spam."""
        pass


class PrometheusExporter:
    """
    Prometheus metrics exporter for Purple Pipeline Parser Eater.

    Provides:
    - Standalone HTTP server on configurable port
    - Prometheus-formatted metrics
    - System and application metrics collection
    - Thread-safe metric updates

    Attributes:
        host: HTTP server host (default: 0.0.0.0)
        port: HTTP server port (default: 9090)
        metrics_path: Metrics endpoint (default: /metrics)
        registry: Prometheus CollectorRegistry
        server: HTTPServer instance
        thread: Server thread

    Example:
        >>> exporter = PrometheusExporter(port=9090)
        >>> exporter.start()
        >>> # Metrics available at http://localhost:9090/metrics
        >>> time.sleep(3600)
        >>> exporter.stop()
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 9090,
        metrics_path: str = "/metrics"
    ) -> None:
        """
        Initialize Prometheus exporter.

        Args:
            host: Bind address (default: 0.0.0.0)
            port: Bind port (default: 9090)
            metrics_path: Metrics endpoint path (default: /metrics)

        Raises:
            ValueError: If port is invalid
        """
        if not (1 <= port <= 65535):
            raise ValueError(f"Invalid port: {port}")

        self.host = host
        self.port = port
        self.metrics_path = metrics_path

        # Create registry
        self.registry = CollectorRegistry()

        # Store registry in handler class
        MetricsHandler.registry = self.registry

        # Initialize metrics
        self._init_metrics()

        # Server thread
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False

        logger.info(f"Prometheus exporter initialized on {host}:{port}")

    def _init_metrics(self) -> None:
        """
        Initialize all Prometheus metrics.

        Creates:
        - Event processing counters
        - Parser performance metrics
        - API call metrics
        - Error tracking
        - Request latency histograms
        - Gauge metrics for active items
        - Summary statistics

        Returns:
            None
        """
        logger.info("Initializing Prometheus metrics...")

        # Event Processing Counters
        self.events_processed_total = Counter(
            'purple_events_processed_total',
            'Total events processed',
            ['source_type', 'parser_id'],
            registry=self.registry
        )

        self.events_success_total = Counter(
            'purple_events_success_total',
            'Successfully processed events',
            ['source_type', 'parser_id'],
            registry=self.registry
        )

        self.events_failed_total = Counter(
            'purple_events_failed_total',
            'Failed event processing',
            ['source_type', 'parser_id', 'error_type'],
            registry=self.registry
        )

        # Parser-specific metrics
        self.parser_execution_duration = Histogram(
            'purple_parser_execution_duration_seconds',
            'Parser execution duration',
            ['parser_id'],
            buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
            registry=self.registry
        )

        self.parser_error_rate = Gauge(
            'purple_parser_error_rate',
            'Parser error rate (0-1)',
            ['parser_id'],
            registry=self.registry
        )

        # API Metrics
        self.api_calls_total = Counter(
            'purple_api_calls_total',
            'Total API calls',
            ['api_name', 'method'],
            registry=self.registry
        )

        self.api_errors_total = Counter(
            'purple_api_errors_total',
            'Failed API calls',
            ['api_name', 'error_code'],
            registry=self.registry
        )

        self.api_latency = Histogram(
            'purple_api_latency_seconds',
            'API call latency',
            ['api_name'],
            buckets=(0.01, 0.1, 0.5, 1.0, 5.0, 10.0),
            registry=self.registry
        )

        # Transformation Metrics
        self.transformations_total = Counter(
            'purple_transformations_total',
            'Total Lua transformations executed',
            ['parser_id'],
            registry=self.registry
        )

        self.transformation_latency = Histogram(
            'purple_transformation_latency_seconds',
            'Lua transformation execution time',
            ['parser_id'],
            buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1.0),
            registry=self.registry
        )

        # Output Metrics
        self.events_delivered_total = Counter(
            'purple_events_delivered_total',
            'Events delivered to sinks',
            ['sink_type'],
            registry=self.registry
        )

        self.delivery_failures_total = Counter(
            'purple_delivery_failures_total',
            'Event delivery failures',
            ['sink_type', 'reason'],
            registry=self.registry
        )

        # System Metrics
        self.active_workers = Gauge(
            'purple_active_workers',
            'Number of active worker threads',
            registry=self.registry
        )

        self.queue_size = Gauge(
            'purple_queue_size',
            'Event queue size',
            ['queue_name'],
            registry=self.registry
        )

        self.memory_bytes = Gauge(
            'purple_memory_bytes',
            'Memory usage in bytes',
            registry=self.registry
        )

        self.uptime_seconds = Gauge(
            'purple_uptime_seconds',
            'Process uptime in seconds',
            registry=self.registry
        )

        # Canary/A-B Testing Metrics
        self.canary_events = Counter(
            'purple_canary_events_total',
            'Events routed to canary version',
            ['parser_id'],
            registry=self.registry
        )

        self.canary_errors = Counter(
            'purple_canary_errors_total',
            'Canary version errors',
            ['parser_id'],
            registry=self.registry
        )

        # Cache Metrics
        self.cache_hits = Counter(
            'purple_cache_hits_total',
            'Cache hits',
            ['cache_name'],
            registry=self.registry
        )

        self.cache_misses = Counter(
            'purple_cache_misses_total',
            'Cache misses',
            ['cache_name'],
            registry=self.registry
        )

        # Database Metrics
        self.db_queries = Counter(
            'purple_db_queries_total',
            'Database queries',
            ['operation', 'table'],
            registry=self.registry
        )

        self.db_query_duration = Histogram(
            'purple_db_query_duration_seconds',
            'Database query duration',
            ['operation'],
            buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1.0),
            registry=self.registry
        )

        logger.info("Prometheus metrics initialized successfully")

    def record_event_processed(
        self,
        source_type: str,
        parser_id: str,
        success: bool,
        error_type: Optional[str] = None
    ) -> None:
        """
        Record an event processing attempt.

        Args:
            source_type: Event source type (e.g., 'kafka', 's3')
            parser_id: Parser identifier
            success: Whether processing succeeded
            error_type: Error type if failed

        Returns:
            None
        """
        self.events_processed_total.labels(
            source_type=source_type,
            parser_id=parser_id
        ).inc()

        if success:
            self.events_success_total.labels(
                source_type=source_type,
                parser_id=parser_id
            ).inc()
        else:
            error_type = error_type or 'unknown'
            self.events_failed_total.labels(
                source_type=source_type,
                parser_id=parser_id,
                error_type=error_type
            ).inc()

    def record_parser_execution(
        self,
        parser_id: str,
        duration_seconds: float
    ) -> None:
        """
        Record parser execution metrics.

        Args:
            parser_id: Parser identifier
            duration_seconds: Execution duration in seconds

        Returns:
            None
        """
        self.parser_execution_duration.labels(parser_id=parser_id).observe(duration_seconds)

    def record_api_call(
        self,
        api_name: str,
        method: str,
        duration_seconds: float,
        success: bool,
        error_code: Optional[str] = None
    ) -> None:
        """
        Record API call metrics.

        Args:
            api_name: API name (e.g., 'claude_api', 'observo_api')
            method: HTTP method (GET, POST, etc.)
            duration_seconds: Call duration in seconds
            success: Whether call succeeded
            error_code: Error code if failed

        Returns:
            None
        """
        self.api_calls_total.labels(api_name=api_name, method=method).inc()
        self.api_latency.labels(api_name=api_name).observe(duration_seconds)

        if not success and error_code:
            self.api_errors_total.labels(
                api_name=api_name,
                error_code=error_code
            ).inc()

    def record_transformation(
        self,
        parser_id: str,
        duration_seconds: float
    ) -> None:
        """
        Record Lua transformation execution metrics.

        Args:
            parser_id: Parser identifier
            duration_seconds: Execution duration in seconds

        Returns:
            None
        """
        self.transformations_total.labels(parser_id=parser_id).inc()
        self.transformation_latency.labels(parser_id=parser_id).observe(duration_seconds)

    def record_delivery(
        self,
        sink_type: str,
        success: bool,
        reason: Optional[str] = None
    ) -> None:
        """
        Record event delivery metrics.

        Args:
            sink_type: Sink type (e.g., 'observo', 's3', 'syslog')
            success: Whether delivery succeeded
            reason: Failure reason if applicable

        Returns:
            None
        """
        if success:
            self.events_delivered_total.labels(sink_type=sink_type).inc()
        else:
            reason = reason or 'unknown'
            self.delivery_failures_total.labels(
                sink_type=sink_type,
                reason=reason
            ).inc()

    def set_active_workers(self, count: int) -> None:
        """
        Set number of active worker threads.

        Args:
            count: Number of active workers

        Returns:
            None
        """
        self.active_workers.set(count)

    def set_queue_size(self, queue_name: str, size: int) -> None:
        """
        Set event queue size.

        Args:
            queue_name: Name of queue
            size: Current queue size

        Returns:
            None
        """
        self.queue_size.labels(queue_name=queue_name).set(size)

    def set_memory_usage(self, bytes_used: int) -> None:
        """
        Set memory usage metric.

        Args:
            bytes_used: Memory used in bytes

        Returns:
            None
        """
        self.memory_bytes.set(bytes_used)

    def start(self) -> None:
        """
        Start the Prometheus metrics HTTP server.

        Starts a background thread serving metrics on configured host/port.
        The server handles /metrics, /health, and / endpoints.

        Returns:
            None

        Raises:
            RuntimeError: If server fails to start
        """
        if self.running:
            logger.warning("Exporter already running")
            return

        try:
            # Create HTTP server
            self.server = HTTPServer((self.host, self.port), MetricsHandler)

            # Start in background thread
            self.thread = threading.Thread(
                target=self.server.serve_forever,
                daemon=True,
                name="PrometheusExporter"
            )
            self.thread.start()
            self.running = True

            logger.info(f"Prometheus exporter started on http://{self.host}:{self.port}/metrics")

        except OSError as e:
            logger.error(f"Failed to start exporter: {e}")
            raise RuntimeError(f"Failed to start Prometheus exporter: {e}")

    def stop(self) -> None:
        """
        Stop the Prometheus metrics HTTP server.

        Gracefully shuts down the server and waits for thread completion.

        Returns:
            None
        """
        if not self.running or not self.server:
            return

        try:
            self.server.shutdown()
            self.server.server_close()
            self.running = False
            logger.info("Prometheus exporter stopped")
        except Exception as e:
            logger.error(f"Error stopping exporter: {e}")


# Global exporter instance
_exporter: Optional[PrometheusExporter] = None


def get_exporter() -> PrometheusExporter:
    """
    Get or create the global Prometheus exporter instance.

    Returns:
        PrometheusExporter instance

    Example:
        >>> exporter = get_exporter()
        >>> exporter.start()
    """
    global _exporter
    if _exporter is None:
        port = int(os.getenv('PROMETHEUS_PORT', 9090))
        host = os.getenv('PROMETHEUS_HOST', '0.0.0.0')
        _exporter = PrometheusExporter(host=host, port=port)
    return _exporter


if __name__ == '__main__':
    # Simple test/demo
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    exporter = PrometheusExporter()
    exporter.start()

    logger.info("Prometheus exporter running")
    logger.info("Metrics available at http://localhost:9090/metrics")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        exporter.stop()
