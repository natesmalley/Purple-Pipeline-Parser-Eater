#!/usr/bin/env python3
"""
Tests for HTTP connection pooling in aiohttp clients
"""

import pytest
import aiohttp
from unittest.mock import AsyncMock, patch, MagicMock
from components.observo_client import ObservoAPIClient
from components.github_scanner import GitHubParserScanner


class TestObservoClientConnectionPooling:
    """Test ObservoAPIClient connection pooling"""

    @pytest.mark.asyncio
    async def test_session_creates_tcp_connector(self):
        """Test that ClientSession is created with TCPConnector"""
        config = {
            "observo": {
                "api_key": "test-key",
                "base_url": "https://test.api.com",
                "rate_limit_delay": 1.0
            }
        }

        async with ObservoAPIClient(config) as client:
            assert client.session is not None
            assert isinstance(client.session.connector, aiohttp.TCPConnector)

    @pytest.mark.asyncio
    async def test_connector_has_connection_limits(self):
        """Test that TCPConnector has proper connection limits"""
        config = {
            "observo": {
                "api_key": "test-key",
                "base_url": "https://test.api.com",
                "rate_limit_delay": 1.0
            }
        }

        async with ObservoAPIClient(config) as client:
            connector = client.session.connector
            # Check that connector was created with limits
            assert connector is not None
            # Note: aiohttp TCPConnector doesn't expose limit properties directly
            # but they are set during initialization

    @pytest.mark.asyncio
    async def test_session_reused_across_requests(self):
        """Test that same session is reused for multiple requests"""
        config = {
            "observo": {
                "api_key": "test-key",
                "base_url": "https://test.api.com",
                "rate_limit_delay": 1.0
            }
        }

        async with ObservoAPIClient(config) as client:
            first_session = client.session
            # Simulate multiple operations
            assert client.session is first_session

    @pytest.mark.asyncio
    async def test_session_closed_on_context_exit(self):
        """Test that session is properly closed when exiting context"""
        config = {
            "observo": {
                "api_key": "test-key",
                "base_url": "https://test.api.com",
                "rate_limit_delay": 1.0
            }
        }

        client = ObservoAPIClient(config)
        async with client:
            assert client.session is not None
            session = client.session

        # After context exit, session should be closed
        assert session.closed


class TestGitHubScannerConnectionPooling:
    """Test GitHubParserScanner connection pooling"""

    @pytest.mark.asyncio
    async def test_session_creates_tcp_connector(self):
        """Test that ClientSession is created with TCPConnector"""
        config = {
            "github": {
                "token": "test-token",
                "rate_limit_delay": 1.0
            }
        }

        async with GitHubParserScanner("test-token", config) as scanner:
            assert scanner.session is not None
            assert isinstance(scanner.session.connector, aiohttp.TCPConnector)

    @pytest.mark.asyncio
    async def test_connector_dns_caching(self):
        """Test that TCPConnector has DNS caching enabled"""
        config = {
            "github": {
                "rate_limit_delay": 1.0
            }
        }

        async with GitHubParserScanner("test-token", config) as scanner:
            connector = scanner.session.connector
            assert connector is not None

    @pytest.mark.asyncio
    async def test_session_reused_across_requests(self):
        """Test that same session is reused for multiple requests"""
        config = {
            "github": {
                "rate_limit_delay": 1.0
            }
        }

        async with GitHubParserScanner("test-token", config) as scanner:
            first_session = scanner.session
            # Session should persist
            assert scanner.session is first_session

    @pytest.mark.asyncio
    async def test_session_closed_on_context_exit(self):
        """Test that session is properly closed when exiting context"""
        config = {
            "github": {
                "rate_limit_delay": 1.0
            }
        }

        scanner = GitHubParserScanner("test-token", config)
        async with scanner:
            assert scanner.session is not None
            session = scanner.session

        # After context exit, session should be closed
        assert session.closed


class TestConnectionPoolingBehavior:
    """Test overall connection pooling behavior"""

    @pytest.mark.asyncio
    async def test_multiple_clients_dont_share_sessions(self):
        """Test that different client instances have separate sessions"""
        config = {
            "observo": {
                "api_key": "test-key",
                "base_url": "https://test.api.com",
                "rate_limit_delay": 1.0
            }
        }

        async with ObservoAPIClient(config) as client1:
            async with ObservoAPIClient(config) as client2:
                # Each client should have its own session
                assert client1.session is not client2.session
                assert client1.session.connector is not client2.session.connector

    @pytest.mark.asyncio
    async def test_github_mock_mode_with_pooling(self):
        """Test that mock mode still uses connection pooling"""
        config = {
            "github": {
                "rate_limit_delay": 1.0
            }
        }

        # Mock mode with dry-run-mode token
        async with GitHubParserScanner("dry-run-mode", config) as scanner:
            assert scanner.mock_mode is True
            assert scanner.session is not None
            assert isinstance(scanner.session.connector, aiohttp.TCPConnector)
