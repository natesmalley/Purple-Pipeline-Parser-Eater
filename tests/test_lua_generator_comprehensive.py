"""
Comprehensive tests for Claude LUA Generator component

Tests LUA code generation for Observo.ai transformation, field transformations,
syntax validation, and batch processing.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
import json

from components.lua_generator import ClaudeLuaGenerator, LuaGenerationResult
from utils.error_handler import LuaGenerationError


@pytest.fixture
def generator_config():
    """Standard generator configuration."""
    return {
        "anthropic": {
            "api_key": "test-api-key-12345",
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 4000,
            "temperature": 0.1,
            "rate_limit_delay": 1.0
        }
    }


@pytest.fixture
def sample_parser_analysis():
    """Sample parser analysis result."""
    return {
        "parser_id": "test-parser",
        "semantic_summary": "Authentication parser",
        "parser_complexity": {
            "level": "Medium",
            "factors": ["field_count"],
            "confidence": 0.85
        },
        "field_mappings": {
            "username": {
                "target_ocsf_field": "user.name",
                "transformation_type": "copy",
                "confidence": 0.95
            },
            "event_code": {
                "target_ocsf_field": "activity_id",
                "transformation_type": "cast",
                "confidence": 0.90
            }
        },
        "ocsf_classification": {
            "class_uid": 3002,
            "class_name": "Authentication",
            "category_uid": 3,
            "category_name": "Identity & Access Management",
            "confidence": 0.95
        },
        "data_source_analysis": {
            "vendor": "Test",
            "product": "Test Product",
            "log_format": "JSON"
        },
        "optimization_opportunities": ["Combine operations"],
        "performance_characteristics": {
            "expected_volume": "High",
            "processing_complexity": "Moderate"
        },
        "overall_confidence": 0.88
    }


@pytest.fixture
def sample_lua_response():
    """Sample Claude API response for LUA generation."""
    return """```lua
-- SentinelOne Parser: test-parser
-- OCSF Class: Authentication (3002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-15T10:30:00

function transform(record)
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    local output = {
        class_uid = 3002,
        class_name = "Authentication",
        category_uid = 3,
        category_name = "Identity & Access Management",
        activity_id = 1,
        type_uid = 300201
    }

    -- Copy username to user.name
    if record.username then
        output.user = output.user or {}
        output.user.name = record.username
    end

    -- Cast event_code to activity_id
    if record.event_code then
        output.activity_id = tonumber(record.event_code)
    end

    -- Validate required OCSF fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    if not output.time then
        output.time = os.time() * 1000
    end

    return output
end
```

