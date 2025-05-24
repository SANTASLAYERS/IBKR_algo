#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OrderManager Integration Tests with TWSConnection.

Tests the updated OrderManager working with TWSConnection for order management.
"""

import pytest
import asyncio
import logging
from unittest.mock import Mock, AsyncMock

from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from src.event.bus import EventBus
from src.order.manager import OrderManager
from src.order.base import OrderType, OrderSide, TimeInForce
from tests.integration.conftest import get_tws_credentials

logger = logging.getLogger("order_manager_tests")


class TestOrderManagerTWS:
    """Tests for OrderManager integration with TWSConnection."""

    @pytest.mark.asyncio
    async def test_order_manager_initialization(self):
        """Test OrderManager initialization without TWS connection."""
        event_bus = EventBus()
        order_manager = OrderManager(event_bus)
        
        # Should initialize without connection
        await order_manager.initialize()
        
        # Test creating an order
        order = await order_manager.create_order(
            symbol="AAPL",
            quantity=100,
            order_type=OrderType.MARKET,
            auto_submit=False
        )
        
        assert order is not None
        assert order.symbol == "AAPL"
        assert order.quantity == 100
        assert order.order_type == OrderType.MARKET
        
        # Test order retrieval
        retrieved_order = await order_manager.get_order(order.order_id)
        assert retrieved_order == order
        
        logger.info("✅ OrderManager initialization test passed")

    @pytest.mark.asyncio
    async def test_order_manager_with_mock_tws(self):
        """Test OrderManager with mock TWSConnection."""
        event_bus = EventBus()
        
        # Create mock TWSConnection
        mock_tws = Mock()
        mock_tws.get_next_order_id.return_value = 1001
        mock_tws.placeOrder = Mock()
        mock_tws.cancelOrder = Mock()
        mock_tws.request_next_order_id = Mock()
        
        order_manager = OrderManager(event_bus, mock_tws)
        await order_manager.initialize()
        
        # Test order submission
        order = await order_manager.create_order(
            symbol="MSFT",
            quantity=50,
            order_type=OrderType.LIMIT,
            limit_price=300.0,
            auto_submit=True
        )
        
        # Should have called TWS methods
        mock_tws.get_next_order_id.assert_called()
        mock_tws.placeOrder.assert_called_once()
        
        # Test order cancellation
        await order_manager.cancel_order(order.order_id)
        mock_tws.cancelOrder.assert_called_once()
        
        logger.info("✅ OrderManager with mock TWS test passed")

    @pytest.mark.asyncio  
    async def test_order_manager_simulation_mode(self):
        """Test OrderManager in simulation mode (no TWS connection)."""
        event_bus = EventBus()
        order_manager = OrderManager(event_bus)  # No TWS connection
        await order_manager.initialize()
        
        # Test creating and submitting order without TWS
        order = await order_manager.create_order(
            symbol="GOOGL",
            quantity=25,
            order_type=OrderType.MARKET,
            auto_submit=True  # Should work in simulation mode
        )
        
        # Give time for async order processing
        await asyncio.sleep(0.2)
        
        # Order should be simulated as accepted
        assert order.status.value in ["submitted", "accepted"]
        
        # Test order cancellation in simulation mode
        cancel_result = await order_manager.cancel_order(order.order_id, "Test cancellation")
        assert cancel_result == True
        
        logger.info("✅ OrderManager simulation mode test passed")

    @pytest.mark.asyncio
    async def test_order_group_creation(self):
        """Test creating order groups (bracket orders, OCO)."""
        event_bus = EventBus()
        order_manager = OrderManager(event_bus)
        await order_manager.initialize()
        
        # Test bracket order creation
        bracket = await order_manager.create_bracket_order(
            symbol="TSLA",
            quantity=10,
            entry_price=200.0,
            stop_loss_price=180.0,
            take_profit_price=220.0,
            entry_type=OrderType.LIMIT,
            auto_submit=False
        )
        
        assert bracket is not None
        assert len(bracket.orders) == 1  # Initially only entry order exists
        assert bracket.entry_order_id is not None
        
        # Simulate entry order fill to create child orders
        entry_order = bracket.orders[bracket.entry_order_id]
        entry_order.add_fill(10, 200.0)  # Fill the entry order
        
        # Now create the child orders (this would normally be done by OrderManager)
        stop_id, target_id = bracket.handle_entry_fill(200.0)
        
        # Now should have 3 orders: entry + stop loss + take profit
        assert len(bracket.orders) == 3
        assert bracket.stop_loss_order_id is not None
        assert bracket.take_profit_order_id is not None
        
        # Test OCO order creation  
        oco_orders = [
            {
                "symbol": "NVDA",
                "quantity": 5,
                "order_type": OrderType.LIMIT,
                "limit_price": 400.0
            },
            {
                "symbol": "NVDA", 
                "quantity": 5,
                "order_type": OrderType.STOP,
                "stop_price": 350.0
            }
        ]
        
        oco_group = await order_manager.create_oco_orders(oco_orders, auto_submit=False)
        assert oco_group is not None
        assert len(oco_group.get_orders()) == 2
        
        logger.info("✅ Order group creation test passed")

    @pytest.mark.asyncio
    async def test_order_status_callbacks(self):
        """Test order status callback handling."""
        event_bus = EventBus()
        
        # Create mock TWSConnection with callback support
        mock_tws = Mock()
        mock_tws.get_next_order_id.return_value = 2001
        mock_tws.placeOrder = Mock()
        mock_tws.orderStatus = None  # Will be overridden by OrderManager
        mock_tws.execDetails = None  # Will be overridden by OrderManager
        
        order_manager = OrderManager(event_bus, mock_tws)
        await order_manager.initialize()
        
        # Create an order
        order = await order_manager.create_order(
            symbol="AMD",
            quantity=20,
            order_type=OrderType.MARKET,
            auto_submit=True
        )
        
        # Simulate order status update
        await order_manager.handle_order_status_update(
            broker_order_id=str(2001),
            status="Submitted",
            filled=0.0,
            remaining=20.0,
            avg_fill_price=0.0,
            last_fill_price=0.0
        )
        
        # Simulate execution
        await order_manager.handle_execution_update(
            broker_order_id=str(2001),
            exec_id="EXEC_001",
            symbol="AMD",
            side="BUY",
            quantity=20.0,
            price=95.0,
            commission=1.0
        )
        
        logger.info("✅ Order status callbacks test passed")

    @pytest.mark.usefixtures("check_tws")
    @pytest.mark.asyncio
    async def test_order_manager_with_real_tws_connection(self):
        """Test OrderManager with real TWSConnection (connection only, no actual orders)."""
        credentials = get_tws_credentials()
        config = TWSConfig(
            host=credentials["host"],
            port=credentials["port"],
            client_id=credentials["client_id"] + 50,  # Offset to avoid conflicts
            connection_timeout=10.0
        )
        
        event_bus = EventBus()
        tws_connection = TWSConnection(config)
        order_manager = OrderManager(event_bus, tws_connection)
        
        try:
            # Connect to TWS
            connected = await tws_connection.connect()
            assert connected, "Failed to connect to TWS"
            
            # Initialize OrderManager with TWS connection
            await order_manager.initialize()
            
            # Test that OrderManager recognizes TWS connection
            assert order_manager.gateway is not None
            assert hasattr(order_manager.gateway, 'placeOrder')
            assert hasattr(order_manager.gateway, 'cancelOrder')
            
            # Test getting next order ID
            next_id = tws_connection.get_next_order_id()
            assert next_id is not None
            assert next_id > 0
            
            # Test basic TWS functionality
            tws_connection.request_current_time()
            await asyncio.sleep(1)
            
            # Create an order but don't submit it (safe)
            order = await order_manager.create_order(
                symbol="AAPL",
                quantity=1,
                order_type=OrderType.LIMIT,
                limit_price=100.0,  # Far below market
                auto_submit=False  # Don't actually submit
            )
            
            assert order is not None
            assert order.symbol == "AAPL"
            
            logger.info("✅ OrderManager with real TWSConnection test passed")
            
        finally:
            if tws_connection.is_connected():
                tws_connection.disconnect()
                await asyncio.sleep(1)

    @pytest.mark.asyncio
    async def test_multiple_orders_management(self):
        """Test managing multiple orders simultaneously."""
        event_bus = EventBus()
        order_manager = OrderManager(event_bus)
        await order_manager.initialize()
        
        # Create multiple orders
        symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"]
        orders = []
        
        for symbol in symbols:
            order = await order_manager.create_order(
                symbol=symbol,
                quantity=10,
                order_type=OrderType.MARKET,
                auto_submit=False
            )
            orders.append(order)
        
        # Test retrieving orders by symbol
        for symbol in symbols:
            symbol_orders = await order_manager.get_orders_for_symbol(symbol)
            assert len(symbol_orders) == 1
            assert symbol_orders[0].symbol == symbol
        
        # Test getting all orders (created orders are pending, not active)
        all_orders = []
        for symbol in symbols:
            symbol_orders = await order_manager.get_orders_for_symbol(symbol)
            all_orders.extend(symbol_orders)
        assert len(all_orders) == len(symbols)
        
        # Test cancelling all orders for a specific symbol
        # First submit orders so they can be cancelled (orders in CREATED status can't be cancelled)
        for order in orders:
            if order.symbol == "AAPL":
                await order_manager.submit_order(order.order_id)
        
        cancelled = await order_manager.cancel_all_orders(symbol="AAPL")
        assert cancelled == 1
        
        # Test cancelling all remaining orders
        # Submit remaining orders so they can be cancelled
        for order in orders:
            if order.symbol != "AAPL":
                await order_manager.submit_order(order.order_id)
        
        remaining_cancelled = await order_manager.cancel_all_orders()
        assert remaining_cancelled == len(symbols) - 1
        
        logger.info("✅ Multiple orders management test passed") 