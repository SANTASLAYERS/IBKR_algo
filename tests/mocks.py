#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import MagicMock

class MockIBKRAPI:
    """Mock of the IBKR API for testing purposes."""
    
    def __init__(self):
        self.isConnected = MagicMock(return_value=True)
        self.connect = MagicMock(return_value=None)
        self.disconnect = MagicMock(return_value=None)
        self.reqCurrentTime = MagicMock(return_value=None)
        self.run = MagicMock(return_value=None)
        self.reqAccountUpdates = MagicMock(return_value=None)
        self.reqMktData = MagicMock(return_value=None)
        self.connectAck = MagicMock(return_value=None)
        self.connectionClosed = MagicMock(return_value=None)
        self.currentTime = MagicMock(return_value=None)
        self.error = MagicMock(return_value=None)
        self.managedAccounts = MagicMock(return_value=None)
        
        # Simulation control
        self.should_fail_connect = False
        self.should_timeout = False
        self.should_disconnect = False
        self.connection_state = "disconnected"
        
    def set_connection_state(self, state: str):
        """Set the connection state for testing."""
        self.connection_state = state
        if state == "connected":
            self.isConnected.return_value = True
        else:
            self.isConnected.return_value = False
    
    def simulate_connect(self, success: bool = True):
        """Simulate a connection attempt."""
        if not success or self.should_fail_connect:
            raise ConnectionError("Simulated connection failure")
        
        self.set_connection_state("connected")
        
    def simulate_disconnect(self):
        """Simulate a disconnect."""
        self.set_connection_state("disconnected")
        
    def simulate_heartbeat_timeout(self):
        """Simulate a heartbeat timeout."""
        self.should_timeout = True
        
    def simulate_error(self, req_id: int, error_code: int, error_string: str):
        """Simulate an error from IBKR."""
        self.error(req_id, error_code, error_string, "")
        
    async def simulate_async_connect(self, success: bool = True):
        """Simulate an async connection attempt."""
        await asyncio.sleep(0.1)  # Small delay to simulate network
        self.simulate_connect(success)
        return success


class MockConfig:
    """Mock configuration for testing."""
    
    def __init__(self):
        self.host = "127.0.0.1"
        self.port = 7497
        self.client_id = 1
        self.heartbeat_timeout = 0.5  # Short timeout for testing
        self.heartbeat_interval = 0.2  # Short interval for testing
        self.reconnect_delay = 0.1  # Short delay for testing
        self.max_reconnect_attempts = 3
        self.request_timeout = 1.0  # Short timeout for testing
        self.log_level = "INFO"
        self.log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        self.log_file = None
        self.account_ids = []
        self.custom_settings = {}


class MockErrorHandler:
    """Mock error handler for testing."""
    
    def __init__(self):
        self.handle_error = MagicMock()
        self.register_callback = MagicMock()
        self.unregister_callback = MagicMock()
        self.get_error_history = MagicMock(return_value=[])
        self.clear_error_history = MagicMock()
        
        # Storage for callbacks
        self.callbacks = {}
        
    def add_callback(self, callback: Callable, category: str = "any"):
        """Add a callback for a specific error category."""
        if category not in self.callbacks:
            self.callbacks[category] = []
        self.callbacks[category].append(callback)
        
    def simulate_error(self, req_id: int, error_code: int, error_string: str, category: str = "any"):
        """Simulate an error and trigger callbacks."""
        self.handle_error(req_id, error_code, error_string)
        
        # Call relevant callbacks for the category
        if category in self.callbacks:
            for callback in self.callbacks[category]:
                callback({"req_id": req_id, "error_code": error_code, "error_string": error_string})


class AsyncMock(MagicMock):
    """Mock for async functions."""
    
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)