"""Tests for OpenAPI/Swagger API documentation.

Tests the api_docs module for proper OpenAPI schema generation,
endpoint documentation, and specification compliance.
"""

import pytest
from components.api_docs import (
    OpenAPIDocumentation,
    APIDocumentationBuilder,
    get_default_endpoints
)


class TestOpenAPIDocumentation:
    """Tests for OpenAPIDocumentation class."""

    def test_initialization(self):
        """Test OpenAPI documentation initialization."""
        docs = OpenAPIDocumentation(version="1.0.0")

        assert docs.version == "1.0.0"
        assert docs.endpoints == {}

    def test_register_single_endpoint(self):
        """Test registering a single endpoint."""
        docs = OpenAPIDocumentation()

        docs.register_endpoint(
            path="/api/v1/status",
            method="GET",
            summary="Get Status",
            description="Returns API status"
        )

        assert len(docs.endpoints) == 1
        assert "GET /api/v1/status" in docs.endpoints

    def test_register_multiple_endpoints(self):
        """Test registering multiple endpoints."""
        docs = OpenAPIDocumentation()

        docs.register_endpoint("/api/v1/status", "GET", "Get Status", "Status endpoint")
        docs.register_endpoint("/api/v1/health", "GET", "Health Check", "Health endpoint")
        docs.register_endpoint("/api/v1/metrics", "GET", "Get Metrics", "Metrics endpoint")

        assert len(docs.endpoints) == 3

    def test_endpoint_registration_with_parameters(self):
        """Test endpoint registration with parameters."""
        docs = OpenAPIDocumentation()

        parameters = [
            {
                "name": "limit",
                "in": "query",
                "schema": {"type": "integer"},
                "description": "Result limit"
            }
        ]

        docs.register_endpoint(
            path="/api/v1/list",
            method="GET",
            summary="List Items",
            description="List all items",
            parameters=parameters
        )

        endpoint = docs.endpoints["GET /api/v1/list"]
        assert endpoint["parameters"] == parameters

    def test_endpoint_registration_with_models(self):
        """Test endpoint registration with request/response models."""
        docs = OpenAPIDocumentation()

        request_model = {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            }
        }

        response_model = {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"}
            }
        }

        docs.register_endpoint(
            path="/api/v1/items",
            method="POST",
            summary="Create Item",
            description="Create a new item",
            request_model=request_model,
            response_model=response_model
        )

        endpoint = docs.endpoints["POST /api/v1/items"]
        assert endpoint["request_model"] == request_model
        assert endpoint["response_model"] == response_model

    def test_openapi_spec_generation(self):
        """Test OpenAPI specification generation."""
        docs = OpenAPIDocumentation(version="2.0.0")

        docs.register_endpoint(
            "/api/v1/test",
            "GET",
            "Test Endpoint",
            "A test endpoint"
        )

        spec = docs.get_openapi_spec()

        assert spec["openapi"] == "3.0.0"
        assert spec["info"]["version"] == "2.0.0"
        assert spec["info"]["title"] == "Purple Pipeline Parser Eater API"
        assert "paths" in spec
        assert "components" in spec

    def test_openapi_spec_security_schemes(self):
        """Test OpenAPI security schemes."""
        docs = OpenAPIDocumentation()
        spec = docs.get_openapi_spec()

        assert "components" in spec
        assert "securitySchemes" in spec["components"]
        assert "BearerAuth" in spec["components"]["securitySchemes"]

    def test_openapi_spec_schemas(self):
        """Test OpenAPI component schemas."""
        docs = OpenAPIDocumentation()
        spec = docs.get_openapi_spec()

        schemas = spec["components"]["schemas"]
        assert "StatusResponse" in schemas
        assert "ErrorResponse" in schemas

    def test_endpoint_with_security_required(self):
        """Test endpoint with security requirement."""
        docs = OpenAPIDocumentation()

        docs.register_endpoint(
            "/secure",
            "GET",
            "Secure Endpoint",
            "Requires authentication",
            security_required=True
        )

        endpoint = docs.endpoints["GET /secure"]
        assert endpoint["security_required"] is True

    def test_endpoint_with_security_not_required(self):
        """Test endpoint without security requirement."""
        docs = OpenAPIDocumentation()

        docs.register_endpoint(
            "/public",
            "GET",
            "Public Endpoint",
            "No authentication required",
            security_required=False
        )

        endpoint = docs.endpoints["GET /public"]
        assert endpoint["security_required"] is False

    def test_endpoint_with_tags(self):
        """Test endpoint with tags."""
        docs = OpenAPIDocumentation()

        docs.register_endpoint(
            "/api/v1/users",
            "GET",
            "List Users",
            "Get all users",
            tags=["Users", "Public"]
        )

        endpoint = docs.endpoints["GET /api/v1/users"]
        assert endpoint["tags"] == ["Users", "Public"]

    def test_to_dict_export(self):
        """Test exporting documentation as dictionary."""
        docs = OpenAPIDocumentation()

        docs.register_endpoint(
            "/test",
            "GET",
            "Test",
            "Test endpoint"
        )

        spec_dict = docs.to_dict()

        assert isinstance(spec_dict, dict)
        assert "openapi" in spec_dict
        assert "info" in spec_dict
        assert "paths" in spec_dict


