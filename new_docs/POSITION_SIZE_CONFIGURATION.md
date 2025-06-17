# Position Size Configuration

## Overview
The trading system uses a configurable default position size to determine how much capital to allocate per trade. This has been updated from $30,000 to $12,000 as requested.

## Configuration

### Environment Variable
Set the default position size using the `DEFAULT_POSITION_SIZE` environment variable:
```bash
DEFAULT_POSITION_SIZE=12000
```

### Configuration Location
The setting is defined in `src/config/broker_config.py` as part of the `TradingConfig` class:
```python
default_position_size: int = 12000  # Default allocation per trade
```

## Usage in Trading Strategies

When setting up trading strategies, the system uses this default position size for each ticker's allocation. For example:

```python
strategies = {
    "CVNA": {
        "confidence_threshold": 0.50, 
        "allocation": trading_config.default_position_size,  # $12,000
        "atr_stop_multiplier": 6.0, 
        "atr_target_multiplier": 4.0, 
        "cooldown_minutes": 3
    },
    # ... other tickers
}
```

## Position Sizing Calculation

The actual number of shares to trade is calculated by the `PositionSizer` class:
- Takes the allocation amount ($12,000)
- Divides by the current stock price
- Rounds to whole shares
- Applies min/max share constraints

### Example
- Stock price: $50
- Allocation: $12,000
- Calculated shares: 240 shares
- Actual order value: $12,000

## Changing the Position Size

To change the position size:

1. **Environment Variable** (Recommended):
   ```bash
   export DEFAULT_POSITION_SIZE=15000  # Change to $15,000
   ```

2. **Direct Configuration**:
   Update the default value in `src/config/broker_config.py`

3. **Per-Symbol Override**:
   You can override the default for specific symbols in your strategy configuration

## Important Notes

- The position size is the dollar amount to allocate, not the number of shares
- The system will calculate the appropriate number of shares based on current price
- Position sizing respects the `max_position_size` limit configured separately
- For paper trading, ensure your account has sufficient buying power 