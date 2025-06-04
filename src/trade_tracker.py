"""
Trade Tracker for managing active trades.

This module provides persistent tracking of active trades to prevent
duplicate entries when multiple signals arrive.
"""

import logging
from typing import Dict, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TradeStatus(Enum):
    """Status of a trade."""
    ACTIVE = "active"
    CLOSED = "closed"
    PENDING_EXIT = "pending_exit"


@dataclass
class TradeInfo:
    """Information about an active trade."""
    symbol: str
    side: str  # "BUY" or "SELL"
    entry_time: datetime
    status: TradeStatus = TradeStatus.ACTIVE
    main_order_ids: Set[str] = field(default_factory=set)
    stop_order_ids: Set[str] = field(default_factory=set)
    target_order_ids: Set[str] = field(default_factory=set)
    
    def add_order(self, order_id: str, order_type: str):
        """Add an order ID to the appropriate set."""
        if order_type == "main":
            self.main_order_ids.add(order_id)
        elif order_type == "stop":
            self.stop_order_ids.add(order_id)
        elif order_type == "target":
            self.target_order_ids.add(order_id)


class TradeTracker:
    """
    Singleton class to track active trades across the application.
    
    This provides persistent tracking that survives between rule executions,
    unlike the context which gets copied.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._active_trades: Dict[str, TradeInfo] = {}
            self._initialized = True
            logger.info("TradeTracker initialized")
    
    def has_active_trade(self, symbol: str) -> bool:
        """Check if there's an active trade for a symbol."""
        return symbol in self._active_trades and self._active_trades[symbol].status == TradeStatus.ACTIVE
    
    def get_active_trade(self, symbol: str) -> Optional[TradeInfo]:
        """Get the active trade info for a symbol."""
        trade = self._active_trades.get(symbol)
        if trade and trade.status == TradeStatus.ACTIVE:
            return trade
        return None
    
    def start_trade(self, symbol: str, side: str) -> TradeInfo:
        """Start tracking a new trade."""
        if self.has_active_trade(symbol):
            logger.warning(f"Trade already active for {symbol}")
            return self._active_trades[symbol]
        
        trade = TradeInfo(
            symbol=symbol,
            side=side,
            entry_time=datetime.now()
        )
        self._active_trades[symbol] = trade
        logger.info(f"Started tracking {side} trade for {symbol}")
        return trade
    
    def close_trade(self, symbol: str):
        """Mark a trade as closed."""
        if symbol in self._active_trades:
            self._active_trades[symbol].status = TradeStatus.CLOSED
            logger.info(f"Closed trade for {symbol}")
            # Optionally remove from active trades
            del self._active_trades[symbol]
    
    def get_all_active_trades(self) -> Dict[str, TradeInfo]:
        """Get all active trades."""
        return {
            symbol: trade 
            for symbol, trade in self._active_trades.items() 
            if trade.status == TradeStatus.ACTIVE
        }
    
    def clear_all(self):
        """Clear all trades (for testing)."""
        self._active_trades.clear()
        logger.info("Cleared all trades from tracker") 