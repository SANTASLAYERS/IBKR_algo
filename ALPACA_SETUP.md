# Alpaca Trading System Setup Guide

## Overview
This automated trading system connects to Alpaca Markets for trade execution and monitors a prediction API for trading signals. It automatically places trades based on high-confidence predictions with built-in risk management.

## Prerequisites

### 1. Alpaca Account
- Sign up at https://alpaca.markets
- Get your API credentials from the dashboard
- Use paper trading for testing

### 2. Prediction API Access
- API endpoint: https://toine-todo-list-4ef27f1146af.herokuapp.com/api/v1/
- Obtain API key for authentication

## Environment Variables

Create a `.env` file or set these environment variables:

```bash
# Alpaca Credentials (REQUIRED)
ALPACA_API_KEY=your_alpaca_api_key
ALPACA_SECRET_KEY=your_alpaca_secret_key
ALPACA_TRADING_MODE=paper  # or 'live' for real trading

# Prediction API Credentials (REQUIRED)
API_BASE_URL=https://toine-todo-list-4ef27f1146af.herokuapp.com/api/v1/
API_KEY=your_prediction_api_key
```

## Quick Start

### Windows PowerShell
```powershell
# Set environment variables
$env:ALPACA_API_KEY="your_alpaca_api_key"
$env:ALPACA_SECRET_KEY="your_alpaca_secret_key"
$env:ALPACA_TRADING_MODE="paper"
$env:API_BASE_URL="https://toine-todo-list-4ef27f1146af.herokuapp.com/api/v1/"
$env:API_KEY="your_prediction_api_key"

# Run the trading app
python main_trading_app.py
```

### Windows Batch Script
Save as `run_trading.bat`:
```batch
@echo off
set ALPACA_API_KEY=your_alpaca_api_key
set ALPACA_SECRET_KEY=your_alpaca_secret_key
set ALPACA_TRADING_MODE=paper
set API_BASE_URL=https://toine-todo-list-4ef27f1146af.herokuapp.com/api/v1/
set API_KEY=your_prediction_api_key

python main_trading_app.py
```

### Linux/Mac
```bash
export ALPACA_API_KEY="your_alpaca_api_key"
export ALPACA_SECRET_KEY="your_alpaca_secret_key"
export ALPACA_TRADING_MODE="paper"
export API_BASE_URL="https://toine-todo-list-4ef27f1146af.herokuapp.com/api/v1/"
export API_KEY="your_prediction_api_key"

python main_trading_app.py
```

## System Components

### 1. **Monitored Tickers** (8 total)
- CVNA - Carvana
- UVXY - Ultra VIX Short-Term Futures ETF
- SOXL - Semiconductor Bull 3X ETF
- SOXS - Semiconductor Bear 3X ETF
- TQQQ - ProShares UltraPro QQQ (3X Bull)
- SQQQ - ProShares UltraPro Short QQQ (3X Bear)
- GLD - SPDR Gold Trust
- SLV - iShares Silver Trust

### 2. **Trading Parameters**
- **Confidence Threshold**: 80% (only trades when prediction confidence ≥ 0.80)
- **Position Size**: 100 shares per trade (configurable)
- **Stop Loss**: 3% from entry price
- **Take Profit**: 8% from entry price
- **Cooldown**: 5 minutes between trades per ticker

### 3. **Active Features**
- ✅ Real-time Alpaca connection with WebSocket streaming
- ✅ Position tracking and synchronization (every 30 seconds)
- ✅ Automatic order management with stop loss and take profit
- ✅ UnifiedFillManager for handling partial fills
- ✅ Prediction API monitoring (polls every 60 seconds)
- ✅ Rule engine for automated trade execution
- ✅ Position reversal handling (exits current position before entering opposite)

## Trading Logic

### Signal Processing
1. **Prediction Reception**: System polls the prediction API every 60 seconds
2. **Confidence Check**: Only processes signals with ≥80% confidence
3. **Position Check**: 
   - If no position exists → Create new position
   - If same-side position exists → Ignore signal
   - If opposite-side position exists → Exit current, then enter new

