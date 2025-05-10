# Minute Bar Data Module

This module provides functionality for fetching, processing, and caching historical minute bar data from Interactive Brokers.

## Overview

The minute data module allows you to:

1. Fetch historical minute-level OHLCV (Open, High, Low, Close, Volume) data from IB
2. Cache the data locally to reduce API calls
3. Export data in different formats (CSV, JSON)
4. Process and analyze minute data programmatically

## Components

### MinuteBar Model

The `MinuteBar` class represents a single minute bar with the following properties:

- `symbol`: Ticker symbol
- `timestamp`: Bar timestamp (timezone-aware)
- `open_price`: Opening price
- `high_price`: Highest price
- `low_price`: Lowest price
- `close_price`: Closing price
- `volume`: Trading volume
- `count`: Number of trades (optional)
- `wap`: Weighted average price (optional)

### MinuteBarCollection

The `MinuteBarCollection` class stores and manages a collection of minute bars for a specific symbol:

- Keeps bars sorted by timestamp
- Provides conversion to CSV, JSON, and pandas DataFrame
- Validates that all bars belong to the same symbol
- Supports various I/O operations

### MinuteBarManager

The `MinuteBarManager` class handles requests to IB API for historical minute data:

- Interacts with IB API to request historical data
- Processes API callbacks and converts data to MinuteBar objects
- Provides both synchronous and asynchronous request methods
- Integrates with caching for performance

### MinuteDataCache

The `MinuteDataCache` class provides caching functionality:

- Stores and retrieves minute data from local filesystem
- Handles cache expiration
- Manages cache size limits
- Provides key generation based on request parameters

## CLI Usage

The minute data module is integrated with the gateway CLI. You can fetch and manage minute data using the following commands:

```bash
# Fetch 1-minute bars for the last day for AAPL
python gateway_cli.py --fetch-minutes AAPL

# Fetch 5-minute bars for the last week
python gateway_cli.py --fetch-minutes AAPL --duration "1 W" --bar-size "5 mins"

# Specify an end date (default is now)
python gateway_cli.py --fetch-minutes AAPL --end-date "2023-05-01 16:00:00"

# Save to file in CSV format
python gateway_cli.py --fetch-minutes AAPL --output-file aapl_minutes.csv

# Save to file in JSON format
python gateway_cli.py --fetch-minutes AAPL --output-format json --output-file aapl_minutes.json

# Bypass cache
python gateway_cli.py --fetch-minutes AAPL --no-cache
```

## Programmatic Usage

### Basic Usage

```python
import asyncio
from datetime import datetime, timezone
from ibapi.contract import Contract
from src.gateway import IBGateway, IBGatewayConfig

async def fetch_minute_data():
    # Create configuration
    config = IBGatewayConfig(
        host="127.0.0.1",
        port=4002,  # Paper trading port
        client_id=1
    )
    
    # Create gateway
    gateway = IBGateway(config)
    
    # Connect
    connected = await gateway.connect_async()
    
    if connected:
        # Create contract
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        
        try:
            # Fetch minute bars for the last day
            bars = await gateway.minute_bar_manager.fetch_minute_bars(
                contract=contract,
                duration="1 D",
                bar_size="1 min"
            )
            
            print(f"Retrieved {len(bars)} minute bars")
            
            # Print first 5 bars
            for i in range(min(5, len(bars))):
                bar = bars[i]
                print(f"{bar.timestamp}: Open={bar.open_price}, High={bar.high_price}, "
                      f"Low={bar.low_price}, Close={bar.close_price}, Volume={bar.volume}")
                
            # Convert to pandas DataFrame
            df = bars.to_dataframe()
            print("\nDataFrame head:")
            print(df.head())
            
        finally:
            # Disconnect
            gateway.disconnect()
    
if __name__ == "__main__":
    asyncio.run(fetch_minute_data())
```

### Using Cache

```python
# Fetch with caching enabled (default)
bars = await gateway.minute_bar_manager.fetch_minute_bars(
    contract=contract,
    duration="1 D",
    bar_size="1 min",
    use_cache=True  # This is the default
)

# Disable cache for real-time data
bars = await gateway.minute_bar_manager.fetch_minute_bars(
    contract=contract,
    duration="1 D",
    bar_size="1 min",
    use_cache=False
)

# Access cache directly
cache = gateway.minute_bar_manager.cache
cache.clear()  # Clear all cached data
cache.clear_expired()  # Clear only expired entries
```

## Supported Parameters

### Duration Strings

- `x S`: Seconds
- `x D`: Days
- `x W`: Weeks
- `x M`: Months
- `x Y`: Years

Examples: `"1 D"`, `"2 W"`, `"3 M"`, `"1 Y"`

### Bar Size Strings

- `"1 secs"`: 1 second bars
- `"5 secs"`: 5 second bars
- `"10 secs"`: 10 second bars
- `"15 secs"`: 15 second bars
- `"30 secs"`: 30 second bars
- `"1 min"`: 1 minute bars
- `"2 mins"`: 2 minute bars
- `"3 mins"`: 3 minute bars
- `"5 mins"`: 5 minute bars
- `"10 mins"`: 10 minute bars
- `"15 mins"`: 15 minute bars
- `"20 mins"`: 20 minute bars
- `"30 mins"`: 30 minute bars
- `"1 hour"`: 1 hour bars
- `"2 hours"`: 2 hour bars
- `"3 hours"`: 3 hour bars
- `"4 hours"`: 4 hour bars
- `"8 hours"`: 8 hour bars
- `"1 day"`: 1 day bars
- `"1 week"`: 1 week bars
- `"1 month"`: 1 month bars

## Data Limitations

- Historical data is subject to IB's data subscription level
- Pacing violations may occur if too many requests are made in a short time
- IB's historical data may have gaps or inaccuracies for certain time periods
- Only SMART exchange is currently supported for US equities

## Error Handling

The module handles common IB API errors:

- Pacing violations (error code 162)
- No data returned errors
- Connection issues
- Request timeout errors

Errors are propagated as exceptions that can be caught and handled in your code.