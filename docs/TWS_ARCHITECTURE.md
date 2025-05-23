# TWS Trading Framework Architecture

This document outlines the architecture of the TWS Trading Framework, a Python-based system for automated trading with Interactive Brokers Trader Workstation.

## System Overview

The framework is built around a **direct TWS connection** using async Python patterns and an **event-driven architecture** for component communication. It eliminates the complexity of the old IB Gateway system by connecting directly to TWS.

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   TWS (IBKR)    │◄──►│ TWSConnection   │◄──►│   Event Bus     │
│                 │    │                 │    │                 │
│ • Market Data   │    │ • Async Conn.   │    │ • Order Events  │
│ • Order Exec.   │    │ • Reconnection  │    │ • Market Events │
│ • Account Info  │    │ • API Requests  │    │ • Position Evts │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                       ┌─────────────────┐             │
                       │ Position Tracker│◄────────────┤
                       │                 │             │
                       │ • P&L Calc.     │             │
                       │ • Risk Mgmt.    │             │
                       │ • Stop Loss     │             │
                       └─────────────────┘             │
                                                       │
                       ┌─────────────────┐             │
                       │ Order Manager   │◄────────────┘
                       │                 │
                       │ • Order Groups  │
                       │ • Fill Tracking │
                       │ • Lifecycle Mgmt│
                       └─────────────────┘
```

## Core Components

### 1. TWS Connection Layer

#### `TWSConnection` (`src/tws_connection.py`)
- **Purpose**: Direct connection to TWS using IBAPI
- **Key Features**:
  - Async connection management with timeouts
  - Automatic reconnection handling  
  - Basic API operations (time, accounts, order IDs)
  - Thread-safe message processing
  - Connection state callbacks

```python
class TWSConnection(EWrapper, EClient):
    async def connect(self) -> bool:
        """Connect to TWS asynchronously"""
        
    def is_connected(self) -> bool:
        """Check connection status"""
        
    def disconnect(self):
        """Clean disconnection"""
```

#### `TWSConfig` (`src/tws_config.py`)
- **Purpose**: Configuration management for TWS connections
- **Features**:
  - Environment variable loading
  - Configuration validation
  - Default values for paper/live trading

### 2. Event System

#### `EventBus` (`src/event/bus.py`)
- **Purpose**: Central event communication hub
- **Features**:
  - Async event emission and subscription
  - Type-safe event handling
  - Component decoupling
  - Event filtering and routing

#### Event Types (`src/event/`)
- **Market Events**: Price updates, volume data
- **Order Events**: Order status, fills, cancellations
- **Position Events**: Position opens/closes, P&L updates  
- **API Events**: Prediction signals, external data

```python
# Example event flow
price_event = PriceEvent(symbol="AAPL", price=150.0, volume=1000)
await event_bus.emit(price_event)
```

### 3. Order Management

#### `OrderManager` (`src/order/manager.py`)
- **Purpose**: Complete order lifecycle management
- **Features**:
  - Order creation and validation
  - Submission to TWS
  - Status tracking and updates
  - Fill processing

#### `Order` (`src/order/base.py`)
- **Purpose**: Order representation and state management
- **Features**:
  - Order types (Market, Limit, Stop)
  - Fill tracking and average pricing
  - Order groups and relationships

### 4. Position Management

#### `PositionTracker` (`src/position/tracker.py`)
- **Purpose**: Real-time position monitoring
- **Features**:
  - Position creation from fills
  - P&L calculations (realized/unrealized)
  - Risk management integration
  - Position lifecycle tracking

#### `Position` (`src/position/base.py`)
- **Purpose**: Individual position representation
- **Features**:
  - Entry/exit price tracking
  - Stop loss and take profit
  - Position sizing and validation

## Data Flow

### Order Placement Flow
```
1. Trading Logic → OrderManager.create_order()
2. OrderManager → TWSConnection.placeOrder()
3. TWS → Order Status Updates
4. TWSConnection → OrderEvent
5. EventBus → OrderManager.handle_order_event()
6. OrderManager → Position Updates (if filled)
```

### Market Data Flow
```
1. TWS → Market Data Updates
2. TWSConnection → PriceEvent
3. EventBus → PositionTracker.handle_price_event()
4. PositionTracker → P&L Recalculation
5. PositionTracker → Risk Management Checks
```

## Design Patterns

### 1. Event-Driven Architecture
- **Components communicate through events**
- **Loose coupling between modules**
- **Async event processing**

### 2. Observer Pattern
- **EventBus subscribers for event handling**
- **Callback registration for connection events**

### 3. State Machine
- **Order lifecycle state management**
- **Position status transitions**

### 4. Factory Pattern
- **Configuration creation from environment**
- **Event creation with timestamps**

## Configuration

### Environment-Based Configuration
```python
config = TWSConfig.from_env()  # Loads from environment variables
```

### Direct Configuration
```python
config = TWSConfig(
    host="127.0.0.1",
    port=7497,
    client_id=1,
    trading_mode="paper"
)
```

## Safety Features

### Connection Safety
- **Connection timeouts and retries**
- **Graceful disconnection handling**
- **Connection state validation**

### Trading Safety
- **Position size limits**
- **Order validation before submission**
- **Paper trading mode enforcement**
- **Risk management checks**

### Testing Safety
- **Integration tests with safety flags**
- **Immediate order cancellation in tests**
- **Mock objects for unit testing**

## Extension Points

### Custom Event Handlers
```python
async def custom_price_handler(event: PriceEvent):
    # Custom logic for price updates
    pass

await event_bus.subscribe(PriceEvent, custom_price_handler)
```

### Custom Order Types
```python
class CustomOrder(Order):
    # Extended order functionality
    pass
```

### Custom Risk Management
```python
class CustomRiskManager:
    async def check_position_limits(self, position):
        # Custom risk checks
        pass
```

## Performance Considerations

### Async Design
- **Non-blocking I/O operations**
- **Concurrent event processing**
- **Efficient connection management**

### Memory Management
- **Event lifecycle management**
- **Position history cleanup**
- **Connection resource cleanup**

### Latency Optimization
- **Direct TWS connection (no intermediary)**
- **Efficient event routing**
- **Minimal serialization overhead**

## Future Enhancements

### Planned Features
- **Multi-symbol market data streaming**
- **Advanced order types (brackets, OCO)**
- **Portfolio-level risk management**
- **Historical data integration**
- **Performance monitoring and metrics**

### Scalability Improvements
- **Connection pooling for multiple accounts**
- **Event persistence and replay**
- **Distributed trading across multiple instances**

## Testing Architecture

### Unit Tests
- **Mock-based component testing**
- **Event system validation**
- **Configuration testing**

### Integration Tests
- **Real TWS connectivity**
- **Order placement validation**
- **Market data processing**
- **End-to-end workflow testing**

The architecture prioritizes **safety**, **simplicity**, and **reliability** while providing the flexibility needed for automated trading systems. 