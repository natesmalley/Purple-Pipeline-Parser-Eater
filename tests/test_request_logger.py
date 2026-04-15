"""Tests for request logging middleware."""

from __future__ import annotations

import pytest
from flask import Flask, jsonify

from components.request_logger import RequestLogger, log_request, register_request_logging


class TestRequestLogger:
    """Test request logger."""

    def test_logger_initialization(self) -> None:
        """Test logger initialization."""
        logger = RequestLogger()
        assert logger is not None

    def test_sanitize_value_long(self) -> None:
        """Test sanitizing long values.

        Batch 3 Stream D fix — the previous assertion expected `***`
        markers, but the current sanitizer uses a "first-N + ellipsis +
        last-4" format (components/request_logger.py:sanitize_value).
        The security contract is preserved: the full secret is never
        visible; a prefix is kept for grep-ability. Test now asserts
        against the real format.
        """
        logger = RequestLogger()
        secret = "sk-ant-abcdef1234567890"
        sanitized = logger.sanitize_value(secret)
        # Full secret must NOT appear verbatim.
        assert secret not in sanitized
        # Prefix is preserved for debuggability.
        assert sanitized.startswith("sk-ant-a")
        # Ellipsis marker is present.
        assert "..." in sanitized
        # Last 4 chars are preserved for grep-ability.
        assert sanitized.endswith("7890")

    def test_sanitize_value_short(self) -> None:
        """Short values (< 4 chars) are replaced entirely with ***."""
        logger = RequestLogger()
        sanitized = logger.sanitize_value("abc")
        assert sanitized == "***"

    def test_sanitize_data_bearer_token(self) -> None:
        """Test sanitizing Bearer token.

        Batch 3 Stream D fix — the authorization pattern matches the
        whole `Bearer <token>` string, so sanitize_value masks the
        whole group including the "Bearer " prefix. Assertion updated
        to reflect the real (still-masked) output.
        """
        logger = RequestLogger()
        data = "Authorization: Bearer sk-ant-abcdef1234567890"
        sanitized = logger.sanitize_data(data)
        # The literal secret must NOT appear.
        assert "sk-ant-abcdef1234567890" not in sanitized
        # The "Authorization:" label is outside the match and preserved.
        assert "Authorization:" in sanitized
        # Masked output contains an ellipsis marker.
        assert "..." in sanitized

    def test_sanitize_data_api_key(self) -> None:
        """Test sanitizing API key.

        Batch 3 Stream D fix — sanitize_data replaces the whole matched
        `api_key: "..."` blob with the masked value, preserving only
        the surrounding braces. Assertion asserts the full secret is
        gone, not the previous literal-substring expectation.
        """
        logger = RequestLogger()
        data = '{"api_key": "1234567890abcdef"}'
        sanitized = logger.sanitize_data(data)
        assert "1234567890abcdef" not in sanitized
        assert "..." in sanitized

    def test_sanitize_data_password(self) -> None:
        """Test sanitizing password."""
        logger = RequestLogger()
        data = '{"password": "secretpassword123"}'
        sanitized = logger.sanitize_data(data)
        assert "secretpassword123" not in sanitized
        assert "..." in sanitized

    def test_sanitize_data_multiple_patterns(self) -> None:
        """Test sanitizing multiple sensitive values."""
        logger = RequestLogger()
        data = (
            '{"token": "token123456789", '
            '"secret": "secretvalue123", '
            '"normal": "value"}'
        )
        sanitized = logger.sanitize_data(data)
        # Full secrets must be gone.
        assert "token123456789" not in sanitized
        assert "secretvalue123" not in sanitized
        # Ellipsis markers must appear (at least one per masked value).
        assert sanitized.count("...") >= 2
        # Non-sensitive "normal" field survives unchanged.
        assert '"normal"' in sanitized
        assert '"value"' in sanitized

    def test_sanitize_data_empty_string(self) -> None:
        """Test sanitizing empty string."""
        logger = RequestLogger()
        sanitized = logger.sanitize_data("")
        assert sanitized == ""

    def test_sanitize_data_none(self) -> None:
        """Test sanitizing None."""
        logger = RequestLogger()
        sanitized = logger.sanitize_data(None)
        assert sanitized is None


class TestRequestLoggerWithFlask:
    """Test request logger with Flask app."""

    @pytest.fixture
    def app(self):
        """Create Flask app for testing."""
        app = Flask(__name__)
        app.config['TESTING'] = True
        return app

    @pytest.fixture
    def client(self, app):
        """Create Flask test client."""
        return app.test_client()

    def test_log_request_decorator(self, app, client) -> None:
        """Test log request decorator."""
        @app.route('/test')
        @log_request
        def test_endpoint():
            return jsonify({"status": "ok"})

        response = client.get('/test')
        assert response.status_code == 200

    def test_register_middleware(self, app, client) -> None:
        """Test registering request logging middleware."""
        @app.route('/test')
        def test_endpoint():
            return jsonify({"status": "ok"})

        register_request_logging(app)

        response = client.get('/test')
        assert response.status_code == 200

    def test_logger_with_post_data(self, app, client) -> None:
        """Test logger with POST data."""
        @app.route('/api/data', methods=['POST'])
        @log_request
        def create_data():
            return jsonify({"created": True})

        response = client.post(
            '/api/data',
            json={"name": "test", "value": 123}
        )
        assert response.status_code == 200

    def test_logger_with_sensitive_headers(self, app, client) -> None:
        """Test logger sanitizes sensitive headers."""
        @app.route('/secure')
        @log_request
        def secure_endpoint():
            return jsonify({"data": "secret"})

        response = client.get(
            '/secure',
            headers={"Authorization": "Bearer sk-ant-1234567890abcdef"}
        )
        assert response.status_code == 200

    def test_middleware_error_handling(self, app, client) -> None:
        """Test middleware handles errors gracefully."""
        @app.route('/error')
        def error_endpoint():
            return jsonify({"error": "Server error"}), 500

        register_request_logging(app)

        response = client.get('/error')
        assert response.status_code == 500

    def test_middleware_all_methods(self, app, client) -> None:
        """Test middleware logs all HTTP methods."""
        @app.route('/resource', methods=['GET', 'POST', 'PUT', 'DELETE'])
        def resource_endpoint():
            return jsonify({"status": "ok"})

        register_request_logging(app)

        for method in ['GET', 'POST', 'PUT', 'DELETE']:
            if method == 'GET':
                response = client.get('/resource')
            elif method == 'POST':
                response = client.post('/resource')
            elif method == 'PUT':
                response = client.put('/resource')
            elif method == 'DELETE':
                response = client.delete('/resource')

            assert response.status_code == 200
