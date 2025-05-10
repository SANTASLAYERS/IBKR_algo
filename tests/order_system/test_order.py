"""
Tests for the order management system.

This module contains tests for the order management components including
order classes and the order manager.
"""

import asyncio
import pytest
import sys
from datetime import datetime
from pathlib import Path

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.event.bus import EventBus
from src.order.base import Order, OrderStatus, OrderType, TimeInForce, OrderSide
from src.order.group import OrderGroup, BracketOrder, OCOGroup
from src.order.manager import OrderManager


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
def order_manager(event_bus):
    """Create an order manager for testing."""
    return OrderManager(event_bus)


class TestOrder:
    """Tests for the Order class."""
    
    def test_order_initialization(self):
        """Test order initialization."""
        order = Order(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.MARKET
        )
        
        assert order.symbol == "AAPL"
        assert order.quantity == 100
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.MARKET
        assert order.status == OrderStatus.CREATED
        assert order.is_active is False
        assert order.is_pending is True
    
    def test_order_side_inference(self):
        """Test order side inference from quantity."""
        buy_order = Order("AAPL", 100)
        sell_order = Order("AAPL", -100)
        
        assert buy_order.side == OrderSide.BUY
        assert sell_order.side == OrderSide.SELL
    
    def test_order_validation(self):
        """Test order validation."""
        # Limit order requires limit price
        with pytest.raises(ValueError):
            Order("AAPL", 100, OrderType.LIMIT)
        
        # Stop order requires stop price
        with pytest.raises(ValueError):
            Order("AAPL", 100, OrderType.STOP)
        
        # Valid limit order
        limit_order = Order("AAPL", 100, OrderType.LIMIT, limit_price=150.0)
        assert limit_order.limit_price == 150.0
        
        # Valid stop order
        stop_order = Order("AAPL", 100, OrderType.STOP, stop_price=140.0)
        assert stop_order.stop_price == 140.0
    
    def test_order_status_transitions(self):
        """Test order status transitions."""
        order = Order("AAPL", 100, OrderType.MARKET)
        
        # Initial status
        assert order.status == OrderStatus.CREATED
        
        # Update status to submitted
        order.update_status(OrderStatus.SUBMITTED)
        assert order.status == OrderStatus.SUBMITTED
        assert order.is_pending is True
        
        # Update status to accepted
        order.update_status(OrderStatus.ACCEPTED)
        assert order.status == OrderStatus.ACCEPTED
        assert order.is_active is True
        
        # Update status to filled
        order.update_status(OrderStatus.FILLED)
        assert order.status == OrderStatus.FILLED
        assert order.is_filled is True
        assert order.is_complete is True
        assert order.is_active is False
    
    def test_order_fill(self):
        """Test order fill processing."""
        order = Order("AAPL", 100, OrderType.MARKET)
        
        # Add a partial fill
        success = order.add_fill(50, 150.0)
        assert success is True
        assert order.filled_quantity == 50
        assert order.remaining_quantity == 50
        assert order.avg_fill_price == 150.0
        assert order.status == OrderStatus.PARTIALLY_FILLED
        
        # Add another partial fill at a different price
        success = order.add_fill(25, 152.0)
        assert success is True
        assert order.filled_quantity == 75
        assert order.remaining_quantity == 25
        # The exact value might vary slightly due to floating point arithmetic
        assert round(order.avg_fill_price, 2) == 150.67  # (50*150 + 25*152) / 75 ≈ 150.67
        
        # Complete the fill
        success = order.add_fill(25, 153.0)
        assert success is True
        assert order.filled_quantity == 100
        assert order.remaining_quantity == 0
        assert order.status == OrderStatus.FILLED
        assert order.avg_fill_price == 151.25  # (50*150 + 25*152 + 25*153) / 100 = 151.25
    
    def test_order_cancel(self):
        """Test order cancellation."""
        order = Order("AAPL", 100, OrderType.MARKET)
        
        # Update status to submitted
        order.update_status(OrderStatus.SUBMITTED)
        
        # Cancel the order
        success = order.cancel("Testing cancellation")
        assert success is True
        assert order.status == OrderStatus.PENDING_CANCEL
        assert order.reason == "Testing cancellation"
        
        # Update status to cancelled
        order.update_status(OrderStatus.CANCELLED)
        assert order.status == OrderStatus.CANCELLED
        assert order.is_complete is True
        
        # Try to cancel a completed order
        success = order.cancel("Should fail")
        assert success is False


