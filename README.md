# TWS Trading Framework

A Python framework for automated trading with Interactive Brokers Trader Workstation (TWS), featuring async connectivity, event-driven architecture, and comprehensive testing.

## Features

- **Direct TWS Integration**: Native connection to Trader Workstation (no IB Gateway required)
- **Async Architecture**: Modern async/await patterns for non-blocking operations
- **Event-Driven System**: Robust event bus for order management and position tracking
- **Real-Time Market Data**: Live price feeds and market data processing
- **Order Management**: Complete order lifecycle with fills, cancellations, and status tracking
- **Position Tracking**: Real-time position monitoring with P&L calculations
- **Risk Management**: Built-in controls for position limits and stop losses
- **Comprehensive Testing**: Integration tests with real TWS connections

## Requirements

- Python 3.8+
- Interactive Brokers Trader Workstation (TWS)
- Windows 10/11 (native Windows support)
- Paper trading account (recommended for testing)

## Quick Start

### 1. Installation

```bash
git clone <repository-url>
cd ibkr-tws-framework
pip install -r requirements.txt
```

### 2. Setup TWS

1. **Start TWS** in paper trading mode
2. **Enable API**: Go to Global Configuration → API → Settings
   - Check "Enable ActiveX and Socket Clients"
   - Set Socket port to `7497` (paper trading)
   - Check "Allow connections from localhost only"

### 3. Configuration

Set environment variables:
```bash
export TWS_HOST=127.0.0.1
export TWS_PORT=7497
export TWS_CLIENT_ID=10
export TWS_ACCOUNT=your_paper_account
```

### 4. Test Connection

```bash
# Run basic connectivity tests
python run_integration_tests.py basic

# Test market data (safe - read only)
python run_integration_tests.py market_data
```

## Basic Usage

### Simple TWS Connection

```python
import asyncio
from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection

async def main():
    # Create configuration
    config = TWSConfig(
        host="127.0.0.1",
        port=7497,  # TWS paper trading port
        client_id=1
    )
    
    # Create connection
    connection = TWSConnection(config)
    
    # Connect to TWS
    connected = await connection.connect()
    
    if connected:
        print("Connected to TWS!")
        
        # Request current time
        connection.request_current_time()
        
        # Disconnect when done
        connection.disconnect()
    else:
        print("Failed to connect to TWS")

if __name__ == "__main__":
    asyncio.run(main())
```

### Event-Driven Trading System

```python
import asyncio
from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from src.event.bus import EventBus
from src.event.market import PriceEvent
from src.position.tracker import PositionTracker
from src.order.manager import OrderManager

async def main():
    # Initialize components
    config = TWSConfig.from_env()
    tws_connection = TWSConnection(config)
    event_bus = EventBus()
    position_tracker = PositionTracker(event_bus)
    order_manager = OrderManager(event_bus)
    
    # Connect to TWS
    await tws_connection.connect()
    
    # Initialize trading components
    await position_tracker.initialize()
    await order_manager.initialize()
    
    # Your trading logic here...
    
    # Cleanup
    tws_connection.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

## Testing

The framework includes comprehensive testing at multiple levels:

### Integration Tests (Real TWS)

```bash
# Show available test levels
python run_integration_tests.py --list

# Safe connectivity tests
python run_integration_tests.py basic

# Market data tests (read-only)
python run_integration_tests.py market_data

# Order placement tests (CAUTION - places real orders!)
export TWS_ENABLE_ORDER_TESTS=true
python run_integration_tests.py orders

# Complete system tests
python run_integration_tests.py e2e
```

### Unit Tests

```bash
# Run all unit tests
pytest tests/

# Run specific test categories
pytest tests/event_system/
pytest tests/position/
pytest tests/order/
```

## Project Structure

```
├── src/
│   ├── tws_config.py        # TWS configuration management
│   ├── tws_connection.py    # Direct TWS connection
│   ├── event/               # Event-driven architecture
│   ├── order/               # Order management system
│   ├── position/            # Position tracking
│   └── ...
├── tests/
│   ├── integration/         # Real TWS integration tests
│   ├── event_system/        # Event system unit tests
│   ├── position/            # Position management tests
│   └── order/               # Order management tests
├── docs/                    # Documentation
└── run_integration_tests.py # Safe test runner
```

## Safety Guidelines

### For Development:
- **Always use paper trading accounts**
- **Never run against live money during development**
- **Test incrementally** (basic → market_data → orders)
- **Monitor order placement tests manually**

### For Production:
- **Implement comprehensive risk controls**
- **Use position limits and stop losses**
- **Monitor system health continuously**
- **Have emergency stop procedures**

## Documentation

| Document | Description |
|----------|-------------|
| [TWS Setup Guide](docs/TWS_SETUP_GUIDE.md) | Complete TWS configuration and setup guide |
| [Architecture](docs/TWS_ARCHITECTURE.md) | System architecture and component design |
| [Testing Strategy](tests/COMPREHENSIVE_TESTING_STRATEGY.md) | Complete testing approach and roadmap |
| [Integration Tests](tests/integration/README.md) | How to run integration tests safely |
| [Order System](docs/ORDER_POSITION_SYSTEM.md) | Order and position management details |
| [Event System](docs/EVENT_POSITION_SYSTEM_DOCUMENTATION.md) | Event-driven architecture guide |

## Key Components

### TWS Connection (`src/tws_connection.py`)
- Direct connection to Trader Workstation
- Async connection management with timeouts
- Automatic reconnection handling
- Basic API operations (time, accounts, order IDs)

### Event System (`src/event/`)
- Event bus for component communication
- Market data events, order events, position events
- Async event processing with subscriptions

### Order Management (`src/order/`)
- Complete order lifecycle management
- Order groups and bracket orders
- Fill processing and execution tracking

### Position Tracking (`src/position/`)
- Real-time position monitoring
- P&L calculations (realized and unrealized)
- Risk management integration

## Contributing

1. **Setup development environment**:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

2. **Run tests before committing**:
   ```bash
   pytest tests/
   python run_integration_tests.py basic
   ```

3. **Follow safety guidelines**:
   - Use paper trading only
   - Test incrementally
   - Document changes thoroughly

## License

MIT License - see LICENSE file for details

---

**⚠️ Important**: This framework is designed for educational and development purposes. Always use paper trading accounts for testing and development. Never risk real money without thorough testing and proper risk management procedures.