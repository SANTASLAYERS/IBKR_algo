# Historical Minute Data Module

## Overview

The Minute Data module provides functionality for retrieving, storing, and managing historical minute bar data from Interactive Brokers. This data is essential for technical analysis, strategy development, and backtesting. The module offers efficient caching mechanisms to reduce API calls and improve performance.

## Key Components

### Data Models (`models.py`)

The `models.py` file defines the data structures for minute bar data:

```python
class MinuteBar:
    """
    Represents a single minute bar of OHLCV data.
    """
    def __init__(
        self,
        timestamp: datetime,
        open_price: float,
        high_price: float,
        low_price: float,
        close_price: float,
        volume: int,
        symbol: str,
    ):
        self.timestamp = timestamp
        self.open = open_price
        self.high = high_price
        self.low = low_price
        self.close = close_price
        self.volume = volume
        self.symbol = symbol
        
    # Additional methods for data access and analysis
```

### Cache Management (`cache.py`)

The caching system provides efficient storage and retrieval of minute bar data:

```python
class MinuteDataCache:
    """
    Caches minute bar data to reduce API calls.
    """
    def __init__(self, max_age: timedelta = timedelta(days=1)):
        self.max_age = max_age
        self.cache = {}
        self.last_updated = {}
        
    async def get_data(
        self, 
        symbol: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[MinuteBar]:
        """
        Retrieve data from cache if available and not expired.
        """
        # Cache lookup and management logic
        
    async def store_data(
        self, 
        symbol: str, 
        data: List[MinuteBar]
    ):
        """
        Store data in the cache.
        """
        # Data storage logic
```

### Data Manager (`manager.py`)

The `MinuteDataManager` class orchestrates data retrieval, caching, and processing:

```python
class MinuteDataManager:
    """
    Manages retrieval and processing of minute bar data.
    """
    def __init__(
        self, 
        gateway: IBGateway,
        cache: Optional[MinuteDataCache] = None
    ):
        self.gateway = gateway
        self.cache = cache or MinuteDataCache()
        self.callbacks = {}
        
    async def get_historical_data(
        self, 
        symbol: str, 
        start_date: datetime, 
        end_date: datetime,
        use_cache: bool = True
    ) -> List[MinuteBar]:
        """
        Retrieve historical minute bar data for a symbol.
        """
        # Data retrieval logic with caching
        
    def register_callback(
        self, 
        symbol: str, 
        callback: Callable[[List[MinuteBar]], None]
    ):
        """
        Register a callback for data updates.
        """
        # Callback registration logic
```

## Usage Examples

### Basic Data Retrieval

```python
import asyncio
from datetime import datetime, timedelta
from src.minute_data.manager import MinuteDataManager
from src.gateway import IBGateway

async def fetch_data():
    # Initialize gateway and manager
    gateway = IBGateway(...)
    await gateway.connect_gateway()
    
    # Create minute data manager
    manager = MinuteDataManager(gateway)
    
    # Define date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5)
    
    # Fetch data
    data = await manager.get_historical_data("AAPL", start_date, end_date)
    
    # Process data
    for bar in data:
        print(f"{bar.timestamp}: O={bar.open}, H={bar.high}, L={bar.low}, C={bar.close}, V={bar.volume}")

# Run the async function
asyncio.run(fetch_data())
```

### With Callbacks

```python
import asyncio
from src.minute_data.manager import MinuteDataManager

async def setup_callbacks():
    # Initialize manager (assuming gateway is connected)
    manager = MinuteDataManager(gateway)
    
    # Define callback function
    def on_data_update(bars):
        for bar in bars:
            print(f"New data for {bar.symbol}: {bar.timestamp} - Close: {bar.close}")
    
    # Register callback
    manager.register_callback("AAPL", on_data_update)
    
    # Start data subscription
    await manager.start_subscription("AAPL")
    
    # Run for a while
    await asyncio.sleep(3600)
    
    # Stop subscription
    await manager.stop_subscription("AAPL")
```

## Integration with Other Components

### Event System Integration

The minute data module integrates with the event system:

```python
from src.event.bus import EventBus
from src.event.market import HistoricalDataEvent

# Create event bus and minute data manager
event_bus = EventBus()
manager = MinuteDataManager(gateway, event_bus=event_bus)

# Now minute data updates will generate events on the bus
# that other components can subscribe to
```

### Rule Engine Integration

Minute data can be used in rule conditions:

```python
from src.rule.condition import PricePatternCondition
from src.rule.base import Rule

# Create a condition based on a price pattern
condition = PricePatternCondition(
    symbol="AAPL",
    pattern_type="bullish_engulfing",
    lookback_bars=20
)

# Use this condition in a rule
rule = Rule(
    rule_id="bullish_engulfing_entry",
    name="Enter on Bullish Engulfing Pattern",
    condition=condition,
    action=buy_action,
    enabled=True
)
```

## Performance Considerations

The minute data module is optimized for performance:

1. **Caching**: Reduces unnecessary API calls
2. **Memory Management**: Efficient storage to handle large datasets
3. **Batch Processing**: Processes data in batches to reduce memory pressure
4. **Async Operations**: Uses async I/O for non-blocking operations

## Configuration

Configuration options for the minute data module:

```python
minute_data_config = {
    "cache": {
        "enabled": True,
        "max_age_days": 1,
        "storage_path": "/path/to/cache"
    },
    "data_retrieval": {
        "bar_size": "1 min",
        "what_to_show": "TRADES",
        "use_rth": True
    },
    "subscriptions": {
        "auto_renew": True,
        "update_interval": 60
    }
}
```

## Error Handling

The module implements robust error handling:

1. **API Errors**: Proper handling of IB API errors
2. **Data Validation**: Validation of retrieved data
3. **Timeout Handling**: Graceful handling of timeout situations
4. **Retry Logic**: Automatic retries for transient errors

## CLI Commands

The module provides CLI commands for data retrieval and management:

```bash
# Fetch and display minute data
python gateway_cli.py --minute-data AAPL --days 5

# Save data to CSV
python gateway_cli.py --minute-data AAPL --days 5 --output aapl_data.csv

# Show available data in cache
python gateway_cli.py --list-cached-data
```