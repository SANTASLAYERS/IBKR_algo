# Rule Engine Specification

## Overview

The Rule Engine is a critical component in the IBKR Trading Framework that enables automated decision-making based on events, market conditions, and system state. It provides a flexible, configurable way to define trading strategies, risk management protocols, and system responses without requiring code changes.

## Core Concepts

### Rules

A rule consists of:
- **Condition**: When the rule should trigger
- **Action**: What the rule should do when triggered
- **Metadata**: Additional information about the rule (priority, cooldown, description, etc.)

### Conditions

Conditions are predicates that evaluate to true or false based on:
- Event data (e.g., price movements, prediction signals)
- Position data (e.g., unrealized P&L, duration)
- System state (e.g., time of day, market conditions)
- Historical data (e.g., moving averages, volatility)

### Actions

Actions are operations performed when a condition is met:
- Create/modify/close positions
- Create/modify/cancel orders
- Adjust risk parameters
- Generate notifications or alerts
- Log information for auditing

## Detailed Component Design

### 1. Rule Definition

```python
@dataclass
class Rule:
    """Represents a configurable rule in the system."""
    
    # Core properties
    rule_id: str
    name: str
    description: str
    enabled: bool = True
    
    # Execution characteristics
    priority: int = 0  # Higher numbers = higher priority
    cooldown_seconds: Optional[float] = None  # Minimum time between executions
    max_executions_per_day: Optional[int] = None  # Daily execution limit
    
    # Runtime tracking
    last_execution_time: Optional[datetime] = None
    execution_count: int = 0
    total_execution_count: int = 0
    
    # Rule logic (will be composed from Condition and Action objects)
    condition: Condition
    action: Action
    
    # Lifecycle hooks
    pre_execution_hook: Optional[Callable] = None
    post_execution_hook: Optional[Callable] = None
    
    # Optional context data (symbol, etc.)
    context: Dict[str, Any] = field(default_factory=dict)
```

### 2. Condition Framework

#### Base Condition

```python
class Condition(ABC):
    """Base abstract class for all conditions."""
    
    @abstractmethod
    async def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate the condition and return True if it is met."""
        pass
    
    def __and__(self, other: 'Condition') -> 'Condition':
        """Combine conditions with AND operator."""
        return AndCondition(self, other)
    
    def __or__(self, other: 'Condition') -> 'Condition':
        """Combine conditions with OR operator."""
        return OrCondition(self, other)
    
    def __invert__(self) -> 'Condition':
        """Negate condition with NOT operator."""
        return NotCondition(self)
```

#### Composite Conditions

```python
class AndCondition(Condition):
    """Represents a logical AND of multiple conditions."""
    
    def __init__(self, *conditions: Condition):
        self.conditions = conditions
    
    async def evaluate(self, context: Dict[str, Any]) -> bool:
        """Return True if all conditions are met."""
        for condition in self.conditions:
            if not await condition.evaluate(context):
                return False
        return True

class OrCondition(Condition):
    """Represents a logical OR of multiple conditions."""
    
    def __init__(self, *conditions: Condition):
        self.conditions = conditions
    
    async def evaluate(self, context: Dict[str, Any]) -> bool:
        """Return True if any condition is met."""
        for condition in self.conditions:
            if await condition.evaluate(context):
                return True
        return False

class NotCondition(Condition):
    """Represents a logical NOT of a condition."""
    
    def __init__(self, condition: Condition):
        self.condition = condition
    
    async def evaluate(self, context: Dict[str, Any]) -> bool:
        """Return True if the condition is not met."""
        return not await self.condition.evaluate(context)
```

#### Specific Condition Types

