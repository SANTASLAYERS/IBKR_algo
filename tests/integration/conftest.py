#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Configuration and fixtures for TWS integration tests.

These fixtures manage connection to TWS for testing trading functionality.
"""

import os
import pytest
import asyncio
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("integration_tests")


def pytest_addoption(parser):
    """Add command-line options for integration tests."""
    parser.addoption(
        "--force-tws",
        action="store_true",
        default=False,
        help="Force execution of TWS integration tests even if TWS appears to be down",
    )


async def is_tws_available_async(host: str, port: int, client_id: int, timeout: float = 5.0) -> bool:
    """
    Check if TWS is available using proper IBAPI connection.
    
    ⚠️ IMPORTANT: This uses IBAPI instead of raw sockets to avoid corrupting TWS state.
    
    Args:
        host: TWS hostname or IP
        port: TWS port
        client_id: Client ID to use for test connection
        timeout: Connection timeout in seconds
        
    Returns:
        bool: True if connection succeeds, False otherwise
    """
    try:
        # Import here to avoid circular imports
        from src.tws_config import TWSConfig
        from src.tws_connection import TWSConnection
        
        # Create test configuration
        config = TWSConfig(
            host=host,
            port=port,
            client_id=client_id + 900,  # Use offset client ID for availability checks
            connection_timeout=timeout
        )
        
        # Test connection using proper IBAPI
        test_connection = TWSConnection(config)
        
        try:
            connected = await test_connection.connect()
            if connected:
                # Clean disconnect to avoid corrupting TWS state
                test_connection.disconnect()
                await asyncio.sleep(1)  # Give time for clean disconnect
                return True
            return False
            
        except Exception as e:
            logger.debug(f"TWS availability check failed: {e}")
            return False
        finally:
            # Ensure clean disconnect
            if test_connection.is_connected():
                test_connection.disconnect()
                await asyncio.sleep(1)
            
    except Exception as e:
        logger.debug(f"Error during TWS availability check: {e}")
        return False


def is_tws_available(host: str, port: int, client_id: int, timeout: float = 5.0) -> bool:
    """
    Synchronous wrapper for TWS availability check.
    
    Args:
        host: TWS hostname or IP
        port: TWS port
        client_id: Client ID to use for test connection
        timeout: Connection timeout in seconds
        
    Returns:
        bool: True if connection succeeds, False otherwise
    """
    try:
        # Run the async check
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(is_tws_available_async(host, port, client_id, timeout))
        finally:
            loop.close()
    except Exception as e:
        logger.debug(f"Error in TWS availability check: {e}")
        return False


def get_tws_credentials():
    """
    Get TWS credentials from environment variables.
    
    Returns:
        dict: Dictionary with connection parameters
    """
    return {
        "host": os.environ.get("TWS_HOST", "127.0.0.1"),
        "port": int(os.environ.get("TWS_PORT", "7497")),  # Default to TWS paper trading
        "client_id": int(os.environ.get("TWS_CLIENT_ID", "10")),
        "account": os.environ.get("TWS_ACCOUNT", ""),
    }


@pytest.fixture(scope="session")
def check_tws(request) -> bool:
    """
    Check if TWS is available and decide whether to skip integration tests.
    
    Uses proper IBAPI connection instead of raw sockets to avoid corrupting TWS state.
    
    Returns:
        bool: True if TWS is available, False otherwise
    """
    credentials = get_tws_credentials()
    force_tests = request.config.getoption("--force-tws")
    
    # Use proper IBAPI check instead of raw socket check
    tws_available = is_tws_available(
        credentials["host"], 
        credentials["port"], 
        credentials["client_id"]
    )
    
    if not tws_available and not force_tests:
        pytest.skip(
            f"TWS not available at {credentials['host']}:{credentials['port']}. "
            "Make sure TWS is running and API is enabled. Set --force-tws to run tests anyway."
        )
    
    return tws_available 