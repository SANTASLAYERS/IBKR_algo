"""
Linked Order Actions for automatic order relationship management.

This module provides enhanced order actions that automatically link related orders
through the rule engine context, enabling easy tracking and management of order groups.
"""

import logging
from typing import Dict, Any, Optional, List
from src.rule.base import Action
from src.rule.action import CreateOrderAction
from src.order import OrderType
from src.event.order import FillEvent
from src.trade_tracker import TradeTracker
import asyncio
from datetime import datetime

from src.event.bus import EventBus
from src.order.manager import OrderManager
from src.position.tracker import PositionTracker
from src.position.position_manager import PositionManager

logger = logging.getLogger(__name__)


class LinkedOrderConclusionManager:
    """Manages automatic context reset when positions are concluded via stops/targets."""
    
    def __init__(self, context: Dict[str, Any], event_bus):
        self.context = context
        self.event_bus = event_bus
        self._initialized = False
    
    async def initialize(self):
        """Subscribe to fill events to detect position conclusions."""
        if not self._initialized:
            # Import here to avoid circular imports
            await self.event_bus.subscribe(FillEvent, self.on_order_fill)
            self._initialized = True
            logger.info("LinkedOrderConclusionManager initialized - monitoring for position conclusions")
    
    async def on_order_fill(self, event):
        """Handle order fill events to detect position conclusions."""
        try:
            # Check if this was a stop or target order that concluded the position
            symbol = event.symbol
            order_id = event.order_id
            
            # Use PositionManager to find position and check if it's a protective order
            position_manager = PositionManager()
            position = position_manager.find_position_by_order(order_id)
            
            if not position:
                logger.debug(f"No position found for order {order_id}")
                return
            
            is_protective, order_type = position.is_protective_order(order_id)
            if not is_protective:
                logger.debug(f"Order {order_id} is not a protective order")
                return
            
            # Position concluded via stop/target fill
            logger.info(f"🎯 {position.side} position concluded for {symbol} - {order_type} order {order_id} filled at ${event.fill_price}")
            
            # Get all orders to cancel
            all_orders = position.get_all_orders()
            
            # Remove the filled order from the list
            all_orders.discard(order_id)
            
            # Cancel all remaining orders
            order_manager = self.context.get("order_manager")
            if order_manager:
                for remaining_order_id in all_orders:
                    try:
                        await order_manager.cancel_order(remaining_order_id, f"Position concluded via {order_type} fill")
                        logger.info(f"Cancelled remaining order {remaining_order_id} for {symbol}")
                    except Exception as e:
                        logger.warning(f"Failed to cancel order {remaining_order_id}: {e}")
            
            # Update both TradeTracker and PositionManager
            trade_tracker = TradeTracker()
            trade_tracker.close_trade(symbol)
            position_manager.close_position(symbol)
            
        except Exception as e:
            logger.error(f"Error handling fill event for position conclusion: {e}")


class CooldownResetManager:
    """Manages cooldown reset when stop loss orders are filled."""
    
    def __init__(self, rule_engine, event_bus):
        self.rule_engine = rule_engine
        self.event_bus = event_bus
        self._initialized = False
    
    async def initialize(self):
        """Subscribe to fill events to detect stop loss fills."""
        if not self._initialized:
            # Import here to avoid circular imports
            await self.event_bus.subscribe(FillEvent, self.on_order_fill)
            self._initialized = True
            logger.info("CooldownResetManager initialized - monitoring for stop loss fills")
    
    async def on_order_fill(self, event):
        """Handle order fill events to detect stop loss fills and reset cooldowns."""
        try:
            # Check if this was a stop loss order that got filled
            symbol = event.symbol
            order_id = event.order_id
            
            # Use PositionManager to check if it's a stop order
            position_manager = PositionManager()
            position = position_manager.find_position_by_order(order_id)
            
            if position and order_id in position.stop_orders:
                # Stop loss was hit - reset cooldowns for this symbol's rules
                side = position.side
                logger.info(f"🔄 Stop loss hit for {symbol} {side} position - resetting rule cooldowns")
                
                # Find and reset cooldowns for rules related to this symbol
                await self._reset_symbol_cooldowns(symbol)
                
        except Exception as e:
            logger.error(f"Error handling fill event for cooldown reset: {e}")
    
    async def _reset_symbol_cooldowns(self, symbol: str):
        """Reset cooldowns for all rules related to a specific symbol."""
        try:
            # Get all rules from the rule engine
            all_rules = self.rule_engine.get_all_rules()
            
            # Find rules that are related to this symbol
            symbol_rules = []
            for rule in all_rules:
                # Check if rule ID contains the symbol (our naming convention)
                if symbol.lower() in rule.rule_id.lower():
                    symbol_rules.append(rule)
            
            # Reset cooldowns for these rules
            for rule in symbol_rules:
                rule.reset_cooldown()
                logger.info(f"🔄 Reset cooldown for rule: {rule.rule_id}")
                
            if symbol_rules:
                logger.info(f"✅ Reset cooldowns for {len(symbol_rules)} rules related to {symbol}")
            
        except Exception as e:
            logger.error(f"Error resetting cooldowns for {symbol}: {e}")


