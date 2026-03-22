"""S3 Archive sink for OCSF event archival."""

import asyncio
import gzip
import json
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

try:
    import boto3
except ImportError:
    boto3 = None

from .base_sink import BaseSink

logger = logging.getLogger(__name__)


class S3ArchiveSink(BaseSink):
    """
    Archive OCSF events to AWS S3.

    Features:
    - Partitioned by date and parser_id
    - JSONL format with gzip compression
    - Batch uploads for efficiency
    """

    def __init__(
        self,
        bucket_name: str,
        prefix: str = "purple-pipeline",
        aws_region: str = "us-east-1",
        batch_size: int = 1000,
        compression: bool = True,
    ):
        """
        Initialize S3 Archive Sink.

        Args:
            bucket_name: S3 bucket name
            prefix: Key prefix (folder path)
            aws_region: AWS region
            batch_size: Events per file
            compression: Enable gzip compression
        """
        if boto3 is None:
            raise ImportError(
                "boto3 is required for S3ArchiveSink. "
                "Install it with: pip install boto3"
            )

        self.bucket_name = bucket_name
        self.prefix = prefix
        self.batch_size = batch_size
        self.compression = compression

        self.s3_client = boto3.client("s3", region_name=aws_region)

        self.buffer: List[Dict[str, Any]] = []

        self.stats = {
            "total_archived": 0,
            "total_files": 0,
            "total_bytes": 0,
            "errors": 0,
        }

        logger.info(
            f"S3ArchiveSink initialized: s3://{bucket_name}/{prefix}"
        )

    async def write_event(self, event: Dict[str, Any]) -> bool:
        """
        Write event to S3 (buffered).

        Args:
            event: OCSF event with metadata

        Returns:
            True if successful, False on error
        """
        self.buffer.append(event)

        if len(self.buffer) >= self.batch_size:
            return await self.flush()

        return True

    async def write_events(self, events: List[Dict[str, Any]]) -> bool:
        """
        Write multiple events to S3.

        Args:
            events: List of OCSF events

        Returns:
            True if successful, False on error
        """
        for event in events:
            self.buffer.append(event)

        while len(self.buffer) >= self.batch_size:
            success = await self.flush()
            if not success:
                return False

        return True

    async def flush(self) -> bool:
        """
        Flush buffered events to S3.

        Returns:
            True if successful, False on error
        """
        if not self.buffer:
            return True

        try:
            events_by_parser: Dict[str, List[Dict[str, Any]]] = {}

            for event in self.buffer:
                parser_id = (
                    event.get("_metadata", {}).get("parser_id", "unknown")
                )
                if parser_id not in events_by_parser:
                    events_by_parser[parser_id] = []
                events_by_parser[parser_id].append(event)

            for parser_id, events in events_by_parser.items():
                await self._upload_partition(parser_id, events)

            count = len(self.buffer)
            self.buffer.clear()

            logger.info(f"Flushed {count} events to S3")
            return True

        except Exception as e:
            logger.error(
                f"Failed to flush events to S3: {e}", exc_info=True
            )
            self.stats["errors"] += 1
            return False

    async def _upload_partition(
        self, parser_id: str, events: List[Dict[str, Any]]
    ) -> None:
        """Upload events for a specific parser partition."""
        now = datetime.utcnow()

        key = (
            f"{self.prefix}/"
            f"year={now.year}/"
            f"month={now.month:02d}/"
            f"day={now.day:02d}/"
            f"hour={now.hour:02d}/"
            f"parser_id={parser_id}/"
            f"events-{now.strftime('%Y%m%d-%H%M%S')}.jsonl"
        )

        if self.compression:
            key += ".gz"

        with tempfile.NamedTemporaryFile(
            mode="wb", delete=False
        ) as tmp_file:
            tmp_path = tmp_file.name

            if self.compression:
                with gzip.open(tmp_file, "wt", encoding="utf-8") as gz_file:
                    for event in events:
                        json.dump(event, gz_file)
                        gz_file.write("\n")
            else:
                for event in events:
                    tmp_file.write(json.dumps(event).encode("utf-8"))
                    tmp_file.write(b"\n")

        try:
            file_size = Path(tmp_path).stat().st_size

            self.s3_client.upload_file(
                tmp_path,
                self.bucket_name,
                key,
                ExtraArgs={
                    "ContentType": "application/x-ndjson",
                    "ContentEncoding": "gzip" if self.compression else None,
                },
            )

            self.stats["total_archived"] += len(events)
            self.stats["total_files"] += 1
            self.stats["total_bytes"] += file_size

            logger.info(
                f"Uploaded {len(events)} events to "
                f"s3://{self.bucket_name}/{key} ({file_size} bytes)"
            )

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def get_statistics(self) -> Dict[str, Any]:
        """Get archive statistics."""
        return {**self.stats, "buffer_size": len(self.buffer)}

    async def close(self) -> None:
        """Close the sink."""
        await self.flush()
