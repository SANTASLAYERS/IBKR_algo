# Rule Engine Documentation

## Overview

The Rule Engine is a powerful component of the IBKR Trading Framework that enables event-driven and time-based automated trading decisions. It provides a flexible, configurable way to define trading strategies, risk management protocols, and automated responses without requiring code changes.

**🆕 Recent Enhancement**: Full BUY/SELL side support with automatic order linking, context reset, and short position management.

## Core Components

### Rule

The `Rule` class serves as the fundamental building block of the Rule Engine:

```python
@dataclass
class Rule:
    """Represents a configurable rule in the system."""
    rule_id: str                     # Unique identifier
    name: str                        # Name for human readability
    description: str                 # Detailed description
    condition: Condition             # When the rule should trigger
    action: Action                   # What the rule should do
    enabled: bool = True             # Whether the rule is active
    priority: int = 0                # Higher numbers = higher priority
    cooldown_seconds: Optional[float] = None  # Minimum time between executions
    # Additional metadata...
```

Each rule combines a condition (when to trigger) with an action (what to do) and includes metadata for controlling execution behavior.

### Conditions

Conditions determine when rules should trigger:

1. **Base Class**: All conditions inherit from the abstract `Condition` class:
   ```python
   class Condition(ABC):
       @abstractmethod
       async def evaluate(self, context: Dict[str, Any]) -> bool:
           """Evaluate the condition and return True if it is met."""
           pass
   ```

2. **Event-Based Conditions**: Trigger on specific events
   ```python
   # Trigger on price updates for AAPL above $150
   condition = EventCondition(
       event_type=PriceEvent,
       field_conditions={
           "symbol": "AAPL",
           "price": lambda p: p > 150.0
       }
   )
   ```

3. **State-Based Conditions**: Trigger based on position or market state
   ```python
   # Trigger when a position is profitable
   condition = PositionCondition(min_unrealized_pnl_pct=0.05)
   ```

4. **Time-Based Conditions**: Trigger at specific times
   ```python
   # Trigger during market hours
   condition = TimeCondition(
       start_time=time(9, 30),
       end_time=time(16, 0),
       days_of_week=[0, 1, 2, 3, 4]  # Monday to Friday
   )
   ```

5. **Composite Conditions**: Combine conditions with logical operators
   ```python
   # AND condition
   condition = condition1 & condition2
   
   # OR condition
   condition = condition1 | condition2
   
   # NOT condition
   condition = ~condition1
   ```

### Actions

Actions define what happens when a rule triggers:

1. **Base Class**: All actions inherit from the abstract `Action` class:
   ```python
   class Action(ABC):
       @abstractmethod
       async def execute(self, context: Dict[str, Any]) -> bool:
           """Execute the action and return True if successful."""
           pass
   ```

2. **🆕 Linked Order Actions**: Enhanced actions with automatic order linking and BUY/SELL side support
   ```python
   # Long position entry with automatic stop/target creation
   action = LinkedCreateOrderAction(
       symbol="AAPL",
       quantity=100,
       side="BUY",                    # Explicit side for position tracking
       order_type=OrderType.MARKET,
       auto_create_stops=True,        # Auto-create stop loss and take profit
       stop_loss_pct=0.03,
       take_profit_pct=0.08
   )
   
   # Short position entry with correctly positioned stops/targets
   action = LinkedCreateOrderAction(
       symbol="AAPL", 
       quantity=100,
       side="SELL",                   # Explicit side for short position
       auto_create_stops=True,        # Stop ABOVE entry, target BELOW entry
       stop_loss_pct=0.03,
       take_profit_pct=0.08
   )
   
   # Scale-in with automatic stop/target adjustment
   action = LinkedScaleInAction(
       symbol="AAPL",
       scale_quantity=50,
       trigger_profit_pct=0.02        # Only scale if 2%+ profitable
   )
   
   # Close all orders and position for symbol
   action = LinkedCloseAllAction(
       symbol="AAPL",
       reason="Risk management exit"
   )
   ```