```json
{
  "performance_metrics": {
    "estimated_throughput": "10000+ events/sec",
    "memory_per_event": "2-4 KB",
    "cpu_complexity": "O(n)"
  },
  "memory_analysis": "Uses local variables for 15% improvement, efficient string operations",
  "deployment_notes": "Deploy as standard transform function in Observo.ai pipeline",
  "monitoring_recommendations": [
    "Monitor transformation errors",
    "Track processing latency",
    "Alert on field mapping failures"
  ],
  "test_cases": "Test Case 1: Valid input with all fields"
}
```
"""


class TestLuaGeneratorCodeGeneration:
    """Test Suite 1: LUA Code Generation Basics"""

    def test_generator_initialization(self, generator_config):
        """Test generator initialization with valid config."""
        with patch('components.lua_generator.AsyncAnthropic'):
            generator = ClaudeLuaGenerator(generator_config)

            assert generator is not None
            assert generator.model == "claude-3-5-sonnet-20241022"
            assert generator.max_tokens == 4000
            assert generator.temperature == 0.1

    @pytest.mark.asyncio
    async def test_generate_lua_success(self, generator_config, sample_parser_analysis, sample_lua_response):
        """Test successful LUA code generation."""
        with patch('components.lua_generator.AsyncAnthropic') as mock_client:
            with patch('components.lua_generator.validate_lua_code', return_value=True):
                mock_response = MagicMock()
                mock_response.content = [MagicMock(text=sample_lua_response)]
                mock_response.usage = MagicMock(input_tokens=600, output_tokens=1500)
                mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

                generator = ClaudeLuaGenerator(generator_config)
                result = await generator.generate_lua("test-parser", sample_parser_analysis)

                assert isinstance(result, LuaGenerationResult)
                assert result.parser_id == "test-parser"
                assert "function transform" in result.lua_code

    @pytest.mark.asyncio
    async def test_generate_lua_no_lua_code_found(self, generator_config, sample_parser_analysis):
        """Test handling when no LUA code found in response."""
        with patch('components.lua_generator.AsyncAnthropic') as mock_client:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="No code here")]
            mock_response.usage = MagicMock(input_tokens=600, output_tokens=100)
            mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

            generator = ClaudeLuaGenerator(generator_config)
            result = await generator.generate_lua("test-parser", sample_parser_analysis)

            assert result is None

    @pytest.mark.asyncio
    async def test_generate_lua_validation_fails(self, generator_config, sample_parser_analysis, sample_lua_response):
        """Test handling when generated code fails validation."""
        with patch('components.lua_generator.AsyncAnthropic') as mock_client:
            with patch('components.lua_generator.validate_lua_code', return_value=False):
                mock_response = MagicMock()
                mock_response.content = [MagicMock(text=sample_lua_response)]
                mock_response.usage = MagicMock(input_tokens=600, output_tokens=1500)
                mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

                generator = ClaudeLuaGenerator(generator_config)

                with pytest.raises(LuaGenerationError):
                    await generator.generate_lua("test-parser", sample_parser_analysis)

    @pytest.mark.asyncio
    async def test_generate_lua_api_error(self, generator_config, sample_parser_analysis):
        """Test handling of API errors during generation."""
        with patch('components.lua_generator.AsyncAnthropic') as mock_client:
            mock_client.return_value.messages.create = AsyncMock(
                side_effect=Exception("API error")
            )

            generator = ClaudeLuaGenerator(generator_config)

            with pytest.raises(LuaGenerationError):
                await generator.generate_lua("test-parser", sample_parser_analysis)


class TestLuaGeneratorLuaSyntax:
    """Test Suite 2: LUA Syntax Validation"""

    def test_generate_field_transformations_copy(self, generator_config):
        """Test field transformation generation for copy type."""
        with patch('components.lua_generator.AsyncAnthropic'):
            generator = ClaudeLuaGenerator(generator_config)

            field_mappings = {
                "username": {
                    "target_ocsf_field": "user.name",
                    "transformation_type": "copy"
                }
            }

            code = generator._generate_field_transformations(field_mappings)

            assert "username" in code
            assert "user.name" in code
            assert "if record.username then" in code

    def test_generate_field_transformations_constant(self, generator_config):
        """Test field transformation generation for constant type."""
        with patch('components.lua_generator.AsyncAnthropic'):
            generator = ClaudeLuaGenerator(generator_config)

            field_mappings = {
                "vendor": {
                    "target_ocsf_field": "vendor_name",
                    "transformation_type": "constant",
                    "value": "SentinelOne"
                }
            }

            code = generator._generate_field_transformations(field_mappings)

            assert "vendor_name" in code
            assert "SentinelOne" in code

    def test_generate_field_transformations_cast(self, generator_config):
        """Test field transformation generation for cast type."""
        with patch('components.lua_generator.AsyncAnthropic'):
            generator = ClaudeLuaGenerator(generator_config)

            field_mappings = {
                "event_code": {
                    "target_ocsf_field": "activity_id",
                    "transformation_type": "cast"
                }
            }

            code = generator._generate_field_transformations(field_mappings)

            assert "event_code" in code
            assert "tonumber" in code
            assert "activity_id" in code

    def test_generate_field_transformations_empty(self, generator_config):
        """Test field transformation with empty mappings."""
        with patch('components.lua_generator.AsyncAnthropic'):
            generator = ClaudeLuaGenerator(generator_config)

            code = generator._generate_field_transformations({})

            assert "No field transformations specified" in code

    def test_generate_validation_logic(self, generator_config):
        """Test LUA validation logic generation."""
        with patch('components.lua_generator.AsyncAnthropic'):
            generator = ClaudeLuaGenerator(generator_config)

            ocsf_class = {
                "class_uid": 3002,
                "class_name": "Authentication"
            }

            code = generator._generate_validation_logic(ocsf_class)

            assert "class_uid" in code
            assert "Invalid class_uid" in code
            assert "time" in code or "os.time" in code

    def test_generate_test_cases(self, generator_config, sample_parser_analysis):
        """Test LUA test case generation."""
        with patch('components.lua_generator.AsyncAnthropic'):
            generator = ClaudeLuaGenerator(generator_config)

            test_cases = generator._generate_test_cases("test-parser", sample_parser_analysis)

            assert "transform" in test_cases
            assert "Test Case" in test_cases
            assert "3002" in test_cases  # class_uid


class TestLuaGeneratorFieldTransformation:
    """Test Suite 3: Field Transformation Logic"""

    def test_prepare_generation_prompt_structure(self, generator_config, sample_parser_analysis):
        """Test prompt preparation includes all required fields."""
        with patch('components.lua_generator.AsyncAnthropic'):
            generator = ClaudeLuaGenerator(generator_config)

            prompt = generator._prepare_generation_prompt("test-parser", sample_parser_analysis)

            assert "test-parser" in prompt
            assert "field_mappings" in prompt
            assert "OCSF" in prompt
            assert "function transform" in prompt

    def test_prepare_generation_prompt_ocsf_values(self, generator_config, sample_parser_analysis):
        """Test OCSF classification values in prompt."""
        with patch('components.lua_generator.AsyncAnthropic'):
            generator = ClaudeLuaGenerator(generator_config)

            prompt = generator._prepare_generation_prompt("test-parser", sample_parser_analysis)

            assert "3002" in prompt  # class_uid
            assert "Authentication" in prompt
            assert "300201" in prompt  # type_uid

    def test_extract_metrics_from_response_with_json_block(self, generator_config):
        """Test metrics extraction from JSON code block."""
        with patch('components.lua_generator.AsyncAnthropic'):
            generator = ClaudeLuaGenerator(generator_config)

            response = """Some text
