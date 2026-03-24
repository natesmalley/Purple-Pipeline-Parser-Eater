#!/usr/bin/env python3
"""
Retry logic with exponential backoff

Utilities for retrying operations with configurable backoff strategies.
"""

import asyncio
import logging
from typing import Callable, Optional, Type, Tuple, Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)


def is_retryable_error(exception: Exception) -> bool:
    """
    Check if error should be retried.

    Args:
        exception: Exception to check

    Returns:
        True if error is retryable, False otherwise
    """
    try:
        import aiohttp
        # Retry on network errors
        if isinstance(exception, (
            aiohttp.ClientError,
            aiohttp.ServerTimeoutError,
            aiohttp.ClientConnectorError,
            asyncio.TimeoutError,
        )):
            return True

        # Retry on 5xx server errors
        if isinstance(exception, aiohttp.ClientResponseError):
            if 500 <= exception.status < 600:
                return True
    except ImportError:
        pass

    return False


def retry_on_retryable_error(max_attempts: int = 3):
    """
    Decorator for retrying on retryable errors.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)

    Returns:
        Decorator function
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((
            Exception,  # Catch all for now, filter in is_retryable_error
        )),
        reraise=True,
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying {retry_state.fn.__name__} "
            f"(attempt {retry_state.attempt_number}/{max_attempts})"
        )
    )


class RetryConfig:
    """Configuration for retry behavior"""

    def __init__(
        self,
        max_attempts: int = 3,
        initial_wait: float = 2,
        max_wait: float = 60,
        exponential_base: float = 2
    ):
        """
        Initialize retry configuration.

        Args:
            max_attempts: Maximum number of attempts
            initial_wait: Initial wait time in seconds
            max_wait: Maximum wait time in seconds
            exponential_base: Base for exponential backoff
        """
        self.max_attempts = max_attempts
        self.initial_wait = initial_wait
        self.max_wait = max_wait
        self.exponential_base = exponential_base

    def get_wait_time(self, attempt: int) -> float:
        """
        Get wait time for attempt number.

        Args:
            attempt: Attempt number (0-indexed)

        Returns:
            Wait time in seconds
        """
        wait_time = self.initial_wait * (self.exponential_base ** attempt)
        return min(wait_time, self.max_wait)


async def retry_async(
    func: Callable,
    config: Optional[RetryConfig] = None,
    *args,
    **kwargs
) -> Any:
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        config: RetryConfig instance (default: sensible defaults)
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func

    Returns:
        Result from func

    Raises:
        Last exception if all attempts fail
    """
    if config is None:
        config = RetryConfig()

    last_exception = None

    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e

            if attempt < config.max_attempts - 1:
                wait_time = config.get_wait_time(attempt)
                logger.warning(
                    f"Attempt {attempt + 1}/{config.max_attempts} failed: {type(e).__name__}. "
                    f"Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error(
                    f"All {config.max_attempts} attempts failed: {type(e).__name__}"
                )

    if last_exception:
        raise last_exception

    raise RuntimeError("Retry failed with unknown error")
