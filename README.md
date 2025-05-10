# Multi-Ticker IB Trading Framework

An asynchronous Python framework for automated trading with Interactive Brokers (IB), designed to handle research, order routing, and risk controls for multiple US equity tickers.

## Features

- **Async Connection Handling**: Connect to IBKR using modern async/await patterns
- **Heartbeat Monitoring**: Detect connection issues quickly with customizable heartbeat
- **Automatic Reconnection**: Recover from connection loss with exponential backoff
- **Event Loop Management**: Dedicated event loop for message processing
- **Error Handling**: Comprehensive error categorization and callback system
- **API Client**: Access options flow data and ML predictions 
- **Gateway CLI**: Command-line interface for IB Gateway operations

## Requirements

- Python 3.6+
- Interactive Brokers API (ibapi)
- Additional requirements in `requirements.txt`

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/ibkr-multi-ticker.git
   cd ibkr-multi-ticker
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Make sure Interactive Brokers Trader Workstation (TWS) or IB Gateway is running

## Documentation

| Document | Description |
|----------|-------------|
| [Connection Setup Guide](docs/CONNECTION_SETUP.md) | Configure IB Gateway, WSL connectivity, and Docker deployment |
| [Architecture Documentation](docs/ARCHITECTURE.md) | System design, components, and patterns |
| [Development Roadmap](docs/DEVELOPMENT_ROADMAP.md) | Planned features and enhancements |
| [API Reference](docs/API_REFERENCE.md) | Options Flow Monitor API documentation |

## Basic Usage

```python
import asyncio
from src.connection import IBKRConnection
from src.event_loop import IBKREventLoop
from src.config import Config

async def main():
    # Create configuration
    config = Config(
        host="127.0.0.1",  # For WSL2 to Windows, use your WSL gateway IP
        port=4002,         # Paper trading port (7497 for TWS)
        client_id=1
    )
    
    # Set up event loop
    event_loop = IBKREventLoop()
    event_loop.start()
    
    # Create connection
    connection = IBKRConnection(config)
    
    # Add message processor
    event_loop.add_message_processor(connection.run)
    
    # Connect
    connected = await connection.connect_async()
    
    if connected:
        print("Connected to IBKR!")
        
        # Do something with the connection
        
        # Disconnect when done
        connection.disconnect()
    
    # Stop event loop
    event_loop.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

## Gateway CLI

The system provides a command-line interface for IB Gateway operations:

```bash
# Check Gateway connection
python gateway_cli.py --check

# Start Gateway process
python gateway_cli.py --start --gateway-path /path/to/ibgateway

# Subscribe to market data for a symbol
python gateway_cli.py --subscribe AAPL

# Show current positions
python gateway_cli.py --positions

# Show account information
python gateway_cli.py --account
```

## API Client

The API client provides access to the Multi-Ticker Options Flow Monitor API:

```python
from api_client import ApiClient, TradesEndpoint, PredictionEndpoint

# Create API client (environment variables API_KEY and API_BASE_URL must be set)
client = ApiClient()

# Get recent trades for a ticker
trades_endpoint = TradesEndpoint(client)
recent_trades = trades_endpoint.get_trades('SLV', recent=True, limit=10)

# Get latest ML prediction
prediction_endpoint = PredictionEndpoint(client)
latest_prediction = prediction_endpoint.get_latest_prediction('GLD')
```

See [API Client Documentation](api_client/README.md) for detailed usage examples.

## Directory Structure

| Directory | Description |
|-----------|-------------|
| `src/` | Core connection and event handling code |
| `api_client/` | API client for Options Flow Monitor |
| `tests/` | Test suite for components and integrations |
| `docs/` | Comprehensive documentation |
| `connection/` | IB auth, heartbeat, rate-limit |

## Testing

Run the test suite with:

```bash
# Run the full test suite
pytest

# Run unit tests only
pytest tests/unittest_*.py

# Run a specific test file
pytest tests/test_connection.py
```

## Development

For development and contribution, follow these steps:

1. Run linting checks:
   ```bash
   make lint
   ```

2. Start the development server:
   ```bash
   make run-dev
   ```

## License

MIT License