"""
Base position class for the position management system.

This module defines the base Position class that provides common functionality
for all position types in the system.
"""

import uuid
import asyncio
import logging
from typing import Dict, Any, Optional, List, Set, Callable
from datetime import datetime
from enum import Enum

from src.event.position import PositionStatus

# Set up logger
logger = logging.getLogger(__name__)


class Position:
    """
    Base class for all position types.
    
    Provides common functionality for position tracking, state management,
    and lifecycle operations.
    """
    
    def __init__(self, symbol: str, position_id: Optional[str] = None):
        """
        Initialize a new position.
        
        Args:
            symbol: The symbol for this position
            position_id: Optional position ID (generated if not provided)
        """
        # Identifiers
        self.position_id = position_id or str(uuid.uuid4())
        self.symbol = symbol
        
        # Position state
        self._status = PositionStatus.PLANNED
        # Simplified locking for demo purposes
        self._lock = None
        self._version = 0
        
        # Timing
        self.create_time = datetime.now()
        self.update_time = self.create_time
        self.open_time = None
        self.close_time = None
        
        # Position details
        self.quantity = 0.0
        self.entry_price = None
        self.current_price = None
        self.exit_price = None
        
        # Risk management
        self.stop_loss = None
        self.take_profit = None
        
        # P&L tracking
        self.unrealized_pnl = 0.0
        self.realized_pnl = 0.0
        
        # Order management
        self.entry_order_ids: List[str] = []
        self.exit_order_ids: List[str] = []
        self.stop_order_ids: List[str] = []
        self.profit_order_ids: List[str] = []
        
        # Strategy reference
        self.strategy = None
        
        # Additional data
        self.metadata: Dict[str, Any] = {}
        
        # Update history
        self._updates: List[Dict[str, Any]] = []
        
        logger.debug(f"Created position {self.position_id} for {symbol}")
    
    @property
    def status(self) -> PositionStatus:
        """Get the current position status."""
        return self._status
    
    @property
    def is_active(self) -> bool:
        """Check if the position is active (not planned or closed)."""
        return self._status not in (PositionStatus.PLANNED, PositionStatus.CLOSED)
    
    @property
    def is_long(self) -> bool:
        """Check if the position is long (positive quantity)."""
        return self.quantity > 0
    
    @property
    def is_short(self) -> bool:
        """Check if the position is short (negative quantity)."""
        return self.quantity < 0
    
    @property
    def position_value(self) -> float:
        """Get the current value of the position."""
        if self.current_price is None or self.quantity == 0:
            return 0.0
        return abs(self.quantity) * self.current_price
    
    @property
    def entry_value(self) -> float:
        """Get the entry value of the position."""
        if self.entry_price is None or self.quantity == 0:
            return 0.0
        return abs(self.quantity) * self.entry_price
    
    @property
    def unrealized_pnl_pct(self) -> float:
        """Get the unrealized P&L as a percentage of entry value."""
        if self.entry_value == 0:
            return 0.0
        return self.unrealized_pnl / self.entry_value
    
    async def update_status(self, new_status: PositionStatus, reason: Optional[str] = None) -> bool:
        """
        Update the position status.

        Args:
            new_status: The new status to set
            reason: Optional reason for the status change

        Returns:
            bool: True if the status was changed, False if it was already set
        """
        # Simplified for demo - no locking
        if self._status == new_status:
            return False

        old_status = self._status
        self._status = new_status
        self.update_time = datetime.now()

        # Special status handling
        if new_status == PositionStatus.OPEN and not self.open_time:
            self.open_time = self.update_time
        elif new_status == PositionStatus.CLOSED and not self.close_time:
            self.close_time = self.update_time

        # Record the update
        self._record_update("status_change", {
            "old_status": old_status.value,
            "new_status": new_status.value,
            "reason": reason
        })

        logger.info(f"Position {self.position_id} status changed: {old_status.value} -> {new_status.value} ({reason or 'no reason'})")
        return True
    
    async def update_price(self, price: float) -> None:
        """
        Update the current price of the position.

        Args:
            price: The new price
        """
        # Simplified for demo - no locking
        old_price = self.current_price
        self.current_price = price
        self.update_time = datetime.now()

        # Recalculate P&L if we have an entry price
        if self.entry_price is not None:
            old_pnl = self.unrealized_pnl

            # Calculate new P&L
            if self.is_long:
                self.unrealized_pnl = (price - self.entry_price) * abs(self.quantity)
            else:
                self.unrealized_pnl = (self.entry_price - price) * abs(self.quantity)

            pnl_change = self.unrealized_pnl - old_pnl

            # Record significant P&L changes
            if abs(pnl_change) > 0.01:
                self._record_update("price_update", {
                    "old_price": old_price,
                    "new_price": price,
                    "old_pnl": old_pnl,
                    "new_pnl": self.unrealized_pnl,
                    "pnl_change": pnl_change
                })
    
    async def open(self, quantity: float, entry_price: float, order_id: Optional[str] = None) -> None:
        """
        Open the position with the specified quantity and entry price.

        Args:
            quantity: The position quantity (positive for long, negative for short)
            entry_price: The entry price
            order_id: Optional order ID associated with this open
        """
        # Simplified for demo - no locking
        self.quantity = quantity
        self.entry_price = entry_price
        self.current_price = entry_price  # Initialize current price to entry price
        self.unrealized_pnl = 0.0  # No P&L at entry

        if order_id:
            self.entry_order_ids.append(order_id)

        await self.update_status(PositionStatus.OPEN)

        # Record the open
        self._record_update("position_open", {
            "quantity": quantity,
            "entry_price": entry_price,
            "order_id": order_id
        })

        logger.info(f"Opened position {self.position_id} for {self.symbol}: {quantity} @ {entry_price}")
    
    async def close(self, exit_price: float, reason: Optional[str] = None, order_id: Optional[str] = None) -> None:
        """
        Close the position at the specified exit price.

        Args:
            exit_price: The exit price
            reason: Optional reason for closing
            order_id: Optional order ID associated with this close
        """
        # Simplified for demo - no locking
        self.exit_price = exit_price
        self.current_price = exit_price

        # Calculate realized P&L
        if self.entry_price is not None:
            if self.is_long:
                self.realized_pnl = (exit_price - self.entry_price) * abs(self.quantity)
            else:
                self.realized_pnl = (self.entry_price - exit_price) * abs(self.quantity)

        # Reset unrealized P&L
        self.unrealized_pnl = 0.0

        if order_id:
            self.exit_order_ids.append(order_id)

        await self.update_status(PositionStatus.CLOSED, reason)

        # Record the close
        self._record_update("position_close", {
            "exit_price": exit_price,
            "realized_pnl": self.realized_pnl,
            "reason": reason,
            "order_id": order_id
        })

        logger.info(f"Closed position {self.position_id} for {self.symbol}: {self.quantity} @ {exit_price} (P&L: {self.realized_pnl})")
    
    async def update_stop_loss(self, price: float) -> None:
        """
        Update the stop loss price.

        Args:
            price: The new stop loss price
        """
        # Simplified for demo - no locking
        old_stop = self.stop_loss
        self.stop_loss = price

        # Record the update
        self._record_update("stop_loss_update", {
            "old_stop": old_stop,
            "new_stop": price
        })

        logger.info(f"Updated stop loss for position {self.position_id}: {old_stop} -> {price}")
    
    async def update_take_profit(self, price: float) -> None:
        """
        Update the take profit price.

        Args:
            price: The new take profit price
        """
        # Simplified for demo - no locking
        old_target = self.take_profit
        self.take_profit = price

        # Record the update
        self._record_update("take_profit_update", {
            "old_target": old_target,
            "new_target": price
        })

        logger.info(f"Updated take profit for position {self.position_id}: {old_target} -> {price}")
    
    async def adjust(self,
                    quantity: Optional[float] = None,
                    stop_loss: Optional[float] = None,
                    take_profit: Optional[float] = None) -> None:
        """
        Adjust the position parameters.

        Args:
            quantity: Optional new quantity
            stop_loss: Optional new stop loss price
            take_profit: Optional new take profit price
        """
        # Simplified for demo - no locking
        await self.update_status(PositionStatus.ADJUSTING)

        updates = {}

        if quantity is not None and quantity != self.quantity:
            old_quantity = self.quantity
            self.quantity = quantity
            updates["quantity"] = {"old": old_quantity, "new": quantity}

        if stop_loss is not None and stop_loss != self.stop_loss:
            old_stop = self.stop_loss
            self.stop_loss = stop_loss
            updates["stop_loss"] = {"old": old_stop, "new": stop_loss}

        if take_profit is not None and take_profit != self.take_profit:
            old_target = self.take_profit
            self.take_profit = take_profit
            updates["take_profit"] = {"old": old_target, "new": take_profit}

        if updates:
            self._record_update("position_adjust", updates)

            await self.update_status(PositionStatus.OPEN)
            logger.info(f"Adjusted position {self.position_id} for {self.symbol}: {updates}")
        else:
            await self.update_status(PositionStatus.OPEN)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the position to a dictionary."""
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "status": self._status.value,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "exit_price": self.exit_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "create_time": self.create_time.isoformat(),
            "update_time": self.update_time.isoformat(),
            "open_time": self.open_time.isoformat() if self.open_time else None,
            "close_time": self.close_time.isoformat() if self.close_time else None,
            "entry_order_ids": self.entry_order_ids,
            "exit_order_ids": self.exit_order_ids,
            "stop_order_ids": self.stop_order_ids,
            "profit_order_ids": self.profit_order_ids,
            "strategy": self.strategy,
            "metadata": self.metadata
        }
    
    def _record_update(self, update_type: str, details: Dict[str, Any]) -> None:
        """
        Record a position update.
        
        Args:
            update_type: The type of update
            details: Details of the update
        """
        self._version += 1
        self._updates.append({
            "type": update_type,
            "version": self._version,
            "timestamp": datetime.now().isoformat(),
            "details": details
        })
    
    def __str__(self) -> str:
        """String representation of the position."""
        direction = "LONG" if self.is_long else "SHORT"
        status_str = self._status.value.upper()
        
        if self.entry_price is not None:
            price_str = f"{self.entry_price:.2f}"
        else:
            price_str = "N/A"
            
        if self.current_price is not None:
            current_str = f", current: {self.current_price:.2f}"
        else:
            current_str = ""
            
        pnl_str = ""
        if self.status == PositionStatus.OPEN:
            pnl_str = f", P&L: {self.unrealized_pnl:.2f} ({self.unrealized_pnl_pct:.2%})"
        elif self.status == PositionStatus.CLOSED:
            pnl_str = f", P&L: {self.realized_pnl:.2f}"
            
        return f"{self.symbol} {direction} {abs(self.quantity)} @ {price_str}{current_str}{pnl_str} [{status_str}]"