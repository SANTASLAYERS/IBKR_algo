# Alpaca Trading System - Advanced Features

## Overview
The Alpaca trading system now includes all advanced features from the TWS trading system, providing sophisticated automated trading capabilities with dynamic risk management.

## 1. ATR-Based Stop Loss and Take Profit

### How It Works
- **ATR (Average True Range)** measures market volatility over a specified period
- Stop loss and take profit levels automatically adjust based on current volatility
- More volatile markets = wider stops, less volatile = tighter stops

### Configuration Per Ticker
```python
# Standard tickers (CVNA, UVXY, SOXL, SOXS, TQQQ, SQQQ, SLV)
"atr_stop_multiplier": 6.0,    # Stop loss at 6x ATR from entry
"atr_target_multiplier": 4.0,  # Take profit at 4x ATR from entry

# Gold (GLD) - Less volatile, needs wider stops
"atr_stop_multiplier": 10.0,   # Stop loss at 10x ATR from entry
"atr_target_multiplier": 5.0,  # Take profit at 5x ATR from entry
```

### Example Calculation
- If ATR = $0.50 for a stock trading at $100:
  - Stop Loss: $100 - (6 × $0.50) = $97.00
  - Take Profit: $100 + (4 × $0.50) = $102.00
  - Risk/Reward Ratio: 6:4 = 1.5:1

### Fallback Mechanism
If ATR calculation fails, the system falls back to percentage-based stops:
- Stop Loss: 3% from entry
- Take Profit: 8% from entry

## 2. Dynamic Position Sizing

### Dollar-Based Allocation
Instead of fixed share quantities, each position uses a **$30,000 allocation**:
```python
"allocation": 30000  # $30,000 per position
```

### How Shares Are Calculated
1. System gets current market price
2. Calculates shares: `shares = $30,000 / current_price`
3. Rounds to nearest whole share
4. Respects min/max share limits (1-10,000)

### Examples
- Stock at $50: 30,000 / 50 = **600 shares**
- Stock at $150: 30,000 / 150 = **200 shares**
- Stock at $3,000: 30,000 / 3,000 = **10 shares**

## 3. Customized Strategy Parameters Per Ticker

### Current Configuration
| Ticker | Confidence | Allocation | Stop (ATR) | Target (ATR) | Cooldown |
|--------|------------|------------|------------|--------------|----------|
| CVNA   | 50%        | $30,000    | 6x         | 4x           | 3 min    |
| UVXY   | 50%        | $30,000    | 6x         | 4x           | 3 min    |
| SOXL   | 50%        | $30,000    | 6x         | 4x           | 3 min    |
| SOXS   | 50%        | $30,000    | 6x         | 4x           | 3 min    |
| TQQQ   | 50%        | $30,000    | 6x         | 4x           | 3 min    |
| SQQQ   | 50%        | $30,000    | 6x         | 4x           | 3 min    |
| GLD    | 50%        | $30,000    | 10x        | 5x           | 3 min    |
| SLV    | 50%        | $30,000    | 6x         | 4x           | 3 min    |

### Key Differences from Basic Version
- **Lower confidence threshold**: 50% vs 80% (more trades)
- **Shorter cooldown**: 3 minutes vs 5 minutes (faster re-entry)
- **Ticker-specific ATR multipliers**: GLD has different settings

## 4. End-of-Day Position Closure

### Automatic Market Close Protection
- **Trigger Time**: 3:59 PM ET (1 minute before market close)
- **Actions Taken**:
  1. Closes all open positions at market
  2. Cancels all pending orders
  3. Ensures clean slate for next trading day

### Implementation
```python
TimeCondition(
    start_time=dt_time(15, 59),  # 3:59 PM ET
    end_time=dt_time(16, 0)      # 4:00 PM ET
)
```

### Benefits
- Prevents overnight gap risk
- Avoids margin calls
- Ensures all positions are flat before market close

## 5. Double Down Orders (Auto-Scaling)

