"""
Position tracking functionality for the position management system.

This module provides the PositionTracker class, which manages multiple positions
and handles position lifecycle events.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set, Any, Callable, Union
from datetime import datetime

from src.event.bus import EventBus
from src.event.position import (
    PositionEvent, PositionOpenEvent, PositionUpdateEvent, PositionCloseEvent, PositionStatus
)
from src.position.base import Position
from src.position.stock import StockPosition

# Set up logger
logger = logging.getLogger(__name__)


class PositionTracker:
    """
    Tracks and manages all active positions.
    
    The position tracker is responsible for:
    1. Creating and tracking positions
    2. Updating positions with market data
    3. Generating position events
    4. Storing position history
    """
    
    def __init__(self, event_bus: EventBus):
        """
        Initialize the position tracker.
        
        Args:
            event_bus: The event bus to publish position events to
        """
        self.event_bus = event_bus
        
        # Active positions mapped by position_id
        self._positions: Dict[str, Position] = {}
        
        # Positions by symbol
        self._positions_by_symbol: Dict[str, Set[str]] = {}
        
        # Closed positions history
        self._closed_positions: List[Position] = []
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        logger.debug("PositionTracker initialized")
    
    async def initialize(self):
        """
        Initialize the position tracker for async operations.
        
        This method can be called to perform any async initialization
        that cannot be done in __init__.
        """
        logger.info("PositionTracker async initialization completed")
        return True
    
    async def create_stock_position(self, 
                                  symbol: str, 
                                  quantity: float = 0, 
                                  entry_price: Optional[float] = None,
                                  stop_loss: Optional[float] = None,
                                  take_profit: Optional[float] = None,
                                  strategy: Optional[str] = None,
                                  metadata: Optional[Dict[str, Any]] = None) -> StockPosition:
        """
        Create a new stock position.
        
        Args:
            symbol: Stock symbol
            quantity: Position quantity (positive for long, negative for short)
            entry_price: Optional entry price (if already known)
            stop_loss: Optional stop loss price
            take_profit: Optional take profit price
            strategy: Optional strategy name
            metadata: Optional position metadata
            
        Returns:
            StockPosition: The newly created position
        """
        position = StockPosition(symbol)
        position.strategy = strategy
        
        if metadata:
            position.metadata = metadata
        
        # Open the position if entry price is provided
        if entry_price is not None and quantity != 0:
            await position.open(quantity, entry_price)
            
            # Set stop loss and take profit if provided
            if stop_loss is not None:
                await position.update_stop_loss(stop_loss)
            
            if take_profit is not None:
                await position.update_take_profit(take_profit)
        
        # Add to tracker
        await self._add_position(position)
        
        # Emit event if position is open
        if position.status == PositionStatus.OPEN:
            event = PositionOpenEvent(
                position_id=position.position_id,
                symbol=position.symbol,
                status=position.status,
                quantity=position.quantity,
                entry_price=position.entry_price,
                current_price=position.current_price,
                stop_loss=position.stop_loss,
                take_profit=position.take_profit,
                strategy=position.strategy,
                open_time=position.open_time
            )
            await self.event_bus.emit(event)
        
        logger.info(f"Created new position: {position}")
        return position
    
    async def get_position(self, position_id: str) -> Optional[Position]:
        """
        Get a position by ID.
        
        Args:
            position_id: Position ID
            
        Returns:
            Optional[Position]: The position if found, None otherwise
        """
        async with self._lock:
            return self._positions.get(position_id)
    
    async def get_positions_for_symbol(self, symbol: str) -> List[Position]:
        """
        Get all positions for a symbol.
        
        Args:
            symbol: The symbol to get positions for
            
        Returns:
            List[Position]: List of positions for the symbol
        """
        async with self._lock:
            position_ids = self._positions_by_symbol.get(symbol, set())
            return [self._positions[pid] for pid in position_ids if pid in self._positions]
    
    async def get_all_positions(self) -> List[Position]:
        """
        Get all active positions.
        
        Returns:
            List[Position]: List of all active positions
        """
        async with self._lock:
            return list(self._positions.values())
    
    async def get_closed_positions(self, limit: Optional[int] = None) -> List[Position]:
        """
        Get closed positions history.
        
        Args:
            limit: Optional limit on the number of positions to return
            
        Returns:
            List[Position]: List of closed positions
        """
        async with self._lock:
            if limit is not None:
                return self._closed_positions[-limit:]
            return self._closed_positions
    
    async def update_position_price(self, position_id: str, price: float) -> None:
        """
        Update a position with a new price.
        
        Args:
            position_id: Position ID
            price: New price
        """
        position = await self.get_position(position_id)
        if position:
            old_pnl = position.unrealized_pnl
            await position.update_price(price)
            
            # Emit update event if significant change
            if abs(position.unrealized_pnl - old_pnl) > 0.01:
                event = PositionUpdateEvent(
                    position_id=position.position_id,
                    symbol=position.symbol,
                    status=position.status,
                    quantity=position.quantity,
                    entry_price=position.entry_price,
                    current_price=position.current_price,
                    unrealized_pnl=position.unrealized_pnl
                )
                await self.event_bus.emit(event)
    
    async def update_all_positions_price(self, symbol: str, price: float) -> None:
        """
        Update all positions for a symbol with a new price.
        
        Args:
            symbol: Symbol to update positions for
            price: New price
        """
        positions = await self.get_positions_for_symbol(symbol)
        for position in positions:
            await self.update_position_price(position.position_id, price)
    
    async def close_position(self, 
                           position_id: str, 
                           exit_price: float, 
                           reason: Optional[str] = None,
                           order_id: Optional[str] = None) -> None:
        """
        Close a position.
        
        Args:
            position_id: Position ID
            exit_price: Exit price
            reason: Optional reason for closing
            order_id: Optional order ID associated with the close
        """
        position = await self.get_position(position_id)
        if position:
            await position.close(exit_price, reason, order_id)
            
            # Emit close event
            event = PositionCloseEvent(
                position_id=position.position_id,
                symbol=position.symbol,
                status=position.status,
                quantity=position.quantity,
                entry_price=position.entry_price,
                exit_price=position.exit_price,
                realized_pnl=position.realized_pnl,
                close_time=position.close_time,
                reason=reason
            )
            await self.event_bus.emit(event)
            
            # Move to closed positions history
            await self._remove_position(position)
            async with self._lock:
                self._closed_positions.append(position)
    
    async def adjust_position(self,
                            position_id: str,
                            quantity: Optional[float] = None,
                            stop_loss: Optional[float] = None,
                            take_profit: Optional[float] = None,
                            reason: Optional[str] = None) -> None:
        """
        Adjust a position.
        
        Args:
            position_id: Position ID
            quantity: Optional new quantity
            stop_loss: Optional new stop loss price
            take_profit: Optional new take profit price
            reason: Optional reason for adjustment
        """
        position = await self.get_position(position_id)
        if position:
            # Record previous values
            prev_quantity = position.quantity
            prev_stop = position.stop_loss
            prev_target = position.take_profit
            
            # Adjust the position
            await position.adjust(quantity, stop_loss, take_profit)
            
            # Emit update event
            event = PositionUpdateEvent(
                position_id=position.position_id,
                symbol=position.symbol,
                status=position.status,
                quantity=position.quantity,
                previous_quantity=prev_quantity,
                entry_price=position.entry_price,
                current_price=position.current_price,
                unrealized_pnl=position.unrealized_pnl,
                stop_loss_updated=stop_loss is not None,
                new_stop_loss=position.stop_loss,
                take_profit_updated=take_profit is not None,
                new_take_profit=position.take_profit,
                reason=reason
            )
            await self.event_bus.emit(event)
    
    async def update_stop_loss(self,
                             position_id: str,
                             price: float,
                             reason: Optional[str] = None) -> None:
        """
        Update stop loss for a position.
        
        Args:
            position_id: Position ID
            price: New stop loss price
            reason: Optional reason for update
        """
        position = await self.get_position(position_id)
        if position:
            prev_stop = position.stop_loss
            await position.update_stop_loss(price)
            
            # Emit update event
            event = PositionUpdateEvent(
                position_id=position.position_id,
                symbol=position.symbol,
                status=position.status,
                quantity=position.quantity,
                entry_price=position.entry_price,
                current_price=position.current_price,
                stop_loss_updated=True,
                new_stop_loss=position.stop_loss,
                reason=reason
            )
            await self.event_bus.emit(event)
    
    async def update_take_profit(self,
                               position_id: str,
                               price: float,
                               reason: Optional[str] = None) -> None:
        """
        Update take profit for a position.
        
        Args:
            position_id: Position ID
            price: New take profit price
            reason: Optional reason for update
        """
        position = await self.get_position(position_id)
        if position:
            prev_target = position.take_profit
            await position.update_take_profit(price)
            
            # Emit update event
            event = PositionUpdateEvent(
                position_id=position.position_id,
                symbol=position.symbol,
                status=position.status,
                quantity=position.quantity,
                entry_price=position.entry_price,
                current_price=position.current_price,
                take_profit_updated=True,
                new_take_profit=position.take_profit,
                reason=reason
            )
            await self.event_bus.emit(event)
    
    async def has_open_positions(self, symbol: Optional[str] = None) -> bool:
        """
        Check if there are open positions.
        
        Args:
            symbol: Optional symbol to check for
            
        Returns:
            bool: True if there are open positions, False otherwise
        """
        if symbol:
            positions = await self.get_positions_for_symbol(symbol)
            return any(p.status == PositionStatus.OPEN for p in positions)
        else:
            positions = await self.get_all_positions()
            return any(p.status == PositionStatus.OPEN for p in positions)
    
    async def get_position_summary(self) -> Dict[str, Any]:
        """
        Get a summary of active positions.
        
        Returns:
            Dict[str, Any]: Summary of active positions
        """
        positions = await self.get_all_positions()
        
        total_value = sum(p.position_value for p in positions)
        total_unrealized_pnl = sum(p.unrealized_pnl for p in positions)
        
        closed_positions = await self.get_closed_positions()
        total_realized_pnl = sum(p.realized_pnl for p in closed_positions)
        
        by_symbol = {}
        for p in positions:
            if p.symbol not in by_symbol:
                by_symbol[p.symbol] = {
                    "count": 0,
                    "value": 0,
                    "unrealized_pnl": 0
                }
            by_symbol[p.symbol]["count"] += 1
            by_symbol[p.symbol]["value"] += p.position_value
            by_symbol[p.symbol]["unrealized_pnl"] += p.unrealized_pnl
        
        return {
            "total_positions": len(positions),
            "total_value": total_value,
            "total_unrealized_pnl": total_unrealized_pnl,
            "total_realized_pnl": total_realized_pnl,
            "by_symbol": by_symbol
        }
    
    async def _add_position(self, position: Position) -> None:
        """
        Add a position to the tracker.
        
        Args:
            position: The position to add
        """
        async with self._lock:
            self._positions[position.position_id] = position
            
            if position.symbol not in self._positions_by_symbol:
                self._positions_by_symbol[position.symbol] = set()
            
            self._positions_by_symbol[position.symbol].add(position.position_id)
    
    async def _remove_position(self, position: Position) -> None:
        """
        Remove a position from the tracker.
        
        Args:
            position: The position to remove
        """
        async with self._lock:
            if position.position_id in self._positions:
                del self._positions[position.position_id]
            
            if position.symbol in self._positions_by_symbol:
                self._positions_by_symbol[position.symbol].discard(position.position_id)
                
                # Clean up empty sets
                if not self._positions_by_symbol[position.symbol]:
                    del self._positions_by_symbol[position.symbol]