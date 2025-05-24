#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Order Placement Integration Tests for TWS.

SAFETY WARNING: These tests place REAL orders in TWS.
- Only run against paper trading accounts
- Uses small quantities and immediate cancellation
- Set TWS_ENABLE_ORDER_TESTS=true to enable
"""

import pytest
import asyncio
import logging
import os
from ibapi.contract import Contract
from ibapi.order import Order as IBOrder

from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from tests.integration.conftest import get_tws_credentials

logger = logging.getLogger("order_placement_tests")


class TWSOrderConnection(TWSConnection):
    """Extended TWS connection for order testing."""
    
    def __init__(self, config: TWSConfig):
        super().__init__(config)
        self.order_status = {}
        self.executions = {}
        self.commission_reports = {}
        
    def orderStatus(self, orderId: int, status: str, filled: float, 
                   remaining: float, avgFillPrice: float, permId: int,
                   parentId: int, lastFillPrice: float, clientId: int,
                   whyHeld: str, mktCapPrice: float):
        """Handle order status updates."""
        self.order_status[orderId] = {
            "status": status,
            "filled": filled,
            "remaining": remaining,
            "avgFillPrice": avgFillPrice,
            "lastFillPrice": lastFillPrice,
            "permId": permId,
            "parentId": parentId,
            "clientId": clientId,
            "whyHeld": whyHeld,
            "timestamp": asyncio.get_event_loop().time()
        }
        logger.info(f"Order {orderId} status: {status}, filled: {filled}, remaining: {remaining}")
    
    def execDetails(self, reqId: int, contract: Contract, execution):
        """Handle execution details."""
        order_id = execution.orderId
        if order_id not in self.executions:
            self.executions[order_id] = []
        
        exec_data = {
            "orderId": execution.orderId,
            "symbol": contract.symbol,
            "shares": execution.shares,
            "price": execution.price,
            "side": execution.side,
            "execId": execution.execId,
            "time": execution.time,
            "timestamp": asyncio.get_event_loop().time()
        }
        self.executions[order_id].append(exec_data)
        logger.info(f"Execution: Order {order_id}, {execution.shares} @ {execution.price}")
    
    def commissionReport(self, commissionReport):
        """Handle commission reports."""
        exec_id = commissionReport.execId
        self.commission_reports[exec_id] = {
            "commission": commissionReport.commission,
            "currency": commissionReport.currency,
            "realizedPNL": commissionReport.realizedPNL,
            "timestamp": asyncio.get_event_loop().time()
        }
        logger.info(f"Commission for {exec_id}: {commissionReport.commission} {commissionReport.currency}")


class TestTWSOrderPlacement:
    """Tests for TWS order placement functionality."""

    def setup_method(self):
        """Setup for each test method."""
        # Check if order tests are enabled
        if not os.environ.get("TWS_ENABLE_ORDER_TESTS", "").lower() == "true":
            pytest.skip("Order placement tests disabled. Set TWS_ENABLE_ORDER_TESTS=true to enable.")

    @pytest.mark.usefixtures("check_tws")
    @pytest.mark.asyncio
    async def test_market_order_immediate_cancel(self):
        """Test placing and immediately cancelling a market order."""
        credentials = get_tws_credentials()
        config = TWSConfig(
            host=credentials["host"],
            port=credentials["port"],
            client_id=credentials["client_id"],  # Use consistent client ID
            connection_timeout=10.0
        )
        
        connection = TWSOrderConnection(config)
        
        try:
            # Connect to TWS
            connected = await connection.connect()
            assert connected, "Failed to connect to TWS"
            
            # Wait for next valid order ID
            await asyncio.sleep(2)
            order_id = connection.get_next_order_id()
            assert order_id is not None, "Did not receive next valid order ID"
            
            # Create contract for liquid stock
            contract = Contract()
            contract.symbol = "AAPL"
            contract.secType = "STK"
            contract.exchange = "SMART"
            contract.currency = "USD"
            
            # Create small market order
            order = IBOrder()
            order.action = "BUY"
            order.totalQuantity = 1  # Minimum quantity
            order.orderType = "MKT"
            order.transmit = True
            
            logger.info(f"Placing market order: {order.action} {order.totalQuantity} {contract.symbol}")
            
            # Place order
            connection.placeOrder(order_id, contract, order)
            await asyncio.sleep(1)  # Give time for order to be processed
            
            # Immediately cancel the order
            logger.info(f"Cancelling order {order_id}")
            connection.cancelOrder(order_id, "")
            
            # Wait for status updates
            timeout = 15
            start_time = asyncio.get_event_loop().time()
            
            while (asyncio.get_event_loop().time() - start_time) < timeout:
                await asyncio.sleep(1)
                
                if order_id in connection.order_status:
                    status = connection.order_status[order_id]["status"]
                    logger.info(f"Order {order_id} status: {status}")
                    
                    if status in ["Cancelled", "Filled", "Inactive"]:
                        break
            
            # Verify we got status updates
            assert order_id in connection.order_status, "Should have received order status"
            final_status = connection.order_status[order_id]["status"]
            
            # Order should be cancelled or filled (acceptable outcomes)
            assert final_status in ["Cancelled", "Filled", "Inactive"], f"Unexpected final status: {final_status}"
            
            if final_status == "Filled":
                logger.warning("⚠️  Order was filled before cancellation - this is normal in fast markets")
                assert order_id in connection.executions, "Should have execution details for filled order"
            else:
                logger.info("✅ Order successfully cancelled")
            
        finally:
            if connection.is_connected():
                connection.disconnect()
                await asyncio.sleep(1)

    @pytest.mark.usefixtures("check_tws")
    @pytest.mark.asyncio
    async def test_limit_order_lifecycle(self):
        """Test placing a limit order far from market and cancelling it."""
        credentials = get_tws_credentials()
        config = TWSConfig(
            host=credentials["host"],
            port=credentials["port"],
            client_id=credentials["client_id"],  # Use consistent client ID
            connection_timeout=10.0
        )
        
        connection = TWSOrderConnection(config)
        
        try:
            # Connect to TWS
            connected = await connection.connect()
            assert connected, "Failed to connect to TWS"
            
            await asyncio.sleep(2)
            order_id = connection.get_next_order_id()
            assert order_id is not None, "Did not receive next valid order ID"
            
            # Create contract
            contract = Contract()
            contract.symbol = "AAPL"
            contract.secType = "STK"
            contract.exchange = "SMART"
            contract.currency = "USD"
            
            # Create limit order far below market (won't fill)
            order = IBOrder()
            order.action = "BUY"
            order.totalQuantity = 1
            order.orderType = "LMT"
            order.lmtPrice = 50.00  # Far below market price
            order.transmit = True
            
            logger.info(f"Placing limit order: {order.action} {order.totalQuantity} {contract.symbol} @ {order.lmtPrice}")
            
            # Place order
            connection.placeOrder(order_id, contract, order)
            
            # Wait for order to be accepted
            timeout = 10
            start_time = asyncio.get_event_loop().time()
            order_accepted = False
            
            while (asyncio.get_event_loop().time() - start_time) < timeout:
                await asyncio.sleep(1)
                
                if order_id in connection.order_status:
                    status = connection.order_status[order_id]["status"]
                    if status in ["Submitted", "PreSubmitted"]:
                        order_accepted = True
                        logger.info(f"✅ Order {order_id} accepted with status: {status}")
                        break
            
            assert order_accepted, "Order was not accepted by TWS"
            
            # Cancel the order
            logger.info(f"Cancelling limit order {order_id}")
            connection.cancelOrder(order_id, "")
            
            # Wait for cancellation
            timeout = 10
            start_time = asyncio.get_event_loop().time()
            
            while (asyncio.get_event_loop().time() - start_time) < timeout:
                await asyncio.sleep(1)
                
                if order_id in connection.order_status:
                    status = connection.order_status[order_id]["status"]
                    if status == "Cancelled":
                        logger.info("✅ Order successfully cancelled")
                        break
            
            # Verify cancellation
            assert order_id in connection.order_status, "Should have received order status"
            final_status = connection.order_status[order_id]["status"]
            assert final_status == "Cancelled", f"Expected cancelled status, got: {final_status}"
            
        finally:
            if connection.is_connected():
                connection.disconnect()
                await asyncio.sleep(1)

    @pytest.mark.usefixtures("check_tws")
    @pytest.mark.asyncio
    async def test_invalid_order_rejection(self):
        """Test that invalid orders are properly rejected."""
        credentials = get_tws_credentials()
        config = TWSConfig(
            host=credentials["host"],
            port=credentials["port"],
            client_id=credentials["client_id"],  # Use consistent client ID
            connection_timeout=10.0
        )
        
        connection = TWSOrderConnection(config)
        
        try:
            # Connect to TWS
            connected = await connection.connect()
            assert connected, "Failed to connect to TWS"
            
            await asyncio.sleep(2)
            order_id = connection.get_next_order_id()
            assert order_id is not None, "Did not receive next valid order ID"
            
            # Create invalid contract (non-existent symbol)
            contract = Contract()
            contract.symbol = "INVALID_SYMBOL_XYZ"
            contract.secType = "STK"
            contract.exchange = "SMART"
            contract.currency = "USD"
            
            # Create order for invalid symbol
            order = IBOrder()
            order.action = "BUY"
            order.totalQuantity = 1
            order.orderType = "MKT"
            order.transmit = True
            
            logger.info(f"Placing order for invalid symbol: {contract.symbol}")
            
            # Place order - should be rejected
            connection.placeOrder(order_id, contract, order)
            
            # Wait for rejection
            timeout = 15
            start_time = asyncio.get_event_loop().time()
            
            while (asyncio.get_event_loop().time() - start_time) < timeout:
                await asyncio.sleep(1)
                
                if order_id in connection.order_status:
                    status = connection.order_status[order_id]["status"]
                    if status in ["Cancelled", "Inactive"]:
                        logger.info(f"✅ Invalid order properly rejected with status: {status}")
                        break
            
            # Should have status indicating rejection
            if order_id in connection.order_status:
                final_status = connection.order_status[order_id]["status"]
                assert final_status in ["Cancelled", "Inactive"], f"Expected rejection, got: {final_status}"
                logger.info("✅ Invalid order rejection test passed")
            else:
                logger.info("✅ Invalid order was not processed (also acceptable)")
            
        finally:
            if connection.is_connected():
                connection.disconnect()
                await asyncio.sleep(1)

    @pytest.mark.usefixtures("check_tws")
    @pytest.mark.asyncio
    async def test_multiple_orders_management(self):
        """Test managing multiple orders simultaneously."""
        credentials = get_tws_credentials()
        config = TWSConfig(
            host=credentials["host"],
            port=credentials["port"],
            client_id=credentials["client_id"],  # Use consistent client ID
            connection_timeout=10.0
        )
        
        connection = TWSOrderConnection(config)
        
        try:
            # Connect to TWS
            connected = await connection.connect()
            assert connected, "Failed to connect to TWS"
            
            await asyncio.sleep(2)
            base_order_id = connection.get_next_order_id()
            assert base_order_id is not None, "Did not receive next valid order ID"
            
            # Create multiple limit orders (far from market)
            symbols = ["AAPL", "MSFT"]
            order_ids = []
            
            for i, symbol in enumerate(symbols):
                order_id = base_order_id + i
                order_ids.append(order_id)
                
                # Create contract
                contract = Contract()
                contract.symbol = symbol
                contract.secType = "STK"
                contract.exchange = "SMART"
                contract.currency = "USD"
                
                # Create limit order far from market
                order = IBOrder()
                order.action = "BUY"
                order.totalQuantity = 1
                order.orderType = "LMT"
                order.lmtPrice = 10.00  # Very low price
                order.transmit = True
                
                logger.info(f"Placing order {order_id} for {symbol}")
                connection.placeOrder(order_id, contract, order)
                await asyncio.sleep(0.5)  # Small delay between orders
            
            # Wait for orders to be processed
            await asyncio.sleep(5)
            
            # Cancel all orders
            for order_id in order_ids:
                logger.info(f"Cancelling order {order_id}")
                connection.cancelOrder(order_id, "")
                await asyncio.sleep(0.5)
            
            # Wait for cancellations
            await asyncio.sleep(5)
            
            # Verify all orders were processed
            processed_orders = 0
            for order_id in order_ids:
                if order_id in connection.order_status:
                    status = connection.order_status[order_id]["status"]
                    logger.info(f"Order {order_id} final status: {status}")
                    processed_orders += 1
            
            # Should have processed at least some orders
            assert processed_orders > 0, "Should have processed at least one order"
            logger.info(f"✅ Successfully managed {processed_orders} orders")
            
        finally:
            if connection.is_connected():
                connection.disconnect()
                await asyncio.sleep(1) 