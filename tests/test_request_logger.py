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
        """Test sanitizing long values."""
        logger = RequestLogger()
        sanitized = logger.sanitize_value("sk-ant-abcdef1234567890")
        assert "***" in sanitized
        assert "sk-ant-abc" in sanitized

    def test_sanitize_value_short(self) -> None:
        """Test sanitizing short values."""
        logger = RequestLogger()
        sanitized = logger.sanitize_value("abc")
        assert sanitized == "***"

    def test_sanitize_data_bearer_token(self) -> None:
        """Test sanitizing Bearer token."""
        logger = RequestLogger()
        data = "Authorization: Bearer sk-ant-abcdef1234567890"
        sanitized = logger.sanitize_data(data)
        assert "Bearer sk-ant-abc..." in sanitized

    def test_sanitize_data_api_key(self) -> None:
        """Test sanitizing API key."""
        logger = RequestLogger()
        data = '{"api_key": "1234567890abcdef"}'
        sanitized = logger.sanitize_data(data)
        assert "1234567890..." in sanitized

    def test_sanitize_data_password(self) -> None:
        """Test sanitizing password."""
        logger = RequestLogger()
        data = '{"password": "secretpassword123"}'
        sanitized = logger.sanitize_data(data)
        assert "secret..." in sanitized

    def test_sanitize_data_multiple_patterns(self) -> None:
        """Test sanitizing multiple sensitive values."""
        logger = RequestLogger()
        data = (
            '{"token": "token123456789", '
            '"secret": "secretvalue123", '
            '"normal": "value"}'
        )
        sanitized = logger.sanitize_data(data)
        assert "token123..." in sanitized
        assert "secretv..." in sanitized
        assert "normal" in sanitized
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
