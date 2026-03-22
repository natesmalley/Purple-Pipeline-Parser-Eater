"""SCOL API poller event source."""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp

from .base_source import BaseEventSource

logger = logging.getLogger(__name__)


class CheckpointStore:
    """SQLite-backed checkpoint storage for API polling."""

    def __init__(self, db_path: str) -> None:
        """Initialize checkpoint store.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def get_checkpoint(self, key: str) -> Optional[str]:
        """Retrieve checkpoint value.

        Args:
            key: Checkpoint key.

        Returns:
            Checkpoint value or None if not set.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT value FROM checkpoints WHERE key = ?",
                (key,),
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def set_checkpoint(self, key: str, value: str) -> None:
        """Save checkpoint value.

        Args:
            key: Checkpoint key.
            value: Checkpoint value to save.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO checkpoints (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                (key, value),
            )
            conn.commit()


class SCOLAPISource(BaseEventSource):
    """SCOL (Security Collection) API poller.

    Polls REST APIs with checkpoint management for incremental polling.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize SCOL API source.

        Args:
            config: Configuration with keys:
                - api_url: REST API endpoint URL
                - auth_token: Bearer token for authentication
                - poll_interval_secs: Polling interval (default 60)
                - checkpoint_db: Path to checkpoint database
                - checkpoint_key: Unique key for this source's checkpoint
                - parser_id: Parser to apply to events
                - query_params: Optional dict of query parameters
        """
        super().__init__(config)
        self.validate_config([
            "api_url",
            "auth_token",
            "checkpoint_key",
            "parser_id",
        ])

        self.api_url = config["api_url"]
        self.auth_token = config["auth_token"]
        self.poll_interval = config.get("poll_interval_secs", 60)
        self.checkpoint_key = config["checkpoint_key"]
        self.parser_id = config["parser_id"]
        self.query_params = config.get("query_params", {})

        checkpoint_db = config.get(
            "checkpoint_db",
            "data/scol_checkpoints.db",
        )
        self.checkpoint_store = CheckpointStore(checkpoint_db)

        self._running = False
        self._callback = None
        self._task = None

    def get_source_type(self) -> str:
        """Return source type identifier."""
        return "scol"

    async def start(self) -> None:
        """Start polling API."""
        self._running = True
        self._task = asyncio.create_task(self._polling_loop())
        logger.info(
            "SCOL API poller started for %s (interval: %ds)",
            self.api_url,
            self.poll_interval,
        )

    async def stop(self) -> None:
        """Stop polling and cleanup."""
        self._running = False
        if self._task:
            await self._task
        logger.info("SCOL API poller stopped")

    def set_event_callback(self, callback) -> None:
        """Set callback function for fetched events.

        Args:
            callback: Async callable(event, parser_id) that processes events.
        """
        self._callback = callback

    async def _polling_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                events = await self.poll_api()
                if events and self._callback:
                    for event in events:
                        await self._callback(event, self.parser_id)
            except Exception as e:
                logger.error("Error in SCOL polling loop: %s", e)

            await asyncio.sleep(self.poll_interval)

    async def poll_api(self) -> List[Dict[str, Any]]:
        """Poll API endpoint.

        Steps:
        1. Read checkpoint (last fetch timestamp)
        2. Calculate time window
        3. HTTP GET with query params
        4. Parse JSON response
        5. Extract events
        6. Update checkpoint

        Returns:
            List of events from API.
        """
        last_checkpoint = self.checkpoint_store.get_checkpoint(self.checkpoint_key)

        params = self.query_params.copy()
        if last_checkpoint:
            params["timestamp"] = last_checkpoint

        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Accept": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.api_url,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status != 200:
                        logger.error(
                            "API returned status %d: %s",
                            response.status,
                            await response.text(),
                        )
                        return []

                    data = await response.json()

                    # Extract events from response
                    events = self._extract_events(data)

                    # Update checkpoint
                    if events:
                        new_checkpoint = datetime.now().isoformat()
                        self.checkpoint_store.set_checkpoint(
                            self.checkpoint_key,
                            new_checkpoint,
                        )

                    logger.debug("Polled %d events from %s", len(events), self.api_url)
                    return events

        except asyncio.TimeoutError:
            logger.warning("API poll timed out: %s", self.api_url)
            return []
        except Exception as e:
            logger.error("Error polling API %s: %s", self.api_url, e)
            return []

    @staticmethod
    def _extract_events(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract events from API response.

        Args:
            data: API response data.

        Returns:
            List of events.
        """
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Try common event array keys
            for key in ["events", "records", "logs", "data", "results"]:
                if key in data:
                    value = data[key]
                    if isinstance(value, list):
                        return value
            # If dict has event-like structure, return as single event
            if any(k in data for k in ["timestamp", "time", "date", "event"]):
                return [data]
        return []
