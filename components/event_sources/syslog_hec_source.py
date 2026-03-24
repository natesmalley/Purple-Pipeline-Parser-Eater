"""Syslog HTTP Event Collector (HEC) receiver source."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from .base_source import BaseEventSource

logger = logging.getLogger(__name__)


class SyslogHECSource(BaseEventSource):
    """Syslog HTTP Event Collector endpoint.

    Features:
    - HTTP POST endpoint (/services/collector/event)
    - Token-based authentication
    - Splunk HEC protocol compatible
    - Batch event support
    - JSON and raw format support
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize Syslog HEC source.

        Args:
            config: Configuration with keys:
                - host: Bind address (default 0.0.0.0)
                - port: Listen port (default 8088)
                - auth_tokens: List of valid bearer tokens
                - ssl_enabled: Enable TLS (default False)
                - ssl_cert_path: Path to SSL certificate (if ssl_enabled)
                - ssl_key_path: Path to SSL key (if ssl_enabled)
                - default_parser_id: Default parser ID
                - source_routing: Optional dict mapping source names to parser IDs
        """
        super().__init__(config)
        self.validate_config(["auth_tokens", "default_parser_id"])

        self.host = config.get("host", "0.0.0.0")
        self.port = config.get("port", 8088)
        self.auth_tokens = config["auth_tokens"]
        self.ssl_enabled = config.get("ssl_enabled", False)
        self.ssl_cert_path = config.get("ssl_cert_path")
        self.ssl_key_path = config.get("ssl_key_path")
        self.default_parser_id = config["default_parser_id"]
        self.source_routing = config.get("source_routing", {})

        self._app = None
        self._runner = None
        self._site = None
        self._callback = None

    def get_source_type(self) -> str:
        """Return source type identifier."""
        return "syslog"

    async def start(self) -> None:
        """Start HTTP server."""
        try:
            from aiohttp import web  # type: ignore
        except ImportError as e:
            raise ImportError("aiohttp not installed. Install with: pip install aiohttp") from e

        try:
            self._app = web.Application()
            self._app.router.add_post("/services/collector/event", self._handle_event)
            self._app.router.add_post("/services/collector/raw", self._handle_raw)

            self._runner = web.AppRunner(self._app)
            await self._runner.setup()

            if self.ssl_enabled:
                import ssl
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ssl_context.load_cert_chain(self.ssl_cert_path, self.ssl_key_path)
                self._site = web.TCPSite(
                    self._runner,
                    self.host,
                    self.port,
                    ssl_context=ssl_context,
                )
            else:
                self._site = web.TCPSite(self._runner, self.host, self.port)

            await self._site.start()
            logger.info(
                "Syslog HEC receiver started on %s:%d (SSL: %s)",
                self.host,
                self.port,
                self.ssl_enabled,
            )

        except Exception as e:
            logger.error("Failed to start Syslog HEC receiver: %s", e)
            raise

    async def stop(self) -> None:
        """Stop HTTP server and cleanup."""
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
        logger.info("Syslog HEC receiver stopped")

    def set_event_callback(self, callback) -> None:
        """Set callback function for received events.

        Args:
            callback: Async callable(event, parser_id) that processes events.
        """
        self._callback = callback

    def _verify_token(self, auth_header: str) -> bool:
        """Verify HEC authentication token.

        Args:
            auth_header: Authorization header value.

        Returns:
            True if token is valid.
        """
        if not auth_header:
            return False

        # Remove 'Splunk ' prefix if present
        token = auth_header.replace("Splunk ", "").strip()
        return token in self.auth_tokens

    def _get_parser_id(self, event: Dict[str, Any]) -> str:
        """Determine parser ID for event.

        Args:
            event: Event data.

        Returns:
            Parser ID to use.
        """
        source = event.get("source", "").lower()
        for source_name, parser_id in self.source_routing.items():
            if source_name.lower() in source:
                return parser_id
        return self.default_parser_id

    async def _handle_event(self, request) -> Any:
        """Handle HEC event POST.

        Expected format:
        {
          "event": {...},
          "time": 1234567890,
          "source": "my-source",
          "sourcetype": "json"
        }
        """
        # Verify authentication
        auth_header = request.headers.get("Authorization", "")
        if not self._verify_token(auth_header):
            logger.warning("Unauthorized HEC request from %s", request.remote)
            from aiohttp import web
            return web.json_response(
                {"error": "Invalid authentication token"},
                status=401,
            )

        try:
            data = await request.json()
        except Exception as e:
            logger.warning("Failed to parse HEC request: %s", e)
            from aiohttp import web
            return web.json_response(
                {"error": "Invalid JSON"},
                status=400,
            )

        try:
            # Extract event data
            event = data.get("event", data)
            parser_id = self._get_parser_id(data)

            # Process event
            if self._callback:
                await self._callback(event, parser_id)

            from aiohttp import web
            return web.json_response({"success": True})

        except Exception as e:
            logger.error("Error processing HEC event: %s", e)
            from aiohttp import web
            return web.json_response(
                {"error": str(e)},
                status=500,
            )

    async def _handle_raw(self, request) -> Any:
        """Handle HEC raw event POST.

        Expects raw text data with optional metadata in headers.
        """
        # Verify authentication
        auth_header = request.headers.get("Authorization", "")
        if not self._verify_token(auth_header):
            logger.warning("Unauthorized HEC raw request from %s", request.remote)
            from aiohttp import web
            return web.json_response(
                {"error": "Invalid authentication token"},
                status=401,
            )

        try:
            # Read raw body
            body = await request.read()
            raw_text = body.decode("utf-8")

            # Extract metadata from headers
            source = request.headers.get("X-Event-Source", "syslog")
            sourcetype = request.headers.get("X-Event-Sourcetype", "raw")

            # Create event dict
            event = {
                "raw": raw_text,
                "source": source,
                "sourcetype": sourcetype,
            }

            parser_id = self._get_parser_id(event)

            # Process event
            if self._callback:
                await self._callback(event, parser_id)

            from aiohttp import web
            return web.json_response({"success": True})

        except Exception as e:
            logger.error("Error processing HEC raw event: %s", e)
            from aiohttp import web
            return web.json_response(
                {"error": str(e)},
                status=500,
            )
