#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for API Versioning Implementation.

Tests the API versioning functionality including:
- Versioned route prefixes (/api/v1/)
- API version headers in responses
- Backwards compatibility considerations
"""

import pytest
import json
import asyncio
from unittest.mock import Mock, MagicMock, patch
from flask import Flask
from components.web_ui import WebFeedbackServer


@pytest.fixture
def mock_config():
    """Create a mock configuration for WebFeedbackServer."""
    return {
        'web_ui': {
            'host': '127.0.0.1',
            'port': 5000,
            'auth_token': 'test-token-12345',
            'token_header': 'X-PPPE-Token',
            'tls': {'enabled': False}
        },
        'app_env': 'development'
    }


@pytest.fixture
def mock_feedback_queue():
    """Create a mock feedback queue."""
    queue = asyncio.Queue()
    return queue


@pytest.fixture
def mock_service():
    """Create a mock service."""
    service = Mock()
    service.get_status.return_value = {'status': 'healthy', 'pending_conversions': 0}
    service.pending_conversions = {}
    service.approved_conversions = {}
    service.rejected_conversions = {}
    service.modified_conversions = {}
    return service


@pytest.fixture
def event_loop():
    """Create an event loop for async testing."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def web_server(mock_config, mock_feedback_queue, mock_service, event_loop):
    """Create a WebFeedbackServer instance for testing."""
    server = WebFeedbackServer(
        config=mock_config,
        feedback_queue=mock_feedback_queue,
        service=mock_service,
        event_loop=event_loop
    )
    return server


@pytest.fixture
def client(web_server):
    """Create a Flask test client."""
    return web_server.app.test_client()


class TestAPIVersioningRoutes:
    """Tests for API versioning route structure."""

    def test_status_endpoint_uses_v1_prefix(self, client):
        """Test that status endpoint uses /api/v1/ prefix."""
        response = client.get(
            '/api/v1/status',
            headers={'X-PPPE-Token': 'test-token-12345'}
        )
        # Should be 200 or 401, not 404
        assert response.status_code != 404

    def test_pending_endpoint_uses_v1_prefix(self, client):
        """Test that pending endpoint uses /api/v1/ prefix."""
        response = client.get(
            '/api/v1/pending',
            headers={'X-PPPE-Token': 'test-token-12345'}
        )
        assert response.status_code != 404

    def test_approve_endpoint_uses_v1_prefix(self, client):
        """Test that approve endpoint uses /api/v1/ prefix."""
        response = client.post(
            '/api/v1/approve',
            headers={'X-PPPE-Token': 'test-token-12345'},
            json={'parser_name': 'test'}
        )
        assert response.status_code != 404

    def test_reject_endpoint_uses_v1_prefix(self, client):
        """Test that reject endpoint uses /api/v1/ prefix."""
        response = client.post(
            '/api/v1/reject',
            headers={'X-PPPE-Token': 'test-token-12345'},
            json={'parser_name': 'test'}
        )
        assert response.status_code != 404

    def test_modify_endpoint_uses_v1_prefix(self, client):
        """Test that modify endpoint uses /api/v1/ prefix."""
        response = client.post(
            '/api/v1/modify',
            headers={'X-PPPE-Token': 'test-token-12345'},
            json={'parser_name': 'test', 'corrected_lua': 'code'}
        )
        assert response.status_code != 404

    def test_metrics_endpoint_uses_v1_prefix(self, client):
        """Test that metrics endpoint uses /api/v1/ prefix."""
        response = client.get('/api/v1/metrics')
        assert response.status_code != 404

    def test_old_api_routes_not_available(self, client):
        """Test that old /api/ routes (without version) return 404."""
        old_endpoints = [
            ('/api/status', 'GET'),
            ('/api/pending', 'GET'),
            ('/api/approve', 'POST'),
            ('/api/reject', 'POST'),
            ('/api/modify', 'POST'),
        ]

        for endpoint, method in old_endpoints:
            if method == 'GET':
                response = client.get(endpoint, headers={'X-PPPE-Token': 'test-token-12345'})
            else:
                response = client.post(
                    endpoint,
                    headers={'X-PPPE-Token': 'test-token-12345'},
                    json={}
                )
            assert response.status_code == 404, f"Old endpoint {endpoint} should return 404"