class TestOrderGroup:
    """Tests for the OrderGroup class."""
    
    def test_basic_order_group(self):
        """Test basic OrderGroup functionality."""
        group = OrderGroup()
        
        # Add orders to the group
        order1 = Order("AAPL", 100, OrderType.MARKET)
        order2 = Order("AAPL", -100, OrderType.LIMIT, limit_price=160.0)
        
        group.add_order(order1)
        group.add_order(order2)
        
        # Check group properties
        assert len(group.get_orders()) == 2
        assert group.is_active() is False  # Orders are not yet active
        
        # Update order status
        order1.update_status(OrderStatus.ACCEPTED)
        assert group.is_active() is True
        
        # Check order retrieval
        retrieved_order = group.get_order(order1.order_id)
        assert retrieved_order is order1
        
        # Test cancel_all
        order1.update_status(OrderStatus.WORKING)
        order2.update_status(OrderStatus.WORKING)
        assert group.is_active() is True
        
        cancelled = group.cancel_all("Testing group cancellation")
        assert cancelled == 2
        assert order1.status == OrderStatus.PENDING_CANCEL
        assert order2.status == OrderStatus.PENDING_CANCEL
    
    def test_bracket_order(self):
        """Test BracketOrder functionality."""
        # Create a bracket order for a buy
        bracket = BracketOrder(
            symbol="AAPL",
            quantity=100,
            entry_price=150.0,
            stop_loss_price=145.0,
            take_profit_price=160.0,
            entry_type=OrderType.LIMIT
        )
        
        # Check bracket properties
        assert bracket.entry_order.symbol == "AAPL"
        assert bracket.entry_order.quantity == 100
        assert bracket.entry_order.limit_price == 150.0
        assert bracket.stop_loss_price == 145.0
        assert bracket.take_profit_price == 160.0
        assert bracket.child_orders_created is False
        
        # Simulate entry fill and create child orders
        stop_id, take_id = bracket.handle_entry_fill(150.0)
        assert bracket.child_orders_created is True
        assert len(bracket.get_orders()) == 3
        
        # Check stop loss order
        stop_order = bracket.orders[stop_id]
        assert stop_order.symbol == "AAPL"
        assert stop_order.quantity == -100  # Opposite direction of entry
        assert stop_order.order_type == OrderType.STOP
        assert stop_order.stop_price == 145.0
        
        # Check take profit order
        take_order = bracket.orders[take_id]
        assert take_order.symbol == "AAPL"
        assert take_order.quantity == -100  # Opposite direction of entry
        assert take_order.order_type == OrderType.LIMIT
        assert take_order.limit_price == 160.0
        
        # Test updating stops
        bracket.update_stops(new_stop_loss=146.0, new_take_profit=162.0)
        assert bracket.stop_loss_price == 146.0
        assert bracket.take_profit_price == 162.0
        assert stop_order.stop_price == 146.0
        assert take_order.limit_price == 162.0
    
    def test_oco_group(self):
        """Test OCOGroup functionality."""
        # Create orders for OCO group
        order1 = Order("AAPL", 100, OrderType.LIMIT, limit_price=150.0)
        order2 = Order("AAPL", 100, OrderType.STOP, stop_price=140.0)
        
        # Create OCO group
        oco = OCOGroup([order1, order2])
        
        # Check OCO properties
        assert len(oco.get_orders()) == 2
        assert "oco_order_ids" in order1.metadata
        assert order2.order_id in order1.metadata["oco_order_ids"]
        
        # Update order status
        order1.update_status(OrderStatus.WORKING)
        order2.update_status(OrderStatus.WORKING)
        
        # Simulate a fill on order1
        order1.add_fill(100, 150.0)
        
        # Handle the fill - should cancel order2
        cancelled_orders = oco.handle_fill(order1.order_id)
        assert len(cancelled_orders) == 1
        assert cancelled_orders[0] == order2.order_id
        assert order2.status == OrderStatus.PENDING_CANCEL


class TestOrderManager:
    """Tests for the OrderManager class."""
    
    @pytest.mark.asyncio
    async def test_order_creation(self, order_manager):
        """Test order creation through manager."""
        # Create a market order
        order = await order_manager.create_order(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.MARKET
        )
        
        # Check order properties
        assert order.symbol == "AAPL"
        assert order.quantity == 100
        assert order.order_type == OrderType.MARKET
        
        # Check manager state
        active_orders = await order_manager.get_active_orders()
        assert len(active_orders) == 0  # Not submitted yet
        
        # Get the order by ID
        retrieved_order = await order_manager.get_order(order.order_id)
        assert retrieved_order is order
        
        # Get orders for symbol
        symbol_orders = await order_manager.get_orders_for_symbol("AAPL")
        assert len(symbol_orders) == 1
        assert symbol_orders[0] is order
    
    @pytest.mark.asyncio
    async def test_order_lifecycle(self, order_manager):
        """Test complete order lifecycle through manager."""
        # Create and submit a market order
        order = await order_manager.create_order(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.MARKET,
            auto_submit=True
        )
        
        # Wait for order processing
        await asyncio.sleep(0.2)
        
        # Check order status
        retrieved_order = await order_manager.get_order(order.order_id)
        assert retrieved_order.status == OrderStatus.ACCEPTED
        
        # Process a fill
        success, _ = await order_manager.process_fill(
            order_id=order.order_id,
            quantity=100,
            price=150.0
        )
        assert success is True
        
        # Check order status after fill
        retrieved_order = await order_manager.get_order(order.order_id)
        assert retrieved_order.status == OrderStatus.FILLED
        
        # Check completed orders
        completed_orders = await order_manager.get_completed_orders()
        assert len(completed_orders) == 1
        assert completed_orders[0].order_id == order.order_id
    
    @pytest.mark.asyncio
    async def test_bracket_order_creation(self, order_manager):
        """Test bracket order creation through manager."""
        # Create a bracket order
        bracket = await order_manager.create_bracket_order(
            symbol="AAPL",
            quantity=100,
            entry_price=150.0,
            stop_loss_price=145.0,
            take_profit_price=160.0,
            entry_type=OrderType.LIMIT
        )
        
        # Check bracket properties
        assert bracket.entry_order.symbol == "AAPL"
        assert bracket.entry_order.quantity == 100
        assert bracket.entry_order.limit_price == 150.0
        
        # Get the order group
        retrieved_group = await order_manager.get_order_group(bracket.group_id)
        assert retrieved_group is bracket
    
    @pytest.mark.asyncio
    async def test_order_cancellation(self, order_manager):
        """Test order cancellation through manager."""
        # Create and submit an order
        order = await order_manager.create_order(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.LIMIT,
            limit_price=150.0,
            auto_submit=True
        )
        
        # Wait for order processing
        await asyncio.sleep(0.2)
        
        # Cancel the order
        success = await order_manager.cancel_order(order.order_id, "Testing cancellation")
        assert success is True
        
        # Check order status
        retrieved_order = await order_manager.get_order(order.order_id)
        assert retrieved_order.status == OrderStatus.CANCELLED