#!/usr/bin/env python3
"""
Tests for retry logic
"""

import pytest
import asyncio
from utils.retry import (
    is_retryable_error, RetryConfig, retry_async
)


class TestRetryableError:
    """Test retryable error detection"""

    def test_generic_exception_not_retryable(self):
        """Test that generic exceptions are not retryable"""
        assert not is_retryable_error(ValueError("test"))
        assert not is_retryable_error(RuntimeError("test"))

    def test_retryable_timeout_error(self):
        """Test that timeout errors are retryable"""
        assert is_retryable_error(asyncio.TimeoutError())


class TestRetryConfig:
    """Test retry configuration"""

    def test_default_config(self):
        """Test default retry config"""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.initial_wait == 2
        assert config.max_wait == 60
        assert config.exponential_base == 2

    def test_custom_config(self):
        """Test custom retry config"""
        config = RetryConfig(
            max_attempts=5,
            initial_wait=1,
            max_wait=30,
            exponential_base=1.5
        )
        assert config.max_attempts == 5
        assert config.initial_wait == 1
        assert config.max_wait == 30
        assert config.exponential_base == 1.5

    def test_exponential_backoff(self):
        """Test exponential backoff calculation"""
        config = RetryConfig(initial_wait=2, max_wait=60, exponential_base=2)

        # Attempt 0: 2 seconds
        assert config.get_wait_time(0) == 2

        # Attempt 1: 4 seconds
        assert config.get_wait_time(1) == 4

        # Attempt 2: 8 seconds
        assert config.get_wait_time(2) == 8

        # Attempt 3: 16 seconds
        assert config.get_wait_time(3) == 16

    def test_max_wait_capping(self):
        """Test that wait time is capped at max_wait"""
        config = RetryConfig(initial_wait=2, max_wait=10, exponential_base=2)

        # Attempt 0-2 are under max
        assert config.get_wait_time(0) == 2
        assert config.get_wait_time(1) == 4
        assert config.get_wait_time(2) == 8

        # Attempt 3+ should be capped at max_wait
        assert config.get_wait_time(3) == 10
        assert config.get_wait_time(4) == 10


class TestRetryAsync:
    """Test async retry functionality"""

    @pytest.mark.asyncio
    async def test_successful_first_attempt(self):
        """Test function succeeds on first attempt"""
        call_count = 0

        async def succeeds():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_async(succeeds)
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_failure_then_success(self):
        """Test function retries and succeeds"""
        call_count = 0

        async def fails_then_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("Temporary failure")
            return "success"

        config = RetryConfig(max_attempts=3)
        result = await retry_async(fails_then_succeeds, config)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_all_attempts_fail(self):
        """Test function fails after all attempts"""
        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        config = RetryConfig(max_attempts=3)
        with pytest.raises(ValueError, match="Always fails"):
            await retry_async(always_fails, config)

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_with_arguments(self):
        """Test retry with function arguments"""
        call_count = 0

        async def func_with_args(a, b, c=None):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("Retry me")
            return (a, b, c)

        config = RetryConfig(max_attempts=2)
        result = await retry_async(func_with_args, config, 1, 2, c=3)
        assert result == (1, 2, 3)
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_single_attempt_config(self):
        """Test retry with max_attempts=1 (no retry)"""
        call_count = 0

        async def fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Failed")

        config = RetryConfig(max_attempts=1)
        with pytest.raises(ValueError):
            await retry_async(fails, config)

        assert call_count == 1
