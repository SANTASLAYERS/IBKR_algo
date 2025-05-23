#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TWS Connection Integration Tests.

These tests validate the actual TWS connection functionality.
"""

import pytest
import asyncio
import logging

from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from tests.integration.conftest import get_tws_credentials

logger = logging.getLogger("tws_connection_tests")


class TestTWSConnection:
    """Tests for TWS connection functionality."""

    def test_tws_config_creation(self):
        """Test creating TWS configuration."""
        config = TWSConfig()
        
        # Check defaults
        assert config.host == "127.0.0.1"
        assert config.port == 7497
        assert config.client_id == 1
        assert config.trading_mode == "paper"
        
        # Check validation
        assert config.validate()
        
        logger.info(f"Created config: {config}")

    def test_tws_config_from_env(self):
        """Test creating TWS configuration from environment."""
        config = TWSConfig.from_env()
        
        # Should not raise an exception
        assert config.validate()
        
        logger.info(f"Config from env: {config}")

    def test_tws_connection_creation(self):
        """Test creating TWS connection instance."""
        config = TWSConfig()
        connection = TWSConnection(config)
        
        # Check initial state
        assert not connection.is_connected()
        assert connection.get_next_order_id() is None
        
        logger.info("Successfully created TWS connection instance")

    @pytest.mark.usefixtures("check_tws")
    @pytest.mark.asyncio
    async def test_tws_connection_to_live_tws(self):
        """Test actual connection to running TWS (requires TWS to be running)."""
        credentials = get_tws_credentials()
        
        # Create configuration from test credentials
        config = TWSConfig(
            host=credentials["host"],
            port=credentials["port"],
            client_id=credentials["client_id"],
            account_id=credentials["account"],
            connection_timeout=10.0
        )
        
        # Create connection
        connection = TWSConnection(config)
        
        # Track connection events
        connected_event = asyncio.Event()
        error_occurred = None
        
        def on_connected():
            logger.info("Connection callback: Connected to TWS")
            connected_event.set()
        
        def on_error(req_id, error_code, error_string):
            nonlocal error_occurred
            error_occurred = (req_id, error_code, error_string)
            logger.error(f"Connection callback: Error {error_code}: {error_string}")
        
        # Set callbacks
        connection.set_callbacks(
            on_connected=on_connected,
            on_error=on_error
        )
        
        try:
            # Attempt connection
            logger.info(f"Connecting to TWS at {config.host}:{config.port}")
            connected = await connection.connect()
            
            assert connected, f"Failed to connect to TWS at {config.host}:{config.port}"
            assert connection.is_connected(), "Connection state not properly set"
            
            # Wait for connection event
            try:
                await asyncio.wait_for(connected_event.wait(), timeout=5.0)
                logger.info("✅ Connection event received")
            except asyncio.TimeoutError:
                logger.warning("Connection event not received within timeout")
            
            # Test basic functionality
            logger.info("Testing basic TWS API calls...")
            
            # Request current time
            connection.request_current_time()
            await asyncio.sleep(1)  # Give time for response
            
            # Request managed accounts
            connection.request_managed_accounts()
            await asyncio.sleep(1)  # Give time for response
            
            # Request next order ID
            connection.request_next_order_id()
            await asyncio.sleep(2)  # Give time for response
            
            # Check if we received order ID
            order_id = connection.get_next_order_id()
            if order_id is not None:
                logger.info(f"✅ Received next order ID: {order_id}")
                assert order_id > 0, "Order ID should be positive"
            else:
                logger.warning("Did not receive order ID from TWS")
            
            logger.info("✅ Successfully tested TWS connection and basic functionality")
            
        finally:
            # Always disconnect
            if connection.is_connected():
                logger.info("Disconnecting from TWS")
                connection.disconnect()
                
                # Give time for disconnection
                await asyncio.sleep(1)
                
                # Verify disconnection
                assert not connection.is_connected(), "Should be disconnected"
                logger.info("✅ Successfully disconnected from TWS")

    @pytest.mark.usefixtures("check_tws")
    @pytest.mark.asyncio
    async def test_tws_connection_timeout(self):
        """Test connection timeout behavior."""
        # Use invalid port to trigger timeout
        config = TWSConfig(
            host="127.0.0.1",
            port=9999,  # Invalid port
            client_id=99,
            connection_timeout=2.0  # Short timeout for test
        )
        
        connection = TWSConnection(config)
        
        logger.info("Testing connection timeout with invalid port")
        connected = await connection.connect()
        
        assert not connected, "Should fail to connect to invalid port"
        assert not connection.is_connected(), "Should not be connected"
        
        logger.info("✅ Connection timeout behavior works correctly") 