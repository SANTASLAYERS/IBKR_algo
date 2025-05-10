"""
Order group management for the order management system.

This module provides functionality for managing related orders like bracket orders
(entry + stop loss + take profit) and OCO (one-cancels-other) orders.
"""

import uuid
import logging
from typing import Dict, Any, Optional, List, Set, Tuple
from datetime import datetime

from src.order.base import Order, OrderStatus, OrderType, TimeInForce, OrderSide

# Set up logger
logger = logging.getLogger(__name__)


class OrderGroup:
    """
    Base class for managing a group of related orders.
    
    Provides common functionality for tracking and managing multiple related orders.
    """
    
    def __init__(self, group_id: Optional[str] = None):
        """
        Initialize a new order group.
        
        Args:
            group_id: Optional group ID (generated if not provided)
        """
        self.group_id = group_id or str(uuid.uuid4())
        self.orders: Dict[str, Order] = {}  # order_id -> Order
        self.metadata: Dict[str, Any] = {}
        self.create_time = datetime.now()
        self.last_update_time = self.create_time
        
        logger.debug(f"Created order group {self.group_id}")
    
    def add_order(self, order: Order) -> str:
        """
        Add an order to the group.
        
        Args:
            order: The order to add
            
        Returns:
            str: The order ID
        """
        order.group_id = self.group_id
        self.orders[order.order_id] = order
        self.last_update_time = datetime.now()
        
        logger.debug(f"Added order {order.order_id} to group {self.group_id}")
        return order.order_id
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """
        Get an order by ID.
        
        Args:
            order_id: The order ID
            
        Returns:
            Optional[Order]: The order if found, None otherwise
        """
        return self.orders.get(order_id)
    
    def get_orders(self) -> List[Order]:
        """
        Get all orders in the group.
        
        Returns:
            List[Order]: All orders in the group
        """
        return list(self.orders.values())
    
    def cancel_all(self, reason: Optional[str] = None) -> int:
        """
        Cancel all active orders in the group.
        
        Args:
            reason: Optional reason for cancellation
            
        Returns:
            int: Number of orders cancelled
        """
        cancelled = 0
        for order in self.orders.values():
            if order.is_active and order.cancel(reason or "Group cancelled"):
                cancelled += 1
        
        if cancelled > 0:
            self.last_update_time = datetime.now()
            logger.info(f"Cancelled {cancelled} orders in group {self.group_id}")
        
        return cancelled
    
    def is_complete(self) -> bool:
        """
        Check if all orders in the group are complete.
        
        Returns:
            bool: True if all orders are complete, False otherwise
        """
        return all(order.is_complete for order in self.orders.values())
    
    def is_active(self) -> bool:
        """
        Check if any order in the group is active.
        
        Returns:
            bool: True if any order is active, False otherwise
        """
        return any(order.is_active for order in self.orders.values())
    
    def get_filled_orders(self) -> List[Order]:
        """
        Get all filled orders in the group.
        
        Returns:
            List[Order]: All filled orders
        """
        return [order for order in self.orders.values() if order.is_filled]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the order group to a dictionary."""
        return {
            "group_id": self.group_id,
            "orders": {order_id: order.to_dict() for order_id, order in self.orders.items()},
            "metadata": self.metadata,
            "create_time": self.create_time.isoformat(),
            "last_update_time": self.last_update_time.isoformat(),
            "is_complete": self.is_complete(),
            "is_active": self.is_active()
        }
    
    def __str__(self) -> str:
        """String representation of the order group."""
        return f"OrderGroup {self.group_id} with {len(self.orders)} orders"


class BracketOrder(OrderGroup):
    """
    Bracket order group (entry + stop loss + take profit).
    
    A bracket order consists of:
    1. An entry order (market or limit)
    2. A stop loss order (triggered when price moves against the position)
    3. A take profit order (limit order at target price)
    
    The stop loss and take profit orders are submitted once the entry order fills,
    and they are linked as OCO (one-cancels-other).
    """
    
    def __init__(
        self,
        symbol: str,
        quantity: float,
        entry_price: Optional[float] = None,
        stop_loss_price: float = 0.0,
        take_profit_price: float = 0.0,
        entry_type: OrderType = OrderType.MARKET,
        group_id: Optional[str] = None
    ):
        """
        Initialize a new bracket order.
        
        Args:
            symbol: Symbol to trade
            quantity: Order quantity (positive for buy, negative for sell)
            entry_price: Entry price (required for limit orders)
            stop_loss_price: Stop loss price (must be less than entry for buys, greater for sells)
            take_profit_price: Take profit price (must be greater than entry for buys, less for sells)
            entry_type: Entry order type (MARKET or LIMIT)
            group_id: Optional group ID (generated if not provided)
        """
        super().__init__(group_id)
        
        # Validate that prices are sensible
        self._validate_prices(quantity, entry_price, stop_loss_price, take_profit_price, entry_type)
        
        # Create the entry order
        self.entry_order = Order(
            symbol=symbol,
            quantity=quantity,
            order_type=entry_type,
            limit_price=entry_price if entry_type == OrderType.LIMIT else None,
            time_in_force=TimeInForce.DAY
        )
        self.add_order(self.entry_order)
        
        # Store the stop loss and take profit prices (orders created when entry fills)
        self.entry_order_id = self.entry_order.order_id
        self.stop_loss_price = stop_loss_price
        self.take_profit_price = take_profit_price
        self.stop_loss_order_id = None
        self.take_profit_order_id = None
        
        # Flag to track whether child orders have been created
        self.child_orders_created = False
        
        # Add bracket-specific metadata
        self.metadata["bracket_type"] = "standard"
        self.metadata["entry_type"] = entry_type.value
        self.metadata["is_buy"] = quantity > 0
        
        logger.info(f"Created bracket order for {symbol}: {entry_type.value} entry at {entry_price}, "
                   f"stop at {stop_loss_price}, target at {take_profit_price}")
    
    def _validate_prices(
        self,
        quantity: float,
        entry_price: Optional[float],
        stop_loss_price: float,
        take_profit_price: float,
        entry_type: OrderType
    ) -> None:
        """
        Validate that the bracket order prices make sense.
        
        Args:
            quantity: Order quantity
            entry_price: Entry price
            stop_loss_price: Stop loss price
            take_profit_price: Take profit price
            entry_type: Entry order type
            
        Raises:
            ValueError: If the prices do not make sense
        """
        is_buy = quantity > 0
        
        # For limit orders, entry price is required
        if entry_type == OrderType.LIMIT and entry_price is None:
            raise ValueError("Entry price is required for limit orders")
        
        # Skip further validation for market orders without entry price
        if entry_price is None:
            return
        
        # Validate stop loss price
        if stop_loss_price <= 0:
            raise ValueError("Stop loss price must be greater than zero")
        
        if is_buy and stop_loss_price >= entry_price:
            raise ValueError("Stop loss price must be less than entry price for buy orders")
        elif not is_buy and stop_loss_price <= entry_price:
            raise ValueError("Stop loss price must be greater than entry price for sell orders")
        
        # Validate take profit price
        if take_profit_price <= 0:
            raise ValueError("Take profit price must be greater than zero")
        
        if is_buy and take_profit_price <= entry_price:
            raise ValueError("Take profit price must be greater than entry price for buy orders")
        elif not is_buy and take_profit_price >= entry_price:
            raise ValueError("Take profit price must be less than entry price for sell orders")
    
    def handle_entry_fill(self, fill_price: float) -> Tuple[str, str]:
        """
        Handle the entry order fill by creating stop loss and take profit orders.
        
        Args:
            fill_price: Fill price of the entry order
            
        Returns:
            Tuple[str, str]: Stop loss and take profit order IDs
        """
        if self.child_orders_created:
            logger.warning(f"Child orders already created for bracket {self.group_id}")
            return self.stop_loss_order_id, self.take_profit_order_id
        
        # Get entry order details
        entry_order = self.orders[self.entry_order_id]
        symbol = entry_order.symbol
        quantity = -entry_order.quantity  # Opposite direction for exit orders
        is_buy = entry_order.side == OrderSide.BUY
        
        # Create stop loss order
        stop_loss_order = Order(
            symbol=symbol,
            quantity=quantity,
            order_type=OrderType.STOP,
            stop_price=self.stop_loss_price,
            time_in_force=TimeInForce.GTC,  # Usually want stop loss to persist
            parent_id=self.entry_order_id
        )
        self.add_order(stop_loss_order)
        self.stop_loss_order_id = stop_loss_order.order_id
        
        # Create take profit order
        take_profit_order = Order(
            symbol=symbol,
            quantity=quantity,
            order_type=OrderType.LIMIT,
            limit_price=self.take_profit_price,
            time_in_force=TimeInForce.GTC,  # Usually want take profit to persist
            parent_id=self.entry_order_id
        )
        self.add_order(take_profit_order)
        self.take_profit_order_id = take_profit_order.order_id
        
        # Link the orders as OCO (one-cancels-other)
        stop_loss_order.metadata["oco_order_id"] = take_profit_order.order_id
        take_profit_order.metadata["oco_order_id"] = stop_loss_order.order_id
        
        # Mark child orders as created
        self.child_orders_created = True
        self.last_update_time = datetime.now()
        
        logger.info(f"Created child orders for bracket {self.group_id}: "
                    f"stop loss at {self.stop_loss_price}, take profit at {self.take_profit_price}")
        
        return self.stop_loss_order_id, self.take_profit_order_id
    
    def update_stops(self, new_stop_loss: Optional[float] = None, new_take_profit: Optional[float] = None) -> bool:
        """
        Update the stop loss and/or take profit prices.
        
        If the child orders have already been created, this updates the existing orders.
        If not, it updates the stored prices to be used when creating the orders.
        
        Args:
            new_stop_loss: New stop loss price
            new_take_profit: New take profit price
            
        Returns:
            bool: True if the stops were updated
        """
        updated = False
        
        # Update stop loss if provided
        if new_stop_loss is not None and new_stop_loss != self.stop_loss_price:
            # Validate the new stop loss price
            entry_order = self.orders[self.entry_order_id]
            is_buy = entry_order.side == OrderSide.BUY
            
            # Get fill price if available, otherwise use limit price
            reference_price = None
            if entry_order.avg_fill_price is not None:
                reference_price = entry_order.avg_fill_price
            elif entry_order.limit_price is not None:
                reference_price = entry_order.limit_price
            
            # Validate if we have a reference price
            if reference_price is not None:
                if is_buy and new_stop_loss >= reference_price:
                    raise ValueError("Stop loss price must be less than entry price for buy orders")
                elif not is_buy and new_stop_loss <= reference_price:
                    raise ValueError("Stop loss price must be greater than entry price for sell orders")
            
            # Update the price
            self.stop_loss_price = new_stop_loss
            updated = True
            
            # If the stop loss order has been created, update it
            if self.stop_loss_order_id and self.stop_loss_order_id in self.orders:
                stop_loss_order = self.orders[self.stop_loss_order_id]
                stop_loss_order.stop_price = new_stop_loss
                logger.info(f"Updated stop loss for bracket {self.group_id} to {new_stop_loss}")
        
        # Update take profit if provided
        if new_take_profit is not None and new_take_profit != self.take_profit_price:
            # Validate the new take profit price
            entry_order = self.orders[self.entry_order_id]
            is_buy = entry_order.side == OrderSide.BUY
            
            # Get fill price if available, otherwise use limit price
            reference_price = None
            if entry_order.avg_fill_price is not None:
                reference_price = entry_order.avg_fill_price
            elif entry_order.limit_price is not None:
                reference_price = entry_order.limit_price
            
            # Validate if we have a reference price
            if reference_price is not None:
                if is_buy and new_take_profit <= reference_price:
                    raise ValueError("Take profit price must be greater than entry price for buy orders")
                elif not is_buy and new_take_profit >= reference_price:
                    raise ValueError("Take profit price must be less than entry price for sell orders")
            
            # Update the price
            self.take_profit_price = new_take_profit
            updated = True
            
            # If the take profit order has been created, update it
            if self.take_profit_order_id and self.take_profit_order_id in self.orders:
                take_profit_order = self.orders[self.take_profit_order_id]
                take_profit_order.limit_price = new_take_profit
                logger.info(f"Updated take profit for bracket {self.group_id} to {new_take_profit}")
        
        if updated:
            self.last_update_time = datetime.now()
        
        return updated
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the bracket order to a dictionary."""
        bracket_dict = super().to_dict()
        bracket_dict.update({
            "order_type": "bracket",
            "entry_order_id": self.entry_order_id,
            "stop_loss_price": self.stop_loss_price,
            "take_profit_price": self.take_profit_price,
            "stop_loss_order_id": self.stop_loss_order_id,
            "take_profit_order_id": self.take_profit_order_id,
            "child_orders_created": self.child_orders_created
        })
        return bracket_dict
    
    def __str__(self) -> str:
        """String representation of the bracket order."""
        entry_order = self.orders[self.entry_order_id]
        action = "BUY" if entry_order.side == OrderSide.BUY else "SELL"
        status = "PENDING" if not self.child_orders_created else "ACTIVE"
        
        return (f"Bracket {self.group_id}: {entry_order.symbol} {action} {abs(entry_order.quantity)} "
                f"@ {entry_order.limit_price or 'MARKET'}, SL={self.stop_loss_price}, TP={self.take_profit_price} "
                f"[{status}]")


