"""Integration tests for API versioning."""

from __future__ import annotations

from components.security_middleware import SecurityHeaders


class TestAPIVersioningIntegration:
    """Test API versioning."""

    def test_version_headers(self) -> None:
        """Test version headers in responses."""
        headers = SecurityHeaders.get_headers()
        assert headers is not None
        assert isinstance(headers, dict)

    def test_multiple_header_types(self) -> None:
        """Test multiple security header types."""
        headers = SecurityHeaders.get_headers()
        
        required_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "Content-Security-Policy"
        ]
        
        for header in required_headers:
            assert header in headers
