"""
Rule Templates for Reusable Trading Strategies
==============================================

This module provides template functions for creating commonly used trading rules.
These templates can be configured with different parameters and applied to different symbols.

Usage:
    from src.rule.templates import create_scale_in_rule, create_stop_loss_rule
    
    # Create rules for different stocks
    aapl_scale = create_scale_in_rule("AAPL", scale_qty=50, profit_threshold=0.03)
    tsla_scale = create_scale_in_rule("TSLA", scale_qty=10, profit_threshold=0.05)
"""

import logging
from typing import Optional, Callable
from src.rule.base import Rule
from src.rule.condition import EventCondition, TimeCondition
from src.rule.linked_order_actions import LinkedCreateOrderAction, LinkedScaleInAction, LinkedCloseAllAction
from src.event.api import PredictionSignalEvent
from src.order import OrderType
from datetime import time

logger = logging.getLogger(__name__)


# ===== BUY/SELL RULE TEMPLATES =====

def create_buy_rule(
    symbol: str,
    quantity: int,
    confidence_threshold: float = 0.80,
    stop_loss_pct: float = 0.03,
    take_profit_pct: float = 0.08,
    cooldown_minutes: int = 5
) -> Rule:
    """
    Create a buy rule triggered by prediction signals.
    
    Args:
        symbol: Stock symbol (e.g., "AAPL")
        quantity: Number of shares to buy
        confidence_threshold: Minimum confidence level (0.0-1.0)
        stop_loss_pct: Stop loss percentage (e.g., 0.03 = 3%)
        take_profit_pct: Take profit percentage (e.g., 0.08 = 8%)
        cooldown_minutes: Cooldown period between trades
    """
    condition = EventCondition(
        event_type=PredictionSignalEvent,
        field_conditions={
            "symbol": symbol,
            "signal": "BUY",
            "confidence": lambda c: c >= confidence_threshold
        }
    )
    
    action = LinkedCreateOrderAction(
        symbol=symbol,
        quantity=quantity,
        order_type=OrderType.MARKET,
        auto_create_stops=True,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct
    )
    
    return Rule(
        rule_id=f"{symbol.lower()}_buy_rule",
        name=f"{symbol} Buy Rule",
        description=f"Buy {quantity} shares of {symbol} when confidence >= {confidence_threshold}",
        condition=condition,
        action=action,
        priority=100,
        cooldown_seconds=cooldown_minutes * 60
    )


def create_sell_rule(
    symbol: str,
    confidence_threshold: float = 0.80,
    cooldown_minutes: int = 5
) -> Rule:
    """Create a sell rule that closes all positions and orders for a symbol."""
    condition = EventCondition(
        event_type=PredictionSignalEvent,
        field_conditions={
            "symbol": symbol,
            "signal": "SELL",
            "confidence": lambda c: c >= confidence_threshold
        }
    )
    
    action = LinkedCloseAllAction(
        symbol=symbol,
        reason="Sell signal from prediction API"
    )
    
    return Rule(
        rule_id=f"{symbol.lower()}_sell_rule",
        name=f"{symbol} Sell Rule",
        description=f"Sell all {symbol} positions when confidence >= {confidence_threshold}",
        condition=condition,
        action=action,
        priority=100,
        cooldown_seconds=cooldown_minutes * 60
    )


# ===== SCALE-IN RULE TEMPLATES =====

def create_scale_in_rule(
    symbol: str,
    scale_quantity: int,
    confidence_threshold: float = 0.85,
    profit_threshold: float = 0.02,
    cooldown_minutes: int = 10
) -> Rule:
    """
    Create a scale-in rule that adds to existing profitable positions.
    
    Args:
        symbol: Stock symbol
        scale_quantity: Additional shares to buy
        confidence_threshold: Minimum confidence for scale-in (usually higher than initial buy)
        profit_threshold: Minimum profit percentage before allowing scale-in
        cooldown_minutes: Cooldown between scale-in attempts
    """
    condition = EventCondition(
        event_type=PredictionSignalEvent,
        field_conditions={
            "symbol": symbol,
            "signal": "BUY",
            "confidence": lambda c: c >= confidence_threshold
        }
    )
    
    action = LinkedScaleInAction(
        symbol=symbol,
        scale_quantity=scale_quantity,
        trigger_profit_pct=profit_threshold
    )
    
    return Rule(
        rule_id=f"{symbol.lower()}_scale_in_rule",
        name=f"{symbol} Scale-In Rule",
        description=f"Scale into {symbol} with {scale_quantity} shares when profitable and confidence >= {confidence_threshold}",
        condition=condition,
        action=action,
        priority=90,  # Lower priority than initial entry
        cooldown_seconds=cooldown_minutes * 60
    )


