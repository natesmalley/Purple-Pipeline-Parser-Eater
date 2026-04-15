"""
Comprehensive tests for Claude Parser Analyzer component

Tests semantic analysis of SentinelOne parsers using Claude AI, including
response parsing, rate limiting, batch processing, and error handling.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
import json

from components.claude_analyzer import ClaudeParserAnalyzer, ParserAnalysis, DateTimeEncoder
from utils.error_handler import ClaudeAPIError


@pytest.fixture
def analyzer_config():
    """Standard analyzer configuration."""
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
def valid_parser():
    """Valid parser configuration for testing."""
    return {
        "parser_id": "test-parser-001",
        "source_type": "syslog",
        "config": {
            "name": "Test Parser",
            "version": "1.0",
            "fields": ["event_type", "severity", "source_ip"]
        },
        "metadata": {
            "created_by": "system",
            "version": "1.0"
        }
    }


@pytest.fixture
def sample_analysis_response():
    """Sample Claude API response for parser analysis."""
    return json.dumps({
        "semantic_summary": "This parser processes authentication events from test source",
        "parser_complexity": {
            "level": "Medium",
            "factors": ["field_count", "regex_patterns"],
            "confidence": 0.85
        },
        "field_mappings": {
            "event_type": {
                "target_ocsf_field": "activity_id",
                "transformation_type": "copy",
                "confidence": 0.90
            },
            "source_ip": {
                "target_ocsf_field": "src_endpoint.ip",
                "transformation_type": "copy",
                "confidence": 0.95
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
            "vendor": "Test Vendor",
            "product": "Test Product",
            "log_format": "JSON",
            "ingestion_method": "API"
        },
        "optimization_opportunities": [
            "Combine similar operations",
            "Optimize regex patterns"
        ],
        "performance_characteristics": {
            "expected_volume": "Medium",
            "processing_complexity": "Moderate",
            "resource_requirements": "Standard"
        },
        "overall_confidence": 0.88
    })


class TestClaudeAnalyzerBasicOperations:
    """Test Suite 1: Basic Analyzer Operations"""

    def test_analyzer_initialization(self, analyzer_config):
        """Test analyzer initialization with valid config.

        Batch 3 Stream D fix — typo `ClaudeAnalyzerAnalyzer` → real
        class is `ClaudeParserAnalyzer` (see the import at line 13).
        """
        with patch('components.claude_analyzer.AsyncAnthropic'):
            analyzer = ClaudeParserAnalyzer(analyzer_config)

            assert analyzer is not None
            assert analyzer.model == "claude-3-5-sonnet-20241022"
            assert analyzer.max_tokens == 4000
            assert analyzer.temperature == 0.1

    def test_analyzer_initialization_missing_api_key(self):
        """Test initialization fails without API key."""
        # SECURITY NOTE: This is a test placeholder value, not a real API key
        TEST_API_KEY_PLACEHOLDER = "your-anthropic-api-key-here"
        config = {
            "anthropic": {
                "api_key": TEST_API_KEY_PLACEHOLDER,  # Test placeholder value
                "model": "claude-3-5-sonnet-20241022"
            }
        }

        with pytest.raises(ClaudeAPIError):
            ClaudeParserAnalyzer(config)

    def test_datetime_encoder_with_datetime(self):
        """Test DateTimeEncoder handles datetime objects."""
        from datetime import datetime
        encoder = DateTimeEncoder()

        dt = datetime(2025, 10, 13, 18, 22, 12)
        result = encoder.default(dt)

        assert isinstance(result, str)
        assert "2025-10-13" in result

    def test_datetime_encoder_with_date(self):
        """Test DateTimeEncoder handles date objects."""
        from datetime import date
        encoder = DateTimeEncoder()

        d = date(2025, 10, 13)
        result = encoder.default(d)

        assert isinstance(result, str)
        assert "2025-10-13" == result

    @pytest.mark.asyncio
    async def test_get_statistics_initial_state(self, analyzer_config):
        """Test statistics are initialized correctly."""
        with patch('components.claude_analyzer.AsyncAnthropic'):
            analyzer = ClaudeParserAnalyzer(analyzer_config)
            stats = analyzer.get_statistics()

            assert stats["total_analyzed"] == 0
            assert stats["successful"] == 0
            assert stats["failed"] == 0
            assert stats["success_rate"] == 0


class TestClaudeAnalyzerClaudeAPI:
    """Test Suite 2: Claude API Integration"""

    @pytest.mark.asyncio
    async def test_analyze_parser_success(self, analyzer_config, valid_parser, sample_analysis_response):
        """Test successful parser analysis."""
        with patch('components.claude_analyzer.AsyncAnthropic') as mock_client:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=sample_analysis_response)]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=1500)
            mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

            analyzer = ClaudeParserAnalyzer(analyzer_config)
            result = await analyzer.analyze_parser(valid_parser)

            assert isinstance(result, ParserAnalysis)
            assert result.parser_id == "test-parser-001"
            assert result.overall_confidence == 0.88

    @pytest.mark.asyncio
    async def test_analyze_parser_malformed_json(self, analyzer_config, valid_parser):
        """Test handling of malformed JSON response."""
        with patch('components.claude_analyzer.AsyncAnthropic') as mock_client:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="{ invalid json")]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=100)
            mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

            analyzer = ClaudeParserAnalyzer(analyzer_config)
            result = await analyzer.analyze_parser(valid_parser)

            assert result is None

    @pytest.mark.asyncio
    async def test_analyze_parser_missing_required_field(self, analyzer_config, valid_parser):
        """Test handling of response missing required fields."""
        missing_field_response = json.dumps({
            "semantic_summary": "Test summary",
            "parser_complexity": {"level": "Medium"},
            # Missing: ocsf_classification, overall_confidence
        })

        with patch('components.claude_analyzer.AsyncAnthropic') as mock_client:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=missing_field_response)]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=500)
            mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

            analyzer = ClaudeParserAnalyzer(analyzer_config)
            result = await analyzer.analyze_parser(valid_parser)

            assert result is None

    @pytest.mark.asyncio
    async def test_analyze_parser_with_markdown_code_block(self, analyzer_config, valid_parser, sample_analysis_response):
        """Test parsing response with markdown code blocks."""
        markdown_response = f"```json\n{sample_analysis_response}\n```"

        with patch('components.claude_analyzer.AsyncAnthropic') as mock_client:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=markdown_response)]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=1500)
            mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

            analyzer = ClaudeParserAnalyzer(analyzer_config)
            result = await analyzer.analyze_parser(valid_parser)

            assert isinstance(result, ParserAnalysis)
            assert result.parser_id == "test-parser-001"

    @pytest.mark.asyncio
    async def test_analyze_parser_api_error(self, analyzer_config, valid_parser):
        """Test handling of API errors."""
        with patch('components.claude_analyzer.AsyncAnthropic') as mock_client:
            mock_client.return_value.messages.create = AsyncMock(
                side_effect=Exception("API rate limit exceeded")
            )

            analyzer = ClaudeParserAnalyzer(analyzer_config)

            with pytest.raises(ClaudeAPIError):
                await analyzer.analyze_parser(valid_parser)


class TestClaudeAnalyzerRateLimiting:
    """Test Suite 3: Rate Limiting and Token Bucket"""

    @pytest.mark.asyncio
    async def test_token_bucket_initialization(self, analyzer_config):
        """Test token bucket is initialized with correct limits."""
        with patch('components.claude_analyzer.AsyncAnthropic'):
            analyzer = ClaudeParserAnalyzer(analyzer_config)

            assert analyzer.token_bucket is not None
            # Token bucket should track tokens per minute
            tokens_available = analyzer.token_bucket.tokens_available()
            assert tokens_available is not None

    @pytest.mark.asyncio
    async def test_token_usage_recorded(self, analyzer_config, valid_parser, sample_analysis_response):
        """Test token usage is recorded in token bucket."""
        with patch('components.claude_analyzer.AsyncAnthropic') as mock_client:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=sample_analysis_response)]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=1500)
            mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

            analyzer = ClaudeParserAnalyzer(analyzer_config)

            with patch.object(analyzer.token_bucket, 'record_usage') as mock_record:
                result = await analyzer.analyze_parser(valid_parser)

                # Verify token usage was recorded
                mock_record.assert_called_once()
                call_args = mock_record.call_args
                assert call_args[1]['input_tokens'] == 500
                assert call_args[1]['output_tokens'] == 1500

    @pytest.mark.asyncio
    async def test_adaptive_batch_sizing(self, analyzer_config):
        """Test adaptive batch sizer is initialized.

        Batch 3 Stream D fix — AdaptiveBatchSizer stores the init value
        as `current_batch_size` (rate_limiter.py:200), not
        `initial_batch_size`. The class accepts `initial_batch_size` as
        a constructor kwarg but does not expose it as an attribute.
        Test now asserts against the real attribute names and the
        values ClaudeParserAnalyzer initializes the sizer with
        (components/claude_analyzer.py:103).
        """
        with patch('components.claude_analyzer.AsyncAnthropic'):
            analyzer = ClaudeParserAnalyzer(analyzer_config)

            assert analyzer.batch_sizer is not None
            assert analyzer.batch_sizer.current_batch_size == 5
            assert analyzer.batch_sizer.min_batch_size == 1
            assert analyzer.batch_sizer.max_batch_size == 10


class TestClaudeAnalyzerBatchProcessing:
    """Test Suite 4: Batch Processing"""

    @pytest.mark.asyncio
    async def test_batch_analyze_single_batch(self, analyzer_config, valid_parser, sample_analysis_response):
        """Test batch analysis with single batch."""
        with patch('components.claude_analyzer.AsyncAnthropic') as mock_client:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=sample_analysis_response)]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=1500)
            mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

            analyzer = ClaudeParserAnalyzer(analyzer_config)
            parsers = [valid_parser, valid_parser]

            results = await analyzer.batch_analyze_parsers(parsers, batch_size=5, max_concurrent=2)

            assert len(results) == 2
            assert all(isinstance(r, ParserAnalysis) for r in results)

    @pytest.mark.asyncio
    async def test_batch_analyze_multiple_batches(self, analyzer_config, valid_parser, sample_analysis_response):
        """Test batch analysis splits into multiple batches."""
        with patch('components.claude_analyzer.AsyncAnthropic') as mock_client:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=sample_analysis_response)]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=1500)
            mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

            analyzer = ClaudeParserAnalyzer(analyzer_config)

            # Create 10 parsers to trigger multiple batches
            parsers = [valid_parser] * 10

            with patch.object(analyzer.batch_sizer, 'get_batch_size', return_value=3):
                results = await analyzer.batch_analyze_parsers(parsers, batch_size=3, max_concurrent=2)

                assert len(results) >= 6  # At least 6 successful (some may fail in testing)

    @pytest.mark.asyncio
    async def test_batch_success_tracking(self, analyzer_config, valid_parser, sample_analysis_response):
        """Test batch success/failure tracking for adaptive sizing."""
        with patch('components.claude_analyzer.AsyncAnthropic') as mock_client:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=sample_analysis_response)]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=1500)
            mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

            analyzer = ClaudeParserAnalyzer(analyzer_config)

            with patch.object(analyzer.batch_sizer, 'record_success') as mock_success:
                parsers = [valid_parser] * 3
                await analyzer.batch_analyze_parsers(parsers, batch_size=5, max_concurrent=2)

                # Should record successes
                assert mock_success.called


class TestClaudeAnalyzerRetryLogic:
    """Test Suite 5: Retry and Recovery"""

    @pytest.mark.asyncio
    async def test_analyze_with_retry_success_first_attempt(self, analyzer_config, valid_parser, sample_analysis_response):
        """Test retry succeeds on first attempt."""
        with patch('components.claude_analyzer.AsyncAnthropic') as mock_client:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=sample_analysis_response)]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=1500)
            mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

            analyzer = ClaudeParserAnalyzer(analyzer_config)
            result = await analyzer.analyze_with_retry(valid_parser, max_retries=3)

            assert isinstance(result, ParserAnalysis)

    @pytest.mark.asyncio
    async def test_analyze_with_retry_exponential_backoff(self, analyzer_config, valid_parser):
        """Test exponential backoff in retry logic."""
        with patch('components.claude_analyzer.AsyncAnthropic') as mock_client:
            # Fail twice, succeed on third attempt
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="{}")]  # Invalid response
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=100)
            mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

            analyzer = ClaudeParserAnalyzer(analyzer_config)

            with patch('asyncio.sleep', new_callable=AsyncMock):
                result = await analyzer.analyze_with_retry(valid_parser, max_retries=2)

                # Should return None after max retries
                assert result is None

    @pytest.mark.asyncio
    async def test_analyze_with_retry_max_retries_exceeded(self, analyzer_config, valid_parser):
        """Test behavior when max retries exceeded."""
        with patch('components.claude_analyzer.AsyncAnthropic') as mock_client:
            mock_client.return_value.messages.create = AsyncMock(
                side_effect=ClaudeAPIError("API error")
            )

            analyzer = ClaudeParserAnalyzer(analyzer_config)
            result = await analyzer.analyze_with_retry(valid_parser, max_retries=2)

            assert result is None


class TestClaudeAnalyzerStatistics:
    """Test Suite 6: Statistics Tracking"""

    @pytest.mark.asyncio
    async def test_statistics_updated_after_analysis(self, analyzer_config, valid_parser, sample_analysis_response):
        """Test statistics are updated after successful analysis."""
        with patch('components.claude_analyzer.AsyncAnthropic') as mock_client:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=sample_analysis_response)]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=1500)
            mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

            analyzer = ClaudeParserAnalyzer(analyzer_config)
            await analyzer.analyze_parser(valid_parser)

            stats = analyzer.get_statistics()
            assert stats["total_analyzed"] == 1
            assert stats["successful"] == 1
            assert stats["failed"] == 0
            assert stats["total_tokens_used"] == 2000

    @pytest.mark.asyncio
    async def test_statistics_failed_analysis(self, analyzer_config, valid_parser):
        """Test statistics track failed analyses."""
        with patch('components.claude_analyzer.AsyncAnthropic') as mock_client:
            mock_client.return_value.messages.create = AsyncMock(
                side_effect=Exception("API error")
            )

            analyzer = ClaudeParserAnalyzer(analyzer_config)

            try:
                await analyzer.analyze_parser(valid_parser)
            except ClaudeAPIError:
                pass

            stats = analyzer.get_statistics()
            assert stats["failed"] == 1
            assert stats["successful"] == 0

    @pytest.mark.asyncio
    async def test_statistics_success_rate(self, analyzer_config, valid_parser, sample_analysis_response):
        """Test success rate calculation."""
        with patch('components.claude_analyzer.AsyncAnthropic') as mock_client:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=sample_analysis_response)]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=1500)
            mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

            analyzer = ClaudeParserAnalyzer(analyzer_config)

            # Analyze 2 parsers
            await analyzer.analyze_parser(valid_parser)
            await analyzer.analyze_parser(valid_parser)

            stats = analyzer.get_statistics()
            assert stats["success_rate"] == 1.0  # 2 out of 2


class TestClaudeAnalyzerIntegration:
    """Integration tests for Claude Analyzer"""

    @pytest.mark.asyncio
    async def test_full_analysis_flow(self, analyzer_config, valid_parser, sample_analysis_response):
        """Test complete analysis flow from parser to result."""
        with patch('components.claude_analyzer.AsyncAnthropic') as mock_client:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=sample_analysis_response)]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=1500)
            mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

            analyzer = ClaudeParserAnalyzer(analyzer_config)
            result = await analyzer.analyze_parser(valid_parser)

            # Verify complete result structure
            assert result.parser_id == "test-parser-001"
            assert result.semantic_summary is not None
            assert result.parser_complexity is not None
            assert result.ocsf_classification is not None
            assert result.overall_confidence > 0

    @pytest.mark.asyncio
    async def test_analysis_with_datetime_metadata(self, analyzer_config):
        """Test analysis with datetime objects in metadata."""
        from datetime import datetime

        parser_with_datetime = {
            "parser_id": "test-parser-datetime",
            "source_type": "json",
            "config": {"name": "Test"},
            "metadata": {
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "version": "1.0"
            }
        }

        sample_response = json.dumps({
            "semantic_summary": "Test",
            "parser_complexity": {"level": "Low", "factors": [], "confidence": 0.8},
            "field_mappings": {},
            "ocsf_classification": {
                "class_uid": 1001,
                "class_name": "Alerts",
                "category_uid": 1,
                "category_name": "System",
                "confidence": 0.9
            },
            "data_source_analysis": {},
            "optimization_opportunities": [],
            "performance_characteristics": {},
            "overall_confidence": 0.8
        })

        with patch('components.claude_analyzer.AsyncAnthropic') as mock_client:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=sample_response)]
            mock_response.usage = MagicMock(input_tokens=500, output_tokens=1500)
            mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

            analyzer = ClaudeParserAnalyzer(analyzer_config)
            result = await analyzer.analyze_parser(parser_with_datetime)

            assert result is not None
            assert result.parser_id == "test-parser-datetime"
