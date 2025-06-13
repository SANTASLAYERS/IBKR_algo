"""
Unified Fill Manager for handling all order fills and updating protective orders.

This manager replaces the separate LinkedDoubleDownFillManager and parts of
LinkedOrderConclusionManager to provide a centralized approach to handling fills
and updating protective orders based on current position size.

Key features:
- Handles all fill events (main orders, double downs, protective orders)
- Updates protective orders on any fill to match current position size
- Only closes positions when protective orders are FULLY filled
- Correctly handles partial fills for limit and stop orders
- Thread-safe: Serializes fill processing per symbol to prevent race conditions
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from src.event.order import FillEvent
from src.position.position_manager import PositionManager
from src.trade_tracker import TradeTracker
from src.order.base import OrderType, OrderStatus

logger = logging.getLogger(__name__)


class OrderOperationType(Enum):
    """Types of order operations that can be queued."""
    REPLACE_STOP = "replace_stop"
    REPLACE_TARGET = "replace_target"
    CANCEL_ALL = "cancel_all"


@dataclass
class OrderOperation:
    """Represents a queued order operation."""
    operation_type: OrderOperationType
    symbol: str
    old_order_id: Optional[str] = None
    new_quantity: Optional[float] = None
    price: Optional[float] = None
    reason: Optional[str] = None


class UnifiedFillManager:
    """
    Centralized manager that handles ALL fill events and updates protective orders.
    Assumes main orders are market orders (always fill completely).
    
    Thread-safe: Uses per-symbol locks to serialize fill processing for the same symbol
    while allowing concurrent processing across different symbols.
    """
    
    def __init__(self, context: Dict[str, Any], event_bus):
        self.context = context
        self.event_bus = event_bus
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Per-symbol locks to serialize fill processing
        self._symbol_locks: Dict[str, asyncio.Lock] = {}
        
        # Lock for managing the symbol locks dictionary
        self._locks_lock = asyncio.Lock()
        
        # Per-symbol order operation queues
        self._order_queues: Dict[str, asyncio.Queue] = {}
        
        # Tasks for processing order queues
        self._queue_processors: Dict[str, asyncio.Task] = {}
        
    async def initialize(self):
        """Subscribe to fill events."""
        await self.event_bus.subscribe(FillEvent, self.on_order_fill)
        self.logger.info("UnifiedFillManager initialized with concurrency control")
    
    async def _get_symbol_lock(self, symbol: str) -> asyncio.Lock:
        """Get or create a lock for the given symbol."""
        async with self._locks_lock:
            if symbol not in self._symbol_locks:
                self._symbol_locks[symbol] = asyncio.Lock()
            return self._symbol_locks[symbol]
    
    async def _get_order_queue(self, symbol: str) -> asyncio.Queue:
        """Get or create an order operation queue for the given symbol."""
        async with self._locks_lock:
            if symbol not in self._order_queues:
                self._order_queues[symbol] = asyncio.Queue()
                # Start a processor for this queue
                self._queue_processors[symbol] = asyncio.create_task(
                    self._process_order_queue(symbol)
                )
            return self._order_queues[symbol]
    
    async def _process_order_queue(self, symbol: str):
        """Process order operations for a symbol sequentially."""
        queue = self._order_queues[symbol]
        
        self.logger.info(f"Started order queue processor for {symbol}")
        
        while True:
            try:
                # Wait for an operation
                operation = await queue.get()
                
                self.logger.info(f"Processing operation for {symbol}: {operation.operation_type.value}")
                
                # Process the operation
                if operation.operation_type == OrderOperationType.REPLACE_STOP:
                    await self._execute_replace_order(
                        symbol, operation.old_order_id, operation.new_quantity,
                        "stop", operation.price
                    )
                elif operation.operation_type == OrderOperationType.REPLACE_TARGET:
                    await self._execute_replace_order(
                        symbol, operation.old_order_id, operation.new_quantity,
                        "target", operation.price
                    )
                elif operation.operation_type == OrderOperationType.CANCEL_ALL:
                    await self._execute_cancel_all_orders(symbol, operation.reason)
                
                # Mark the operation as done
                queue.task_done()
                self.logger.info(f"Completed operation for {symbol}: {operation.operation_type.value}")
                
            except asyncio.CancelledError:
                self.logger.info(f"Order queue processor for {symbol} cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error processing order queue for {symbol}: {e}", exc_info=True)
    
    async def on_order_fill(self, event: FillEvent):
        """
        Handle fill events and update protective orders accordingly.
        Main orders (market) always fill completely.
        Double downs, stops, and targets may partially fill.
        
        Thread-safe: Serializes processing for the same symbol.
        """
        symbol = event.symbol
        
        # Get the lock for this symbol
        symbol_lock = await self._get_symbol_lock(symbol)
        
        # Process the fill with the symbol lock held
        async with symbol_lock:
            await self._process_fill(event)
    
    async def _process_fill(self, event: FillEvent):
        """
        Process a fill event with the symbol lock held.
        This ensures atomic processing of fills for the same symbol.
        """
        try:
            symbol = event.symbol
            order_id = event.order_id
            fill_quantity = event.fill_quantity
            
            self.logger.info(f"Processing fill for {symbol}: {fill_quantity} shares on order {order_id}")
            
            # Get PositionManager to track order relationships
            position_manager = PositionManager()
            pm_position = position_manager.get_position(symbol)
            
            if not pm_position:
                self.logger.warning(f"No position found in PositionManager for {symbol}")
                return
            
            # Determine order type from PositionManager
            order_type = self._get_order_type(pm_position, order_id)
            self.logger.info(f"Fill is for {order_type} order")
            
            # Get order details to check if fully filled
            order_manager = self.context.get("order_manager")
            order = await order_manager.get_order(order_id)
            
            if not order:
                self.logger.error(f"Could not find order {order_id}")
                return
            
            # Use the fill event status to determine if fully filled
            # The event status is more accurate than the order status in OrderManager
            # which may not be updated yet
            is_fully_filled = (event.status.value == "filled")
            self.logger.info(f"Order {order_id} fill status: {event.status.value}, is_fully_filled: {is_fully_filled}")
            
            # Handle based on order type
            if order_type == "main":
                # Market order - always fills completely, create initial protective orders
                await self._handle_main_order_fill(symbol, pm_position)
                
            elif order_type == "doubledown":
                # Double down fill (partial or full) - update protective orders
                await self._handle_doubledown_fill(symbol, pm_position)
                
            elif order_type in ["stop", "target"]:
                # Protective order fill
                if is_fully_filled:
                    # Protective order fully filled - close position
                    await self._handle_position_closure(
                        symbol, 
                        f"{order_type.capitalize()} order fully filled"
                    )
                else:
                    # Partial fill of protective order - update the other protective order
                    await self._handle_protective_partial_fill(symbol, pm_position, order_type)
            
        except Exception as e:
            self.logger.error(f"Error handling fill event: {e}", exc_info=True)
    
    def _get_order_type(self, pm_position, order_id: str) -> str:
        """Determine what type of order this is."""
        if order_id in pm_position.main_orders:
            return "main"
        elif order_id in pm_position.doubledown_orders:
            return "doubledown"
        elif order_id in pm_position.stop_orders:
            return "stop"
        elif order_id in pm_position.target_orders:
            return "target"
        # Scale orders not implemented yet
        # elif order_id in pm_position.scale_orders:
        #     return "scale"
        else:
            return "unknown"
    
    async def _calculate_current_position_size(self, symbol: str) -> float:
        """
        Calculate current position size from filled quantities.
        Main orders are market orders (fully filled).
        Other orders may be partially filled.
        """
        order_manager = self.context.get("order_manager")
        position_manager = PositionManager()
        pm_position = position_manager.get_position(symbol)
        
        if not pm_position:
            return 0.0
        
        total_position = 0.0
        
        # Main orders (market orders - fully filled)
        for order_id in pm_position.main_orders:
            order = await order_manager.get_order(order_id)
            if order:
                total_position += order.quantity  # Market orders use full quantity
        
        # Double down orders (may be partially filled)
        for order_id in pm_position.doubledown_orders:
            order = await order_manager.get_order(order_id)
            if order:
                signed_fill = order.filled_quantity * (1 if order.quantity > 0 else -1)
                total_position += signed_fill  # Preserve trade direction
        
        # Scale-in orders (may be partially filled) - if they exist
        if hasattr(pm_position, 'scale_orders'):
            for order_id in pm_position.scale_orders:
                order = await order_manager.get_order(order_id)
                if order:
                    signed_fill = order.filled_quantity * (1 if order.quantity > 0 else -1)
                    total_position += signed_fill
        
        # Subtract protective order fills (these reduce position)
        for order_id in pm_position.stop_orders | pm_position.target_orders:
            order = await order_manager.get_order(order_id)
            if order:
                signed_fill = order.filled_quantity * (1 if order.quantity > 0 else -1)
                total_position += signed_fill  # Apply correct sign
        
        return total_position
    
    async def _handle_main_order_fill(self, symbol: str, pm_position):
        """
        Handle main order fill (market order - always complete).
        Initial protective orders should already be created by LinkedCreateOrderAction.
        """
        self.logger.info(f"Main order filled for {symbol}")
        # Protective orders should already exist from LinkedCreateOrderAction
        # No action needed here
        
        # Log current position state
        self.logger.info(f"Position state after main fill:")
        self.logger.info(f"  Main orders: {pm_position.main_orders}")
        self.logger.info(f"  Stop orders: {pm_position.stop_orders}")
        self.logger.info(f"  Target orders: {pm_position.target_orders}")
        self.logger.info(f"  Double down orders: {pm_position.doubledown_orders}")
        
        # Check if we should update protective orders
        current_position = await self._calculate_current_position_size(symbol)
        self.logger.info(f"  Current position size: {current_position}")
        
        # If we have a position, ensure protective orders match
        if abs(current_position) > 0.0001:
            self.logger.info(f"Updating protective orders after main fill to match position size: {current_position}")
            await self._update_protective_orders(symbol, current_position, pm_position)
    
    async def _handle_doubledown_fill(self, symbol: str, pm_position):
        """
        Handle double down fill (partial or full).
        Update protective orders to match new position size.
        """
        # Calculate current total position
        current_position = await self._calculate_current_position_size(symbol)
        
        if abs(current_position) < 0.0001:
            self.logger.warning(f"Position for {symbol} is flat after double down")
            await self._handle_position_closure(symbol, "Position flat after double down")
            return
        
        self.logger.info(f"Double down fill for {symbol}, new position size: {current_position}")
        
        # Update protective orders to match new position size
        await self._update_protective_orders(symbol, current_position, pm_position)
    
    async def _handle_protective_partial_fill(self, symbol: str, pm_position, filled_type: str):
        """
        Handle partial fill of stop or target order.
        Update the OTHER protective order to match remaining position.
        """
        # Calculate current position after partial fill
        current_position = await self._calculate_current_position_size(symbol)
        
        if abs(current_position) < 0.0001:
            self.logger.info(f"Position for {symbol} is flat after partial {filled_type} fill")
            await self._handle_position_closure(symbol, "Position flat")
            return
        
        self.logger.info(f"Partial {filled_type} fill for {symbol}, remaining position: {current_position}")
        
        # Update the OTHER protective order (not the one that partially filled)
        # This ensures both protective orders match the remaining position size
        await self._update_protective_orders(symbol, current_position, pm_position, exclude_type=filled_type)
    
    async def _update_protective_orders(self, symbol: str, position_size: float, 
                                       pm_position, exclude_type: Optional[str] = None):
        """
        Update protective orders to match current position size.
        
        Args:
            symbol: The symbol to update
            position_size: Current net position (positive for long, negative for short)
            pm_position: Position from PositionManager
            exclude_type: 'stop' or 'target' to exclude from updates (for partial fills)
        """
        order_manager = self.context.get("order_manager")
        
        # Determine position direction
        is_long = position_size > 0
        abs_position = abs(position_size)
        
        # Protective orders have opposite sign
        protective_quantity = -abs_position if is_long else abs_position
        
        self.logger.info(f"Updating protective orders for {symbol}: position={position_size}, protective_qty={protective_quantity}")
        
        # Get the order queue for this symbol
        queue = await self._get_order_queue(symbol)
        
        self.logger.info(f"Checking protective orders to update for {symbol}")
        
        # Queue stop order updates (unless excluded)
        if exclude_type != "stop":
            self.logger.info(f"Checking {len(pm_position.stop_orders)} stop orders")
            for stop_id in pm_position.stop_orders:
                stop_order = await order_manager.get_order(stop_id)
                if stop_order and stop_order.status.value in ["submitted", "accepted", "working"]:
                    # Only update if quantity is different
                    if abs(stop_order.quantity - protective_quantity) > 0.0001:
                        self.logger.info(f"Queueing update for stop order {stop_id}: current qty={stop_order.quantity}, new qty={protective_quantity}")
                        # Queue the replacement operation
                        operation = OrderOperation(
                            operation_type=OrderOperationType.REPLACE_STOP,
                            symbol=symbol,
                            old_order_id=stop_id,
                            new_quantity=protective_quantity,
                            price=stop_order.stop_price
                        )
                        await queue.put(operation)
                    else:
                        self.logger.info(f"Stop order {stop_id} already has correct quantity {stop_order.quantity}, no update needed")
                else:
                    self.logger.info(f"Stop order {stop_id} not active, skipping update")
        
        # Queue target order updates (unless excluded)
        if exclude_type != "target":
            self.logger.info(f"Checking {len(pm_position.target_orders)} target orders")
            for target_id in pm_position.target_orders:
                target_order = await order_manager.get_order(target_id)
                if target_order and target_order.status.value in ["submitted", "accepted", "working"]:
                    # Only update if quantity is different
                    if abs(target_order.quantity - protective_quantity) > 0.0001:
                        self.logger.info(f"Queueing update for target order {target_id}: current qty={target_order.quantity}, new qty={protective_quantity}")
                        # Queue the replacement operation
                        operation = OrderOperation(
                            operation_type=OrderOperationType.REPLACE_TARGET,
                            symbol=symbol,
                            old_order_id=target_id,
                            new_quantity=protective_quantity,
                            price=target_order.limit_price
                        )
                        await queue.put(operation)
                    else:
                        self.logger.info(f"Target order {target_id} already has correct quantity {target_order.quantity}, no update needed")
                else:
                    self.logger.info(f"Target order {target_id} not active, skipping update")
    
    async def _execute_replace_order(self, symbol: str, old_order_id: str, 
                                    new_quantity: float, order_type: str,
                                    price: float):
        """Execute order replacement with updated quantity.
        
        Includes retry logic for transient failures.
        This method is called by the queue processor to ensure serialization.
        """
        order_manager = self.context.get("order_manager")
        position_manager = PositionManager()
        
        max_retries = 3
        retry_delay = 0.5  # seconds
        
        for attempt in range(max_retries):
            try:
                # Cancel old order
                cancel_success = await order_manager.cancel_order(
                    old_order_id, 
                    f"Updating quantity to {new_quantity}"
                )
                
                if not cancel_success:
                    self.logger.warning(
                        f"Failed to cancel order {old_order_id} on attempt {attempt + 1}"
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        continue
                
                # Remove from position tracking
                position_manager.remove_order(symbol, old_order_id)
                
                # Small delay to ensure cancellation is processed
                await asyncio.sleep(0.1)
                
                # Create new order with updated quantity
                if order_type == "stop":
                    new_order = await order_manager.create_order(
                        symbol=symbol,
                        quantity=new_quantity,
                        order_type=OrderType.STOP,
                        stop_price=price,
                        auto_submit=True
                    )
                    if new_order:
                        position_manager.add_orders_to_position(symbol, "stop", [new_order.order_id])
                        self.logger.info(f"Created updated stop order {new_order.order_id} "
                                       f"for {symbol} at ${price:.2f} for {new_quantity} shares")
                        return  # Success
                
                elif order_type == "target":
                    new_order = await order_manager.create_order(
                        symbol=symbol,
                        quantity=new_quantity,
                        order_type=OrderType.LIMIT,
                        limit_price=price,
                        auto_submit=True
                    )
                    if new_order:
                        position_manager.add_orders_to_position(symbol, "target", [new_order.order_id])
                        self.logger.info(f"Created updated target order {new_order.order_id} "
                                       f"for {symbol} at ${price:.2f} for {new_quantity} shares")
                        return  # Success
                
                # If we get here, order creation failed
                if attempt < max_retries - 1:
                    self.logger.warning(
                        f"Failed to create new {order_type} order on attempt {attempt + 1}, retrying..."
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    self.logger.error(
                        f"Failed to create new {order_type} order after {max_retries} attempts"
                    )
                    
            except Exception as e:
                self.logger.error(
                    f"Error replacing {order_type} order on attempt {attempt + 1}: {e}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    self.logger.error(
                        f"Failed to replace {order_type} order after {max_retries} attempts: {e}"
                    )
    
    async def _handle_position_closure(self, symbol: str, reason: str):
        """
        Handle complete position closure.
        Only called when position is flat or protective order FULLY filled.
        """
        self.logger.info(f"Closing position for {symbol}: {reason}")
        
        # Queue the cancel all operation
        queue = await self._get_order_queue(symbol)
        operation = OrderOperation(
            operation_type=OrderOperationType.CANCEL_ALL,
            symbol=symbol,
            reason=reason
        )
        await queue.put(operation)
        
        # Update position status immediately
        position_manager = PositionManager()
        position_manager.close_position(symbol)
        
        # Update PositionTracker
        position_tracker = self.context.get("position_tracker")
        if position_tracker:
            positions = await position_tracker.get_positions_for_symbol(symbol)
            for pos in positions:
                await position_tracker.close_position(pos.position_id, reason)
        
        # Update TradeTracker
        trade_tracker = TradeTracker()
        trade_tracker.close_trade(symbol)
        
        self.logger.info(f"Position closed for {symbol}: cancellation queued, trackers updated")
    
    async def _execute_cancel_all_orders(self, symbol: str, reason: str):
        """
        Execute cancellation of all orders for a symbol.
        This method is called by the queue processor to ensure serialization.
        """
        order_manager = self.context.get("order_manager")
        position_manager = PositionManager()
        pm_position = position_manager.get_position(symbol)
        
        if not pm_position:
            return
        
        # Cancel all remaining orders
        all_order_ids = list(
            pm_position.main_orders | 
            pm_position.stop_orders | 
            pm_position.target_orders |
            pm_position.doubledown_orders
        )
        
        # Add scale orders if they exist
        if hasattr(pm_position, 'scale_orders'):
            all_order_ids.extend(list(pm_position.scale_orders))
        
        cancelled_count = 0
        for order_id in all_order_ids:
            try:
                order = await order_manager.get_order(order_id)
                if order and order.is_active:
                    success = await order_manager.cancel_order(order_id, f"Position closed: {reason}")
                    if success:
                        cancelled_count += 1
            except Exception as e:
                self.logger.warning(f"Failed to cancel order {order_id}: {e}")
        
        self.logger.info(f"Cancelled {cancelled_count} orders for {symbol}")
    
    async def cleanup(self):
        """Clean up resources when shutting down."""
        # Cancel all queue processor tasks
        for symbol, task in self._queue_processors.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._queue_processors.clear()
        self._order_queues.clear()
        self._symbol_locks.clear()
        
        self.logger.info("UnifiedFillManager cleanup completed") 