class LinkedCreateOrderAction(Action):
    """Enhanced order creation that automatically links orders."""
    
    def __init__(self, 
                 symbol: str,
                 quantity: float,               # Can be allocation (if > 1000) or fixed shares
                 side: str,                    # NEW: Required parameter "BUY" or "SELL"
                 order_type: OrderType = OrderType.MARKET,
                 limit_price: Optional[float] = None,
                 stop_price: Optional[float] = None,
                 link_type: str = "main",  # main, stop, target, scale
                 auto_create_stops: bool = False,
                 stop_loss_pct: Optional[float] = None,
                 take_profit_pct: Optional[float] = None,
                 atr_stop_multiplier: Optional[float] = None,      # NEW: ATR multiplier for stop loss
                 atr_target_multiplier: Optional[float] = None):   # NEW: ATR multiplier for profit target
        
        self.symbol = symbol
        self.quantity = quantity  # Can be allocation or fixed shares
        self.side = side  # "BUY" or "SELL"
        self.order_type = order_type
        self.limit_price = limit_price
        self.stop_price = stop_price
        self.link_type = link_type
        self.auto_create_stops = auto_create_stops
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.atr_stop_multiplier = atr_stop_multiplier      # NEW: ATR * this for stop distance
        self.atr_target_multiplier = atr_target_multiplier  # NEW: ATR * this for target distance
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Create order and automatically link it with position reversal logic."""
        logger.debug(f"LinkedCreateOrderAction.execute called with context keys: {list(context.keys())}")
        
        order_manager = context.get("order_manager")
        if not order_manager:
            logger.error("Order manager not found in context")
            return False
        
        # Get the trade tracker singleton
        trade_tracker = TradeTracker()
        
        # Get the position manager singleton (for dual-write)
        position_manager = PositionManager()
        
        # FIRST: Check if we already have an active trade for this symbol
        active_trade = trade_tracker.get_active_trade(self.symbol)
        if active_trade:
            if active_trade.side == self.side:
                # Same side signal → IGNORE (we already have a trade in this direction)
                logger.info(f"Ignoring {self.side} signal for {self.symbol} - already have active {active_trade.side} trade")
                return True
            else:
                # Opposite side signal → EXIT current trade, then ENTER new trade
                logger.info(f"Reversing trade for {self.symbol}: {active_trade.side} → {self.side}")
                success = await self._exit_current_position(context)
                if not success:
                    logger.error(f"Failed to exit current trade for {self.symbol}")
                    return False
                # Trade tracker will be updated when exit completes
        
        # SECOND: Check actual positions from PositionTracker (as backup)
        position_tracker = context.get("position_tracker")
        if position_tracker:
            positions = await position_tracker.get_positions_for_symbol(self.symbol)
            active_positions = [p for p in positions if p.status.value == "open"]
            
            if active_positions:
                position = active_positions[0]
                position_side = "BUY" if position.is_long else "SELL"
                
                if position_side == self.side:
                    # Same side signal → IGNORE (we already have a position in this direction)
                    logger.info(f"Ignoring {self.side} signal for {self.symbol} - already have {position_side} position")
                    return True
                else:
                    # Opposite side signal → EXIT current position, then ENTER new position
                    logger.info(f"Reversing position for {self.symbol}: {position_side} → {self.side}")
                    success = await self._exit_current_position(context)
                    if not success:
                        logger.error(f"Failed to exit current position for {self.symbol}")
                        return False
                    # Context is now cleared, proceed with new position creation
        
        # Note: Context modifications (like adding symbol entries) are not persisted 
        # between rule executions because the rule creates a copy of the context.
        # The duplicate prevention relies on checking active orders and positions above.
        
        try:
            # Start tracking this new trade
            trade_tracker.start_trade(self.symbol, self.side)
            
            # DUAL-WRITE: Also open position in PositionManager
            position_manager.open_position(self.symbol, self.side)
            logger.debug(f"Opened position in PositionManager for {self.symbol} {self.side}")
            
            # Calculate actual shares to trade
            actual_shares = await self._calculate_position_size(context)
            if actual_shares is None:
                logger.warning(f"Could not calculate position size for {self.symbol}")
                return False
            
            # Adjust quantity based on side (positive for BUY, negative for SELL)
            actual_quantity = abs(actual_shares) if self.side == "BUY" else -abs(actual_shares)
            
            # Create the main order
            order = await order_manager.create_order(
                symbol=self.symbol,
                quantity=actual_quantity,
                order_type=self.order_type,
                limit_price=self.limit_price,
                stop_price=self.stop_price,
                auto_submit=True  # Submit immediately
            )
            
            # Track in PositionManager
            position_manager.add_orders_to_position(self.symbol, self.link_type, [order.order_id])
            
            # Store quantity and ATR multipliers in PositionManager instead of context
            position_manager.update_position_entry(self.symbol, self.limit_price or 0, actual_quantity)
            if self.atr_stop_multiplier is not None or self.atr_target_multiplier is not None:
                position_manager.update_position_atr_params(
                    self.symbol, 
                    self.atr_stop_multiplier, 
                    self.atr_target_multiplier
                )
            
            # Auto-create stop loss and take profit if requested
            if self.auto_create_stops and self.link_type == "main":
                await self._create_protective_orders(context, order, actual_shares)
                
                # Auto-create double down orders only if we have stops
                await self._create_double_down_orders(context, actual_shares)
            
            logger.info(f"Created and linked {self.side} {self.link_type} order {order.order_id} for {self.symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating linked order for {self.symbol}: {e}")
            return False
    
    async def _calculate_position_size(self, context: Dict[str, Any]) -> Optional[int]:
        """Calculate position size based on allocation or use fixed quantity."""
        # If quantity is large (> 1000), treat it as dollar allocation
        if self.quantity > 1000:
            # Dynamic position sizing based on allocation
            price_service = context.get("price_service")
            position_sizer = context.get("position_sizer")
            
            if not price_service or not position_sizer:
                logger.warning(f"Price service or position sizer not available - using quantity as shares")
                return int(self.quantity)
            
            # Get current price
            current_price = await price_service.get_price(self.symbol)
            if not current_price:
                logger.error(f"Could not get price for {self.symbol}")
                return None
            
            # Calculate shares for allocation
            shares = position_sizer.calculate_shares(
                allocation=self.quantity,
                price=current_price,
                side=self.side
            )
            
            if shares is None:
                logger.error(f"Position sizer returned None for {self.symbol}")
                return None
                
            return shares
        else:
            # Treat as fixed number of shares
            logger.info(f"Using fixed position size: {int(self.quantity)} shares for {self.symbol}")
            return int(self.quantity)
    
    async def _exit_current_position(self, context: Dict[str, Any]) -> bool:
        """Exit current position by canceling all orders and closing position."""
        try:
            # Use LinkedCloseAllAction to cleanly exit current position
            close_action = LinkedCloseAllAction(
                symbol=self.symbol,
                reason="Position reversal - exiting current position"
            )
            
            result = await close_action.execute(context)
            if result:
                logger.info(f"Successfully exited current position for {self.symbol}")
            else:
                logger.warning(f"Failed to fully exit current position for {self.symbol}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error exiting current position for {self.symbol}: {e}")
            return False
    
    async def _create_protective_orders(self, context: Dict[str, Any], main_order, actual_shares):
        """Create stop loss and take profit orders."""
        order_manager = context.get("order_manager")
        position_manager = PositionManager()
        
        # Get current price for calculations
        current_price = self.limit_price or context.get("prices", {}).get(self.symbol)
        if not current_price:
            price_service = context.get("price_service")
            if price_service:
                current_price = await price_service.get_price(self.symbol)
        
        if not current_price:
            logger.warning(f"No price available for {self.symbol} protective orders")
            return
        
        # Try to get ATR value if using ATR-based stops
        atr_value = None
        if self.atr_stop_multiplier is not None or self.atr_target_multiplier is not None:
            indicator_manager = context.get("indicator_manager")
            if indicator_manager:
                try:
                    # Calculate 10-second ATR with 14 periods
                    atr_value = await indicator_manager.get_atr(
                        symbol=self.symbol,
                        period=14,
                        days=1,
                        bar_size="10 secs"
                    )
                    if atr_value:
                        logger.info(f"ATR for {self.symbol}: {atr_value:.4f}")
                    else:
                        logger.warning(f"Failed to calculate ATR for {self.symbol}")
                except Exception as e:
                    logger.error(f"Error calculating ATR for {self.symbol}: {e}")
        
        # Create stop loss order
        stop_price = None
        if self.atr_stop_multiplier is not None and atr_value is not None:
            # Use ATR-based stop loss
            stop_distance = atr_value * self.atr_stop_multiplier
            if self.side == "BUY":  # Long position
                stop_price = current_price - stop_distance
                stop_quantity = -abs(actual_shares)  # Sell to close long
            else:  # Short position (SELL)
                stop_price = current_price + stop_distance
                stop_quantity = abs(actual_shares)   # Buy to close short
            logger.info(f"ATR-based stop: {self.symbol} stop at ${stop_price:.2f} (ATR: {atr_value:.4f} * {self.atr_stop_multiplier} = {stop_distance:.4f})")
            
        elif self.stop_loss_pct:
            # Fallback to percentage-based stop loss
            if self.side == "BUY":  # Long position
                stop_price = current_price * (1 - self.stop_loss_pct)
                stop_quantity = -abs(actual_shares)  # Sell to close long
            else:  # Short position (SELL)
                stop_price = current_price * (1 + self.stop_loss_pct)  # Higher than entry
                stop_quantity = abs(actual_shares)   # Buy to close short
            logger.info(f"Percentage-based stop: {self.symbol} stop at ${stop_price:.2f} ({self.stop_loss_pct:.1%})")
        
        if stop_price is not None:
            # Round to 2 decimal places for proper tick size
            stop_price = round(stop_price, 2)
            stop_order = await order_manager.create_order(
                symbol=self.symbol,
                quantity=stop_quantity,
                order_type=OrderType.STOP,
                stop_price=stop_price,
                auto_submit=True  # Submit immediately
            )
            
            position_manager.add_orders_to_position(self.symbol, "stop", [stop_order.order_id])
            logger.info(f"Auto-created {self.side} stop loss {stop_order.order_id} at ${stop_price:.2f}")
        
        # Create take profit order
        target_price = None
        if self.atr_target_multiplier is not None and atr_value is not None:
            # Use ATR-based take profit
            target_distance = atr_value * self.atr_target_multiplier
            if self.side == "BUY":  # Long position
                target_price = current_price + target_distance
                target_quantity = -abs(actual_shares)  # Sell to close long
            else:  # Short position (SELL)
                target_price = current_price - target_distance
                target_quantity = abs(actual_shares)   # Buy to close short
            logger.info(f"ATR-based target: {self.symbol} target at ${target_price:.2f} (ATR: {atr_value:.4f} * {self.atr_target_multiplier} = {target_distance:.4f})")
            
        elif self.take_profit_pct:
            # Fallback to percentage-based take profit
            if self.side == "BUY":  # Long position
                target_price = current_price * (1 + self.take_profit_pct)
                target_quantity = -abs(actual_shares)  # Sell to close long
            else:  # Short position (SELL)
                target_price = current_price * (1 - self.take_profit_pct)  # Lower than entry
                target_quantity = abs(actual_shares)   # Buy to close short
            logger.info(f"Percentage-based target: {self.symbol} target at ${target_price:.2f} ({self.take_profit_pct:.1%})")
        
        if target_price is not None:
            # Round to 2 decimal places for proper tick size
            target_price = round(target_price, 2)
            target_order = await order_manager.create_order(
                symbol=self.symbol,
                quantity=target_quantity,
                order_type=OrderType.LIMIT,
                limit_price=target_price,
                auto_submit=True  # Submit immediately
            )
            
            position_manager.add_orders_to_position(self.symbol, "target", [target_order.order_id])
            logger.info(f"Auto-created {self.side} take profit {target_order.order_id} at ${target_price:.2f}")

    async def _create_double_down_orders(self, context: Dict[str, Any], actual_shares):
        """Create double down limit orders automatically after entry."""
        try:
            logger.info(f"Starting double down order creation for {self.symbol}")
            
            # Wait a bit for stop orders to be created
            await asyncio.sleep(0.5)
            
            # Get position manager
            position_manager = PositionManager()
            
            # Check if stop orders exist now
            stop_orders = position_manager.get_linked_orders(self.symbol, "stop")
            logger.info(f"Found {len(stop_orders)} stop orders for {self.symbol}: {stop_orders}")
            
            if not stop_orders:
                logger.warning(f"No stop orders found yet for {self.symbol}, skipping double down creation")
                return
            
            # Create double down action
            double_down_action = LinkedDoubleDownAction(
                symbol=self.symbol,
                distance_to_stop_multiplier=0.5,  # 1/2 of the way to stop loss (halfway)
                quantity_multiplier=1.0,          # Same size as original position
                level_name="doubledown1"          # First double down level
            )
            
            # Execute double down creation
            logger.info(f"Executing double down action for {self.symbol}")
            success = await double_down_action.execute(context)
            if success:
                logger.info(f"Auto-created double down order for {self.symbol}")
            else:
                logger.warning(f"Failed to create double down order for {self.symbol}")
                
        except Exception as e:
            logger.error(f"Error creating double down orders for {self.symbol}: {e}", exc_info=True)


class LinkedScaleInAction(Action):
    """Scale-in action that automatically links and updates related orders."""
    
    def __init__(self, 
                 symbol: str,
                 scale_quantity: float,
                 trigger_profit_pct: float = 0.02):
        self.symbol = symbol
        self.scale_quantity = scale_quantity
        self.trigger_profit_pct = trigger_profit_pct
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Execute scale-in and update linked orders."""
        order_manager = context.get("order_manager")
        position_tracker = context.get("position_tracker")
        
        if not order_manager or not position_tracker:
            logger.error("Required managers not found in context")
            return False
        
        try:
            # Get position manager
            position_manager = PositionManager()
            
            # Find the side of existing position
            side = await position_manager.find_active_position_side(self.symbol)
            if not side:
                logger.info(f"No active position for {self.symbol} scale-in")
                return False
            
            # Check if we have an existing position
            positions = await position_tracker.get_positions_for_symbol(self.symbol)
            active_positions = [p for p in positions if p.status.value == "open"]
            
            if not active_positions:
                logger.info(f"No active position for {self.symbol} scale-in")
                return False
            
            position = active_positions[0]
            
            # Check profitability threshold
            if position.unrealized_pnl_pct < self.trigger_profit_pct:
                logger.info(f"Position not profitable enough for scale-in: {position.unrealized_pnl_pct:.2%}")
                return False
            
            # Create scale-in order with correct quantity for side
            if side == "BUY":
                scale_quantity = abs(self.scale_quantity)  # Positive for additional long
            else:  # SELL
                scale_quantity = -abs(self.scale_quantity)  # Negative for additional short
            
            scale_order = await order_manager.create_order(
                symbol=self.symbol,
                quantity=scale_quantity,
                order_type=OrderType.MARKET,
                auto_submit=True  # Submit immediately
            )
            
            # Link the scale order
            position_manager.add_orders_to_position(self.symbol, "scale", [scale_order.order_id])
            
            # Update stop and target orders with new average price
            await self._update_protective_orders(context, position, scale_order, side)
            
            logger.info(f"Scale-in executed: {side} {scale_order.order_id} for {self.symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error executing scale-in for {self.symbol}: {e}")
            return False
    
    async def _update_protective_orders(self, context: Dict[str, Any], position, scale_order, side: str):
        """Update stop loss and take profit orders after scale-in."""
        order_manager = context.get("order_manager")
        position_manager = PositionManager()
        
        # Calculate new average price
        current_value = position.quantity * position.entry_price
        new_value = scale_order.quantity * position.current_price
        new_quantity = position.quantity + scale_order.quantity
        new_avg_price = (current_value + new_value) / new_quantity
        
        # Get linked stop and target orders
        stop_orders = position_manager.get_linked_orders(self.symbol, "stop")
        target_orders = position_manager.get_linked_orders(self.symbol, "target")
        
        # Cancel existing stop and target orders
        old_stop_orders = stop_orders.copy()
        old_target_orders = target_orders.copy()
        
        for stop_id in old_stop_orders:
            try:
                await order_manager.cancel_order(stop_id, "Scale-in - updating protective orders")
                logger.info(f"Cancelled old stop order {stop_id}")
            except Exception as e:
                logger.warning(f"Failed to cancel stop order {stop_id}: {e}")
        
        for target_id in old_target_orders:
            try:
                await order_manager.cancel_order(target_id, "Scale-in - updating protective orders")
                logger.info(f"Cancelled old target order {target_id}")
            except Exception as e:
                logger.warning(f"Failed to cancel target order {target_id}: {e}")
        
        # Remove old orders from PositionManager
        for order_id in old_stop_orders + old_target_orders:
            position_manager.remove_order(self.symbol, order_id)
        
        # Get position ATR parameters
        pm_position = position_manager.get_position(self.symbol)
        
        # Calculate new stop and target prices
        if pm_position and (pm_position.atr_stop_multiplier is not None or pm_position.atr_target_multiplier is not None):
            # Try to get ATR
            indicator_manager = context.get("indicator_manager")
            atr = None
            if indicator_manager:
                try:
                    atr = await indicator_manager.get_atr(self.symbol, period=14, days=1, bar_size="10 secs")
                except Exception as e:
                    logger.warning(f"Could not get ATR: {e}")
            
            if atr and pm_position.atr_stop_multiplier is not None:
                stop_distance = atr * pm_position.atr_stop_multiplier
            else:
                stop_distance = new_avg_price * 0.03
                
            if atr and pm_position.atr_target_multiplier is not None:
                target_distance = atr * pm_position.atr_target_multiplier
            else:
                target_distance = new_avg_price * 0.06
        else:
            # Fallback to percentage-based (3% stop, 6% target)
            stop_distance = new_avg_price * 0.03
            target_distance = new_avg_price * 0.06
        
        if side == "BUY":
            stop_price = new_avg_price - stop_distance
            target_price = new_avg_price + target_distance
            # For long positions, stop/target orders are sell orders (negative quantity)
            order_quantity = -abs(new_quantity)
        else:
            stop_price = new_avg_price + stop_distance
            target_price = new_avg_price - target_distance
            # For short positions, stop/target orders are buy orders (positive quantity)
            order_quantity = abs(new_quantity)
        
        # Round to 2 decimal places
        stop_price = round(stop_price, 2)
        target_price = round(target_price, 2)
        
        # Create new stop order
        try:
            stop_order = await order_manager.create_order(
                symbol=self.symbol,
                quantity=order_quantity,
                order_type=OrderType.STOP,
                stop_price=stop_price,
                auto_submit=True  # Submit immediately
            )
            
            if stop_order:
                # Track in PositionManager
                position_manager.add_orders_to_position(self.symbol, "stop", [stop_order.order_id])
                
                self.logger.info(f"Created updated stop order {stop_order.order_id} for {self.symbol} "
                               f"at ${stop_price:.2f} for {order_quantity} shares")
        except Exception as e:
            self.logger.error(f"Failed to create stop order: {e}")
        
        # Create new target order
        try:
            target_order = await order_manager.create_order(
                symbol=self.symbol,
                quantity=order_quantity,
                order_type=OrderType.LIMIT,
                limit_price=target_price,
                auto_submit=True  # Submit immediately
            )
            
            if target_order:
                # Track in PositionManager
                position_manager.add_orders_to_position(self.symbol, "target", [target_order.order_id])
                
                self.logger.info(f"Created updated target order {target_order.order_id} for {self.symbol} "
                               f"at ${target_price:.2f} for {order_quantity} shares")
        except Exception as e:
            self.logger.error(f"Failed to create target order: {e}")
        
        # Update position info with new metrics
        position_manager.update_position_entry(self.symbol, new_avg_price, new_quantity)
        
        self.logger.info(f"Updated protective orders for {self.symbol}: "
                        f"New quantity={new_quantity}, New avg=${new_avg_price:.2f}") 


