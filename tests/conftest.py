#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import os
import sys
import pytest
import logging
from unittest.mock import patch

# Add the parent directory to the system path to import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import mocks
from tests.mocks import MockIBKRAPI, MockConfig, MockErrorHandler, AsyncMock

# Import modules to test
from src.config import Config
from src.heartbeat import HeartbeatMonitor
from src.event_loop import IBKREventLoop
from src.error_handler import ErrorHandler


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    # Close all tasks
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()
    # Run the event loop until all tasks are done or cancelled
    if pending:
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    loop.close()


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return MockConfig()


@pytest.fixture
def mock_ibkr_api():
    """Create a mock IBKR API for testing."""
    return MockIBKRAPI()


@pytest.fixture
def mock_error_handler():
    """Create a mock error handler for testing."""
    return MockErrorHandler()


@pytest.fixture
def heartbeat_monitor():
    """Create a heartbeat monitor instance for testing."""
    monitor = HeartbeatMonitor(
        heartbeat_timeout=0.5,  # Short timeout for testing
        heartbeat_interval=0.2,  # Short interval for testing
        on_timeout=lambda: None
    )
    yield monitor
    # Ensure monitor is stopped after test
    if monitor.is_running():
        monitor.stop()


@pytest.fixture
def event_loop_instance():
    """Create an event loop instance for testing."""
    loop = IBKREventLoop(max_workers=2)
    yield loop
    # Ensure loop is stopped after test
    if loop.is_running():
        loop.stop()


@pytest.fixture
def disable_logging():
    """Temporarily disable logging for tests."""
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)


@pytest.fixture
async def async_context():
    """Provide an async context for tests."""
    # Set up any async resources
    yield
    # Clean up async resources


@pytest.fixture
def patched_ibkr_connection():
    """
    Patch the IBKR connection classes with mock objects.
    This allows testing the connection without a real IBKR connection.
    """
    with patch('ibapi.client.EClient') as mock_client, \
         patch('ibapi.wrapper.EWrapper') as mock_wrapper:
        
        # Configure mocks
        mock_instance = MockIBKRAPI()
        mock_client.return_value = mock_instance
        mock_wrapper.return_value = mock_instance
        
        yield mock_instance