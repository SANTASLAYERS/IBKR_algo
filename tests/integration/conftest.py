#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Configuration and fixtures for TWS integration tests.

These fixtures manage connection to TWS for testing trading functionality.
"""

import os
import pytest
import socket
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


def is_tws_available(host: str, port: int, timeout: float = 2.0) -> bool:
    """
    Check if TWS is available by attempting to connect to the specified host and port.
    
    Args:
        host: TWS hostname or IP
        port: TWS port
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
    
    Returns:
        bool: True if TWS is available, False otherwise
    """
    credentials = get_tws_credentials()
    force_tests = request.config.getoption("--force-tws")
    
    tws_available = is_tws_available(credentials["host"], credentials["port"])
    
    if not tws_available and not force_tests:
        pytest.skip(
            f"TWS not available at {credentials['host']}:{credentials['port']}. "
            "Make sure TWS is running and API is enabled. Set --force-tws to run tests anyway."
        )
    
    return tws_available 