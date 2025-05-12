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

## Directory map
| Dir          | Role                                |
|--------------|-------------------------------------|
| `src`        | Core implementation                 |
|  ├─ `connection.py`  | Main connection handling with reconnection logic |
|  ├─ `heartbeat.py`   | Connection heartbeat monitoring |
|  ├─ `event_loop.py`  | Async event processing loop |
|  ├─ `error_handler.py` | IBKR error processing and callbacks |
|  ├─ `config.py`      | Configuration management |
|  ├─ `logger.py`      | Logging functionality |
|  ├─ `gateway.py`     | Enhanced IB Gateway connection |
|  ├─ `subscription_manager.py` | Market data subscription management |
|  ├─ `event/`         | Event system components |
|  ├─ `position/`      | Position management |
|  ├─ `order/`         | Order management |
|  ├─ `rule/`          | Rule engine for trading automation |
|  ├─ `api/`           | API integration components |
|  └─ `minute_data/`   | Historical minute bar data |
| `api_client` | API client for Options Flow Monitor |
| `connection` | IB auth, heartbeat, rate‑limit      |
| `docs`       | Documentation files                 |
| `tests`      | Test suite for src components       |
|  ├─ `event_system/`  | Event system tests |
|  ├─ `order_system/`  | Order management tests |
|  ├─ `rule_engine/`   | Rule engine tests |
|  ├─ `minute_data/`   | Minute data tests |
|  └─ `integration/`   | Integration tests |
| `examples`   | Usage examples and demonstrations   |

## Features

- **Async Connection Handling**: Connect to IBKR using modern async/await patterns
- **Heartbeat Monitoring**: Detect connection issues quickly with customizable heartbeat
- **Automatic Reconnection**: Recover from connection loss with exponential backoff
- **Event Loop Management**: Dedicated event loop for message processing
- **Error Handling**: Comprehensive error categorization and callback system
- **API Client**: Access options flow data and ML predictions
- **Gateway CLI**: Command-line interface for IB Gateway operations
- **Event-Driven Architecture**: Flexible event system for component communication
- **Position Management**: Comprehensive position tracking and risk management
- **Order Management**: Robust order creation, tracking, and lifecycle management
- **Rule Engine**: Configurable rule-based trading strategies without code changes
- **Minute Data**: Historical minute bar data retrieval and caching

## Key Documentation
| Component             | Documentation Location                  |
|-----------------------|----------------------------------------|
| Core Architecture     | `docs/ARCHITECTURE.md`                 |
| Connection System     | `src/CLAUDE.md`, `connection/CLAUDE.md` |
| Order & Position System | `docs/ORDER_POSITION_SYSTEM.md`          |
| Order-IBKR Integration | `docs/ORDER_IBKR_INTEGRATION.md`        |
| Rule Engine           | `src/rule/CLAUDE.md`, `docs/RULE_ENGINE_SPECIFICATION.md`, `docs/RULE_ENGINE_ATR_INTEGRATION.md` |
| API Client            | `api_client/CLAUDE.md`, `api_client/README.md` |
| API Integration       | `src/api/CLAUDE.md`                    |
| Minute Data           | `src/minute_data/CLAUDE.md`, `docs/MINUTE_DATA.md` |
| Testing               | `tests/CLAUDE.md`                      |
| Integration Tests     | `tests/integration/README.md`, `tests/INTEGRATION_TESTING.md` |
| Gateway Testing       | `tests/GATEWAY_TESTING.md`            |
| Order & Position Tests| `tests/ORDER_POSITION_TESTS.md`       |
| Rule Engine Tests     | `tests/RULE_ENGINE_TESTS.md`          |

## Shared constraints
* Async first (`asyncio`, `httpx`); avoid blocking calls.
* All event handlers inherit from `BaseEvent`.
* Each component has clear responsibilities with minimal dependencies.
* Code quality enforced with `mypy`, `ruff`, and `black` (run `make lint` to check).
* Comprehensive test coverage required for all components.
* Production code should never contain debugging print statements (use the logger).

## Testing

The test suite provides comprehensive coverage for all system components. Tests are designed to run without an actual IB API key or connection.

```bash
# Run all tests
pytest

# Run tests with coverage report
pytest --cov=src tests/

# Run specific component tests
pytest tests/test_heartbeat.py
pytest tests/event_system/
pytest tests/rule_engine/

# Run integration tests
pytest tests/integration/
```

See `tests/CLAUDE.md` for detailed testing documentation.

## Gateway Usage
The IB Gateway connection provides functionality for interacting with Interactive Brokers:

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

## API Client Usage

The API client provides access to the Multi-Ticker Options Flow Monitor API. See `api_client/README.md` for detailed usage examples.