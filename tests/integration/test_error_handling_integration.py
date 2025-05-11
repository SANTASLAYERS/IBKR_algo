#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Integration tests for error handling and recovery with IB Gateway.

These tests validate how the system handles various error conditions
and recovers from connection issues.
"""

import asyncio
import logging
import pytest
import socket
import time
from datetime import datetime, timedelta
from ibapi.contract import Contract
from ibapi.order import Order as IBOrder

from src.gateway import IBGateway
from src.error_handler import ErrorHandler

logger = logging.getLogger("error_handling_integration_tests")


@pytest.mark.usefixtures("ib_gateway")
class TestErrorHandlingIntegration:
    """
    Integration tests for error handling and recovery.
    
    These tests validate behavior when errors occur during normal operations.
    """
    
    # Class variable to receive the gateway from the fixture
    gateway: IBGateway = None
    
    @classmethod
    def setup_class(cls):
        """Set up test class."""
        logger.info("Setting up ErrorHandlingIntegration test class")
        
        # Track resources for cleanup
        cls.test_orders = []
        cls.market_data_requests = []
    
    @classmethod
    def teardown_class(cls):
        """Clean up after all tests."""
        logger.info("Tearing down ErrorHandlingIntegration test class")
        
        # Clean up any resources
        if cls.gateway and cls.gateway.is_connected():
            # Cancel orders
            for order_id in cls.test_orders:
                try:
                    cls.gateway.cancel_order(order_id)
                except Exception:
                    pass
                    
            # Cancel market data subscriptions
            for req_id in cls.market_data_requests:
                try:
                    cls.gateway.unsubscribe_market_data(req_id)
                except Exception:
                    pass
    
    def create_stock_contract(self, symbol):
        """Create a stock contract for testing."""
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        return contract
    
    @pytest.mark.asyncio
    async def test_invalid_contract_handling(self):
        """
        Test handling of invalid contract specifications.
        
        This test verifies that:
        1. Requests for invalid contracts generate appropriate errors
        2. The error is captured and handled properly
        3. The error doesn't crash the connection
        """
        # Skip test if gateway not available
        if not self.gateway or not self.gateway.is_connected():
            pytest.skip("IB Gateway not available")
        
        # Create an invalid contract (non-existent symbol)
        invalid_symbol = "INVALID123XYZ"  # This symbol should not exist
        contract = self.create_stock_contract(invalid_symbol)
        
        # Initialize error tracking
        error_received = False
        error_info = None
        
        # Define error callback
        def error_callback(req_id, error_code, error_msg):
            nonlocal error_received, error_info
            error_received = True
            error_info = {
                'req_id': req_id,
                'error_code': error_code,
                'error_msg': error_msg
            }
            logger.info(f"Received error: {error_code} - {error_msg}")
        
        # Register callback
        self.gateway.register_error_callback(error_callback)
        
        # Initialize market data tracking
        market_data_received = []
        
        # Define market data callback
        def market_data_callback(data):
            market_data_received.append(data)
            logger.info(f"Received market data: {data}")
        
        try:
            # Request market data for invalid contract
            logger.info(f"Requesting market data for invalid symbol: {invalid_symbol}")
            req_id = self.gateway.subscribe_market_data(
                contract=contract,
                callback=market_data_callback
            )
            
            assert req_id > 0, "Market data request failed to generate request ID"
            logger.info(f"Market data requested, request ID: {req_id}")
            
            # Add to tracking for cleanup
            self.market_data_requests.append(req_id)
            
            # Wait for error response
            timeout = 10  # 10 seconds
            start_time = datetime.now()
            
            while datetime.now() - start_time < timedelta(seconds=timeout):
                if error_received:
                    logger.info("Error response received")
                    break
                
                # Wait a bit before checking again
                await asyncio.sleep(0.5)
            
            # Validate error handling
            assert error_received, f"No error received for invalid symbol {invalid_symbol}"
            assert error_info, "Error info not captured"
            
            # The specific error code and message may vary, but there should be an error
            # related to the contract
            logger.info(f"Validated error handling for invalid contract: {error_info}")
            
            # Verify gateway still connected after error
            assert self.gateway.is_connected(), "Gateway disconnected after contract error"
            
        finally:
            # Unregister callback
            self.gateway.unregister_error_callback(error_callback)
            
            # Cancel market data request
            if 'req_id' in locals() and req_id > 0:
                logger.info(f"Cancelling market data request {req_id}")
                try:
                    self.gateway.unsubscribe_market_data(req_id)
                except Exception as e:
                    logger.warning(f"Error cancelling market data request: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_invalid_order_handling(self):
        """
        Test handling of invalid order specifications.
        
        This test verifies that:
        1. Invalid orders are properly rejected
        2. The error is captured and handled correctly
        3. The system remains operational after an order error
        """
        # Skip test if gateway not available
        if not self.gateway or not self.gateway.is_connected():
            pytest.skip("IB Gateway not available")
        
        # Create a valid contract
        symbol = "SPY"
        contract = self.create_stock_contract(symbol)
        
        # Create an invalid order (no price for limit order)
        invalid_order = IBOrder()
        invalid_order.action = "BUY"
        invalid_order.orderType = "LMT"  # Limit order requires a price
        invalid_order.totalQuantity = 1
        # Intentionally omit the limit price
        
        # Initialize error tracking
        order_error_received = False
        order_error_info = None
        
        # Define order status callback
        def order_status_callback(status_update):
            logger.info(f"Order status update: {status_update}")
        
        # Define error callback
        def error_callback(req_id, error_code, error_msg):
            nonlocal order_error_received, order_error_info
            # Only capture order-related errors
            if req_id > 0:  # Order IDs are typically positive
                order_error_received = True
                order_error_info = {
                    'req_id': req_id,
                    'error_code': error_code,
                    'error_msg': error_msg
                }
                logger.info(f"Received order error: {error_code} - {error_msg}")
        
        # Register callbacks
        self.gateway.register_order_status_callback(order_status_callback)
        self.gateway.register_error_callback(error_callback)
        
        try:
            # Submit the invalid order
            logger.info(f"Submitting invalid order (limit order without price) for {symbol}")
            order_id = self.gateway.submit_order(contract, invalid_order)
            
            # Some gateways might reject immediately, others might assign an ID
            # and reject later
            if order_id > 0:
                logger.info(f"Order assigned ID: {order_id}")
                self.test_orders.append(order_id)
            
            # Wait for error response
            timeout = 10  # 10 seconds
            start_time = datetime.now()
            
            while datetime.now() - start_time < timedelta(seconds=timeout):
                if order_error_received:
                    logger.info("Order error received")
                    break
                
                # Wait a bit before checking again
                await asyncio.sleep(0.5)
            
            # Validate error handling
            assert order_error_received, "No error received for invalid order"
            assert order_error_info, "Order error info not captured"
            
            # The specific error code and message may vary
            logger.info(f"Validated error handling for invalid order: {order_error_info}")
            
            # Verify gateway still connected after error
            assert self.gateway.is_connected(), "Gateway disconnected after order error"
            
        finally:
            # Unregister callbacks
            self.gateway.unregister_order_status_callback(order_status_callback)
            self.gateway.unregister_error_callback(error_callback)
            
            # Cancel order if one was created
            if 'order_id' in locals() and order_id > 0:
                logger.info(f"Cancelling order {order_id}")
                try:
                    self.gateway.cancel_order(order_id)
                except Exception as e:
                    logger.warning(f"Error cancelling order: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_multiple_errors_handling(self):
        """
        Test handling of multiple errors in sequence.
        
        This test verifies that:
        1. The system can handle multiple errors in quick succession
        2. Error handling remains consistent
        3. The connection remains stable
        """
        # Skip test if gateway not available
        if not self.gateway or not self.gateway.is_connected():
            pytest.skip("IB Gateway not available")
        
        # Create several invalid contracts with different issues
        invalid_contracts = [
            {"symbol": "INVALID123", "secType": "STK", "exchange": "SMART", "currency": "USD"},
            {"symbol": "AAPL", "secType": "STK", "exchange": "INVALID_EXCHANGE", "currency": "USD"},
            {"symbol": "SPY", "secType": "STK", "exchange": "SMART", "currency": "XYZ"}  # Invalid currency
        ]
        
        # Initialize error tracking
        errors_received = []
        
        # Define error callback
        def error_callback(req_id, error_code, error_msg):
            errors_received.append({
                'req_id': req_id,
                'error_code': error_code,
                'error_msg': error_msg
            })
            logger.info(f"Received error: {error_code} - {error_msg}")
        
        # Register callback
        self.gateway.register_error_callback(error_callback)
        
        # Initialize market data requests for cleanup
        market_data_reqs = []
        
        try:
            # Submit multiple problematic requests in sequence
            for i, contract_data in enumerate(invalid_contracts):
                # Create contract
                contract = Contract()
                for key, value in contract_data.items():
                    setattr(contract, key, value)
                
                # Request market data
                logger.info(f"Requesting market data for invalid contract {i+1}: {contract_data}")
                req_id = self.gateway.subscribe_market_data(
                    contract=contract,
                    callback=lambda data: None  # Dummy callback
                )
                
                # Track request for cleanup
                if req_id > 0:
                    market_data_reqs.append(req_id)
                    self.market_data_requests.append(req_id)
                
                # Wait briefly between requests
                await asyncio.sleep(0.5)
            
            # Wait for error responses
            timeout = 15  # 15 seconds
            start_time = datetime.now()
            
            while datetime.now() - start_time < timedelta(seconds=timeout):
                if len(errors_received) >= len(invalid_contracts):
                    logger.info(f"Received enough errors: {len(errors_received)}")
                    break
                
                # Wait a bit before checking again
                await asyncio.sleep(0.5)
            
            # Validate error handling
            assert errors_received, "No errors received for invalid contracts"
            logger.info(f"Received {len(errors_received)} errors")
            
            # Verify gateway still connected after multiple errors
            assert self.gateway.is_connected(), "Gateway disconnected after multiple errors"
            
            # Test that a valid request still works after errors
            valid_contract = self.create_stock_contract("SPY")
            logger.info("Testing valid market data request after errors")
            req_id = self.gateway.subscribe_market_data(
                contract=valid_contract,
                callback=lambda data: None  # Dummy callback
            )
            
            assert req_id > 0, "Valid request failed after error sequence"
            market_data_reqs.append(req_id)
            self.market_data_requests.append(req_id)
            
            logger.info("System remains operational after handling multiple errors")
            
        finally:
            # Unregister callback
            self.gateway.unregister_error_callback(error_callback)
            
            # Cancel all market data requests
            for req_id in market_data_reqs:
                try:
                    self.gateway.unsubscribe_market_data(req_id)
                    logger.info(f"Cancelled market data request {req_id}")
                except Exception as e:
                    logger.warning(f"Error cancelling market data request {req_id}: {str(e)}")


@pytest.mark.usefixtures("ib_gateway")
class TestReconnectionIntegration:
    """
    Integration tests for connection loss and reconnection.
    
    These tests validate connection recovery behavior.
    Note: Some tests require manual intervention or may not be
    fully automatable due to the nature of connection testing.
    """
    
    # Class variable to receive the gateway from the fixture
    gateway: IBGateway = None
    
    @classmethod
    def setup_class(cls):
        """Set up test class."""
        logger.info("Setting up ReconnectionIntegration test class")
    
    @pytest.mark.asyncio
    async def test_heartbeat_monitoring(self):
        """
        Test heartbeat monitoring functionality.
        
        This test verifies that:
        1. Heartbeat requests are sent and processed
        2. The system correctly identifies active connections
        """
        # Skip test if gateway not available
        if not self.gateway or not self.gateway.is_connected():
            pytest.skip("IB Gateway not available")
        
        try:
            # Verify initial connection state
            assert self.gateway.is_connected(), "Gateway should be connected"
            
            # Request heartbeat
            logger.info("Requesting heartbeat")
            self.gateway.reqHeartbeat()
            
            # Wait briefly for heartbeat response
            await asyncio.sleep(2)
            
            # Verify connection still active after heartbeat
            assert self.gateway.is_connected(), "Gateway should still be connected after heartbeat"
            logger.info("Heartbeat monitoring is functioning correctly")
            
        except Exception as e:
            logger.error(f"Error in heartbeat monitoring test: {str(e)}")
            raise
    
    @pytest.mark.asyncio
    async def test_normal_disconnect_reconnect(self):
        """
        Test normal disconnection and reconnection.
        
        This test verifies that:
        1. The system can gracefully disconnect
        2. The system can reconnect after a normal disconnection
        3. All functionality is restored after reconnection
        """
        # Skip test if gateway not available
        if not self.gateway or not self.gateway.is_connected():
            pytest.skip("IB Gateway not available")
        
        # Create a valid contract for testing
        symbol = "SPY"
        contract = self.create_stock_contract(symbol)
        
        try:
            # Verify initial connection
            assert self.gateway.is_connected(), "Gateway should be connected initially"
            
            # Perform a normal disconnect
            logger.info("Performing normal disconnect")
            self.gateway.disconnect()
            
            # Verify disconnected state
            assert not self.gateway.is_connected(), "Gateway should be disconnected"
            logger.info("Successfully disconnected")
            
            # Attempt reconnection
            logger.info("Attempting to reconnect")
            connected = await self.gateway.reconnect()
            
            # Verify reconnection
            assert connected, "Reconnection failed"
            assert self.gateway.is_connected(), "Gateway should be connected after reconnection"
            logger.info("Successfully reconnected")
            
            # Verify functionality after reconnection by making a request
            logger.info("Testing functionality after reconnection")
            req_id = self.gateway.subscribe_market_data(
                contract=contract,
                callback=lambda data: None,  # Dummy callback
                snapshot=True  # Use snapshot to avoid ongoing subscription
            )
            
            assert req_id > 0, "Market data request failed after reconnection"
            logger.info(f"Market data request successful after reconnection (ID: {req_id})")
            
            # Clean up the request
            self.gateway.unsubscribe_market_data(req_id)
            
            logger.info("Normal disconnect/reconnect cycle validated successfully")
            
        except Exception as e:
            logger.error(f"Error in disconnect/reconnect test: {str(e)}")
            raise
        finally:
            # Ensure connection is re-established if the test fails
            if not self.gateway.is_connected():
                try:
                    await self.gateway.reconnect()
                except Exception:
                    pass