# IBKR Connection Module

## Overview
The connection module provides robust connection handling for Interactive Brokers (IB) API with asynchronous support, heartbeat monitoring, and automatic reconnection capabilities.

## Components

### Connection Management
- **Authentication**: Secure connection to IBKR's TWS or Gateway
- **Heartbeat Monitoring**: Detection of connection issues with customizable intervals
- **Rate Limiting**: Protection against API rate limits
- **Reconnection Logic**: Automatic reconnection with exponential backoff

## Structure
The connection module relies on core implementations in the src directory:
- `src/connection.py`: Core connection functionality
- `src/heartbeat.py`: Heartbeat monitoring system
- `src/error_handler.py`: Error processing and callback system

## Usage
```python
import asyncio
from connection import IBKRConnectionManager
from src.config import Config

async def main():
    config = Config(
        host="127.0.0.1",
        port=7497,  # 7497 for TWS, 4002 for Gateway in paper trading
        client_id=1
    )

    connection = IBKRConnectionManager(config)
    connected = await connection.connect()

    if connected:
        print("Connected to IBKR!")
        # ... perform operations ...
        await connection.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

## Configuration
The connection can be configured using:
1. Connection parameters (host, port, client_id)
2. Heartbeat settings (interval, timeout)
3. Reconnection policy (delay, max_attempts)

## Error Handling
The connection module provides comprehensive error handling:
- Connection errors
- Timeout detection
- Heartbeat failures
- Rate limit management

## Future Implementations
This directory will contain enhanced connection components that build upon the core functionality in the src directory:

### WebSocketProvider
Real-time market data streaming using WebSockets, enabling:
- Higher-performance data feeds
- Reduced latency for price updates
- Support for multiple subscription models
- Bandwidth optimization for high-volume data

```python
# Example of planned WebSocket implementation
async with WebSocketProvider(config) as ws:
    await ws.subscribe("AAPL", data_type="TRADES")
    await ws.subscribe("MSFT", data_type="QUOTES")

    async for update in ws.updates():
        if update.ticker == "AAPL":
            print(f"AAPL trade: {update.price} x {update.size}")
```

### Other Planned Components
- **IBKRConnectionManager**: High-level connection management
- **AuthManager**: Authentication handling for different account types
- **RateLimiter**: Intelligent API rate limit handling with quota management
- **ConnectionMonitor**: Enhanced connection monitoring with metrics
- **ConnectionPool**: Management of multiple concurrent connections
- **CircuitBreaker**: Prevent cascade failures during API instability
- **SessionManager**: Persistent session state across reconnections