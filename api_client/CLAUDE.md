# Multi-Ticker Options Flow Monitor API Client

## Architecture Overview

The API client is NOT THE IB API and provides a robust interface to the Multi-Ticker Options Flow Monitor API, which delivers options flow data, trade analytics, and ML-based trading signal predictions. The client handles authentication, request preparation, error handling, and provides both synchronous and asynchronous interfaces.

## Key Components

### ApiClient (`client.py`)

The core API client class that manages HTTP connections to the API:

- **Authentication**: Handles API key authentication via headers
- **Request Management**: 
  - Synchronous and asynchronous HTTP requests
  - Proper URL construction
  - Error handling and response processing
- **Resource Management**: 
  - Context manager support for both sync and async contexts
  - Proper cleanup of HTTP resources
- **Error Handling**:
  - Specialized ApiException class
  - Categorization of HTTP and API-level errors
  - Detailed error messages with status codes

```python
# Basic usage
client = ApiClient(
    base_url="https://your-server-address/api/v1",
    api_key="your-api-key"
)
response = client.get('status')
```

### Endpoint Classes (`endpoints.py`)

Specialized classes for each API endpoint:

- **BaseEndpoint**: Common functionality for all endpoints
- **StatusEndpoint**: System status information
- **TickersEndpoint**: Supported ticker symbols
- **TradesEndpoint**: Options trades data 
- **MinuteDataEndpoint**: Minute-by-minute OHLCV data
- **DivergenceEndpoint**: Delta divergence data
- **PredictionEndpoint**: Machine learning predictions
- **DataRangeEndpoint**: Custom date range data with filters

Each endpoint class provides both synchronous and asynchronous methods for accessing the API. They handle parameter formatting, response parsing, and expose a clean interface for the specific data they provide.

```python
# Using endpoints
status = StatusEndpoint(client)
system_status = status.get_status()

tickers = TickersEndpoint(client)
supported_tickers = tickers.get_tickers()

trades = TradesEndpoint(client)
recent_trades = trades.get_trades('SLV', recent=True, limit=5)
```

## Data Flow

1. **Client Initialization**:
   - Create ApiClient with base URL and API key
   - Options for timeout and SSL verification

2. **Endpoint Creation**:
   - Create endpoint instances with client reference
   - Each endpoint handles specific API functionality

3. **Request Execution**:
   - Endpoint methods prepare parameters
   - Client builds request with authentication headers
   - Request sent to API server

4. **Response Processing**:
   - Client verifies response status code
   - JSON parsing and error detection
   - Returns structured data or raises ApiException

5. **Error Handling**:
   - HTTP errors (4xx, 5xx) converted to ApiException
   - Rate limit (429) detection
   - Authentication failures (401)
   - API-level errors in successful responses

## Usage Patterns

### Synchronous Usage

```python
from api_client import ApiClient, TradesEndpoint

# Create client
client = ApiClient(
    base_url="https://your-server-address/api/v1",
    api_key="your-api-key"
)

# Use with context manager for automatic cleanup
with ApiClient(base_url="...", api_key="...") as client:
    trades = TradesEndpoint(client)
    slv_trades = trades.get_trades('SLV', recent=True, limit=5)
    print(f"Recent SLV trades: {slv_trades['trades']}")
```

### Asynchronous Usage

```python
import asyncio
from api_client import ApiClient, PredictionEndpoint

async def main():
    # Async context manager
    async with ApiClient(base_url="...", api_key="...") as client:
        prediction = PredictionEndpoint(client)
        latest = await prediction.get_latest_prediction_async('SLV')
        print(f"Latest prediction: {latest['prediction']['signal']}")

asyncio.run(main())
```

### Alternative Configuration Methods

```python
# From environment variables
import os
os.environ['API_BASE_URL'] = "https://your-server-address/api/v1"
os.environ['API_KEY'] = "your-api-key"
client = ApiClient()  # Uses environment variables

# From .env file
from api_client.utils import load_env
load_env()  # Load from .env file
client = ApiClient()  # Uses loaded environment variables
```

## Error Handling

```python
from api_client import ApiClient, ApiException

try:
    client = ApiClient(base_url="...", api_key="...")
    response = client.get('invalid-endpoint')
except ApiException as e:
    print(f"API Error: {e.message}")
    print(f"Status code: {e.status_code}")
    if e.response:
        print(f"Response data: {e.response}")
```

## Design Patterns

The API client employs several design patterns:

1. **Factory Pattern**: Creating HTTP clients for sync and async contexts
2. **Adapter Pattern**: Converting HTTP responses to structured data
3. **Strategy Pattern**: Different endpoint implementations for API areas
4. **Decorator Pattern**: Methods adding functionality to base request methods
5. **Repository Pattern**: Endpoint classes as data access repositories

## Best Practices

When using the API client:

1. **Use Context Managers**: For proper resource cleanup
2. **Handle Exceptions**: Always catch ApiException
3. **Consider Rate Limits**: The API has rate limits per endpoint
4. **Choose Appropriate Methods**: Use async methods in async contexts
5. **Parameterize Requests**: Use endpoint parameters for filtering data
6. **Set Reasonable Timeouts**: Adjust timeout for data-intensive endpoints

## Testing

The client includes comprehensive test coverage:

- **Unit Tests**: Mock-based testing of client and endpoints 
- **Integration Tests**: Testing against the actual API server
- **Error Handling**: Tests for various error conditions
- **Edge Cases**: Parameter validation and extreme values

```bash
# Run tests
pytest tests/test_api_client.py tests/test_api_endpoints.py
```

## Extending the Client

When extending the client:

1. **Subclass BaseEndpoint**: For new endpoint types
2. **Follow Parameter Patterns**: Use consistent parameter naming
3. **Provide Both Interfaces**: Implement both sync and async methods
4. **Handle API Errors**: Use ApiException for error consistency
5. **Document Methods**: Include parameter and return type documentation
6. **Test New Functionality**: Add tests for new endpoint methods