```python
class EventCondition(Condition):
    """Condition based on an event."""
    
    def __init__(self, event_type: Type[BaseEvent], field_conditions: Dict[str, Any] = None):
        self.event_type = event_type
        self.field_conditions = field_conditions or {}
    
    async def evaluate(self, context: Dict[str, Any]) -> bool:
        """Check if the event meets the criteria."""
        event = context.get("event")
        if not isinstance(event, self.event_type):
            return False
            
        # Check field conditions
        for field, expected_value in self.field_conditions.items():
            if not hasattr(event, field):
                return False
            actual_value = getattr(event, field)
            
            # Handle callable predicates
            if callable(expected_value):
                if not expected_value(actual_value):
                    return False
            # Direct comparison
            elif actual_value != expected_value:
                return False
                
        return True

class PositionCondition(Condition):
    """Condition based on position state."""
    
    def __init__(self, 
                 symbol: Optional[str] = None,
                 position_id: Optional[str] = None,
                 min_unrealized_pnl_pct: Optional[float] = None,
                 max_unrealized_pnl_pct: Optional[float] = None,
                 min_position_duration: Optional[timedelta] = None,
                 status: Optional[PositionStatus] = None):
        self.symbol = symbol
        self.position_id = position_id
        self.min_unrealized_pnl_pct = min_unrealized_pnl_pct
        self.max_unrealized_pnl_pct = max_unrealized_pnl_pct
        self.min_position_duration = min_position_duration
        self.status = status
    
    async def evaluate(self, context: Dict[str, Any]) -> bool:
        """Check if the position meets the criteria."""
        position = context.get("position")
        if not position:
            return False
            
        # Check position properties
        if self.symbol and position.symbol != self.symbol:
            return False
            
        if self.position_id and position.position_id != self.position_id:
            return False
            
        if self.status and position.status != self.status:
            return False
            
        if self.min_unrealized_pnl_pct is not None:
            if position.unrealized_pnl_pct < self.min_unrealized_pnl_pct:
                return False
                
        if self.max_unrealized_pnl_pct is not None:
            if position.unrealized_pnl_pct > self.max_unrealized_pnl_pct:
                return False
                
        if self.min_position_duration is not None:
            if datetime.now() - position.open_time < self.min_position_duration:
                return False
                
        return True

class TimeCondition(Condition):
    """Condition based on time."""
    
    def __init__(self, 
                 start_time: Optional[time] = None, 
                 end_time: Optional[time] = None,
                 days_of_week: Optional[List[int]] = None,  # 0=Monday, 6=Sunday
                 market_hours_only: bool = False):
        self.start_time = start_time
        self.end_time = end_time
        self.days_of_week = days_of_week
        self.market_hours_only = market_hours_only
    
    async def evaluate(self, context: Dict[str, Any]) -> bool:
        """Check if the current time meets the criteria."""
        now = datetime.now()
        
        # Check day of week
        if self.days_of_week and now.weekday() not in self.days_of_week:
            return False
            
        # Check time range
        current_time = now.time()
        if self.start_time and current_time < self.start_time:
            return False
            
        if self.end_time and current_time > self.end_time:
            return False
            
        # Check market hours (simplified)
        if self.market_hours_only:
            # 9:30 AM to 4:00 PM Eastern Time, converted to local time
            # This is a simplified check and would need to be enhanced for accuracy
            market_open = time(9, 30)  # Adjust for timezone difference
            market_close = time(16, 0)  # Adjust for timezone difference
            
            if current_time < market_open or current_time > market_close:
                return False
                
        return True

class MarketCondition(Condition):
    """Condition based on market indicators."""
    
    def __init__(self,
                 symbol: str,
                 min_price: Optional[float] = None,
                 max_price: Optional[float] = None,
                 min_volume: Optional[int] = None,
                 max_volatility: Optional[float] = None,
                 indicator_conditions: Dict[str, Callable[[float], bool]] = None):
        self.symbol = symbol
        self.min_price = min_price
        self.max_price = max_price
        self.min_volume = min_volume
        self.max_volatility = max_volatility
        self.indicator_conditions = indicator_conditions or {}
    
    async def evaluate(self, context: Dict[str, Any]) -> bool:
        """Check if the market conditions meet the criteria."""
        market_data = context.get("market_data", {}).get(self.symbol)
        if not market_data:
            return False
            
        # Check price
        current_price = market_data.get("price")
        if current_price is None:
            return False
            
        if self.min_price is not None and current_price < self.min_price:
            return False
            
        if self.max_price is not None and current_price > self.max_price:
            return False
            
        # Check volume
        current_volume = market_data.get("volume")
        if self.min_volume is not None:
            if not current_volume or current_volume < self.min_volume:
                return False
        
        # Check volatility
        current_volatility = market_data.get("volatility")
        if self.max_volatility is not None:
            if not current_volatility or current_volatility > self.max_volatility:
                return False
        
        # Check indicators
        indicators = market_data.get("indicators", {})
        for indicator_name, condition_func in self.indicator_conditions.items():
            indicator_value = indicators.get(indicator_name)
            if indicator_value is None or not condition_func(indicator_value):
                return False
                
        return True
```

