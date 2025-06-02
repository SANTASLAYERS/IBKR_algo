"""
Live Tests Configuration
========================

Configuration and fixtures for live testing with real TWS connections.
"""

import pytest
import asyncio
import logging
import os

# Import from existing integration test infrastructure
from tests.integration.conftest import get_tws_credentials, is_tws_available

logger = logging.getLogger("live_tests")


@pytest.fixture(scope="session")
def tws_credentials():
    """Get TWS credentials for live testing."""
    return get_tws_credentials()


@pytest.fixture(scope="session")
def check_live_tws(request):
    """
    Check if TWS is available for live testing.
    
    This reuses the existing integration test infrastructure.
    """
    credentials = get_tws_credentials()
    force_tests = request.config.getoption("--force-tws", default=False)
    
    # Check if TWS is available
    tws_available = is_tws_available(
        credentials["host"], 
        credentials["port"], 
        credentials["client_id"] + 500  # Offset client ID for live tests
    )
    
    if not tws_available and not force_tests:
        pytest.skip(
            f"TWS not available at {credentials['host']}:{credentials['port']}. "
            "Make sure TWS is running and API is enabled. "
            "Use --force-tws to run tests anyway."
        )
    
    return tws_available


def pytest_addoption(parser):
    """Add command line options for live tests."""
    parser.addoption(
        "--force-tws", 
        action="store_true", 
        default=False,
        help="Force TWS tests to run even if TWS appears unavailable"
    )
    parser.addoption(
        "--live-only",
        action="store_true", 
        default=False,
        help="Run only live tests (skip mocked tests)"
    ) 