class TestAPIVersionHeaders:
    """Tests for API version header in responses."""

    def test_status_endpoint_includes_version_header(self, client):
        """Test that status endpoint response includes X-API-Version header."""
        response = client.get(
            '/api/v1/status',
            headers={'X-PPPE-Token': 'test-token-12345'}
        )
        assert 'X-API-Version' in response.headers
        assert response.headers['X-API-Version'] == '1.0.0'

    def test_pending_endpoint_includes_version_header(self, client):
        """Test that pending endpoint response includes X-API-Version header."""
        response = client.get(
            '/api/v1/pending',
            headers={'X-PPPE-Token': 'test-token-12345'}
        )
        assert 'X-API-Version' in response.headers
        assert response.headers['X-API-Version'] == '1.0.0'

    def test_metrics_endpoint_includes_version_header(self, client):
        """Test that metrics endpoint response includes X-API-Version header."""
        response = client.get('/api/v1/metrics')
        assert 'X-API-Version' in response.headers

    def test_html_responses_include_version_header(self, client):
        """Test that HTML responses also include X-API-Version header."""
        response = client.get(
            '/',
            headers={'X-PPPE-Token': 'test-token-12345'}
        )
        assert 'X-API-Version' in response.headers

    def test_version_header_format(self, client):
        """Test that X-API-Version header has correct format."""
        response = client.get(
            '/api/v1/status',
            headers={'X-PPPE-Token': 'test-token-12345'}
        )
        version = response.headers.get('X-API-Version')
        # Should be in format X.Y.Z
        assert version is not None
        parts = version.split('.')
        assert len(parts) == 3
        for part in parts:
            assert part.isdigit()


class TestAPIVersionCompliance:
    """Tests for API version specification compliance."""

    def test_v1_endpoints_return_json(self, client):
        """Test that v1 endpoints return JSON format."""
        response = client.get(
            '/api/v1/pending',
            headers={'X-PPPE-Token': 'test-token-12345'}
        )
        assert 'application/json' in response.content_type
        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_v1_endpoints_include_status_codes(self, client):
        """Test that v1 endpoints return appropriate HTTP status codes."""
        response = client.get(
            '/api/v1/status',
            headers={'X-PPPE-Token': 'test-token-12345'}
        )
        assert response.status_code in [200, 400, 401, 403, 500]

    def test_v1_error_responses_are_json(self, client):
        """Test that v1 error responses are JSON format."""
        response = client.get(
            '/api/v1/pending',
            headers={'X-PPPE-Token': 'invalid-token'}
        )
        # Should fail auth and return JSON error
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'error' in data


class TestAPIVersioningConsistency:
    """Tests for consistency across versioned endpoints."""

    def test_all_api_endpoints_use_same_version(self, client):
        """Test that all API endpoints use the same version."""
        endpoints = [
            ('/api/v1/status', 'GET'),
            ('/api/v1/pending', 'GET'),
            ('/api/v1/metrics', 'GET'),
        ]

        versions = set()
        for endpoint, method in endpoints:
            if method == 'GET':
                response = client.get(
                    endpoint,
                    headers={'X-PPPE-Token': 'test-token-12345'}
                    if 'metrics' not in endpoint else {}
                )
            versions.add(response.headers.get('X-API-Version'))

        # All should have the same version
        assert len(versions) == 1

    def test_version_persists_across_requests(self, client):
        """Test that API version remains consistent across multiple requests."""
        version = None
        for _ in range(3):
            response = client.get(
                '/api/v1/status',
                headers={'X-PPPE-Token': 'test-token-12345'}
            )
            if version is None:
                version = response.headers.get('X-API-Version')
            else:
                assert response.headers.get('X-API-Version') == version


