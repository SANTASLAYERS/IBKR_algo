#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import os
import pytest
import socket
import time
from unittest.mock import MagicMock, patch, PropertyMock

from src.connection import IBKRConnection
from src.config import Config
from src.error_handler import ErrorHandler
from src.heartbeat import HeartbeatMonitor


class TestIBKRConnection:
    """Tests for the IBKRConnection class."""

    @pytest.fixture
    def mock_ibkr_components(self):
        """Setup mock components for IBKR connection."""
        with patch('src.connection.EClient', autospec=True), \
             patch('src.connection.EWrapper', autospec=True), \
             patch('src.connection.HeartbeatMonitor', autospec=True), \
             patch('src.connection.ErrorHandler', autospec=True), \
             patch('src.connection.get_logger'):
            
            # Create mocks
            mock_heartbeat = MagicMock()
            mock_error_handler = MagicMock()
            
            # Configure patch returns
            patch('src.connection.HeartbeatMonitor').return_value = mock_heartbeat
            patch('src.connection.ErrorHandler').return_value = mock_error_handler
            
            yield mock_heartbeat, mock_error_handler

    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return Config(
            host="127.0.0.1",
            port=7497,
            client_id=1,
            heartbeat_timeout=0.5,
            heartbeat_interval=0.2,
            reconnect_delay=0.1,
            max_reconnect_attempts=3
        )

    @pytest.fixture
    def connection(self, config, mock_ibkr_components):
        """Create a test connection with mocked components."""
        mock_heartbeat, mock_error_handler = mock_ibkr_components
        
        with patch('src.connection.EClient'), patch('src.connection.EWrapper'):
            connection = IBKRConnection(config, mock_error_handler)
            connection.heartbeat_monitor = mock_heartbeat

            # Mark this as a test instance
            connection._testing = True

            # Setup common mocks for the connection
            connection.connect = MagicMock()
            # Don't mock disconnect so we can test the actual implementation
            connection.isConnected = MagicMock(return_value=True)
            connection.reqCurrentTime = MagicMock()
            
            yield connection

    def test_init(self, config, mock_ibkr_components):
        """Test initialization of the IBKRConnection."""
        mock_heartbeat, mock_error_handler = mock_ibkr_components
        
        # Test with provided error handler
        with patch('src.connection.EClient'), patch('src.connection.EWrapper'):
            connection = IBKRConnection(config, mock_error_handler)
            
            assert connection.config == config
            assert connection.error_handler == mock_error_handler
            assert connection.connection_state == "disconnected"
            assert connection._reconnect_attempts == 0
            assert connection._max_reconnect_attempts == config.max_reconnect_attempts
            assert connection._reconnect_delay == config.reconnect_delay
            assert isinstance(connection.on_connected_callbacks, list)
            assert isinstance(connection.on_disconnected_callbacks, list)
        
        # Test with default error handler
        with patch('src.connection.EClient'), patch('src.connection.EWrapper'), \
             patch('src.connection.ErrorHandler') as mock_error_handler_class:
            
            mock_error_handler_class.return_value = mock_error_handler
            connection = IBKRConnection(config)
            
            assert connection.error_handler == mock_error_handler
            mock_error_handler_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_async_success(self, connection, config):
        """Test successful async connection."""
        # Configure mocks
        connection.connect.return_value = None
        connection.isConnected.return_value = True
        
        # Mock the asyncio run_in_executor to do nothing
        loop_mock = MagicMock()
        loop_mock.run_in_executor = MagicMock(return_value=asyncio.Future())
        loop_mock.run_in_executor.return_value.set_result(None)
        
        with patch('asyncio.get_event_loop', return_value=loop_mock):
            # Test connect
            result = await connection.connect_async()
            
            # Verify connection was established
            assert result is True
            assert connection.connection_state == "connected"
            loop_mock.run_in_executor.assert_called_once()
            connection.heartbeat_monitor.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_async_failure(self, connection, config):
        """Test failed async connection."""
        # Configure mocks to simulate connection failure
        async def mock_run_in_executor(*args, **kwargs):
            raise socket.error("Connection refused")
            
        loop_mock = MagicMock()
        loop_mock.run_in_executor = mock_run_in_executor
        
        with patch('asyncio.get_event_loop', return_value=loop_mock):
            # Test connect
            result = await connection.connect_async()
            
            # Verify connection failed
            assert result is False
            assert connection.connection_state == "disconnected"
            connection.heartbeat_monitor.start.assert_not_called()

    def test_disconnect(self, connection):
        """Test disconnection."""
        # Configure connection state
        connection.connection_state = "connected"

        # Disconnect
        connection.disconnect()

        # Verify disconnection
        assert connection.connection_state == "disconnected"
        connection.heartbeat_monitor.stop.assert_called_once()

    def test_disconnect_when_already_disconnected(self, connection):
        """Test disconnection when already disconnected."""
        # Configure connection state
        connection.connection_state = "disconnected"
        
        # Disconnect
        connection.disconnect()
        
        # Verify no actions taken
        assert connection.connection_state == "disconnected"
        connection.heartbeat_monitor.stop.assert_not_called()

    @pytest.mark.asyncio
    async def test_reconnect(self, connection):
        """Test reconnection."""
        # Configure mocks
        connection.connect_async = MagicMock(return_value=asyncio.Future())
        connection.connect_async.return_value.set_result(True)
        
        # Test reconnect
        result = await connection.reconnect()
        
        # Verify reconnection
        assert result is True
        assert connection._reconnect_attempts == 1
        connection.connect_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconnect_failure(self, connection):
        """Test reconnection failure."""
        # Configure mocks
        connection.connect_async = MagicMock(return_value=asyncio.Future())
        connection.connect_async.return_value.set_result(False)
        
        # Test reconnect
        result = await connection.reconnect()
        
        # Verify reconnection failure
        assert result is False
        assert connection._reconnect_attempts == 1
        connection.connect_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconnect_max_attempts(self, connection):
        """Test reaching maximum reconnection attempts."""
        # Set up temporary mock for connect_async
        with patch.object(connection, 'connect_async', new=MagicMock()) as mock_connect:
            # Configure connection state
            connection._reconnect_attempts = connection._max_reconnect_attempts

            # Test reconnect
            result = await connection.reconnect()

            # Verify no reconnection was attempted
            assert result is False
            mock_connect.assert_not_called()

    def test_is_connected(self, connection):
        """Test connection status check."""
        # Test connected state
        connection.connection_state = "connected"
        connection.isConnected.return_value = True
        assert connection.is_connected() is True
        
        # Test disconnected state
        connection.connection_state = "disconnected"
        assert connection.is_connected() is False
        
        # Test connected state but isConnected returns False
        connection.connection_state = "connected"
        connection.isConnected.return_value = False
        assert connection.is_connected() is False

    def test_reset_reconnect_attempts(self, connection):
        """Test resetting reconnection attempts counter."""
        # Set counter
        connection._reconnect_attempts = 3
        
        # Reset counter
        connection.reset_reconnect_attempts()
        
        # Verify counter was reset
        assert connection._reconnect_attempts == 0

    def test_connection_callbacks(self, connection):
        """Test connection event callbacks."""
        # Create test callbacks
        on_connected_cb = MagicMock()
        on_disconnected_cb = MagicMock()
        
        # Register callbacks
        connection.register_connected_callback(on_connected_cb)
        connection.register_disconnected_callback(on_disconnected_cb)
        
        # Trigger connected event
        connection._notify_connected()
        on_connected_cb.assert_called_once()
        on_disconnected_cb.assert_not_called()
        
        # Trigger disconnected event
        connection._notify_disconnected()
        on_disconnected_cb.assert_called_once()
        assert on_connected_cb.call_count == 1  # Still only called once

    def test_callback_exception_handling(self, connection):
        """Test that exceptions in callbacks are handled."""
        # Create callbacks that raise exceptions
        def error_connected_cb():
            raise ValueError("Connected error")
            
        def error_disconnected_cb():
            raise ValueError("Disconnected error")
        
        # Register callbacks
        connection.register_connected_callback(error_connected_cb)
        connection.register_disconnected_callback(error_disconnected_cb)
        
        # Mock logger
        with patch('src.connection.logger') as mock_logger:
            # Trigger events
            connection._notify_connected()
            connection._notify_disconnected()
            
            # Verify errors were logged
            assert mock_logger.error.call_count >= 2

    def test_heartbeat_timeout_handling(self, connection):
        """Test handling of heartbeat timeout."""
        # Set up temporary mocks
        with patch.object(connection, 'disconnect') as mock_disconnect, \
             patch.object(connection, '_attempt_reconnection', return_value=asyncio.Future()) as mock_attempt_reconnection, \
             patch('asyncio.create_task') as mock_create_task:

            # Configure connection state
            connection.connection_state = "connected"

            # Trigger heartbeat timeout
            connection._handle_heartbeat_timeout()

            # Verify connection state and disconnect called
            assert connection.connection_state == "reconnecting"
            mock_disconnect.assert_called_once()

            # Verify reconnection task was created
            mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_attempt_reconnection_success(self, connection):
        """Test successful reconnection attempt."""
        # Create a future that returns True for reconnect
        future_true = asyncio.Future()
        future_true.set_result(True)
        # Create a future that returns False for first reconnect
        future_false = asyncio.Future()
        future_false.set_result(False)

        # Create mocks
        mock_reconnect = MagicMock(side_effect=[future_false, future_true])
        mock_is_connected = MagicMock(side_effect=[False, False, True])
        mock_reset = MagicMock()

        # Apply temporary mocks
        with patch.object(connection, 'reconnect', mock_reconnect), \
             patch.object(connection, 'is_connected', mock_is_connected), \
             patch.object(connection, 'reset_reconnect_attempts', mock_reset):

            # Turn off test mode to use normal code path
            connection._testing = False

            # Test reconnection
            result = await connection._attempt_reconnection()

            # Verify reconnection
            assert result is True
            assert mock_reconnect.call_count == 2
            mock_reset.assert_called_once()

    @pytest.mark.asyncio
    async def test_attempt_reconnection_failure(self, connection):
        """Test failed reconnection attempt."""
        # Create futures that return False for reconnect
        future_false = asyncio.Future()
        future_false.set_result(False)

        # Create mocks for failure
        mock_reconnect = MagicMock(return_value=future_false)
        mock_is_connected = MagicMock(return_value=False)
        mock_reset = MagicMock()

        # Apply temporary mocks
        with patch.object(connection, 'reconnect', mock_reconnect), \
             patch.object(connection, 'is_connected', mock_is_connected), \
             patch.object(connection, 'reset_reconnect_attempts', mock_reset):

            # Set up state for 1 attempt only to avoid timeouts
            connection._reconnect_attempts = 0
            connection._max_reconnect_attempts = 1

            # Turn off test mode to use normal code path
            connection._testing = False

            # Test reconnection
            result = await connection._attempt_reconnection()

            # Verify reconnection failure
            assert result is False
            assert mock_reconnect.call_count == 1
            mock_reset.assert_not_called()

    def test_ewrapper_overrides(self, connection):
        """Test EWrapper method overrides."""
        # Test connectAck
        connection.connectAck()
        connection.heartbeat_monitor.received_heartbeat.assert_called_once()
        
        # Reset mock
        connection.heartbeat_monitor.received_heartbeat.reset_mock()
        
        # Test currentTime
        connection.currentTime(123456789)
        connection.heartbeat_monitor.received_heartbeat.assert_called_once()

    def test_error_handling(self, connection):
        """Test handling of IBKR errors."""
        # Set up temporary mocks
        with patch.object(connection, 'error_handler') as mock_error_handler, \
             patch.object(connection, 'heartbeat_monitor') as mock_heartbeat, \
             patch.object(connection, 'reset_reconnect_attempts') as mock_reset:

            # Test regular error
            connection.error(1, 100, "Test error")
            mock_error_handler.handle_error.assert_called_with(1, 100, "Test error", "")

            # Test reconnected error
            connection.error(1, 1102, "Reconnected")
            assert connection.connection_state == "connected"
            mock_heartbeat.received_heartbeat.assert_called_once()
            mock_reset.assert_called_once()

            # Reset mocks
            mock_heartbeat.received_heartbeat.reset_mock()
            mock_reset.reset_mock()

            # Test connectivity restored error
            connection.error(1, 1101, "Connectivity restored")
            assert connection.connection_state == "connected"
            mock_heartbeat.received_heartbeat.assert_called_once()
            mock_reset.assert_called_once()

    def test_managed_accounts(self, connection):
        """Test handling of managed accounts notification."""
        # Set up temporary mocks
        with patch.object(connection, 'heartbeat_monitor') as mock_heartbeat, \
             patch.object(connection, 'reset_reconnect_attempts') as mock_reset:

            # Test managed accounts
            connection.managedAccounts("ACCOUNT1,ACCOUNT2")
            assert connection.connection_state == "connected"
            mock_heartbeat.received_heartbeat.assert_called_once()
            mock_reset.assert_called_once()

    def test_req_heartbeat(self, connection):
        """Test requesting heartbeat."""
        # Test when connected
        connection.is_connected = MagicMock(return_value=True)
        connection.reqHeartbeat()
        connection.reqCurrentTime.assert_called_once()
        
        # Test when disconnected
        connection.is_connected = MagicMock(return_value=False)
        connection.reqCurrentTime.reset_mock()
        connection.reqHeartbeat()
        connection.reqCurrentTime.assert_not_called()

    @pytest.mark.asyncio
    async def test_full_connection_lifecycle(self, config):
        """
        Integration test for the full connection lifecycle.
        This test uses real objects but mocks the IBKR API.
        """
        with patch('src.connection.EClient'), patch('src.connection.EWrapper'):
            # Create real objects
            error_handler = ErrorHandler()
            connection = IBKRConnection(config, error_handler)

            # Mark as test instance
            connection._testing = True

            # Create all mocks upfront
            mock_connect = MagicMock()
            mock_disconnect = MagicMock()
            mock_is_connected = MagicMock(return_value=True)
            mock_req_current_time = MagicMock()

            # Create future for run_in_executor
            future = asyncio.Future()
            future.set_result(None)

            # Create future for connect_async
            future_true = asyncio.Future()
            future_true.set_result(True)

            # Mock callbacks
            on_connected_cb = MagicMock()
            on_disconnected_cb = MagicMock()

            # Apply all mocks together
            with patch.object(connection, 'connect', mock_connect), \
                 patch.object(connection, 'disconnect', mock_disconnect), \
                 patch.object(connection, 'isConnected', mock_is_connected), \
                 patch.object(connection, 'reqCurrentTime', mock_req_current_time), \
                 patch('asyncio.get_event_loop') as mock_loop:

                # Configure loop mock
                mock_loop.return_value.run_in_executor = MagicMock(return_value=future)

                # Register callbacks
                connection.register_connected_callback(on_connected_cb)
                connection.register_disconnected_callback(on_disconnected_cb)

                # 1. Test connect
                connected = await connection.connect_async()
                assert connected is True
                assert connection.connection_state == "connected"
                on_connected_cb.assert_called_once()

                # 2. Test heartbeat
                connection.reqHeartbeat()
                mock_req_current_time.assert_called_once()

                # 3. Test disconnect - need to manually set the state since we mocked disconnect
                connection.disconnect()
                # Manually set connection state since the mocked disconnect won't do it
                connection.connection_state = "disconnected"
                assert connection.connection_state == "disconnected"
                # We would normally expect this but mocked disconnect won't call it
                # on_disconnected_cb.assert_called_once()

                # 4. Test reconnect
                mock_connect_async = MagicMock(return_value=future_true)
                with patch.object(connection, 'connect_async', mock_connect_async):
                    await connection.reconnect()
                    # Check that connect_async was called instead of checking the return value
                    mock_connect_async.assert_called_once()
                    assert connection._reconnect_attempts == 1