"""
Order manager for the order management system.

This module provides the OrderManager class that manages order tracking,
submission, and integration with the IBKR Gateway.
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
    Manages orders and integrates with TWS Connection.
    
    The OrderManager is responsible for:
    1. Tracking all orders and order groups
    2. Submitting orders to TWS via TWSConnection
    3. Handling order status updates and fills
    4. Managing order relationships (parent-child, OCO)
    5. Generating order events
    """
    
    def __init__(self, event_bus: EventBus, tws_connection=None):
        """
        Initialize the order manager.
        
        Args:
            event_bus: Event bus for publishing order events
            tws_connection: Optional TWSConnection instance for order execution
        """
        self.event_bus = event_bus
        self.gateway = tws_connection  # Keep 'gateway' name for backward compatibility
        
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
        """Initialize the OrderManager and set up TWS callbacks if available."""
        if self.gateway:
            # Set up callbacks for order status updates
            def on_order_status(orderId, status, filled, remaining, avgFillPrice, permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
                """Handle order status updates from TWS."""
                asyncio.create_task(
                    self.handle_order_status_update(
                        broker_order_id=str(orderId),
                        status=status,
                        filled=filled,
                        remaining=remaining,
                        avg_fill_price=avgFillPrice,
                        last_fill_price=lastFillPrice
                    )
                )
            
            def on_exec_details(reqId, contract, execution):
                """Handle execution details from TWS."""
                asyncio.create_task(
                    self.handle_execution_update(
                        broker_order_id=str(execution.orderId),
                        exec_id=execution.execId,
                        symbol=contract.symbol,
                        side=execution.side,
                        quantity=execution.shares,
                        price=execution.price,
                        commission=None  # Commission comes in separate callback
                    )
                )
            
            # Override TWS callbacks to route to our handlers
            self.gateway.orderStatus = on_order_status
            self.gateway.execDetails = on_exec_details
                
            logger.info("OrderManager callbacks set up with TWSConnection")
        else:
            logger.info("OrderManager initialized without TWS connection")
    
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

        # If we have a TWS connection, submit the order
        if self.gateway and hasattr(self.gateway, 'placeOrder'):
            logger.info(f"Submitting order {order_id} to TWS")

            try:
                # Convert our order to IB's order format
                ib_contract = self._create_ib_contract(order)
                ib_order = self._create_ib_order(order)

                # Get next valid order ID from TWS
                broker_order_id = self.gateway.get_next_order_id()
                if not broker_order_id:
                    # If no order ID available, try to get one
                    self.gateway.request_next_order_id()
                    await asyncio.sleep(1)  # Wait for order ID
                    broker_order_id = self.gateway.get_next_order_id()

                if not broker_order_id:
                    error_msg = "Could not get valid order ID from TWS"
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
                
                # Submit the order to TWS using IBAPI
                logger.info(f"Calling placeOrder with ID {broker_order_id}, contract {ib_contract}, order {ib_order}")
                self.gateway.placeOrder(broker_order_id, ib_contract, ib_order)
                logger.info(f"placeOrder called successfully for order {order_id}")

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
            # No TWS connection, simulate order submission
            logger.info(f"No TWS connection, simulating order submission for {order_id}")

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
            reason=reason or "User cancelled"
        )
        await self.event_bus.emit(event)

        # If we have a TWS connection and a broker order ID, send cancellation to IB
        if self.gateway and hasattr(self.gateway, 'cancelOrder') and order.broker_order_id:
            logger.info(f"Cancelling order {order_id} with broker ID {order.broker_order_id}")

            try:
                # Convert to int if possible
                try:
                    broker_order_id_int = int(order.broker_order_id)
                except ValueError:
                    broker_order_id_int = 0

                if broker_order_id_int > 0:
                    # Use TWS connection to cancel the order
                    self.gateway.cancelOrder(broker_order_id_int)

                    # Update order status to pending cancel
                    # Final cancellation will be confirmed by IB callbacks
                    order.update_status(OrderStatus.PENDING_CANCEL, reason or "User requested cancellation")

                    return True
                else:
                    logger.error(f"Invalid broker order ID format: {order.broker_order_id}")
                    return False

            except Exception as e:
                logger.error(f"Error cancelling order {order_id}: {e}")
                return False
        else:
            # No TWS connection or broker order ID, simulate cancellation
            logger.info(f"No TWS connection or broker ID, simulating order cancellation for {order_id}")

            # Update the order status
            order.update_status(OrderStatus.CANCELLED, reason or "User cancelled")

            # Move to completed orders
            self._active_orders.discard(order_id)
            self._completed_orders.add(order_id)

            # Handle OCO orders
            await self._handle_cancelled_order(order)

            return True
    
    async def cancel_all_orders(self, symbol: Optional[str] = None, reason: Optional[str] = None) -> int:
        """
        Cancel all active orders, optionally filtered by symbol.
        
        Args:
            symbol: Optional symbol to filter by
            reason: Optional reason for cancellation
            
        Returns:
            int: Number of orders cancelled
        """
        cancelled = 0
        
        if symbol:
            # Cancel orders for a specific symbol
            order_ids = list(self._orders_by_symbol.get(symbol, set()))
        else:
            # Cancel all active orders
            order_ids = list(self._active_orders)
        
        for order_id in order_ids:
            if await self.cancel_order(order_id, reason or "Cancel all orders"):
                cancelled += 1
        
        return cancelled
    
    async def cancel_order_group(self, group_id: str, reason: Optional[str] = None) -> int:
        """
        Cancel all active orders in a group.
        
        Args:
            group_id: The group ID to cancel
            reason: Optional reason for cancellation
            
        Returns:
            int: Number of orders cancelled
        """
        group = self._order_groups.get(group_id)
        if not group:
            logger.warning(f"Cannot cancel unknown order group {group_id}")
            return 0
        
        cancelled = 0
        for order_id in [o.order_id for o in group.get_orders() if o.is_active]:
            if await self.cancel_order(order_id, reason or f"Group {group_id} cancelled"):
                cancelled += 1
        
        return cancelled
    
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
            commission: Optional commission paid
            fill_time: Optional fill timestamp
            
        Returns:
            Tuple[bool, Optional[str]]: Success flag and position ID if applicable
        """
        order = self._orders.get(order_id)
        if not order:
            logger.warning(f"Cannot process fill for unknown order {order_id}")
            return False, None
        
        if not order.is_active and not order.status == OrderStatus.ACCEPTED:
            logger.warning(f"Cannot process fill for inactive order {order_id} with status {order.status.value}")
            return False, None
        
        # Process the fill
        if not order.add_fill(quantity, price, commission, fill_time):
            logger.error(f"Failed to add fill to order {order_id}")
            return False, None
        
        # If fully filled, move to completed orders
        if order.is_filled:
            self._active_orders.discard(order_id)
            self._completed_orders.add(order_id)
        
        # Create and emit the fill event
        event = FillEvent(
            order_id=order.order_id,
            symbol=order.symbol,
            status=order.status,
            fill_price=price,
            fill_quantity=quantity,
            cumulative_quantity=order.filled_quantity,
            remaining_quantity=order.remaining_quantity,
            fill_time=fill_time or datetime.now(),
            commission=commission
        )
        await self.event_bus.emit(event)
        
        # Handle related orders if this is part of a group
        if order.group_id and order.group_id in self._order_groups:
            group = self._order_groups[order.group_id]
            
            # For bracket orders, create child orders when entry fills
            if isinstance(group, BracketOrder) and order.order_id == group.entry_order_id:
                if not group.child_orders_created:
                    stop_id, target_id = group.handle_entry_fill(price)
                    
                    # Submit the child orders
                    await self.submit_order(stop_id)
                    await self.submit_order(target_id)
            
            # For OCO orders, cancel other orders when one fills
            elif isinstance(group, OCOGroup):
                cancelled_orders = group.handle_fill(order.order_id)
                
                # Cancel the related orders
                for other_id in cancelled_orders:
                    await self.cancel_order(other_id, "OCO order filled")
        
        # Handle child orders if this is a parent order
        position_id = None
        
        return True, position_id
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """
        Get an order by ID.
        
        Args:
            order_id: The order ID to retrieve
            
        Returns:
            Optional[Order]: The order if found, None otherwise
        """
        return self._orders.get(order_id)
    
    async def get_order_by_broker_id(self, broker_order_id: str) -> Optional[Order]:
        """
        Get an order by broker order ID.
        
        Args:
            broker_order_id: The broker order ID to retrieve
            
        Returns:
            Optional[Order]: The order if found, None otherwise
        """
        order_id = self._broker_order_map.get(broker_order_id)
        if order_id:
            return self._orders.get(order_id)
        return None
    
    async def get_orders_for_symbol(self, symbol: str) -> List[Order]:
        """
        Get all orders for a symbol.
        
        Args:
            symbol: The symbol to get orders for
            
        Returns:
            List[Order]: List of orders for the symbol
        """
        order_ids = self._orders_by_symbol.get(symbol, set())
        return [self._orders[order_id] for order_id in order_ids if order_id in self._orders]
    
    async def get_active_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """
        Get all active orders, optionally filtered by symbol.
        
        Args:
            symbol: Optional symbol to filter by
            
        Returns:
            List[Order]: List of active orders
        """
        if symbol:
            # Get active orders for a specific symbol
            symbol_orders = self._orders_by_symbol.get(symbol, set())
            order_ids = symbol_orders.intersection(self._active_orders)
        else:
            # Get all active orders
            order_ids = self._active_orders
        
        return [self._orders[order_id] for order_id in order_ids]
    
    async def get_completed_orders(self, symbol: Optional[str] = None, limit: Optional[int] = None) -> List[Order]:
        """
        Get completed orders, optionally filtered by symbol and limited.
        
        Args:
            symbol: Optional symbol to filter by
            limit: Optional limit on the number of orders to return
            
        Returns:
            List[Order]: List of completed orders
        """
        if symbol:
            # Get completed orders for a specific symbol
            symbol_orders = self._orders_by_symbol.get(symbol, set())
            order_ids = symbol_orders.intersection(self._completed_orders)
        else:
            # Get all completed orders
            order_ids = self._completed_orders
        
        # Sort by completion time and limit if requested
        completed_orders = [self._orders[order_id] for order_id in order_ids]
        completed_orders.sort(key=lambda o: o.status_time, reverse=True)
        
        if limit:
            completed_orders = completed_orders[:limit]
        
        return completed_orders
    
    async def get_order_group(self, group_id: str) -> Optional[OrderGroup]:
        """
        Get an order group by ID.
        
        Args:
            group_id: The group ID to retrieve
            
        Returns:
            Optional[OrderGroup]: The order group if found, None otherwise
        """
        return self._order_groups.get(group_id)
    
    async def get_active_order_groups(self) -> List[OrderGroup]:
        """
        Get all active order groups.
        
        Returns:
            List[OrderGroup]: List of active order groups
        """
        return [group for group in self._order_groups.values() if group.is_active()]
    
    def _register_order(self, order: Order) -> None:
        """
        Register an order with the manager.
        
        Args:
            order: The order to register
        """
        # Add to orders map
        self._orders[order.order_id] = order
        
        # Add to symbol map
        if order.symbol not in self._orders_by_symbol:
            self._orders_by_symbol[order.symbol] = set()
        self._orders_by_symbol[order.symbol].add(order.order_id)
        
        # Add to status map
        if order.is_active:
            self._active_orders.add(order.order_id)
        elif order.is_complete:
            self._completed_orders.add(order.order_id)
        else:
            self._pending_orders.add(order.order_id)
        
        logger.debug(f"Registered order {order.order_id} for {order.symbol}")
    
    def _register_order_group(self, group: OrderGroup) -> None:
        """
        Register an order group with the manager.
        
        Args:
            group: The order group to register
        """
        self._order_groups[group.group_id] = group
        logger.debug(f"Registered order group {group.group_id}")
    
    async def _handle_cancelled_order(self, order: Order) -> None:
        """
        Handle special processing for cancelled orders.

        Args:
            order: The cancelled order
        """
        # Check if this is an OCO order
        if "oco_order_id" in order.metadata:
            # For single OCO relationship
            oco_id = order.metadata["oco_order_id"]
            if oco_id in self._orders:
                logger.debug(f"Cancelled order {order.order_id} has OCO order {oco_id}")

        # Check if this is part of an OCO group with multiple orders
        if "oco_order_ids" in order.metadata:
            # For multiple OCO relationships
            for oco_id in order.metadata["oco_order_ids"]:
                if oco_id in self._orders:
                    logger.debug(f"Cancelled order {order.order_id} has OCO order {oco_id}")

        # Check if this is a parent order with children
        child_orders = [o for o in self._orders.values() if o.parent_id == order.order_id]
        if child_orders:
            logger.debug(f"Cancelled order {order.order_id} has {len(child_orders)} child orders")

            # Cancel all child orders
            for child in child_orders:
                if child.is_active:
                    await self.cancel_order(child.order_id, f"Parent order {order.order_id} cancelled")

    def _create_ib_contract(self, order: Order) -> 'Contract':
        """
        Create an IB Contract object from our order.

        Args:
            order: Our internal order object

        Returns:
            Contract: IB API Contract object
        """
        from ibapi.contract import Contract

        contract = Contract()
        contract.symbol = order.symbol
        contract.secType = "STK"  # Default to stock
        contract.exchange = "SMART"  # Default to SMART routing
        contract.currency = "USD"  # Default to USD

        # Apply any contract overrides from order metadata
        if "contract" in order.metadata:
            contract_data = order.metadata["contract"]
            for key, value in contract_data.items():
                if hasattr(contract, key):
                    setattr(contract, key, value)

        return contract

    def _create_ib_order(self, order: Order) -> 'ibapi.order.Order':
        """
        Create an IB Order object from our order.

        Args:
            order: Our internal order object

        Returns:
            ibapi.order.Order: IB API Order object
        """
        from ibapi.order import Order as IBOrder

        # Create the IB order
        ib_order = IBOrder()

        # Only set the absolutely necessary fields
        # Initialize price fields to avoid max float values
        ib_order.lmtPrice = 0
        ib_order.auxPrice = 0
        
        # Disable deprecated attributes that cause warnings
        ib_order.eTradeOnly = False
        ib_order.firmQuoteOnly = False

        # Use our order ID as the IB order ID if possible
        try:
            ib_order.orderId = int(order.order_id.split('-')[-1])
        except (ValueError, IndexError):
            # Let the gateway assign an order ID
            ib_order.orderId = 0

        # Set the parent ID if this is a child order
        if order.parent_id:
            try:
                parent_order = self._orders.get(order.parent_id)
                if parent_order and parent_order.broker_order_id:
                    ib_order.parentId = int(parent_order.broker_order_id)
            except (ValueError, TypeError):
                logger.warning(f"Could not set parent ID for order {order.order_id}")

        # Set core order properties
        ib_order.action = "BUY" if order.is_buy else "SELL"
        ib_order.totalQuantity = abs(order.quantity)

        # Set order type and related properties
        if order.order_type == OrderType.MARKET:
            ib_order.orderType = "MKT"
        elif order.order_type == OrderType.LIMIT:
            ib_order.orderType = "LMT"
            ib_order.lmtPrice = order.limit_price or 0
        elif order.order_type == OrderType.STOP:
            ib_order.orderType = "STP"
            ib_order.auxPrice = order.stop_price or 0
        elif order.order_type == OrderType.STOP_LIMIT:
            ib_order.orderType = "STP LMT"
            ib_order.lmtPrice = order.limit_price or 0
            ib_order.auxPrice = order.stop_price or 0

        # Set time in force
        if order.time_in_force == TimeInForce.DAY:
            ib_order.tif = "DAY"
        elif order.time_in_force == TimeInForce.GTC:
            ib_order.tif = "GTC"
        elif order.time_in_force == TimeInForce.IOC:
            ib_order.tif = "IOC"
        elif order.time_in_force == TimeInForce.FOK:
            ib_order.tif = "FOK"

        # Apply any order overrides from metadata
        if "ib_order_params" in order.metadata:
            ib_params = order.metadata["ib_order_params"]
            for key, value in ib_params.items():
                if hasattr(ib_order, key):
                    setattr(ib_order, key, value)

        return ib_order

    async def handle_order_status_update(self,
                                      broker_order_id: str,
                                      status: str,
                                      filled: float,
                                      remaining: float,
                                      avg_fill_price: float,
                                      last_fill_price: float) -> None:
        """
        Handle an order status update from IB Gateway.

        Args:
            broker_order_id: The broker's order ID
            status: Current status string
            filled: Filled quantity
            remaining: Remaining quantity
            avg_fill_price: Average fill price
            last_fill_price: Last fill price
        """
        # Find our internal order
        order_id = self._broker_order_map.get(broker_order_id)
        if not order_id or order_id not in self._orders:
            logger.warning(f"Received status update for unknown order: {broker_order_id}")
            return

        order = self._orders[order_id]
        previous_status = order.status

        # Map IB status to our status
        if status == "Submitted":
            new_status = OrderStatus.SUBMITTED
        elif status == "Cancelled":
            new_status = OrderStatus.CANCELLED
        elif status == "Filled":
            new_status = OrderStatus.FILLED
        elif status == "Partially Filled":
            new_status = OrderStatus.PARTIALLY_FILLED
        elif status == "PendingCancel":
            new_status = OrderStatus.PENDING_CANCEL
        elif status == "PendingSubmit":
            new_status = OrderStatus.PENDING_SUBMIT
        elif status == "PreSubmitted" or status == "ApiPending":
            new_status = OrderStatus.ACCEPTED
        elif status == "Inactive":
            new_status = OrderStatus.INACTIVE
        else:
            logger.warning(f"Unknown IB order status: {status} for order {order_id}")
            return

        # Update order status if changed
        if order.status != new_status:
            order.update_status(new_status, f"IB status: {status}")

            # Update order tracking
            if new_status.is_active:
                self._pending_orders.discard(order_id)
                self._active_orders.add(order_id)
            elif new_status.is_complete:
                self._active_orders.discard(order_id)
                self._pending_orders.discard(order_id)
                self._completed_orders.add(order_id)

            # Emit status change event
            event = OrderStatusEvent(
                order_id=order_id,
                symbol=order.symbol,
                status=new_status,
                previous_status=previous_status,
                status_time=datetime.now()
            )
            asyncio.create_task(self.event_bus.emit(event))

        # Check if we need to handle a new fill
        if filled > order.filled_quantity:
            new_fill_quantity = filled - order.filled_quantity

            # Process the fill
            asyncio.create_task(
                self.process_fill(
                    order_id=order_id,
                    quantity=new_fill_quantity,
                    price=last_fill_price or avg_fill_price
                )
            )

    async def handle_execution_update(self,
                                   broker_order_id: str,
                                   exec_id: str,
                                   symbol: str,
                                   side: str,
                                   quantity: float,
                                   price: float,
                                   commission: Optional[float] = None) -> None:
        """
        Handle an execution update from IB Gateway.

        Args:
            broker_order_id: The broker's order ID
            exec_id: Execution ID
            symbol: Symbol that was traded
            side: Side of the execution (BUY/SELL)
            quantity: Executed quantity
            price: Execution price
            commission: Optional commission amount
        """
        # Find our internal order
        order_id = self._broker_order_map.get(broker_order_id)
        if not order_id or order_id not in self._orders:
            logger.warning(f"Received execution for unknown order: {broker_order_id}")
            return

        order = self._orders[order_id]

        # Check if this execution is already processed
        if f"exec_{exec_id}" in order.metadata:
            logger.debug(f"Ignoring duplicate execution {exec_id} for order {order_id}")
            return

        # Store execution ID to prevent duplicates
        order.metadata[f"exec_{exec_id}"] = {
            "quantity": quantity,
            "price": price,
            "commission": commission
        }

        # Process the fill
        await self.process_fill(
            order_id=order_id,
            quantity=quantity,
            price=price,
            commission=commission
        )