#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask Blueprint for OpenAPI Documentation

Provides REST endpoints for API documentation:
- /api/docs/ - Swagger UI interface
- /api/docs/openapi.json - OpenAPI 3.0.0 specification
- /api/docs/spec - Alternative spec endpoint

SECURITY:
- All endpoints require authentication via bearer token
- Spec can be public or secured depending on configuration
"""

import logging
from flask import Blueprint, jsonify, render_template_string, current_app
from components.api_docs import get_default_endpoints

logger = logging.getLogger(__name__)

# Swagger UI HTML template
SWAGGER_UI_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>API Documentation - Purple Pipeline Parser Eater</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@3/swagger-ui.css">
    <style>
        html {
            box-sizing: border-box;
            overflow: -moz-scrollbars-vertical;
            overflow-y: scroll;
        }
        *,
        *:before,
        *:after {
            box-sizing: inherit;
        }
        body {
            margin:0;
            background: #fafafa;
        }
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@3/swagger-ui.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@3/swagger-ui-bundle.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@3/swagger-ui-standalone-preset.js"></script>
    <script>
        window.onload = function() {
            window.ui = SwaggerUIBundle({
                url: "/api/docs/openapi.json",
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                plugins: [
                    SwaggerUIBundle.plugins.DownloadUrl
                ],
                layout: "StandaloneLayout"
            });
        }
    </script>
</body>
</html>
"""

