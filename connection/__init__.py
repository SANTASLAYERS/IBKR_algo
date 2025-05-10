"""
IBKR Connection Module

Provides robust connection handling for Interactive Brokers API with
asynchronous support, heartbeat monitoring, and automatic reconnection.

This package will import and reexport the main connection components
from the src directory.
"""

# Import and re-export core functionality from src
from src.connection import IBKRConnection
from src.heartbeat import HeartbeatMonitor
from src.error_handler import ErrorHandler