"""
Base event classes for the event system.

This module defines the base event class that all events in the system inherit from,
as well as common functionality for event handling.
"""

import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class BaseEvent:
    """Base class for all events in the system."""
    
    # Unique identifier for this event
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Timestamp when the event was created
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Additional metadata for the event
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Source of the event (e.g., "market", "order", "api")
    source: Optional[str] = None
    
    def __post_init__(self):
        """Post-initialization hook."""
        # Ensure timestamp is timezone-aware
        if self.timestamp.tzinfo is None:
            from datetime import timezone
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)
    
    @property
    def event_type(self) -> str:
        """Get the event type as a string."""
        return self.__class__.__name__
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the event to a dictionary."""
        result = {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
        }
        
        # Add class-specific attributes (excluding the ones above)
        for key, value in self.__dict__.items():
            if key not in ["event_id", "timestamp", "metadata", "source"]:
                result[key] = value
        
        # Add metadata
        if self.metadata:
            result["metadata"] = self.metadata
            
        return result
    
    def __str__(self) -> str:
        """String representation of the event."""
        return f"{self.event_type}(id={self.event_id}, ts={self.timestamp.isoformat()})"