#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the API Documentation Blueprint.

Tests the Flask blueprint integration for OpenAPI documentation endpoints,
including Swagger UI, spec generation, and documentation pages.
"""

import pytest
import json
from flask import Flask
from components.api_docs_blueprint import create_api_docs_blueprint


@pytest.fixture
def flask_app():
    """Create a Flask app for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def flask_app_with_auth(flask_app):
    """Create a Flask app with simple authentication."""
    def require_auth(func):
        def wrapper(*args, **kwargs):
            # In tests, don't require auth
            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        return wrapper

    return flask_app, require_auth


@pytest.fixture
def client_with_blueprint(flask_app_with_auth):
    """Create a Flask test client with the docs blueprint registered."""
    app, require_auth = flask_app_with_auth

    # Create and register the blueprint without auth requirement
    bp = create_api_docs_blueprint(auth_required=False)
    app.register_blueprint(bp)

    return app.test_client()


@pytest.fixture
def client_with_auth_blueprint(flask_app_with_auth):
    """Create a Flask test client with authenticated docs blueprint."""
    app, require_auth = flask_app_with_auth

    # Create and register the blueprint with auth
    bp = create_api_docs_blueprint(auth_required=True, require_auth=require_auth)
    app.register_blueprint(bp)

    return app.test_client()


class TestApiDocsBlueprintEndpoints:
    """Tests for API documentation blueprint endpoints."""

    def test_docs_index_endpoint(self, client_with_blueprint):
        """Test documentation landing page endpoint."""
        response = client_with_blueprint.get('/api/docs/')

        assert response.status_code == 200
        assert 'text/html' in response.content_type
        assert b'Purple Pipeline Parser Eater' in response.data
        assert b'API Documentation' in response.data

    def test_swagger_ui_endpoint(self, client_with_blueprint):
        """Test Swagger UI endpoint."""
        response = client_with_blueprint.get('/api/docs/swagger')

        assert response.status_code == 200
        assert 'text/html' in response.content_type
        assert b'swagger-ui' in response.data
        assert b'/api/docs/openapi.json' in response.data

    def test_openapi_spec_endpoint(self, client_with_blueprint):
        """Test OpenAPI specification endpoint."""
        response = client_with_blueprint.get('/api/docs/openapi.json')

        assert response.status_code == 200
        assert 'application/json' in response.content_type

        # Verify it's valid JSON
        spec = json.loads(response.data)

        # Verify OpenAPI structure
        assert 'openapi' in spec
        assert spec['openapi'] == '3.0.0'
        assert 'info' in spec
        assert 'paths' in spec
        assert 'components' in spec

    def test_openapi_spec_alternative_endpoint(self, client_with_blueprint):
        """Test alternative OpenAPI specification endpoint."""
        response = client_with_blueprint.get('/api/docs/spec')

        assert response.status_code == 200
        assert 'application/json' in response.content_type

        # Verify it's the same as /openapi.json
        spec = json.loads(response.data)
        assert 'openapi' in spec
        assert spec['openapi'] == '3.0.0'

    def test_docs_health_endpoint(self, client_with_blueprint):
        """Test documentation health check endpoint."""
        response = client_with_blueprint.get('/api/docs/health')

        assert response.status_code == 200
        assert 'application/json' in response.content_type

        data = json.loads(response.data)
        assert data['status'] == 'healthy'
        assert data['docs_available'] is True
        assert 'swagger_ui' in data
        assert 'openapi_spec' in data


