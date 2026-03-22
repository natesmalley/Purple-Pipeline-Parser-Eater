"""
Claude LUA Generator for Purple Pipeline Parser Eater
Generates optimized LUA transformation code for Observo.ai
"""
import asyncio
import json
import logging
from typing import Dict, Optional, List
from datetime import datetime
from anthropic import AsyncAnthropic
from dataclasses import dataclass

# Use absolute imports for proper module execution
try:
    from utils.error_handler import LuaGenerationError, RateLimiter, validate_lua_code
    from components.rate_limiter import TokenBucket, AdaptiveBatchSizer
    from components.claude_analyzer import DateTimeEncoder
except ImportError:
    from ..utils.error_handler import LuaGenerationError, RateLimiter, validate_lua_code
    from .rate_limiter import TokenBucket, AdaptiveBatchSizer
    from .claude_analyzer import DateTimeEncoder


logger = logging.getLogger(__name__)


@dataclass
class LuaGenerationResult:
    """Result of LUA code generation"""
    parser_id: str
    lua_code: str
    test_cases: str
    performance_metrics: Dict
    memory_analysis: str
    deployment_notes: str
    monitoring_recommendations: List[str]
    generated_at: str
    confidence_score: float

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "parser_id": self.parser_id,
            "lua_code": self.lua_code,
            "test_cases": self.test_cases,
            "performance_metrics": self.performance_metrics,
            "memory_analysis": self.memory_analysis,
            "deployment_notes": self.deployment_notes,
            "monitoring_recommendations": self.monitoring_recommendations,
            "generated_at": self.generated_at,
            "confidence_score": self.confidence_score
        }


