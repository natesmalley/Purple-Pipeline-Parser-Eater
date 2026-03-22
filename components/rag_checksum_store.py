"""Checksum store for RAG ingestion deduplication."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Optional


class RAGChecksumStore:
    def __init__(self, db_path: str = "data/rag_checksums.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checksums (
                    source_id TEXT PRIMARY KEY,
                    sha256 TEXT NOT NULL,
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    doc_type TEXT,
                    file_path TEXT
                )
                """
            )

    @staticmethod
    def compute_checksum(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def should_ingest(self, source_id: str, content: str) -> bool:
        checksum = self.compute_checksum(content)
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute("SELECT sha256 FROM checksums WHERE source_id = ?", (source_id,))
            row = cur.fetchone()
        return row is None or row[0] != checksum

    def mark_ingested(self, source_id: str, content: str, doc_type: str, file_path: Optional[str] = None) -> None:
        checksum = self.compute_checksum(content)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO checksums (source_id, sha256, doc_type, file_path, ingested_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (source_id, checksum, doc_type, file_path)
            )

