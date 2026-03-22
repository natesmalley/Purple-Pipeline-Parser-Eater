"""
SDL Logging Handler - Send ALL Application Logs to SentinelOne SDL

This component creates a Python logging handler that sends EVERY log message
(operational, security, errors, warnings, info) to SentinelOne SDL for
centralized log aggregation and SIEM analysis.

Captures:
- Application startup/shutdown
- Parser conversions (start, success, failure)
- User interactions (Web UI access, button clicks)
- Security events (auth failures, validation errors)
- Errors and exceptions
- Performance metrics
- RAG operations
- GitHub sync events
- Everything that gets logged!
"""

import logging
import asyncio
import json
from datetime import datetime
from typing import Dict, Optional
import socket
import os
import queue
import threading

logger = logging.getLogger(__name__)


class SDLLoggingHandler(logging.Handler):
    """
    Python logging handler that sends ALL logs to SentinelOne SDL

    Integrates with Python's standard logging system to capture
    every log message and send it to SDL for centralized aggregation.

    Usage:
        # Add to logging configuration
        sdl_handler = SDLLoggingHandler(config)
        logging.root.addHandler(sdl_handler)

        # Now ALL logger.info/warning/error calls go to SDL!
    """

    def __init__(self, config: Dict, level=logging.INFO):
        """
        Initialize SDL logging handler

        Args:
            config: Application configuration dict
            level: Minimum log level to send to SDL (default: INFO)
        """
        super().__init__(level=level)

        # SDL configuration
        sdl_config = config.get("sentinelone_sdl", {})
        self.api_url = sdl_config.get("api_url", "https://xdr.us1.sentinelone.net/api/addEvents")
        self.api_key = sdl_config.get("api_key")
        self.enabled = sdl_config.get("audit_logging_enabled", True) and sdl_config.get("send_all_logs", True)
        self.batch_size = sdl_config.get("batch_size", 10)

        # Session info
        import uuid
        self.session_id = f"pppe-logs-{uuid.uuid4().hex[:16]}"
        self.hostname = socket.gethostname()
        self.service_name = "purple-pipeline-parser-eater"

        # Async queue for batching events
        self.event_queue = queue.Queue(maxsize=1000)
        self.batch = []
        self.lock = threading.Lock()

        # Statistics
        self.events_sent = 0
        self.events_failed = 0
        self.events_dropped = 0

        # Start background thread for sending batches
        if self.enabled:
            self.shutdown_flag = threading.Event()
            self.sender_thread = threading.Thread(target=self._sender_loop, daemon=True)
            self.sender_thread.start()
            logger.info(f"[SDL HANDLER] Initialized - sending ALL logs to SDL")
        else:
            logger.info("[SDL HANDLER] Disabled - logs stay local only")

    def emit(self, record: logging.LogRecord):
        """
        Called by Python logging system for each log message

        Converts log record to SDL event format and queues for sending
        """
        if not self.enabled:
            return

        try:
            # Convert log record to SDL event
            sdl_event = self._record_to_sdl_event(record)

            # Queue for batch sending (non-blocking)
            try:
                self.event_queue.put_nowait(sdl_event)
            except queue.Full:
                self.events_dropped += 1
                # Queue full - drop event to avoid blocking application

        except Exception as e:
            # Never let logging handler crash the application
            self.handleError(record)

    def _record_to_sdl_event(self, record: logging.LogRecord) -> Dict:
        """
        Convert Python log record to SDL event format

        Args:
            record: Python LogRecord object

        Returns:
            SDL event dict ready for /addEvents API
        """
        # Convert timestamp to nanoseconds
        ts_nanos = str(int(record.created * 1_000_000_000))

        # Map log level to SDL severity (0-6)
        severity_map = {
            logging.DEBUG: 1,
            logging.INFO: 2,
            logging.WARNING: 4,
            logging.ERROR: 5,
            logging.CRITICAL: 6
        }
        sev = severity_map.get(record.levelno, 2)

        # Build SDL event
        sdl_event = {
            "ts": ts_nanos,
            "sev": sev,
            "attrs": {
                "message": self.format(record),
                "logger_name": record.name,
                "level": record.levelname,
                "module": record.module,
                "function": record.funcName,
                "line_number": record.lineno,
                "hostname": self.hostname,
                "service": self.service_name,
                "process_id": record.process,
                "thread_id": record.thread,
                "thread_name": record.threadName,
            }
        }

        # Add exception info if present
        if record.exc_info:
            sdl_event["attrs"]["exception_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            sdl_event["attrs"]["exception_message"] = str(record.exc_info[1]) if record.exc_info[1] else None
            sdl_event["attrs"]["has_exception"] = True

        # Add extra fields from LogRecord
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName',
                               'levelname', 'levelno', 'lineno', 'module', 'msecs',
                               'message', 'pathname', 'process', 'processName', 'relativeCreated',
                               'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info']:
                    # Add custom fields (like parser_name, action, etc.)
                    sdl_event["attrs"][key] = str(value) if value is not None else ""

        return sdl_event

    def _sender_loop(self):
        """
        Background thread that batches and sends events to SDL

        Runs continuously, sending batches every 5 seconds or when batch is full
        """
        import httpx
        import time

        while not self.shutdown_flag.is_set():
            try:
                # Collect events for batch (timeout after 5 seconds)
                batch = []
                deadline = time.time() + 5.0

                while time.time() < deadline and len(batch) < self.batch_size:
                    try:
                        timeout = max(0.1, deadline - time.time())
                        event = self.event_queue.get(timeout=timeout)
                        batch.append(event)
                    except queue.Empty:
                        break

                # Send batch if we have events
                if batch:
                    self._send_batch(batch)

            except Exception as e:
                logger.error(f"[SDL HANDLER] Error in sender loop: {e}")
                time.sleep(1)

    def _send_batch(self, events: list):
        """Send batch of events to SDL"""
        try:
            import httpx

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # SDL /addEvents API payload
            payload = {
                "token": self.api_key,
                "session": self.session_id,
                "sessionInfo": {
                    "serverHost": self.hostname,
                    "application": self.service_name,
                    "log_type": "application_logs"
                },
                "events": events
            }

            # Synchronous send (in background thread)
            with httpx.Client(timeout=30.0) as client:
                response = client.post(self.api_url, json=payload, headers=headers)

                if response.status_code == 200:
                    self.events_sent += len(events)
                    resp_data = response.json()
                    logger.debug(
                        f"[SDL HANDLER] ✓ Sent {len(events)} logs to SDL "
                        f"(charged: {resp_data.get('bytesCharged', 0)} bytes)"
                    )
                else:
                    self.events_failed += len(events)
                    logger.error(
                        f"[SDL HANDLER] ✗ Failed to send {len(events)} logs: "
                        f"HTTP {response.status_code} - {response.text[:200]}"
                    )

        except Exception as e:
            self.events_failed += len(events)
            logger.error(f"[SDL HANDLER] Error sending batch: {e}")

    def close(self):
        """Flush remaining events and shutdown"""
        if self.enabled:
            # Signal shutdown
            self.shutdown_flag.set()

            # Wait for sender thread
            if hasattr(self, 'sender_thread'):
                self.sender_thread.join(timeout=10.0)

            # Flush remaining events
            remaining = []
            while not self.event_queue.empty():
                try:
                    remaining.append(self.event_queue.get_nowait())
                except queue.Empty:
                    break

            if remaining:
                self._send_batch(remaining)

        super().close()

    def get_statistics(self) -> Dict:
        """Get handler statistics"""
        return {
            "events_sent": self.events_sent,
            "events_failed": self.events_failed,
            "events_dropped": self.events_dropped,
            "queue_size": self.event_queue.qsize(),
            "enabled": self.enabled
        }


def configure_sdl_logging(config: Dict):
    """
    Configure Python logging to send ALL logs to SDL

    Call this once during application startup to enable
    centralized log aggregation to SentinelOne SDL.

    Args:
        config: Application configuration dict

    Example:
        # In continuous_conversion_service.py or orchestrator.py:
        from components.sdl_logging_handler import configure_sdl_logging
        configure_sdl_logging(config)

        # Now ALL logs go to SDL!
        logger.info("Starting conversion")  → Sent to SDL
        logger.error("Conversion failed")   → Sent to SDL
        logger.warning("Rate limit hit")    → Sent to SDL
    """
    # Create SDL handler
    sdl_handler = SDLLoggingHandler(config, level=logging.INFO)

    # Set formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    sdl_handler.setFormatter(formatter)

    # Add to root logger (captures ALL loggers)
    logging.root.addHandler(sdl_handler)

    logger.info("[SDL HANDLER] Configured - ALL application logs now sent to SentinelOne SDL")

    return sdl_handler