class TestAPIDocumentationBuilder:
    """Tests for APIDocumentationBuilder class."""

    def test_builder_initialization(self):
        """Test builder initialization."""
        builder = APIDocumentationBuilder(version="1.5.0")

        assert builder.docs.version == "1.5.0"

    def test_builder_add_endpoint(self):
        """Test adding endpoint via builder."""
        builder = APIDocumentationBuilder()

        result = builder.add_endpoint(
            path="/test",
            method="GET",
            summary="Test",
            description="Test endpoint"
        )

        # Should return self for chaining
        assert result is builder
        assert len(builder.docs.endpoints) == 1

    def test_builder_chaining(self):
        """Test method chaining in builder."""
        builder = (
            APIDocumentationBuilder()
            .add_endpoint("/api/v1/a", "GET", "A", "Endpoint A")
            .add_endpoint("/api/v1/b", "POST", "B", "Endpoint B")
            .add_endpoint("/api/v1/c", "DELETE", "C", "Endpoint C")
        )

        assert len(builder.docs.endpoints) == 3

    def test_builder_build(self):
        """Test building documentation."""
        builder = APIDocumentationBuilder(version="2.0.0")

        builder.add_endpoint("/test", "GET", "Test", "Test endpoint")

        docs = builder.build()

        assert isinstance(docs, OpenAPIDocumentation)
        assert docs.version == "2.0.0"
        assert len(docs.endpoints) == 1


class TestDefaultEndpoints:
    """Tests for default endpoint documentation."""

    def test_get_default_endpoints(self):
        """Test getting default endpoints."""
        builder = get_default_endpoints()

        assert isinstance(builder, APIDocumentationBuilder)
        assert len(builder.docs.endpoints) > 0

    def test_default_endpoints_include_status(self):
        """Test that default endpoints include status endpoint."""
        builder = get_default_endpoints()
        docs = builder.build()

        assert "GET /api/v1/status" in docs.endpoints

    def test_default_endpoints_include_pending(self):
        """Test that default endpoints include pending endpoint."""
        builder = get_default_endpoints()
        docs = builder.build()

        assert "GET /api/v1/pending" in docs.endpoints

    def test_default_endpoints_include_approve(self):
        """Test that default endpoints include approve endpoint."""
        builder = get_default_endpoints()
        docs = builder.build()

        assert "POST /api/v1/approve/{parser_id}" in docs.endpoints

    def test_default_endpoints_include_reject(self):
        """Test that default endpoints include reject endpoint."""
        builder = get_default_endpoints()
        docs = builder.build()

        assert "POST /api/v1/reject/{parser_id}" in docs.endpoints

    def test_default_endpoints_include_modify(self):
        """Test that default endpoints include modify endpoint."""
        builder = get_default_endpoints()
        docs = builder.build()

        assert "PUT /api/v1/modify/{parser_id}" in docs.endpoints

    def test_default_endpoints_include_metrics(self):
        """Test that default endpoints include metrics endpoint."""
        builder = get_default_endpoints()
        docs = builder.build()

        assert "GET /api/v1/metrics" in docs.endpoints

    def test_default_endpoints_have_descriptions(self):
        """Test that all default endpoints have descriptions."""
        builder = get_default_endpoints()
        docs = builder.build()

        for endpoint_key, endpoint_info in docs.endpoints.items():
            assert endpoint_info["summary"]
            assert endpoint_info["description"]

    def test_default_endpoints_security_settings(self):
        """Test security settings on default endpoints."""
        builder = get_default_endpoints()
        docs = builder.build()

        # Most endpoints should require security
        secure_endpoints = [
            "GET /api/v1/status",
            "GET /api/v1/pending",
            "POST /api/v1/approve/{parser_id}",
            "POST /api/v1/reject/{parser_id}",
            "PUT /api/v1/modify/{parser_id}"
        ]

        for endpoint_key in secure_endpoints:
            assert docs.endpoints[endpoint_key]["security_required"] is True

        # Metrics endpoint should not require security
        assert docs.endpoints["GET /api/v1/metrics"]["security_required"] is False


