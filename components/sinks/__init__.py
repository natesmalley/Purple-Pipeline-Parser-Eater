"""Output sinks for event delivery."""

from .base_sink import BaseSink
from .s3_archive_sink import S3ArchiveSink

__all__ = ["BaseSink", "S3ArchiveSink"]
