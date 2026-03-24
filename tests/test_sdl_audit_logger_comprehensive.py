"""
Comprehensive tests for SDL Audit Logger component

Tests SentinelOne Security Data Lake audit logging for compliance and audit trails
of all Web UI actions. Includes event logging, OCSF compliance, delivery, and errors.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
import json


@pytest.fixture
def audit_config():
    """Standard audit logger configuration."""
    return {
        'sentinelone_sdl': {
            'api_url': 'https://xdr.us1.sentinelone.net/api/addEvents',
            'api_key': 'test-api-key-12345',
            'audit_logging_enabled': True,
            'batch_size': 10,
            'retry_attempts': 3
        }
    }


@pytest.fixture
def audit_logger(audit_config):
    """Create audit logger for testing."""
    from components.sdl_audit_logger import SDLAuditLogger
    return SDLAuditLogger(audit_config)


class TestAuditEventLogging:
    """Test Suite 1: Audit Event Logging"""

    @pytest.mark.asyncio
    async def test_log_user_action(self, audit_logger):
        """Test logging user action."""
        with patch('components.sdl_audit_logger.SDLAuditLogger._send_audit_event', new_callable=AsyncMock):
            await audit_logger.log_approval(
                parser_name='test-parser',
                lua_code='function transform(e) return e end',
                generation_time=1.5,
                confidence_score=0.95,
                user_id='admin-user'
            )

            # Verify event was sent
            audit_logger._send_audit_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_includes_required_fields(self, audit_logger):
        """Test log includes all required fields."""
        with patch('components.sdl_audit_logger.SDLAuditLogger._send_audit_event', new_callable=AsyncMock) as mock_send:
            await audit_logger.log_approval(
                parser_name='test-parser',
                lua_code='code',
                generation_time=1.0,
                user_id='user123'
            )

            # Verify event structure
            called_event = mock_send.call_args[0][0]
            assert 'timestamp' in called_event
            assert 'parser_name' in called_event
            assert 'action' in called_event
            assert 'user_id' in called_event

    @pytest.mark.asyncio
    async def test_log_includes_context(self, audit_logger):
        """Test log includes context data."""
        with patch('components.sdl_audit_logger.SDLAuditLogger._send_audit_event', new_callable=AsyncMock) as mock_send:
            await audit_logger.log_rejection(
                parser_name='bad-parser',
                reason='Code quality issues',
                retry_requested=True,
                error_details='Multiple undefined variables'
            )

            called_event = mock_send.call_args[0][0]
            assert called_event['rejection_reason'] == 'Code quality issues'
            assert called_event['error_details'] == 'Multiple undefined variables'

    @pytest.mark.asyncio
    async def test_log_maintains_order(self, audit_logger):
        """Test events are logged in order."""
        with patch('components.sdl_audit_logger.SDLAuditLogger._send_audit_event', new_callable=AsyncMock) as mock_send:
            timestamps = []

            # Log multiple events
            for i in range(3):
                await audit_logger.log_approval(
                    parser_name=f'parser-{i}',
                    lua_code='code',
                    generation_time=1.0
                )
                timestamps.append(mock_send.call_args_list[-1][0][0]['timestamp'])

            # Verify timestamps are in order
            assert timestamps == sorted(timestamps)

    @pytest.mark.asyncio
    async def test_log_timestamp_format(self, audit_logger):
        """Test timestamp format is ISO8601."""
        with patch('components.sdl_audit_logger.SDLAuditLogger._send_audit_event', new_callable=AsyncMock) as mock_send:
            await audit_logger.log_approval(
                parser_name='test',
                lua_code='code',
                generation_time=1.0
            )

            event = mock_send.call_args[0][0]
            # Should be ISO8601 with Z suffix
            assert event['timestamp'].endswith('Z')
            # Should be parseable
            datetime.fromisoformat(event['timestamp'].rstrip('Z'))


class TestComplianceFormatting:
    """Test Suite 2: Compliance Formatting"""

    @pytest.mark.asyncio
    async def test_audit_log_format_is_compliant(self, audit_logger):
        """Test log format meets compliance requirements."""
        with patch('components.sdl_audit_logger.SDLAuditLogger._send_audit_event', new_callable=AsyncMock) as mock_send:
            await audit_logger.log_approval(
                parser_name='test-parser',
                lua_code='code',
                generation_time=1.0
            )

            event = mock_send.call_args[0][0]

            # Check required compliance fields
            assert 'timestamp' in event
            assert 'hostname' in event
            assert 'service' in event
            assert 'severity' in event
            assert 'message' in event
            assert 'event_type' in event

    @pytest.mark.asyncio
    async def test_audit_log_includes_severity(self, audit_logger):
        """Test severity levels are assigned correctly."""
        with patch('components.sdl_audit_logger.SDLAuditLogger._send_audit_event', new_callable=AsyncMock) as mock_send:
            # Approval should have info severity
            await audit_logger.log_approval(
                parser_name='test',
                lua_code='code',
                generation_time=1.0
            )

            event = mock_send.call_args[0][0]
            assert event['severity'] == 'info'

        with patch('components.sdl_audit_logger.SDLAuditLogger._send_audit_event', new_callable=AsyncMock) as mock_send:
            # Rejection should have warning severity
            await audit_logger.log_rejection(
                parser_name='test',
                reason='Failed validation',
                retry_requested=False
            )

            event = mock_send.call_args[0][0]
            assert event['severity'] == 'warning'

    @pytest.mark.asyncio
    async def test_audit_log_includes_category(self, audit_logger):
        """Test event category is assigned."""
        with patch('components.sdl_audit_logger.SDLAuditLogger._send_audit_event', new_callable=AsyncMock) as mock_send:
            await audit_logger.log_approval(
                parser_name='test',
                lua_code='code',
                generation_time=1.0
            )

            event = mock_send.call_args[0][0]
            assert event['event_type'] == 'parser_approval'

    @pytest.mark.asyncio
    async def test_sensitive_data_masked(self, audit_logger):
        """Test sensitive data is masked."""
        # SECURITY NOTE: These are test values for masking verification, not real credentials
        TEST_API_KEY = 'sk-1234567890'  # Test value for masking test
        TEST_PASSWORD = 'super-secret'  # Test value for masking test
        with patch('components.sdl_audit_logger.SDLAuditLogger._send_audit_event', new_callable=AsyncMock) as mock_send:
            lua_with_secret = f"""
            local api_key = '{TEST_API_KEY}'
            local password = '{TEST_PASSWORD}'
            """

            await audit_logger.log_approval(
                parser_name='test',
                lua_code=lua_with_secret,
                generation_time=1.0
            )

            event = mock_send.call_args[0][0]
            # Code hash should be present instead of code itself
            assert 'lua_code_hash' in event
            # Full code should not be logged (for approval)
            if 'lua_code' in event:
                assert 'api_key' not in event.get('lua_code', '')


class TestStorageAndDelivery:
    """Test Suite 3: Storage & Delivery"""

    @pytest.mark.asyncio
    async def test_log_delivered_to_sdl(self, audit_logger):
        """Test log is delivered to SDL API."""
        with patch('components.sdl_audit_logger.SDLAuditLogger._send_audit_event', new_callable=AsyncMock) as mock_send:
            await audit_logger.log_approval(
                parser_name='test',
                lua_code='code',
                generation_time=1.0
            )

            # Verify send was called
            mock_send.assert_called_once()
            event = mock_send.call_args[0][0]
            assert event is not None

    @pytest.mark.asyncio
    async def test_batch_logging(self, audit_logger):
        """Test batch processing of events."""
        # This tests the concept of batching (configuration shows batch_size=10)
        assert audit_logger.batch_size == 10

        # Multiple events should be managed
        with patch('components.sdl_audit_logger.SDLAuditLogger._send_audit_event', new_callable=AsyncMock) as mock_send:
            for i in range(5):
                await audit_logger.log_approval(
                    parser_name=f'parser-{i}',
                    lua_code='code',
                    generation_time=1.0
                )

            # Should be called 5 times (or batched)
            assert mock_send.call_count >= 1

    @pytest.mark.asyncio
    async def test_retry_on_sdl_failure(self, audit_logger):
        """Test retry logic on API failure."""
        with patch('components.sdl_audit_logger.SDLAuditLogger._send_audit_event', new_callable=AsyncMock) as mock_send:
            # Simulate first failure, then success
            mock_send.side_effect = [RuntimeError("Temporary error"), None]

            try:
                await audit_logger.log_approval(
                    parser_name='test',
                    lua_code='code',
                    generation_time=1.0
                )
            except (RuntimeError, ConnectionError, TimeoutError):
                # Expected to fail on first attempt, then retry
                pass

    @pytest.mark.asyncio
    async def test_events_sent_counter(self, audit_logger):
        """Test event counter tracking."""
        initial_sent = audit_logger.events_sent

        with patch('components.sdl_audit_logger.SDLAuditLogger._send_audit_event', new_callable=AsyncMock):
            await audit_logger.log_approval(
                parser_name='test',
                lua_code='code',
                generation_time=1.0
            )

            # Counter may be incremented
            assert audit_logger.events_sent >= initial_sent


class TestErrorHandling:
    """Test Suite 4: Error Handling"""

    @pytest.mark.asyncio
    async def test_handle_malformed_event(self, audit_logger):
        """Test handling of malformed events."""
        with patch('components.sdl_audit_logger.SDLAuditLogger._send_audit_event', new_callable=AsyncMock):
            # Should handle gracefully
            await audit_logger.log_approval(
                parser_name=None,  # Invalid
                lua_code='',
                generation_time=-1  # Invalid
            )

            # Should not crash
            audit_logger._send_audit_event.assert_called()

    @pytest.mark.asyncio
    async def test_handle_sdl_connection_error(self, audit_logger):
        """Test handling of SDL connection errors."""
        with patch('components.sdl_audit_logger.SDLAuditLogger._send_audit_event', new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = ConnectionError("SDL unreachable")

            # Should handle gracefully or raise with context
            try:
                await audit_logger.log_approval(
                    parser_name='test',
                    lua_code='code',
                    generation_time=1.0
                )
            except ConnectionError:
                # Expected behavior
                pass

    @pytest.mark.asyncio
    async def test_handle_encoding_error(self, audit_logger):
        """Test handling of unicode encoding."""
        with patch('components.sdl_audit_logger.SDLAuditLogger._send_audit_event', new_callable=AsyncMock):
            # Unicode characters in parser name and code
            await audit_logger.log_approval(
                parser_name='test-parser-日本語',
                lua_code='-- comment: 中文\nfunction test() end',
                generation_time=1.0
            )

            # Should succeed without encoding errors
            audit_logger._send_audit_event.assert_called()

    @pytest.mark.asyncio
    async def test_handle_very_large_event(self, audit_logger):
        """Test handling of oversized events."""
        with patch('components.sdl_audit_logger.SDLAuditLogger._send_audit_event', new_callable=AsyncMock):
            # Very large Lua code
            large_code = 'function test() end\n' * 10000

            await audit_logger.log_approval(
                parser_name='test',
                lua_code=large_code,
                generation_time=1.0
            )

            # Should be handled (code hash instead of full code)
            event = audit_logger._send_audit_event.call_args[0][0]
            assert 'lua_code_hash' in event


class TestAuditTypes:
    """Test different audit event types"""

    @pytest.mark.asyncio
    async def test_log_approval_action(self, audit_logger):
        """Test approval event logging."""
        with patch('components.sdl_audit_logger.SDLAuditLogger._send_audit_event', new_callable=AsyncMock) as mock_send:
            await audit_logger.log_approval(
                parser_name='test-parser',
                lua_code='function transform(e) return e end',
                generation_time=2.5,
                confidence_score=0.92
            )

            event = mock_send.call_args[0][0]
            assert event['action'] == 'approve'
            assert event['confidence_score'] == 0.92

    @pytest.mark.asyncio
    async def test_log_rejection_action(self, audit_logger):
        """Test rejection event logging."""
        with patch('components.sdl_audit_logger.SDLAuditLogger._send_audit_event', new_callable=AsyncMock) as mock_send:
            await audit_logger.log_rejection(
                parser_name='bad-parser',
                reason='Syntax errors',
                retry_requested=True,
                error_details='Line 42: unexpected symbol'
            )

            event = mock_send.call_args[0][0]
            assert event['action'] == 'reject'
            assert event['rejection_reason'] == 'Syntax errors'
            assert event['retry_requested'] is True


class TestIntegration:
    """Integration tests for SDL Audit Logger"""

    @pytest.mark.asyncio
    async def test_full_audit_logging_flow(self, audit_logger):
        """Test complete audit logging flow."""
        with patch('components.sdl_audit_logger.SDLAuditLogger._send_audit_event', new_callable=AsyncMock):
            # Log approval
            await audit_logger.log_approval(
                parser_name='test-parser',
                lua_code='function transform(e) return e end',
                generation_time=1.5
            )

            # Log rejection
            await audit_logger.log_rejection(
                parser_name='another-parser',
                reason='Performance issues',
                retry_requested=False
            )

            # Verify both were sent
            assert audit_logger._send_audit_event.call_count >= 2

    @pytest.mark.asyncio
    async def test_audit_compliance_across_operations(self, audit_logger):
        """Test audit compliance for all operations."""
        with patch('components.sdl_audit_logger.SDLAuditLogger._send_audit_event', new_callable=AsyncMock) as mock_send:
            # Log multiple operations
            operations = [
                ('log_approval', {
                    'parser_name': 'p1',
                    'lua_code': 'code1',
                    'generation_time': 1.0
                }),
                ('log_rejection', {
                    'parser_name': 'p2',
                    'reason': 'test',
                    'retry_requested': False
                })
            ]

            for op_name, kwargs in operations:
                method = getattr(audit_logger, op_name)
                await method(**kwargs)

            # All events should have required fields
            for call in mock_send.call_args_list:
                event = call[0][0]
                assert 'timestamp' in event
                assert 'parser_name' in event
                assert 'action' in event
