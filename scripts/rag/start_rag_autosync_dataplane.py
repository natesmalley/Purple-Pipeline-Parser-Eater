"""Dataplane documentation ingestion using checksum store."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from components.rag_checksum_store import RAGChecksumStore
from components.rag_knowledge import RAGKnowledgeBase
from utils.config import load_config


logger = logging.getLogger(__name__)


async def ingest_dataplane_docs() -> None:
    config = load_config()
    checksum_store = RAGChecksumStore(config.get("rag", {}).get("checksum_store_path", "data/rag_checksums.db"))
    knowledge_base = RAGKnowledgeBase(config)

    dataplane_docs_dir = os.getenv("DATAPLANE_DOCS_DIR", "").strip()
    if not dataplane_docs_dir:
        logger.warning(
            "DATAPLANE_DOCS_DIR is not set; skipping dataplane docs ingestion"
        )
        return

    dataplane_path = Path(dataplane_docs_dir)
    if not dataplane_path.exists():
        logger.warning(
            "Configured DATAPLANE_DOCS_DIR does not exist (%s); skipping ingestion",
            dataplane_path,
        )
        return

    for doc in dataplane_path.rglob("*.md"):
        content = doc.read_text(encoding="utf-8")
        source_id = f"dataplane_doc:{doc.relative_to(dataplane_path)}"
        if not checksum_store.should_ingest(source_id, content):
            continue
        knowledge_base.add_document(content, {
            "source_id": source_id,
            "type": "dataplane_doc",
            "path": str(doc)
        })
        checksum_store.mark_ingested(source_id, content, "dataplane_doc", str(doc))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(ingest_dataplane_docs())
