# Project: Multi‑Ticker IB (Interactive Brokers) Trading Framework
## Purpose
Automate research, order routing, and risk controls for many US‑equity tickers.

## How Claude should help
1. Answer architecture questions using the component docs below.
2. Generate or refactor code that **passes mypy, Ruff, Black** (`make lint`).
3. Never touch secrets in `.env`.
4. Ask before installing new PyPI packages.

## Key commands
| Task                  | Command                |
|-----------------------|------------------------|
| Dev server            | `make run-dev`         |
| Unit tests            | `pytest -q`            |
| Style check & format  | `make lint`            |
| DB migrate            | `alembic upgrade head` |
| Gateway CLI           | `python gateway_cli.py` |

## Directory map (Updated)
| Dir          | Role                                |
|--------------|-------------------------------------|
| `src`        | Connection with async/heartbeat     |
|  ├─ `connection.py`  | Main connection handling with reconnection logic |
|  ├─ `heartbeat.py`   | Connection heartbeat monitoring |
|  ├─ `event_loop.py`  | Async event processing loop |
|  ├─ `error_handler.py` | IBKR error processing and callbacks |
|  ├─ `config.py`      | Configuration management |
|  ├─ `logger.py`      | Logging functionality |
|  └─ `gateway.py`     | Enhanced IB Gateway connection |
| `api_client` | API client for Options Flow Monitor |
|  ├─ `client.py`      | Base API client with request handling |
|  ├─ `endpoints.py`   | Endpoint-specific API methods |
|  ├─ `utils.py`       | Utility functions for the API client |
|  └─ `README.md`      | API client usage documentation |
| `connection` | IB auth, heartbeat, rate‑limit      |
|  └─ `__init__.py`    | Package initialization |
| `docs`       | Documentation files                 |
|  ├─ `ARCHITECTURE.md` | System architecture overview |
|  ├─ `CONNECTION_SETUP.md` | Connection configuration guide |
|  ├─ `DEVELOPMENT_ROADMAP.md` | Future development plans |
|  └─ `API_REFERENCE.md` | Detailed API endpoint documentation |
| `tests`      | Test suite for src components       |
|  ├─ `test_connection.py` | Connection tests with mocks |
|  ├─ `test_heartbeat.py`  | Heartbeat monitor tests |
|  ├─ `test_event_loop.py` | Event loop tests |
|  ├─ `test_gateway.py`    | Gateway connection tests |
|  ├─ `test_live_connection.py` | Live IBKR Gateway connectivity tests |
|  ├─ `test_gateway_connectivity.py` | Gateway connectivity test script |
|  ├─ `test_reconnection.py` | Reconnection capability test script |
|  ├─ `test_api_client.py` | API client tests |
|  ├─ `test_api_endpoints.py` | API endpoint tests |
|  ├─ `test_api_fixed.py` | API fixed tests |
|  ├─ `test_api_live.py` | Live API connectivity tests |
|  ├─ `conftest.py`    | Pytest fixtures and setup |
|  ├─ `mocks.py`       | Mock objects for testing |
|  ├─ `unittest_heartbeat.py` | Heartbeat unit tests |
|  ├─ `unittest_runner.py` | Unit test runner |
|  └─ `CLAUDE.md`      | Test suite documentation |
| `gateway_cli.py` | Command-line interface for IB Gateway operations |
| `check_env.py` | Script to check environment setup |
| `main.py` | Main application entry point |
| `README.md` | Project overview and usage instructions |
| `requirements.txt` | Project dependencies |
| `Makefile` | Build and development automation |

## Features

- **Async Connection Handling**: Connect to IBKR using modern async/await patterns
- **Heartbeat Monitoring**: Detect connection issues quickly with customizable heartbeat
- **Automatic Reconnection**: Recover from connection loss with exponential backoff
- **Event Loop Management**: Dedicated event loop for message processing
- **Error Handling**: Comprehensive error categorization and callback system
- **API Client**: Access options flow data and ML predictions 
- **Gateway CLI**: Command-line interface for IB Gateway operations

## Documentation
| File                       | Description                               |
|----------------------------|-------------------------------------------|
| `README.md`                | Project overview and usage instructions    |
| `docs/ARCHITECTURE.md`     | System architecture overview              |
| `docs/CONNECTION_SETUP.md` | Connection configuration guide            |
| `docs/DEVELOPMENT_ROADMAP.md` | Future development plans               |
| `docs/API_REFERENCE.md`    | Detailed API endpoint documentation       |
| `src/CLAUDE.md`            | Source code architecture documentation    |
| `tests/CLAUDE.md`          | Test suite documentation                  |
| `api_client/CLAUDE.md`     | API client architecture documentation     |
| `api_client/README.md`     | API client usage guide                    |

## Shared constraints
* Async first (`asyncio`, `httpx`); avoid blocking calls.
* All event handlers inherit from `BaseEvent`.
* Use dependency‑injection via `container.py`.

## Testing

The test suite provides comprehensive coverage for both the IBKR connection system and the API client. Tests are designed to run without an actual IB API key or connection.

```bash
# Run all tests
pytest

# Run tests with coverage report
pytest --cov=src tests/

# Run specific test files
pytest tests/test_heartbeat.py
pytest tests/test_connection.py

# Component-specific tests
pytest tests/test_api_client.py tests/test_api_endpoints.py
```

See `tests/CLAUDE.md` for detailed testing documentation.

## Gateway Usage
The IB Gateway connection provides enhanced functionality for interacting with Interactive Brokers:

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

Configuration options can be provided via command line or config file:
```bash
python gateway_cli.py --config config.ini --trading-mode paper
```

_For external predictions see **docs/API_REFERENCE.md**._

## API Client Usage

The API client provides access to the Multi-Ticker Options Flow Monitor API:

```python
from api_client import ApiClient, TradesEndpoint, PredictionEndpoint

# Create API client (environment variables API_KEY and API_BASE_URL must be set)
client = ApiClient()

# Or specify directly
client = ApiClient(
    base_url="https://your-server-address/api/v1",
    api_key="your-api-key"
)

# Get recent trades for a ticker
trades_endpoint = TradesEndpoint(client)
recent_trades = trades_endpoint.get_trades('SLV', recent=True, limit=10)
print(f"Recent SLV trades: {recent_trades['trades']}")

# Get latest ML prediction
prediction_endpoint = PredictionEndpoint(client)
latest_prediction = prediction_endpoint.get_latest_prediction('GLD')
print(f"GLD prediction: {latest_prediction['prediction']['signal']}")
print(f"Confidence: {latest_prediction['prediction']['confidence']}")

# Close client when done
client.close()
```

For asynchronous usage:

```python
import asyncio
from api_client import ApiClient, PredictionEndpoint

async def main():
    async with ApiClient(base_url="...", api_key="...") as client:
        prediction = PredictionEndpoint(client)
        latest = await prediction.get_latest_prediction_async('SLV')
        print(f"Latest prediction: {latest['prediction']['signal']}")

asyncio.run(main())
```

See `api_client/README.md` for detailed usage examples.