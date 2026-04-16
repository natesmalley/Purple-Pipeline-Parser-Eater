"""
Claude Parser Analyzer for Purple Pipeline Parser Eater
Uses Claude AI for semantic analysis of SentinelOne parsers
"""
import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date
from anthropic import Anthropic, AsyncAnthropic
from dataclasses import dataclass, asdict

# Use absolute imports for proper module execution
try:
    from utils.error_handler import ClaudeAPIError, RateLimiter, safe_json_parse
    from components.rate_limiter import TokenBucket, AdaptiveBatchSizer
except ImportError:
    from ..utils.error_handler import ClaudeAPIError, RateLimiter, safe_json_parse
    from .rate_limiter import TokenBucket, AdaptiveBatchSizer


logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that converts date and datetime objects to ISO 8601 strings.

    This encoder is required because parser metadata from marketplace parsers
    contains Python datetime objects (created_at, updated_at, published_date)
    that are not natively JSON-serializable.

    Usage:
        json.dumps(data, cls=DateTimeEncoder)
    """

    def default(self, obj: Any) -> Any:
        """
        Override default JSON serialization for datetime objects.

        Args:
            obj: Object to serialize

        Returns:
            ISO 8601 string for datetime/date objects, default serialization otherwise
        """
        if isinstance(obj, datetime):
            return obj.isoformat()  # e.g., "2025-10-13T18:22:12.713811Z"
        if isinstance(obj, date):
            return obj.isoformat()  # e.g., "2025-10-13"
        return super().default(obj)


@dataclass
class ParserAnalysis:
    """Structured parser analysis results"""
    parser_id: str
    semantic_summary: str
    parser_complexity: Dict
    field_mappings: Dict
    ocsf_classification: Dict
    data_source_analysis: Dict
    optimization_opportunities: List[str]
    performance_characteristics: Dict
    overall_confidence: float
    analyzed_at: str
    raw_response: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)


class ClaudeParserAnalyzer:
    """Analyze SentinelOne parsers using Claude AI for semantic understanding"""

    def __init__(self, config: Dict):
        self.config = config
        anthropic_config = config.get("anthropic", {})

        self.api_key = anthropic_config.get("api_key")
        if not self.api_key or self.api_key == "your-anthropic-api-key-here":
            raise ClaudeAPIError("Anthropic API key not configured")

        self.model = anthropic_config.get("model", "claude-sonnet-4-6")
        self.max_tokens = anthropic_config.get("max_tokens", 4000)
        self.temperature = anthropic_config.get("temperature", 0.1)

        self.client = AsyncAnthropic(api_key=self.api_key)
        self.rate_limiter = RateLimiter(
            calls_per_second=1.0 / anthropic_config.get("rate_limit_delay", 1.0)
        )

        # Add token bucket rate limiter
        self.token_bucket = TokenBucket(
            output_tokens_per_minute=8000,  # Anthropic limit
            input_tokens_per_minute=50000,   # Conservative input limit
            window_seconds=60
        )

        # Add adaptive batch sizer
        self.batch_sizer = AdaptiveBatchSizer(
            initial_batch_size=5,  # Start conservative
            min_batch_size=1,
            max_batch_size=10,
            tokens_per_minute=8000
        )

        self.analysis_prompt_template = """Analyze the following SentinelOne parser configuration and provide detailed semantic analysis:

Parser ID: {parser_id}
Source Type: {source_type}

Parser Configuration:
{parser_config}

Metadata:
{metadata}

OCSF Context: This parser maps to OCSF (Open Cybersecurity Schema Framework) fields for standardized security event representation.

