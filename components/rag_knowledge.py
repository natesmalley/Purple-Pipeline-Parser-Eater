"""
RAG Knowledge Base for Purple Pipeline Parser Eater
Vector database integration with Milvus for Observo.ai documentation
"""
import logging
import os
from typing import List, Dict, Optional, Tuple
import json
from datetime import datetime

try:
    from pymilvus import (
        connections,
        Collection,
        CollectionSchema,
        FieldSchema,
        DataType,
        utility
    )
    from sentence_transformers import SentenceTransformer
    MILVUS_AVAILABLE = True
except ImportError:
    MILVUS_AVAILABLE = False
    logging.warning("Milvus or sentence-transformers not available, RAG features disabled")


logger = logging.getLogger(__name__)


class RAGKnowledgeBase:
    """Vector database for Observo.ai knowledge and best practices"""

    def __init__(self, config: Dict):
        if not MILVUS_AVAILABLE:
            logger.warning("RAG Knowledge Base disabled: dependencies not installed")
            self.enabled = False
            return

        self.config = config
        milvus_config = config.get("milvus", {})

        # Override config with environment variables (for Docker compatibility)
        self.host = os.getenv('MILVUS_HOST', milvus_config.get("host", "localhost"))
        self.port = int(os.getenv('MILVUS_PORT', str(milvus_config.get("port", "19530"))))
        self.collection_name = milvus_config.get("collection_name", "observo_knowledge")

        logger.info(f"[CONFIG] Milvus connection: {self.host}:{self.port}")

        self.embedding_model = None
        self.collection = None
        self.enabled = False

        try:
            self._initialize_milvus()
            self._load_embedding_model()
            self.enabled = True
            logger.info("[OK] RAG Knowledge Base initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize RAG Knowledge Base: {e}")
            self.enabled = False

    def _initialize_milvus(self):
        """Initialize connection to Milvus vector database"""
        try:
            # Connect to Milvus
            connections.connect(
                alias="default",
                host=self.host,
                port=self.port
            )
            logger.info(f"Connected to Milvus at {self.host}:{self.port}")

            # Check if collection exists
            if utility.has_collection(self.collection_name):
                logger.info(f"Using existing collection: {self.collection_name}")
                self.collection = Collection(self.collection_name)
                self.collection.load()
            else:
                logger.info(f"Creating new collection: {self.collection_name}")
                self._create_collection()

        except Exception as e:
            logger.error(f"Milvus initialization failed: {e}")
            raise

    def _create_collection(self):
        """Create Milvus collection schema for Observo.ai knowledge"""
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=384),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=1000),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=500),
            FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="created_at", dtype=DataType.VARCHAR, max_length=100)
        ]

        schema = CollectionSchema(
            fields,
            description="Observo.ai knowledge base for parser conversion"
        )

        self.collection = Collection(self.collection_name, schema)

        # Create index for efficient similarity search
        index_params = {
            "metric_type": "L2",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128}
        }

        self.collection.create_index("embedding", index_params)
        self.collection.load()

        logger.info(f"Created and indexed collection: {self.collection_name}")

    def _load_embedding_model(self):
        """Load sentence transformer model for embeddings"""
        try:
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Loaded embedding model: all-MiniLM-L6-v2")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise

    def ingest_observo_documentation(self) -> bool:
        """Ingest Observo.ai documentation into vector database"""
        if not self.enabled:
            logger.warning("RAG not enabled, skipping documentation ingestion")
            return False

        logger.info("[INGEST] Ingesting Observo.ai documentation into knowledge base")

        # Comprehensive Observo.ai documentation
        observo_docs = [
            {
                "title": "LUA Performance Optimization in Observo.ai",
                "content": """LUA functions in Observo.ai must be optimized for high-volume processing.
                Use local variables exclusively as global variables cause 40-60% performance degradation.
                Implement string operations with string.format() for complex concatenations. Use table.insert()
                for array operations rather than indexed assignment in loops. Minimize table creation - reuse
                tables where possible. Implement proper error handling with pcall() for production reliability
                without throwing exceptions that halt processing.""",
                "source": "observo_performance_guide",
                "doc_type": "performance"
            },
            {
                "title": "OCSF Field Mapping Best Practices",
                "content": """When mapping to OCSF fields, ensure class_uid and category_uid are always integers.
                Use tonumber() for numeric field conversions with nil checking. Validate required OCSF fields before
                processing: class_uid (required), activity_id (required), time (required), and severity_id (recommended).
                Type_uid should be calculated as class_uid * 100 + activity_id. Always include category_name and
                class_name string fields for human readability. Handle missing fields gracefully with default values.""",
                "source": "ocsf_mapping_guide",
                "doc_type": "schema"
            },
            {
                "title": "High-Volume Processing Patterns",
                "content": """For processing high-volume security logs (10K+ events/sec), implement these patterns:
                1) Use early return for invalid data to avoid unnecessary processing. 2) Batch field operations to
                reduce table access overhead. 3) Implement circuit breaker patterns for external API calls with
                exponential backoff. 4) Monitor memory usage with collectgarbage("count") in long-running transformations.
                5) Use proper logging levels - ERROR for failures, WARN for recoverable issues, INFO for significant events.
                6) Avoid regex in hot paths - use string matching functions instead.""",
                "source": "high_volume_guide",
                "doc_type": "architecture"
            },
            {
                "title": "Error Handling and Resilience",
                "content": """Robust error handling in Observo.ai pipelines requires multiple strategies. Never use
                error() or assert() as they halt processing. Instead return nil with descriptive error message as
                second return value. Implement input validation at function entry with type checks. Use pcall() to
                wrap risky operations like external calls or complex parsing. Log errors with context including
                parser_id and timestamp. Implement fallback values for optional fields. Track error rates and alert
                when they exceed thresholds (>1% typically indicates issues).""",
                "source": "error_handling_guide",
                "doc_type": "reliability"
            },
            {
                "title": "Memory Management in LUA Transformations",
                "content": """LUA memory management is critical for production deployments. Avoid creating temporary
                tables in loops - preallocate or reuse. String concatenation creates temporary strings, use table-based
                buffering for building large strings. Monitor memory with collectgarbage("count") and trigger collection
                when memory exceeds thresholds. Typical memory per event should be 2-8KB. Optimize by using string.sub()
                instead of creating substrings. Clear large tables after use by setting to nil. Avoid closures in hot
                paths as they capture environment and increase memory usage.""",
                "source": "memory_management_guide",
                "doc_type": "performance"
            },
            {
                "title": "OCSF Schema Compliance Requirements",
                "content": """OCSF compliance requires strict adherence to field types and naming conventions. All events
                must have: class_uid (integer), category_uid (integer), activity_id (integer), time (integer timestamp
                in milliseconds), severity_id (integer 0-6). Optional but recommended: type_uid, message, status, metadata.
                Use snake_case for all field names. Nested objects use dot notation (user.name, device.ip). Arrays must be
                homogeneous type. Enumerations must use OCSF-defined values. Include unmapped fields in 'unmapped' object
                for debugging. Add observo_metadata object with pipeline info, transformation timestamp, and version.""",
                "source": "ocsf_compliance_guide",
                "doc_type": "schema"
            },
            {
                "title": "Testing and Validation Strategies",
                "content": """Comprehensive testing for Observo.ai pipelines includes: 1) Unit tests with sample events
                covering all field mapping paths. 2) Performance tests with 10K events to measure throughput. 3) Error
                case testing with malformed, missing, and null fields. 4) Edge case testing with boundary values, special
                characters, very long strings. 5) Integration testing with real data samples. 6) Regression testing after
                modifications. Use assert-style checks for output validation. Measure memory usage per event. Monitor
                transformation latency (target <1ms per event). Validate OCSF schema compliance with automated checkers.""",
                "source": "testing_guide",
                "doc_type": "quality"
            },
            {
                "title": "Deployment and Monitoring Best Practices",
                "content": """Deploy Observo.ai pipelines with progressive rollout: 1) Test in staging with production data
                sample. 2) Deploy to 10% of traffic initially. 3) Monitor error rates, latency, throughput for 24 hours.
                4) Gradually increase to 100% over 3-5 days. Monitor these metrics: transformation_errors (alert >1%),
                processing_latency_p99 (alert >10ms), events_processed_per_sec (track trends), memory_usage_mb (alert >500MB),
                cpu_utilization (alert >70%). Implement health checks that validate sample transformations. Set up alerts
                for schema validation failures. Maintain runbooks for common failure scenarios.""",
                "source": "deployment_guide",
                "doc_type": "operations"
            },
            {
                "title": "Cost Optimization Techniques",
                "content": """Optimize Observo.ai costs through efficient resource usage: 1) Right-size compute resources based
                on actual throughput needs (measure during testing). 2) Use batch processing for non-real-time pipelines to
                reduce overhead. 3) Implement sampling for high-volume, low-value logs (keep 10-20%). 4) Filter unnecessary
                fields early in pipeline to reduce downstream processing. 5) Compress data in storage layer. 6) Use cold storage
                for logs older than 90 days. 7) Monitor per-pipeline costs and optimize highest-cost pipelines first. Typical
                costs: $0.001-0.003 per GB ingested, $0.10-0.20 per GB stored per month.""",
                "source": "cost_optimization_guide",
                "doc_type": "operations"
            },
            {
                "title": "Data Type Conversions and Casting",
                "content": """Handle data type conversions safely in LUA: Use tonumber(value) with nil checks for numeric
                conversions. Convert timestamps with proper epoch handling (milliseconds for OCSF). Boolean conversions: treat
                "true", "1", 1, true as true; everything else as false. String conversions: use tostring() but check for nil
                first. Array/table conversions: validate structure before processing. Handle ISO8601 timestamps by converting
                to Unix epoch in milliseconds. IP addresses: validate format before assignment. Enum values: map to OCSF integer
                enumerations with lookup tables. Always provide fallback values for failed conversions.""",
                "source": "data_types_guide",
                "doc_type": "development"
            }
        ]

        try:
            # Generate embeddings and insert documents
            for doc in observo_docs:
                embedding = self.embedding_model.encode(doc["content"]).tolist()

                self.collection.insert([
                    [embedding],
                    [doc["content"]],
                    [doc["title"]],
                    [doc["source"]],
                    [doc["doc_type"]],
                    [datetime.now().isoformat()]
                ])

            self.collection.flush()
            logger.info(f"[OK] Ingested {len(observo_docs)} documentation items")
            return True

        except Exception as e:
            logger.error(f"Failed to ingest documentation: {e}")
            return False

    def search_knowledge(
        self,
        query: str,
        top_k: int = 3,
        doc_type_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Search knowledge base for relevant information
        Returns list of relevant documents with similarity scores
        """
        if not self.enabled:
            logger.warning("RAG not enabled")
            return []

        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode(query).tolist()

            # Build search parameters
            search_params = {"metric_type": "L2", "params": {"nprobe": 10}}

            # Build filter expression
            expr = None
            if doc_type_filter:
                expr = f'doc_type == "{doc_type_filter}"'

            # Search collection
            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=["content", "title", "source", "doc_type", "created_at"]
            )

            # Format results
            formatted_results = []
            for hits in results:
                for hit in hits:
                    formatted_results.append({
                        "content": hit.entity.get("content"),
                        "title": hit.entity.get("title"),
                        "source": hit.entity.get("source"),
                        "doc_type": hit.entity.get("doc_type"),
                        "similarity_score": 1.0 / (1.0 + hit.distance),  # Convert distance to similarity
                        "created_at": hit.entity.get("created_at")
                    })

            logger.debug(f"Found {len(formatted_results)} relevant documents for query")
            return formatted_results

        except Exception as e:
            logger.error(f"Knowledge search failed: {e}")
            return []

    def get_parser_recommendations(self, parser_analysis: Dict) -> List[Dict]:
        """Get recommendations based on parser characteristics"""
        if not self.enabled:
            return []

        # Build query from parser analysis
        complexity = parser_analysis.get("parser_complexity", {}).get("level", "Medium")
        volume = parser_analysis.get("performance_characteristics", {}).get("expected_volume", "Medium")

        query = f"""Optimize {complexity} complexity parser for {volume} volume processing
        with OCSF field mappings and error handling"""

        return self.search_knowledge(query, top_k=5)

    def cleanup(self):
        """Clean up connections"""
        if self.enabled and self.collection:
            try:
                self.collection.release()
                connections.disconnect("default")
                logger.info("RAG Knowledge Base connections closed")
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
