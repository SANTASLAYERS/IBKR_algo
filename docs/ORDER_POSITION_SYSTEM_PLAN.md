# Event-Driven Order and Position Management System Plan

## Overview

This document outlines the implementation plan for an event-driven order and position management system for the IBKR Trading Framework. The system will focus exclusively on stock trading while leveraging the options flow data and predictions from the API client.

## Core Components

### 1. Event System
- Event Bus implementation for publish-subscribe pattern
- Hierarchical event type structure
- Handler registration and dispatching mechanism

### 2. Position Management (Stocks Only)
- Stock position tracking and lifecycle management
- Risk metrics calculation (P&L, exposure)
- Position state transitions

### 3. Order Management
- Order creation and tracking
- Order state machine implementation
- Bracket and OCO order management

### 4. API Integration
- Processing prediction signals from API client
- Converting signals to actionable trading decisions
- Placeholder infrastructure for future divergence and trade data processing

### 5. Rule Engine
- Condition evaluation framework
- Action execution system
- Rule priority and cooldown management

## Event Hierarchy

```
BaseEvent
├── MarketEvent
│   ├── PriceEvent
│   ├── IndicatorEvent
│   └── VolumeEvent
├── OrderEvent
│   ├── NewOrderEvent
│   ├── FillEvent
│   ├── CancelEvent
│   └── RejectEvent
├── PositionEvent
│   ├── PositionOpenEvent
│   ├── PositionUpdateEvent
│   └── PositionCloseEvent
├── OptionsFlowEvent
│   ├── PredictionSignalEvent
│   └── FlowThresholdEvent (placeholder)
└── SystemEvent
    ├── ConnectEvent
    ├── DisconnectEvent
    └── ErrorEvent
```

## Implementation Phases

### Phase 1: Event System and API Integration
- Create event base classes and hierarchy
- Implement event bus with subscription management
- Set up API client integration for prediction signals
- Add placeholder functions for future trade and divergence processing

### Phase 2: Position Management
- Implement stock position class
- Create position lifecycle state machine
- Add position tracking and management functions

### Phase 3: Order Management
- Implement order classes and state machine
- Create order group management (brackets, OCO)
- Connect orders to IBKR gateway

### Phase 4: Rule Engine
- Implement rule condition and action framework
- Create rule registry and evaluation system
- Add rule prioritization and scheduling

### Phase 5: Integration and Testing
- Connect all components into cohesive system
- Implement comprehensive logging and error handling
- Create test cases for common scenarios

## API Integration Design

The system will initially focus on integrating with the prediction signals from the API client, with placeholders for future divergence and trade data integration:

```python
class OptionsFlowMonitor:
    """Monitors options flow API data and generates events."""
    
    def __init__(self, event_bus, api_client):
        self.event_bus = event_bus
        self.api_client = api_client
        self.thresholds = {
            'prediction_confidence_min': 0.75
        }
        
    async def start_monitoring(self):
        """Start the monitoring process."""
        # Schedule periodic prediction checking
        asyncio.create_task(self._poll_predictions())
        
    async def _poll_predictions(self):
        """Poll for new predictions from the API."""
        while True:
            try:
                # For each configured ticker
                for ticker in self.configured_tickers:
                    prediction = await self.api_client.prediction.get_latest_prediction_async(ticker)
                    
                    # Check confidence threshold
                    if prediction['prediction']['confidence'] >= self.thresholds['prediction_confidence_min']:
                        # Create and emit event
                        event = PredictionSignalEvent(
                            ticker=ticker,
                            signal=prediction['prediction']['signal'],
                            confidence=prediction['prediction']['confidence'],
                            price=prediction['prediction']['stock_price']
                        )
                        await self.event_bus.emit(event)
            except Exception as e:
                logger.error(f"Error polling predictions: {e}")
                
            # Sleep before next poll
            await asyncio.sleep(60)  # Check every minute
            
    async def _poll_trades(self):
        """Poll for unusual options trades (placeholder for future implementation)."""
        # This will be implemented in the future
        pass
        
    async def _poll_divergence(self):
        """Poll for delta divergence changes (placeholder for future implementation)."""
        # This will be implemented in the future
        pass
```

## Rule Examples

```python
# Example: Take position based on high-confidence API prediction
Rule(
    name="PredictionEntry",
    condition=lambda event: (
        isinstance(event, PredictionSignalEvent) and 
        event.confidence > 0.85 and 
        event.signal == "BUY"
    ),
    action=lambda event, context: context.create_stock_position(
        symbol=event.ticker,
        size=calculate_position_size(event.ticker, context.account_value),
        entry_type="market",
        stop_loss_pct=0.03,
        take_profit_pct=0.09
    ),
    priority=1
)

# Example: Trailing stop adjustment when position is profitable
Rule(
    name="TrailingStopAdjustment",
    condition=lambda position: position.unrealized_profit_pct > 0.05,
    action=lambda position: position.update_stop_loss(
        new_level=max(position.current_stop, position.current_price * 0.97)
    ),
    priority=2
)
```

## Directory Structure

```
src/
  ├── event/
  │   ├── __init__.py
  │   ├── base.py       # Base event classes
  │   ├── bus.py        # Event bus implementation
  │   ├── market.py     # Market-related events
  │   ├── order.py      # Order-related events
  │   ├── position.py   # Position-related events
  │   └── api.py        # API and options flow events
  │
  ├── position/
  │   ├── __init__.py
  │   ├── base.py       # Base position class
  │   ├── stock.py      # Stock position implementation
  │   ├── tracker.py    # Position tracking and management
  │   └── risk.py       # Risk calculation and metrics
  │
  ├── order/
  │   ├── __init__.py
  │   ├── base.py       # Base order class
  │   ├── types.py      # Different order types
  │   ├── group.py      # Order group management
  │   └── manager.py    # Order tracking and execution
  │
  ├── rule/
  │   ├── __init__.py
  │   ├── base.py       # Rule definition and execution
  │   ├── condition.py  # Condition implementations
  │   ├── action.py     # Action implementations
  │   └── engine.py     # Rule evaluation engine
  │
  └── api/
      ├── __init__.py
      ├── monitor.py    # API monitoring and event generation
      └── signals.py    # Signal processing and interpretation
```

## Testing Strategy

The implementation will include:

1. Unit tests for individual components
2. Integration tests for component interactions
3. Mock-based tests for API and gateway interactions
4. Scenario-based tests for common trading situations

## Next Steps

1. Implement the event system foundation
2. Create the API monitor with prediction signal processing
3. Implement position management system
4. Add order management capabilities
5. Create the rule engine
6. Integrate all components

This plan provides a framework for implementing an event-driven order and position management system focused initially on stock trading while leveraging prediction signals from the API client.