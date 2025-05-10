"""
Tests for the position management system.

This module contains tests for the position management components including
position classes and the position tracker.
"""

import asyncio
import pytest
import sys
from datetime import datetime
from pathlib import Path

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.event.bus import EventBus
from src.event.position import PositionStatus, PositionOpenEvent, PositionUpdateEvent, PositionCloseEvent
from src.position.base import Position
from src.position.stock import StockPosition
from src.position.tracker import PositionTracker


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


@pytest.fixture
def position_tracker(event_bus):
    """Create a position tracker for testing."""
    return PositionTracker(event_bus)


class TestPosition:
    """Tests for the Position class."""
    
    def test_position_initialization(self):
        """Test position initialization."""
        position = Position("AAPL")
        
        assert position.symbol == "AAPL"
        assert position.status == PositionStatus.PLANNED
        assert position.quantity == 0.0
        assert position.entry_price is None
        assert position.is_active is False
    
    @pytest.mark.asyncio
    async def test_position_lifecycle(self):
        """Test position lifecycle."""
        position = Position("AAPL")
        
        # Check initial state
        assert position.status == PositionStatus.PLANNED
        
        # Open position
        await position.open(100, 150.0)
        assert position.status == PositionStatus.OPEN
        assert position.quantity == 100
        assert position.entry_price == 150.0
        assert position.is_active is True
        assert position.is_long is True
        
        # Update price
        await position.update_price(160.0)
        assert position.current_price == 160.0
        assert position.unrealized_pnl == 1000.0  # (160-150) * 100
        
        # Close position
        await position.close(170.0, "Take profit")
        assert position.status == PositionStatus.CLOSED
        assert position.exit_price == 170.0
        assert position.realized_pnl == 2000.0  # (170-150) * 100
        assert position.is_active is False
    
    @pytest.mark.asyncio
    async def test_position_adjustments(self):
        """Test position adjustments."""
        position = Position("AAPL")
        
        # Open position
        await position.open(100, 150.0)
        
        # Set stop loss and take profit
        await position.update_stop_loss(145.0)
        await position.update_take_profit(165.0)
        
        assert position.stop_loss == 145.0
        assert position.take_profit == 165.0
        
        # Adjust position
        await position.adjust(quantity=200, stop_loss=140.0, take_profit=170.0)
        
        assert position.quantity == 200
        assert position.stop_loss == 140.0
        assert position.take_profit == 170.0


class TestStockPosition(TestPosition):
    """Tests for the StockPosition class."""
    
    def test_stock_position_initialization(self):
        """Test stock position initialization."""
        position = StockPosition("AAPL")
        
        assert position.symbol == "AAPL"
        assert position.status == PositionStatus.PLANNED
        assert position.beta is None
        assert position.sector is None
    
    @pytest.mark.asyncio
    async def test_stock_info_update(self):
        """Test updating stock info."""
        position = StockPosition("AAPL")
        
        await position.set_stock_info(
            avg_volume=10000000,
            beta=1.2,
            dividend_yield=0.5,
            sector="Technology",
            industry="Consumer Electronics",
            market_cap=2500000000000
        )
        
        assert position.average_volume == 10000000
        assert position.beta == 1.2
        assert position.dividend_yield == 0.5
        assert position.sector == "Technology"
        assert position.industry == "Consumer Electronics"
        assert position.market_cap == 2500000000000
    
    @pytest.mark.asyncio
    async def test_stop_loss_calculation(self):
        """Test stop loss calculation based on ATR."""
        position = StockPosition("AAPL")
        
        # Open position
        await position.open(100, 150.0)
        
        # Calculate stop loss based on ATR
        position.metadata["atr"] = 3.0
        stop_loss = await position.calculate_optimal_stop_loss(atr_multiple=2.0)
        
        assert stop_loss == 144.0  # 150 - (3.0 * 2.0)
        
        # For short positions
        short_position = StockPosition("AAPL")
        await short_position.open(-100, 150.0)
        short_position.metadata["atr"] = 3.0
        short_stop = await short_position.calculate_optimal_stop_loss(atr_multiple=2.0)
        
        assert short_stop == 156.0  # 150 + (3.0 * 2.0)
    
    @pytest.mark.asyncio
    async def test_take_profit_calculation(self):
        """Test take profit calculation based on risk-reward ratio."""
        position = StockPosition("AAPL")
        
        # Open position
        await position.open(100, 150.0)
        await position.update_stop_loss(145.0)
        
        # Calculate take profit based on risk-reward ratio
        take_profit = await position.calculate_optimal_take_profit(risk_reward_ratio=3.0)
        
        assert take_profit == 165.0  # 150 + (5 * 3.0) where 5 is the risk per share (150-145)


