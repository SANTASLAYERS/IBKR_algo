# Multi-Ticker Options Flow Monitor API Client

This package provides a Python client for interacting with the Multi-Ticker Options Flow Monitor API. It handles authentication, request preparation, error handling, and provides both synchronous and asynchronous interfaces.

## Installation

```bash
# From the project root
pip install -e .
```

## Configuration

The API client requires an API key and base URL. These can be provided in several ways:

1. Direct initialization:

```python
from api_client import ApiClient

client = ApiClient(
    base_url="https://your-api-server.com/api/v1",
    api_key="your-api-key"
)
```

2. Environment variables:

```
export API_BASE_URL="https://your-api-server.com/api/v1"
export API_KEY="your-api-key"
```

```python
from api_client import ApiClient

client = ApiClient()  # Will use environment variables
```

3. Configuration file (.env):

Create a .env file in your project root:
```
API_BASE_URL=https://your-api-server.com/api/v1
API_KEY=your-api-key
```

Then use the load_env utility:
```python
from api_client import ApiClient
from api_client.utils import load_env

load_env()  # Load variables from .env file
client = ApiClient()  # Will use variables loaded from .env
```

## Usage

### Basic Usage

```python
from api_client import ApiClient, StatusEndpoint, TickersEndpoint

# Create API client
client = ApiClient(
    base_url="https://your-api-server.com/api/v1",
    api_key="your-api-key"
)

# Check system status
status = StatusEndpoint(client)
system_status = status.get_status()
print(f"System status: {system_status['system']['status']}")
print(f"Market hours: {system_status['market']['is_market_hours']}")

# Get supported tickers
tickers = TickersEndpoint(client)
supported_tickers = tickers.get_tickers()
print(f"Supported tickers: {supported_tickers}")

# Clean up
client.close()
```

### With Context Manager

```python
from api_client import ApiClient, TickersEndpoint, TradesEndpoint

with ApiClient(
    base_url="https://your-api-server.com/api/v1",
    api_key="your-api-key"
) as client:
    # Get ticker trades
    trades = TradesEndpoint(client)
    slv_trades = trades.get_trades('SLV', recent=True, limit=5)
    
    print(f"Recent SLV trades: {slv_trades['trades']}")
    print(f"Trade count: {slv_trades['count']}")
```

### Asynchronous Usage

```python
import asyncio
from api_client import ApiClient, PredictionEndpoint

async def main():
    async with ApiClient(
        base_url="https://your-api-server.com/api/v1",
        api_key="your-api-key"
    ) as client:
        # Get latest prediction
        prediction = PredictionEndpoint(client)
        slv_prediction = await prediction.get_latest_prediction_async('SLV')
        
        signal = slv_prediction['prediction']['signal']
        confidence = slv_prediction['prediction']['confidence']
        price = slv_prediction['prediction']['stock_price']
        
        print(f"SLV prediction: {signal} (confidence: {confidence}, price: {price})")

asyncio.run(main())
```

## Available Endpoints

- `StatusEndpoint`: System status information
- `TickersEndpoint`: Supported ticker symbols
- `TradesEndpoint`: Options trades data
- `MinuteDataEndpoint`: Minute-by-minute OHLCV data
- `DivergenceEndpoint`: Delta divergence data
- `PredictionEndpoint`: Machine learning predictions
- `DataRangeEndpoint`: Custom date range data with filters

## Error Handling

The client raises `ApiException` for any API-related errors:

```python
from api_client import ApiClient, ApiException, DivergenceEndpoint

try:
    client = ApiClient(
        base_url="https://your-api-server.com/api/v1",
        api_key="your-api-key"
    )
    
    divergence = DivergenceEndpoint(client)
    data = divergence.get_divergence('INVALID_TICKER')
except ApiException as e:
    print(f"API Error: {e.message}")
    print(f"Status code: {e.status_code}")
finally:
    client.close()
```

## Important Notes

- The base URL should include the API version path (e.g., `/api/v1`) if required by the server
- All endpoint methods are available in both synchronous and asynchronous versions
- For date parameters, you can use string format ('YYYY-MM-DD') or Python's date/datetime objects
- The client automatically handles proper URL construction and authentication headers