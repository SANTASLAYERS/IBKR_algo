"""
Alpaca Event Adapter

This module provides adaptation between Alpaca's event format and the internal
event system, ensuring seamless integration of order updates and fills.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

from src.event.order import (
    OrderStatus, OrderStatusEvent, FillEvent, 
    RejectEvent, CancelEvent
)
from src.event.bus import EventBus

logger = logging.getLogger(__name__)


class AlpacaEventAdapter:
    """
    Adapts Alpaca trade updates to internal event format.
    
    This class handles:
    1. Status mapping from Alpaca to internal format
    2. Fill event generation from trade updates
    3. Error and rejection handling
    4. Event enrichment with additional data
    """
    
    # Alpaca status to internal status mapping
    STATUS_MAP = {
        'new': OrderStatus.CREATED,
        'partially_filled': OrderStatus.PARTIALLY_FILLED,
        'filled': OrderStatus.FILLED,
        'done_for_day': OrderStatus.CANCELLED,
        'canceled': OrderStatus.CANCELLED,
        'expired': OrderStatus.CANCELLED,
        'replaced': OrderStatus.ACCEPTED,
        'pending_cancel': OrderStatus.CANCELLED,
        'pending_replace': OrderStatus.ACCEPTED,
        'accepted': OrderStatus.ACCEPTED,
        'pending_new': OrderStatus.SUBMITTED,
        'accepted_for_bidding': OrderStatus.ACCEPTED,
        'stopped': OrderStatus.CANCELLED,
        'rejected': OrderStatus.REJECTED,
        'suspended': OrderStatus.ERROR,
        'calculated': OrderStatus.ACCEPTED
    }
    
    def __init__(self, event_bus: EventBus):
        """
        Initialize the Alpaca event adapter.
        
        Args:
            event_bus: Event bus for emitting adapted events
        """
        self.event_bus = event_bus
        self._last_fill_qty: Dict[str, float] = {}  # Track fills per order
        self._order_status: Dict[str, OrderStatus] = {}  # Track status per order
        
        logger.info("AlpacaEventAdapter initialized")
    
    async def handle_trade_update(self, data: Any) -> None:
        """
        Handle a trade update from Alpaca and emit appropriate events.
        
        Args:
            data: Alpaca trade update data
        """
        try:
            order = data.order
            event_type = data.event
            
            # Extract common order information
            order_id = order.client_order_id or order.id
            symbol = order.symbol
            
            # Get current and previous status
            alpaca_status = order.status
            internal_status = self.STATUS_MAP.get(alpaca_status, OrderStatus.ERROR)
            previous_status = self._order_status.get(order_id)
            
            # Update tracked status
            self._order_status[order_id] = internal_status
            
            logger.debug(f"Processing Alpaca event '{event_type}' for order {order_id} "
                        f"(status: {alpaca_status} -> {internal_status.value})")
            
            # Handle different event types
            if event_type in ['fill', 'partial_fill']:
                await self._handle_fill_event(data, order, order_id, symbol)
            
            elif event_type == 'rejected':
                await self._handle_rejection(order, order_id, symbol)
            
            elif event_type == 'canceled':
                await self._handle_cancellation(order, order_id, symbol)
            
            # Always emit status update if status changed
            if previous_status != internal_status:
                await self._emit_status_update(
                    order_id=order_id,
                    symbol=symbol,
                    status=internal_status,
                    previous_status=previous_status,
                    order=order
                )
            
        except Exception as e:
            logger.error(f"Error handling Alpaca trade update: {e}", exc_info=True)
    
    async def _handle_fill_event(self, data: Any, order: Any, 
                                order_id: str, symbol: str) -> None:
        """
        Handle fill and partial fill events.
        
        Args:
            data: Trade update data
            order: Order object
            order_id: Order ID
            symbol: Trading symbol
        """
        try:
            # Extract fill information
            filled_qty = float(order.filled_qty) if order.filled_qty else 0.0
            avg_fill_price = float(order.filled_avg_price) if order.filled_avg_price else 0.0
            
            # Calculate new fill quantity
            last_filled = self._last_fill_qty.get(order_id, 0.0)
            new_fill_qty = filled_qty - last_filled
            
            if new_fill_qty <= 0:
                logger.debug(f"No new fill quantity for order {order_id}")
                return
            
            # Update tracked fill quantity
            self._last_fill_qty[order_id] = filled_qty
            
            # Get fill price (use event price if available, otherwise average)
            fill_price = float(data.price) if hasattr(data, 'price') and data.price else avg_fill_price
            
            # Calculate remaining quantity
            total_qty = float(order.qty)
            remaining_qty = total_qty - filled_qty
            
            # Create fill event
            fill_event = FillEvent(
                order_id=order_id,
                symbol=symbol,
                status=self._order_status[order_id],
                fill_price=fill_price,
                fill_quantity=new_fill_qty,
                cumulative_quantity=filled_qty,
                remaining_quantity=remaining_qty,
                fill_time=self._parse_timestamp(data.timestamp if hasattr(data, 'timestamp') else None),
                fill_id=str(uuid.uuid4()),
                is_partial=remaining_qty > 0,
                order_data={
                    'alpaca_order_id': order.id,
                    'side': order.side,
                    'order_type': order.order_type,
                    'time_in_force': order.time_in_force
                }
            )
            
            await self.event_bus.emit(fill_event)
            logger.info(f"Emitted fill event for order {order_id}: "
                       f"{new_fill_qty} @ ${fill_price:.2f}")
            
        except Exception as e:
            logger.error(f"Error handling fill event: {e}", exc_info=True)
    
    async def _handle_rejection(self, order: Any, order_id: str, symbol: str) -> None:
        """
        Handle order rejection.
        
        Args:
            order: Order object
            order_id: Order ID
            symbol: Trading symbol
        """
        try:
            reject_event = RejectEvent(
                order_id=order_id,
                symbol=symbol,
                status=OrderStatus.REJECTED,
                reject_time=datetime.now(),
                reason="Order rejected by Alpaca",
                error_message=getattr(order, 'reject_reason', 'Unknown rejection reason'),
                order_data={
                    'alpaca_order_id': order.id,
                    'side': order.side,
                    'order_type': order.order_type,
                    'quantity': order.qty
                }
            )
            
            await self.event_bus.emit(reject_event)
            logger.warning(f"Order {order_id} rejected: {reject_event.error_message}")
            
        except Exception as e:
            logger.error(f"Error handling rejection: {e}", exc_info=True)
    
    async def _handle_cancellation(self, order: Any, order_id: str, symbol: str) -> None:
        """
        Handle order cancellation.
        
        Args:
            order: Order object
            order_id: Order ID
            symbol: Trading symbol
        """
        try:
            cancel_event = CancelEvent(
                order_id=order_id,
                symbol=symbol,
                status=OrderStatus.CANCELLED,
                cancel_time=self._parse_timestamp(order.canceled_at),
                reason="Order cancelled",
                user_initiated=True,  # Assume user-initiated for now
                order_data={
                    'alpaca_order_id': order.id,
                    'side': order.side,
                    'order_type': order.order_type,
                    'filled_qty': order.filled_qty or 0
                }
            )
            
            await self.event_bus.emit(cancel_event)
            logger.info(f"Order {order_id} cancelled")
            
        except Exception as e:
            logger.error(f"Error handling cancellation: {e}", exc_info=True)
    
    async def _emit_status_update(self, order_id: str, symbol: str, 
                                 status: OrderStatus, 
                                 previous_status: Optional[OrderStatus],
                                 order: Any) -> None:
        """
        Emit an order status update event.
        
        Args:
            order_id: Order ID
            symbol: Trading symbol
            status: New status
            previous_status: Previous status
            order: Order object
        """
        try:
            status_event = OrderStatusEvent(
                order_id=order_id,
                symbol=symbol,
                status=status,
                previous_status=previous_status,
                status_time=datetime.now(),
                reason=f"Alpaca status: {order.status}",
                order_data={
                    'alpaca_order_id': order.id,
                    'side': order.side,
                    'order_type': order.order_type,
                    'filled_qty': order.filled_qty or 0,
                    'avg_fill_price': order.filled_avg_price or 0
                }
            )
            
            await self.event_bus.emit(status_event)
            logger.debug(f"Emitted status update for order {order_id}: "
                        f"{previous_status.value if previous_status else 'None'} -> {status.value}")
            
        except Exception as e:
            logger.error(f"Error emitting status update: {e}", exc_info=True)
    
    def _parse_timestamp(self, timestamp: Any) -> datetime:
        """
        Parse Alpaca timestamp to datetime.
        
        Args:
            timestamp: Alpaca timestamp (various formats)
            
        Returns:
            datetime object
        """
        if timestamp is None:
            return datetime.now()
        
        if isinstance(timestamp, datetime):
            return timestamp
        
        if isinstance(timestamp, str):
            try:
                # Try ISO format first
                return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                pass
        
        # Default to now if parsing fails
        return datetime.now()
    
    def reset_order_tracking(self, order_id: str) -> None:
        """
        Reset tracking for a specific order.
        
        Args:
            order_id: Order ID to reset
        """
        self._last_fill_qty.pop(order_id, None)
        self._order_status.pop(order_id, None)
        logger.debug(f"Reset tracking for order {order_id}")
    
    def get_order_status(self, order_id: str) -> Optional[OrderStatus]:
        """
        Get the current tracked status for an order.
        
        Args:
            order_id: Order ID
            
        Returns:
            Current order status if tracked
        """
        return self._order_status.get(order_id) 