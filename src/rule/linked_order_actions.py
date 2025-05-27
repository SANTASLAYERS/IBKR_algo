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
            from src.event.order import FillEvent
            await self.event_bus.subscribe(FillEvent, self.on_order_fill)
            self._initialized = True
            logger.info("LinkedOrderConclusionManager initialized - monitoring for position conclusions")
    
    async def on_order_fill(self, event):
        """Handle order fill events to detect position conclusions."""
        try:
            # Check if this was a stop or target order that concluded the position
            symbol = event.symbol
            order_id = event.order_id
            
            # Get the order group for this symbol
            group = self.context.get(symbol, {})
            
            # Check if the filled order was a stop or target order
            if (order_id in group.get("stop_orders", []) or 
                order_id in group.get("target_orders", [])):
                
                # Position concluded via stop/target fill - clear context completely
                side = group.get("side", "UNKNOWN")
                if symbol in self.context:
                    del self.context[symbol]
                    logger.info(f"🎯 {side} position concluded for {symbol} - {event.status.value} order {order_id} filled at ${event.fill_price} - context cleared")
                
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
            from src.event.order import FillEvent
            await self.event_bus.subscribe(FillEvent, self.on_order_fill)
            self._initialized = True
            logger.info("CooldownResetManager initialized - monitoring for stop loss fills")
    
    async def on_order_fill(self, event):
        """Handle order fill events to detect stop loss fills and reset cooldowns."""
        try:
            # Check if this was a stop loss order that got filled
            symbol = event.symbol
            order_id = event.order_id
            
            # Get the order group for this symbol from rule engine context
            context = self.rule_engine.context
            group = context.get(symbol, {})
            
            # Check if the filled order was a stop order (stop loss)
            if order_id in group.get("stop_orders", []):
                # Stop loss was hit - reset cooldowns for this symbol's rules
                side = group.get("side", "UNKNOWN")
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


