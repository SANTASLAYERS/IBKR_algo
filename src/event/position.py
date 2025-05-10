"""
Position-related events for the event system.

This module defines events related to position management, such as opening,
updating, and closing positions.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from src.event.base import BaseEvent


class PositionStatus(Enum):
    """Possible states of a position."""
    PLANNED = "planned"
    OPENING = "opening"
    OPEN = "open"
    ADJUSTING = "adjusting"
    CLOSING = "closing"
    CLOSED = "closed"


@dataclass
class PositionEvent(BaseEvent):
    """Base class for all position-related events."""
    
    source: str = "position"
    
    # Position identifier
    position_id: str = ""
    
    # Symbol the position is for
    symbol: str = ""
    
    # Current status of the position
    status: PositionStatus = PositionStatus.PLANNED
    
    # Current quantity (positive for long, negative for short)
    quantity: float = 0.0
    
    # Average entry price
    entry_price: Optional[float] = None
    
    # Current market price
    current_price: Optional[float] = None
    
    # Unrealized profit/loss
    unrealized_pnl: Optional[float] = None
    
    # Realized profit/loss (for closed positions or partial closes)
    realized_pnl: Optional[float] = None
    
    # The time the position was created
    create_time: Optional[datetime] = None
    
    # The time the position was last updated
    update_time: Optional[datetime] = None
    
    # Additional position metadata
    position_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PositionOpenEvent(PositionEvent):
    """Event for a new position being opened."""
    
    # The time the position was opened
    open_time: datetime = field(default_factory=datetime.now)
    
    # Related order IDs
    order_ids: List[str] = field(default_factory=list)
    
    # Initial stop loss price
    stop_loss: Optional[float] = None
    
    # Initial take profit price
    take_profit: Optional[float] = None
    
    # Strategy that generated this position
    strategy: Optional[str] = None


@dataclass
class PositionUpdateEvent(PositionEvent):
    """Event for a position update."""
    
    # Previous status
    previous_status: Optional[PositionStatus] = None
    
    # Previous quantity
    previous_quantity: Optional[float] = None
    
    # Previous entry price
    previous_entry_price: Optional[float] = None
    
    # The time of the update
    update_time: datetime = field(default_factory=datetime.now)
    
    # Reason for the update
    reason: Optional[str] = None
    
    # Whether stop loss was updated
    stop_loss_updated: bool = False
    
    # New stop loss price (if updated)
    new_stop_loss: Optional[float] = None
    
    # Whether take profit was updated
    take_profit_updated: bool = False
    
    # New take profit price (if updated)
    new_take_profit: Optional[float] = None


@dataclass
class PositionCloseEvent(PositionEvent):
    """Event for a position being closed."""
    
    # The time the position was closed
    close_time: datetime = field(default_factory=datetime.now)
    
    # Final realized profit/loss
    realized_pnl: float = 0.0
    
    # Related order IDs
    order_ids: List[str] = field(default_factory=list)
    
    # Reason for closing
    reason: Optional[str] = None
    
    # Exit price
    exit_price: float = 0.0
    
    # Whether the position was fully closed
    fully_closed: bool = True
    
    # If partially closed, the quantity closed
    quantity_closed: Optional[float] = None