# ===== TIME-BASED RULE TEMPLATES =====

def create_eod_close_rule(
    symbol: str,
    close_time_hour: int = 15,
    close_time_minute: int = 30
) -> Rule:
    """Create an end-of-day rule to close all positions and orders for a symbol."""
    condition = TimeCondition(
        time_check=lambda: time().replace(hour=close_time_hour, minute=close_time_minute) <= time().now().time()
    )
    
    action = LinkedCloseAllAction(
        symbol=symbol,
        reason="End of day close"
    )
    
    return Rule(
        rule_id=f"{symbol.lower()}_eod_close",
        name=f"{symbol} End-of-Day Close",
        description=f"Close all {symbol} positions at {close_time_hour}:{close_time_minute:02d}",
        condition=condition,
        action=action,
        priority=200  # High priority
    )


# ===== STRATEGY BUILDER CLASS =====

class StrategyBuilder:
    """Helper class for building complete trading strategies."""
    
    @staticmethod
    def create_basic_strategy(
        symbol: str,
        quantity: int,
        confidence_threshold: float = 0.80,
        stop_loss_pct: float = 0.03,
        take_profit_pct: float = 0.08,
        enable_scale_in: bool = True,
        scale_quantity: Optional[int] = None
    ) -> list[Rule]:
        """
        Create a complete basic trading strategy with buy, sell, and optional scale-in rules.
        
        Returns:
            List of rules ready to be registered with the rule engine
        """
        rules = []
        
        # Main buy rule
        buy_rule = create_buy_rule(
            symbol=symbol,
            quantity=quantity,
            confidence_threshold=confidence_threshold,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct
        )
        rules.append(buy_rule)
        
        # Sell rule
        sell_rule = create_sell_rule(
            symbol=symbol,
            confidence_threshold=confidence_threshold
        )
        rules.append(sell_rule)
        
        # Optional scale-in rule
        if enable_scale_in:
            scale_qty = scale_quantity or (quantity // 2)  # Default to half the main quantity
            scale_rule = create_scale_in_rule(
                symbol=symbol,
                scale_quantity=scale_qty,
                confidence_threshold=confidence_threshold + 0.05  # Higher threshold
            )
            rules.append(scale_rule)
        
        # End-of-day close rule
        eod_rule = create_eod_close_rule(symbol)
        rules.append(eod_rule)
        
        logger.info(f"Created {len(rules)} rules for {symbol} strategy")
        return rules


# ===== EXAMPLE USAGE =====

def example_usage():
    """Example of how to use rule templates."""
    
    # Method 1: Individual rules
    aapl_buy = create_buy_rule("AAPL", quantity=100, confidence_threshold=0.85)
    aapl_scale = create_scale_in_rule("AAPL", scale_quantity=50)
    aapl_sell = create_sell_rule("AAPL")
    
    # Method 2: Complete strategy
    tsla_strategy = StrategyBuilder.create_basic_strategy(
        symbol="TSLA",
        quantity=25,
        confidence_threshold=0.90,
        stop_loss_pct=0.04,
        take_profit_pct=0.12,
        enable_scale_in=True,
        scale_quantity=10
    )
    
    # Method 3: Multiple stocks with same pattern
    symbols = ["AAPL", "MSFT", "NVDA"]
    all_rules = []
    
    for symbol in symbols:
        strategy_rules = StrategyBuilder.create_basic_strategy(
            symbol=symbol,
            quantity=50,
            confidence_threshold=0.80
        )
        all_rules.extend(strategy_rules)
    
    return all_rules 