class TestMetricsEndpoint:
    """Tests for the metrics endpoint."""

    def test_metrics_endpoint_exists(self, client):
        """Test that /api/v1/metrics endpoint exists."""
        response = client.get('/api/v1/metrics')
        assert response.status_code != 404

    def test_metrics_endpoint_returns_prometheus_format(self, client):
        """Test that metrics endpoint returns Prometheus format."""
        response = client.get('/api/v1/metrics')
        content = response.data.decode('utf-8')
        # Should contain Prometheus metric format
        assert '#' in content  # Comments

    def test_metrics_endpoint_no_auth_required(self, client):
        """Test that metrics endpoint does not require authentication."""
        response = client.get('/api/v1/metrics')
        # Should return 200 or 500 (service error), not 401
        assert response.status_code != 401


class TestRuntimeEndpoints:
    """Tests for runtime-related endpoints with v1 prefix."""

    def test_runtime_status_endpoint_uses_v1(self, client):
        """Test that runtime status endpoint uses /api/v1/ prefix."""
        response = client.get(
            '/api/v1/runtime/status',
            headers={'X-PPPE-Token': 'test-token-12345'}
        )
        assert response.status_code != 404

    def test_runtime_reload_endpoint_uses_v1(self, client):
        """Test that runtime reload endpoint uses /api/v1/ prefix."""
        response = client.post(
            '/api/v1/runtime/reload/test-parser',
            headers={'X-PPPE-Token': 'test-token-12345'}
        )
        assert response.status_code != 404

    def test_runtime_canary_endpoint_uses_v1(self, client):
        """Test that runtime canary endpoint uses /api/v1/ prefix."""
        response = client.post(
            '/api/v1/runtime/canary/test-parser/promote',
            headers={'X-PPPE-Token': 'test-token-12345'}
        )
        assert response.status_code != 404


class TestAPIVersioningBackwardsCompatibility:
    """Tests for backwards compatibility considerations."""

    def test_version_header_helps_clients_identify_version(self, client):
        """Test that clients can identify API version from header."""
        response = client.get(
            '/api/v1/status',
            headers={'X-PPPE-Token': 'test-token-12345'}
        )
        # Client can check X-API-Version header to handle compatibility
        assert 'X-API-Version' in response.headers
        version = response.headers.get('X-API-Version')
        assert version is not None

    def test_future_versioning_possible(self, client):
        """Test that future API versions could coexist."""
        # /api/v1/ endpoints should exist
        response = client.get(
            '/api/v1/status',
            headers={'X-PPPE-Token': 'test-token-12345'}
        )
        assert response.status_code != 404
        # /api/v2/ endpoints would not exist yet (404 is expected)
        response = client.get(
            '/api/v2/status',
            headers={'X-PPPE-Token': 'test-token-12345'}
        )
        assert response.status_code == 404


class TestAPIVersioningDocumentation:
    """Tests for API versioning in documentation."""

    def test_openapi_spec_reflects_v1_version(self, client):
        """Test that OpenAPI spec reflects API v1 routes."""
        response = client.get(
            '/api/docs/openapi.json',
            headers={'X-PPPE-Token': 'test-token-12345'}
        )
        spec = json.loads(response.data)

        # Check that paths use /api/v1/ prefix
        paths = spec.get('paths', {})
        v1_paths = [p for p in paths.keys() if '/api/v1/' in p]

        assert len(v1_paths) > 0, "OpenAPI spec should include /api/v1/ paths"


class TestVersionedResponseStructure:
    """Tests for response structure in v1 API."""

    def test_v1_status_response_structure(self, client):
        """Test that v1 status endpoint returns expected response structure."""
        response = client.get(
            '/api/v1/status',
            headers={'X-PPPE-Token': 'test-token-12345'}
        )

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, dict)

    def test_v1_pending_response_structure(self, client):
        """Test that v1 pending endpoint returns expected response structure."""
        response = client.get(
            '/api/v1/pending',
            headers={'X-PPPE-Token': 'test-token-12345'}
        )

        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'pending' in data
            assert isinstance(data['pending'], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