class ClaudeLuaGenerator:
    """Generate optimized LUA transformation functions for Observo.ai"""

    def __init__(self, config: Dict):
        self.config = config
        anthropic_config = config.get("anthropic", {})

        self.api_key = anthropic_config.get("api_key")
        self.model = anthropic_config.get("model", "claude-3-5-sonnet-20241022")
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

        self.lua_generation_prompt_template = """Generate an optimized LUA transformation function for Observo.ai based on this parser analysis:

Parser ID: {parser_id}
Parser Analysis:
{parser_analysis}

Field Mappings:
{field_mappings}

OCSF Target Schema Context:
{ocsf_schema}

Requirements for LUA Generation:
1. HIGH PERFORMANCE: Optimize for processing 10,000+ events per second
2. MEMORY EFFICIENT: Use local variables, avoid global state, minimize allocations
3. ERROR HANDLING: Comprehensive validation and error recovery
4. OCSF COMPLIANCE: Ensure all field mappings follow OCSF schema
5. OBSERVO OPTIMIZATION: Use Observo.ai best practices for LUA functions

Generate complete LUA code in this structure:

```lua
-- SentinelOne Parser: {parser_name}
-- OCSF Class: {ocsf_class} ({class_uid})
-- Performance Level: High-volume optimized
-- Generated: {timestamp}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output structure
    local output = {{
        class_uid = {class_uid},
        class_name = "{class_name}",
        category_uid = {category_uid},
        category_name = "{category_name}",
        activity_id = 1,
        type_uid = {type_uid}
    }}

    -- Performance-optimized field transformations
    {field_transformations}

    -- Validation and cleanup
    {validation_logic}

    return output
end

-- Performance optimizations applied:
-- 1. Local variables for 15% performance improvement
-- 2. Early validation reduces processing overhead
-- 3. Efficient string operations minimize memory allocation
-- 4. Batch field assignments reduce table operations

-- Test cases:
{test_cases}
```

After the LUA code, provide in JSON format:

{{
  "performance_metrics": {{
    "estimated_throughput": "10000+ events/sec",
    "memory_per_event": "2-4 KB",
    "cpu_complexity": "O(n)"
  }},
  "memory_analysis": "Detailed memory usage breakdown",
  "deployment_notes": "Step-by-step deployment instructions",
  "monitoring_recommendations": [
    "Monitor transformation errors",
    "Track processing latency",
    "Alert on field mapping failures"
  ],
  "test_cases": "Comprehensive test scenarios"
}}

Include these specific optimizations:
- Use local variables exclusively for better performance
- Implement efficient string handling with string.format where appropriate
- Add proper error handling that doesn't throw exceptions
- Include input validation that handles malformed data gracefully
- Optimize for Observo.ai's LUA runtime environment
- Add comprehensive inline documentation

Respond with the complete LUA code first, followed by the JSON metrics."""

        self.statistics = {
            "total_generated": 0,
            "successful": 0,
            "failed": 0,
            "total_tokens_used": 0,
            "errors": []
        }

    async def generate_lua(
        self,
        parser_id: str,
        parser_analysis: Dict,
        ocsf_schema: Optional[Dict] = None
    ) -> Optional[LuaGenerationResult]:
        """
        Generate optimized LUA transformation code
        """
        logger.info(f"[INIT]  Generating LUA code for parser: {parser_id}")

        await self.rate_limiter.wait()

        try:
            # Prepare generation prompt
            prompt = self._prepare_generation_prompt(parser_id, parser_analysis, ocsf_schema)

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

            # Extract response
            response_text = response.content[0].text

            # Track token usage
            self.statistics["total_tokens_used"] += response.usage.input_tokens + response.usage.output_tokens

            # Record token usage in token bucket
            self.token_bucket.record_usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens
            )

            # Parse LUA code and metrics
            lua_result = self._parse_lua_response(response_text, parser_id, parser_analysis)
            if not lua_result:
                logger.error(f"Failed to parse LUA generation for {parser_id}")
                self.statistics["failed"] += 1
                return None

            # Validate generated LUA
            if not validate_lua_code(lua_result.lua_code):
                logger.error(f"Generated LUA code validation failed for {parser_id}")
                self.statistics["failed"] += 1
                return None

            self.statistics["successful"] += 1
            self.statistics["total_generated"] += 1
            logger.info(f"[OK] Successfully generated LUA for {parser_id}")

            return lua_result

        except Exception as e:
            logger.error(f"Failed to generate LUA for {parser_id}: {e}")
            self.statistics["failed"] += 1
            self.statistics["errors"].append(f"{parser_id}: {str(e)}")
            raise LuaGenerationError(f"LUA generation failed for {parser_id}: {e}")

    def _prepare_generation_prompt(
        self,
        parser_id: str,
        parser_analysis: Dict,
        ocsf_schema: Optional[Dict]
    ) -> str:
        """Prepare the LUA generation prompt"""

        # Extract OCSF classification
        ocsf_class = parser_analysis.get("ocsf_classification", {})
        class_uid = ocsf_class.get("class_uid", 0)
        class_name = ocsf_class.get("class_name", "Unknown")
        category_uid = ocsf_class.get("category_uid", 0)
        category_name = ocsf_class.get("category_name", "Unknown")

        # Calculate type_uid (class_uid * 100 + activity_id)
        type_uid = class_uid * 100 + 1

        # Format field mappings with DateTimeEncoder
        field_mappings = json.dumps(
            parser_analysis.get("field_mappings", {}),
            indent=2,
            cls=DateTimeEncoder
        )

        # Format OCSF schema with DateTimeEncoder
        ocsf_schema_str = json.dumps(ocsf_schema or {}, indent=2, cls=DateTimeEncoder)

        # Generate field transformation code
        field_transformations = self._generate_field_transformations(
            parser_analysis.get("field_mappings", {})
        )

        # Generate validation logic
        validation_logic = self._generate_validation_logic(ocsf_class)

        # Generate test cases
        test_cases = self._generate_test_cases(parser_id, parser_analysis)

        return self.lua_generation_prompt_template.format(
            parser_id=parser_id,
            parser_name=parser_id,
            parser_analysis=json.dumps(parser_analysis, indent=2, cls=DateTimeEncoder),
            field_mappings=field_mappings,
            ocsf_schema=ocsf_schema_str,
            ocsf_class=class_name,
            class_uid=class_uid,
            class_name=class_name,
            category_uid=category_uid,
            category_name=category_name,
            type_uid=type_uid,
            field_transformations=field_transformations,
            validation_logic=validation_logic,
            test_cases=test_cases,
            timestamp=datetime.now().isoformat()
        )

    def _generate_field_transformations(self, field_mappings: Dict) -> str:
        """Generate LUA code for field transformations"""
        transformations = []

        for source_field, mapping in field_mappings.items():
            target_field = mapping.get("target_ocsf_field", "")
            transform_type = mapping.get("transformation_type", "copy")

            if transform_type == "copy":
                transformations.append(
                    f"    -- Copy {source_field} to {target_field}\n"
                    f"    if record.{source_field} then\n"
                    f"        output.{target_field} = record.{source_field}\n"
                    f"    end\n"
                )
            elif transform_type == "constant":
                value = mapping.get("value", "")
                transformations.append(
                    f"    output.{target_field} = {json.dumps(value)}\n"
                )
            elif transform_type == "cast":
                transformations.append(
                    f"    -- Cast {source_field} to number for {target_field}\n"
                    f"    if record.{source_field} then\n"
                    f"        output.{target_field} = tonumber(record.{source_field})\n"
                    f"    end\n"
                )

        return "\n".join(transformations) if transformations else "    -- No field transformations specified"

    def _generate_validation_logic(self, ocsf_class: Dict) -> str:
        """Generate LUA validation logic"""
        return """    -- Validate required OCSF fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    -- Add timestamp if not present
    if not output.time then
        output.time = os.time() * 1000
    end"""

    def _generate_test_cases(self, parser_id: str, parser_analysis: Dict) -> str:
        """Generate test cases for LUA function"""
        return f"""-- Test Case 1: Valid input
local test1 = transform({{field1 = "value1", field2 = "value2"}})
-- Expected: Valid OCSF output with class_uid = {parser_analysis.get('ocsf_classification', {}).get('class_uid', 0)}

-- Test Case 2: Malformed input
local test2 = transform(nil)
-- Expected: nil, "Invalid input record"

-- Test Case 3: Empty record
local test3 = transform({{}})
-- Expected: Valid output with defaults"""

    def _parse_lua_response(
        self,
        response_text: str,
        parser_id: str,
        parser_analysis: Dict
    ) -> Optional[LuaGenerationResult]:
        """Parse Claude's LUA generation response"""
        try:
            # Extract LUA code
            lua_code = ""
            if "```lua" in response_text:
                parts = response_text.split("```lua")
                if len(parts) > 1:
                    lua_code = parts[1].split("```")[0].strip()
            else:
                # Fallback: look for function transform
                if "function transform" in response_text:
                    lua_code = response_text.strip()

            if not lua_code:
                logger.error(f"No LUA code found in response for {parser_id}")
                return None

            # Try to extract JSON metrics
            metrics = self._extract_metrics_from_response(response_text)

            # Create result
            result = LuaGenerationResult(
                parser_id=parser_id,
                lua_code=lua_code,
                test_cases=metrics.get("test_cases", "No test cases provided"),
                performance_metrics=metrics.get("performance_metrics", {}),
                memory_analysis=metrics.get("memory_analysis", "Not provided"),
                deployment_notes=metrics.get("deployment_notes", "Standard deployment"),
                monitoring_recommendations=metrics.get("monitoring_recommendations", []),
                generated_at=datetime.now().isoformat(),
                confidence_score=parser_analysis.get("overall_confidence", 0.5)
            )

            return result

        except Exception as e:
            logger.error(f"Failed to parse LUA response for {parser_id}: {e}")
            return None

    def _extract_metrics_from_response(self, response_text: str) -> Dict:
        """Extract metrics JSON from response"""
        try:
            # Look for JSON block
            if "```json" in response_text:
                parts = response_text.split("```json")
                if len(parts) > 1:
                    json_str = parts[1].split("```")[0].strip()
                    return json.loads(json_str)

            # Try to find JSON object in text
            import re
            json_match = re.search(r'\{[^{}]*"performance_metrics"[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))

        except Exception as e:
            logger.warning(f"Failed to extract metrics JSON: {e}")

        return {}

    async def batch_generate_lua(
        self,
        analyses: List[Dict],
        batch_size: int = 5,
        max_concurrent: int = 3
    ) -> List[LuaGenerationResult]:
        """Generate LUA for multiple parsers in batches with adaptive rate limiting"""
        logger.info(f"[INIT] Starting batch LUA generation for {len(analyses)} parsers")
        all_results = []

        analysis_index = 0
        total_analyses = len(analyses)

        while analysis_index < total_analyses:
            # Get recommended batch size based on available tokens
            _, output_available = self.token_bucket.tokens_available()
            adaptive_batch_size = self.batch_sizer.get_batch_size(output_available)

            # Get actual batch
            batch = analyses[analysis_index:analysis_index + adaptive_batch_size]
            batch_num = (analysis_index // adaptive_batch_size) + 1
            logger.info(f"Generating batch {batch_num} with {len(batch)} parsers (adaptive sizing)")

            # Estimate tokens for this batch
            estimated_input_per_parser = 600
            estimated_output_per_parser = 1500
            total_estimated_output = estimated_output_per_parser * len(batch)

            # Wait for tokens if necessary
            await self.token_bucket.wait_for_tokens(
                estimated_input=estimated_input_per_parser * len(batch),
                estimated_output=total_estimated_output
            )

            # Create tasks with semaphore for concurrency control
            semaphore = asyncio.Semaphore(max_concurrent)

            async def generate_with_semaphore(analysis):
                async with semaphore:
                    try:
                        parser_id = analysis.get("parser_id", "unknown")
                        return await self.generate_lua(parser_id, analysis)
                    except Exception as e:
                        logger.error(f"Batch generation error: {e}")
                        return None

            batch_tasks = [generate_with_semaphore(a) for a in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Collect successful results and track batch success
            batch_success_count = 0
            for result in batch_results:
                if isinstance(result, LuaGenerationResult):
                    all_results.append(result)
                    batch_success_count += 1

            # Record batch success/failure for adaptive sizing
            if batch_success_count == len(batch):
                self.batch_sizer.record_success()
            elif batch_success_count < len(batch) / 2:
                self.batch_sizer.record_failure()

            analysis_index += len(batch)

        logger.info(f"[OK] Batch LUA generation complete: {len(all_results)}/{len(analyses)} successful")
        return all_results

    def get_statistics(self) -> Dict:
        """Get generation statistics"""
        return {
            **self.statistics,
            "success_rate": (
                self.statistics["successful"] / self.statistics["total_generated"]
                if self.statistics["total_generated"] > 0 else 0
            )
        }
