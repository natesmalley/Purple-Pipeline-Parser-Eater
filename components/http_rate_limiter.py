"""HTTP endpoint rate limiting with per-endpoint configuration."""

from __future__ import annotations

import logging
from functools import wraps
from typing import Callable, Dict, Optional, Tuple
from datetime import datetime, timedelta, timezone

from flask import request, jsonify, Response

logger = logging.getLogger(__name__)


class EndpointRateLimiter:
    """Track and enforce rate limits per endpoint and client."""

    def __init__(self) -> None:
        """Initialize endpoint rate limiter."""
        # {(client_ip, endpoint): [timestamp1, timestamp2, ...]}
        self.request_times: Dict[Tuple[str, str], list] = {}
        self.cleanup_interval = 3600  # Clean old entries every hour
        self.last_cleanup = datetime.now(timezone.utc)

    def _get_client_ip(self) -> str:
        """Get client IP address from request.

        Returns:
            Client IP address, or "unknown" when called outside a Flask
            request context (library / test usage).

        Batch 1 Stream D fix — previously `request.headers` would raise
        RuntimeError("Working outside of request context") when the rate
        limiter was exercised in a pytest unit test that does not wrap
        the call in a Flask test_request_context. The integration test
        at tests/integration/test_web_ui_complete.py::TestRateLimiting
        Integration::test_rate_limit_check relies on the library-level
        path here.
        """
        try:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                return forwarded.split(",")[0].strip()
            return request.remote_addr or "unknown"
        except RuntimeError:
            # No active request context — library / test usage.
            return "unknown"

    def _cleanup_old_entries(self) -> None:
        """Clean up old timestamp entries."""
        now = datetime.now(timezone.utc)
        if (now - self.last_cleanup).total_seconds() < self.cleanup_interval:
            return

        cutoff = now - timedelta(hours=1)
        keys_to_delete = []

        for key in self.request_times.keys():
            self.request_times[key] = [
                ts for ts in self.request_times[key] if ts > cutoff
            ]
            if not self.request_times[key]:
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self.request_times[key]

        self.last_cleanup = now

    def check_rate_limit(
        self,
        endpoint: str,
        max_requests: int,
        window_seconds: int
    ) -> Tuple[bool, int, int]:
        """Check if request is within rate limit.

        Args:
            endpoint: Endpoint identifier.
            max_requests: Maximum requests allowed.
            window_seconds: Time window in seconds.

        Returns:
            Tuple of (allowed: bool, remaining_requests: int, retry_after_seconds: int).
        """
        self._cleanup_old_entries()

        client_ip = self._get_client_ip()
        key = (client_ip, endpoint)
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=window_seconds)

        # Initialize request times for this client/endpoint
        if key not in self.request_times:
            self.request_times[key] = []

        # Remove requests outside window
        self.request_times[key] = [
            ts for ts in self.request_times[key] if ts > cutoff
        ]

        current_count = len(self.request_times[key])
        allowed = current_count < max_requests

        if allowed:
            # Record this request
            self.request_times[key].append(now)
            remaining = max_requests - current_count - 1
            return True, remaining, 0
        else:
            # Calculate retry-after (when oldest request expires)
            oldest = self.request_times[key][0]
            retry_after = int((oldest - cutoff).total_seconds()) + 1
            return False, 0, max(1, retry_after)

    def rate_limit_decorator(
        self,
        endpoint: Optional[str] = None,
        max_requests: Optional[int] = None,
        window_seconds: Optional[int] = None
    ) -> Callable:
        """Decorator for rate limiting Flask endpoints.

        Args:
            endpoint: Endpoint identifier (auto if None).
            max_requests: Max requests (10 for POST/PUT/DELETE, 100 for GET if None).
            window_seconds: Time window (60 seconds if None).

        Returns:
            Decorator function.
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Determine endpoint
                ep = endpoint or f"{request.method}_{request.path}"

                # Determine limits
                if max_requests is None:
                    # Stricter limits for state-changing operations
                    if request.method in ("POST", "PUT", "DELETE"):
                        max_req = 5  # 5 requests per minute
                    else:
                        max_req = 100  # 100 requests per minute for GET
                else:
                    max_req = max_requests

                window = window_seconds or 60

                # Check rate limit
                allowed, remaining, retry_after = self.check_rate_limit(
                    ep, max_req, window
                )

                # If limit exceeded, return 429
                if not allowed:
                    response = jsonify({
                        "error": "Rate limit exceeded",
                        "message": f"Maximum {max_req} requests per {window} seconds",
                        "retry_after": retry_after,
                    })
                    response.status_code = 429
                    response.headers["Retry-After"] = str(retry_after)
                    response.headers["X-RateLimit-Limit"] = str(max_req)
                    response.headers["X-RateLimit-Remaining"] = "0"
                    response.headers["X-RateLimit-Reset"] = str(
                        int(datetime.now(timezone.utc).timestamp()) + retry_after
                    )
                    logger.warning(
                        "Rate limit exceeded for %s from %s",
                        ep, self._get_client_ip()
                    )
                    return response

                # Call the function
                result = func(*args, **kwargs)

                # Add rate limit headers to response
                if isinstance(result, Response):
                    response = result
                elif isinstance(result, tuple):
                    # Handle (data, status, headers) tuples
                    if len(result) == 3:
                        response = jsonify(result[0])
                        response.status_code = result[1]
                        for key, value in result[2].items():
                            response.headers[key] = value
                    else:
                        response = jsonify(result[0])
                        response.status_code = result[1]
                else:
                    response = jsonify(result) if isinstance(result, dict) else result

                # Add rate limit headers
                response.headers["X-RateLimit-Limit"] = str(max_req)
                response.headers["X-RateLimit-Remaining"] = str(remaining)
                response.headers["X-RateLimit-Reset"] = str(
                    int(datetime.now(timezone.utc).timestamp()) + window
                )

                return response

            return wrapper
        return decorator


# Global instance
_global_limiter = EndpointRateLimiter()


def get_rate_limiter() -> EndpointRateLimiter:
    """Get global rate limiter instance.

    Returns:
        Global EndpointRateLimiter.
    """
    return _global_limiter


def rate_limit(
    endpoint: Optional[str] = None,
    max_requests: Optional[int] = None,
    window_seconds: Optional[int] = None
) -> Callable:
    """Rate limit decorator.

    Usage:
        @app.route('/api/data')
        @rate_limit(max_requests=10, window_seconds=60)
        def get_data():
            return {"data": "..."}

    Args:
        endpoint: Endpoint ID (auto if None).
        max_requests: Max requests (auto-determined if None).
        window_seconds: Time window in seconds (default 60).

    Returns:
        Decorator function.
    """
    return _global_limiter.rate_limit_decorator(
        endpoint=endpoint,
        max_requests=max_requests,
        window_seconds=window_seconds
    )