class TestPositionTracker:
    """Tests for the PositionTracker class."""
    
    @pytest.mark.asyncio
    async def test_create_position(self, position_tracker):
        """Test creating a position with the tracker."""
        position = await position_tracker.create_stock_position("AAPL")
        
        assert position.symbol == "AAPL"
        assert position.status == PositionStatus.PLANNED
        
        # Get the position by ID
        retrieved = await position_tracker.get_position(position.position_id)
        assert retrieved is position
        
        # Get positions for symbol
        symbol_positions = await position_tracker.get_positions_for_symbol("AAPL")
        assert len(symbol_positions) == 1
        assert symbol_positions[0] is position
    
    @pytest.mark.asyncio
    async def test_position_lifecycle_with_tracker(self, position_tracker, event_bus):
        """Test position lifecycle with the tracker."""
        # Track emitted events
        open_events = []
        update_events = []
        close_events = []
        
        async def on_open(event):
            if isinstance(event, PositionOpenEvent):
                open_events.append(event)
                
        async def on_update(event):
            if isinstance(event, PositionUpdateEvent):
                update_events.append(event)
                
        async def on_close(event):
            if isinstance(event, PositionCloseEvent):
                close_events.append(event)
        
        # Subscribe to events
        await event_bus.subscribe(PositionOpenEvent, on_open)
        await event_bus.subscribe(PositionUpdateEvent, on_update)
        await event_bus.subscribe(PositionCloseEvent, on_close)
        
        # Create a position that opens immediately
        position = await position_tracker.create_stock_position(
            "AAPL",
            quantity=100,
            entry_price=150.0,
            stop_loss=145.0,
            take_profit=165.0
        )
        
        # Wait for events to be processed
        await asyncio.sleep(0.1)
        
        assert len(open_events) == 1
        assert open_events[0].symbol == "AAPL"
        assert open_events[0].quantity == 100
        
        # Update position price
        await position_tracker.update_position_price(position.position_id, 155.0)
        
        # Wait for events to be processed
        await asyncio.sleep(0.1)
        
        assert len(update_events) >= 1
        assert update_events[-1].symbol == "AAPL"
        assert update_events[-1].current_price == 155.0
        
        # Close the position
        await position_tracker.close_position(position.position_id, 160.0, "Take profit")
        
        # Wait for events to be processed
        await asyncio.sleep(0.1)
        
        assert len(close_events) == 1
        assert close_events[0].symbol == "AAPL"
        assert close_events[0].exit_price == 160.0
        assert close_events[0].reason == "Take profit"
        
        # Position should be moved to closed positions
        all_positions = await position_tracker.get_all_positions()
        assert len(all_positions) == 0
        
        closed_positions = await position_tracker.get_closed_positions()
        assert len(closed_positions) == 1
        assert closed_positions[0].position_id == position.position_id
    
    @pytest.mark.asyncio
    async def test_position_adjustments_with_tracker(self, position_tracker, event_bus):
        """Test position adjustments with the tracker."""
        # Create a position
        position = await position_tracker.create_stock_position(
            "AAPL",
            quantity=100,
            entry_price=150.0,
            stop_loss=145.0,
            take_profit=165.0
        )
        
        # Track update events
        update_events = []
        async def on_update(event):
            if isinstance(event, PositionUpdateEvent):
                update_events.append(event)
        
        await event_bus.subscribe(PositionUpdateEvent, on_update)
        
        # Adjust the position
        await position_tracker.adjust_position(
            position.position_id,
            quantity=200,
            stop_loss=140.0,
            take_profit=170.0,
            reason="Position size increase"
        )
        
        # Wait for events to be processed
        await asyncio.sleep(0.1)
        
        assert len(update_events) >= 1
        assert update_events[-1].quantity == 200
        assert update_events[-1].stop_loss_updated is True
        assert update_events[-1].new_stop_loss == 140.0
        assert update_events[-1].take_profit_updated is True
        assert update_events[-1].new_take_profit == 170.0
        assert update_events[-1].reason == "Position size increase"
        
        # Check the position
        updated_position = await position_tracker.get_position(position.position_id)
        assert updated_position.quantity == 200
        assert updated_position.stop_loss == 140.0
        assert updated_position.take_profit == 170.0
    
    @pytest.mark.asyncio
    async def test_multiple_positions(self, position_tracker):
        """Test managing multiple positions."""
        # Create positions for multiple symbols
        aapl_position = await position_tracker.create_stock_position(
            "AAPL",
            quantity=100,
            entry_price=150.0
        )
        
        msft_position = await position_tracker.create_stock_position(
            "MSFT",
            quantity=50,
            entry_price=300.0
        )
        
        googl_position = await position_tracker.create_stock_position(
            "GOOGL",
            quantity=20,
            entry_price=2500.0
        )
        
        # Get all positions
        all_positions = await position_tracker.get_all_positions()
        assert len(all_positions) == 3
        
        # Check has_open_positions
        assert await position_tracker.has_open_positions() is True
        assert await position_tracker.has_open_positions("AAPL") is True
        
        # Check position summary
        summary = await position_tracker.get_position_summary()
        assert summary["total_positions"] == 3
        assert "AAPL" in summary["by_symbol"]
        assert "MSFT" in summary["by_symbol"]
        assert "GOOGL" in summary["by_symbol"]
        
        # Close one position
        await position_tracker.close_position(aapl_position.position_id, 160.0, "Take profit")
        
        # Get all positions again
        all_positions = await position_tracker.get_all_positions()
        assert len(all_positions) == 2
        
        # Check has_open_positions again
        assert await position_tracker.has_open_positions() is True
        assert await position_tracker.has_open_positions("AAPL") is False