# Trading Thresholds and Trade Execution

## Overview
The Alpaca trading system uses a multi-level threshold system to determine when to execute trades based on prediction API signals.

## Key Thresholds

### 1. Prediction Monitoring Threshold: 50%
- **Location**: `OptionsFlowMonitor` configuration
- **Purpose**: Determines which predictions to process and emit as events
- **Effect**: Only predictions with confidence ≥ 50% are passed to the rule engine

### 2. Trading Execution Threshold: 50%
- **Location**: Strategy configuration for each ticker
- **Purpose**: Determines when to actually place trades
- **Current Setting**: ALL tickers are set to 50% confidence threshold

## When Trades Are Taken

A trade will be executed when ALL of the following conditions are met:

1. **Prediction Confidence ≥ 50%**
   - The prediction API returns a BUY or SHORT signal with at least 50% confidence
   
2. **Signal Type Matches**
   - BUY signal → Creates a long position
   - SHORT signal → Creates a short position
   - NEUTRAL signal → No action taken

3. **No Existing Position**
   - The system checks if there's already an open position for that ticker
   - If a position exists in the same direction → No action
   - If a position exists in opposite direction → Closes existing, then enters new

4. **Cooldown Period Expired**
   - 3-minute cooldown between trades for the same ticker
   - Prevents rapid-fire trading on volatile predictions

5. **Market Hours**
   - Trades only execute during regular market hours
   - Alpaca handles this automatically

## Example Scenarios

### Trade Executed:
- GLD prediction: SELL @ $312.00 (confidence: 65%) → **TRADE PLACED**
- No existing GLD position
- Cooldown expired

### Trade NOT Executed:
- SOXL prediction: NEUTRAL @ $22.00 (confidence: 85%) → **NO TRADE** (NEUTRAL signal)
- SLV prediction: BUY @ $33.80 (confidence: 45%) → **NO TRADE** (below 50% threshold)
- CVNA prediction: BUY @ $293.00 (confidence: 75%) → **NO TRADE** if already long CVNA

## Position Sizing

When a trade is executed:
- **Allocation**: $30,000 per position
- **Share Calculation**: $30,000 ÷ Current Price = Number of shares
- **Examples**:
  - GLD @ $312: 96 shares
  - SOXL @ $22: 1,363 shares
  - CVNA @ $293: 102 shares

## Risk Management

Each position automatically gets:
1. **Stop Loss Order**
   - Default: 6x ATR below entry (most tickers)
   - GLD/SLV: 10x ATR (less volatile)
   - Fallback: 3% if ATR calculation fails

2. **Take Profit Order**
   - Default: 4x ATR above entry (most tickers)
   - GLD/SLV: 5x ATR
   - Fallback: 8% if ATR calculation fails

3. **Double-Down Order**
   - Placed at 50% of stop loss distance
   - Same size as initial position

## Current System Status

Based on the recent logs, the system is receiving predictions like:
- CVNA: NEUTRAL @ $292.77 (93.0%) → No trade (NEUTRAL)
- GLD: NEUTRAL @ $312.04 (92.6%) → No trade (NEUTRAL)
- SLV: SELL @ $33.80 (55.6%) → Would execute if no position/cooldown

The 50% threshold is relatively low, meaning the system will act on predictions where the model has moderate confidence. This is balanced by the risk management features (stops, position sizing, cooldowns). 