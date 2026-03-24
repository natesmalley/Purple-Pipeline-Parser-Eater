"""
Observo.ai Documentation Processor for RAG Knowledge Base
Intelligent parsing, chunking, and ingestion of Observo documentation
"""
import logging
import re
import json
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


class ObservoDocsProcessor:
    """
    Processes Observo.ai documentation for RAG knowledge base ingestion

    Features:
    - Intelligent markdown parsing
    - Section-based chunking
    - Code example extraction
    - API endpoint identification
    - Metadata tagging
    """

    def __init__(self, docs_directory: str):
        """
        Initialize documentation processor

        Args:
            docs_directory: Path to Observo documentation directory
        """
        self.docs_directory = Path(docs_directory)
        self.statistics = {
            "files_processed": 0,
            "chunks_created": 0,
            "code_examples_extracted": 0,
            "api_endpoints_found": 0,
            "errors": []
        }

    def process_all_docs(self) -> List[Dict[str, Any]]:
        """
        Process all documentation files in directory

        Returns:
            List of document chunks ready for RAG ingestion
        """
        logger.info(f"Processing documentation from: {self.docs_directory}")

        all_chunks = []

        # Find all markdown files
        md_files = list(self.docs_directory.glob("*.md"))
        logger.info(f"Found {len(md_files)} markdown files")

        for md_file in md_files:
            try:
                chunks = self.process_document(md_file)
                all_chunks.extend(chunks)
                self.statistics["files_processed"] += 1
                logger.info(f"Processed {md_file.name}: {len(chunks)} chunks")
            except Exception as e:
                error_msg = f"Failed to process {md_file.name}: {e}"
                logger.error(error_msg)
                self.statistics["errors"].append(error_msg)

        self.statistics["chunks_created"] = len(all_chunks)
        logger.info(f"[OK] Processing complete: {len(all_chunks)} total chunks from {len(md_files)} files")

        return all_chunks

    def process_document(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Process single documentation file

        Args:
            file_path: Path to markdown file

        Returns:
            List of document chunks with metadata
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Determine document type
        doc_type = self._classify_document(file_path.name, content)

        # Parse document into sections
        sections = self._parse_sections(content)

        # Create chunks from sections
        chunks = []
        for section in sections:
            chunk = self._create_chunk(
                file_path=file_path,
                doc_type=doc_type,
                section=section
            )
            chunks.append(chunk)

        # Extract and add code examples as separate chunks
        code_examples = self._extract_code_examples(content)
        for example in code_examples:
            chunk = self._create_code_chunk(
                file_path=file_path,
                doc_type=doc_type,
                code_example=example
            )
            chunks.append(chunk)
            self.statistics["code_examples_extracted"] += 1

        # Extract API endpoints if present
        api_endpoints = self._extract_api_endpoints(content)
        self.statistics["api_endpoints_found"] += len(api_endpoints)

        return chunks

    def _classify_document(self, filename: str, content: str) -> str:
        """
        Classify document type based on filename and content

        Args:
            filename: Document filename
            content: Document content

        Returns:
            Document type classification
        """
        filename_lower = filename.lower()

        # Classification rules
        if "api" in content.lower() or "endpoint" in content.lower():
            if "pipeline" in filename_lower:
                return "api-pipeline"
            elif "source" in filename_lower:
                return "api-source"
            elif "sink" in filename_lower:
                return "api-sink"
            elif "transform" in filename_lower:
                return "api-transform"
            elif "models" in filename_lower:
                return "api-models"
            else:
                return "api-general"

        # Source-specific documentation
        source_keywords = ["okta", "syslog", "aws", "azure", "gcp", "splunk", "kafka"]
        for keyword in source_keywords:
            if keyword in filename_lower:
                return f"source-{keyword}"

        # Configuration guides
        if "setup" in filename_lower or "configuration" in filename_lower:
            return "configuration"

        # Overview and general docs
        if "overview" in filename_lower or "introduction" in filename_lower:
            return "overview"

        if "lua" in filename_lower:
            return "transform-lua"

        if "pipeline" in filename_lower and "creation" in filename_lower:
            return "guide-pipeline-creation"

        return "general"

    def _parse_sections(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse markdown into sections

        Args:
            content: Markdown content

        Returns:
            List of sections with headers and content
        """
        sections = []
        current_section = {"title": "", "level": 0, "content": ""}

        lines = content.split("\n")
        in_code_block = False

        for line in lines:
            # Track code blocks
            if line.strip().startswith("```"):
                in_code_block = not in_code_block

            # Check for headers (not in code blocks)
            if not in_code_block and line.startswith("#"):
                # Save previous section if it has content
                if current_section["content"].strip():
                    sections.append(current_section.copy())

                # Start new section
                level = len(line) - len(line.lstrip("#"))
                title = line.lstrip("#").strip()
                current_section = {
                    "title": title,
                    "level": level,
                    "content": ""
                }
            else:
                # Add line to current section
                current_section["content"] += line + "\n"

        # Add final section
        if current_section["content"].strip():
            sections.append(current_section)

        return sections

    def _extract_code_examples(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract code blocks from markdown

        Args:
            content: Markdown content

        Returns:
            List of code examples with language and content
        """
        code_pattern = r"```(\w+)?\n(.*?)```"
        matches = re.findall(code_pattern, content, re.DOTALL)

        examples = []
        for language, code in matches:
            if code.strip():
                examples.append({
                    "language": language or "text",
                    "code": code.strip()
                })

        return examples

    def _extract_api_endpoints(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract API endpoints from content

        Args:
            content: Document content

        Returns:
            List of API endpoints with method and path
        """
        # Match API endpoints like: GET /gateway/v1/pipeline
        endpoint_pattern = r"(GET|POST|PUT|PATCH|DELETE)\s+(/[^\s\n]+)"
        matches = re.findall(endpoint_pattern, content)

        endpoints = []
        for method, path in matches:
            endpoints.append({
                "method": method,
                "path": path
            })

        return endpoints

    def _create_chunk(
        self,
        file_path: Path,
        doc_type: str,
        section: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create document chunk with metadata

        Args:
            file_path: Source file path
            doc_type: Document type classification
            section: Section data

        Returns:
            Document chunk ready for RAG
        """
        content = f"# {section['title']}\n\n{section['content']}" if section['title'] else section['content']

        # Generate unique ID
        # SECURITY: MD5 used for content identification only, not cryptographic security
        chunk_id = hashlib.md5(
            f"{file_path.name}:{section['title']}:{content[:100]}".encode(),
            usedforsecurity=False  # Phase 5: Bandit fix - not used for security
        ).hexdigest()

        return {
            "id": chunk_id,
            "title": section['title'] or file_path.stem,
            "content": content.strip(),
            "source": file_path.name,
            "doc_type": doc_type,
            "section_level": section['level'],
            "created_at": datetime.now().isoformat(),
            "metadata": {
                "filename": file_path.name,
                "doc_type": doc_type,
                "section_title": section['title'],
                "section_level": section['level'],
                "char_count": len(content),
                "word_count": len(content.split())
            }
        }

    def _create_code_chunk(
        self,
        file_path: Path,
        doc_type: str,
        code_example: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create code example chunk

        Args:
            file_path: Source file path
            doc_type: Document type classification
            code_example: Code example data

        Returns:
            Code chunk ready for RAG
        """
        content = f"```{code_example['language']}\n{code_example['code']}\n```"

        # Generate unique ID
        # SECURITY: MD5 used for content identification only, not cryptographic security
        chunk_id = hashlib.md5(
            f"{file_path.name}:code:{code_example['code'][:50]}".encode(),
            usedforsecurity=False  # Phase 5: Bandit fix - not used for security
        ).hexdigest()

        return {
            "id": chunk_id,
            "title": f"Code Example from {file_path.stem}",
            "content": content,
            "source": file_path.name,
            "doc_type": f"{doc_type}-code",
            "section_level": 0,
            "created_at": datetime.now().isoformat(),
            "metadata": {
                "filename": file_path.name,
                "doc_type": doc_type,
                "content_type": "code",
                "language": code_example['language'],
                "char_count": len(content),
                "word_count": len(content.split())
            }
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get processing statistics

        Returns:
            Statistics dictionary
        """
        return self.statistics


class ObservoRAGIngester:
    """
    Ingest processed Observo documentation into RAG knowledge base
    """

    def __init__(self, rag_knowledge_base):
        """
        Initialize RAG ingester

        Args:
            rag_knowledge_base: RAGKnowledgeBase instance
        """
        self.rag = rag_knowledge_base
        self.statistics = {
            "chunks_ingested": 0,
            "chunks_failed": 0,
            "errors": []
        }

    async def ingest_chunks(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Ingest document chunks into RAG knowledge base

        Args:
            chunks: List of document chunks

        Returns:
            Ingestion statistics
        """
        if not self.rag.enabled:
            logger.warning("RAG knowledge base not enabled, skipping ingestion")
            return {
                "status": "skipped",
                "reason": "RAG not enabled",
                "chunks_processed": 0
            }

        logger.info(f"Starting ingestion of {len(chunks)} chunks")

        for chunk in chunks:
            try:
                # Add to RAG knowledge base
                await self._ingest_chunk(chunk)
                self.statistics["chunks_ingested"] += 1

                if self.statistics["chunks_ingested"] % 10 == 0:
                    logger.info(f"Ingested {self.statistics['chunks_ingested']}/{len(chunks)} chunks")

            except Exception as e:
                error_msg = f"Failed to ingest chunk {chunk.get('id', 'unknown')}: {e}"
                logger.error(error_msg)
                self.statistics["chunks_failed"] += 1
                self.statistics["errors"].append(error_msg)

        logger.info(f"[OK] Ingestion complete: {self.statistics['chunks_ingested']} chunks ingested")

        return {
            "status": "complete",
            "chunks_ingested": self.statistics["chunks_ingested"],
            "chunks_failed": self.statistics["chunks_failed"],
            "errors": self.statistics["errors"]
        }

    async def _ingest_chunk(self, chunk: Dict[str, Any]):
        """
        Ingest single chunk into RAG

        Args:
            chunk: Document chunk
        """
        # Add to knowledge base with metadata
        self.rag.add_document(
            content=chunk["content"],
            title=chunk["title"],
            source=chunk["source"],
            doc_type=chunk["doc_type"],
            metadata=chunk["metadata"]
        )

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get ingestion statistics

        Returns:
            Statistics dictionary
        """
        return self.statistics


class ObservoDocsManager:
    """
    High-level manager for Observo documentation processing and RAG ingestion
    """

    def __init__(self, docs_directory: str, rag_knowledge_base=None):
        """
        Initialize documentation manager

        Args:
            docs_directory: Path to Observo documentation
            rag_knowledge_base: Optional RAG knowledge base instance
        """
        self.processor = ObservoDocsProcessor(docs_directory)
        self.ingester = ObservoRAGIngester(rag_knowledge_base) if rag_knowledge_base else None

    async def process_and_ingest(self) -> Dict[str, Any]:
        """
        Process all documentation and ingest into RAG

        Returns:
            Combined statistics
        """
        # Process documentation
        logger.info("[ANALYZE] Processing Observo documentation...")
        chunks = self.processor.process_all_docs()

        processing_stats = self.processor.get_statistics()
        logger.info(f"[NOTE] Processed {processing_stats['files_processed']} files")
        logger.info(f"[NOTE] Created {processing_stats['chunks_created']} chunks")
        logger.info(f"[NOTE] Extracted {processing_stats['code_examples_extracted']} code examples")
        logger.info(f"[NOTE] Found {processing_stats['api_endpoints_found']} API endpoints")

        # Ingest into RAG if available
        ingestion_stats = {}
        if self.ingester:
            logger.info("[INGEST] Ingesting into RAG knowledge base...")
            ingestion_stats = await self.ingester.ingest_chunks(chunks)
        else:
            logger.warning("RAG knowledge base not available, skipping ingestion")
            ingestion_stats = {
                "status": "skipped",
                "reason": "No RAG knowledge base provided"
            }

        # Combined statistics
        return {
            "processing": processing_stats,
            "ingestion": ingestion_stats,
            "summary": {
                "files_processed": processing_stats["files_processed"],
                "chunks_created": processing_stats["chunks_created"],
                "chunks_ingested": ingestion_stats.get("chunks_ingested", 0),
                "code_examples": processing_stats["code_examples_extracted"],
                "api_endpoints": processing_stats["api_endpoints_found"],
                "errors": processing_stats["errors"] + ingestion_stats.get("errors", [])
            }
        }

    def get_document_summary(self) -> Dict[str, Any]:
        """
        Get summary of available documentation

        Returns:
            Documentation summary
        """
        docs_path = Path(self.processor.docs_directory)
        md_files = list(docs_path.glob("*.md"))

        summary = {
            "total_files": len(md_files),
            "files": [],
            "total_size_kb": 0
        }

        for md_file in md_files:
            size_kb = md_file.stat().st_size / 1024
            summary["files"].append({
                "name": md_file.name,
                "size_kb": round(size_kb, 2),
                "lines": len(md_file.read_text(encoding='utf-8').split('\n'))
            })
            summary["total_size_kb"] += size_kb

        summary["total_size_kb"] = round(summary["total_size_kb"], 2)
        summary["files"] = sorted(summary["files"], key=lambda x: x["size_kb"], reverse=True)

        return summary
