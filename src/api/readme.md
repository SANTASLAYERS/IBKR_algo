# API Integration Components

## Overview

The API integration components provide connectivity to the Multi-Ticker Options Flow Monitor API, enabling the system to receive and process prediction signals and options flow data. These components generate events that can be used by the rule engine for automated trading decisions.

## Key Components

### OptionsFlowMonitor (`monitor.py`)

The `OptionsFlowMonitor` class is responsible for polling the API for new prediction signals and options flow data, then converting them to events for the event bus:

- **API Client Integration**: Uses the `api_client` package to communicate with the API
- **Event Generation**: Creates `PredictionSignalEvent` and other events based on API responses
- **Polling Management**: Configurable polling intervals with backoff on errors
- **Filtering**: Optional symbol filtering for targeted data retrieval
- **Error Handling**: Proper error handling and logging for API connectivity issues

```python
# Basic usage
from src.api.monitor import OptionsFlowMonitor
from api_client import ApiClient
from src.event.bus import EventBus

# Create event bus
event_bus = EventBus()

# Create API client
api_client = ApiClient(base_url="...", api_key="...")

# Create monitor
monitor = OptionsFlowMonitor(
    api_client=api_client,
    event_bus=event_bus,
    poll_interval=60.0,  # Poll every 60 seconds
    symbols=["AAPL", "MSFT", "AMZN"]  # Optional symbol filter
)

# Start monitoring
await monitor.start()

# Stop monitoring
await monitor.stop()
```

## Integration with Event System

The API components integrate with the event system by:

1. Creating and emitting prediction and trade events based on API data
2. Allowing event subscribers to react to these events
3. Supporting rule engine conditions based on prediction signals

### Event Types

```python
# PredictionSignalEvent from src.event.api
class PredictionSignalEvent(BaseEvent):
    """Event representing a prediction signal from the API."""
    
    def __init__(
        self,
        symbol: str,
        signal: str,
        confidence: float,
        prediction_id: str,
        timestamp: float,
        **kwargs
    ):
        super().__init__(event_type="prediction_signal", **kwargs)
        self.symbol = symbol
        self.signal = signal  # "BUY", "SELL", "NEUTRAL"
        self.confidence = confidence  # 0.0 to 1.0
        self.prediction_id = prediction_id
        self.timestamp = timestamp
```

## Integration with Rule Engine

The API components enable rule-based trading by:

1. Providing events that can be used in rule conditions
2. Supporting automated position and order creation based on signals

```python
# Example rule triggered by prediction signal
from src.rule.base import Rule
from src.rule.condition import EventCondition
from src.rule.action import CreatePositionAction

# Create condition triggered by high-confidence buy signals
condition = EventCondition(
    event_type=PredictionSignalEvent,
    field_conditions={
        "signal": "BUY",
        "confidence": lambda c: c > 0.85
    }
)

# Create action to open position based on signal
action = CreatePositionAction(
    symbol=lambda ctx: ctx["event"].symbol,
    quantity=100,
    stop_loss_pct=0.03,
    take_profit_pct=0.08
)

# Create rule combining condition and action
rule = Rule(
    rule_id="api_prediction_entry",
    name="Enter Position on High Confidence Buy Signal",
    description="Open a new position when a high-confidence buy signal is received",
    condition=condition,
    action=action
)
```

## Configuration

The API integration components can be configured through the system configuration:

```python
# Example configuration
config = {
    "api": {
        "base_url": "https://api.example.com/v1",
        "api_key": "your-api-key",
        "poll_interval": 60.0,
        "symbols": ["AAPL", "MSFT", "AMZN"],
        "retries": 3,
        "timeout": 30.0
    }
}
```

## Best Practices

When extending or using the API integration components:

1. **API Rate Limits**: Be mindful of API rate limits when configuring poll intervals
2. **Error Handling**: Implement proper error handling for API connectivity issues
3. **Event Filtering**: Filter events appropriately to avoid unnecessary processing
4. **Signal Validation**: Validate prediction signals before taking trading actions
5. **Secure API Keys**: Store API keys securely and never hardcode them

## Future Enhancements

Planned enhancements for the API integration components include:

1. WebSocket support for real-time updates instead of polling
2. Enhanced signal validation and quality metrics
3. Historical signal analysis for strategy backtesting
4. Multi-provider API support for signal aggregation
5. Advanced sentiment analysis integration