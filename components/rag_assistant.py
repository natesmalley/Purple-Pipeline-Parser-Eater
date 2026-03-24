"""
Claude RAG Assistant for Purple Pipeline Parser Eater
Provides contextual assistance using RAG knowledge base
"""
import logging
from typing import Dict, Optional, List
from datetime import datetime
from anthropic import AsyncAnthropic

# Use absolute imports for proper module execution
try:
    from utils.error_handler import ClaudeAPIError, RateLimiter
except ImportError:
    from ..utils.error_handler import ClaudeAPIError, RateLimiter


logger = logging.getLogger(__name__)


class ClaudeRAGAssistant:
    """Contextual AI assistant using RAG for Observo.ai expertise"""

    def __init__(self, config: Dict, knowledge_base):
        self.config = config
        self.knowledge_base = knowledge_base

        anthropic_config = config.get("anthropic", {})
        self.api_key = anthropic_config.get("api_key")
        self.model = anthropic_config.get("model", "claude-3-5-sonnet-20241022")
        self.max_tokens = anthropic_config.get("max_tokens", 4000)
        self.temperature = anthropic_config.get("temperature", 0.1)

        self.client = AsyncAnthropic(api_key=self.api_key)
        self.rate_limiter = RateLimiter(
            calls_per_second=1.0 / anthropic_config.get("rate_limit_delay", 1.0)
        )

        self.contextual_assistance_prompt = """You are an expert Observo.ai pipeline engineer helping with SentinelOne parser conversion.

Relevant Context from Knowledge Base:
{retrieved_context}

User Query: {user_query}

Current Parser Information:
- Parser: {parser_name}
- Complexity: {complexity}
- OCSF Class: {ocsf_class}
- Data Volume: {expected_volume}

Provide expert assistance including:
1. Direct answer to the user's question
2. Specific code examples for Observo.ai LUA if relevant
3. Performance optimization recommendations
4. Common pitfalls to avoid
5. Monitoring and troubleshooting guidance
6. Cost optimization suggestions

Keep responses practical and focused on Observo.ai implementation details."""

        self.documentation_generation_prompt = """Generate comprehensive documentation for this Observo.ai pipeline:

Pipeline Configuration:
{pipeline_config}

Generated LUA Code:
{lua_code}

Parser Source Information:
{parser_metadata}

Context from Knowledge Base:
{knowledge_context}

Create professional technical documentation with these sections:

# {parser_name} Pipeline Documentation

## Overview
- Purpose and functionality
- Data source details
- OCSF classification

## Deployment Instructions
- Prerequisites and dependencies
- Configuration parameters
- Step-by-step deployment process

## Field Mapping Reference
- Complete source to target field mappings
- Data transformation logic
- Type conversions and validations

## Performance Characteristics
- Expected throughput and latency
- Resource requirements
- Scaling recommendations

## Monitoring and Alerting
- Key metrics to monitor
- Recommended alert thresholds
- Troubleshooting procedures

## Cost Optimization
- Resource usage estimates
- Optimization recommendations
- Cost monitoring setup

## Troubleshooting Guide
- Common issues and solutions
- Debugging procedures
- Performance tuning tips

## Testing
- Sample test cases
- Validation procedures
- Expected outputs

Format as professional Markdown with clear examples and code snippets."""

    async def get_contextual_help(
        self,
        query: str,
        parser_info: Optional[Dict] = None,
        context_filter: Optional[str] = None
    ) -> str:
        """
        Get contextual help using RAG and Claude
        """
        logger.info(f"[INFO] Getting contextual help for: {query[:50]}...")

        await self.rate_limiter.wait()

        try:
            # Retrieve relevant context from knowledge base
            retrieved_docs = self.knowledge_base.search_knowledge(
                query,
                top_k=3,
                doc_type_filter=context_filter
            )

            # Format retrieved context
            context_text = self._format_retrieved_context(retrieved_docs)

            # Extract parser information
            parser_name = parser_info.get("parser_id", "Unknown") if parser_info else "Unknown"
            complexity = "Unknown"
            ocsf_class = "Unknown"
            expected_volume = "Unknown"

            if parser_info:
                complexity = parser_info.get("parser_complexity", {}).get("level", "Unknown")
                ocsf_class = parser_info.get("ocsf_classification", {}).get("class_name", "Unknown")
                expected_volume = parser_info.get("performance_characteristics", {}).get("expected_volume", "Unknown")

            # Build prompt
            prompt = self.contextual_assistance_prompt.format(
                retrieved_context=context_text,
                user_query=query,
                parser_name=parser_name,
                complexity=complexity,
                ocsf_class=ocsf_class,
                expected_volume=expected_volume
            )

            # Call Claude
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )

            answer = response.content[0].text
            logger.info("[OK] Generated contextual help response")

            return answer

        except Exception as e:
            logger.error(f"Failed to generate contextual help: {e}")
            raise ClaudeAPIError(f"Contextual help failed: {e}")

    async def generate_pipeline_documentation(
        self,
        parser_name: str,
        pipeline_config: Dict,
        lua_code: str,
        parser_metadata: Dict
    ) -> str:
        """
        Generate comprehensive pipeline documentation
        """
        logger.info(f"[NOTE] Generating documentation for pipeline: {parser_name}")

        await self.rate_limiter.wait()

        try:
            # Get relevant documentation context
            doc_query = f"Documentation best practices for {parser_name} pipeline deployment and monitoring"
            knowledge_docs = self.knowledge_base.search_knowledge(doc_query, top_k=5)
            knowledge_context = self._format_retrieved_context(knowledge_docs)

            # Build prompt
            prompt = self.documentation_generation_prompt.format(
                parser_name=parser_name,
                pipeline_config=self._format_json(pipeline_config),
                lua_code=lua_code,
                parser_metadata=self._format_json(parser_metadata),
                knowledge_context=knowledge_context
            )

            # Call Claude
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )

            documentation = response.content[0].text
            logger.info(f"[OK] Generated documentation for {parser_name}")

            return documentation

        except Exception as e:
            logger.error(f"Failed to generate documentation: {e}")
            raise ClaudeAPIError(f"Documentation generation failed: {e}")

    def _format_retrieved_context(self, docs: List[Dict]) -> str:
        """Format retrieved documents into context string"""
        if not docs:
            return "No relevant context found in knowledge base."

        context_parts = []
        for i, doc in enumerate(docs, 1):
            context_parts.append(
                f"--- Document {i}: {doc.get('title', 'Untitled')} ---\n"
                f"Source: {doc.get('source', 'Unknown')}\n"
                f"Type: {doc.get('doc_type', 'Unknown')}\n"
                f"Relevance: {doc.get('similarity_score', 0):.2f}\n\n"
                f"{doc.get('content', '')}\n"
            )

        return "\n".join(context_parts)

    def _format_json(self, data: Dict) -> str:
        """Format dict as JSON string"""
        import json
        return json.dumps(data, indent=2)

    async def get_optimization_recommendations(
        self,
        parser_analysis: Dict,
        lua_code: str
    ) -> Dict:
        """
        Get specific optimization recommendations for a pipeline
        """
        logger.info(f"[SEARCH] Getting optimization recommendations for {parser_analysis.get('parser_id')}")

        query = f"""Analyze this LUA pipeline code for optimization opportunities:

Parser: {parser_analysis.get('parser_id')}
Complexity: {parser_analysis.get('parser_complexity', {}).get('level')}
Volume: {parser_analysis.get('performance_characteristics', {}).get('expected_volume')}

LUA Code:
{lua_code[:1000]}...

Provide specific optimization recommendations."""

        try:
            recommendations = await self.get_contextual_help(
                query,
                parser_info=parser_analysis,
                context_filter="performance"
            )

            return {
                "parser_id": parser_analysis.get('parser_id'),
                "recommendations": recommendations,
                "generated_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get optimization recommendations: {e}")
            return {
                "parser_id": parser_analysis.get('parser_id'),
                "recommendations": "Failed to generate recommendations",
                "error": str(e)
            }

    async def get_troubleshooting_guide(self, parser_name: str, error_context: str) -> str:
        """
        Generate troubleshooting guide for specific errors
        """
        query = f"""Generate troubleshooting guide for {parser_name} pipeline error:

Error Context:
{error_context}

Include:
1. Root cause analysis
2. Step-by-step debugging procedure
3. Common solutions
4. Prevention strategies"""

        try:
            return await self.get_contextual_help(query, context_filter="reliability")
        except Exception as e:
            logger.error(f"Failed to generate troubleshooting guide: {e}")
            return "Unable to generate troubleshooting guide"
