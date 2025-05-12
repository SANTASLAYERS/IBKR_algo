#!/usr/bin/env python3
"""
Integration test for Order Management System with real IBKR Gateway connection.

This test validates the integration between the OrderManager and IBGateway by
placing actual orders, tracking their status, and validating the bidirectional
communication.

IMPORTANT: This test requires a connection to the IB Gateway in paper trading mode.
Never run this in live trading mode without explicit modifications.
"""

import asyncio
import logging
import os
import pytest
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from ibapi.contract import Contract
from ibapi.order import Order as IBOrder

from src.config import Config
from src.gateway import IBGateway, IBGatewayConfig
from src.event.bus import EventBus
from src.event.order import OrderStatus, OrderStatusEvent, FillEvent, CancelEvent
from src.order.base import Order, OrderType, TimeInForce, OrderSide
from src.order.manager import OrderManager
from src.order.group import BracketOrder

# Set up logging for tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_order_ibkr")

# Test configuration - read from environment or use defaults
TEST_HOST = os.environ.get("TEST_IB_HOST", "127.0.0.1")
TEST_PORT = int(os.environ.get("TEST_IB_PORT", "4002"))  # Paper trading port
TEST_CLIENT_ID = int(os.environ.get("TEST_IB_CLIENT_ID", "999"))  # Use high client ID for tests
TEST_ACCOUNT = os.environ.get("TEST_IB_ACCOUNT", "")  # Account ID if needed

# Test symbols and parameters
TEST_SYMBOL = "SPY"  # Use a liquid ETF for testing
TEST_QUANTITY = 1  # Small quantity for testing
TEST_PRICE_OFFSET = 10.0  # Place orders far from market to avoid execution


@pytest.fixture(scope="module")
async def gateway():
    """Create and connect to IB Gateway for tests."""
    config = IBGatewayConfig(
        host=TEST_HOST,
        port=TEST_PORT,
        client_id=TEST_CLIENT_ID,
        account_id=TEST_ACCOUNT,
        trading_mode="paper"
    )
    
    gateway = IBGateway(config)
    connected = await gateway.connect_async()
    
    if not connected:
        pytest.skip("Cannot connect to IB Gateway. Skipping integration tests.")
    
    # Wait for connection to fully initialize
    await asyncio.sleep(2)
    
    yield gateway
    
    # Cleanup - disconnect from gateway
    gateway.disconnect()
    await asyncio.sleep(1)


@pytest.fixture(scope="module")
async def event_bus():
    """Create event bus for tests."""
    return EventBus()


@pytest.fixture(scope="module")
async def order_manager(gateway, event_bus):
    """Create order manager connected to gateway."""
    order_manager = OrderManager(event_bus, gateway)
    yield order_manager


@pytest.fixture
async def current_price(gateway) -> float:
    """Get current market price for the test symbol."""
    # Create contract
    contract = Contract()
    contract.symbol = TEST_SYMBOL
    contract.secType = "STK"
    contract.exchange = "SMART"
    contract.currency = "USD"
    
    # Set up price update callback
    price_future = asyncio.Future()
    
    def price_callback(data):
        if not price_future.done() and data.get("last_price"):
            price_future.set_result(data["last_price"])
    
    # Subscribe to market data
    req_id = gateway.subscribe_market_data(contract, callback=price_callback)
    
    try:
        # Wait for price data with timeout
        price = await asyncio.wait_for(price_future, timeout=10.0)
        return price
    except asyncio.TimeoutError:
        pytest.skip(f"Could not get current price for {TEST_SYMBOL}. Skipping test.")
        return 0.0
    finally:
        # Unsubscribe from market data
        gateway.unsubscribe_market_data(req_id)


@pytest.fixture
def stock_contract():
    """Create a stock contract for testing."""
    contract = Contract()
    contract.symbol = TEST_SYMBOL
    contract.secType = "STK"
    contract.exchange = "SMART"
    contract.currency = "USD"
    return contract


class OrderEvents:
    """Helper class to track order events during tests."""
    
    def __init__(self, event_bus, order_ids=None):
        self.event_bus = event_bus
        self.order_ids = order_ids or []
        self.status_events = []
        self.fill_events = []
        self.cancel_events = []
        self._setup_done = False
    
    async def setup(self):
        """Register event handlers."""
        if self._setup_done:
            return
        
        # Register handlers
        await self.event_bus.subscribe(OrderStatusEvent, self._handle_status)
        await self.event_bus.subscribe(FillEvent, self._handle_fill)
        await self.event_bus.subscribe(CancelEvent, self._handle_cancel)
        
        self._setup_done = True
    
    async def _handle_status(self, event):
        """Handle order status events."""
        if not self.order_ids or event.order_id in self.order_ids:
            self.status_events.append(event)
            logger.info(f"Order status event: {event.order_id} - {event.status.value}")
    
    async def _handle_fill(self, event):
        """Handle order fill events."""
        if not self.order_ids or event.order_id in self.order_ids:
            self.fill_events.append(event)
            logger.info(f"Order fill event: {event.order_id} - {event.fill_quantity} @ {event.fill_price}")
    
    async def _handle_cancel(self, event):
        """Handle order cancel events."""
        if not self.order_ids or event.order_id in self.order_ids:
            self.cancel_events.append(event)
            logger.info(f"Order cancel event: {event.order_id} - {event.reason}")
    
    def reset(self):
        """Reset event tracking."""
        self.status_events = []
        self.fill_events = []
        self.cancel_events = []
    
    def get_status_events_for_order(self, order_id):
        """Get status events for a specific order."""
        return [e for e in self.status_events if e.order_id == order_id]
    
    def get_fill_events_for_order(self, order_id):
        """Get fill events for a specific order."""
        return [e for e in self.fill_events if e.order_id == order_id]
    
    def get_cancel_events_for_order(self, order_id):
        """Get cancel events for a specific order."""
        return [e for e in self.cancel_events if e.order_id == order_id]


