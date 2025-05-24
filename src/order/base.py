"""
Base order class for the order management system.

This module defines the base Order class and associated enums that provide
common functionality for all order types in the system.
"""

import uuid
import logging
from enum import Enum
from typing import Dict, Any, Optional, List, Set, Callable, Union
from datetime import datetime

# Set up logger
logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    """Possible states of an order in its lifecycle."""
    CREATED = "created"           # Initial state, not submitted to broker
    PENDING_SUBMIT = "pending_submit"  # About to be submitted
    SUBMITTED = "submitted"       # Sent to broker but not yet confirmed
    ACCEPTED = "accepted"         # Accepted by broker
    WORKING = "working"           # Working at broker/exchange
    PARTIALLY_FILLED = "partially_filled"  # Some quantity filled
    FILLED = "filled"             # Fully filled
    CANCELLED = "cancelled"       # Successfully cancelled
    PENDING_CANCEL = "pending_cancel"  # Cancel requested but not confirmed
    REJECTED = "rejected"         # Rejected by broker/exchange
    EXPIRED = "expired"           # Expired due to time in force
    ERROR = "error"               # Order in an error state


class OrderType(Enum):
    """Types of orders."""
    MARKET = "market"             # Market order, execute at best available price
    LIMIT = "limit"               # Limit order, execute at specified price or better
    STOP = "stop"                 # Stop order, becomes market order when trigger price reached
    STOP_LIMIT = "stop_limit"     # Stop limit order, becomes limit order when trigger price reached
    TRAIL = "trail"               # Trailing stop order, stop price adjusts with market
    TRAIL_LIMIT = "trail_limit"   # Trailing stop limit order
    MOC = "moc"                   # Market-on-close
    LOC = "loc"                   # Limit-on-close


class TimeInForce(Enum):
    """Time in force options for orders."""
    DAY = "day"                   # Valid for the day only
    GTC = "gtc"                   # Good till cancelled
    IOC = "ioc"                   # Immediate or cancel
    FOK = "fok"                   # Fill or kill
    GTD = "gtd"                   # Good till date


class OrderSide(Enum):
    """Order side (buy or sell)."""
    BUY = "buy"
    SELL = "sell"


