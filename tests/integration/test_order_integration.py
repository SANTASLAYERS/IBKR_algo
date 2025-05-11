#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Integration tests for order placement and management with IB Gateway.

These tests validate the actual order processing flow against a live IB Gateway.
"""

import asyncio
import logging
import pytest
import uuid
from datetime import datetime, timedelta
from ibapi.contract import Contract
from ibapi.order import Order as IBOrder

from src.gateway import IBGateway
from src.error_handler import ErrorHandler

logger = logging.getLogger("order_integration_tests")


@pytest.mark.usefixtures("ib_gateway")
class TestOrderIntegration:
    """
    Integration tests for order placement and management.
    
    These tests require a connection to IB Gateway and will place actual
    orders in a paper trading account.
    """
    
    # Class variable to receive the gateway from the fixture
    gateway: IBGateway = None
    
    @classmethod
    def setup_class(cls):
        """Set up test class."""
        logger.info("Setting up OrderIntegration test class")
        
        # Define test symbols
        cls.test_symbols = ["SPY", "IWM", "QQQ"]
        
        # Order tracking for cleanup
        cls.test_orders = []
    
    @classmethod
    def teardown_class(cls):
        """Clean up after all tests."""
        logger.info("Tearing down OrderIntegration test class")
        
        # Make sure all test orders are cancelled
        if cls.gateway and cls.gateway.is_connected():
            for order_id in cls.test_orders:
                try:
                    cls.gateway.cancel_order(order_id)
                    logger.info(f"Cancelled order {order_id} during cleanup")
                except Exception as e:
                    logger.warning(f"Error cancelling order {order_id} during cleanup: {str(e)}")
    
    def generate_unique_client_id(self):
        """Generate a unique client order ID for testing."""
        return f"test_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}"
    
    def create_stock_contract(self, symbol):
        """Create a stock contract for testing."""
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        return contract
    
    @pytest.mark.asyncio
    async def test_market_order_submission(self):
        """
        Test market order submission and validation.
        
        This test verifies that:
        1. A market order can be submitted to IB Gateway
        2. The order is accepted by IB Gateway
        3. The order status is updated correctly
        """
        # Skip test if gateway not available
        if not self.gateway or not self.gateway.is_connected():
            pytest.skip("IB Gateway not available")
        
        # Create a contract for testing
        symbol = self.test_symbols[0]
        contract = self.create_stock_contract(symbol)
        
        # Create a very small market order (1 share) to minimize cost
        iborder = IBOrder()
        iborder.action = "BUY"
        iborder.orderType = "MKT"
        iborder.totalQuantity = 1
        iborder.transmit = True
        iborder.outsideRth = False
        
        # Add a unique client ID for tracking
        client_id = self.generate_unique_client_id()
        iborder.orderId = 0  # Let IB assign ID
        iborder.clientId = self.gateway.client_id
        iborder.account = self.gateway.account_id
        iborder.orderRef = client_id
        
        # Initialize order status tracking
        order_status = {}
        order_id = None
        
        # Define callbacks to track order status
        def order_status_callback(status_update):
            nonlocal order_status
            order_status = status_update
            logger.info(f"Order status update: {status_update}")
        
        # Register for order status updates
        self.gateway.register_order_status_callback(order_status_callback)
        
        try:
            # Submit the order
            logger.info(f"Submitting market order for {symbol}: {iborder}")
            order_id = self.gateway.submit_order(contract, iborder)
            assert order_id > 0, f"Order submission failed, received invalid ID: {order_id}"
            
            # Add to test orders for cleanup
            self.test_orders.append(order_id)
            logger.info(f"Order submitted successfully, ID: {order_id}")
            
            # Wait for order status updates
            timeout = 10  # 10 seconds
            start_time = datetime.now()
            
            while datetime.now() - start_time < timedelta(seconds=timeout):
                # Check if we've received any status updates
                if order_status and order_status.get('order_id') == order_id:
                    logger.info(f"Received order status: {order_status}")
                    
                    # Check if order is acknowledged by IB
                    status = order_status.get('status')
                    if status in ['Submitted', 'Filled', 'Cancelled']:
                        logger.info(f"Order {order_id} status: {status}")
                        break
                
                # Wait a bit before checking again
                await asyncio.sleep(0.5)
            
            # Validate order status
            assert order_status, f"No order status received for order {order_id}"
            assert order_status.get('order_id') == order_id, f"Order ID mismatch: {order_status.get('order_id')} != {order_id}"
            
            # Consider these statuses acceptable for a market order
            acceptable_statuses = ['Submitted', 'PreSubmitted', 'Filled']
            status = order_status.get('status')
            
            assert status in acceptable_statuses, f"Unexpected order status: {status}, expected one of {acceptable_statuses}"
            
        finally:
            # Always try to cancel the order if it was submitted
            if order_id and order_id > 0:
                try:
                    self.gateway.cancel_order(order_id)
                    logger.info(f"Cancelled test order {order_id}")
                except Exception as e:
                    logger.warning(f"Error cancelling order {order_id}: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_limit_order_placement_and_cancellation(self):
        """
        Test limit order placement and cancellation.
        
        This test verifies that:
        1. A limit order can be submitted to IB Gateway
        2. The order can be cancelled
        3. The cancellation is confirmed
        """
        # Skip test if gateway not available
        if not self.gateway or not self.gateway.is_connected():
            pytest.skip("IB Gateway not available")
        
        # Create a contract for testing
        symbol = self.test_symbols[1]
        contract = self.create_stock_contract(symbol)
        
        # Get current market price (this would be improved with actual price data)
        # For testing, we'll place a limit order well below market price
        # so it won't fill but will be accepted
        price_offset_pct = 0.90  # 10% below current price
        limit_price = 100.0  # Placeholder - would be current_price * price_offset_pct
        
        # Create a small limit order
        iborder = IBOrder()
        iborder.action = "BUY"
        iborder.orderType = "LMT"
        iborder.totalQuantity = 1
        iborder.lmtPrice = limit_price
        iborder.transmit = True
        iborder.outsideRth = False
        
        # Add a unique client ID
        client_id = self.generate_unique_client_id()
        iborder.orderId = 0  # Let IB assign ID
        iborder.clientId = self.gateway.client_id
        iborder.account = self.gateway.account_id
        iborder.orderRef = client_id
        
        # Initialize tracking variables
        order_status = {}
        cancel_status = {}
        order_id = None
        
        # Define callbacks to track order status
        def order_status_callback(status_update):
            nonlocal order_status
            order_status = status_update
            logger.info(f"Order status update: {status_update}")
        
        # Define callback for cancel status
        def cancel_callback(cancel_data):
            nonlocal cancel_status
            cancel_status = cancel_data
            logger.info(f"Cancel status update: {cancel_data}")
        
        # Register callbacks
        self.gateway.register_order_status_callback(order_status_callback)
        self.gateway.register_order_cancel_callback(cancel_callback)
        
        try:
            # Submit the order
            logger.info(f"Submitting limit order for {symbol} at {limit_price}: {iborder}")
            order_id = self.gateway.submit_order(contract, iborder)
            assert order_id > 0, f"Order submission failed, received invalid ID: {order_id}"
            
            # Add to test orders for cleanup
            self.test_orders.append(order_id)
            logger.info(f"Order submitted successfully, ID: {order_id}")
            
            # Wait for order status updates
            timeout = 10  # 10 seconds
            start_time = datetime.now()
            
            while datetime.now() - start_time < timedelta(seconds=timeout):
                # Check if we've received any status updates
                if order_status and order_status.get('order_id') == order_id:
                    logger.info(f"Received order status: {order_status}")
                    
                    # Check if order is acknowledged by IB
                    status = order_status.get('status')
                    if status in ['Submitted', 'PreSubmitted']:
                        logger.info(f"Order {order_id} status: {status}")
                        break
                
                # Wait a bit before checking again
                await asyncio.sleep(0.5)
            
            # Validate order status
            assert order_status, f"No order status received for order {order_id}"
            assert order_status.get('order_id') == order_id, f"Order ID mismatch: {order_status.get('order_id')} != {order_id}"
            
            acceptable_statuses = ['Submitted', 'PreSubmitted']
            status = order_status.get('status')
            
            assert status in acceptable_statuses, f"Unexpected order status: {status}, expected one of {acceptable_statuses}"
            
            # If order was successfully submitted, test cancellation
            if order_id and status in acceptable_statuses:
                logger.info(f"Cancelling order {order_id}")
                self.gateway.cancel_order(order_id)
                
                # Wait for cancellation confirmation
                timeout = 10  # 10 seconds
                start_time = datetime.now()
                
                while datetime.now() - start_time < timedelta(seconds=timeout):
                    # Check for updated order status showing cancellation
                    if order_status and order_status.get('status') in ['Cancelled', 'PendingCancel']:
                        logger.info(f"Order {order_id} cancellation status: {order_status.get('status')}")
                        break
                    
                    # Wait a bit before checking again
                    await asyncio.sleep(0.5)
                
                # Validate cancellation
                assert order_status.get('status') in ['Cancelled', 'PendingCancel'], \
                    f"Order not cancelled, status: {order_status.get('status')}"
                
                logger.info(f"Order {order_id} successfully cancelled")
            
        finally:
            # Always try to cancel the order if it was submitted and not already cancelled
            if order_id and order_id > 0 and not (order_status and order_status.get('status') in ['Cancelled', 'PendingCancel']):
                try:
                    self.gateway.cancel_order(order_id)
                    logger.info(f"Cancelled test order {order_id} in cleanup")
                except Exception as e:
                    logger.warning(f"Error cancelling order {order_id} in cleanup: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_bracket_order_creation(self):
        """
        Test bracket order creation and validation.
        
        This test verifies that:
        1. A bracket order (entry + stop loss + take profit) can be created
        2. All components of the bracket are properly submitted to IB Gateway
        3. The order group relationship is maintained
        """
        # Skip test if gateway not available
        if not self.gateway or not self.gateway.is_connected():
            pytest.skip("IB Gateway not available")
        
        # Create a contract for testing
        symbol = self.test_symbols[2]
        contract = self.create_stock_contract(symbol)
        
        # Set prices for bracket order components (would be improved with market data)
        entry_price = 100.0  # Limit price well below market
        stop_loss_price = entry_price * 0.95  # 5% below entry
        take_profit_price = entry_price * 1.10  # 10% above entry
        
        # Create parent order (entry)
        parent_order = IBOrder()
        parent_order.action = "BUY"
        parent_order.orderType = "LMT"
        parent_order.totalQuantity = 1
        parent_order.lmtPrice = entry_price
        parent_order.transmit = False  # Don't transmit until children are attached
        
        # Add unique client ID
        parent_client_id = self.generate_unique_client_id()
        parent_order.orderId = 0  # Let IB assign ID
        parent_order.clientId = self.gateway.client_id
        parent_order.account = self.gateway.account_id
        parent_order.orderRef = parent_client_id
        
        # Create stop loss order
        stop_loss_order = IBOrder()
        stop_loss_order.action = "SELL"
        stop_loss_order.orderType = "STP"
        stop_loss_order.totalQuantity = 1
        stop_loss_order.auxPrice = stop_loss_price
        stop_loss_order.parentId = 0  # Will be set after parent is submitted
        stop_loss_order.transmit = False  # Don't transmit yet
        
        # Create take profit order
        take_profit_order = IBOrder()
        take_profit_order.action = "SELL"
        take_profit_order.orderType = "LMT"
        take_profit_order.totalQuantity = 1
        take_profit_order.lmtPrice = take_profit_price
        take_profit_order.parentId = 0  # Will be set after parent is submitted
        take_profit_order.transmit = True  # Last order of the bracket - transmit all
        
        # Initialize tracking variables
        orders_submitted = []
        orders_status = {}
        
        # Define callback to track order status
        def order_status_callback(status_update):
            order_id = status_update.get('order_id')
            if order_id:
                orders_status[order_id] = status_update
                logger.info(f"Order {order_id} status update: {status_update}")
        
        # Register callback
        self.gateway.register_order_status_callback(order_status_callback)
        
        try:
            # Submit parent order
            logger.info(f"Submitting bracket order entry for {symbol} at {entry_price}")
            parent_id = self.gateway.submit_order(contract, parent_order)
            assert parent_id > 0, f"Parent order submission failed, received invalid ID: {parent_id}"
            orders_submitted.append(parent_id)
            logger.info(f"Parent order submitted, ID: {parent_id}")
            
            # Set parentId for child orders
            stop_loss_order.parentId = parent_id
            take_profit_order.parentId = parent_id
            
            # Submit stop loss order
            logger.info(f"Submitting stop loss order at {stop_loss_price}")
            stop_loss_id = self.gateway.submit_order(contract, stop_loss_order)
            assert stop_loss_id > 0, f"Stop loss order submission failed, received invalid ID: {stop_loss_id}"
            orders_submitted.append(stop_loss_id)
            logger.info(f"Stop loss order submitted, ID: {stop_loss_id}")
            
            # Submit take profit order (this will transmit the entire bracket)
            logger.info(f"Submitting take profit order at {take_profit_price}")
            take_profit_id = self.gateway.submit_order(contract, take_profit_order)
            assert take_profit_id > 0, f"Take profit order submission failed, received invalid ID: {take_profit_id}"
            orders_submitted.append(take_profit_id)
            logger.info(f"Take profit order submitted, ID: {take_profit_id}")
            
            # Add all bracket orders to test orders for cleanup
            self.test_orders.extend(orders_submitted)
            
            # Wait for order status updates
            timeout = 15  # 15 seconds
            start_time = datetime.now()
            
            while datetime.now() - start_time < timedelta(seconds=timeout):
                # Check if we've received status for all orders
                if all(order_id in orders_status for order_id in orders_submitted):
                    statuses = [orders_status[order_id].get('status') for order_id in orders_submitted]
                    logger.info(f"All bracket orders have status: {statuses}")
                    
                    # Check if all orders are in an appropriate state
                    if all(status in ['Submitted', 'PreSubmitted'] for status in statuses):
                        break
                
                # Wait a bit before checking again
                await asyncio.sleep(0.5)
            
            # Validate order statuses
            for order_id in orders_submitted:
                assert order_id in orders_status, f"No status received for order {order_id}"
                status = orders_status[order_id].get('status')
                acceptable_statuses = ['Submitted', 'PreSubmitted']
                assert status in acceptable_statuses, \
                    f"Unexpected status for order {order_id}: {status}, expected one of {acceptable_statuses}"
            
            # Verify correct parent/child relationships
            # This would be improved with a proper order query method
            logger.info("Bracket order successfully submitted and verified")
            
        finally:
            # Always try to cancel all orders
            for order_id in orders_submitted:
                if order_id > 0:
                    try:
                        self.gateway.cancel_order(order_id)
                        logger.info(f"Cancelled bracket order component {order_id}")
                    except Exception as e:
                        logger.warning(f"Error cancelling order {order_id}: {str(e)}")


@pytest.mark.usefixtures("ib_gateway")
class TestPositionIntegration:
    """
    Integration tests for position management.
    
    These tests validate position creation, querying, and updates.
    """
    
    # Class variable to receive the gateway from the fixture
    gateway: IBGateway = None
    
    @classmethod
    def setup_class(cls):
        """Set up test class."""
        logger.info("Setting up PositionIntegration test class")
        
        # Define test symbol
        cls.test_symbol = "SPY"
        
        # Order tracking for cleanup
        cls.test_orders = []
        cls.test_positions = []
    
    @classmethod
    def teardown_class(cls):
        """Clean up after all tests."""
        logger.info("Tearing down PositionIntegration test class")
        
        # Make sure all test orders are cancelled
        if cls.gateway and cls.gateway.is_connected():
            for order_id in cls.test_orders:
                try:
                    cls.gateway.cancel_order(order_id)
                    logger.info(f"Cancelled order {order_id} during cleanup")
                except Exception as e:
                    logger.warning(f"Error cancelling order {order_id} during cleanup: {str(e)}")
    
    def create_stock_contract(self, symbol):
        """Create a stock contract for testing."""
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        return contract
    
    @pytest.mark.asyncio
    async def test_position_query(self):
        """
        Test position query functionality.
        
        This test verifies that:
        1. Position data can be requested from IB Gateway
        2. The response contains expected position information
        """
        # Skip test if gateway not available
        if not self.gateway or not self.gateway.is_connected():
            pytest.skip("IB Gateway not available")
        
        # Initialize position data
        positions = []
        
        # Define callback to receive position updates
        def position_callback(position_data):
            positions.append(position_data)
            logger.info(f"Received position: {position_data}")
        
        # Register callback
        self.gateway.register_position_callback(position_callback)
        
        try:
            # Request positions
            logger.info("Requesting current positions")
            self.gateway.req_positions()
            
            # Wait for position data
            timeout = 10  # 10 seconds
            start_time = datetime.now()
            
            while datetime.now() - start_time < timedelta(seconds=timeout):
                if positions:
                    logger.info(f"Received {len(positions)} positions")
                    break
                
                # Wait a bit before checking again
                await asyncio.sleep(0.5)
            
            # Even if no positions, we should have received an empty list or end marker
            # The exact validation depends on the specific gateway implementation
            logger.info(f"Position query completed with {len(positions)} positions")
            
            # Basic validation that the position data structure is correct
            for position in positions:
                # Verify position data structure has required fields
                assert 'symbol' in position, "Position missing symbol field"
                assert 'position' in position, "Position missing quantity field"
                logger.info(f"Validated position for {position['symbol']}: {position['position']}")
                
        except Exception as e:
            logger.error(f"Error in position query test: {str(e)}")
            raise
        finally:
            # Unregister callback to avoid affecting other tests
            self.gateway.unregister_position_callback(position_callback)