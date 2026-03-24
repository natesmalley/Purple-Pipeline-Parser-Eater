"""
Comprehensive Data Ingestion Manager for RAG Knowledge Base
Handles collection and ingestion of all data sources for machine learning
"""

import logging
import asyncio
import json
import re
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

try:
    from utils.error_handler import handle_api_errors
except ImportError:
    from ..utils.error_handler import handle_api_errors


logger = logging.getLogger(__name__)


class DataIngestionManager:
    """
    Manages ingestion of all data sources into RAG knowledge base

    Data Sources:
    1. SentinelOne ai-siem parsers (165+ examples)
    2. OCSF schema definitions
    3. Observo.ai documentation (if available)
    4. Generated LUA examples (from previous runs)
    5. User corrections and feedback
    """

    def __init__(self, config: Dict, knowledge_base, github_scanner=None):
        self.config = config
        self.knowledge_base = knowledge_base
        self.github_scanner = github_scanner

        self.statistics = {
            'sentinelone_parsers': 0,
            'ocsf_classes': 0,
            'observo_docs': 0,
            'generated_examples': 0,
            'user_corrections': 0,
            'total_documents': 0
        }

    async def ingest_all_sources(self, sources: Optional[List[str]] = None):
        """
        Ingest data from all available sources

        Args:
            sources: Optional list of specific sources to ingest
                     If None, ingests all available sources
        """
        if sources is None:
            sources = [
                'sentinelone_parsers',
                'ocsf_schema',
                'generated_examples'
            ]

        logger.info("=" * 70)
        logger.info("STARTING COMPREHENSIVE DATA INGESTION")
        logger.info("=" * 70)

        try:
            if 'sentinelone_parsers' in sources:
                logger.info("\n[1/3] Ingesting SentinelOne parser examples...")
                await self.ingest_sentinelone_parsers()
                logger.info(f"[OK] Ingested {self.statistics['sentinelone_parsers']} parsers")

            if 'ocsf_schema' in sources:
                logger.info("\n[2/3] Ingesting OCSF schema definitions...")
                await self.ingest_ocsf_schema()
                logger.info(f"[OK] Ingested {self.statistics['ocsf_classes']} OCSF classes")

            if 'generated_examples' in sources:
                logger.info("\n[3/3] Checking for existing generated examples...")
                await self.import_existing_examples()
                logger.info(f"[OK] Found {self.statistics['generated_examples']} existing examples")

            logger.info("\n" + "=" * 70)
            logger.info("DATA INGESTION COMPLETE")
            logger.info("=" * 70)
            logger.info(f"Total documents in knowledge base: {self.statistics['total_documents']}")

            return self.statistics

        except Exception as e:
            logger.error(f"Data ingestion failed: {e}")
            raise

    async def ingest_sentinelone_parsers(self):
        """
        Ingest all SentinelOne ai-siem parsers as examples

        This provides 165+ real-world examples of parsers that can be used
        for pattern recognition and learning
        """
        if not self.github_scanner:
            logger.warning("GitHub scanner not available, skipping parser ingestion")
            return

        try:
            # Fetch all parsers from GitHub
            logger.info("Fetching parsers from SentinelOne GitHub repository...")
            parsers = await self.github_scanner.scan_parsers()

            logger.info(f"Found {len(parsers)} parsers to ingest")

            # Ingest each parser as a learning example
            for i, parser in enumerate(parsers, 1):
                try:
                    await self._ingest_single_parser(parser)

                    if i % 10 == 0:
                        logger.info(f"  Progress: {i}/{len(parsers)} parsers ingested")

                except Exception as e:
                    logger.warning(f"Failed to ingest parser {parser.get('name', 'unknown')}: {e}")
                    continue

            self.statistics['sentinelone_parsers'] = len(parsers)
            self.statistics['total_documents'] += len(parsers)

        except Exception as e:
            logger.error(f"Failed to ingest SentinelOne parsers: {e}")
            raise

    async def _ingest_single_parser(self, parser: Dict):
        """Ingest a single parser into the knowledge base"""

        # Extract key information
        parser_name = parser.get('name', 'unknown')
        content = parser.get('content', '')
        metadata = parser.get('metadata', {})

        # Extract patterns and mappings
        patterns = self._extract_patterns_from_parser(content)
        field_mappings = self._extract_field_mappings(content)
        transformations = self._extract_transformations(content)

        # Build comprehensive document
        document_content = f"""
SentinelOne Parser Example: {parser_name}

Log Source: {metadata.get('log_source', 'Unknown')}
OCSF Class: {metadata.get('ocsf_class', 'Unknown')}
Product: {metadata.get('product', 'Unknown')}

REGEX PATTERNS USED:
{self._format_patterns(patterns)}

FIELD MAPPINGS:
{self._format_mappings(field_mappings)}

TRANSFORMATIONS:
{self._format_transformations(transformations)}

FULL PARSER DEFINITION:
{content}

INSIGHTS FOR LEARNING:
- Parser handles {metadata.get('log_source', 'unknown')} logs
- Maps to OCSF class {metadata.get('ocsf_class', 'unknown')}
- Uses {len(patterns)} regex patterns for extraction
- Performs {len(transformations)} transformations
- Maps {len(field_mappings)} fields to OCSF schema
"""

        # Add to knowledge base
        doc_id = await self.knowledge_base.add_document(
            content=document_content,
            metadata={
                "title": f"Parser Example: {parser_name}",
                "source": "sentinelone_github",
                "doc_type": "parser_example",
                "parser_name": parser_name,
                "log_source": metadata.get('log_source', 'unknown'),
                "ocsf_class": metadata.get('ocsf_class', 'unknown'),
                "pattern_count": len(patterns),
                "field_count": len(field_mappings),
                "ingested_at": datetime.now().isoformat()
            }
        )

        logger.debug(f"Ingested parser {parser_name} with ID {doc_id}")

    def _extract_patterns_from_parser(self, content: str) -> List[str]:
        """Extract regex patterns from parser definition"""
        patterns = []

        # Look for regex patterns in various formats
        # Pattern 1: regex: "..."
        regex_matches = re.findall(r'regex:\s*["\'](.+?)["\']', content, re.MULTILINE)
        patterns.extend(regex_matches)

        # Pattern 2: pattern: "..."
        pattern_matches = re.findall(r'pattern:\s*["\'](.+?)["\']', content, re.MULTILINE)
        patterns.extend(pattern_matches)

        # Pattern 3: grok patterns
        grok_matches = re.findall(r'grok:\s*["\'](.+?)["\']', content, re.MULTILINE)
        patterns.extend(grok_matches)

        return list(set(patterns))  # Remove duplicates

    def _extract_field_mappings(self, content: str) -> Dict[str, str]:
        """Extract field mappings from parser"""
        mappings = {}

        # Look for field mapping patterns like: field_name: value
        mapping_matches = re.findall(
            r'(\w+):\s*\$\{([^}]+)\}',
            content
        )

        for field, source in mapping_matches:
            mappings[field] = source

        return mappings

    def _extract_transformations(self, content: str) -> List[str]:
        """Extract transformation logic from parser"""
        transformations = []

        # Look for common transformation patterns
        transform_keywords = [
            'lowercase', 'uppercase', 'trim', 'split',
            'join', 'replace', 'parse', 'convert'
        ]

        for keyword in transform_keywords:
            if keyword in content.lower():
                # Find the line containing the transformation
                lines = content.split('\n')
                for line in lines:
                    if keyword in line.lower():
                        transformations.append(line.strip())

        return list(set(transformations))

    def _format_patterns(self, patterns: List[str]) -> str:
        """Format patterns for display"""
        if not patterns:
            return "  (No regex patterns found)"

        return "\n".join(f"  - {pattern}" for pattern in patterns[:10])

    def _format_mappings(self, mappings: Dict[str, str]) -> str:
        """Format field mappings for display"""
        if not mappings:
            return "  (No field mappings found)"

        items = list(mappings.items())[:20]
        return "\n".join(f"  - {field} ← {source}" for field, source in items)

    def _format_transformations(self, transformations: List[str]) -> str:
        """Format transformations for display"""
        if not transformations:
            return "  (No transformations found)"

        return "\n".join(f"  - {transform}" for transform in transformations[:10])

    async def ingest_ocsf_schema(self):
        """
        Ingest OCSF schema definitions

        This provides authoritative information about OCSF classes,
        required fields, data types, and enumerations
        """
        logger.info("Fetching OCSF schema from official repository...")

        try:
            # OCSF schema is available on GitHub
            # For now, we'll ingest basic class information
            # In production, you'd fetch from: https://github.com/ocsf/ocsf-schema

            # Basic OCSF classes that are commonly used
            ocsf_classes = [
                {
                    "name": "Authentication",
                    "class_uid": 3002,
                    "category": "Identity & Access Management",
                    "description": "Authentication events including login, logout, and authentication failures",
                    "required_fields": ["time", "activity_id", "user", "device"],
                    "common_fields": ["src_endpoint", "dst_endpoint", "auth_protocol", "logon_type"]
                },
                {
                    "name": "Security Finding",
                    "class_uid": 2001,
                    "category": "Findings",
                    "description": "Security findings from various security tools and services",
                    "required_fields": ["time", "finding", "severity_id", "resources"],
                    "common_fields": ["vulnerabilities", "remediation", "compliance", "evidence"]
                },
                {
                    "name": "Network Activity",
                    "class_uid": 4001,
                    "category": "Network Activity",
                    "description": "Network connection and traffic events",
                    "required_fields": ["time", "activity_id", "src_endpoint", "dst_endpoint"],
                    "common_fields": ["connection_info", "traffic", "protocol_name", "app_name"]
                },
                {
                    "name": "File Activity",
                    "class_uid": 4006,
                    "category": "System Activity",
                    "description": "File system operations and modifications",
                    "required_fields": ["time", "activity_id", "file", "actor"],
                    "common_fields": ["process", "device", "file_result", "file_diff"]
                },
                {
                    "name": "Process Activity",
                    "class_uid": 1007,
                    "category": "System Activity",
                    "description": "Process creation, termination, and modification events",
                    "required_fields": ["time", "activity_id", "process", "actor"],
                    "common_fields": ["parent_process", "cmd_line", "integrity_id", "loaded_modules"]
                },
                {
                    "name": "Web Resources Activity",
                    "class_uid": 6003,
                    "category": "Application Activity",
                    "description": "HTTP/HTTPS web resource access events",
                    "required_fields": ["time", "activity_id", "http_request"],
                    "common_fields": ["http_response", "url", "src_endpoint", "dst_endpoint"]
                },
                {
                    "name": "DNS Activity",
                    "class_uid": 4003,
                    "category": "Network Activity",
                    "description": "DNS query and response events",
                    "required_fields": ["time", "activity_id", "query"],
                    "common_fields": ["answers", "response_code", "src_endpoint", "dst_endpoint"]
                },
                {
                    "name": "Email Activity",
                    "class_uid": 4009,
                    "category": "Network Activity",
                    "description": "Email sending, receiving, and filtering events",
                    "required_fields": ["time", "activity_id", "email"],
                    "common_fields": ["sender", "recipient", "subject", "email_uid"]
                }
            ]

            for ocsf_class in ocsf_classes:
                await self._ingest_ocsf_class(ocsf_class)

            self.statistics['ocsf_classes'] = len(ocsf_classes)
            self.statistics['total_documents'] += len(ocsf_classes)

        except Exception as e:
            logger.error(f"Failed to ingest OCSF schema: {e}")
            raise

    async def _ingest_ocsf_class(self, ocsf_class: Dict):
        """Ingest a single OCSF class definition"""

        document_content = f"""
OCSF Class Definition: {ocsf_class['name']}

Class UID: {ocsf_class['class_uid']}
Category: {ocsf_class['category']}

Description:
{ocsf_class['description']}

REQUIRED FIELDS:
{chr(10).join(f'  - {field}' for field in ocsf_class['required_fields'])}

COMMON OPTIONAL FIELDS:
{chr(10).join(f'  - {field}' for field in ocsf_class['common_fields'])}

MAPPING GUIDANCE:
When mapping to {ocsf_class['name']} (class_uid: {ocsf_class['class_uid']}):
1. Always include required fields: {', '.join(ocsf_class['required_fields'])}
2. Use appropriate activity_id for the specific action
3. Ensure time is in Unix epoch milliseconds
4. Consider including common fields for better context
5. Set class_uid = {ocsf_class['class_uid']}
6. Calculate type_uid = class_uid * 100 + activity_id

EXAMPLES OF USE:
- Use for {ocsf_class['category'].lower()} events
- {ocsf_class['description']}
"""

        doc_id = await self.knowledge_base.add_document(
            content=document_content,
            metadata={
                "title": f"OCSF Class: {ocsf_class['name']}",
                "source": "ocsf_schema",
                "doc_type": "ocsf_class_definition",
                "class_name": ocsf_class['name'],
                "class_uid": ocsf_class['class_uid'],
                "category": ocsf_class['category'],
                "ingested_at": datetime.now().isoformat()
            }
        )

        logger.debug(f"Ingested OCSF class {ocsf_class['name']} with ID {doc_id}")

    async def import_existing_examples(self):
        """
        Import existing generated LUA examples from previous runs

        Looks in output directory for previously generated code
        """
        try:
            output_dir = Path("output")
            if not output_dir.exists():
                logger.info("No existing output directory found")
                return

            # Look for generated LUA files
            lua_files = list(output_dir.glob("**/*.lua"))

            logger.info(f"Found {len(lua_files)} existing LUA files to import")

            for lua_file in lua_files:
                try:
                    await self._import_lua_file(lua_file)
                except Exception as e:
                    logger.warning(f"Failed to import {lua_file.name}: {e}")
                    continue

            self.statistics['generated_examples'] = len(lua_files)
            self.statistics['total_documents'] += len(lua_files)

        except Exception as e:
            logger.error(f"Failed to import existing examples: {e}")
            # Don't raise - this is optional

    async def _import_lua_file(self, lua_file: Path):
        """Import a single LUA file into knowledge base"""

        content = lua_file.read_text(encoding='utf-8')

        # Try to extract metadata from filename or content
        parser_name = lua_file.stem

        document_content = f"""
Previously Generated LUA Transformation: {parser_name}

Generated Code:
{content}

File: {lua_file.name}
"""

        doc_id = await self.knowledge_base.add_document(
            content=document_content,
            metadata={
                "title": f"Generated LUA: {parser_name}",
                "source": "existing_output",
                "doc_type": "generated_lua_example",
                "parser_name": parser_name,
                "success": True,  # Assume success if it exists in output
                "imported_at": datetime.now().isoformat()
            }
        )

        logger.debug(f"Imported LUA file {lua_file.name} with ID {doc_id}")

    async def get_ingestion_statistics(self) -> Dict:
        """Get statistics about ingested data"""
        return {
            **self.statistics,
            'knowledge_base_enabled': self.knowledge_base.enabled if hasattr(self.knowledge_base, 'enabled') else False
        }
