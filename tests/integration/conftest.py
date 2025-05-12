#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Configuration and fixtures for IB Gateway integration tests.

These fixtures manage connection to IB Gateway for testing trading functionality.
"""

import asyncio
import os
import pytest
import pytest_asyncio
import socket
import logging
from typing import Dict, Any

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


# 1) Provide one event-loop for the whole session so the gateway never loses it
@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the entire test session."""
    logger.info("Creating session-wide event loop")
    loop = asyncio.new_event_loop()
    yield loop
    
    # Clean up all tasks
    logger.info("Cleaning up session event loop")
    pending = asyncio.all_tasks(loop)
    if pending:
        logger.info(f"Cancelling {len(pending)} pending tasks")
        for task in pending:
            task.cancel()
    
        # Run the event loop until all tasks are done or cancelled
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    
    loop.close()


# 2) Open IB Gateway once per session and cleanly disconnect at the end
@pytest_asyncio.fixture(scope="session")
async def ib_gateway(event_loop):
    """
    Create an IBGateway instance and connect to IB Gateway.
    
    This fixture should be used for integration tests that require a gateway connection.
    If IB Gateway is not available, tests using this fixture will be skipped.
    
    Yields:
        IBGateway: Connected gateway instance
    """
    logger.info("Setting up session-wide ib_gateway fixture")
    
    credentials = get_ib_credentials()
    logger.info(f"Using credentials: host={credentials['host']}, port={credentials['port']}, "
                f"client_id={credentials['client_id']}")
    
    # For WSL environments connecting to IB Gateway on Windows
    if credentials["host"] == "172.28.64.1":
        logger.info("Using known WSL-to-Windows IP 172.28.64.1")
    else:
        # Check if gateway is available for non-WSL connections
        gateway_available = is_ib_gateway_available(credentials["host"], credentials["port"])
        if not gateway_available:
            logger.error(f"IB Gateway not available at {credentials['host']}:{credentials['port']}")
            pytest.skip(f"IB Gateway not available at {credentials['host']}:{credentials['port']}")
    
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
    logger.info(f"Created gateway instance: {gateway}")
    
    try:
        # Connect to IB Gateway
        logger.info(f"Connecting to IB Gateway at {config.host}:{config.port}...")
        
        # Use the direct connection method
        connected = await gateway.connect_async()
        logger.info(f"Connection result: {connected}")
        
        if not connected:
            logger.error("❌ Failed to connect to IB Gateway")
            pytest.skip("Failed to connect to IB Gateway")
        
        logger.info("✅ Successfully connected to IB Gateway!")
        
        # Store account ID on the gateway
        if credentials["account"]:
            gateway.account_id = credentials["account"]
            logger.info(f"Set account ID to {credentials['account']}")
        
        # Request current time to verify connection
        gateway.reqCurrentTime()
        logger.info("Requested current time from gateway")
        
        # Wait for connection to stabilize
        logger.info("Waiting for connection to stabilize...")
        await asyncio.sleep(1)
        
        # Check if gateway is still connected
        if not gateway.is_connected():
            logger.error("❌ Connection to IB Gateway was established but then lost")
            pytest.skip("Connection to IB Gateway was established but then lost")
        
        logger.info(f"Connection is stable, state: {gateway.connection_state}")
        
        # Yield gateway to tests
        yield gateway
        
    except Exception as e:
        logger.error(f"Error setting up IB Gateway connection: {str(e)}")
        pytest.skip(f"IB Gateway connection failed: {str(e)}")
    finally:
        # Always disconnect when done with all tests
        if gateway and gateway.is_connected():
            logger.info("Disconnecting from IB Gateway...")
            gateway.disconnect()
            logger.info("Disconnected from IB Gateway")


# 3) Inject the gateway as a class attribute for all test classes
@pytest.fixture(autouse=True)
def _inject_gateway(request, ib_gateway):
    """
    Automatically inject the gateway instance into test classes.
    This allows test methods to access the gateway via self.gateway.
    """
    if request.cls is not None:
        logger.info(f"Injecting gateway into test class: {request.cls.__name__}")
        request.cls.gateway = ib_gateway
        
        # Verify gateway was properly assigned
        if hasattr(request.cls, 'gateway') and request.cls.gateway is not None:
            logger.info(f"Verified gateway injection: {request.cls.gateway}")
        else:
            logger.warning("Failed to verify gateway injection")
    return