### 3. Action Framework

#### Base Action

```python
class Action(ABC):
    """Base abstract class for all actions."""
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Execute the action and return True if successful."""
        pass
    
    def __add__(self, other: 'Action') -> 'Action':
        """Combine actions to execute sequentially."""
        return SequentialAction(self, other)
```

#### Composite Actions

```python
class SequentialAction(Action):
    """Execute multiple actions in sequence."""
    
    def __init__(self, *actions: Action):
        self.actions = actions
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Execute all actions in sequence."""
        success = True
        for action in self.actions:
            action_success = await action.execute(context)
            success = success and action_success
        return success

class ConditionalAction(Action):
    """Execute an action only if a condition is met."""
    
    def __init__(self, condition: Condition, action: Action):
        self.condition = condition
        self.action = action
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Execute the action if the condition is met."""
        if await self.condition.evaluate(context):
            return await self.action.execute(context)
        return True  # Not executing is considered successful
```

#### Specific Action Types

```python
class CreatePositionAction(Action):
    """Action to create a new position."""
    
    def __init__(self, 
                 symbol: str, 
                 quantity: float,
                 position_type: str = "stock",
                 stop_loss_pct: Optional[float] = None,
                 take_profit_pct: Optional[float] = None,
                 trailing_stop_pct: Optional[float] = None):
        self.symbol = symbol
        self.quantity = quantity
        self.position_type = position_type
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.trailing_stop_pct = trailing_stop_pct
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Create a new position."""
        position_tracker = context.get("position_tracker")
        if not position_tracker:
            logger.error("Position tracker not found in context")
            return False
            
        try:
            if self.position_type == "stock":
                await position_tracker.create_stock_position(
                    symbol=self.symbol,
                    quantity=self.quantity,
                    stop_loss_pct=self.stop_loss_pct,
                    take_profit_pct=self.take_profit_pct,
                    trailing_stop_pct=self.trailing_stop_pct
                )
            return True
        except Exception as e:
            logger.error(f"Error creating position: {e}")
            return False

class ClosePositionAction(Action):
    """Action to close an existing position."""
    
    def __init__(self, 
                 position_id: Optional[str] = None,
                 symbol: Optional[str] = None,
                 reason: str = "Rule triggered"):
        self.position_id = position_id
        self.symbol = symbol
        self.reason = reason
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Close the position."""
        position_tracker = context.get("position_tracker")
        if not position_tracker:
            logger.error("Position tracker not found in context")
            return False
            
        try:
            # Close by ID
            if self.position_id:
                await position_tracker.close_position(
                    position_id=self.position_id,
                    reason=self.reason
                )
                return True
                
            # Close by symbol
            if self.symbol:
                positions = await position_tracker.get_positions_for_symbol(self.symbol)
                for position in positions:
                    await position_tracker.close_position(
                        position_id=position.position_id,
                        reason=self.reason
                    )
                return True
                
            # Close specific position in context
            position = context.get("position")
            if position:
                await position_tracker.close_position(
                    position_id=position.position_id,
                    reason=self.reason
                )
                return True
                
            return False
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return False

class AdjustPositionAction(Action):
    """Action to adjust an existing position."""
    
    def __init__(self,
                 position_id: Optional[str] = None,
                 stop_loss_pct: Optional[float] = None,
                 take_profit_pct: Optional[float] = None,
                 trailing_stop_pct: Optional[float] = None,
                 reason: str = "Rule triggered"):
        self.position_id = position_id
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.reason = reason
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Adjust the position parameters."""
        position_tracker = context.get("position_tracker")
        if not position_tracker:
            logger.error("Position tracker not found in context")
            return False
            
        try:
            # Determine which position to adjust
            position_id = self.position_id
            if not position_id:
                position = context.get("position")
                if position:
                    position_id = position.position_id
                    
            if not position_id:
                logger.error("No position ID provided or found in context")
                return False
                
            # Get current price for percentage calculations
            position = await position_tracker.get_position(position_id)
            if not position:
                logger.error(f"Position not found: {position_id}")
                return False
                
            current_price = position.current_price
            if not current_price:
                logger.error(f"No current price available for position: {position_id}")
                return False
                
            # Calculate absolute values from percentages
            stop_loss = None
            if self.stop_loss_pct is not None:
                if position.is_long:
                    stop_loss = current_price * (1 - self.stop_loss_pct)
                else:
                    stop_loss = current_price * (1 + self.stop_loss_pct)
                    
            take_profit = None
            if self.take_profit_pct is not None:
                if position.is_long:
                    take_profit = current_price * (1 + self.take_profit_pct)
                else:
                    take_profit = current_price * (1 - self.take_profit_pct)
            
            # Apply adjustments
            await position_tracker.adjust_position(
                position_id=position_id,
                stop_loss=stop_loss,
                take_profit=take_profit,
                trailing_stop_pct=self.trailing_stop_pct,
                reason=self.reason
            )
            
            return True
        except Exception as e:
            logger.error(f"Error adjusting position: {e}")
            return False

class CreateOrderAction(Action):
    """Action to create an order."""
    
    def __init__(self,
                 symbol: str,
                 quantity: float,
                 order_type: OrderType = OrderType.MARKET,
                 limit_price: Optional[float] = None,
                 stop_price: Optional[float] = None,
                 time_in_force: TimeInForce = TimeInForce.DAY,
                 auto_submit: bool = True):
        self.symbol = symbol
        self.quantity = quantity
        self.order_type = order_type
        self.limit_price = limit_price
        self.stop_price = stop_price
        self.time_in_force = time_in_force
        self.auto_submit = auto_submit
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Create an order."""
        order_manager = context.get("order_manager")
        if not order_manager:
            logger.error("Order manager not found in context")
            return False
            
        try:
            order = await order_manager.create_order(
                symbol=self.symbol,
                quantity=self.quantity,
                order_type=self.order_type,
                limit_price=self.limit_price,
                stop_price=self.stop_price,
                time_in_force=self.time_in_force,
                auto_submit=self.auto_submit
            )
            
            # Add order to context for potential further actions
            context["created_order"] = order
            return True
        except Exception as e:
            logger.error(f"Error creating order: {e}")
            return False

class CancelOrderAction(Action):
    """Action to cancel an order."""
    
    def __init__(self, 
                 order_id: Optional[str] = None,
                 symbol: Optional[str] = None,
                 reason: str = "Rule triggered"):
        self.order_id = order_id
        self.symbol = symbol
        self.reason = reason
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Cancel the order."""
        order_manager = context.get("order_manager")
        if not order_manager:
            logger.error("Order manager not found in context")
            return False
            
        try:
            # Cancel by ID
            if self.order_id:
                await order_manager.cancel_order(
                    order_id=self.order_id,
                    reason=self.reason
                )
                return True
                
            # Cancel by symbol
            if self.symbol:
                orders = await order_manager.get_orders_for_symbol(self.symbol)
                for order in orders:
                    if order.is_active or order.is_pending:
                        await order_manager.cancel_order(
                            order_id=order.order_id,
                            reason=self.reason
                        )
                return True
                
            # Cancel specific order in context
            order = context.get("order")
            if order:
                await order_manager.cancel_order(
                    order_id=order.order_id,
                    reason=self.reason
                )
                return True
                
            return False
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False

class CreateBracketOrderAction(Action):
    """Action to create a bracket order."""
    
    def __init__(self,
                 symbol: str,
                 quantity: float,
                 entry_price: Optional[float] = None,
                 stop_loss_price: Optional[float] = None,
                 take_profit_price: Optional[float] = None,
                 entry_type: OrderType = OrderType.MARKET,
                 auto_submit: bool = True):
        self.symbol = symbol
        self.quantity = quantity
        self.entry_price = entry_price
        self.stop_loss_price = stop_loss_price
        self.take_profit_price = take_profit_price
        self.entry_type = entry_type
        self.auto_submit = auto_submit
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Create a bracket order."""
        order_manager = context.get("order_manager")
        if not order_manager:
            logger.error("Order manager not found in context")
            return False
            
        try:
            bracket = await order_manager.create_bracket_order(
                symbol=self.symbol,
                quantity=self.quantity,
                entry_price=self.entry_price,
                stop_loss_price=self.stop_loss_price,
                take_profit_price=self.take_profit_price,
                entry_type=self.entry_type,
                auto_submit=self.auto_submit
            )
            
            # Add bracket to context for potential further actions
            context["created_bracket"] = bracket
            return True
        except Exception as e:
            logger.error(f"Error creating bracket order: {e}")
            return False

class LogAction(Action):
    """Action to log information."""
    
    def __init__(self, message: str, level: str = "INFO"):
        self.message = message
        self.level = level.upper()
    
    async def execute(self, context: Dict[str, Any]) -> bool:
        """Log the message."""
        try:
            log_func = getattr(logger, self.level.lower(), logger.info)
            log_func(self.message)
            return True
        except Exception as e:
            logger.error(f"Error logging message: {e}")
            return False
```

