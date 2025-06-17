"""
Order manager for the order management system.

This module provides the OrderManager class that manages order tracking,
submission, and integration with Alpaca.
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Set, Union, Callable, Tuple

from src.event.bus import EventBus
from src.event.order import (
    OrderEvent, NewOrderEvent, OrderStatusEvent, FillEvent, 
    CancelEvent, RejectEvent, OrderGroupEvent
)
from src.order.base import Order, OrderStatus, OrderType, TimeInForce, OrderSide
from src.order.group import OrderGroup, BracketOrder, OCOGroup

# Set up logger
logger = logging.getLogger(__name__)


class OrderManager:
    """
    Manages orders and integrates with Alpaca broker connection.
    
    The OrderManager is responsible for:
    1. Tracking all orders and order groups
    2. Submitting orders to Alpaca
    3. Handling order status updates and fills
    4. Managing order relationships (parent-child, OCO)
    5. Generating order events
    """
    
    def __init__(self, event_bus: EventBus, broker_connection=None):
        """
        Initialize the order manager.
        
        Args:
            event_bus: Event bus for publishing order events
            broker_connection: Optional AlpacaConnection instance for order execution
        """
        self.event_bus = event_bus
        self.gateway = broker_connection  # Keep 'gateway' name for backward compatibility
        
        # Order tracking
        self._orders: Dict[str, Order] = {}  # order_id -> Order
        self._broker_order_map: Dict[str, str] = {}  # broker_order_id -> order_id
        self._order_groups: Dict[str, OrderGroup] = {}  # group_id -> OrderGroup
        
        # Status tracking
        self._pending_orders: Set[str] = set()  # order_ids of pending orders
        self._active_orders: Set[str] = set()  # order_ids of active orders
        self._completed_orders: Set[str] = set()  # order_ids of completed orders
        
        # Symbol tracking
        self._orders_by_symbol: Dict[str, Set[str]] = {}  # symbol -> set(order_ids)
        
        logger.debug("OrderManager initialized")
    
    async def initialize(self):
        """Initialize the OrderManager and set up Alpaca callbacks if available."""
        if self.gateway:
            # Set up callbacks for order status updates
            def on_order_update(order_data):
                """Handle order updates from Alpaca."""
                # Schedule the async handler in the main event loop
                asyncio.create_task(
                    self.handle_order_status_update(
                        broker_order_id=order_data.get('id'),
                        status=order_data.get('status'),
                        filled_qty=order_data.get('filled_qty', 0),
                        filled_avg_price=order_data.get('filled_avg_price', 0)
                    )
                )
            
            def on_trade_update(trade_data):
                """Handle trade updates from Alpaca."""
                # Schedule the async handler in the main event loop
                asyncio.create_task(
                    self.handle_execution_update(
                        broker_order_id=trade_data.get('order_id'),
                        exec_id=trade_data.get('id'),
                        symbol=trade_data.get('symbol'),
                        side=trade_data.get('side'),
                        quantity=trade_data.get('qty'),
                        price=trade_data.get('price')
                    )
                )
            
            # Register callbacks with Alpaca connection
            if hasattr(self.gateway, 'register_order_callback'):
                self.gateway.register_order_callback(on_order_update)
                self.gateway.register_trade_callback(on_trade_update)
                logger.info("OrderManager callbacks set up with AlpacaConnection")
            else:
                logger.info("AlpacaConnection does not support callbacks")
        else:
            logger.info("OrderManager initialized without broker connection")
    
    async def create_order(self, 
                        symbol: str,
                        quantity: float,
                        order_type: OrderType = OrderType.MARKET,
                        side: Optional[OrderSide] = None,
                        limit_price: Optional[float] = None,
                        stop_price: Optional[float] = None,
                        time_in_force: TimeInForce = TimeInForce.DAY,
                        parent_id: Optional[str] = None,
                        auto_submit: bool = False,
                        **kwargs) -> Order:
        """
        Create a new order.
        
        Args:
            symbol: Symbol to trade
            quantity: Order quantity (positive for buy, negative for sell)
            order_type: Type of order
            side: Order side (optional, if omitted, determined from quantity)
            limit_price: Limit price (required for LIMIT, STOP_LIMIT orders)
            stop_price: Stop price (required for STOP, STOP_LIMIT orders)
            time_in_force: Time in force option
            parent_id: Parent order ID for child orders
            auto_submit: Whether to automatically submit the order
            **kwargs: Additional order parameters
            
        Returns:
            Order: The created order
        """
        # Create the order
        order = Order(
            symbol=symbol,
            quantity=quantity,
            order_type=order_type,
            side=side,
            limit_price=limit_price,
            stop_price=stop_price,
            time_in_force=time_in_force,
            parent_id=parent_id,
            **kwargs
        )
        
        # Register the order
        self._register_order(order)
        
        # Create and emit the new order event
        event = NewOrderEvent(
            order_id=order.order_id,
            symbol=order.symbol,
            status=order.status,
            order_type=order.order_type,
            quantity=order.quantity,
            limit_price=order.limit_price,
            stop_price=order.stop_price,
            create_time=order.create_time
        )
        await self.event_bus.emit(event)
        
        # Submit the order if requested
        if auto_submit:
            await self.submit_order(order.order_id)
        
        return order
    
    async def create_bracket_order(self,
                                 symbol: str,
                                 quantity: float,
                                 entry_price: Optional[float] = None,
                                 stop_loss_price: float = 0.0,
                                 take_profit_price: float = 0.0,
                                 entry_type: OrderType = OrderType.MARKET,
                                 auto_submit: bool = False) -> BracketOrder:
        """
        Create a bracket order (entry + stop loss + take profit).
        
        Args:
            symbol: Symbol to trade
            quantity: Order quantity (positive for buy, negative for sell)
            entry_price: Entry price (required for limit orders)
            stop_loss_price: Stop loss price
            take_profit_price: Take profit price
            entry_type: Entry order type (MARKET or LIMIT)
            auto_submit: Whether to automatically submit the entry order
            
        Returns:
            BracketOrder: The created bracket order
        """
        # Create the bracket order
        bracket = BracketOrder(
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            entry_type=entry_type
        )
        
        # Register the order group
        self._register_order_group(bracket)
        
        # Register all the orders
        for order in bracket.orders.values():
            self._register_order(order)
        
        # Create and emit the order group event
        event = OrderGroupEvent(
            order_id=bracket.entry_order_id,
            symbol=symbol,
            group_type="bracket",
            group_id=bracket.group_id,
            related_orders=[bracket.entry_order_id]
        )
        await self.event_bus.emit(event)
        
        # Submit the entry order if requested
        if auto_submit:
            await self.submit_order(bracket.entry_order_id)
        
        return bracket
    
    async def create_oco_orders(self,
                             orders: List[Dict[str, Any]],
                             auto_submit: bool = False) -> OCOGroup:
        """
        Create an OCO (one-cancels-other) order group.
        
        Args:
            orders: List of order parameters for each order in the group
            auto_submit: Whether to automatically submit the orders
            
        Returns:
            OCOGroup: The created OCO order group
        """
        # Create all the orders
        order_objects = []
        for order_params in orders:
            order = Order(**order_params)
            order_objects.append(order)
        
        # Create the OCO group
        oco_group = OCOGroup(order_objects)
        
        # Register the order group
        self._register_order_group(oco_group)
        
        # Register all the orders
        for order in oco_group.orders.values():
            self._register_order(order)
        
        # Create and emit the order group event
        event = OrderGroupEvent(
            order_id=oco_group.get_orders()[0].order_id,
            symbol=oco_group.get_orders()[0].symbol,
            group_type="oco",
            group_id=oco_group.group_id,
            related_orders=[order.order_id for order in oco_group.get_orders()]
        )
        await self.event_bus.emit(event)
        
        # Submit the orders if requested
        if auto_submit:
            for order in oco_group.get_orders():
                await self.submit_order(order.order_id)
        
        return oco_group
    
    async def submit_order(self, order_id: str) -> bool:
        """
        Submit an order to the broker.

        Args:
            order_id: The order ID to submit

        Returns:
            bool: True if the order was submitted successfully
        """
        order = self._orders.get(order_id)
        if not order:
            logger.warning(f"Cannot submit unknown order {order_id}")
            return False

        if order.status != OrderStatus.CREATED:
            logger.warning(f"Cannot submit order {order_id} with status {order.status.value}")
            return False

        # Update the order status
        order.update_status(OrderStatus.PENDING_SUBMIT, "Submitting to broker")
        self._pending_orders.add(order_id)

        # Create and emit the order status event
        event = OrderStatusEvent(
            order_id=order.order_id,
            symbol=order.symbol,
            status=order.status,
            previous_status=OrderStatus.CREATED,
            status_time=order.status_time
        )
        await self.event_bus.emit(event)

        # If we have an Alpaca connection, submit the order
        if self.gateway and hasattr(self.gateway, 'placeOrder'):
            logger.info(f"Submitting order {order_id} to Alpaca")

            try:
                # Convert order type to Alpaca format
                order_type_map = {
                    OrderType.MARKET: 'MKT',
                    OrderType.LIMIT: 'LMT',
                    OrderType.STOP: 'STP',
                    OrderType.STOP_LIMIT: 'STP_LMT'
                }
                
                # Convert time in force to Alpaca format
                tif_map = {
                    TimeInForce.DAY: 'DAY',
                    TimeInForce.GTC: 'GTC',
                    TimeInForce.IOC: 'IOC',
                    TimeInForce.FOK: 'FOK'
                }
                
                # Submit the order to broker
                self.gateway.placeOrder(
                    orderId=str(order_id),
                    symbol=order.symbol,
                    quantity=abs(order.quantity),
                    order_type=order_type_map.get(order.order_type, 'MKT'),
                    side='BUY' if order.is_buy else 'SELL',
                    limit_price=order.limit_price,
                    stop_price=order.stop_price,
                    time_in_force=tif_map.get(order.time_in_force, 'DAY')
                )
                
                # For now, use the order_id as the broker_order_id
                # In a real implementation, we'd get this from the broker response
                broker_order_id = order_id
                
                if not broker_order_id:
                    error_msg = "Failed to submit order to Alpaca"
                    logger.error(f"{error_msg} for {order_id}")

                    # Update the order status
                    order.reject(error_msg)

                    # Move to completed orders
                    self._pending_orders.discard(order_id)
                    self._completed_orders.add(order_id)

                    # Create and emit the reject event
                    event = RejectEvent(
                        order_id=order.order_id,
                        symbol=order.symbol,
                        status=order.status,
                        reject_time=order.status_time,
                        reason=error_msg
                    )
                    await self.event_bus.emit(event)

                    return False

                logger.info(f"Got broker order ID {broker_order_id} for order {order_id}")

                # Store broker order ID mapping
                broker_order_id_str = str(broker_order_id)
                order.set_broker_order_id(broker_order_id_str)
                self._broker_order_map[broker_order_id_str] = order_id

                # Update the order status
                order.update_status(OrderStatus.SUBMITTED, "Submitted to broker")

                # Move the order to active
                self._pending_orders.discard(order_id)
                self._active_orders.add(order_id)

                # Create and emit the order status event
                event = OrderStatusEvent(
                    order_id=order.order_id,
                    symbol=order.symbol,
                    status=order.status,
                    previous_status=OrderStatus.PENDING_SUBMIT,
                    status_time=order.status_time
                )
                await self.event_bus.emit(event)

                return True

            except Exception as e:
                logger.error(f"Error submitting order {order_id}: {e}")

                # Update the order status
                order.reject(str(e))

                # Move to completed orders
                self._pending_orders.discard(order_id)
                self._completed_orders.add(order_id)

                # Create and emit the reject event
                event = RejectEvent(
                    order_id=order.order_id,
                    symbol=order.symbol,
                    status=order.status,
                    reject_time=order.status_time,
                    reason=str(e)
                )
                await self.event_bus.emit(event)

                return False
        else:
            # No broker connection, simulate order submission
            logger.info(f"No broker connection, simulating order submission for {order_id}")

            # Simulate a broker order ID
            broker_order_id = f"SIM{order_id[-6:]}"
            order.set_broker_order_id(broker_order_id)
            self._broker_order_map[broker_order_id] = order_id

            # Update the order status
            order.update_status(OrderStatus.SUBMITTED, "Simulated submission")

            # Move the order to active
            self._pending_orders.discard(order_id)
            self._active_orders.add(order_id)

            # Create and emit the order status event
            event = OrderStatusEvent(
                order_id=order.order_id,
                symbol=order.symbol,
                status=order.status,
                previous_status=OrderStatus.PENDING_SUBMIT,
                status_time=order.status_time
            )
            await self.event_bus.emit(event)

            # Simulate later acceptance by the broker
            await asyncio.sleep(0.1)

            # Update the order status
            order.update_status(OrderStatus.ACCEPTED, "Simulated acceptance")

            # Create and emit the order status event
            event = OrderStatusEvent(
                order_id=order.order_id,
                symbol=order.symbol,
                status=order.status,
                previous_status=OrderStatus.SUBMITTED,
                status_time=order.status_time
            )
            await self.event_bus.emit(event)

            return True
    
    async def cancel_order(self, order_id: str, reason: Optional[str] = None) -> bool:
        """
        Cancel an order.

        Args:
            order_id: The order ID to cancel
            reason: Optional reason for cancellation

        Returns:
            bool: True if the cancellation was initiated
        """
        order = self._orders.get(order_id)
        if not order:
            logger.warning(f"Cannot cancel unknown order {order_id}")
            return False

        if not order.is_active:
            logger.warning(f"Cannot cancel inactive order {order_id} with status {order.status.value}")
            return False

        # Try to cancel the order
        if not order.cancel(reason or "User cancelled"):
            return False

        # Create and emit the cancel event
        event = CancelEvent(
            order_id=order.order_id,
            symbol=order.symbol,
            status=order.status,
            cancel_time=order.status_time,
            reason=order.reason or reason or "User cancelled"
        )
        await self.event_bus.emit(event)

        # If we have an Alpaca connection and a broker order ID, send cancellation
        if self.gateway and order.broker_order_id and hasattr(self.gateway, 'cancelOrder'):
            logger.info(f"Sending cancellation for order {order_id} (broker ID: {order.broker_order_id})")

            try:
                # Use Alpaca connection to cancel the order
                self.gateway.cancelOrder(order.broker_order_id)
                logger.info(f"Cancellation request sent for order {order_id}")
                    
                # Final cancellation will be confirmed by Alpaca callbacks
                return True

            except Exception as e:
                logger.error(f"Error cancelling order {order_id}: {e}")
                return False
        else:
            # No broker connection or broker order ID, simulate cancellation
            logger.info(f"No broker connection or broker ID, simulating order cancellation for {order_id}")

            # Simulate later cancellation confirmation
            await asyncio.sleep(0.1)

            # Update the order status
            order.update_status(OrderStatus.CANCELLED, "Simulated cancellation")

            # Move the order from active to completed
            self._active_orders.discard(order_id)
            self._completed_orders.add(order_id)

            # Create and emit the order status event
            event = OrderStatusEvent(
                order_id=order.order_id,
                symbol=order.symbol,
                status=order.status,
                previous_status=OrderStatus.PENDING_CANCEL,
                status_time=order.status_time
            )
            await self.event_bus.emit(event)

            # Handle any child orders
            await self._handle_cancelled_order(order)

            return True
    
    async def cancel_all_orders(self, symbol: Optional[str] = None, reason: Optional[str] = None) -> int:
        """
        Cancel all active orders, optionally filtered by symbol.

        Args:
            symbol: Optional symbol to filter orders
            reason: Optional reason for cancellation

        Returns:
            int: Number of orders cancelled
        """
        # Get active orders
        active_orders = await self.get_active_orders(symbol)

        # Cancel each order
        cancelled_count = 0
        for order in active_orders:
            if await self.cancel_order(order.order_id, reason):
                cancelled_count += 1

        logger.info(f"Cancelled {cancelled_count} orders" + (f" for {symbol}" if symbol else ""))
        return cancelled_count
    
    async def cancel_order_group(self, group_id: str, reason: Optional[str] = None) -> int:
        """
        Cancel all orders in an order group.

        Args:
            group_id: The order group ID
            reason: Optional reason for cancellation

        Returns:
            int: Number of orders cancelled
        """
        group = self._order_groups.get(group_id)
        if not group:
            logger.warning(f"Cannot cancel unknown order group {group_id}")
            return 0

        # Cancel all orders in the group
        cancelled_count = 0
        for order in group.get_orders():
            if await self.cancel_order(order.order_id, reason):
                cancelled_count += 1

        logger.info(f"Cancelled {cancelled_count} orders in group {group_id}")
        return cancelled_count
    
    async def process_fill(self, 
                         order_id: str, 
                         quantity: float, 
                         price: float, 
                         commission: Optional[float] = None,
                         fill_time: Optional[datetime] = None) -> Tuple[bool, Optional[str]]:
        """
        Process a fill for an order.

        Args:
            order_id: The order ID that was filled
            quantity: The filled quantity
            price: The fill price
            commission: Optional commission for the fill
            fill_time: Optional timestamp of the fill

        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        order = self._orders.get(order_id)
        if not order:
            error_msg = f"Cannot process fill for unknown order {order_id}"
            logger.warning(error_msg)
            return False, error_msg

        # Process the fill
        if not order.add_fill(quantity, price, commission, fill_time):
            error_msg = f"Failed to process fill for order {order_id}"
            logger.warning(error_msg)
            return False, error_msg

        # Create and emit the fill event
        event = FillEvent(
            order_id=order.order_id,
            symbol=order.symbol,
            status=order.status,
            fill_time=fill_time or datetime.now(),
            fill_price=price,
            fill_quantity=quantity,
            commission=commission,
            cumulative_quantity=order.filled_quantity,
            average_price=order.avg_fill_price,
            remaining_quantity=order.remaining_quantity
        )
        await self.event_bus.emit(event)

        # Check if the order is now complete
        if order.is_filled:
            # Move the order from active to completed
            self._active_orders.discard(order_id)
            self._completed_orders.add(order_id)

            # Create and emit the order status event
            event = OrderStatusEvent(
                order_id=order.order_id,
                symbol=order.symbol,
                status=order.status,
                previous_status=OrderStatus.ACCEPTED,
                status_time=order.status_time
            )
            await self.event_bus.emit(event)

            # Handle any child orders
            if order.group_id and order.group_id in self._order_groups:
                group = self._order_groups[order.group_id]
                if isinstance(group, BracketOrder):
                    # If this is the entry order of a bracket, submit the exit orders
                    if order_id == group.entry_order_id:
                        logger.info(f"Entry order filled for bracket {group.group_id}, submitting exit orders")
                        if group.stop_loss_order_id:
                            await self.submit_order(group.stop_loss_order_id)
                        if group.take_profit_order_id:
                            await self.submit_order(group.take_profit_order_id)

        return True, None
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """
        Get an order by ID.

        Args:
            order_id: The order ID

        Returns:
            Optional[Order]: The order if found
        """
        return self._orders.get(order_id)
    
    async def get_order_by_broker_id(self, broker_order_id: str) -> Optional[Order]:
        """
        Get an order by broker order ID.

        Args:
            broker_order_id: The broker order ID

        Returns:
            Optional[Order]: The order if found
        """
        order_id = self._broker_order_map.get(broker_order_id)
        if order_id:
            return self._orders.get(order_id)
        return None
    
    async def get_orders_for_symbol(self, symbol: str) -> List[Order]:
        """
        Get all orders for a symbol.

        Args:
            symbol: The symbol

        Returns:
            List[Order]: List of orders for the symbol
        """
        order_ids = self._orders_by_symbol.get(symbol, set())
        return [self._orders[order_id] for order_id in order_ids if order_id in self._orders]
    
    async def get_active_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """
        Get all active orders, optionally filtered by symbol.

        Args:
            symbol: Optional symbol to filter orders

        Returns:
            List[Order]: List of active orders
        """
        active_orders = []
        for order_id in self._active_orders:
            order = self._orders.get(order_id)
            if order and (not symbol or order.symbol == symbol):
                active_orders.append(order)
        
        return active_orders
    
    async def get_completed_orders(self, symbol: Optional[str] = None, limit: Optional[int] = None) -> List[Order]:
        """
        Get completed orders, optionally filtered by symbol.

        Args:
            symbol: Optional symbol to filter orders
            limit: Optional limit on number of orders to return

        Returns:
            List[Order]: List of completed orders
        """
        completed_orders = []
        for order_id in self._completed_orders:
            order = self._orders.get(order_id)
            if order and (not symbol or order.symbol == symbol):
                completed_orders.append(order)
        
        # Sort by completion time (most recent first)
        completed_orders.sort(key=lambda o: o.status_time, reverse=True)
        
        # Apply limit if specified
        if limit:
            completed_orders = completed_orders[:limit]
        
        return completed_orders
    
    async def get_order_group(self, group_id: str) -> Optional[OrderGroup]:
        """
        Get an order group by ID.

        Args:
            group_id: The order group ID

        Returns:
            Optional[OrderGroup]: The order group if found
        """
        return self._order_groups.get(group_id)
    
    async def get_active_order_groups(self) -> List[OrderGroup]:
        """
        Get all active order groups.

        Returns:
            List[OrderGroup]: List of active order groups
        """
        active_groups = []
        for group in self._order_groups.values():
            if group.is_active:
                active_groups.append(group)
        return active_groups
    
    def _register_order(self, order: Order) -> None:
        """
        Register an order internally.

        Args:
            order: The order to register
        """
        order_id = order.order_id
        symbol = order.symbol

        # Add to main order dict
        self._orders[order_id] = order

        # Add to symbol tracking
        if symbol not in self._orders_by_symbol:
            self._orders_by_symbol[symbol] = set()
        self._orders_by_symbol[symbol].add(order_id)

        # Add to pending orders
        self._pending_orders.add(order_id)

        logger.debug(f"Registered order {order_id} for {symbol}")
    
    def _register_order_group(self, group: OrderGroup) -> None:
        """
        Register an order group internally.

        Args:
            group: The order group to register
        """
        self._order_groups[group.group_id] = group
        logger.debug(f"Registered order group {group.group_id}")
    
    async def _handle_cancelled_order(self, order: Order) -> None:
        """
        Handle a cancelled order, including cancelling related orders.

        Args:
            order: The cancelled order
        """
        # If this order is part of a group, handle related orders
        if order.group_id and order.group_id in self._order_groups:
            group = self._order_groups[order.group_id]
            
            # If this order is part of a bracket, cancel the other exit order
            if isinstance(group, BracketOrder):
                bracket = group
                
                # If this is one of the exit orders, cancel the other
                if order.order_id == bracket.stop_loss_order_id and bracket.take_profit_order_id:
                    other_order = self._orders.get(bracket.take_profit_order_id)
                    if other_order and other_order.is_active:
                        await self.cancel_order(bracket.take_profit_order_id, "Bracket order cancelled")
                elif order.order_id == bracket.take_profit_order_id and bracket.stop_loss_order_id:
                    other_order = self._orders.get(bracket.stop_loss_order_id)
                    if other_order and other_order.is_active:
                        await self.cancel_order(bracket.stop_loss_order_id, "Bracket order cancelled")
            
            # If this order is part of an OCO group, cancel all other orders
            elif isinstance(group, OCOGroup):
                oco_group = group
                for other_order in oco_group.get_orders():
                    if other_order.order_id != order.order_id and other_order.is_active:
                        await self.cancel_order(other_order.order_id, "OCO order cancelled")
    
    async def handle_order_status_update(self,
                                      broker_order_id: str,
                                      status: str,
                                      filled_qty: float,
                                      filled_avg_price: float) -> None:
        """
        Handle an order status update from Alpaca.

        Args:
            broker_order_id: The broker's order ID
            status: The order status from Alpaca
            filled_qty: The filled quantity
            filled_avg_price: The average fill price
        """
        # Get the order
        order = await self.get_order_by_broker_id(broker_order_id)
        if not order:
            logger.warning(f"Received status update for unknown broker order {broker_order_id}")
            return

        order_id = order.order_id
        logger.debug(f"Order status update for {order_id}: {status}, filled={filled_qty}")

        # Map Alpaca status to our status
        status_map = {
            'new': OrderStatus.SUBMITTED,
            'accepted': OrderStatus.ACCEPTED,
            'pending_new': OrderStatus.PENDING_SUBMIT,
            'partially_filled': OrderStatus.PARTIAL_FILL,
            'filled': OrderStatus.FILLED,
            'done_for_day': OrderStatus.CANCELLED,
            'canceled': OrderStatus.CANCELLED,
            'expired': OrderStatus.CANCELLED,
            'replaced': OrderStatus.CANCELLED,
            'pending_cancel': OrderStatus.PENDING_CANCEL,
            'pending_replace': OrderStatus.PENDING_CANCEL,
            'rejected': OrderStatus.REJECTED,
            'suspended': OrderStatus.INACTIVE,
            'calculated': OrderStatus.ACCEPTED
        }

        new_status = status_map.get(status)
        if not new_status:
            logger.warning(f"Unknown Alpaca order status: {status} for order {order_id}")
            return

        # Update the order status if it changed
        if order.status != new_status:
            previous_status = order.status
            order.update_status(new_status, f"Alpaca status: {status}")

            # Update tracking sets
            if new_status in [OrderStatus.SUBMITTED, OrderStatus.ACCEPTED, OrderStatus.PARTIAL_FILL]:
                self._pending_orders.discard(order_id)
                self._active_orders.add(order_id)
            elif new_status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
                self._pending_orders.discard(order_id)
                self._active_orders.discard(order_id)
                self._completed_orders.add(order_id)

            # Create and emit the order status event
            event = OrderStatusEvent(
                order_id=order.order_id,
                symbol=order.symbol,
                status=new_status,
                previous_status=previous_status,
                status_time=order.status_time
            )
            await self.event_bus.emit(event)

            # Handle cancelled orders
            if new_status == OrderStatus.CANCELLED:
                await self._handle_cancelled_order(order)

        # Process fills if any
        if filled_qty > 0 and filled_qty > order.filled_quantity:
            fill_qty = filled_qty - order.filled_quantity
            await self.process_fill(order_id, fill_qty, filled_avg_price)
    
    async def handle_execution_update(self,
                                   broker_order_id: str,
                                   exec_id: str,
                                   symbol: str,
                                   side: str,
                                   quantity: float,
                                   price: float,
                                   commission: Optional[float] = None) -> None:
        """
        Handle an execution update from Alpaca.

        Args:
            broker_order_id: The broker's order ID
            exec_id: The execution ID
            symbol: The symbol
            side: The side (buy/sell)
            quantity: The executed quantity
            price: The execution price
            commission: Optional commission
        """
        # Get the order
        order = await self.get_order_by_broker_id(broker_order_id)
        if not order:
            logger.warning(f"Received execution for unknown broker order {broker_order_id}")
            return

        logger.info(f"Execution for order {order.order_id}: {quantity} @ {price}")

        # Process the fill
        await self.process_fill(order.order_id, quantity, price, commission)