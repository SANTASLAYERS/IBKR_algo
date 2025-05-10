"""
Event system for the IBKR Trading Framework.

This package provides an event-driven architecture for handling trading events,
including market data, order updates, position changes, and API signal events.
"""

from src.event.base import BaseEvent
from src.event.bus import EventBus

__all__ = ["BaseEvent", "EventBus"]