class OCOGroup(OrderGroup):
    """
    One-Cancels-Other (OCO) order group.
    
    An OCO group consists of two or more orders where if one order is filled or
    triggered, the remaining orders are cancelled.
    """
    
    def __init__(self, orders: List[Order], group_id: Optional[str] = None):
        """
        Initialize a new OCO group.
        
        Args:
            orders: List of orders to include in the OCO group
            group_id: Optional group ID (generated if not provided)
        """
        super().__init__(group_id)
        
        if len(orders) < 2:
            raise ValueError("OCO group must contain at least two orders")
        
        # Add all orders to the group and link them
        for order in orders:
            self.add_order(order)
            
            # Link to all other orders in the group
            for other_order in orders:
                if other_order != order:
                    if "oco_order_ids" not in order.metadata:
                        order.metadata["oco_order_ids"] = []
                    order.metadata["oco_order_ids"].append(other_order.order_id)
        
        # Set OCO specific metadata
        self.metadata["order_type"] = "oco"
        
        logger.info(f"Created OCO group {self.group_id} with {len(orders)} orders")
    
    def handle_fill(self, filled_order_id: str) -> List[str]:
        """
        Handle an order fill by cancelling all other orders in the group.
        
        Args:
            filled_order_id: The ID of the filled order
            
        Returns:
            List[str]: List of cancelled order IDs
        """
        cancelled_orders = []
        for order_id, order in self.orders.items():
            if order_id != filled_order_id and order.is_active:
                if order.cancel("OCO order filled"):
                    cancelled_orders.append(order_id)
        
        if cancelled_orders:
            logger.info(f"OCO group {self.group_id}: cancelled {len(cancelled_orders)} orders "
                        f"after {filled_order_id} was filled")
        
        return cancelled_orders
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the OCO group to a dictionary."""
        oco_dict = super().to_dict()
        oco_dict["order_type"] = "oco"
        return oco_dict
    
    def __str__(self) -> str:
        """String representation of the OCO group."""
        orders_str = ", ".join(str(order) for order in self.orders.values())
        return f"OCO Group {self.group_id}: {orders_str}"