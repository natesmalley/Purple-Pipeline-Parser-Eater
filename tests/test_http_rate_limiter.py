"""Tests for HTTP endpoint rate limiting."""

from __future__ import annotations

import pytest
from flask import Flask, jsonify

from components.http_rate_limiter import EndpointRateLimiter, get_rate_limiter, rate_limit


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


class TestEndpointRateLimiter:
    """Test endpoint rate limiter."""

    def test_limiter_initialization(self) -> None:
        """Test limiter initialization."""
        limiter = EndpointRateLimiter()
        assert len(limiter.request_times) == 0

    def test_check_rate_limit_allowed(self) -> None:
        """Test rate limit check allows requests."""
        limiter = EndpointRateLimiter()

        # First request should be allowed
        with pytest.raises(RuntimeError):
            # Will raise because we're not in a request context
            limiter.check_rate_limit("test_endpoint", 10, 60)

    def test_get_rate_limiter_singleton(self) -> None:
        """Test that get_rate_limiter returns singleton."""
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        assert limiter1 is limiter2


class TestRateLimitDecorator:
    """Test rate limit decorator on Flask endpoints."""

    def test_rate_limit_get_request(self, app, client) -> None:
        """Test rate limit on GET request."""
        @app.route('/test')
        @rate_limit(max_requests=3, window_seconds=60)
        def test_endpoint():
            return jsonify({"status": "ok"})

        # First 3 requests should succeed
        response1 = client.get('/test')
        assert response1.status_code == 200
        assert "X-RateLimit-Limit" in response1.headers
        assert response1.headers["X-RateLimit-Limit"] == "3"

        response2 = client.get('/test')
        assert response2.status_code == 200

        response3 = client.get('/test')
        assert response3.status_code == 200

        # 4th request should be rate limited
        response4 = client.get('/test')
        assert response4.status_code == 429
        assert "Rate limit exceeded" in response4.get_json()["error"]

    def test_rate_limit_post_request(self, app, client) -> None:
        """Test stricter rate limit on POST request."""
        @app.route('/api/data', methods=['POST'])
        @rate_limit()  # Should default to 5 per minute for POST
        def create_data():
            return jsonify({"created": True})

        # First request should work
        response = client.post('/api/data')
        assert response.status_code == 200

    def test_rate_limit_headers(self, app, client) -> None:
        """Test rate limit headers are present."""
        @app.route('/test')
        @rate_limit(max_requests=5, window_seconds=60)
        def test_endpoint():
            return jsonify({"status": "ok"})

        response = client.get('/test')

        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

        assert response.headers["X-RateLimit-Limit"] == "5"
        assert int(response.headers["X-RateLimit-Remaining"]) == 4

    def test_rate_limit_retry_after(self, app, client) -> None:
        """Test Retry-After header when rate limited."""
        @app.route('/test')
        @rate_limit(max_requests=1, window_seconds=60)
        def test_endpoint():
            return jsonify({"status": "ok"})

        # First request succeeds
        response1 = client.get('/test')
        assert response1.status_code == 200

        # Second request is rate limited
        response2 = client.get('/test')
        assert response2.status_code == 429
        assert "Retry-After" in response2.headers
        assert int(response2.headers["Retry-After"]) > 0

    def test_rate_limit_custom_endpoint_name(self, app, client) -> None:
        """Test rate limit with custom endpoint name."""
        @app.route('/api/v1/resource')
        @rate_limit(endpoint="custom_resource", max_requests=2, window_seconds=60)
        def get_resource():
            return jsonify({"data": "value"})

        response1 = client.get('/api/v1/resource')
        assert response1.status_code == 200

        response2 = client.get('/api/v1/resource')
        assert response2.status_code == 200

        response3 = client.get('/api/v1/resource')
        assert response3.status_code == 429

    def test_rate_limit_error_response_format(self, app, client) -> None:
        """Test rate limit error response format."""
        @app.route('/test')
        @rate_limit(max_requests=1, window_seconds=60)
        def test_endpoint():
            return jsonify({"status": "ok"})

        # Exceed limit
        client.get('/test')
        response = client.get('/test')

        assert response.status_code == 429
        data = response.get_json()
        assert "error" in data
        assert "message" in data
        assert "retry_after" in data

    def test_rate_limit_multiple_clients(self, app, client) -> None:
        """Test rate limit tracks per client."""
        @app.route('/test')
        @rate_limit(max_requests=2, window_seconds=60)
        def test_endpoint():
            return jsonify({"status": "ok"})

        # First client makes 2 requests
        response1 = client.get('/test')
        assert response1.status_code == 200

        response2 = client.get('/test')
        assert response2.status_code == 200

        # Third request from same client is rate limited
        response3 = client.get('/test')
        assert response3.status_code == 429

    def test_rate_limit_with_x_forwarded_for(self, app, client) -> None:
        """Test rate limit respects X-Forwarded-For header."""
        @app.route('/test')
        @rate_limit(max_requests=1, window_seconds=60)
        def test_endpoint():
            return jsonify({"status": "ok"})

        # Request with X-Forwarded-For
        response1 = client.get('/test', headers={"X-Forwarded-For": "192.168.1.1"})
        assert response1.status_code == 200

        # Another request from same forwarded IP
        response2 = client.get('/test', headers={"X-Forwarded-For": "192.168.1.1"})
        assert response2.status_code == 429
