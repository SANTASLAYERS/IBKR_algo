# ATR Functionality Status with Alpaca

## Summary
The ATR (Average True Range) indicator functionality is **fully working** with Alpaca. The system successfully calculates ATR values using historical price data from Alpaca's IEX feed.

## Key Components

### 1. ATR Calculator (`src/indicators/atr.py`)
- Implements the standard ATR calculation algorithm
- Calculates True Range as: max(high-low, |high-prev_close|, |low-prev_close|)
- Averages True Ranges over specified period (default 14)
- Handles insufficient data gracefully

### 2. Indicator Manager (`src/indicators/manager.py`)
- Provides high-level interface for ATR calculation
- Integrates with AlpacaMinuteBarManager for data retrieval
- Supports caching of calculated values
- Configurable parameters:
  - `period`: ATR period (default 14)
  - `days`: Number of days of historical data (default 5)
  - `bar_size`: Timeframe for bars (default "10 secs", but typically "1 min")

### 3. Alpaca Integration (`src/minute_data/alpaca_manager.py`)
- Uses IEX feed (required for paper trading accounts)
- Supports multiple timeframes (1 min, 5 mins, 15 mins, 1 hour)
- Caches historical data for efficiency
- Converts Alpaca bars to MinuteBar format

## Test Results

### ATR Values for Major Symbols (1-minute bars, 14-period)
- **AAPL**: $0.1775 (0.09% of price)
- **SPY**: $0.3229 (0.05% of price)
- **TSLA**: $0.3293 (0.10% of price)
- **GLD**: $0.0921 (0.03% of price)
- **SLV**: $0.0525 (0.16% of price)

### ATR by Timeframe (SPY)
- **1-minute bars**: $0.3229 (0.05% of price)
- **5-minute bars**: $0.4168 (0.07% of price)
- **15-minute bars**: $0.6218 (0.10% of price)
- **Hourly bars**: $1.8646 (0.31% of price)

## Usage in Trading System

### 1. Stop Loss Calculations
The system uses ATR multipliers for dynamic stop loss placement:
```python
# Example for SPY at $602.86 with ATR of $0.3229
- 1.5x ATR stop: $602.38 (0.1% from entry)
- 2.0x ATR stop: $602.21 (0.1% from entry)
- 2.5x ATR stop: $602.05 (0.1% from entry)
- 3.0x ATR stop: $601.89 (0.2% from entry)
```

### 2. Take Profit Targets
Similarly for profit targets:
```python
# Example for SPY at $602.86 with ATR of $0.3229
- 1.5x ATR target: $603.34 (0.1% from entry)
- 2.0x ATR target: $603.51 (0.1% from entry)
- 2.5x ATR target: $603.67 (0.1% from entry)
- 3.0x ATR target: $603.83 (0.2% from entry)
```

### 3. Strategy Configuration
Each ticker has configured ATR multipliers in `main_trading_app.py`:
- **CVNA, UVXY, SOXL, SOXS, TQQQ, SQQQ, SLV**: 
  - Stop: 6.0x ATR
  - Target: 4.0x ATR
- **GLD**: 
  - Stop: 10.0x ATR
  - Target: 5.0x ATR

## Integration Points

### 1. Strategy Controller
- `get_atr()` method calculates and updates ATR in rule engine context
- ATR values accessible via `context["indicators"][symbol]["ATR"]`

### 2. Position Manager
- Stores ATR multipliers per position
- `update_position_atr_params()` method for dynamic updates

### 3. Stock Position
- `calculate_optimal_stop_loss()` uses ATR for stop calculation
- Stores ATR value in position metadata

### 4. Rule Actions
- `LinkedOrderAction` accepts `atr_stop_multiplier` and `atr_target_multiplier`
- Automatically creates stop/target orders based on ATR

## Important Notes

1. **Data Feed**: Paper trading accounts must use IEX feed (not SIP)
2. **Bar Size**: System supports various timeframes, but "1 min" is standard
3. **Caching**: Historical data is cached to reduce API calls
4. **Real-time Updates**: ATR can be recalculated on demand or scheduled

## Verification
Run `python test_alpaca_atr.py` to verify ATR functionality. All tests should pass with:
- ✓ Historical data retrieval
- ✓ ATR calculation
- ✓ Multiple timeframes
- ✓ Caching functionality
- ✓ Stop/target calculations 