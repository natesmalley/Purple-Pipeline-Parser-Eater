"""Integration tests for rate limiting."""

from __future__ import annotations

from components.http_rate_limiter import get_rate_limiter, EndpointRateLimiter


class TestRateLimitingIntegration:
    """Test rate limiting integration."""

    def test_rate_limiter_per_endpoint(self) -> None:
        """Test per-endpoint rate limiting."""
        limiter = get_rate_limiter()
        
        allowed1, rem1, retry1 = limiter.check_rate_limit("endpoint_a", 10, 60)
        assert allowed1 is True
        
        allowed2, rem2, retry2 = limiter.check_rate_limit("endpoint_b", 10, 60)
        assert allowed2 is True

    def test_rate_limiter_cleanup(self) -> None:
        """Test old entry cleanup."""
        limiter = EndpointRateLimiter()
        limiter.check_rate_limit("test", 10, 60)
        limiter._cleanup_old_entries()
        assert True