Please provide analysis in this EXACT JSON structure:
{{
  "semantic_summary": "Detailed description of what this parser processes and its security purpose",
  "parser_complexity": {{
    "level": "Low|Medium|High",
    "factors": ["list", "of", "complexity", "factors"],
    "confidence": 0.85
  }},
  "field_mappings": {{
    "source_field_1": {{
      "target_ocsf_field": "class_uid",
      "transformation_type": "constant|copy|cast|regex",
      "confidence": 0.90
    }}
  }},
  "ocsf_classification": {{
    "class_uid": 3002,
    "class_name": "Authentication",
    "category_uid": 3,
    "category_name": "Identity & Access Management",
    "confidence": 0.95
  }},
  "data_source_analysis": {{
    "vendor": "Cisco",
    "product": "Duo Security",
    "log_format": "JSON",
    "ingestion_method": "API|Syslog|File"
  }},
  "optimization_opportunities": [
    "Combine similar field operations",
    "Optimize regex patterns for performance",
    "Add error handling for missing fields"
  ],
  "performance_characteristics": {{
    "expected_volume": "Low|Medium|High",
    "processing_complexity": "Simple|Moderate|Complex",
    "resource_requirements": "Minimal|Standard|High"
  }},
  "overall_confidence": 0.88
}}