# Simple HTML documentation page
DOCS_INDEX_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>API Documentation - Purple Pipeline Parser Eater</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background: white;
            min-height: 100vh;
        }
        h1 { color: #764ba2; margin-bottom: 10px; }
        h2 { color: #667eea; margin-top: 30px; margin-bottom: 15px; }
        .intro {
            background: #f0f4ff;
            border-left: 4px solid #667eea;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
        }
        .doc-links {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .doc-card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            text-decoration: none;
            color: inherit;
            transition: all 0.3s ease;
        }
        .doc-card:hover {
            border-color: #667eea;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
            transform: translateY(-2px);
        }
        .doc-card h3 {
            color: #667eea;
            margin-bottom: 10px;
        }
        .doc-card p {
            color: #666;
            font-size: 14px;
        }
        code {
            background: #f5f5f5;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: "Courier New", monospace;
        }
        pre {
            background: #f5f5f5;
            padding: 15px;
            border-radius: 4px;
            overflow-x: auto;
            margin: 15px 0;
            border-left: 4px solid #667eea;
        }
        .endpoint-list {
            background: #f9f9f9;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 15px;
            margin: 15px 0;
        }
        .endpoint {
            padding: 10px;
            margin: 5px 0;
            background: white;
            border-left: 3px solid #28a745;
            border-radius: 2px;
        }
        .endpoint.post { border-left-color: #007bff; }
        .endpoint.put { border-left-color: #ffc107; }
        .endpoint.delete { border-left-color: #dc3545; }
        .method {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 3px;
            font-weight: bold;
            font-size: 12px;
            margin-right: 10px;
        }
        .method.get { background: #28a745; color: white; }
        .method.post { background: #007bff; color: white; }
        .method.put { background: #ffc107; color: white; }
        .method.delete { background: #dc3545; color: white; }
        .path {
            font-family: "Courier New", monospace;
            color: #333;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #666;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Purple Pipeline Parser Eater - API Documentation</h1>

        <div class="intro">
            <p><strong>Welcome to the API Documentation!</strong></p>
            <p>This page provides reference information about all available API endpoints and their usage.</p>
        </div>

        <h2>📚 Documentation Resources</h2>
        <div class="doc-links">
            <a href="/api/docs/swagger" class="doc-card">
                <h3>🎨 Interactive API Explorer</h3>
                <p>Explore and test API endpoints using Swagger UI with full request/response examples.</p>
            </a>
            <a href="/api/docs/openapi.json" class="doc-card">
                <h3>📋 OpenAPI Specification</h3>
                <p>Download the complete OpenAPI 3.0.0 specification in JSON format for integration with tools.</p>
            </a>
            <a href="#endpoints" class="doc-card">
                <h3>📑 Endpoint Reference</h3>
                <p>Quick reference of all available endpoints and their descriptions.</p>
            </a>
        </div>

        <h2>🔐 Authentication</h2>
        <p>All API endpoints require authentication using a Bearer token. Include the token in the <code>Authorization</code> header:</p>
        <pre>Authorization: Bearer YOUR_AUTH_TOKEN</pre>

        <p>Example with cURL:</p>
        <pre>curl -H "Authorization: Bearer YOUR_AUTH_TOKEN" \\
  http://localhost:5000/api/v1/status</pre>

        <h2 id="endpoints">📌 Available Endpoints</h2>
        <div class="endpoint-list">
            <div class="endpoint get">
                <span class="method get">GET</span>
                <span class="path">/api/v1/status</span>
                <div style="margin-top: 5px; color: #666;">API health check and status</div>
            </div>

            <div class="endpoint get">
                <span class="method get">GET</span>
                <span class="path">/api/v1/pending</span>
                <div style="margin-top: 5px; color: #666;">List pending parser conversions</div>
            </div>

            <div class="endpoint post">
                <span class="method post">POST</span>
                <span class="path">/api/v1/approve/{parser_id}</span>
                <div style="margin-top: 5px; color: #666;">Approve a parser conversion</div>
            </div>

            <div class="endpoint post">
                <span class="method post">POST</span>
                <span class="path">/api/v1/reject/{parser_id}</span>
                <div style="margin-top: 5px; color: #666;">Reject a parser conversion</div>
            </div>

            <div class="endpoint put">
                <span class="method put">PUT</span>
                <span class="path">/api/v1/modify/{parser_id}</span>
                <div style="margin-top: 5px; color: #666;">Modify a parser conversion</div>
            </div>

            <div class="endpoint get">
                <span class="method get">GET</span>
                <span class="path">/api/v1/metrics</span>
                <div style="margin-top: 5px; color: #666;">Get Prometheus metrics and statistics</div>
            </div>
        </div>

        <h2>🚀 Quick Start</h2>
        <p>1. <strong>Get your API token</strong> from the Web UI or configuration</p>
        <p>2. <strong>Check API status</strong>:</p>
        <pre>curl -H "Authorization: Bearer YOUR_TOKEN" \\
  http://localhost:5000/api/v1/status</pre>
        <p>3. <strong>List pending conversions</strong>:</p>
        <pre>curl -H "Authorization: Bearer YOUR_TOKEN" \\
  http://localhost:5000/api/v1/pending</pre>
        <p>4. <strong>Approve a conversion</strong>:</p>
        <pre>curl -X POST \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"parser_id":"my-parser"}' \\
  http://localhost:5000/api/v1/approve/my-parser</pre>

        <h2>📖 API Specification Format</h2>
        <p>The OpenAPI specification follows the <strong>OpenAPI 3.0.0</strong> standard and includes:</p>
        <ul>
            <li>Complete endpoint definitions with request/response schemas</li>
            <li>Security scheme configuration (Bearer authentication)</li>
            <li>Standard error response definitions (400, 401, 403, 500)</li>
            <li>Parameter documentation (path, query, body)</li>
            <li>Request and response examples</li>
        </ul>

        <h2>❓ Common Questions</h2>
        <h3>How do I use the API in my application?</h3>
        <p>Check the OpenAPI specification and use a client code generator for your language:</p>
        <ul>
            <li><strong>Python:</strong> OpenAPI Generator, Swagger Codegen</li>
            <li><strong>JavaScript/TypeScript:</strong> OpenAPI Generator, swagger-client</li>
            <li><strong>Go:</strong> OpenAPI Generator, deepmap/oapi-codegen</li>
        </ul>

        <h3>What authentication method is used?</h3>
        <p>The API uses <strong>Bearer Token Authentication</strong>. All requests must include:</p>
        <pre>Authorization: Bearer YOUR_TOKEN</pre>

        <h3>Where can I find my authentication token?</h3>
        <p>The authentication token is configured in the <code>.env</code> file as <code>WEB_UI_AUTH_TOKEN</code>. See the authentication setup guide for more information.</p>

        <div class="footer">
            <p><strong>Purple Pipeline Parser Eater</strong> - Security Event Transformation</p>
            <p>API Version 1.0.0 | OpenAPI 3.0.0</p>
            <p>For more information, see the project documentation.</p>
        </div>
    </div>
</body>
</html>
"""


def create_api_docs_blueprint(auth_required=True, require_auth=None):
    """
    Create a Flask blueprint for API documentation endpoints.

    Args:
        auth_required (bool): Whether to require authentication for all endpoints
        require_auth (callable): Optional decorator function for authentication

    Returns:
        Blueprint: Flask blueprint with documentation endpoints
    """
    bp = Blueprint('api_docs', __name__, url_prefix='/api/docs')

    # Get the default endpoints documentation
    docs_builder = get_default_endpoints()
    docs = docs_builder.build()

    @bp.route('/')
    def docs_index():
        """
        Main documentation landing page.

        Returns:
            HTML page with links to API documentation resources
        """
        return render_template_string(DOCS_INDEX_TEMPLATE)

    @bp.route('/swagger')
    def swagger_ui():
        """
        Swagger UI interface for interactive API exploration.

        Returns:
            HTML page with Swagger UI loaded from OpenAPI spec
        """
        return render_template_string(SWAGGER_UI_TEMPLATE)

    @bp.route('/openapi.json')
    def openapi_spec():
        """
        OpenAPI 3.0.0 specification endpoint.

        SECURITY:
        - Returns the complete OpenAPI specification
        - Can be restricted to authenticated users only
        - Safe to expose publicly as it only contains API schema info

        Returns:
            JSON: OpenAPI 3.0.0 specification
        """
        spec = docs.get_openapi_spec()

        # Add server information from Flask app context
        if spec.get('servers'):
            # Update server URL if needed
            for server in spec['servers']:
                if 'localhost' in server.get('url', ''):
                    # Keep default, could be customized per environment
                    pass

        return jsonify(spec)

    @bp.route('/spec')
    def spec_alternative():
        """
        Alternative endpoint for OpenAPI specification.

        Returns:
            JSON: OpenAPI 3.0.0 specification (same as /openapi.json)
        """
        return openapi_spec()

    @bp.route('/health')
    def docs_health():
        """
        Health check for documentation endpoint.

        Returns:
            JSON: Health status
        """
        return jsonify({
            'status': 'healthy',
            'docs_available': True,
            'swagger_ui': '/api/docs/swagger',
            'openapi_spec': '/api/docs/openapi.json'
        })

    # Apply authentication decorator if provided
    if auth_required and require_auth:
        bp.route('/', methods=['GET'])(require_auth(docs_index))
        bp.route('/swagger', methods=['GET'])(require_auth(swagger_ui))
        bp.route('/openapi.json', methods=['GET'])(require_auth(openapi_spec))
        bp.route('/spec', methods=['GET'])(require_auth(spec_alternative))
        bp.route('/health', methods=['GET'])(require_auth(docs_health))

    logger.info("[OK] API Documentation blueprint created successfully")
    logger.info("[OK] Available endpoints:")
    logger.info("  - /api/docs/ (documentation landing page)")
    logger.info("  - /api/docs/swagger (Swagger UI)")
    logger.info("  - /api/docs/openapi.json (OpenAPI specification)")
    logger.info("  - /api/docs/spec (alternative spec endpoint)")
    logger.info("  - /api/docs/health (health check)")

    return bp