### 4. Rule Engine

```python
class RuleEngine:
    """Core engine for evaluating and executing rules."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.rules: Dict[str, Rule] = {}
        self.running = False
        self.context: Dict[str, Any] = {}
        self.evaluation_interval = 1.0  # seconds
        self._evaluation_task = None
        self._locks: Dict[str, asyncio.Lock] = {}
    
    def register_rule(self, rule: Rule) -> bool:
        """Register a rule with the engine."""
        if rule.rule_id in self.rules:
            logger.warning(f"Rule with ID {rule.rule_id} already exists and will be replaced")
            
        self.rules[rule.rule_id] = rule
        self._locks[rule.rule_id] = asyncio.Lock()
        return True
    
    def unregister_rule(self, rule_id: str) -> bool:
        """Unregister a rule from the engine."""
        if rule_id not in self.rules:
            logger.warning(f"Rule with ID {rule_id} not found")
            return False
            
        del self.rules[rule_id]
        if rule_id in self._locks:
            del self._locks[rule_id]
        return True
    
    def enable_rule(self, rule_id: str) -> bool:
        """Enable a rule."""
        if rule_id not in self.rules:
            logger.warning(f"Rule with ID {rule_id} not found")
            return False
            
        self.rules[rule_id].enabled = True
        return True
    
    def disable_rule(self, rule_id: str) -> bool:
        """Disable a rule."""
        if rule_id not in self.rules:
            logger.warning(f"Rule with ID {rule_id} not found")
            return False
            
        self.rules[rule_id].enabled = False
        return True
    
    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Get a rule by ID."""
        return self.rules.get(rule_id)
    
    def get_all_rules(self) -> List[Rule]:
        """Get all registered rules."""
        return list(self.rules.values())
    
    def set_context(self, key: str, value: Any) -> None:
        """Set a value in the shared context."""
        self.context[key] = value
    
    def update_context(self, updates: Dict[str, Any]) -> None:
        """Update multiple values in the shared context."""
        self.context.update(updates)
    
    async def start(self) -> None:
        """Start the rule engine."""
        if self.running:
            logger.warning("Rule engine is already running")
            return
            
        self.running = True
        self._evaluation_task = asyncio.create_task(self._evaluation_loop())
        
        # Subscribe to events
        await self.event_bus.subscribe(BaseEvent, self._handle_event)
        
        logger.info("Rule engine started")
    
    async def stop(self) -> None:
        """Stop the rule engine."""
        if not self.running:
            logger.warning("Rule engine is not running")
            return
            
        self.running = False
        
        # Cancel evaluation task
        if self._evaluation_task:
            self._evaluation_task.cancel()
            try:
                await self._evaluation_task
            except asyncio.CancelledError:
                pass
            
        # Unsubscribe from events
        await self.event_bus.unsubscribe(BaseEvent, self._handle_event)
        
        logger.info("Rule engine stopped")
    
    async def _evaluation_loop(self) -> None:
        """Background task for periodic rule evaluation."""
        while self.running:
            try:
                await self._evaluate_all_rules()
            except Exception as e:
                logger.error(f"Error in rule evaluation loop: {e}")
                
            await asyncio.sleep(self.evaluation_interval)
    
    async def _evaluate_all_rules(self) -> None:
        """Evaluate all rules against the current context."""
        # Sort rules by priority (highest first)
        sorted_rules = sorted(
            [rule for rule in self.rules.values() if rule.enabled],
            key=lambda r: r.priority,
            reverse=True
        )
        
        for rule in sorted_rules:
            # Skip rules that are on cooldown
            if rule.cooldown_seconds and rule.last_execution_time:
                cooldown_expires = rule.last_execution_time + timedelta(seconds=rule.cooldown_seconds)
                if datetime.now() < cooldown_expires:
                    continue
            
            # Skip rules that have reached their daily execution limit
            if rule.max_executions_per_day and rule.execution_count >= rule.max_executions_per_day:
                continue
                
            # Create rule-specific context
            rule_context = self.context.copy()
            rule_context.update(rule.context)
            
            # Acquire lock for this rule
            async with self._locks[rule.rule_id]:
                try:
                    # Pre-execution hook
                    if rule.pre_execution_hook:
                        rule.pre_execution_hook(rule, rule_context)
                    
                    # Evaluate condition
                    if await rule.condition.evaluate(rule_context):
                        # Execute action
                        success = await rule.action.execute(rule_context)
                        
                        # Update rule state
                        if success:
                            rule.last_execution_time = datetime.now()
                            rule.execution_count += 1
                            rule.total_execution_count += 1
                            
                            # Post-execution hook
                            if rule.post_execution_hook:
                                rule.post_execution_hook(rule, rule_context, success)
                except Exception as e:
                    logger.error(f"Error evaluating rule {rule.rule_id}: {e}")
    
    async def _handle_event(self, event: BaseEvent) -> None:
        """Handle an incoming event."""
        # Add event to context
        self.context["event"] = event
        
        # Clone context for event handling
        event_context = self.context.copy()
        
        # Evaluate each rule with the event
        for rule_id, rule in self.rules.items():
            if not rule.enabled:
                continue
                
            # Skip rules that are on cooldown
            if rule.cooldown_seconds and rule.last_execution_time:
                cooldown_expires = rule.last_execution_time + timedelta(seconds=rule.cooldown_seconds)
                if datetime.now() < cooldown_expires:
                    continue
            
            # Skip rules that have reached their daily execution limit
            if rule.max_executions_per_day and rule.execution_count >= rule.max_executions_per_day:
                continue
                
            # Create rule-specific context
            rule_context = event_context.copy()
            rule_context.update(rule.context)
            
            # Acquire lock for this rule
            async with self._locks[rule_id]:
                try:
                    # Pre-execution hook
                    if rule.pre_execution_hook:
                        rule.pre_execution_hook(rule, rule_context)
                    
                    # Evaluate condition
                    if await rule.condition.evaluate(rule_context):
                        # Execute action
                        success = await rule.action.execute(rule_context)
                        
                        # Update rule state
                        if success:
                            rule.last_execution_time = datetime.now()
                            rule.execution_count += 1
                            rule.total_execution_count += 1
                            
                            # Post-execution hook
                            if rule.post_execution_hook:
                                rule.post_execution_hook(rule, rule_context, success)
                except Exception as e:
                    logger.error(f"Error handling event for rule {rule_id}: {e}")
```