```json
{
  "performance_metrics": {"estimated_throughput": "10000+"},
  "memory_analysis": "Low memory usage",
  "monitoring_recommendations": ["monitor errors"]
}
```
More text"""

            metrics = generator._extract_metrics_from_response(response)

            assert "performance_metrics" in metrics
            assert metrics["memory_analysis"] == "Low memory usage"

    def test_extract_metrics_no_json(self, generator_config):
        """Test metrics extraction when no JSON present."""
        with patch('components.lua_generator.AsyncAnthropic'):
            generator = ClaudeLuaGenerator(generator_config)

            response = "No JSON here at all"

            metrics = generator._extract_metrics_from_response(response)

            assert metrics == {}

    def test_parse_lua_response_with_markdown(self, generator_config, sample_parser_analysis):
        """Test parsing LUA code from markdown blocks."""
        with patch('components.lua_generator.AsyncAnthropic'):
            generator = ClaudeLuaGenerator(generator_config)

            response = """```lua
function transform(record)
    return record
end
```

```json
{"performance_metrics": {}}
```
"""

            result = generator._parse_lua_response(response, "test", sample_parser_analysis)

            assert result is not None
            assert "function transform" in result.lua_code
            assert result.parser_id == "test"


class TestLuaGeneratorBatchProcessing:
    """Test Suite 4: Batch Generation"""

    @pytest.mark.asyncio
    async def test_batch_generate_lua_single_batch(self, generator_config, sample_parser_analysis, sample_lua_response):
        """Test batch LUA generation with single batch."""
        with patch('components.lua_generator.AsyncAnthropic') as mock_client:
            with patch('components.lua_generator.validate_lua_code', return_value=True):
                mock_response = MagicMock()
                mock_response.content = [MagicMock(text=sample_lua_response)]
                mock_response.usage = MagicMock(input_tokens=600, output_tokens=1500)
                mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

                generator = ClaudeLuaGenerator(generator_config)
                analyses = [sample_parser_analysis, sample_parser_analysis]

                results = await generator.batch_generate_lua(analyses, batch_size=5, max_concurrent=2)

                assert len(results) >= 1
                assert all(isinstance(r, LuaGenerationResult) for r in results)

    @pytest.mark.asyncio
    async def test_batch_generate_lua_multiple_batches(self, generator_config, sample_parser_analysis, sample_lua_response):
        """Test batch generation splits into multiple batches."""
        with patch('components.lua_generator.AsyncAnthropic') as mock_client:
            with patch('components.lua_generator.validate_lua_code', return_value=True):
                mock_response = MagicMock()
                mock_response.content = [MagicMock(text=sample_lua_response)]
                mock_response.usage = MagicMock(input_tokens=600, output_tokens=1500)
                mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

                generator = ClaudeLuaGenerator(generator_config)

                # Create 10 analyses
                analyses = [sample_parser_analysis] * 10

                with patch.object(generator.batch_sizer, 'get_batch_size', return_value=3):
                    results = await generator.batch_generate_lua(analyses, batch_size=3, max_concurrent=2)

                    assert len(results) >= 3

    @pytest.mark.asyncio
    async def test_batch_success_tracking(self, generator_config, sample_parser_analysis, sample_lua_response):
        """Test batch success/failure tracking."""
        with patch('components.lua_generator.AsyncAnthropic') as mock_client:
            with patch('components.lua_generator.validate_lua_code', return_value=True):
                mock_response = MagicMock()
                mock_response.content = [MagicMock(text=sample_lua_response)]
                mock_response.usage = MagicMock(input_tokens=600, output_tokens=1500)
                mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

                generator = ClaudeLuaGenerator(generator_config)

                with patch.object(generator.batch_sizer, 'record_success') as mock_success:
                    analyses = [sample_parser_analysis] * 3
                    await generator.batch_generate_lua(analyses, batch_size=5, max_concurrent=2)

                    assert mock_success.called


class TestLuaGeneratorStatistics:
    """Test Suite 5: Statistics Tracking"""

    @pytest.mark.asyncio
    async def test_statistics_updated_after_generation(self, generator_config, sample_parser_analysis, sample_lua_response):
        """Test statistics are updated after generation."""
        with patch('components.lua_generator.AsyncAnthropic') as mock_client:
            with patch('components.lua_generator.validate_lua_code', return_value=True):
                mock_response = MagicMock()
                mock_response.content = [MagicMock(text=sample_lua_response)]
                mock_response.usage = MagicMock(input_tokens=600, output_tokens=1500)
                mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

                generator = ClaudeLuaGenerator(generator_config)
                await generator.generate_lua("test-parser", sample_parser_analysis)

                stats = generator.get_statistics()
                assert stats["total_generated"] == 1
                assert stats["successful"] == 1
                assert stats["total_tokens_used"] == 2100

    @pytest.mark.asyncio
    async def test_statistics_failed_generation(self, generator_config, sample_parser_analysis):
        """Test statistics track failed generations."""
        with patch('components.lua_generator.AsyncAnthropic') as mock_client:
            mock_client.return_value.messages.create = AsyncMock(
                side_effect=Exception("API error")
            )

            generator = ClaudeLuaGenerator(generator_config)

            try:
                await generator.generate_lua("test-parser", sample_parser_analysis)
            except LuaGenerationError:
                pass

            stats = generator.get_statistics()
            assert stats["failed"] == 1

    @pytest.mark.asyncio
    async def test_statistics_success_rate(self, generator_config, sample_parser_analysis, sample_lua_response):
        """Test success rate calculation."""
        with patch('components.lua_generator.AsyncAnthropic') as mock_client:
            with patch('components.lua_generator.validate_lua_code', return_value=True):
                mock_response = MagicMock()
                mock_response.content = [MagicMock(text=sample_lua_response)]
                mock_response.usage = MagicMock(input_tokens=600, output_tokens=1500)
                mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

                generator = ClaudeLuaGenerator(generator_config)

                # Generate for 2 analyses
                await generator.generate_lua("test-parser-1", sample_parser_analysis)
                await generator.generate_lua("test-parser-2", sample_parser_analysis)

                stats = generator.get_statistics()
                assert stats["success_rate"] == 1.0


class TestLuaGeneratorTokenManagement:
    """Test Suite 6: Token Bucket and Rate Limiting"""

    @pytest.mark.asyncio
    async def test_token_bucket_initialization(self, generator_config):
        """Test token bucket is initialized."""
        with patch('components.lua_generator.AsyncAnthropic'):
            generator = ClaudeLuaGenerator(generator_config)

            assert generator.token_bucket is not None

    @pytest.mark.asyncio
    async def test_token_usage_recorded(self, generator_config, sample_parser_analysis, sample_lua_response):
        """Test token usage is recorded."""
        with patch('components.lua_generator.AsyncAnthropic') as mock_client:
            with patch('components.lua_generator.validate_lua_code', return_value=True):
                mock_response = MagicMock()
                mock_response.content = [MagicMock(text=sample_lua_response)]
                mock_response.usage = MagicMock(input_tokens=600, output_tokens=1500)
                mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

                generator = ClaudeLuaGenerator(generator_config)

                with patch.object(generator.token_bucket, 'record_usage') as mock_record:
                    await generator.generate_lua("test-parser", sample_parser_analysis)

                    mock_record.assert_called_once()


class TestLuaGeneratorIntegration:
    """Integration tests for LUA Generator"""

    @pytest.mark.asyncio
    async def test_full_generation_flow(self, generator_config, sample_parser_analysis, sample_lua_response):
        """Test complete generation flow from analysis to result."""
        with patch('components.lua_generator.AsyncAnthropic') as mock_client:
            with patch('components.lua_generator.validate_lua_code', return_value=True):
                mock_response = MagicMock()
                mock_response.content = [MagicMock(text=sample_lua_response)]
                mock_response.usage = MagicMock(input_tokens=600, output_tokens=1500)
                mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

                generator = ClaudeLuaGenerator(generator_config)
                result = await generator.generate_lua("test-parser", sample_parser_analysis)

                # Verify complete result structure
                assert result.parser_id == "test-parser"
                assert result.lua_code is not None
                assert "function transform" in result.lua_code
                assert result.performance_metrics is not None
                assert result.confidence_score == 0.88

    @pytest.mark.asyncio
    async def test_result_to_dict_conversion(self, generator_config, sample_parser_analysis, sample_lua_response):
        """Test LuaGenerationResult conversion to dictionary."""
        with patch('components.lua_generator.AsyncAnthropic') as mock_client:
            with patch('components.lua_generator.validate_lua_code', return_value=True):
                mock_response = MagicMock()
                mock_response.content = [MagicMock(text=sample_lua_response)]
                mock_response.usage = MagicMock(input_tokens=600, output_tokens=1500)
                mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

                generator = ClaudeLuaGenerator(generator_config)
                result = await generator.generate_lua("test-parser", sample_parser_analysis)

                result_dict = result.to_dict()

                assert isinstance(result_dict, dict)
                assert "parser_id" in result_dict
                assert "lua_code" in result_dict
                assert "performance_metrics" in result_dict
                assert result_dict["parser_id"] == "test-parser"

    @pytest.mark.asyncio
    async def test_analysis_to_generation_flow(self, generator_config, sample_parser_analysis, sample_lua_response):
        """Test complete flow from analysis output to LUA generation."""
        with patch('components.lua_generator.AsyncAnthropic') as mock_client:
            with patch('components.lua_generator.validate_lua_code', return_value=True):
                # First, generate with the analysis
                mock_response = MagicMock()
                mock_response.content = [MagicMock(text=sample_lua_response)]
                mock_response.usage = MagicMock(input_tokens=600, output_tokens=1500)
                mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

                generator = ClaudeLuaGenerator(generator_config)

                # Verify prompt includes analysis data
                prompt = generator._prepare_generation_prompt(
                    sample_parser_analysis["parser_id"],
                    sample_parser_analysis
                )

                assert sample_parser_analysis["parser_id"] in prompt
                assert str(sample_parser_analysis["ocsf_classification"]["class_uid"]) in prompt

    @pytest.mark.asyncio
    async def test_generate_with_partial_analysis(self, generator_config, sample_lua_response):
        """Test LUA generation with minimal analysis data."""
        minimal_analysis = {
            "parser_id": "minimal-parser",
            "ocsf_classification": {
                "class_uid": 1001,
                "class_name": "System Activity",
                "category_uid": 1
            },
            "field_mappings": {},
            "overall_confidence": 0.5
        }

        with patch('components.lua_generator.AsyncAnthropic') as mock_client:
            with patch('components.lua_generator.validate_lua_code', return_value=True):
                mock_response = MagicMock()
                mock_response.content = [MagicMock(text=sample_lua_response)]
                mock_response.usage = MagicMock(input_tokens=600, output_tokens=1500)
                mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

                generator = ClaudeLuaGenerator(generator_config)
                result = await generator.generate_lua("minimal-parser", minimal_analysis)

                assert result is not None
