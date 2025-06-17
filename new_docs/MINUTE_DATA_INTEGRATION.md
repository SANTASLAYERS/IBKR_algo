# Alpaca Minute Data Integration

## Overview

The AlpacaMinuteBarManager provides historical and real-time minute bar data from Alpaca Markets. It's fully integrated with the existing minute data infrastructure and provides caching, multiple timeframes, and streaming capabilities.

## Features

- **Historical Data Retrieval**: Fetch minute bars for any date range
- **Multiple Timeframes**: Support for 1 min, 5 mins, 15 mins, 30 mins, 1 hour
- **Caching**: Automatic caching of historical data for improved performance
- **Real-time Streaming**: Subscribe to live minute bar updates
- **Compatible Interface**: Works with existing MinuteBar and MinuteBarCollection models

## Architecture

```
AlpacaMinuteBarManager
├── Historical Data
│   ├── get_historical_bars()
│   ├── get_historical_data()
│   └── get_latest_bar()
├── Real-time Streaming
│   ├── subscribe_bars()
│   └── unsubscribe_bars()
└── Data Conversion
    └── Alpaca Bar → MinuteBar
```

## Usage

### Getting Historical Data

```python
from datetime import datetime, timezone, timedelta

# Get historical bars for a specific date range
end = datetime.now(timezone.utc)
start = end - timedelta(days=5)

collection = await connection.minute_bar_manager.get_historical_bars(
    symbol="AAPL",
    start=start,
    end=end,
    bar_size="1 min",
    use_cache=True
)

print(f"Retrieved {len(collection)} bars")
for bar in collection:
    print(f"{bar.timestamp}: O={bar.open_price} H={bar.high_price} L={bar.low_price} C={bar.close_price} V={bar.volume}")
```

### Using Duration Strings

```python
# Get data using IB-style duration strings
collection = await connection.minute_bar_manager.get_historical_bars(
    symbol="SPY",
    duration="5 D",  # 5 days
    bar_size="5 mins",
    use_cache=True
)
```

Supported duration units:
- `D` - Days
- `W` - Weeks  
- `H` - Hours
- `M` - Months (approximate, 30 days)
- `Y` - Years (approximate, 365 days)

### Convenience Method for Indicators

```python
# Get historical data for indicator calculations
bars = await connection.minute_bar_manager.get_historical_data(
    symbol="TSLA",
    days=10,
    bar_size="1 min",
    use_cache=True
)

# Returns a list of MinuteBar objects
for bar in bars:
    print(f"{bar.timestamp}: {bar.close_price}")
```

### Different Timeframes

```python
# Supported timeframes
timeframes = ["1 min", "5 mins", "15 mins", "30 mins", "1 hour"]

for tf in timeframes:
    collection = await connection.minute_bar_manager.get_historical_bars(
        symbol="QQQ",
        duration="1 D",
        bar_size=tf,
        use_cache=False
    )
    print(f"{tf}: {len(collection)} bars")
```

### Real-time Streaming

```python
# Define callback for bar updates
def on_bar_update(bar: MinuteBar):
    print(f"New bar: {bar.symbol} @ {bar.timestamp} - Close: {bar.close_price}")

# Subscribe to symbols
symbols = ["AAPL", "SPY", "TSLA"]
connection.minute_bar_manager.subscribe_bars(symbols, callback=on_bar_update)

# ... bars will be received via callback ...

# Unsubscribe when done
connection.minute_bar_manager.unsubscribe_bars(symbols)
```

## Data Models

### MinuteBar

Each minute bar contains:
- `symbol`: Stock symbol
- `timestamp`: Bar timestamp (timezone-aware)
- `open_price`: Opening price
- `high_price`: Highest price
- `low_price`: Lowest price
- `close_price`: Closing price
- `volume`: Trading volume
- `count`: Number of trades (optional)
- `wap`: Volume-weighted average price (optional)

### MinuteBarCollection

A collection of minute bars for a symbol:
- Automatically sorted by timestamp
- Supports iteration and indexing
- Can be converted to DataFrame (if pandas available)
- Serializable to JSON/CSV

## Caching

The manager includes automatic caching:

1. **Cache Keys**: Generated from symbol, date range, and timeframe
2. **Cache Storage**: Local file system cache
3. **Cache Invalidation**: Use `use_cache=False` to bypass cache

```python
# First request fetches from API
collection1 = await manager.get_historical_bars(
    symbol="AAPL", duration="1 D", use_cache=True
)

# Second request uses cache (much faster)
collection2 = await manager.get_historical_bars(
    symbol="AAPL", duration="1 D", use_cache=True
)
```

## Integration with Trading System

The AlpacaMinuteBarManager integrates with:

1. **Indicator Manager**: Provides data for technical indicators
2. **Rule Engine**: Historical data for strategy conditions
3. **Position Sizing**: Recent price data for position calculations
4. **Price Service**: Latest bar data for current prices

## Best Practices

1. **Use Caching**: Enable caching for frequently accessed data
2. **Batch Requests**: Request larger time ranges rather than many small ones
3. **Handle Market Hours**: Be aware of market hours when requesting recent data
4. **Error Handling**: Always handle potential API errors
5. **Rate Limits**: Respect Alpaca's rate limits (200 requests/minute)

## Troubleshooting

### No Data Returned

1. **Check Date Range**: Ensure dates are during market hours
2. **Verify Symbol**: Confirm symbol is valid and traded
3. **API Limits**: Free tier has limitations on recent data access

### Cache Issues

1. **Windows**: Colons in timestamps are replaced for filename compatibility
2. **Permissions**: Ensure write access to cache directory
3. **Space**: Monitor disk space for cache storage

### Streaming Issues

1. **Market Hours**: Real-time data only available during market hours
2. **Connection**: Ensure WebSocket connection is established
3. **Callbacks**: Verify callback function handles errors

## Migration from IB

The AlpacaMinuteBarManager maintains compatibility with the IB minute data interface:

- Same method names and signatures
- Compatible data models (MinuteBar, MinuteBarCollection)
- IB-style duration strings supported
- Seamless integration with existing code

Key differences:
- No exchange specification needed
- Simpler symbol format
- Better support for extended hours
- More reliable data availability 