class Order:
    """
    Base class for all order types.
    
    Provides common functionality for order tracking, state management,
    and lifecycle operations.
    """
    
    def __init__(
        self,
        symbol: str,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        side: Optional[OrderSide] = None,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.DAY,
        order_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        group_id: Optional[str] = None
    ):
        """
        Initialize a new order.
        
        Args:
            symbol: Symbol to trade
            quantity: Order quantity (positive for buy, negative for sell)
            order_type: Type of order
            side: Order side (optional, if omitted, determined from quantity)
            limit_price: Limit price (required for LIMIT, STOP_LIMIT orders)
            stop_price: Stop price (required for STOP, STOP_LIMIT orders)
            time_in_force: Time in force option
            order_id: Order ID (generated if not provided)
            parent_id: Parent order ID for child orders
            group_id: Group ID for related orders (like brackets)
        """
        # Identifiers
        self.order_id = order_id or str(uuid.uuid4())
        self.parent_id = parent_id
        self.group_id = group_id
        self.broker_order_id = None
        
        # Order details
        self.symbol = symbol
        self.quantity = quantity
        
        # Determine side if not provided
        if side is None:
            self.side = OrderSide.BUY if quantity > 0 else OrderSide.SELL
        else:
            self.side = side
            # Ensure quantity sign matches side
            if (side == OrderSide.BUY and quantity < 0) or (side == OrderSide.SELL and quantity > 0):
                self.quantity = abs(quantity) * (1 if side == OrderSide.BUY else -1)
        
        self.order_type = order_type
        self.limit_price = limit_price
        self.stop_price = stop_price
        self.time_in_force = time_in_force
        self.expiry_date = None  # For GTD orders
        
        # Order state
        self._status = OrderStatus.CREATED
        self.status_time = datetime.now()
        self.create_time = self.status_time
        self.submit_time = None
        self.fill_time = None
        self.cancel_time = None
        self.last_update_time = self.status_time
        
        # Fill details
        self.filled_quantity = 0.0
        self.remaining_quantity = abs(quantity)
        self.avg_fill_price = None
        self.last_fill_price = None
        self.last_fill_time = None
        self.commission = 0.0
        self.fills = []  # List of individual fills
        
        # Additional info
        self.reason = None  # Reason for rejection, cancellation, etc.
        self.error_code = None
        self.error_message = None
        self.metadata = {}  # Additional order metadata
        
        # Validate required fields based on order type
        self._validate()
        
        logger.debug(f"Created order {self.order_id} for {symbol}: {self.side.value} {abs(quantity)} {order_type.value}")
    
    @property
    def status(self) -> OrderStatus:
        """Get the current order status."""
        return self._status
    
    @property
    def is_active(self) -> bool:
        """Check if the order is active (not filled, cancelled, rejected, or expired)."""
        return self._status in (
            OrderStatus.PENDING_SUBMIT,
            OrderStatus.SUBMITTED,
            OrderStatus.ACCEPTED,
            OrderStatus.WORKING,
            OrderStatus.PARTIALLY_FILLED
        )
    
    @property
    def is_filled(self) -> bool:
        """Check if the order is fully filled."""
        return self._status == OrderStatus.FILLED
    
    @property
    def is_complete(self) -> bool:
        """Check if the order is complete (filled, cancelled, rejected, or expired)."""
        return self._status in (
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED
        )
    
    @property
    def is_pending(self) -> bool:
        """Check if the order is pending (not yet working at the broker)."""
        return self._status in (
            OrderStatus.CREATED,
            OrderStatus.PENDING_SUBMIT,
            OrderStatus.SUBMITTED
        )
    
    @property
    def is_buy(self) -> bool:
        """Check if this is a buy order."""
        return self.side == OrderSide.BUY
    
    @property
    def fill_percentage(self) -> float:
        """Get the percentage of the order that has been filled."""
        if abs(self.quantity) == 0:
            return 0.0
        return (self.filled_quantity / abs(self.quantity)) * 100.0
    
    def _validate(self):
        """Validate order parameters based on order type."""
        if self.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT, OrderType.LOC) and self.limit_price is None:
            raise ValueError(f"Limit price is required for {self.order_type.value} orders")
        
        if self.order_type in (OrderType.STOP, OrderType.STOP_LIMIT) and self.stop_price is None:
            raise ValueError(f"Stop price is required for {self.order_type.value} orders")
        
        if self.time_in_force == TimeInForce.GTD and self.expiry_date is None:
            raise ValueError("Expiry date is required for GTD orders")
    
    def update_status(self, new_status: OrderStatus, reason: Optional[str] = None) -> bool:
        """
        Update the order status.
        
        Args:
            new_status: The new status to set
            reason: Optional reason for the status change
            
        Returns:
            bool: True if the status was changed, False if it was already set
        """
        if self._status == new_status:
            return False
        
        old_status = self._status
        self._status = new_status
        self.last_update_time = datetime.now()
        self.status_time = self.last_update_time
        
        # Special status handling
        if new_status == OrderStatus.SUBMITTED and not self.submit_time:
            self.submit_time = self.status_time
        elif new_status == OrderStatus.FILLED and not self.fill_time:
            self.fill_time = self.status_time
        elif new_status == OrderStatus.CANCELLED and not self.cancel_time:
            self.cancel_time = self.status_time
        
        # Set reason if provided
        if reason:
            self.reason = reason
        
        logger.info(f"Order {self.order_id} status changed: {old_status.value} -> {new_status.value} ({reason or 'no reason'})")
        return True
    
    def add_fill(self, quantity: float, price: float, commission: Optional[float] = None, fill_time: Optional[datetime] = None) -> bool:
        """
        Add a fill to the order.
        
        Args:
            quantity: Filled quantity (should be positive)
            price: Fill price
            commission: Optional commission paid for this fill
            fill_time: Optional fill time (current time if not provided)
            
        Returns:
            bool: True if the fill was added successfully
        """
        if quantity <= 0:
            logger.warning(f"Ignoring non-positive fill quantity: {quantity}")
            return False
        
        if quantity > self.remaining_quantity:
            logger.warning(f"Fill quantity ({quantity}) exceeds remaining quantity ({self.remaining_quantity})")
            return False
        
        # Add fill details
        fill_time = fill_time or datetime.now()
        fill = {
            "quantity": quantity,
            "price": price,
            "commission": commission or 0.0,
            "time": fill_time
        }
        self.fills.append(fill)
        
        # Update fill summary
        prev_filled = self.filled_quantity
        self.filled_quantity += quantity
        self.remaining_quantity -= quantity
        self.last_fill_price = price
        self.last_fill_time = fill_time
        
        # Calculate average fill price
        if prev_filled > 0:
            self.avg_fill_price = ((prev_filled * self.avg_fill_price) + (quantity * price)) / self.filled_quantity
        else:
            self.avg_fill_price = price
        
        # Add commission
        if commission:
            self.commission += commission
        
        # Update status if fully filled
        if self.remaining_quantity <= 0.000001:  # Small threshold to handle floating point issues
            self.update_status(OrderStatus.FILLED, "Order fully filled")
        elif self._status != OrderStatus.PARTIALLY_FILLED:
            self.update_status(OrderStatus.PARTIALLY_FILLED, "Order partially filled")
        
        logger.info(f"Order {self.order_id} filled: {quantity} @ {price} ({self.filled_quantity}/{abs(self.quantity)})")
        return True
    
    def cancel(self, reason: Optional[str] = None) -> bool:
        """
        Cancel the order.
        
        Args:
            reason: Optional reason for cancellation
            
        Returns:
            bool: True if the order can be cancelled, False if already complete
        """
        if self.is_complete:
            logger.warning(f"Cannot cancel completed order {self.order_id}")
            return False
        
        self.update_status(OrderStatus.PENDING_CANCEL, reason or "User cancelled")
        return True
    
    def reject(self, reason: str, error_code: Optional[str] = None, error_message: Optional[str] = None) -> None:
        """
        Reject the order.
        
        Args:
            reason: Reason for rejection
            error_code: Optional error code
            error_message: Optional detailed error message
        """
        self.reason = reason
        self.error_code = error_code
        self.error_message = error_message
        self.update_status(OrderStatus.REJECTED, reason)
    
    def expire(self, reason: Optional[str] = None) -> None:
        """
        Expire the order.
        
        Args:
            reason: Optional reason for expiration
        """
        self.update_status(OrderStatus.EXPIRED, reason or "Order expired")
    
    def set_broker_order_id(self, broker_order_id: str) -> None:
        """
        Set the broker's order ID.
        
        Args:
            broker_order_id: The broker-assigned order ID
        """
        self.broker_order_id = broker_order_id
        logger.debug(f"Order {self.order_id} assigned broker ID: {broker_order_id}")
    
    def set_metadata(self, key: str, value: Any) -> None:
        """
        Set metadata for the order.
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the order to a dictionary."""
        return {
            "order_id": self.order_id,
            "broker_order_id": self.broker_order_id,
            "parent_id": self.parent_id,
            "group_id": self.group_id,
            "symbol": self.symbol,
            "quantity": self.quantity,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "time_in_force": self.time_in_force.value,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "status": self._status.value,
            "create_time": self.create_time.isoformat(),
            "submit_time": self.submit_time.isoformat() if self.submit_time else None,
            "fill_time": self.fill_time.isoformat() if self.fill_time else None,
            "cancel_time": self.cancel_time.isoformat() if self.cancel_time else None,
            "last_update_time": self.last_update_time.isoformat(),
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "avg_fill_price": self.avg_fill_price,
            "last_fill_price": self.last_fill_price,
            "last_fill_time": self.last_fill_time.isoformat() if self.last_fill_time else None,
            "commission": self.commission,
            "reason": self.reason,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "fills": self.fills
        }
    
    def __str__(self) -> str:
        """String representation of the order."""
        action = "BUY" if self.side == OrderSide.BUY else "SELL"
        status_str = self._status.value.upper()
        
        price_str = ""
        if self.order_type == OrderType.LIMIT:
            price_str = f" limit={self.limit_price}"
        elif self.order_type == OrderType.STOP:
            price_str = f" stop={self.stop_price}"
        elif self.order_type == OrderType.STOP_LIMIT:
            price_str = f" limit={self.limit_price} stop={self.stop_price}"
        
        filled_str = ""
        if self.filled_quantity > 0:
            filled_str = f" (filled: {self.filled_quantity}/{abs(self.quantity)}@{self.avg_fill_price})"
            
        return f"{self.symbol} {action} {abs(self.quantity)} {self.order_type.value}{price_str}{filled_str} [{status_str}]"