## Context System

The Context system is a fundamental part of the Rule Engine that provides a shared data space for conditions and actions. It enables communication between different components and maintains state during rule execution.

### Context Overview

The context is a dictionary (`Dict[str, Any]`) that contains:
- **System Components**: References to managers (order_manager, position_tracker, etc.)
- **Current State**: Active positions, orders, market data
- **Event Data**: The current event being processed
- **Custom Data**: Any additional data needed by rules

### Context Hierarchy

1. **Global Context** (`rule_engine.context`)
   - Persistent throughout the application lifetime
   - Contains system components and shared state
   - Updated via `set_context()` and `update_context()`

2. **Rule Context** (`rule.context`)
   - Rule-specific data that supplements global context
   - Merged with global context during evaluation

3. **Execution Context** (`rule_context`)
   - Created for each rule evaluation
   - Copy of global context + rule context + event data
   - Isolated to prevent side effects between rules

### Position Management via PositionTracker

The PositionTracker is the single source of truth for all position and order information. Instead of storing position data directly in the context, the system uses PositionTracker:

```python
# Position object contains all trading state
position = Position(
    symbol="AAPL",
    side="BUY",                       # Position side (BUY/SELL)
    quantity=100,                     # Total position size
    entry_price=150.50,               # Average entry price
    main_order_ids=["order_id_1"],    # Entry order IDs
    stop_order_ids=["order_id_2"],    # Stop loss order IDs
    target_order_ids=["order_id_3"],  # Take profit order IDs
    doubledown_order_ids=["order_id_4"], # Double down order IDs
    atr_stop_multiplier=6.5,          # ATR multiplier for stops
    atr_target_multiplier=3.0,        # ATR multiplier for targets
    status=PositionStatus.OPEN        # Position status
)
```

