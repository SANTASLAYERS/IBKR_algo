# Rule Engine ATR Integration

## Overview

This document describes the integration of the Rule Engine with ATR (Average True Range) calculation in the IBKR Trading Framework. This integration enables rules to leverage volatility-based position sizing and risk management.

## Components

The integration consists of these key components:

1. **ATR Calculator**: Calculates Average True Range values from historical price data
2. **Indicator Manager**: Manages technical indicator calculations including ATR
3. **Strategy Controller**: Connects the Rule Engine with other components
4. **Rule Engine Context**: Provides access to ATR values in rule conditions and actions

## ATR Calculator

The ATR Calculator (`src/indicators/atr.py`) implements the standard ATR calculation:

```
ATR = Average of True Ranges over N periods
True Range = Max(High - Low, |High - Previous Close|, |Low - Previous Close|)
```

Key features:
- Customizable period (default: 14)
- Handles market gaps properly
- Supports calculation with limited data
- Returns meaningful errors when data is insufficient

## Indicator Manager

The Indicator Manager (`src/indicators/manager.py`) provides a simplified interface for calculating indicators:

- Fetches required historical data for calculations
- Maintains a basic cache of calculated values
- Currently focused on ATR calculation
- Designed for future expansion to other indicators

## Strategy Controller

The Strategy Controller (`src/strategy/controller.py`) serves as the central integration point:

- Connects the Rule Engine with position and order management
- Updates the Rule Engine context with ATR values
- Handles price events for potential indicator updates
- Provides an interface for requesting ATR calculations

## Using ATR in Rules

ATR values can be accessed in rule conditions and actions through the Rule Engine context:

```python
# Example of using ATR in a condition
from src.rule.condition import Condition

class ATRBasedCondition(Condition):
    def __init__(self, symbol, price_multiple=2.0):
        self.symbol = symbol
        self.price_multiple = price_multiple
        
    async def evaluate(self, context):
        # Get indicators for symbol
        indicators = context.get("indicators", {}).get(self.symbol, {})
        
        # Get current price
        prices = context.get("prices", {})
        current_price = prices.get(self.symbol)
        
        # Get ATR
        atr = indicators.get("ATR")
        
        # Can't evaluate without price and ATR
        if current_price is None or atr is None:
            return False
            
        # Example: True when price has moved more than price_multiple * ATR
        # from the previous day's close (simplified example)
        significant_move = self.price_multiple * atr
        previous_close = context.get("previous_closes", {}).get(self.symbol)
        
        if previous_close and abs(current_price - previous_close) > significant_move:
            return True
            
        return False
```

## Position Sizing with ATR

ATR can be used for position sizing in order actions:

```python
# Example of using ATR for position sizing
from src.rule.action import CreatePositionAction

class ATRPositionSizeAction(CreatePositionAction):
    def __init__(self, 
                 symbol,
                 risk_per_trade=0.01,  # 1% of account
                 risk_atr_multiple=2.0,  # Risk 2x ATR per trade
                 **kwargs):
        super().__init__(symbol=symbol, quantity=0, **kwargs)
        self.risk_per_trade = risk_per_trade
        self.risk_atr_multiple = risk_atr_multiple
        
    async def execute(self, context):
        # Get account value
        account = context.get("account", {})
        account_value = account.get("equity", 0)
        
        # Get ATR value
        indicators = context.get("indicators", {}).get(self.symbol, {})
        atr = indicators.get("ATR")
        
        # Get current price
        prices = context.get("prices", {})
        current_price = prices.get(self.symbol)
        
        if not account_value or not atr or not current_price:
            # Not enough information to size position
            return False
            
        # Calculate position size
        # Formula: (Account * Risk%) / (ATR * Multiple)
        risk_amount = account_value * self.risk_per_trade
        risk_per_share = atr * self.risk_atr_multiple
        
        if risk_per_share <= 0:
            return False
            
        # Calculate quantity
        quantity = int(risk_amount / risk_per_share)
        
        # Ensure minimum position size
        if quantity < 1:
            quantity = 1
            
        # Update quantity in the action
        self.quantity = quantity
        
        # Execute the parent action with the calculated quantity
        return await super().execute(context)
```

## Integration Tests

The ATR Calculator and Strategy Controller have comprehensive tests that verify:

1. Correct ATR calculation with known values
2. Proper handling of insufficient data
3. Integration with the Rule Engine
4. Context updates with ATR values
5. Rule evaluation using ATR data

## Next Steps

Future enhancements to the ATR integration:

1. Add more technical indicators beyond ATR
2. Implement indicator-specific conditions in the Rule Engine
3. Create predefined position sizing strategies based on ATR
4. Add time-based ATR updates (e.g., daily recalculation)
5. Improve caching to optimize performance