Be thorough in your analysis and ensure all confidence scores are realistic based on the parser complexity and clarity.
Respond with ONLY the JSON object, no additional text."""

        self.statistics = {
            "total_analyzed": 0,
            "successful": 0,
            "failed": 0,
            "total_tokens_used": 0,
            "errors": []
        }

    async def analyze_parser(self, parser: Dict) -> Optional[ParserAnalysis]:
        """
        Analyze a single parser configuration using Claude
        Returns ParserAnalysis object or None if analysis fails
        """
        parser_id = parser.get("parser_id", "unknown")
        logger.info(f"[ANALYZE] Analyzing parser: {parser_id}")

        await self.rate_limiter.wait()

        try:
            # Prepare the prompt
            prompt = self._prepare_analysis_prompt(parser)

            # Call Claude API
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Extract response text
            response_text = response.content[0].text

            # Track token usage
            self.statistics["total_tokens_used"] += response.usage.input_tokens + response.usage.output_tokens
            logger.debug(f"Tokens used: {response.usage.input_tokens} input, {response.usage.output_tokens} output")

            # Record token usage in token bucket
            self.token_bucket.record_usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens
            )

            # Parse JSON response
            analysis_data = self._parse_analysis_response(response_text, parser_id)
            if not analysis_data:
                logger.error(f"Failed to parse analysis for {parser_id}")
                self.statistics["failed"] += 1
                return None

            # Create ParserAnalysis object
            analysis = ParserAnalysis(
                parser_id=parser_id,
                semantic_summary=analysis_data.get("semantic_summary", ""),
                parser_complexity=analysis_data.get("parser_complexity", {}),
                field_mappings=analysis_data.get("field_mappings", {}),
                ocsf_classification=analysis_data.get("ocsf_classification", {}),
                data_source_analysis=analysis_data.get("data_source_analysis", {}),
                optimization_opportunities=analysis_data.get("optimization_opportunities", []),
                performance_characteristics=analysis_data.get("performance_characteristics", {}),
                overall_confidence=analysis_data.get("overall_confidence", 0.5),
                analyzed_at=datetime.now().isoformat(),
                raw_response=response_text
            )

            self.statistics["successful"] += 1
            self.statistics["total_analyzed"] += 1
            logger.info(f"[OK] Successfully analyzed {parser_id} (confidence: {analysis.overall_confidence:.2f})")

            return analysis

        except Exception as e:
            logger.error(f"Failed to analyze parser {parser_id}: {e}")
            self.statistics["failed"] += 1
            self.statistics["errors"].append(f"{parser_id}: {str(e)}")
            raise ClaudeAPIError(f"Analysis failed for {parser_id}: {e}")

    def _prepare_analysis_prompt(self, parser: Dict) -> str:
        """Prepare the analysis prompt from parser data"""
        parser_config = json.dumps(parser.get("config", {}), indent=2, cls=DateTimeEncoder)
        metadata = json.dumps(parser.get("metadata", {}), indent=2, cls=DateTimeEncoder)

        return self.analysis_prompt_template.format(
            parser_id=parser.get("parser_id", "unknown"),
            source_type=parser.get("source_type", "unknown"),
            parser_config=parser_config,
            metadata=metadata
        )

    def _parse_analysis_response(self, response_text: str, parser_id: str) -> Optional[Dict]:
        """Parse Claude's JSON response"""
        try:
            # Try to extract JSON from response
            response_text = response_text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1]) if len(lines) > 2 else response_text
                response_text = response_text.replace("```json", "").replace("```", "").strip()

            analysis_data = json.loads(response_text)

            # Validate required fields
            required_fields = [
                "semantic_summary",
                "parser_complexity",
                "ocsf_classification",
                "overall_confidence"
            ]

            for field in required_fields:
                if field not in analysis_data:
                    logger.warning(f"Missing required field '{field}' in analysis for {parser_id}")
                    return None

            return analysis_data

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for {parser_id}: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing response for {parser_id}: {e}")
            return None

    async def batch_analyze_parsers(
        self,
        parsers: List[Dict],
        batch_size: int = 5,
        max_concurrent: int = 3
    ) -> List[ParserAnalysis]:
        """
        Analyze multiple parsers in batches with adaptive rate limiting and concurrency control
        """
        logger.info(f"[STATS] Starting batch analysis of {len(parsers)} parsers")
        all_analyses = []

        parser_index = 0
        total_parsers = len(parsers)

        while parser_index < total_parsers:
            # Get recommended batch size based on available tokens
            _, output_available = self.token_bucket.tokens_available()
            adaptive_batch_size = self.batch_sizer.get_batch_size(output_available)

            # Get actual batch
            batch = parsers[parser_index:parser_index + adaptive_batch_size]
            batch_num = (parser_index // adaptive_batch_size) + 1
            logger.info(f"Processing batch {batch_num} with {len(batch)} parsers (adaptive sizing)")

            # Estimate tokens for this batch
            estimated_input_per_parser = 400
            estimated_output_per_parser = 1200
            total_estimated_output = estimated_output_per_parser * len(batch)

            # Wait for tokens if necessary
            await self.token_bucket.wait_for_tokens(
                estimated_input=estimated_input_per_parser * len(batch),
                estimated_output=total_estimated_output
            )

            # Create tasks with semaphore for concurrency control
            semaphore = asyncio.Semaphore(max_concurrent)

            async def analyze_with_semaphore(parser):
                async with semaphore:
                    try:
                        return await self.analyze_parser(parser)
                    except Exception as e:
                        logger.error(f"Batch analysis error for {parser.get('parser_id')}: {e}")
                        return None

            # Execute batch
            batch_tasks = [analyze_with_semaphore(p) for p in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Collect successful analyses and track batch success
            batch_success_count = 0
            for result in batch_results:
                if isinstance(result, ParserAnalysis):
                    all_analyses.append(result)
                    batch_success_count += 1
                elif isinstance(result, Exception):
                    logger.error(f"Batch analysis exception: {result}")

            # Record batch success/failure for adaptive sizing
            if batch_success_count == len(batch):
                self.batch_sizer.record_success()
            elif batch_success_count < len(batch) / 2:
                self.batch_sizer.record_failure()

            parser_index += len(batch)

        logger.info(f"[OK] Batch analysis complete: {len(all_analyses)}/{len(parsers)} successful")
        return all_analyses

    def get_statistics(self) -> Dict:
        """Get analyzer statistics"""
        return {
            **self.statistics,
            "success_rate": (
                self.statistics["successful"] / self.statistics["total_analyzed"]
                if self.statistics["total_analyzed"] > 0 else 0
            )
        }

    async def analyze_with_retry(self, parser: Dict, max_retries: int = 3) -> Optional[ParserAnalysis]:
        """Analyze parser with retry logic"""
        for attempt in range(max_retries):
            try:
                return await self.analyze_parser(parser)
            except ClaudeAPIError as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Retry {attempt + 1}/{max_retries} for {parser.get('parser_id')} after {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Failed after {max_retries} attempts: {parser.get('parser_id')}")
                    return None
        return None