### Context Usage in Conditions

Conditions access context to make decisions:

```python
class EventCondition(Condition):
    async def evaluate(self, context: Dict[str, Any]) -> bool:
        event = context.get("event")  # Access current event
        # ... evaluation logic
        
class PositionCondition(Condition):
    async def evaluate(self, context: Dict[str, Any]) -> bool:
        position_tracker = context.get("position_tracker")
        if position_tracker:
            positions = await position_tracker.get_positions_for_symbol(self.symbol)
            # ... evaluation logic
```

### Context Usage in Actions

Actions use context to access system components:

```python
class CreateOrderAction(Action):
    async def execute(self, context: Dict[str, Any]) -> bool:
        order_manager = context.get("order_manager")  # Get system component
        position_tracker = context.get("position_tracker")
        
        # Create or update position in PositionTracker
        position = await position_tracker.create_position(
            symbol=self.symbol,
            side=self.side,
            # ... other parameters
        )
        
        # Create order...
        order = await order_manager.create_order(...)
        
        # Update position with order ID
        position.main_order_ids.append(order.order_id)
        
        return True
```

### Context Best Practices

1. **Component Access**
   ```python
   # Always check if component exists
   order_manager = context.get("order_manager")
   if not order_manager:
       logger.error("Order manager not found in context")
       return False
   ```

