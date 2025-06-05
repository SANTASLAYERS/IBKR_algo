"""
Position Manager for unified position and order tracking.

This module provides the PositionManager class that will replace both
TradeTracker and the context-based order tracking system.
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Set, Optional, List, Tuple

logger = logging.getLogger(__name__)


class PositionStatus(Enum):
    """Status of a position."""
    ACTIVE = "active"
    CLOSING = "closing"
    CLOSED = "closed"


@dataclass
class Position:
    """Complete information about a trading position."""
    symbol: str
    side: str  # "BUY" or "SELL"
    
    # Lifecycle
    entry_time: datetime
    exit_time: Optional[datetime] = None
    status: PositionStatus = PositionStatus.ACTIVE
    
    # Orders
    main_orders: Set[str] = field(default_factory=set)
    stop_orders: Set[str] = field(default_factory=set)
    target_orders: Set[str] = field(default_factory=set)
    doubledown_orders: Set[str] = field(default_factory=set)
    
    # Position details
    entry_price: Optional[float] = None
    current_quantity: float = 0
    total_quantity: float = 0
    
    # Metadata for reconciliation
    metadata: Dict[str, any] = field(default_factory=dict)
    
    def add_orders(self, order_type: str, order_ids: List[str]):
        """Add orders to the position."""
        if order_type == "main":
            self.main_orders.update(order_ids)
        elif order_type == "stop":
            self.stop_orders.update(order_ids)
        elif order_type == "target":
            self.target_orders.update(order_ids)
        elif order_type == "doubledown":
            self.doubledown_orders.update(order_ids)
        else:
            logger.warning(f"Unknown order type: {order_type}")
    
    def get_all_orders(self) -> Set[str]:
        """Get all order IDs associated with this position."""
        return (self.main_orders | self.stop_orders | 
                self.target_orders | self.doubledown_orders)
    
    def is_protective_order(self, order_id: str) -> Tuple[bool, str]:
        """Check if order is a stop or target order."""
        if order_id in self.stop_orders:
            return True, "stop"
        elif order_id in self.target_orders:
            return True, "target"
        return False, ""
    
    def remove_order(self, order_id: str) -> bool:
        """Remove an order from all sets."""
        removed = False
        for order_set in [self.main_orders, self.stop_orders, 
                         self.target_orders, self.doubledown_orders]:
            if order_id in order_set:
                order_set.remove(order_id)
                removed = True
        return removed


class PositionManager:
    """
    Unified manager for positions and their order relationships.
    
    This will eventually replace both TradeTracker and the context-based
    order tracking system (LinkedOrderManager).
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern to ensure one instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the position manager."""
        if not self._initialized:
            self._positions: Dict[str, Position] = {}
            self._order_to_position: Dict[str, str] = {}
            self._position_lock = threading.Lock()
            self._initialized = True
            logger.info("PositionManager initialized")
    
    def open_position(self, symbol: str, side: str) -> Position:
        """
        Open a new position.
        
        Args:
            symbol: Trading symbol
            side: "BUY" or "SELL"
            
        Returns:
            Position: The newly created position
            
        Raises:
            ValueError: If position already exists for symbol
        """
        with self._position_lock:
            if symbol in self._positions and self._positions[symbol].status == PositionStatus.ACTIVE:
                logger.warning(f"Position already active for {symbol}")
                return self._positions[symbol]
            
            position = Position(
                symbol=symbol,
                side=side,
                entry_time=datetime.now()
            )
            self._positions[symbol] = position
            logger.info(f"Opened {side} position for {symbol}")
            return position
    
    def add_orders_to_position(self, symbol: str, order_type: str, order_ids: List[str]):
        """
        Add orders to a position and track relationships.
        
        Args:
            symbol: Trading symbol
            order_type: Type of orders ("main", "stop", "target", "doubledown")
            order_ids: List of order IDs to add
        """
        with self._position_lock:
            position = self._positions.get(symbol)
            if not position:
                logger.error(f"No position found for {symbol}")
                return
            
            position.add_orders(order_type, order_ids)
            
            # Track order->position mapping
            for order_id in order_ids:
                self._order_to_position[order_id] = symbol
            
            logger.info(f"Added {len(order_ids)} {order_type} orders to {symbol} position")
    
    def find_position_by_order(self, order_id: str) -> Optional[Position]:
        """
        Find position that contains this order.
        
        Args:
            order_id: Order ID to search for
            
        Returns:
            Position if found, None otherwise
        """
        with self._position_lock:
            symbol = self._order_to_position.get(order_id)
            if symbol:
                return self._positions.get(symbol)
            return None
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for symbol."""
        with self._position_lock:
            return self._positions.get(symbol)
    
    def has_active_position(self, symbol: str) -> bool:
        """Check if there's an active position for symbol."""
        with self._position_lock:
            position = self._positions.get(symbol)
            return position and position.status == PositionStatus.ACTIVE
    
    def get_active_position(self, symbol: str) -> Optional[Position]:
        """Get active position for symbol (compatible with TradeTracker API)."""
        with self._position_lock:
            position = self._positions.get(symbol)
            if position and position.status == PositionStatus.ACTIVE:
                return position
            return None
    
    def close_position(self, symbol: str):
        """Mark position as closed."""
        with self._position_lock:
            position = self._positions.get(symbol)
            if position:
                position.status = PositionStatus.CLOSED
                position.exit_time = datetime.now()
                
                # Clean up order mappings
                for order_id in position.get_all_orders():
                    self._order_to_position.pop(order_id, None)
                
                logger.info(f"Closed position for {symbol}")
                
                # Optionally remove from active positions
                # (keeping for now for reconciliation purposes)
                # del self._positions[symbol]
    
    def get_all_active_positions(self) -> Dict[str, Position]:
        """Get all active positions."""
        with self._position_lock:
            return {
                symbol: position 
                for symbol, position in self._positions.items()
                if position.status == PositionStatus.ACTIVE
            }
    
    def get_linked_orders(self, symbol: str, order_type: Optional[str] = None) -> List[str]:
        """
        Get linked orders for a symbol (compatible with LinkedOrderManager API).
        
        Args:
            symbol: Trading symbol
            order_type: Optional order type filter
            
        Returns:
            List of order IDs
        """
        with self._position_lock:
            position = self._positions.get(symbol)
            if not position:
                return []
            
            if order_type == "main":
                return list(position.main_orders)
            elif order_type == "stop":
                return list(position.stop_orders)
            elif order_type == "target":
                return list(position.target_orders)
            elif order_type == "doubledown":
                return list(position.doubledown_orders)
            else:
                # Return all orders
                return list(position.get_all_orders())
    
    def remove_order(self, symbol: str, order_id: str):
        """Remove an order from position tracking."""
        with self._position_lock:
            position = self._positions.get(symbol)
            if position:
                if position.remove_order(order_id):
                    self._order_to_position.pop(order_id, None)
                    logger.debug(f"Removed order {order_id} from {symbol} position")
    
    def update_position_entry(self, symbol: str, entry_price: float, quantity: float):
        """Update position entry details."""
        with self._position_lock:
            position = self._positions.get(symbol)
            if position:
                position.entry_price = entry_price
                position.current_quantity = quantity
                position.total_quantity = quantity
                logger.debug(f"Updated {symbol} position: price={entry_price}, qty={quantity}")
    
    def clear_all(self):
        """Clear all positions (for testing)."""
        with self._position_lock:
            self._positions.clear()
            self._order_to_position.clear()
            logger.info("Cleared all positions from PositionManager")
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about positions."""
        with self._position_lock:
            active_positions = sum(1 for p in self._positions.values() 
                                 if p.status == PositionStatus.ACTIVE)
            total_orders = sum(len(p.get_all_orders()) for p in self._positions.values())
            
            return {
                "active_positions": active_positions,
                "total_positions": len(self._positions),
                "total_orders_tracked": total_orders,
                "order_mappings": len(self._order_to_position)
            } 