class LinkedCloseAllAction(Action):
    """Close all linked orders for a symbol."""
    
    def __init__(self, symbol: str, reason: str = "Close all linked orders"):
        self.symbol = symbol
        self.reason = reason
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Cancel all linked orders and close position."""
        order_manager = context.get("order_manager")
        position_tracker = context.get("position_tracker")
        
        if not order_manager or not position_tracker:
            return False
        
        try:
            # Get position manager
            position_manager = PositionManager()
            
            # Get all linked orders from PositionManager
            all_orders = position_manager.get_linked_orders(self.symbol)
            
            # Cancel all orders
            for order_id in all_orders:
                await order_manager.cancel_order(order_id, self.reason)
                position_manager.remove_order(self.symbol, order_id)
            
            # Close position
            positions = await position_tracker.get_positions_for_symbol(self.symbol)
            for position in positions:
                await position_tracker.close_position(position.position_id, self.reason)
            
            # Update TradeTracker
            trade_tracker = TradeTracker()
            trade_tracker.close_trade(self.symbol)
            
            # Close in PositionManager
            position_manager.close_position(self.symbol)
            logger.debug(f"Closed position in PositionManager for {self.symbol}")
            
            logger.info(f"Closed all linked orders and position for {self.symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error closing linked orders for {self.symbol}: {e}")
            return False


class LinkedDoubleDownAction(Action):
    """
    Double down action that places limit orders at specified levels below entry.
    Designed for averaging down when price moves against the position.
    """
    
    def __init__(self, 
                 symbol: str,
                 distance_to_stop_multiplier: float = 0.5,  # 0.5 = halfway to stop
                 quantity_multiplier: float = 1.0,          # 1.0 = same size as original
                 level_name: str = "doubledown1"):          # Unique identifier for this level
        """
        Initialize the double down action.
        
        Args:
            symbol: The symbol to trade
            distance_to_stop_multiplier: How far toward the stop to place order (0.5 = halfway)
            quantity_multiplier: Size relative to original position (1.0 = same size)
            level_name: Unique name for this double down level
        """
        self.symbol = symbol
        self.distance_to_stop_multiplier = distance_to_stop_multiplier
        self.quantity_multiplier = quantity_multiplier
        self.level_name = level_name
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Create double down limit order linked to existing position."""
        order_manager = context.get("order_manager")
        if not order_manager:
            logger.error("Order manager not found in context")
            return False
        
        try:
            # Get position manager
            position_manager = PositionManager()
            
            # Check if we have an active position for this symbol
            if not position_manager.has_active_position(self.symbol):
                logger.info(f"No active position for {self.symbol} - cannot create double down order")
                return False
            
            position = position_manager.get_position(self.symbol)
            side = position.side
            
            # Double down works for both BUY and SELL positions
            if side not in ["BUY", "SELL"]:
                logger.error(f"Invalid position side for {self.symbol}: {side}")
                return False
            
            # Check if this double down level already exists
            existing_orders = position_manager.get_linked_orders(self.symbol, "doubledown")
            if any(self.level_name in str(order_id) for order_id in existing_orders):
                logger.info(f"Double down level '{self.level_name}' already exists for {self.symbol}")
                return True
            
            # Get the main order info to calculate quantities and prices
            main_orders = position_manager.get_linked_orders(self.symbol, "main")
            if not main_orders:
                logger.error(f"No main orders found for {self.symbol}")
                return False
            
            # Calculate double down parameters
            double_down_price, double_down_quantity = await self._calculate_double_down_parameters(context)
            if double_down_price is None or double_down_quantity is None:
                logger.error(f"Could not calculate double down parameters for {self.symbol}")
                return False
            
            # Create the double down limit order
            double_down_order = await order_manager.create_order(
                symbol=self.symbol,
                quantity=double_down_quantity,  # Positive for BUY, negative for SELL
                order_type=OrderType.LIMIT,
                limit_price=double_down_price,
                auto_submit=True  # Submit immediately
            )
            
            # Track in PositionManager
            position_manager.add_orders_to_position(self.symbol, "doubledown", [double_down_order.order_id])
            
            logger.info(f"Created {side} double down order '{self.level_name}' for {self.symbol}: "
                       f"{double_down_quantity} shares @ ${double_down_price:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating double down order for {self.symbol}: {e}")
            return False
    
    async def _calculate_double_down_parameters(self, context: Dict[str, Any]) -> tuple[Optional[float], Optional[int]]:
        """Calculate the price and quantity for the double down order."""
        try:
            # Get position manager
            position_manager = PositionManager()
            position = position_manager.get_position(self.symbol)
            if not position:
                logger.error(f"No position found for {self.symbol}")
                return None, None
            
            # Get current price - SKIP price service to avoid 5-second delay
            current_price = context.get("prices", {}).get(self.symbol)
            if current_price:
                logger.info(f"Using context price for {self.symbol}: ${current_price:.2f}")
            
            if not current_price:
                # Only try price service as last resort
                price_service = context.get("price_service")
                if price_service:
                    try:
                        current_price = await price_service.get_price(self.symbol)
                    except Exception as e:
                        logger.warning(f"Price service failed for {self.symbol}: {e}")
                
            if not current_price:
                logger.error(f"Could not get current price for {self.symbol}")
                return None, None
            
            # Get existing stop orders to calculate stop distance
            stop_orders = position_manager.get_linked_orders(self.symbol, "stop")
            if not stop_orders:
                logger.error(f"No stop orders found for {self.symbol}")
                return None, None
            
            # Get stop price from order manager
            order_manager = context.get("order_manager")
            stop_order_id = stop_orders[0]  # Use first stop order
            
            # For this implementation, we'll calculate based on ATR if available
            # Otherwise fall back to a percentage-based approach
            stop_distance = await self._calculate_stop_distance(context, current_price)
            if stop_distance is None:
                logger.error(f"Could not calculate stop distance for {self.symbol}")
                return None, None
            
            # Get position side
            side = position.side
            
            # Calculate double down price based on position side
            double_down_distance = stop_distance * self.distance_to_stop_multiplier
            
            if side == "BUY":
                # For long positions: place limit buy below current price
                double_down_price = current_price - double_down_distance
            else:  # SELL
                # For short positions: place limit sell above current price
                double_down_price = current_price + double_down_distance
            
            # Round to 2 decimal places for proper tick size
            double_down_price = round(double_down_price, 2)
            
            # Calculate double down quantity based on original position size
            original_quantity = abs(position.current_quantity)
            
            if original_quantity == 0:
                # Fallback: calculate from allocation if available
                allocation = 10000  # Default $10K allocation
                original_quantity = int(allocation / current_price)
            
            double_down_quantity = int(original_quantity * self.quantity_multiplier)
            
            # Adjust quantity sign based on side
            if side == "BUY":
                double_down_quantity = abs(double_down_quantity)  # Positive for buy
            else:  # SELL
                double_down_quantity = -abs(double_down_quantity)  # Negative for sell
            
            logger.info(f"Double down calc for {self.symbol} ({side}): "
                       f"current=${current_price:.2f}, stop_distance=${stop_distance:.2f}, "
                       f"dd_distance=${double_down_distance:.2f}, dd_price=${double_down_price:.2f}, "
                       f"original_qty={original_quantity}, dd_qty={double_down_quantity}")
            
            return double_down_price, double_down_quantity
            
        except Exception as e:
            logger.error(f"Error calculating double down parameters: {e}")
            return None, None
    
    async def _calculate_stop_distance(self, context: Dict[str, Any], current_price: float) -> Optional[float]:
        """Calculate the distance from current price to stop loss."""
        try:
            # Get position from PositionManager
            position_manager = PositionManager()
            position = position_manager.get_position(self.symbol)
            
            if position and position.atr_stop_multiplier is not None:
                # Try to get ATR value
                indicator_manager = context.get("indicator_manager")
                if indicator_manager:
                    try:
                        atr_value = await indicator_manager.get_atr(
                            symbol=self.symbol,
                            period=14,
                            days=1,
                            bar_size="10 secs"
                        )
                        if atr_value:
                            stop_distance = atr_value * position.atr_stop_multiplier
                            logger.info(f"Using ATR-based stop distance for {self.symbol}: {stop_distance:.4f}")
                            return stop_distance
                    except Exception as e:
                        logger.warning(f"Could not calculate ATR for {self.symbol}: {e}")
            
            # Fallback to percentage-based stop (3% for most stocks)
            stop_distance = current_price * 0.03
            logger.info(f"Using percentage-based stop distance for {self.symbol}: {stop_distance:.4f}")
            return stop_distance
            
        except Exception as e:
            logger.error(f"Error calculating stop distance: {e}")
            return None