2. **Position Data Management**
   ```python
   # Use PositionTracker for all position data
   position_tracker = context.get("position_tracker")
   positions = await position_tracker.get_positions_for_symbol(symbol)
   
   # Don't store position data directly in context
   # BAD: context[symbol] = {"side": "BUY", ...}
   # GOOD: Use PositionTracker methods
   ```

3. **Context Isolation**
   ```python
   # Don't modify global context directly in rules
   # BAD: self.context["key"] = value
   # GOOD: context["key"] = value  # Modifies execution context only
   ```

4. **Position Lifecycle**
   ```python
   # Position cleanup is handled by PositionTracker
   await position_tracker.close_position(position_id, "Stop loss hit")
   # Position status automatically updated to CLOSED
   ```

### PositionTracker as Single Source of Truth

The PositionTracker provides complete trade management:

| Feature | PositionTracker |
|---------|-----------------|
| **Scope** | Application-wide |
| **Persistence** | Maintains state across rule executions |
| **Purpose** | Complete position and order management |
| **Data** | All position details, order IDs, risk parameters |
| **Lifecycle** | Clear status tracking (OPEN → CLOSED) |

The PositionTracker eliminates the need for separate context-based position tracking, providing a cleaner and more maintainable system.

## Use Cases and Examples

### Example 1: Trading based on API Prediction Signal

```python
# Create a rule to open a position when a high-confidence BUY signal is received
prediction_entry_rule = Rule(
    rule_id="prediction_entry",
    name="Prediction Signal Entry",
    description="Open a long position when a high-confidence BUY signal is received",
    priority=100,
    condition=EventCondition(
        event_type=PredictionSignalEvent,
        field_conditions={
            "signal": "BUY",
            "confidence": lambda c: c >= 0.85
        }
    ),
    action=CreatePositionAction(
        symbol=lambda ctx: ctx["event"].symbol,
        quantity=lambda ctx: calculate_position_size(ctx["event"].symbol, ctx["account_value"]),
        stop_loss_pct=0.03,
        take_profit_pct=0.09
    ),
    cooldown_seconds=300  # 5 minutes cooldown between entries
)

rule_engine.register_rule(prediction_entry_rule)
```

### Example 2: Trailing Stop Adjustment

```python
# Create a rule to adjust stop loss when position is profitable
trailing_stop_rule = Rule(
    rule_id="trailing_stop",
    name="Trailing Stop Adjustment",
    description="Adjust stop loss as position becomes profitable",
    priority=80,
    condition=PositionCondition(
        min_unrealized_pnl_pct=0.05  # Position is at least 5% profitable
    ),
    action=AdjustPositionAction(
        trailing_stop_pct=0.03,  # 3% trailing stop
        reason="Trailing stop adjustment based on profit"
    ),
    cooldown_seconds=60  # Check once per minute
)

rule_engine.register_rule(trailing_stop_rule)
```

### Example 3: Time-Based Position Closure

```python
# Create a rule to close positions at end of day
end_of_day_closure = Rule(
    rule_id="eod_closure",
    name="End of Day Position Closure",
    description="Close all positions before market close",
    priority=200,  # High priority to ensure execution
    condition=TimeCondition(
        start_time=time(15, 45),  # 3:45 PM
        end_time=time(15, 55),    # 3:55 PM
        market_hours_only=True,
        days_of_week=[0, 1, 2, 3, 4]  # Monday-Friday
    ),
    action=ClosePositionAction(
        reason="End of day position closure"
    ),
    # No cooldown, but will only execute once due to time condition
)

rule_engine.register_rule(end_of_day_closure)
```

