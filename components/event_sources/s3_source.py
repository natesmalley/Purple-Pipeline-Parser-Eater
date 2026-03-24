"""S3 bucket event processor source."""

from __future__ import annotations

import bz2
import csv
import gzip
import json
import logging
from io import StringIO
from typing import Any, Dict, List, Optional

from .base_source import BaseEventSource

logger = logging.getLogger(__name__)


class FileParser:
    """Parse different file formats."""

    @staticmethod
    def parse_jsonl(content: str) -> List[Dict[str, Any]]:
        """Parse JSON Lines format.

        Args:
            content: File content in JSONL format.

        Returns:
            List of parsed events.
        """
        events = []
        for line in content.splitlines():
            if line.strip():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.warning("Failed to parse JSONL line: %s", e)
        return events

    @staticmethod
    def parse_json(content: str) -> List[Dict[str, Any]]:
        """Parse JSON format.

        Args:
            content: File content in JSON format.

        Returns:
            List of parsed events.
        """
        data = json.loads(content)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Look for common array keys
            for key in ["events", "records", "logs", "data", "results"]:
                if key in data:
                    value = data[key]
                    if isinstance(value, list):
                        return value
            # Single event as dict
            return [data]
        return []

    @staticmethod
    def parse_csv(content: str) -> List[Dict[str, Any]]:
        """Parse CSV format.

        Args:
            content: File content in CSV format.

        Returns:
            List of parsed events as dicts.
        """
        events = []
        reader = csv.DictReader(StringIO(content))
        if reader and reader.fieldnames:
            for row in reader:
                if row:
                    events.append(row)
        return events


class S3EventSource(BaseEventSource):
    """S3 bucket event processor.

    Features:
    - S3 bucket object processing
    - Support multiple formats: JSONL, JSON, CSV
    - Compression support: gzip, bzip2
    - Checkpointing (track processed files)
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize S3 event source.

        Args:
            config: Configuration with keys:
                - bucket: S3 bucket name
                - region: AWS region (default us-east-1)
                - prefix: S3 key prefix to scan (default '')
                - format: File format (jsonl, json, csv)
                - compression: Compression type (none, gzip, bzip2)
                - parser_id: Parser to apply to events
        """
        super().__init__(config)
        self.validate_config(["bucket", "parser_id"])

        self.bucket = config["bucket"]
        self.region = config.get("region", "us-east-1")
        self.prefix = config.get("prefix", "")
        self.format = config.get("format", "jsonl").lower()
        self.compression = config.get("compression", "none").lower()
        self.parser_id = config["parser_id"]

        self._client = None
        self._callback = None
        self._processed_keys = set()

    def get_source_type(self) -> str:
        """Return source type identifier."""
        return "s3"

    async def start(self) -> None:
        """Start S3 bucket scanning."""
        try:
            import boto3  # type: ignore
        except ImportError as e:
            raise ImportError("boto3 not installed. Install with: pip install boto3") from e

        try:
            self._client = boto3.client("s3", region_name=self.region)
            logger.info("S3 client initialized for bucket: %s", self.bucket)
        except Exception as e:
            logger.error("Failed to initialize S3 client: %s", e)
            raise

    async def stop(self) -> None:
        """Stop S3 client and cleanup."""
        if self._client:
            self._client.close()
            logger.info("S3 client closed")

    def set_event_callback(self, callback) -> None:
        """Set callback function for processed events.

        Args:
            callback: Async callable(event, parser_id) that processes events.
        """
        self._callback = callback

    async def process_file(self, s3_key: str) -> List[Dict[str, Any]]:
        """Download and process S3 file.

        Args:
            s3_key: S3 object key.

        Returns:
            List of events from file.
        """
        if not self._client:
            raise RuntimeError("S3 client not initialized")

        try:
            # Download file
            response = self._client.get_object(Bucket=self.bucket, Key=s3_key)
            body = response["Body"].read()

            # Decompress if needed
            if self.compression == "gzip":
                body = gzip.decompress(body)
            elif self.compression == "bzip2":
                body = bz2.decompress(body)

            content = body.decode("utf-8")

            # Parse based on format
            if self.format == "jsonl":
                events = FileParser.parse_jsonl(content)
            elif self.format == "json":
                events = FileParser.parse_json(content)
            elif self.format == "csv":
                events = FileParser.parse_csv(content)
            else:
                logger.warning("Unknown format: %s, defaulting to jsonl", self.format)
                events = FileParser.parse_jsonl(content)

            logger.debug("Parsed %d events from %s", len(events), s3_key)
            self._processed_keys.add(s3_key)
            return events

        except Exception as e:
            logger.error("Error processing S3 file %s: %s", s3_key, e)
            return []

    async def scan_bucket(self) -> None:
        """Scan bucket for new files and process them."""
        if not self._client:
            raise RuntimeError("S3 client not initialized")

        try:
            paginator = self._client.get_paginator("list_objects_v2")
            pages = paginator.paginate(
                Bucket=self.bucket,
                Prefix=self.prefix,
            )

            for page in pages:
                if "Contents" not in page:
                    continue

                for obj in page["Contents"]:
                    s3_key = obj["Key"]
                    if s3_key in self._processed_keys:
                        continue

                    events = await self.process_file(s3_key)
                    if events and self._callback:
                        for event in events:
                            await self._callback(event, self.parser_id)

        except Exception as e:
            logger.error("Error scanning S3 bucket: %s", e)
