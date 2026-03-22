"""
Rate Limiting System for Purple Pipeline Parser Eater
Implements token bucket algorithm with adaptive batch sizing
"""

import time
import asyncio
import logging
from collections import deque
from typing import Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Record of token usage at a specific time"""
    timestamp: float
    input_tokens: int
    output_tokens: int
    total_tokens: int


class TokenBucket:
    """
    Token bucket algorithm for rate limiting.

    Tracks token usage within a sliding time window and enforces limits.
    Supports both input and output token limits with separate tracking.
    """

    def __init__(
        self,
        output_tokens_per_minute: int = 8000,
        input_tokens_per_minute: Optional[int] = None,
        window_seconds: int = 60
    ):
        """
        Initialize token bucket rate limiter.

        Args:
            output_tokens_per_minute: Maximum output tokens allowed per minute (default: 8000)
            input_tokens_per_minute: Maximum input tokens per minute (None = no limit)
            window_seconds: Rolling window size in seconds (default: 60)
        """
        self.output_limit = output_tokens_per_minute
        self.input_limit = input_tokens_per_minute
        self.window_seconds = window_seconds
        self.usage_history: deque[TokenUsage] = deque()

        logger.info(f"[RATE LIMITER] Initialized: {output_tokens_per_minute} output tokens/min")
        if input_tokens_per_minute:
            logger.info(f"[RATE LIMITER] Input limit: {input_tokens_per_minute} tokens/min")

    def _clean_old_entries(self, now: float) -> None:
        """Remove usage records older than the window"""
        cutoff = now - self.window_seconds
        while self.usage_history and self.usage_history[0].timestamp < cutoff:
            self.usage_history.popleft()

    def tokens_used_in_window(self) -> Tuple[int, int, int]:
        """
        Get total tokens used in the current window.

        Returns:
            Tuple of (input_tokens, output_tokens, total_tokens)
        """
        now = time.time()
        self._clean_old_entries(now)

        input_total = sum(usage.input_tokens for usage in self.usage_history)
        output_total = sum(usage.output_tokens for usage in self.usage_history)
        total = sum(usage.total_tokens for usage in self.usage_history)

        return input_total, output_total, total

    def tokens_available(self) -> Tuple[int, int]:
        """
        Get remaining tokens available in current window.

        Returns:
            Tuple of (input_tokens_available, output_tokens_available)
        """
        input_used, output_used, _ = self.tokens_used_in_window()

        output_available = max(0, self.output_limit - output_used)
        input_available = (
            max(0, self.input_limit - input_used)
            if self.input_limit
            else float('inf')
        )

        return int(input_available), output_available

    def record_usage(
        self,
        input_tokens: int,
        output_tokens: int
    ) -> None:
        """
        Record token usage for a completed API call.

        Args:
            input_tokens: Number of input tokens consumed
            output_tokens: Number of output tokens generated
        """
        usage = TokenUsage(
            timestamp=time.time(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens
        )
        self.usage_history.append(usage)

        input_avail, output_avail = self.tokens_available()
        logger.debug(
            f"[RATE LIMITER] Used: {output_tokens} output, {input_tokens} input | "
            f"Available: {output_avail} output, {input_avail} input"
        )

    def wait_time_for_tokens(
        self,
        estimated_input: int,
        estimated_output: int
    ) -> float:
        """
        Calculate wait time needed to have enough tokens available.

        Args:
            estimated_input: Expected input tokens for next request
            estimated_output: Expected output tokens for next request

        Returns:
            Wait time in seconds (0.0 if tokens available now)
        """
        input_avail, output_avail = self.tokens_available()

        # Check if we have enough tokens
        if (estimated_output <= output_avail and
            (not self.input_limit or estimated_input <= input_avail)):
            return 0.0

        # Not enough tokens - calculate wait time
        if not self.usage_history:
            return 0.0  # Empty history, shouldn't need to wait

        # Wait until the oldest usage record expires
        oldest_timestamp = self.usage_history[0].timestamp
        time_until_window_refresh = self.window_seconds - (time.time() - oldest_timestamp)

        return max(0.0, time_until_window_refresh)

    async def wait_for_tokens(
        self,
        estimated_input: int,
        estimated_output: int
    ) -> None:
        """
        Async wait until enough tokens are available.

        Args:
            estimated_input: Expected input tokens for next request
            estimated_output: Expected output tokens for next request
        """
        wait_time = self.wait_time_for_tokens(estimated_input, estimated_output)

        if wait_time > 0:
            logger.info(
                f"[RATE LIMITER] Rate limit approaching - waiting {wait_time:.1f}s "
                f"for {estimated_output} output tokens"
            )
            await asyncio.sleep(wait_time)


class AdaptiveBatchSizer:
    """
    Dynamically adjusts batch size based on token consumption and success rate.

    Starts conservative and increases batch size as confidence grows.
    Reduces batch size if rate limits are hit.
    """

    def __init__(
        self,
        initial_batch_size: int = 5,
        min_batch_size: int = 1,
        max_batch_size: int = 10,
        tokens_per_minute: int = 8000
    ):
        """
        Initialize adaptive batch sizer.

        Args:
            initial_batch_size: Starting batch size
            min_batch_size: Minimum allowed batch size
            max_batch_size: Maximum allowed batch size
            tokens_per_minute: Rate limit for tokens per minute
        """
        self.current_batch_size = initial_batch_size
        self.min_batch_size = min_batch_size
        self.max_batch_size = max_batch_size
        self.tokens_per_minute = tokens_per_minute

        self.success_streak = 0
        self.failure_streak = 0

        logger.info(f"[ADAPTIVE BATCH] Initialized: size={initial_batch_size}, range=[{min_batch_size}-{max_batch_size}]")

    def estimate_tokens_per_parser(self) -> int:
        """
        Estimate average tokens per parser.

        Returns:
            Estimated tokens per parser (conservative estimate)
        """
        # Conservative estimates based on observed data:
        # - Average input: 400 tokens (parser config + metadata)
        # - Average output: 1200 tokens (analysis/LUA generation)
        return 1600

    def calculate_safe_batch_size(self, tokens_available: int) -> int:
        """
        Calculate safe batch size given available tokens.

        Args:
            tokens_available: Number of tokens available in current window

        Returns:
            Safe batch size (won't exceed rate limit)
        """
        tokens_per_parser = self.estimate_tokens_per_parser()
        safe_size = max(1, tokens_available // tokens_per_parser)

        # Limit to max batch size
        return min(safe_size, self.max_batch_size)

    def record_success(self) -> None:
        """Record successful batch processing"""
        self.success_streak += 1
        self.failure_streak = 0

        # Increase batch size after 3 consecutive successes
        if self.success_streak >= 3 and self.current_batch_size < self.max_batch_size:
            old_size = self.current_batch_size
            self.current_batch_size = min(self.current_batch_size + 1, self.max_batch_size)
            logger.info(f"[ADAPTIVE BATCH] Increased batch size: {old_size} -> {self.current_batch_size}")
            self.success_streak = 0  # Reset streak

    def record_failure(self) -> None:
        """Record failed batch processing (rate limit hit)"""
        self.failure_streak += 1
        self.success_streak = 0

        # Decrease batch size immediately on failure
        if self.current_batch_size > self.min_batch_size:
            old_size = self.current_batch_size
            self.current_batch_size = max(self.current_batch_size - 1, self.min_batch_size)
            logger.warning(f"[ADAPTIVE BATCH] Decreased batch size: {old_size} -> {self.current_batch_size}")

    def get_batch_size(self, tokens_available: int) -> int:
        """
        Get recommended batch size for next batch.

        Args:
            tokens_available: Number of tokens available in current window

        Returns:
            Recommended batch size
        """
        safe_size = self.calculate_safe_batch_size(tokens_available)
        recommended = min(self.current_batch_size, safe_size)

        logger.debug(f"[ADAPTIVE BATCH] Recommended size: {recommended} (current={self.current_batch_size}, safe={safe_size})")
        return recommended
