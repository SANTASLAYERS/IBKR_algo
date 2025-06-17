# Fixes Applied to Alpaca Trading System

## Issues Found and Fixed

### 1. ❌ ATR Calculation Error
**Issue**: System was trying to use "10 secs" bar size
```
Error fetching historical bars for SOXL: Unsupported bar size unit: sec
```

**Root Cause**: Alpaca API doesn't support sub-minute timeframes (only 1min, 5min, 15min, etc.)

**Fix Applied**:
- Changed default bar size from "10 secs" to "1 min" in:
  - `src/indicators/manager.py`
  - `src/rule/linked_order_actions.py` (3 locations)

**Impact**: ATR calculations now work but are based on 1-minute volatility instead of 10-second

### 2. ❌ Event Loop Concurrency Error
**Issue**: Asyncio locks bound to different event loops
```
RuntimeError: <asyncio.locks.Lock object at 0x00000289EB471A50 [locked, waiters:3]> is bound to a different event loop
```

**Root Cause**: Locks were created during rule registration (sync context) but used in async context

**Fix Applied**:
- Modified `src/rule/engine.py` to create locks lazily in the correct event loop
- Added `_get_or_create_lock()` method
- Added lock creation synchronization

**Impact**: No more event loop errors during rule execution

### 3. ✅ Dynamic Position Sizing (Working)
**No Fix Needed**: The system correctly calculated positions based on $30,000 allocation:
- SOXL: 1,341 shares (price ~$22.38)
- GLD: 96 shares (price ~$312.50)
- SLV: 891 shares (price ~$33.67)

### 4. ⚠️ Stop/Target Orders Not Created
**Issue**: Stop loss and take profit orders weren't created due to ATR calculation failure

**Status**: Should be fixed now that ATR calculation works

### 5. ⚠️ Double-Down Orders Not Created
**Issue**: "No stop orders found yet for SOXL, skipping double down creation"

**Root Cause**: Double-down orders wait for stop orders to exist, but stops failed due to ATR error

**Status**: Should be fixed now that ATR calculation works

## Summary of Changes

### Files Modified:
1. **src/indicators/manager.py**
   - Changed default `bar_size` from "10 secs" to "1 min"

2. **src/rule/linked_order_actions.py**
   - Updated 3 ATR calculation calls to use "1 min" instead of "10 secs"

3. **src/rule/engine.py**
   - Added lazy lock creation in correct event loop
   - Added `_get_or_create_lock()` method
   - Added `_lock_creation_lock` for thread-safe lock creation

### Trade-offs:
- **ATR Precision**: Using 1-minute bars instead of 10-second bars means:
  - Less granular volatility measurement
  - Potentially wider stop losses (1-min volatility > 10-sec volatility)
  - May need to adjust ATR multipliers (e.g., reduce from 6x to 4x)

### Recommendations:
1. **Monitor ATR Values**: Check if 1-minute ATR values are appropriate for your risk tolerance
2. **Adjust Multipliers**: Consider reducing ATR multipliers since 1-min bars capture more volatility
3. **Test Thoroughly**: Run paper trading to verify stop/target levels are reasonable

## Running the Fixed Version

Use the new batch file:
```
.\run_trading_fixed.bat
```

This will start the system with all fixes applied and show status messages about the corrections. 