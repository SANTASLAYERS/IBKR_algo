#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Configuration and fixtures for IB Gateway integration tests.

These fixtures manage connection to IB Gateway for testing trading functionality.
"""

import asyncio
import os
import pytest
import socket
import time
import logging
from typing import Generator, Dict, Any

from src.gateway import IBGateway, IBGatewayConfig
from src.error_handler import ErrorHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("integration_tests")


def pytest_addoption(parser):
    """Add command-line options for integration tests."""
    parser.addoption(
        "--force-ib-gateway",
        action="store_true",
        default=False,
        help="Force execution of IB Gateway integration tests even if gateway appears to be down",
    )


def is_ib_gateway_available(host: str, port: int, timeout: float = 2.0) -> bool:
    """
    Check if IB Gateway is available by attempting to connect to the specified host and port.
    
    Args:
        host: Gateway hostname or IP
        port: Gateway port
        timeout: Connection timeout in seconds
        
    Returns:
        bool: True if connection succeeds, False otherwise
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def get_ib_credentials() -> Dict[str, Any]:
    """
    Get IB Gateway credentials from environment variables.
    
    Returns:
        dict: Dictionary with connection parameters
    """
    return {
        "host": os.environ.get("IB_HOST", "127.0.0.1"),
        "port": int(os.environ.get("IB_PORT", "4002")),  # Default to paper trading
        "client_id": int(os.environ.get("IB_CLIENT_ID", "10")),
        "account": os.environ.get("IB_ACCOUNT", ""),
    }


@pytest.fixture(scope="session")
def check_ib_gateway(request) -> bool:
    """
    Check if IB Gateway is available and decide whether to skip integration tests.
    
    Returns:
        bool: True if gateway is available, False otherwise
    """
    credentials = get_ib_credentials()
    force_tests = request.config.getoption("--force-ib-gateway")
    
    gateway_available = is_ib_gateway_available(credentials["host"], credentials["port"])
    
    if not gateway_available and not force_tests:
        pytest.skip(
            f"IB Gateway not available at {credentials['host']}:{credentials['port']}. "
            "Set --force-ib-gateway to run tests anyway."
        )
    
    return gateway_available


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    
    # Clean up all tasks
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()
    
    # Run the event loop until all tasks are done or cancelled
    if pending:
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    
    loop.close()


@pytest.fixture(scope="class")
async def ib_gateway(check_ib_gateway, request) -> Generator:
    """
    Create an IBGateway instance and connect to IB Gateway.
    
    This fixture should be used for integration tests that require a gateway connection.
    If IB Gateway is not available, tests using this fixture will be skipped.
    
    Yields:
        IBGateway: Connected gateway instance
    """
    credentials = get_ib_credentials()
    
    # Create gateway configuration
    config = IBGatewayConfig(
        host=credentials["host"],
        port=credentials["port"],
        client_id=credentials["client_id"],
        account_id=credentials["account"],
        trading_mode="paper" if credentials["port"] == 4002 else "live",
        heartbeat_timeout=10.0,
        heartbeat_interval=5.0,
        reconnect_delay=1.0,
        max_reconnect_attempts=3
    )
    
    # Create error handler
    error_handler = ErrorHandler()
    
    # Create gateway instance
    gateway = IBGateway(config, error_handler)
    
    try:
        # Connect to IB Gateway
        logger.info(f"Connecting to IB Gateway at {config.host}:{config.port}...")
        connected = await gateway.connect_gateway()
        
        if not connected:
            pytest.skip("Failed to connect to IB Gateway")
            return
        
        # Store account ID on the gateway
        if credentials["account"]:
            gateway.account_id = credentials["account"]
        
        # Request current time to verify connection
        gateway.reqCurrentTime()
        
        # Wait for connection to stabilize
        await asyncio.sleep(1)
        
        # Check if gateway is still connected
        if not gateway.is_connected():
            pytest.skip("Connection to IB Gateway was established but then lost")
            return
        
        # Store gateway on the request so test classes can access it
        request.cls.gateway = gateway
        
        # Yield the gateway to the test
        logger.info("IB Gateway connection established. Ready for testing.")
        yield gateway
        
    except Exception as e:
        logger.error(f"Error setting up IB Gateway connection: {str(e)}")
        pytest.skip(f"IB Gateway connection failed: {str(e)}")
    finally:
        # Always disconnect when done
        if gateway.is_connected():
            logger.info("Disconnecting from IB Gateway...")
            gateway.disconnect()
            logger.info("Disconnected from IB Gateway")