class TestOpenAPISpecContent:
    """Tests for the content of the OpenAPI specification."""

    def test_spec_contains_required_fields(self, client_with_blueprint):
        """Test that spec contains all required OpenAPI fields."""
        response = client_with_blueprint.get('/api/docs/openapi.json')
        spec = json.loads(response.data)

        required_fields = ['openapi', 'info', 'servers', 'paths', 'components']
        for field in required_fields:
            assert field in spec, f"Missing required field: {field}"

    def test_spec_info_section(self, client_with_blueprint):
        """Test the info section of the spec."""
        response = client_with_blueprint.get('/api/docs/openapi.json')
        spec = json.loads(response.data)

        info = spec['info']
        assert 'title' in info
        assert 'version' in info
        assert 'Purple Pipeline Parser Eater' in info['title']

    def test_spec_has_default_endpoints(self, client_with_blueprint):
        """Test that spec includes default endpoints."""
        response = client_with_blueprint.get('/api/docs/openapi.json')
        spec = json.loads(response.data)

        paths = spec['paths']

        # Check for expected endpoints
        expected_endpoints = [
            '/api/v1/status',
            '/api/v1/pending',
            '/api/v1/approve/{parser_id}',
            '/api/v1/reject/{parser_id}',
            '/api/v1/modify/{parser_id}',
            '/api/v1/metrics'
        ]

        for endpoint in expected_endpoints:
            assert endpoint in paths, f"Missing endpoint: {endpoint}"

    def test_spec_security_schemes(self, client_with_blueprint):
        """Test that spec defines security schemes."""
        response = client_with_blueprint.get('/api/docs/openapi.json')
        spec = json.loads(response.data)

        components = spec['components']
        assert 'securitySchemes' in components
        assert 'BearerAuth' in components['securitySchemes']

        bearer = components['securitySchemes']['BearerAuth']
        assert bearer['type'] == 'http'
        assert bearer['scheme'] == 'bearer'

    def test_spec_has_error_schemas(self, client_with_blueprint):
        """Test that spec defines error response schemas."""
        response = client_with_blueprint.get('/api/docs/openapi.json')
        spec = json.loads(response.data)

        schemas = spec['components']['schemas']
        assert 'ErrorResponse' in schemas
        assert 'StatusResponse' in schemas

    def test_spec_paths_have_methods(self, client_with_blueprint):
        """Test that all paths have HTTP methods defined."""
        response = client_with_blueprint.get('/api/docs/openapi.json')
        spec = json.loads(response.data)

        paths = spec['paths']
        for path, methods in paths.items():
            assert isinstance(methods, dict)
            # Each path should have at least one method
            assert len(methods) > 0

    def test_spec_methods_have_responses(self, client_with_blueprint):
        """Test that all methods define responses."""
        response = client_with_blueprint.get('/api/docs/openapi.json')
        spec = json.loads(response.data)

        paths = spec['paths']
        for path, methods in paths.items():
            for method, details in methods.items():
                if method in ['get', 'post', 'put', 'delete', 'patch']:
                    assert 'responses' in details
                    assert len(details['responses']) > 0


class TestDocumentationPage:
    """Tests for the documentation landing page content."""

    def test_docs_page_has_links(self, client_with_blueprint):
        """Test that docs page includes links to resources."""
        response = client_with_blueprint.get('/api/docs/')
        content = response.data.decode('utf-8')

        assert '/api/docs/swagger' in content
        assert '/api/docs/openapi.json' in content

    def test_docs_page_has_authentication_info(self, client_with_blueprint):
        """Test that docs page documents authentication."""
        response = client_with_blueprint.get('/api/docs/')
        content = response.data.decode('utf-8')

        assert 'Authentication' in content
        assert 'Bearer' in content
        assert 'Authorization' in content

    def test_docs_page_has_endpoint_reference(self, client_with_blueprint):
        """Test that docs page has endpoint reference section."""
        response = client_with_blueprint.get('/api/docs/')
        content = response.data.decode('utf-8')

        assert 'Available Endpoints' in content
        assert '/api/v1/status' in content
        assert '/api/v1/pending' in content

    def test_docs_page_has_quick_start(self, client_with_blueprint):
        """Test that docs page includes quick start guide."""
        response = client_with_blueprint.get('/api/docs/')
        content = response.data.decode('utf-8')

        assert 'Quick Start' in content
        assert 'curl' in content


class TestSwaggerUIPage:
    """Tests for the Swagger UI page."""

    def test_swagger_page_has_swagger_ui_bundle(self, client_with_blueprint):
        """Test that Swagger UI page loads required scripts."""
        response = client_with_blueprint.get('/api/docs/swagger')
        content = response.data.decode('utf-8')

        assert 'swagger-ui-dist' in content
        assert 'swagger-ui' in content

    def test_swagger_page_references_spec_url(self, client_with_blueprint):
        """Test that Swagger page references the spec endpoint."""
        response = client_with_blueprint.get('/api/docs/swagger')
        content = response.data.decode('utf-8')

        assert '/api/docs/openapi.json' in content