### Automatic Position Averaging
When a position is opened, the system automatically creates a **double-down limit order**:
- **Location**: 50% of the distance to stop loss
- **Size**: Same as initial position size
- **Purpose**: Average into winning positions during pullbacks

### Example
1. Buy 200 shares at $100
2. Stop loss at $94 (6 ATR × $1 = $6 below)
3. Double-down order: Buy 200 more at $97 (halfway to stop)
4. If filled, new average: 400 shares at $98.50

### Risk Management
- Only one double-down level per position
- Protective orders automatically adjust after fill
- Maintains same risk/reward profile

## 6. Additional Advanced Features

### Cooldown Reset on Stop Loss
- When a stop loss is hit, the cooldown period for that ticker resets
- Allows immediate re-entry after being stopped out
- Prevents missing reversal opportunities

### 10-Minute Status Monitoring
- System logs comprehensive status every 10 minutes:
  - Current positions and P&L
  - Account buying power and equity
  - Individual position details
- Helps track system health and performance

### Position Reversal Handling
- If holding a long position and get a SHORT signal:
  1. Exit current long position
  2. Enter new short position
- Seamless transition between opposing positions

### Real-Time Component Integration
- **Price Service**: Real-time price updates for accurate calculations
- **Indicator Manager**: Calculates ATR and other technical indicators
- **Position Sizer**: Ensures proper position sizing based on account equity

## System Architecture Benefits

### Modular Design
- Each component (ATR, sizing, rules) works independently
- Easy to modify individual features without affecting others
- Extensible for future enhancements

### Event-Driven Architecture
- All actions triggered by events (signals, fills, time)
- Asynchronous processing for better performance
- Real-time response to market conditions

### Risk Controls
- Multiple layers of protection:
  1. ATR-based stops (volatility-adjusted)
  2. Position size limits ($30k max allocation)
  3. Cooldown periods (prevent overtrading)
  4. End-of-day closure (no overnight risk)

## Monitoring and Logs

### What to Look For
```
2025-06-17 10:30:00 - Created strategy for CVNA (confidence >= 0.5, allocation: $30,000, ATR stop: 6.0x, ATR target: 4.0x, cooldown: 3 min)
2025-06-17 10:30:00 - Created strategy for GLD (confidence >= 0.5, allocation: $30,000, ATR stop: 10.0x, ATR target: 5.0x, cooldown: 3 min)
2025-06-17 10:30:00 - Advanced features enabled:
  - ATR-based stop loss and take profit
  - Dynamic position sizing ($30k allocation)
  - Customized parameters per ticker
  - End-of-day position closure (3:59 PM)
  - Automatic double-down orders
```

### Status Updates (Every 10 Minutes)
```
SYSTEM STATUS UPDATE
Current positions: 2
Total value: $60,000.00
Unrealized P&L: $1,234.56
Active positions:
  CVNA: 600 shares @ $50.00 (P&L: $600.00)
  GLD: 200 shares @ $150.00 (P&L: $634.56)
Account buying power: $140,000.00
Account equity: $201,234.56
```

## Quick Reference

### To Modify Settings
Edit the `strategies` dictionary in `main_trading_app.py`:
```python
self.strategies = {
    "TICKER": {
        "confidence_threshold": 0.50,    # Min confidence for signals
        "allocation": 30000,             # Position size in dollars
        "atr_stop_multiplier": 6.0,      # ATR multiplier for stop
        "atr_target_multiplier": 4.0,    # ATR multiplier for target
        "cooldown_minutes": 3            # Minutes between trades
    }
}
```

### To Add New Tickers
1. Add to `strategies` dictionary with parameters
2. System automatically creates all necessary rules
3. No other changes needed

### To Disable Features
- **Disable EOD closure**: Remove `_setup_eod_rules()` call
- **Disable double-down**: Set `auto_create_stops=False` in actions
- **Use fixed position size**: Change allocation to share count < 1000 