### Order Execution
1. **Entry Order**: Market order for 100 shares
2. **Stop Loss**: Automatically placed at -3% (long) or +3% (short)
3. **Take Profit**: Automatically placed at +8% (long) or -8% (short)
4. **Cooldown**: 5-minute cooldown per ticker after trade execution

## Monitoring the System

### Log Output
The system provides detailed logging:
```
2025-06-17 10:14:42,032 - __main__ - INFO - Initializing Alpaca Trading System
2025-06-17 10:14:42,157 - src.alpaca_connection - INFO - Connected to Alpaca - Account: PA3IDVID4N3W
2025-06-17 10:14:42,423 - __main__ - INFO - OptionsFlowMonitor started for 8 tickers
2025-06-17 10:14:42,423 - __main__ - INFO - Registered 16 trading rules
2025-06-17 10:14:42,423 - __main__ - INFO - Trading system is running...
```

### Key Indicators
- **Connection Status**: Shows Alpaca account and buying power
- **Active Rules**: 16 rules (BUY and SHORT for each ticker)
- **Position Sync**: Updates every 30 seconds
- **API Polling**: Checks predictions every 60 seconds

## Troubleshooting

### Common Issues

1. **"ALPACA_API_KEY and ALPACA_SECRET_KEY must be set"**
   - Ensure environment variables are set before running
   - Check for typos in variable names

2. **"API key is required"**
   - Set the API_KEY environment variable for prediction API
   - Verify API_BASE_URL is correct

3. **"Error polling predictions"**
   - Check prediction API connectivity
   - Verify API credentials are valid
   - Ensure API_BASE_URL ends with trailing slash

4. **No trades executing**
   - Check if predictions meet 80% confidence threshold
   - Verify market hours (trades only execute during market hours)
   - Check cooldown periods (5 minutes per ticker)

### Debug Mode
For verbose logging, modify the logging level in main_trading_app.py:
```python
logging.basicConfig(level=logging.DEBUG)
```

## Safety Features

1. **Paper Trading Default**: System defaults to paper trading mode
2. **Position Size Limits**: Fixed at 100 shares per trade
3. **Stop Loss Protection**: Automatic 3% stop loss on all positions
4. **Cooldown Periods**: Prevents overtrading with 5-minute cooldowns
5. **Position Sync**: Regular synchronization with Alpaca account

## Advanced Configuration

### Modifying Trading Parameters
In `main_trading_app.py`, adjust the rule creation:
```python
buy_rule = create_buy_rule(
    symbol=ticker,
    quantity=100,              # Change position size
    confidence_threshold=0.80,  # Change confidence requirement
    stop_loss_pct=0.03,        # Change stop loss percentage
    take_profit_pct=0.08,      # Change take profit percentage
    cooldown_minutes=5         # Change cooldown period
)
```

### Adding/Removing Tickers
Modify the `tickers_to_monitor` list:
```python
tickers_to_monitor = ["CVNA", "UVXY", "SOXL", "SOXS", "TQQQ", "SQQQ", "GLD", "SLV", "NEW_TICKER"]
```

## Production Deployment

### Recommended Setup
1. Use a dedicated server or cloud instance
2. Set up process monitoring (systemd, supervisor, etc.)
3. Configure log rotation
4. Set up alerts for errors
5. Use environment variable management (dotenv, secrets manager)

### Example Systemd Service
```ini
[Unit]
Description=Alpaca Trading System
After=network.target

[Service]
Type=simple
User=trading
WorkingDirectory=/home/trading/alpaca-system
Environment="ALPACA_API_KEY=xxx"
Environment="ALPACA_SECRET_KEY=xxx"
Environment="ALPACA_TRADING_MODE=paper"
Environment="API_BASE_URL=https://..."
Environment="API_KEY=xxx"
ExecStart=/usr/bin/python3 /home/trading/alpaca-system/main_trading_app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## Support

For issues or questions:
1. Check the trading.log file for detailed error messages
2. Verify all environment variables are set correctly
3. Ensure Alpaca API access is working (check dashboard)
4. Test prediction API connectivity separately 