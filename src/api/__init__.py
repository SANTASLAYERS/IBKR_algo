"""
API integration components for the IBKR Trading Framework.

This package provides functionality for integrating with the options flow monitor API,
including prediction signal monitoring and event generation.
"""

from src.api.monitor import OptionsFlowMonitor

__all__ = ["OptionsFlowMonitor"]