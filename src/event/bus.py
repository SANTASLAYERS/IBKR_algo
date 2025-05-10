"""
Event bus implementation for the event system.

This module provides the event bus responsible for event distribution
in the event-driven architecture.
"""

import asyncio
import logging
from collections import defaultdict
from typing import Dict, List, Type, Callable, Any, Union, Set, Optional, Coroutine

from src.event.base import BaseEvent

# Set up logger
logger = logging.getLogger(__name__)


class EventBus:
    """
    Central event bus for distributing events to subscribers.
    
    The EventBus is responsible for:
    1. Managing subscriptions to event types
    2. Dispatching events to appropriate handlers
    3. Supporting both sync and async event handlers
    """
    
    def __init__(self):
        """Initialize the event bus."""
        # Map of event type -> list of handler functions
        self._subscribers: Dict[Type[BaseEvent], List[Callable]] = defaultdict(list)
        
        # Set to track all event types that have subscribers
        self._subscribed_types: Set[Type[BaseEvent]] = set()
        
        # Lock to ensure thread safety
        self._lock = asyncio.Lock()
        
        # Flag to enable/disable event distribution
        self._enabled = True
        
        logger.debug("EventBus initialized")
    
    async def subscribe(self, event_type: Type[BaseEvent], handler: Callable) -> None:
        """
        Subscribe a handler function to an event type.
        
        Args:
            event_type: The event class to subscribe to
            handler: The handler function to call when events of this type occur
            
        The handler can be either a regular function or a coroutine function.
        If it's a regular function, it will be run in the default executor.
        """
        async with self._lock:
            self._subscribers[event_type].append(handler)
            self._subscribed_types.add(event_type)
            
        logger.debug(f"Subscribed handler to {event_type.__name__}")
    
    async def unsubscribe(self, event_type: Type[BaseEvent], handler: Callable) -> bool:
        """
        Unsubscribe a handler from an event type.
        
        Args:
            event_type: The event class to unsubscribe from
            handler: The handler function to remove
            
        Returns:
            bool: True if the handler was removed, False if not found
        """
        async with self._lock:
            if event_type in self._subscribers and handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)
                
                # If no more handlers for this type, remove from subscribed types
                if not self._subscribers[event_type]:
                    self._subscribed_types.discard(event_type)
                    
                logger.debug(f"Unsubscribed handler from {event_type.__name__}")
                return True
            
        logger.debug(f"Handler not found for {event_type.__name__}")
        return False
    
    async def emit(self, event: BaseEvent) -> None:
        """
        Emit an event to all subscribers.
        
        Args:
            event: The event to emit
        """
        if not self._enabled:
            logger.debug(f"Event bus disabled, not emitting {event}")
            return
        
        logger.debug(f"Emitting event: {event}")
        
        async with self._lock:
            event_class = event.__class__
            
            # Create a list of all handlers that should receive this event
            handlers_to_notify = []
            
            # Check direct subscribers to this event type
            if event_class in self._subscribers:
                handlers_to_notify.extend(self._subscribers[event_class])
            
            # Check subscribers to parent event types (inheritance)
            for parent_class in event_class.__mro__[1:]:  # Skip the class itself
                if parent_class == object:
                    break
                if parent_class in self._subscribers:
                    handlers_to_notify.extend(self._subscribers[parent_class])
        
        # Process all handlers outside the lock
        for handler in handlers_to_notify:
            try:
                # Check if handler is a coroutine function
                if asyncio.iscoroutinefunction(handler):
                    # Create a task to run asynchronously
                    asyncio.create_task(handler(event))
                else:
                    # Run synchronous function in the default executor
                    loop = asyncio.get_event_loop()
                    loop.run_in_executor(None, handler, event)
                    
            except Exception as e:
                logger.error(f"Error in event handler for {event}: {e}", exc_info=True)
    
    def enable(self) -> None:
        """Enable event distribution."""
        self._enabled = True
        logger.debug("EventBus enabled")
    
    def disable(self) -> None:
        """Disable event distribution."""
        self._enabled = False
        logger.debug("EventBus disabled")
    
    async def get_subscriber_count(self, event_type: Optional[Type[BaseEvent]] = None) -> Union[int, Dict[str, int]]:
        """
        Get the number of subscribers for an event type or all event types.
        
        Args:
            event_type: The event type to check, or None for all types
            
        Returns:
            Union[int, Dict[str, int]]: Either the count for a specific type or
            a dictionary mapping event type names to counts
        """
        async with self._lock:
            if event_type is not None:
                return len(self._subscribers[event_type])
            
            return {
                event_type.__name__: len(handlers)
                for event_type, handlers in self._subscribers.items()
            }