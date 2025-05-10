"""
Order-related events for the event system.

This module defines events related to order management, such as order creation,
updates, fills, and cancellations.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from src.event.base import BaseEvent


class OrderStatus(Enum):
    """Possible states of an order."""
    CREATED = "created"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    ERROR = "error"


class OrderType(Enum):
    """Types of orders."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAIL = "trail"
    TRAIL_LIMIT = "trail_limit"


@dataclass
class OrderEvent(BaseEvent):
    """Base class for all order-related events."""
    
    source: str = "order"
    
    # Order identifier
    order_id: str = ""
    
    # Symbol the order is for
    symbol: str = ""
    
    # Current status of the order
    status: OrderStatus = OrderStatus.CREATED
    
    # Order type
    order_type: OrderType = OrderType.MARKET
    
    # Order quantity (positive for buy, negative for sell)
    quantity: float = 0.0
    
    # Limit price (if applicable)
    limit_price: Optional[float] = None
    
    # Stop price (if applicable)
    stop_price: Optional[float] = None
    
    # The time the order was created
    create_time: Optional[datetime] = None
    
    # The time the order was last updated
    update_time: Optional[datetime] = None
    
    # Additional order metadata
    order_data: Dict[str, Any] = field(default_factory=dict)
    

@dataclass
class NewOrderEvent(OrderEvent):
    """Event for a new order being created."""
    
    # The time the order was created
    create_time: datetime = field(default_factory=datetime.now)


@dataclass
class OrderStatusEvent(OrderEvent):
    """Event for an order status update."""
    
    # Previous status
    previous_status: Optional[OrderStatus] = None
    
    # The time the status changed
    status_time: datetime = field(default_factory=datetime.now)
    
    # Reason for status change
    reason: Optional[str] = None


@dataclass
class FillEvent(OrderEvent):
    """Event for an order fill (partial or complete)."""
    
    # Fill price
    fill_price: float = 0.0
    
    # Fill quantity
    fill_quantity: float = 0.0
    
    # Cumulative filled quantity
    cumulative_quantity: float = 0.0
    
    # Remaining quantity to be filled
    remaining_quantity: float = 0.0
    
    # The time of the fill
    fill_time: datetime = field(default_factory=datetime.now)
    
    # Commission paid for this fill
    commission: Optional[float] = None
    
    # Fill identifier
    fill_id: Optional[str] = None
    
    # Whether this is a partial fill
    is_partial: bool = False


@dataclass
class CancelEvent(OrderEvent):
    """Event for an order cancellation."""
    
    # The time the order was cancelled
    cancel_time: datetime = field(default_factory=datetime.now)
    
    # Reason for cancellation
    reason: Optional[str] = None
    
    # Whether the cancellation was user-initiated
    user_initiated: bool = True


@dataclass
class RejectEvent(OrderEvent):
    """Event for an order rejection."""
    
    # The time the order was rejected
    reject_time: datetime = field(default_factory=datetime.now)
    
    # Reason for rejection
    reason: str = ""
    
    # Error code (if available)
    error_code: Optional[str] = None
    
    # Detailed error message
    error_message: Optional[str] = None


@dataclass
class OrderGroupEvent(OrderEvent):
    """Event for operations on groups of related orders."""
    
    # List of related order IDs
    related_orders: List[str] = field(default_factory=list)
    
    # Group type (e.g., "bracket", "oco")
    group_type: str = ""
    
    # Group identifier
    group_id: Optional[str] = None