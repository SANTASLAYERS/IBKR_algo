#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TWS Connection Integration Tests.

These tests validate the actual TWS connection functionality.
"""

import pytest
import asyncio
import logging
import threading
import sys
import os

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

    # @pytest.mark.usefixtures("check_tws")  # TEMPORARILY DISABLED
    @pytest.mark.asyncio
    async def test_tws_connection_to_live_tws(self):
        """Test actual connection to running TWS (requires TWS to be running)."""
        # EXTENSIVE DEBUGGING - Let's see what's different!
        logger.info("=== PYTEST DEBUGGING START ===")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"Environment TWS_CLIENT_ID: {os.getenv('TWS_CLIENT_ID', 'NOT SET')}")
        logger.info(f"Environment TWS_ACCOUNT: {os.getenv('TWS_ACCOUNT', 'NOT SET')}")
        logger.info(f"Active thread count: {threading.active_count()}")
        logger.info(f"Main thread: {threading.main_thread()}")
        logger.info(f"Current thread: {threading.current_thread()}")
        
        # Check event loop
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            logger.info(f"Event loop: {loop}")
            logger.info(f"Event loop running: {loop.is_running()}")
            logger.info(f"Event loop closed: {loop.is_closed()}")
        except Exception as e:
            logger.info(f"Event loop error: {e}")
        
        credentials = get_tws_credentials()
        logger.info(f"PYTEST: Got credentials: {credentials}")
        
        # Create configuration with UNIQUE client ID (safe pattern)
        config = TWSConfig(
            host=credentials["host"],
            port=credentials["port"],
            client_id=10,  # Use already-approved client ID from diagnostic script
            account_id=credentials["account"],
            connection_timeout=8.0  # Shorter timeout like safe pattern
        )
        
        logger.info(f"PYTEST: Using config: host={config.host}, port={config.port}, client_id={config.client_id}, timeout={config.connection_timeout}")
        
        # Create connection
        connection = TWSConnection(config)
        logger.info(f"PYTEST: Created connection instance: {connection}")
        
        # Track connection events and results
        connected_event = asyncio.Event()
        error_occurred = None
        connection_success = False
        
        def on_connected():
            nonlocal connection_success
            connection_success = True
            logger.info("PYTEST: Connection callback: Connected to TWS")
            connected_event.set()
        
        def on_error(req_id, error_code, error_string):
            nonlocal error_occurred
            error_occurred = (req_id, error_code, error_string)
            logger.error(f"PYTEST: Connection callback: Error {error_code}: {error_string}")
        
        # Set callbacks
        connection.set_callbacks(
            on_connected=on_connected,
            on_error=on_error
        )
        
        logger.info("PYTEST: Set callbacks, about to start connection...")
        
        try:
            # Attempt connection
            logger.info(f"PYTEST: Connecting to TWS at {config.host}:{config.port} with client ID {config.client_id}")
            
            # Let's also check thread state right before connection
            logger.info(f"PYTEST: Pre-connection thread count: {threading.active_count()}")
            for thread in threading.enumerate():
                logger.info(f"PYTEST: Active thread: {thread.name} - {thread}")
            
            connected = await connection.connect()
            
            logger.info(f"PYTEST: Connection result: {connected}")
            logger.info(f"PYTEST: Connection state: {connection._connected}")
            logger.info(f"PYTEST: Connection ack: {connection._connection_ack_received}")
            logger.info(f"PYTEST: API started: {connection._api_started}")
            
            assert connected, f"Failed to connect to TWS at {config.host}:{config.port}"
            assert connection.is_connected(), "Connection state not properly set"
            
            # Test basic functionality
            logger.info("Testing basic TWS API calls...")
            
            # Check if we received order ID (should be automatic)
            order_id = connection.get_next_order_id()
            if order_id is not None:
                logger.info(f"✅ Received next order ID: {order_id}")
                assert order_id > 0, "Order ID should be positive"
            else:
                logger.warning("Did not receive order ID from TWS")
            
            # Request current time
            connection.request_current_time()
            await asyncio.sleep(0.5)  # Shorter wait
            
            # Request managed accounts
            connection.request_managed_accounts()
            await asyncio.sleep(0.5)  # Shorter wait
            
            logger.info("✅ Successfully tested TWS connection and basic functionality")
            
        except Exception as e:
            logger.error(f"❌ PYTEST: Connection exception: {e}")
            logger.error(f"PYTEST: Connection state: {connection._connected}")
            logger.error(f"PYTEST: Connection ack: {connection._connection_ack_received}")
            logger.error(f"PYTEST: API started: {connection._api_started}")
            
            # Check thread state after failure
            logger.error(f"PYTEST: Post-error thread count: {threading.active_count()}")
            for thread in threading.enumerate():
                logger.error(f"PYTEST: Active thread: {thread.name} - {thread}")
            
            raise
            
        finally:
            # Always clean up (safe pattern)
            logger.info("PYTEST: Cleaning up connection...")
            try:
                if connection.is_connected():
                    connection.disconnect()
                # Give TWS time to clean up (safe pattern)
                await asyncio.sleep(1.0)
            except Exception as e:
                logger.error(f"PYTEST: Error during cleanup: {e}")
            
            # Final thread state
            logger.info(f"PYTEST: Final thread count: {threading.active_count()}")
            
            # Verify disconnection
            if connection.is_connected():
                logger.warning("PYTEST: Connection still active after disconnect")
            else:
                logger.info("✅ PYTEST: Successfully disconnected from TWS")
        
        logger.info("=== PYTEST DEBUGGING END ===")

    @pytest.mark.usefixtures("check_tws")
    @pytest.mark.asyncio
    async def test_tws_connection_timeout(self):
        """Test connection timeout behavior."""
        # Use invalid port to trigger timeout
        config = TWSConfig(
            host="127.0.0.1",
            port=9999,  # Invalid port
            client_id=26,  # UNIQUE ID for timeout test
            connection_timeout=2.0  # Short timeout for test
        )
        
        connection = TWSConnection(config)
        
        logger.info("Testing connection timeout with invalid port")
        connected = await connection.connect()
        
        assert not connected, "Should fail to connect to invalid port"
        assert not connection.is_connected(), "Should not be connected"
        
        logger.info("✅ Connection timeout behavior works correctly") 