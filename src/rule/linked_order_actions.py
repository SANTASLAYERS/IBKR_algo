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
            
            # Get the order group for this symbol
            group = self.context.get(symbol, {})
            
            # Check if the filled order was a stop or target order
            if (order_id in group.get("stop_orders", []) or 
                order_id in group.get("target_orders", [])):
                
                # Position concluded via stop/target fill - delete context completely
                side = group.get("side", "UNKNOWN")
                if symbol in self.context:
                    del self.context[symbol]
                    logger.info(f"🎯 {side} position concluded for {symbol} - {event.status.value if hasattr(event, 'status') else 'fill'} order {order_id} filled at ${event.fill_price} - context cleared")
                
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
                "doubledown_orders": [],  # NEW: Centralized list for all double down orders
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
        elif order_type.startswith("doubledown"):  # NEW: Handle any doubledown level
            group["doubledown_orders"].append(order_id)
        else:
            logger.warning(f"Unknown order type '{order_type}' for {symbol}")
        
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
            if order_type == "doubledown":  # NEW: Handle doubledown order type
                return group.get("doubledown_orders", [])
            else:
                return group.get(f"{order_type}_orders", [])
        else:
            # Return all order IDs
            all_orders = []
            for key in ["main_orders", "stop_orders", "target_orders", "scale_orders", "doubledown_orders"]:  # NEW: Include doubledown_orders
                all_orders.extend(group.get(key, []))
            return all_orders
    
    @staticmethod
    def remove_order(context: Dict[str, Any], symbol: str, order_id: str):
        """Remove an order from all groups."""
        group = context.get(symbol, {})
        for key in ["main_orders", "stop_orders", "target_orders", "scale_orders", "doubledown_orders"]:  # NEW: Include doubledown_orders
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
        if self.symbol in context:
            status = context[self.symbol].get("status", "active")
            
            if status == "closed":
                # Clean up closed context before creating new position
                del context[self.symbol]
                logger.info(f"Cleaned up closed context for {self.symbol}")
            elif status == "active":
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
            
            # Store quantity and ATR multipliers in context for double down calculation
            if self.symbol in context:
                context[self.symbol]["quantity"] = actual_quantity
                if self.atr_stop_multiplier is not None:
                    context[self.symbol]["atr_stop_multiplier"] = self.atr_stop_multiplier
                if self.atr_target_multiplier is not None:
                    context[self.symbol]["atr_target_multiplier"] = self.atr_target_multiplier
            
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
                # For position reversal, completely remove the old context
                # so the new position can create a fresh context with the correct side
                if self.symbol in context:
                    del context[self.symbol]
                    logger.info(f"Removed old context for {self.symbol} position reversal")
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
    
    async def _create_double_down_orders(self, context: Dict[str, Any], actual_shares):
        """Create double down limit orders automatically after entry."""
        try:
            # Create double down action
            double_down_action = LinkedDoubleDownAction(
                symbol=self.symbol,
                distance_to_stop_multiplier=0.5,  # Halfway to stop loss
                quantity_multiplier=1.0,          # Same size as original position
                level_name="doubledown1"          # First double down level
            )
            
            # Execute double down creation
            success = await double_down_action.execute(context)
            if success:
                logger.info(f"Auto-created double down order for {self.symbol}")
            else:
                logger.warning(f"Failed to create double down order for {self.symbol}")
                
        except Exception as e:
            logger.error(f"Error creating double down orders for {self.symbol}: {e}")


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
            
            # Delete context completely for clean slate
            if self.symbol in context:
                del context[self.symbol]
                logger.info(f"Cleared context for {self.symbol}")
            
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
            # Check if we have an active position for this symbol
            if self.symbol not in context or context[self.symbol].get("status") != "active":
                logger.info(f"No active position for {self.symbol} - cannot create double down order")
                return False
            
            position_info = context[self.symbol]
            side = position_info.get("side")
            
            # Double down works for both BUY and SELL positions
            if side not in ["BUY", "SELL"]:
                logger.error(f"Invalid position side for {self.symbol}: {side}")
                return False
            
            # Check if this double down level already exists
            existing_orders = LinkedOrderManager.get_linked_orders(context, self.symbol, self.level_name)
            if existing_orders:
                logger.info(f"Double down level '{self.level_name}' already exists for {self.symbol}")
                return True
            
            # Get the main order info to calculate quantities and prices
            main_orders = LinkedOrderManager.get_linked_orders(context, self.symbol, "main")
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
                limit_price=double_down_price
            )
            
            # Link the double down order
            LinkedOrderManager.add_order(context, self.symbol, double_down_order.order_id, self.level_name, side)
            
            logger.info(f"Created {side} double down order '{self.level_name}' for {self.symbol}: "
                       f"{double_down_quantity} shares @ ${double_down_price:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating double down order for {self.symbol}: {e}")
            return False
    
    async def _calculate_double_down_parameters(self, context: Dict[str, Any]) -> tuple[Optional[float], Optional[int]]:
        """Calculate the price and quantity for the double down order."""
        try:
            # Get current price
            price_service = context.get("price_service")
            if not price_service:
                logger.error("Price service not available")
                return None, None
                
            current_price = await price_service.get_price(self.symbol)
            if not current_price:
                logger.error(f"Could not get current price for {self.symbol}")
                return None, None
            
            # Get existing stop orders to calculate stop distance
            stop_orders = LinkedOrderManager.get_linked_orders(context, self.symbol, "stop")
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
            position_info = context[self.symbol]
            side = position_info.get("side")
            
            # Calculate double down price based on position side
            double_down_distance = stop_distance * self.distance_to_stop_multiplier
            
            if side == "BUY":
                # For long positions: place limit buy below current price
                double_down_price = current_price - double_down_distance
            else:  # SELL
                # For short positions: place limit sell above current price
                double_down_price = current_price + double_down_distance
            
            # Calculate double down quantity based on original position size
            original_quantity = abs(position_info.get("quantity", 0))
            
            if original_quantity == 0:
                # Fallback: calculate from allocation if available
                allocation = position_info.get("allocation", 10000)  # Default $10K
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
            # Try to get ATR-based calculation first
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
                        # Use same multiplier as main strategy (6.0)
                        stop_distance = atr_value * 6.0
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
            
            # Check if this symbol has an active position
            if symbol not in self.context or self.context[symbol].get("status") != "active":
                return
            
            position_info = self.context[symbol]
            
            # Check if this is a double down order fill
            if order_id not in position_info.get("doubledown_orders", []):
                return
            
            self.logger.info(f"Double down order {order_id} filled for {symbol} - updating protective orders")
            
            # Get current position data
            position_tracker = self.context.get("position_tracker")
            if not position_tracker:
                self.logger.error("Position tracker not found")
                return
            
            positions = await position_tracker.get_positions_for_symbol(symbol)
            if not positions:
                self.logger.error(f"No position found for {symbol}")
                return
            
            position = positions[0]
            
            # Calculate new position metrics after double down
            old_quantity = position.quantity
            dd_quantity = event.quantity
            new_quantity = old_quantity + dd_quantity
            
            # Calculate new average price
            old_value = abs(old_quantity) * position.entry_price
            dd_value = abs(dd_quantity) * event.fill_price
            new_avg_price = (old_value + dd_value) / abs(new_quantity)
            
            # Update protective orders
            await self._update_protective_orders(
                symbol=symbol,
                new_quantity=new_quantity,
                new_avg_price=new_avg_price,
                position_info=position_info,
                is_long=position.is_long
            )
            
        except Exception as e:
            self.logger.error(f"Error handling double down fill: {e}", exc_info=True)
    
    async def _update_protective_orders(self, symbol: str, new_quantity: float, 
                                       new_avg_price: float, position_info: Dict[str, Any],
                                       is_long: bool):
        """Cancel old and create new protective orders with updated quantities."""
        order_manager = self.context.get("order_manager")
        indicator_manager = self.context.get("indicator_manager")
        
        if not order_manager or not indicator_manager:
            self.logger.error("Required managers not found")
            return
        
        # Get ATR for stop/target calculations
        atr = await indicator_manager.get_atr(symbol, "10s")
        if not atr:
            self.logger.error(f"Could not get ATR for {symbol}")
            return
        
        # Get ATR multipliers from context (default to 6x stop, 3x target)
        stop_multiplier = position_info.get("atr_stop_multiplier", 6.0)
        target_multiplier = position_info.get("atr_target_multiplier", 3.0)
        
        # Cancel existing stop and target orders
        for stop_id in position_info.get("stop_orders", []):
            await order_manager.cancel_order(stop_id, "Double down fill - updating protective orders")
        
        for target_id in position_info.get("target_orders", []):
            await order_manager.cancel_order(target_id, "Double down fill - updating protective orders")
        
        # Clear old order lists
        position_info["stop_orders"] = []
        position_info["target_orders"] = []
        
        # Calculate new stop and target prices
        if is_long:
            stop_price = new_avg_price - (atr * stop_multiplier)
            target_price = new_avg_price + (atr * target_multiplier)
            # For long positions, stop/target orders are sell orders (negative quantity)
            order_quantity = -abs(new_quantity)
        else:
            stop_price = new_avg_price + (atr * stop_multiplier)
            target_price = new_avg_price - (atr * target_multiplier)
            # For short positions, stop/target orders are buy orders (positive quantity)
            order_quantity = abs(new_quantity)
        
        # Create new stop order
        stop_order = await order_manager.create_order(
            symbol=symbol,
            quantity=order_quantity,
            order_type=OrderType.STOP,
            stop_price=stop_price,
            time_in_force="GTC"
        )
        
        if stop_order:
            position_info["stop_orders"].append(stop_order.order_id)
            self.logger.info(f"Created updated stop order {stop_order.order_id} for {symbol} "
                           f"at ${stop_price:.2f} for {order_quantity} shares")
        
        # Create new target order
        target_order = await order_manager.create_order(
            symbol=symbol,
            quantity=order_quantity,
            order_type=OrderType.LIMIT,
            limit_price=target_price,
            time_in_force="GTC"
        )
        
        if target_order:
            position_info["target_orders"].append(target_order.order_id)
            self.logger.info(f"Created updated target order {target_order.order_id} for {symbol} "
                           f"at ${target_price:.2f} for {order_quantity} shares")
        
        # Update position info with new metrics
        position_info["quantity"] = new_quantity
        position_info["entry_price"] = new_avg_price
        
        self.logger.info(f"Updated protective orders for {symbol}: "
                        f"New quantity={new_quantity}, New avg=${new_avg_price:.2f}") 