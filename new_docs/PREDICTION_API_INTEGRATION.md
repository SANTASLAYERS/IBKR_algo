# Prediction API Integration

## Overview

The trading system now integrates with an external prediction API to receive trading signals. The system polls the API every 60 seconds and automatically executes trades when high-confidence predictions are received.

## Components

### 1. OptionsFlowMonitor
Located in `src/api/monitor.py`, this component:
- Polls the prediction API every 60 seconds for each configured ticker
- Checks if predictions meet the confidence threshold (default 80%)
- Emits `PredictionSignalEvent` when actionable predictions are found
- Tracks prediction IDs to avoid processing duplicates

### 2. Trading Rules
The system automatically creates two rules per ticker:
- **Buy Rule**: Executes when a BUY signal is received with ≥80% confidence
- **Short Rule**: Executes when a SHORT signal is received with ≥80% confidence

Each rule includes:
- Automatic stop loss (3% by default)
- Automatic take profit (8% by default)
- 5-minute cooldown between trades

### 3. Monitored Tickers
The system monitors these tickers by default:
- CVNA (Carvana)
- UVXY (Ultra VIX Short-Term Futures)
- SOXL (3x Semiconductor Bull)
- SOXS (3x Semiconductor Bear)
- TQQQ (3x QQQ Bull)
- SQQQ (3x QQQ Bear)
- GLD (Gold ETF)
- SLV (Silver ETF)

## Configuration

### API Credentials
Set these environment variables:
```bash
API_BASE_URL=https://your-prediction-api-url.com/api/
API_KEY=your_api_key_here
```

### Customizing Parameters
In `main_trading_app.py`, you can customize:

```python
# Confidence threshold (0.0 to 1.0)
thresholds={'prediction_confidence_min': 0.80}

# Position size per trade
quantity=100  # shares

# Risk parameters
stop_loss_pct=0.03    # 3% stop loss
take_profit_pct=0.08  # 8% take profit
cooldown_minutes=5    # 5 minutes between trades
```

## How It Works

1. **Polling**: Every 60 seconds, the monitor queries the prediction API for each ticker
2. **Signal Processing**: When a prediction meets the confidence threshold:
   - A `PredictionSignalEvent` is emitted to the event bus
3. **Rule Evaluation**: The rule engine evaluates all rules:
   - Checks if the signal matches (BUY/SHORT)
   - Verifies confidence threshold
   - Ensures cooldown period has passed
4. **Order Execution**: If conditions are met:
   - Creates a market order for the specified quantity
   - Automatically creates stop loss and take profit orders
5. **Position Management**: UnifiedFillManager handles:
   - Updating protective orders if position size changes
   - Closing positions when stop/target is hit

## Monitoring

Watch the logs for:
```
Polling predictions for AAPL
New prediction: AAPL BUY (0.85)
Emitted PredictionSignalEvent for AAPL
Buy 100 shares of AAPL when confidence >= 0.80
```

## API Response Format

The prediction API should return:
```json
{
  "prediction": {
    "id": "unique_prediction_id",
    "signal": "BUY",  // or "SHORT"
    "confidence": 0.85,
    "numeric": 1,  // 1 for BUY, -1 for SHORT
    "stock_price": 150.25,
    "probabilities": {
      "buy": 0.85,
      "hold": 0.10,
      "sell": 0.05
    },
    "feature_values": {
      "momentum": 0.75,
      "volume": 0.82,
      // ... other features
    }
  },
  "model_info": {
    "version": "1.0",
    "timestamp": "2024-01-01T10:00:00Z"
  }
}
```

## Troubleshooting

### No Predictions Received
1. Check API credentials are set correctly
2. Verify API_BASE_URL ends with `/api/`
3. Check network connectivity
4. Look for error messages in logs

### Orders Not Executing
1. Verify market is open
2. Check account has sufficient buying power
3. Ensure cooldown period has passed
4. Verify position sizing is appropriate

### API Errors
Common errors and solutions:
- `401 Unauthorized`: Check API_KEY is correct
- `429 Rate Limited`: Reduce number of tickers or increase poll interval
- `Connection Error`: Check network and API_BASE_URL

## Performance Considerations

- Each ticker requires one API call per minute
- 8 tickers = 480 API calls per hour
- Monitor API rate limits
- Consider reducing ticker list if needed

## Future Enhancements

1. **Dynamic Position Sizing**: Adjust quantity based on confidence
2. **Multiple Models**: Support different prediction models
3. **Custom Polling Intervals**: Per-ticker polling frequencies
4. **Signal Aggregation**: Combine multiple signals before trading 