"""OpenAPI/Swagger API documentation for Purple Pipeline.

Provides auto-generated API documentation with interactive Swagger UI.
Uses Flask-RESTX for OpenAPI schema generation and endpoint documentation.

Usage:
    from components.api_docs import create_api_docs

    app = Flask(__name__)
    api = create_api_docs(app)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class OpenAPIDocumentation:
    """Manages OpenAPI/Swagger documentation for the API.

    Features:
    - Auto-generated API documentation
    - Interactive Swagger UI
    - OpenAPI schema generation
    - Request/response examples
    - Authentication documentation
    """

    def __init__(self, app: Optional[Any] = None, version: str = "1.0.0"):
        """Initialize OpenAPI documentation.

        Args:
            app: Flask application instance
            version: API version
        """
        self.app = app
        self.version = version
        self.endpoints: Dict[str, Dict[str, Any]] = {}

        logger.info(f"OpenAPIDocumentation initialized (version={version})")

    def register_endpoint(
        self,
        path: str,
        method: str,
        summary: str,
        description: str,
        request_model: Optional[Dict] = None,
        response_model: Optional[Dict] = None,
        parameters: Optional[list] = None,
        examples: Optional[Dict] = None,
        tags: Optional[list] = None,
        security_required: bool = True
    ) -> None:
        """Register an endpoint for documentation.

        Args:
            path: API path (e.g., "/api/v1/status")
            method: HTTP method (GET, POST, etc.)
            summary: Short endpoint summary
            description: Detailed description
            request_model: Request body schema
            response_model: Response schema
            parameters: Query/path parameters
            examples: Request/response examples
            tags: API tags for grouping
            security_required: Whether authentication is required
        """
        key = f"{method} {path}"

        self.endpoints[key] = {
            "path": path,
            "method": method,
            "summary": summary,
            "description": description,
            "request_model": request_model,
            "response_model": response_model,
            "parameters": parameters or [],
            "examples": examples or {},
            "tags": tags or ["General"],
            "security_required": security_required
        }

        logger.debug(f"Registered endpoint: {key}")

    def get_openapi_spec(self) -> Dict[str, Any]:
        """Generate OpenAPI 3.0.0 specification.

        Returns:
            Dictionary containing complete OpenAPI specification
        """
        spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "Purple Pipeline Parser Eater API",
                "version": self.version,
                "description": "API for managing security event parsers and transformations",
                "contact": {
                    "name": "Purple Pipeline Team",
                    "url": "https://github.com/jhexiS1/Purple-Pipline-Parser-Eater"
                },
                "license": {
                    "name": "MIT",
                    "url": "https://opensource.org/licenses/MIT"
                }
            },
            "servers": [
                {
                    "url": "http://localhost:5000",
                    "description": "Development server"
                },
                {
                    "url": "http://localhost:5000",
                    "description": "Local server"
                }
            ],
            "components": self._get_components(),
            "paths": self._get_paths(),
            "tags": self._get_tags()
        }

        return spec

    def _get_components(self) -> Dict[str, Any]:
        """Get OpenAPI components (schemas, security, etc.)."""
        return {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": "API access token in Authorization header"
                }
            },
            "schemas": {
                "StatusResponse": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "version": {"type": "string"},
                        "timestamp": {"type": "string"}
                    }
                },
                "ErrorResponse": {
                    "type": "object",
                    "properties": {
                        "error": {"type": "string"},
                        "details": {"type": "string"},
                        "code": {"type": "integer"}
                    }
                }
            }
        }

    def _get_paths(self) -> Dict[str, Any]:
        """Get OpenAPI paths from registered endpoints."""
        paths = {}

        for endpoint_key, endpoint_info in self.endpoints.items():
            path = endpoint_info["path"]
            method = endpoint_info["method"].lower()

            if path not in paths:
                paths[path] = {}

            paths[path][method] = {
                "summary": endpoint_info["summary"],
                "description": endpoint_info["description"],
                "tags": endpoint_info["tags"],
                "parameters": endpoint_info["parameters"],
                "responses": self._get_responses(endpoint_info),
                "security": [{"BearerAuth": []}] if endpoint_info["security_required"] else []
            }

            if endpoint_info["request_model"]:
                paths[path][method]["requestBody"] = {
                    "content": {
                        "application/json": {
                            "schema": endpoint_info["request_model"]
                        }
                    }
                }

        return paths

    def _get_responses(self, endpoint_info: Dict) -> Dict[str, Any]:
        """Get response specifications for endpoint."""
        responses = {
            "200": {
                "description": "Success",
                "content": {
                    "application/json": {
                        "schema": endpoint_info["response_model"] or {"type": "object"}
                    }
                }
            },
            "401": {
                "description": "Unauthorized - Invalid or missing authentication token",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                    }
                }
            },
            "403": {
                "description": "Forbidden - Insufficient permissions",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                    }
                }
            },
            "400": {
                "description": "Bad Request - Invalid parameters",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                    }
                }
            },
            "500": {
                "description": "Internal Server Error",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                    }
                }
            }
        }

        return responses

    def _get_tags(self) -> list:
        """Get API tags for grouping endpoints."""
        tags_set = set()
        for endpoint_info in self.endpoints.values():
            tags_set.update(endpoint_info["tags"])

        return [{"name": tag} for tag in sorted(tags_set)]

    def to_dict(self) -> Dict[str, Any]:
        """Export documentation as dictionary."""
        return self.get_openapi_spec()


class APIDocumentationBuilder:
    """Builder for creating and managing API documentation.

    Simplifies the process of registering endpoints and generating docs.
    """

    def __init__(self, version: str = "1.0.0"):
        """Initialize builder.

        Args:
            version: API version
        """
        self.docs = OpenAPIDocumentation(version=version)

    def add_endpoint(
        self,
        path: str,
        method: str,
        summary: str,
        description: str,
        **kwargs
    ) -> APIDocumentationBuilder:
        """Add endpoint documentation.

        Args:
            path: API path
            method: HTTP method
            summary: Short summary
            description: Detailed description
            **kwargs: Additional endpoint parameters

        Returns:
            Self for chaining
        """
        self.docs.register_endpoint(path, method, summary, description, **kwargs)
        return self

    def build(self) -> OpenAPIDocumentation:
        """Build and return documentation object.

        Returns:
            OpenAPIDocumentation instance
        """
        return self.docs


# Default API endpoints documentation
def get_default_endpoints() -> APIDocumentationBuilder:
    """Create documentation for default API endpoints.

    Returns:
        APIDocumentationBuilder with pre-configured endpoints
    """
    builder = APIDocumentationBuilder(version="1.0.0")

    # Health/Status endpoints
    builder.add_endpoint(
        path="/api/v1/status",
        method="GET",
        summary="Get API Status",
        description="Returns the current status of the Purple Pipeline API",
        response_model={
            "type": "object",
            "properties": {
                "status": {"type": "string", "example": "healthy"},
                "version": {"type": "string", "example": "1.0.0"},
                "timestamp": {"type": "string", "format": "date-time"},
                "uptime_seconds": {"type": "number"}
            }
        },
        tags=["System"],
        security_required=True
    )

    # Pending conversions
    builder.add_endpoint(
        path="/api/v1/pending",
        method="GET",
        summary="List Pending Conversions",
        description="Get list of parsers pending approval",
        parameters=[
            {
                "name": "status",
                "in": "query",
                "schema": {"type": "string", "enum": ["pending", "approved", "rejected"]},
                "description": "Filter by status"
            },
            {
                "name": "limit",
                "in": "query",
                "schema": {"type": "integer", "default": 20},
                "description": "Maximum results to return"
            }
        ],
        response_model={
            "type": "object",
            "properties": {
                "parsers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "status": {"type": "string"},
                            "created_at": {"type": "string", "format": "date-time"}
                        }
                    }
                },
                "total": {"type": "integer"}
            }
        },
        tags=["Parsers"],
        security_required=True
    )

    # Approve conversion
    builder.add_endpoint(
        path="/api/v1/approve/{parser_id}",
        method="POST",
        summary="Approve Parser Conversion",
        description="Approve a pending parser conversion",
        parameters=[
            {
                "name": "parser_id",
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
                "description": "Parser identifier"
            }
        ],
        request_model={
            "type": "object",
            "properties": {
                "notes": {"type": "string", "description": "Approval notes"}
            }
        },
        response_model={
            "type": "object",
            "properties": {
                "parser_id": {"type": "string"},
                "status": {"type": "string", "example": "approved"},
                "message": {"type": "string"}
            }
        },
        tags=["Parsers"],
        security_required=True
    )

    # Reject conversion
    builder.add_endpoint(
        path="/api/v1/reject/{parser_id}",
        method="POST",
        summary="Reject Parser Conversion",
        description="Reject a pending parser conversion",
        parameters=[
            {
                "name": "parser_id",
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
                "description": "Parser identifier"
            }
        ],
        request_model={
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Rejection reason"}
            }
        },
        response_model={
            "type": "object",
            "properties": {
                "parser_id": {"type": "string"},
                "status": {"type": "string", "example": "rejected"},
                "message": {"type": "string"}
            }
        },
        tags=["Parsers"],
        security_required=True
    )

    # Modify conversion
    builder.add_endpoint(
        path="/api/v1/modify/{parser_id}",
        method="PUT",
        summary="Modify Parser Conversion",
        description="Modify a pending or approved parser conversion",
        parameters=[
            {
                "name": "parser_id",
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
                "description": "Parser identifier"
            }
        ],
        request_model={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "settings": {"type": "object"}
            }
        },
        response_model={
            "type": "object",
            "properties": {
                "parser_id": {"type": "string"},
                "status": {"type": "string"},
                "message": {"type": "string"}
            }
        },
        tags=["Parsers"],
        security_required=True
    )

    # Metrics endpoint
    builder.add_endpoint(
        path="/api/v1/metrics",
        method="GET",
        summary="Get Prometheus Metrics",
        description="Get Prometheus-formatted metrics",
        response_model={
            "type": "string",
            "description": "Prometheus metrics format"
        },
        tags=["Monitoring"],
        security_required=False
    )

    return builder


# Export for use in applications
__all__ = [
    "OpenAPIDocumentation",
    "APIDocumentationBuilder",
    "get_default_endpoints"
]