3. **Standard Order Actions**: Basic order management
   ```python
   # Create a market order
   action = CreateOrderAction(
       symbol="AAPL",
       quantity=100,
       order_type=OrderType.MARKET
   )
   
   # Create a bracket order (entry + stop loss + take profit)
   action = CreateBracketOrderAction(
       symbol="AAPL",
       quantity=100,
       entry_price=150.0,
       stop_loss_price=145.0,
       take_profit_price=160.0
   )
   ```

4. **Position Actions**: Manage trading positions
   ```python
   # Create a new position
   action = CreatePositionAction(
       symbol="AAPL",
       quantity=100,
       stop_loss_pct=0.03,
       take_profit_pct=0.09
   )
   
   # Close an existing position
   action = ClosePositionAction(reason="Take profit")
   
   # Adjust position parameters
   action = AdjustPositionAction(trailing_stop_pct=0.02)
   ```

5. **Composite Actions**: Combine actions
   ```python
   # Sequential execution of actions
   action = action1 + action2
   
   # Conditional action execution
   action = ConditionalAction(condition, action1)
   ```

### 🆕 Automatic Context Management

The system now includes automatic context management:

- **Side Tracking**: Context stores position side ("BUY" or "SELL") to prevent order mixing
- **Order Linking**: Related orders (main, stop, target, scale) are automatically linked by symbol
- **Automatic Reset**: Context is automatically cleaned when positions conclude via stops/targets
- **Event-Driven Reset**: Uses `LinkedOrderConclusionManager` to detect position conclusions

### Rule Engine

The `RuleEngine` class manages the lifecycle of rules:

```python
class RuleEngine:
    """Core engine for evaluating and executing rules."""
    
    # Key methods
    def register_rule(self, rule: Rule) -> bool: ...
    def unregister_rule(self, rule_id: str) -> bool: ...
    def enable_rule(self, rule_id: str) -> bool: ...
    def disable_rule(self, rule_id: str) -> bool: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
```

The Rule Engine provides:
- Rule registration and management
- Context sharing between rules
- Event-based rule triggering
- Periodic rule evaluation
- Rule prioritization
- Execution control (cooldowns, limits)

## Usage Examples

### 🆕 Long and Short Position Management

```python
# Long position entry rule
buy_condition = EventCondition(
    event_type=PredictionSignalEvent,
    field_conditions={
        "signal": "BUY",
        "symbol": "AAPL",
        "confidence": lambda c: c > 0.85
    }
)

buy_action = LinkedCreateOrderAction(
    symbol="AAPL",
    quantity=100,
    side="BUY",                      # Long position
    order_type=OrderType.MARKET,
    auto_create_stops=True,
    stop_loss_pct=0.03,
    take_profit_pct=0.08
)

buy_rule = Rule(
    rule_id="aapl_buy_rule",
    name="AAPL Long Entry",
    description="Enter AAPL long position on high confidence BUY signal",
    condition=buy_condition,
    action=buy_action,
    priority=100,
    cooldown_seconds=300
)

# Short position entry rule  
short_condition = EventCondition(
    event_type=PredictionSignalEvent,
    field_conditions={
        "signal": "SHORT",
        "symbol": "AAPL", 
        "confidence": lambda c: c > 0.85
    }
)

short_action = LinkedCreateOrderAction(
    symbol="AAPL",
    quantity=100,
    side="SELL",                     # Short position
    order_type=OrderType.MARKET,
    auto_create_stops=True,          # Stop ABOVE entry, target BELOW entry
    stop_loss_pct=0.03,
    take_profit_pct=0.08
)

short_rule = Rule(
    rule_id="aapl_short_rule", 
    name="AAPL Short Entry",
    description="Enter AAPL short position on high confidence SHORT signal",
    condition=short_condition,
    action=short_action,
    priority=100,
    cooldown_seconds=300
)

# Scale-in rule (works for both long and short)
scalein_condition = EventCondition(
    event_type=PredictionSignalEvent,
    field_conditions={
        "signal": lambda s: s in ["BUY", "SHORT"],  # Matches existing position side
        "symbol": "AAPL",
        "confidence": lambda c: c > 0.90            # Higher threshold for scale-in
    }
)

scalein_action = LinkedScaleInAction(
    symbol="AAPL",
    scale_quantity=50,                              # Half the original size
    trigger_profit_pct=0.02                         # Only if 2%+ profitable
)

scalein_rule = Rule(
    rule_id="aapl_scalein_rule",
    name="AAPL Scale-In",
    description="Scale into existing AAPL position on very high confidence",
    condition=scalein_condition,
    action=scalein_action,
    priority=90,                                    # Lower than entry
    cooldown_seconds=600                            # Longer cooldown
)

# Register all rules
rule_engine.register_rule(buy_rule)
rule_engine.register_rule(short_rule)
rule_engine.register_rule(scalein_rule)
```