class LinkedOrderManager:
    """Helper class for managing linked orders in context."""
    
    @staticmethod
    def get_order_group(context: Dict[str, Any], symbol: str, side: str) -> Dict[str, Any]:
        """Get or create order group for symbol with side."""
        if symbol not in context:
            # Create fresh context for new position
            context[symbol] = {
                "side": side,
                "main_orders": [],
                "stop_orders": [],
                "target_orders": [],
                "scale_orders": [],
                "status": "active"
            }
            logger.info(f"Created new order context for {symbol} {side} position")
        
        return context[symbol]
    
    @staticmethod
    def add_order(context: Dict[str, Any], symbol: str, order_id: str, order_type: str, side: str):
        """Add an order to the appropriate group with side tracking."""
        group = LinkedOrderManager.get_order_group(context, symbol, side)
        
        if order_type == "main":
            group["main_orders"].append(order_id)
        elif order_type == "stop":
            group["stop_orders"].append(order_id)
        elif order_type == "target":
            group["target_orders"].append(order_id)
        elif order_type == "scale":
            group["scale_orders"].append(order_id)
        
        logger.debug(f"Added {order_type} order {order_id} to {symbol} {side} group")
    
    @staticmethod
    async def find_active_position_side(context: Dict[str, Any], symbol: str) -> Optional[str]:
        """Find the side of active position for a symbol."""
        position_tracker = context.get("position_tracker")
        if not position_tracker:
            return None
            
        positions = await position_tracker.get_positions_for_symbol(symbol)
        active_positions = [p for p in positions if p.status.value == "open"]
        
        if active_positions:
            position = active_positions[0]
            return "BUY" if position.is_long else "SELL"
        return None
    
    @staticmethod
    def get_linked_orders(context: Dict[str, Any], symbol: str, order_type: Optional[str] = None) -> List[str]:
        """Get linked orders for a symbol."""
        group = context.get(symbol, {})
        
        if order_type:
            return group.get(f"{order_type}_orders", [])
        else:
            # Return all order IDs
            all_orders = []
            for key in ["main_orders", "stop_orders", "target_orders", "scale_orders"]:
                all_orders.extend(group.get(key, []))
            return all_orders
    
    @staticmethod
    def remove_order(context: Dict[str, Any], symbol: str, order_id: str):
        """Remove an order from all groups."""
        group = context.get(symbol, {})
        for key in ["main_orders", "stop_orders", "target_orders", "scale_orders"]:
            if order_id in group.get(key, []):
                group[key].remove(order_id)
                logger.debug(f"Removed order {order_id} from {symbol} {key}")
                break
    
    @staticmethod
    def validate_position_consistency(context: Dict[str, Any], symbol: str, side: str) -> bool:
        """Validate that context side matches requested side."""
        group = context.get(symbol, {})
        existing_side = group.get("side")
        
        if existing_side and existing_side != side:
            logger.warning(f"Position side conflict for {symbol}: existing={existing_side}, new={side}")
            return False
        return True


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
        order_manager = context.get("order_manager")
        if not order_manager:
            logger.error("Order manager not found in context")
            return False
        
        # Check for existing position and handle position reversal
        if self.symbol in context and context[self.symbol].get("status") == "active":
            current_side = context[self.symbol]["side"]
            
            if current_side == self.side:
                # Same side signal → IGNORE
                logger.info(f"Ignoring {self.side} signal for {self.symbol} - already in {current_side} position")
                return True
            else:
                # Opposite side signal → EXIT current position, then ENTER new position
                logger.info(f"Reversing position for {self.symbol}: {current_side} → {self.side}")
                success = await self._exit_current_position(context)
                if not success:
                    logger.error(f"Failed to exit current position for {self.symbol}")
                    return False
                # Context is now cleared, proceed with new position creation
        
        try:
            # Calculate actual shares to trade
            actual_shares = await self._calculate_position_size(context)
            if actual_shares is None:
                logger.warning(f"Could not calculate position size for {self.symbol}")
                return False
            
            # Adjust quantity based on side (positive for BUY, negative for SELL)
            actual_quantity = abs(actual_shares) if self.side == "BUY" else -abs(actual_shares)
            
            # Create the main order
            order = await order_manager.create_and_submit_order(
                symbol=self.symbol,
                quantity=actual_quantity,
                order_type=self.order_type,
                limit_price=self.limit_price,
                stop_price=self.stop_price
            )
            
            # Link the order with side tracking
            LinkedOrderManager.add_order(context, self.symbol, order.order_id, self.link_type, self.side)
            
            # Auto-create stop loss and take profit if requested
            if self.auto_create_stops and self.link_type == "main":
                await self._create_protective_orders(context, order, actual_shares)
            
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
        
        # Get current price for calculations
        current_price = self.limit_price or context.get("prices", {}).get(self.symbol)
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
            stop_order = await order_manager.create_order(
                symbol=self.symbol,
                quantity=stop_quantity,
                order_type=OrderType.STOP,
                stop_price=stop_price
            )
            
            LinkedOrderManager.add_order(context, self.symbol, stop_order.order_id, "stop", self.side)
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
            target_order = await order_manager.create_order(
                symbol=self.symbol,
                quantity=target_quantity,
                order_type=OrderType.LIMIT,
                limit_price=target_price
            )
            
            LinkedOrderManager.add_order(context, self.symbol, target_order.order_id, "target", self.side)
            logger.info(f"Auto-created {self.side} take profit {target_order.order_id} at ${target_price:.2f}")


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
            # Find the side of existing position
            side = await LinkedOrderManager.find_active_position_side(context, self.symbol)
            if not side:
                logger.info(f"No active position for {self.symbol} scale-in")
                return False
            
            # Check that context matches the position side
            group = context.get(self.symbol, {})
            context_side = group.get("side")
            if context_side and context_side != side:
                logger.warning(f"Context side mismatch for {self.symbol}: context={context_side}, position={side}")
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
            
            scale_order = await order_manager.create_and_submit_order(
                symbol=self.symbol,
                quantity=scale_quantity,
                order_type=OrderType.MARKET
            )
            
            # Link the scale order
            LinkedOrderManager.add_order(context, self.symbol, scale_order.order_id, "scale", side)
            
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
        
        # Calculate new average price
        current_value = position.quantity * position.entry_price
        new_value = scale_order.quantity * position.current_price
        new_quantity = position.quantity + scale_order.quantity
        new_avg_price = (current_value + new_value) / new_quantity
        
        # Get linked stop and target orders
        stop_orders = LinkedOrderManager.get_linked_orders(context, self.symbol, "stop")
        target_orders = LinkedOrderManager.get_linked_orders(context, self.symbol, "target")
        
        # Update stop orders
        for stop_order_id in stop_orders:
            # Cancel old stop and create new one
            await order_manager.cancel_order(stop_order_id, "Scale-in adjustment")
            LinkedOrderManager.remove_order(context, self.symbol, stop_order_id)
            
            # Create new stop at adjusted price with correct logic for side
            if side == "BUY":  # Long position
                new_stop_price = new_avg_price * 0.97  # 3% stop loss below
                stop_quantity = -abs(new_quantity)  # Sell to close
            else:  # Short position
                new_stop_price = new_avg_price * 1.03  # 3% stop loss above
                stop_quantity = abs(new_quantity)   # Buy to close
                
            new_stop = await order_manager.create_order(
                symbol=self.symbol,
                quantity=stop_quantity,
                order_type=OrderType.STOP,
                stop_price=new_stop_price
            )
            LinkedOrderManager.add_order(context, self.symbol, new_stop.order_id, "stop", side)
            logger.info(f"Updated {side} stop loss to {new_stop_price:.2f} after scale-in")
        
        # Update target orders
        for target_order_id in target_orders:
            # Cancel old target and create new one
            await order_manager.cancel_order(target_order_id, "Scale-in adjustment")
            LinkedOrderManager.remove_order(context, self.symbol, target_order_id)
            
            # Create new target at adjusted price with correct logic for side
            if side == "BUY":  # Long position
                new_target_price = new_avg_price * 1.08  # 8% profit target above
                target_quantity = -abs(new_quantity)  # Sell to close
            else:  # Short position
                new_target_price = new_avg_price * 0.92  # 8% profit target below
                target_quantity = abs(new_quantity)   # Buy to close
                
            new_target = await order_manager.create_order(
                symbol=self.symbol,
                quantity=target_quantity,
                order_type=OrderType.LIMIT,
                limit_price=new_target_price
            )
            LinkedOrderManager.add_order(context, self.symbol, new_target.order_id, "target", side)
            logger.info(f"Updated {side} take profit to {new_target_price:.2f} after scale-in")


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
            # Get all linked orders
            all_orders = LinkedOrderManager.get_linked_orders(context, self.symbol)
            
            # Cancel all orders
            for order_id in all_orders:
                await order_manager.cancel_order(order_id, self.reason)
                LinkedOrderManager.remove_order(context, self.symbol, order_id)
            
            # Close position
            positions = await position_tracker.get_positions_for_symbol(self.symbol)
            for position in positions:
                await position_tracker.close_position(position.position_id, self.reason)
            
            # PROPERLY CLEAR context instead of just marking as closed
            if self.symbol in context:
                del context[self.symbol]
                logger.info(f"Cleared context for {self.symbol} - ready for new position")
            
            logger.info(f"Closed all linked orders and position for {self.symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error closing linked orders for {self.symbol}: {e}")
            return False 