### Example 4: Composite Condition and Action

```python
# Rule with combined conditions and actions
combined_rule = Rule(
    rule_id="combined_rule",
    name="Combined Profit Taking and Protection",
    description="Take profit on high earnings but also protect with trailing stop",
    priority=90,
    condition=(
        PositionCondition(min_unrealized_pnl_pct=0.15) &  # Position up 15%
        MarketCondition(
            symbol=lambda ctx: ctx["position"].symbol,
            indicator_conditions={"rsi": lambda rsi: rsi > 70}  # Overbought condition
        )
    ),
    action=(
        # First take partial profit
        ClosePositionAction(
            reason="Partial profit taking on overbought condition"
        ) +
        # Then adjust stop for remaining position
        AdjustPositionAction(
            trailing_stop_pct=0.02,
            reason="Tightened trailing stop after partial profit take"
        )
    )
)

rule_engine.register_rule(combined_rule)
```

## Integration with Existing Components

### Event System Integration

```python
# In system startup code
event_bus = EventBus()
rule_engine = RuleEngine(event_bus)

# Add position and order managers to rule engine context
rule_engine.set_context("position_tracker", position_tracker)
rule_engine.set_context("order_manager", order_manager)

# Start the rule engine
await rule_engine.start()
```

### Position Management Integration

```python
# When a position is updated, update the rule engine context
async def handle_position_update(event: PositionUpdateEvent):
    # Get the updated position
    position = await position_tracker.get_position(event.position_id)
    
    # Update rule engine context
    rule_engine.set_context("position", position)
    
    # Update market data context for the symbol
    if not "market_data" in rule_engine.context:
        rule_engine.set_context("market_data", {})
        
    # Ensure the symbol entry exists
    if not position.symbol in rule_engine.context["market_data"]:
        rule_engine.context["market_data"][position.symbol] = {}
        
    # Update the price
    rule_engine.context["market_data"][position.symbol]["price"] = event.current_price

# Subscribe to position update events
await event_bus.subscribe(PositionUpdateEvent, handle_position_update)
```

### Order Management Integration

```python
# When an order is updated, update the rule engine context
async def handle_order_update(event: OrderEvent):
    # Get the updated order
    order = await order_manager.get_order(event.order_id)
    
    # Update rule engine context
    rule_engine.set_context("order", order)

# Subscribe to order update events
await event_bus.subscribe(OrderEvent, handle_order_update)
```

## Testing Approach

Testing for the Rule Engine will include:

1. **Unit Tests**
   - Test individual conditions and actions
   - Test rule evaluation and execution
   - Test rule engine core functionality (registration, enablement, cooldown, etc.)

2. **Integration Tests**
   - Test rule engine with event system
   - Test rule engine with position management
   - Test rule engine with order management

3. **Scenario Tests**
   - Test predefined trading scenarios
   - Test rule prioritization and conflict resolution
   - Test time-based rules

## Performance Considerations

To ensure efficient operation, especially with many rules:

1. Use fast condition evaluation for high-frequency events
2. Prioritize rules to short-circuit unnecessary evaluations
3. Use cooldowns to prevent excessive rule triggering
4. Implement sampling or throttling for high-volume event sources
5. Consider distributed rule evaluation for large-scale implementations

## Future Enhancements

1. **User Interface for Rule Configuration**
   - Web-based rule builder
   - Visual rule designer
   - Rule template library

2. **Rule Analytics**
   - Execution statistics and performance metrics
   - Rule effectiveness analysis
   - Automatic rule optimization

3. **Persistence and Configuration**
   - Load/save rules from/to database or files
   - Import/export rule configurations
   - Version control for rule sets

4. **Advanced Rule Capabilities**
   - Machine learning integration for condition evaluation
   - Natural language processing for rule definition
   - Automated rule generation based on historical data

5. **Multi-Asset Class Support**
   - Extend for options trading
   - Extend for futures trading
   - Support for multi-asset strategies

## Conclusion

The Rule Engine provides a flexible, powerful framework for automating trading strategies, risk management, and system behaviors. By separating conditions from actions and providing a hierarchical composition system, it enables complex rules to be created without modifying code. The integration with the existing event, position, and order components ensures a cohesive, maintainable system that can evolve with changing requirements.