### Trading Based on Prediction Signal

```python
# Create a rule to buy when a prediction signal arrives
condition = EventCondition(
    event_type=PredictionSignalEvent,
    field_conditions={
        "signal": "BUY",
        "confidence": lambda c: c > 0.8
    }
)

action = CreatePositionAction(
    symbol=lambda ctx: ctx["event"].symbol,
    quantity=100,
    stop_loss_pct=0.03,
    take_profit_pct=0.09
)

rule = Rule(
    rule_id="prediction_entry",
    name="Enter on Prediction Signal",
    description="Enter a position when a high-confidence buy signal is received",
    condition=condition,
    action=action,
    priority=100
)

# Register the rule
rule_engine.register_rule(rule)
```

### Trailing Stop Management

```python
# Create a rule to implement trailing stops for profitable positions
condition = PositionCondition(min_unrealized_pnl_pct=0.05)

action = AdjustPositionAction(
    trailing_stop_pct=0.02,
    reason="Trailing stop adjustment based on profit"
)

rule = Rule(
    rule_id="trailing_stop_adjustment",
    name="Trailing Stop Management",
    description="Adjust trailing stops as position becomes profitable",
    condition=condition,
    action=action,
    cooldown_seconds=60  # Check once per minute
)

# Register the rule
rule_engine.register_rule(rule)
```

### End of Day Position Closure

```python
# Create a rule to close positions at end of day
condition = TimeCondition(
    start_time=time(15, 45),  # 3:45 PM
    end_time=time(15, 55),    # 3:55 PM
    market_hours_only=True,
    days_of_week=[0, 1, 2, 3, 4]  # Monday to Friday
)

action = ClosePositionAction(reason="End of day position closure")

rule = Rule(
    rule_id="eod_closure",
    name="End of Day Position Closure",
    description="Close all positions before market close",
    condition=condition,
    action=action,
    priority=200  # High priority
)

# Register the rule
rule_engine.register_rule(rule)
```

## Integration with Other Components

The Rule Engine integrates with other system components:

1. **Event System**: Subscribes to events and triggers rules based on event conditions
2. **Position Management**: Creates and manages positions through the Position Tracker
3. **Order Management**: Creates and manages orders through the Order Manager
4. **External APIs**: Processes prediction signals and market data

## Architecture Benefits

1. **Decoupled Components**: Each rule is independent and can be enabled/disabled without affecting others
2. **Configurability**: Trading strategies can be modified without code changes
3. **Extensibility**: New conditions and actions can be added to support additional use cases
4. **Testability**: Rules can be tested in isolation and with mocked components

## Best Practices

1. **Rule Organization**: Group related rules together and use consistent naming
2. **Priority Management**: Set priorities to ensure rules execute in the right order
3. **Context Usage**: Use rule context for sharing data between conditions and actions
4. **Error Handling**: Implement proper error handling in actions to prevent cascading failures
5. **Testing**: Test rules both in isolation and integrated with the full system