class TestBlueprintCreation:
    """Tests for the blueprint creation function."""

    def test_create_blueprint_without_auth(self):
        """Test creating blueprint without authentication."""
        bp = create_api_docs_blueprint(auth_required=False)

        assert bp is not None
        assert bp.name == 'api_docs'
        assert bp.url_prefix == '/api/docs'

    def test_create_blueprint_with_auth(self):
        """Test creating blueprint with authentication decorator."""
        def mock_auth(func):
            return func

        bp = create_api_docs_blueprint(auth_required=True, require_auth=mock_auth)

        assert bp is not None
        assert bp.name == 'api_docs'

    def test_blueprint_registration(self, flask_app):
        """Test that blueprint can be registered with Flask app."""
        bp = create_api_docs_blueprint(auth_required=False)
        flask_app.register_blueprint(bp)

        # Verify routes are registered
        routes = [str(rule) for rule in flask_app.url_map.iter_rules()]
        assert any('/api/docs/' in route for route in routes)


class TestEndpointResponses:
    """Tests for endpoint response structure and content."""

    def test_status_endpoint_in_spec(self, client_with_blueprint):
        """Test status endpoint in OpenAPI spec."""
        response = client_with_blueprint.get('/api/docs/openapi.json')
        spec = json.loads(response.data)

        status_path = spec['paths']['/api/v1/status']
        assert 'get' in status_path
        assert 'summary' in status_path['get']
        assert 'description' in status_path['get']

    def test_pending_endpoint_in_spec(self, client_with_blueprint):
        """Test pending endpoint in OpenAPI spec."""
        response = client_with_blueprint.get('/api/docs/openapi.json')
        spec = json.loads(response.data)

        pending_path = spec['paths']['/api/v1/pending']
        assert 'get' in pending_path

    def test_approve_endpoint_in_spec(self, client_with_blueprint):
        """Test approve endpoint in OpenAPI spec."""
        response = client_with_blueprint.get('/api/docs/openapi.json')
        spec = json.loads(response.data)

        approve_path = spec['paths']['/api/v1/approve/{parser_id}']
        assert 'post' in approve_path

    def test_reject_endpoint_in_spec(self, client_with_blueprint):
        """Test reject endpoint in OpenAPI spec."""
        response = client_with_blueprint.get('/api/docs/openapi.json')
        spec = json.loads(response.data)

        reject_path = spec['paths']['/api/v1/reject/{parser_id}']
        assert 'post' in reject_path

    def test_modify_endpoint_in_spec(self, client_with_blueprint):
        """Test modify endpoint in OpenAPI spec."""
        response = client_with_blueprint.get('/api/docs/openapi.json')
        spec = json.loads(response.data)

        modify_path = spec['paths']['/api/v1/modify/{parser_id}']
        assert 'put' in modify_path

    def test_metrics_endpoint_in_spec(self, client_with_blueprint):
        """Test metrics endpoint in OpenAPI spec."""
        response = client_with_blueprint.get('/api/docs/openapi.json')
        spec = json.loads(response.data)

        metrics_path = spec['paths']['/api/v1/metrics']
        assert 'get' in metrics_path


class TestContentTypes:
    """Tests for correct content type headers."""

    def test_docs_index_content_type(self, client_with_blueprint):
        """Test documentation index has correct content type."""
        response = client_with_blueprint.get('/api/docs/')
        assert 'text/html' in response.content_type

    def test_swagger_ui_content_type(self, client_with_blueprint):
        """Test Swagger UI has correct content type."""
        response = client_with_blueprint.get('/api/docs/swagger')
        assert 'text/html' in response.content_type

    def test_openapi_spec_content_type(self, client_with_blueprint):
        """Test OpenAPI spec has correct content type."""
        response = client_with_blueprint.get('/api/docs/openapi.json')
        assert 'application/json' in response.content_type

    def test_health_check_content_type(self, client_with_blueprint):
        """Test health check has correct content type."""
        response = client_with_blueprint.get('/api/docs/health')
        assert 'application/json' in response.content_type


class TestEndpointAccessibility:
    """Tests for endpoint accessibility."""

    def test_all_endpoints_accessible(self, client_with_blueprint):
        """Test that all documentation endpoints are accessible."""
        endpoints = [
            '/api/docs/',
            '/api/docs/swagger',
            '/api/docs/openapi.json',
            '/api/docs/spec',
            '/api/docs/health'
        ]

        for endpoint in endpoints:
            response = client_with_blueprint.get(endpoint)
            assert response.status_code == 200, f"Endpoint {endpoint} returned {response.status_code}"

    def test_nonexistent_endpoint_returns_404(self, client_with_blueprint):
        """Test that nonexistent endpoints return 404."""
        response = client_with_blueprint.get('/api/docs/nonexistent')
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
