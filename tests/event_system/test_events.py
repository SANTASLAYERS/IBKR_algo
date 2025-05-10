"""
Tests for the event system.

This module contains tests for the event system components including
the event bus and event classes.
"""

import asyncio
import pytest
import sys
from datetime import datetime
from pathlib import Path

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.event.base import BaseEvent
from src.event.bus import EventBus
from src.event.market import MarketEvent, PriceEvent
from src.event.order import OrderEvent, NewOrderEvent, OrderStatus, OrderType
from src.event.position import PositionEvent, PositionOpenEvent, PositionStatus
from src.event.api import OptionsFlowEvent, PredictionSignalEvent


@pytest.fixture
def event_loop():
    """Create an event loop for testing."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def event_bus():
    """Create an event bus for testing."""
    return EventBus()


class TestBaseEvent:
    """Tests for the BaseEvent class."""
    
    def test_base_event_creation(self):
        """Test creating a base event."""
        event = BaseEvent()
        
        assert event.event_id is not None
        assert isinstance(event.timestamp, datetime)
        assert event.event_type == "BaseEvent"
    
    def test_event_to_dict(self):
        """Test converting an event to a dictionary."""
        event = BaseEvent(source="test")
        event_dict = event.to_dict()
        
        assert event_dict["event_id"] == event.event_id
        assert event_dict["event_type"] == "BaseEvent"
        assert event_dict["source"] == "test"
        assert "timestamp" in event_dict


class TestEventBus:
    """Tests for the EventBus class."""
    
    @pytest.mark.asyncio
    async def test_event_subscription(self, event_bus):
        """Test subscribing to events."""
        events_received = []
        
        async def handler(event):
            events_received.append(event)
        
        await event_bus.subscribe(BaseEvent, handler)
        
        # Emit an event
        event = BaseEvent()
        await event_bus.emit(event)
        
        # Give the event loop a chance to process
        await asyncio.sleep(0.1)
        
        assert len(events_received) == 1
        assert events_received[0].event_id == event.event_id
    
    @pytest.mark.asyncio
    async def test_inheritance_subscription(self, event_bus):
        """Test subscribing to parent event types."""
        base_events = []
        market_events = []
        price_events = []
        
        async def base_handler(event):
            base_events.append(event)
        
        async def market_handler(event):
            market_events.append(event)
            
        async def price_handler(event):
            price_events.append(event)
        
        # Subscribe to different event types
        await event_bus.subscribe(BaseEvent, base_handler)
        await event_bus.subscribe(MarketEvent, market_handler)
        await event_bus.subscribe(PriceEvent, price_handler)
        
        # Emit a price event (which is a MarketEvent which is a BaseEvent)
        event = PriceEvent(symbol="AAPL", price=150.0)
        await event_bus.emit(event)
        
        # Give the event loop a chance to process
        await asyncio.sleep(0.1)
        
        # The event should be received by all three handlers
        assert len(base_events) == 1
        assert len(market_events) == 1
        assert len(price_events) == 1
    
    @pytest.mark.asyncio
    async def test_event_unsubscribe(self, event_bus):
        """Test unsubscribing from events."""
        events_received = []
        
        async def handler(event):
            events_received.append(event)
        
        # Subscribe and then unsubscribe
        await event_bus.subscribe(BaseEvent, handler)
        success = await event_bus.unsubscribe(BaseEvent, handler)
        
        assert success
        
        # Emit an event
        event = BaseEvent()
        await event_bus.emit(event)
        
        # Give the event loop a chance to process
        await asyncio.sleep(0.1)
        
        # The event should not be received
        assert len(events_received) == 0
    
    @pytest.mark.asyncio
    async def test_get_subscriber_count(self, event_bus):
        """Test getting subscriber counts."""
        async def handler1(event): pass
        async def handler2(event): pass
        
        await event_bus.subscribe(BaseEvent, handler1)
        await event_bus.subscribe(BaseEvent, handler2)
        await event_bus.subscribe(MarketEvent, handler1)
        
        # Get counts
        base_count = await event_bus.get_subscriber_count(BaseEvent)
        market_count = await event_bus.get_subscriber_count(MarketEvent)
        
        assert base_count == 2
        assert market_count == 1
        
        # Get all counts
        all_counts = await event_bus.get_subscriber_count()
        assert all_counts["BaseEvent"] == 2
        assert all_counts["MarketEvent"] == 1


class TestEventTypes:
    """Tests for specific event types."""
    
    def test_market_event(self):
        """Test market event creation."""
        event = PriceEvent(symbol="AAPL", price=150.0, volume=1000)
        
        assert event.event_type == "PriceEvent"
        assert event.source == "market"
        assert event.symbol == "AAPL"
        assert event.price == 150.0
        assert event.volume == 1000
    
    def test_order_event(self):
        """Test order event creation."""
        event = NewOrderEvent(
            order_id="123",
            symbol="AAPL",
            status=OrderStatus.CREATED,
            order_type=OrderType.MARKET,
            quantity=100
        )
        
        assert event.event_type == "NewOrderEvent"
        assert event.source == "order"
        assert event.order_id == "123"
        assert event.symbol == "AAPL"
        assert event.status == OrderStatus.CREATED
        assert event.order_type == OrderType.MARKET
        assert event.quantity == 100
    
    def test_position_event(self):
        """Test position event creation."""
        event = PositionOpenEvent(
            position_id="456",
            symbol="AAPL",
            status=PositionStatus.OPEN,
            quantity=100,
            entry_price=150.0
        )
        
        assert event.event_type == "PositionOpenEvent"
        assert event.source == "position"
        assert event.position_id == "456"
        assert event.symbol == "AAPL"
        assert event.status == PositionStatus.OPEN
        assert event.quantity == 100
        assert event.entry_price == 150.0
    
    def test_api_event(self):
        """Test API event creation."""
        event = PredictionSignalEvent(
            symbol="AAPL",
            signal="BUY",
            confidence=0.85,
            price=150.0
        )
        
        assert event.event_type == "PredictionSignalEvent"
        assert event.source == "api"
        assert event.symbol == "AAPL"
        assert event.signal == "BUY"
        assert event.confidence == 0.85
        assert event.price == 150.0