class TestOpenAPISpecCompliance:
    """Tests for OpenAPI specification compliance."""

    def test_openapi_version(self):
        """Test OpenAPI version is 3.0.0."""
        docs = OpenAPIDocumentation()
        spec = docs.get_openapi_spec()

        assert spec["openapi"] == "3.0.0"

    def test_spec_has_required_fields(self):
        """Test spec has all required OpenAPI fields."""
        docs = OpenAPIDocumentation()
        spec = docs.get_openapi_spec()

        required_fields = ["openapi", "info", "servers", "paths"]
        for field in required_fields:
            assert field in spec

    def test_spec_info_has_required_fields(self):
        """Test info object has required fields."""
        docs = OpenAPIDocumentation()
        spec = docs.get_openapi_spec()

        required_fields = ["title", "version"]
        for field in required_fields:
            assert field in spec["info"]

    def test_spec_servers_configured(self):
        """Test servers are properly configured."""
        docs = OpenAPIDocumentation()
        spec = docs.get_openapi_spec()

        assert "servers" in spec
        assert len(spec["servers"]) > 0
        assert spec["servers"][0]["url"] == "http://localhost:5000"

    def test_spec_has_error_responses(self):
        """Test that 401, 403, 400, 500 error responses are defined."""
        docs = OpenAPIDocumentation()
        docs.register_endpoint("/test", "GET", "Test", "Test endpoint")
        spec = docs.get_openapi_spec()

        test_response = spec["paths"]["/test"]["get"]["responses"]

        error_codes = ["400", "401", "403", "500"]
        for code in error_codes:
            assert code in test_response


class TestEndpointDocumentation:
    """Tests for individual endpoint documentation."""

    def test_endpoint_with_path_parameters(self):
        """Test endpoint with path parameters."""
        docs = OpenAPIDocumentation()

        parameters = [
            {
                "name": "parser_id",
                "in": "path",
                "required": True,
                "schema": {"type": "string"}
            }
        ]

        docs.register_endpoint(
            "/api/v1/parsers/{parser_id}",
            "GET",
            "Get Parser",
            "Get specific parser",
            parameters=parameters
        )

        endpoint = docs.endpoints["GET /api/v1/parsers/{parser_id}"]
        assert len(endpoint["parameters"]) == 1
        assert endpoint["parameters"][0]["name"] == "parser_id"

    def test_endpoint_with_query_parameters(self):
        """Test endpoint with query parameters."""
        docs = OpenAPIDocumentation()

        parameters = [
            {
                "name": "limit",
                "in": "query",
                "schema": {"type": "integer", "default": 20}
            },
            {
                "name": "offset",
                "in": "query",
                "schema": {"type": "integer", "default": 0}
            }
        ]

        docs.register_endpoint(
            "/api/v1/parsers",
            "GET",
            "List Parsers",
            "List all parsers with pagination",
            parameters=parameters
        )

        endpoint = docs.endpoints["GET /api/v1/parsers"]
        assert len(endpoint["parameters"]) == 2

    def test_post_endpoint_with_request_body(self):
        """Test POST endpoint with request body."""
        docs = OpenAPIDocumentation()

        request_model = {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"}
            }
        }

        docs.register_endpoint(
            "/api/v1/parsers",
            "POST",
            "Create Parser",
            "Create a new parser",
            request_model=request_model
        )

        spec = docs.get_openapi_spec()
        post_spec = spec["paths"]["/api/v1/parsers"]["post"]

        assert "requestBody" in post_spec
        assert "application/json" in post_spec["requestBody"]["content"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