class LinkedDoubleDownFillManager:
    """Manager that monitors double down order fills and updates stop/target orders accordingly."""
    
    def __init__(self, context: Dict[str, Any], event_bus):
        self.context = context
        self.event_bus = event_bus
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def initialize(self):
        """Subscribe to order fill events."""
        await self.event_bus.subscribe(FillEvent, self.on_order_fill)
        self.logger.info("LinkedDoubleDownFillManager initialized")
    
    async def on_order_fill(self, event: FillEvent):
        """Handle order fill events to detect double down fills."""
        try:
            symbol = event.symbol
            order_id = event.order_id
            
            self.logger.debug(f"[DD FILL] Checking fill event for {symbol}, order {order_id}")
            
            # Check PositionManager for double down orders
            position_manager = PositionManager()
            position = position_manager.find_position_by_order(order_id)
            if not position or position.symbol != symbol:
                self.logger.debug(f"[DD FILL] Order {order_id} not found in PositionManager")
                return
            
            is_doubledown = order_id in position.doubledown_orders
            if not is_doubledown:
                self.logger.debug(f"[DD FILL] Order {order_id} is not a double down order")
                return
            
            self.logger.info(f"Double down order {order_id} filled for {symbol} - updating protective orders")
            
            # Get current position data
            position_tracker = self.context.get("position_tracker")
            if not position_tracker:
                self.logger.error("Position tracker not found")
                return
            
            positions = await position_tracker.get_positions_for_symbol(symbol)
            if not positions:
                # Fallback: Create mock position data based on the main order fill
                self.logger.warning(f"No position found in PositionTracker for {symbol}, using order data")
                
                # Get the main order fill price from context or use current price
                main_fill_price = event.fill_price  # Use double down fill price as approximation
                
                # Create mock position data
                class MockPosition:
                    def __init__(self, symbol, quantity, entry_price, is_long):
                        self.symbol = symbol
                        self.quantity = quantity
                        self.entry_price = entry_price
                        self.is_long = is_long
                
                # Determine if long or short from PositionManager
                pm_position = position_manager.get_position(symbol)
                if pm_position:
                    is_long = pm_position.side == "BUY"
                    # For long positions, the original quantity should be positive
                    # For short positions, the original quantity should be negative
                    original_quantity = abs(event.fill_quantity) if is_long else -abs(event.fill_quantity)
                else:
                    # Fallback based on event quantity
                    is_long = event.fill_quantity > 0
                    original_quantity = abs(event.fill_quantity) if is_long else -abs(event.fill_quantity)
                
                position = MockPosition(
                    symbol=symbol,
                    quantity=original_quantity,
                    entry_price=main_fill_price,
                    is_long=is_long
                )
            else:
                position = positions[0]
            
            # Calculate new position metrics after double down
            old_quantity = position.quantity
            dd_quantity = event.fill_quantity  # Use fill_quantity, not quantity
            new_quantity = old_quantity + dd_quantity
            
            self.logger.info(f"[DD FILL DEBUG] old_quantity={old_quantity}, dd_quantity={dd_quantity}, new_quantity={new_quantity}")
            
            # Calculate new average price
            old_value = abs(old_quantity) * position.entry_price
            dd_value = abs(dd_quantity) * event.fill_price
            new_avg_price = (old_value + dd_value) / abs(new_quantity)
            
            # Update protective orders
            await self._update_protective_orders(
                symbol=symbol,
                new_quantity=new_quantity,
                new_avg_price=new_avg_price,
                is_long=position.is_long
            )
            
        except Exception as e:
            self.logger.error(f"Error handling double down fill: {e}", exc_info=True)
    
    async def _update_protective_orders(self, symbol: str, new_quantity: float, 
                                       new_avg_price: float, is_long: bool):
        """Cancel old and create new protective orders with updated quantities."""
        order_manager = self.context.get("order_manager")
        indicator_manager = self.context.get("indicator_manager")
        position_manager = PositionManager()
        
        if not order_manager:
            self.logger.error("Order manager not found")
            return
        
        # Get position from PositionManager
        pm_position = position_manager.get_position(symbol)
        if not pm_position:
            self.logger.error(f"Position not found in PositionManager for {symbol}")
            return
        
        # Get ATR for stop/target calculations if indicator manager available
        atr = None
        if indicator_manager:
            try:
                atr = await indicator_manager.get_atr(
                    symbol=symbol,
                    period=14,
                    days=1,
                    bar_size="10 secs"
                )
                if atr:
                    self.logger.info(f"ATR for {symbol}: {atr:.4f}")
            except Exception as e:
                self.logger.warning(f"Could not get ATR for {symbol}: {e}")
        
        # Get ATR multipliers from position
        stop_multiplier = pm_position.atr_stop_multiplier or 6.0
        target_multiplier = pm_position.atr_target_multiplier or 3.0
        
        # Get position side
        side = pm_position.side
        
        # Cancel existing stop and target orders
        old_stop_orders = list(pm_position.stop_orders)
        old_target_orders = list(pm_position.target_orders)
        
        for stop_id in old_stop_orders:
            try:
                await order_manager.cancel_order(stop_id, "Double down fill - updating protective orders")
                self.logger.info(f"Cancelled old stop order {stop_id}")
            except Exception as e:
                self.logger.warning(f"Failed to cancel stop order {stop_id}: {e}")
        
        for target_id in old_target_orders:
            try:
                await order_manager.cancel_order(target_id, "Double down fill - updating protective orders")
                self.logger.info(f"Cancelled old target order {target_id}")
            except Exception as e:
                self.logger.warning(f"Failed to cancel target order {target_id}: {e}")
        
        # Remove old orders from PositionManager
        for order_id in old_stop_orders + old_target_orders:
            position_manager.remove_order(symbol, order_id)
        
        # Calculate new stop and target prices
        if atr:
            # Use ATR-based calculations
            stop_distance = atr * stop_multiplier
            target_distance = atr * target_multiplier
        else:
            # Fallback to percentage-based (3% stop, 6% target)
            stop_distance = new_avg_price * 0.03
            target_distance = new_avg_price * 0.06
        
        if is_long:
            stop_price = new_avg_price - stop_distance
            target_price = new_avg_price + target_distance
            # For long positions, stop/target orders are sell orders (negative quantity)
            order_quantity = -abs(new_quantity)
        else:
            stop_price = new_avg_price + stop_distance
            target_price = new_avg_price - target_distance
            # For short positions, stop/target orders are buy orders (positive quantity)
            order_quantity = abs(new_quantity)
        
        # Round to 2 decimal places
        stop_price = round(stop_price, 2)
        target_price = round(target_price, 2)
        
        # Create new stop order
        try:
            stop_order = await order_manager.create_order(
                symbol=symbol,
                quantity=order_quantity,
                order_type=OrderType.STOP,
                stop_price=stop_price,
                auto_submit=True  # Submit immediately
            )
            
            if stop_order:
                # Track in PositionManager
                position_manager.add_orders_to_position(symbol, "stop", [stop_order.order_id])
                
                self.logger.info(f"Created updated stop order {stop_order.order_id} for {symbol} "
                               f"at ${stop_price:.2f} for {order_quantity} shares")
        except Exception as e:
            self.logger.error(f"Failed to create stop order: {e}")
        
        # Create new target order
        try:
            target_order = await order_manager.create_order(
                symbol=symbol,
                quantity=order_quantity,
                order_type=OrderType.LIMIT,
                limit_price=target_price,
                auto_submit=True  # Submit immediately
            )
            
            if target_order:
                # Track in PositionManager
                position_manager.add_orders_to_position(symbol, "target", [target_order.order_id])
                
                self.logger.info(f"Created updated target order {target_order.order_id} for {symbol} "
                               f"at ${target_price:.2f} for {order_quantity} shares")
        except Exception as e:
            self.logger.error(f"Failed to create target order: {e}")
        
        # Update position info with new metrics
        position_manager.update_position_entry(symbol, new_avg_price, new_quantity)
        
        self.logger.info(f"Updated protective orders for {symbol}: "
                        f"New quantity={new_quantity}, New avg=${new_avg_price:.2f}") 