@pytest.fixture
async def order_events(event_bus):
    """Create an order events tracker."""
    tracker = OrderEvents(event_bus)
    await tracker.setup()
    return tracker


@pytest.mark.asyncio
async def test_order_submission_and_cancellation(order_manager, order_events, current_price, stock_contract):
    """Test basic order submission and cancellation with IB Gateway."""
    # Reset event tracking
    order_events.reset()
    
    # Create a limit order that won't execute (price too low)
    limit_price = current_price - TEST_PRICE_OFFSET
    order = await order_manager.create_order(
        symbol=TEST_SYMBOL,
        quantity=TEST_QUANTITY,
        order_type=OrderType.LIMIT,
        limit_price=limit_price,
        auto_submit=False
    )
    
    # Update tracking
    order_events.order_ids = [order.order_id]
    
    # Verify initial order state
    assert order.status == OrderStatus.CREATED
    assert order.symbol == TEST_SYMBOL
    assert order.quantity == TEST_QUANTITY
    assert order.limit_price == limit_price
    
    # Submit the order
    success = await order_manager.submit_order(order.order_id)
    assert success, "Order submission should succeed"
    
    # Wait for order to be acknowledged by IB
    await asyncio.sleep(3)
    
    # Verify order status progression
    status_events = order_events.get_status_events_for_order(order.order_id)
    assert len(status_events) >= 2, "Should have at least 2 status events"
    
    # Order should now have a broker_order_id
    updated_order = await order_manager.get_order(order.order_id)
    assert updated_order.broker_order_id is not None, "Order should have a broker order ID"
    
    # Cancel the order
    success = await order_manager.cancel_order(order.order_id, "Test cancellation")
    assert success, "Order cancellation should succeed"
    
    # Wait for cancellation to be acknowledged
    await asyncio.sleep(3)
    
    # Verify cancellation
    cancel_events = order_events.get_cancel_events_for_order(order.order_id)
    assert len(cancel_events) > 0, "Should have cancel events"
    
    # Final order status should be cancelled
    updated_order = await order_manager.get_order(order.order_id)
    assert updated_order.status == OrderStatus.CANCELLED, f"Order should be cancelled, but is {updated_order.status.value}"


@pytest.mark.asyncio
async def test_bracket_order(order_manager, order_events, current_price, stock_contract):
    """Test bracket order creation and cancellation with IB Gateway."""
    # Reset event tracking
    order_events.reset()
    
    # Create bracket order parameters
    entry_price = current_price - TEST_PRICE_OFFSET  # Entry price below market to avoid execution
    stop_loss_price = entry_price - 5.0
    take_profit_price = entry_price + 10.0
    
    # Create bracket order
    bracket = await order_manager.create_bracket_order(
        symbol=TEST_SYMBOL,
        quantity=TEST_QUANTITY,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
        entry_type=OrderType.LIMIT,
        auto_submit=False
    )
    
    # Update tracking
    order_events.order_ids = [
        bracket.entry_order_id,
        bracket.stop_loss_order_id,
        bracket.take_profit_order_id
    ]
    
    # Verify bracket structure
    assert bracket.entry_order_id is not None
    assert bracket.stop_loss_order_id is not None
    assert bracket.take_profit_order_id is not None
    
    # Submit entry order
    success = await order_manager.submit_order(bracket.entry_order_id)
    assert success, "Entry order submission should succeed"
    
    # Wait for order to be acknowledged
    await asyncio.sleep(3)
    
    # Verify order status
    entry_status_events = order_events.get_status_events_for_order(bracket.entry_order_id)
    assert len(entry_status_events) >= 1, "Should have entry order status events"
    
    # Cancel the bracket
    cancel_count = await order_manager.cancel_order_group(bracket.group_id, "Test bracket cancellation")
    assert cancel_count >= 1, "Should cancel at least the entry order"
    
    # Wait for cancellation to be acknowledged
    await asyncio.sleep(3)
    
    # Verify cancellation
    cancel_events = order_events.get_cancel_events_for_order(bracket.entry_order_id)
    assert len(cancel_events) > 0, "Should have cancel events for entry order"
    
    # Entry order should be cancelled
    entry_order = await order_manager.get_order(bracket.entry_order_id)
    assert entry_order.status == OrderStatus.CANCELLED or entry_order.status == OrderStatus.PENDING_CANCEL, \
        f"Entry order should be cancelled or pending cancel, but is {entry_order.status.value}"


if __name__ == "__main__":
    # Allow running the test file directly
    asyncio.run(pytest.main(["-xvs", __file__]))