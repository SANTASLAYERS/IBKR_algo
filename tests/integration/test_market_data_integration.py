#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Integration tests for market data functionality with IB Gateway.

These tests validate the actual market data retrieval capabilities.
"""

import asyncio
import logging
import pytest
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from ibapi.contract import Contract

from src.gateway import IBGateway

logger = logging.getLogger("market_data_integration_tests")


@pytest.mark.usefixtures("ib_gateway")
class TestMarketDataIntegration:
    """
    Integration tests for market data retrieval.
    
    These tests validate real-time market data subscriptions and historical
    data retrieval from a live IB Gateway.
    """
    
    # Class variable to receive the gateway from the fixture
    gateway: IBGateway = None
    
    @classmethod
    def setup_class(cls):
        """Set up test class."""
        logger.info("Setting up MarketDataIntegration test class")
        
        # Define test symbols (liquid ETFs that are always available)
        cls.test_symbols = ["SPY", "QQQ", "IWM"]
        
        # Track market data subscriptions for cleanup
        cls.market_data_requests = []
    
    @classmethod
    def teardown_class(cls):
        """Clean up after all tests."""
        logger.info("Tearing down MarketDataIntegration test class")
        
        # Cancel all market data subscriptions
        if cls.gateway and cls.gateway.is_connected():
            for req_id in cls.market_data_requests:
                try:
                    cls.gateway.unsubscribe_market_data(req_id)
                    logger.info(f"Unsubscribed from market data request {req_id}")
                except Exception as e:
                    logger.warning(f"Error unsubscribing from market data request {req_id}: {str(e)}")
    
    def create_stock_contract(self, symbol):
        """Create a stock contract for testing."""
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        return contract
    
    @pytest.mark.asyncio
    async def test_market_data_subscription(self):
        """
        Test market data subscription and data reception.
        
        This test verifies that:
        1. Market data can be requested for a symbol
        2. The subscription generates market data updates
        3. The data contains expected fields (bid, ask, last, etc.)
        """
        # Skip test if gateway not available
        if not self.gateway or not self.gateway.is_connected():
            pytest.skip("IB Gateway not available")
        
        # Select test symbol
        symbol = self.test_symbols[0]
        contract = self.create_stock_contract(symbol)
        
        # Initialize market data container
        market_data_received = []
        
        # Define callback to track market data updates
        def market_data_callback(data):
            market_data_received.append(data)
            logger.info(f"Received market data: {data}")
        
        try:
            # Subscribe to market data
            logger.info(f"Subscribing to market data for {symbol}")
            generic_tick_list = "100,101,104,105,106,107,165,221,233,236,258,293,294,295,318"
            req_id = self.gateway.subscribe_market_data(
                contract=contract,
                generic_tick_list=generic_tick_list,
                snapshot=False,
                callback=market_data_callback
            )
            
            assert req_id > 0, f"Market data subscription failed for {symbol}"
            logger.info(f"Subscribed to market data, request ID: {req_id}")
            
            # Add to subscription list for cleanup
            self.market_data_requests.append(req_id)
            
            # Wait for market data updates
            timeout = 10  # 10 seconds
            start_time = datetime.now()
            
            while datetime.now() - start_time < timedelta(seconds=timeout):
                if market_data_received:
                    # We've received some market data
                    logger.info(f"Received {len(market_data_received)} market data updates")
                    break
                
                # Wait a bit before checking again
                await asyncio.sleep(0.5)
            
            # Validate received market data
            assert market_data_received, f"No market data received for {symbol} within timeout"
            
            # Get the latest market data
            latest_data = market_data_received[-1]
            
            # Verify core price fields (at least some should be present)
            # The exact fields will depend on market conditions and time of day
            price_fields = ['last_price', 'bid_price', 'ask_price']
            has_price_data = any(field in latest_data and latest_data[field] is not None for field in price_fields)
            
            assert has_price_data, f"No price data received in market data: {latest_data}"
            logger.info(f"Validated market data for {symbol}")
            
        finally:
            # Unsubscribe from market data
            if req_id > 0:
                logger.info(f"Unsubscribing from market data request {req_id}")
                self.gateway.unsubscribe_market_data(req_id)
    
    @pytest.mark.asyncio
    async def test_historical_data_request(self):
        """
        Test historical data request functionality.
        
        This test verifies that:
        1. Historical bar data can be requested for a symbol
        2. The data is returned in the expected format
        3. The data contains valid OHLC price information
        """
        # Skip test if gateway not available
        if not self.gateway or not self.gateway.is_connected():
            pytest.skip("IB Gateway not available")
        
        # Select test symbol
        symbol = self.test_symbols[1]
        contract = self.create_stock_contract(symbol)
        
        # Initialize historical data container
        historical_data_received = []
        historical_complete = False
        
        # Define callbacks for historical data
        def historical_data_callback(bar_data):
            historical_data_received.append(bar_data)
            logger.info(f"Received historical bar: {bar_data}")
        
        def historical_end_callback():
            nonlocal historical_complete
            historical_complete = True
            logger.info("Historical data request completed")
        
        try:
            # Request historical data
            end_date_time = ""  # Empty for current time
            duration_str = "1 D"  # 1 day of data
            bar_size_str = "1 hour"  # 1-hour bars
            what_to_show = "MIDPOINT"  # Midpoint prices
            use_rth = 1  # Use regular trading hours only
            
            logger.info(f"Requesting historical data for {symbol}: {duration_str} of {bar_size_str} bars")
            req_id = self.gateway.req_historical_data(
                contract=contract,
                end_date_time=end_date_time,
                duration_str=duration_str,
                bar_size_str=bar_size_str,
                what_to_show=what_to_show,
                use_rth=use_rth,
                callback=historical_data_callback,
                end_callback=historical_end_callback
            )
            
            assert req_id > 0, f"Historical data request failed for {symbol}"
            logger.info(f"Historical data requested, request ID: {req_id}")
            
            # Wait for historical data to complete
            timeout = 20  # 20 seconds
            start_time = datetime.now()
            
            while datetime.now() - start_time < timedelta(seconds=timeout):
                if historical_complete:
                    logger.info("Historical data request marked as complete")
                    break
                
                # Wait a bit before checking again
                await asyncio.sleep(0.5)
            
            # Validate received historical data
            assert historical_data_received, f"No historical data received for {symbol} within timeout"
            assert historical_complete, f"Historical data request for {symbol} did not complete within timeout"
            
            logger.info(f"Received {len(historical_data_received)} historical bars")
            
            # Validate structure of historical data
            for bar in historical_data_received:
                # Verify each bar has the required fields
                assert 'date' in bar, "Historical bar missing date field"
                assert 'open' in bar, "Historical bar missing open field"
                assert 'high' in bar, "Historical bar missing high field"
                assert 'low' in bar, "Historical bar missing low field"
                assert 'close' in bar, "Historical bar missing close field"
                assert 'volume' in bar, "Historical bar missing volume field"
                
                # Verify price data integrity
                assert bar['high'] >= bar['low'], f"Invalid price data: high {bar['high']} < low {bar['low']}"
                assert bar['high'] >= bar['open'], f"Invalid price data: high {bar['high']} < open {bar['open']}"
                assert bar['high'] >= bar['close'], f"Invalid price data: high {bar['high']} < close {bar['close']}"
                assert bar['low'] <= bar['open'], f"Invalid price data: low {bar['low']} > open {bar['open']}"
                assert bar['low'] <= bar['close'], f"Invalid price data: low {bar['low']} > close {bar['close']}"
            
            logger.info(f"Validated historical data for {symbol}")
            
        except Exception as e:
            logger.error(f"Error in historical data test: {str(e)}")
            raise


@pytest.mark.usefixtures("ib_gateway")
class TestAccountIntegration:
    """
    Integration tests for account information retrieval.
    
    These tests validate account data retrieval capabilities.
    """
    
    # Class variable to receive the gateway from the fixture
    gateway: IBGateway = None
    
    @classmethod
    def setup_class(cls):
        """Set up test class."""
        logger.info("Setting up AccountIntegration test class")
    
    @pytest.mark.asyncio
    async def test_account_summary(self):
        """
        Test account summary retrieval.
        
        This test verifies that:
        1. Account summary can be requested
        2. The response contains expected account information fields
        """
        # Skip test if gateway not available
        if not self.gateway or not self.gateway.is_connected():
            pytest.skip("IB Gateway not available")
        
        # Initialize account data
        account_values = {}
        account_complete = False
        
        # Define callbacks for account updates
        def account_summary_callback(data):
            tag = data.get('tag')
            value = data.get('value')
            
            if tag and value:
                account_values[tag] = value
                logger.info(f"Received account value: {tag} = {value}")
        
        def account_summary_end_callback():
            nonlocal account_complete
            account_complete = True
            logger.info("Account summary request completed")
        
        try:
            # Request account summary
            logger.info("Requesting account summary")
            
            account_id = self.gateway.account_id
            assert account_id, "No account ID configured for gateway"
            
            # Define key account values to request
            tags = "NetLiquidation,AvailableFunds,BuyingPower,EquityWithLoanValue,GrossPositionValue"
            
            req_id = self.gateway.req_account_summary(
                account_id=account_id,
                tags=tags,
                callback=account_summary_callback,
                end_callback=account_summary_end_callback
            )
            
            assert req_id > 0, "Account summary request failed"
            logger.info(f"Account summary requested, request ID: {req_id}")
            
            # Wait for account data to complete
            timeout = 10  # 10 seconds
            start_time = datetime.now()
            
            while datetime.now() - start_time < timedelta(seconds=timeout):
                if account_complete:
                    logger.info("Account summary request marked as complete")
                    break
                
                # Wait a bit before checking again
                await asyncio.sleep(0.5)
            
            # Validate received account data
            assert account_values, "No account values received within timeout"
            assert account_complete, "Account summary request did not complete within timeout"
            
            logger.info(f"Received {len(account_values)} account values")
            
            # Validate core account values
            expected_fields = tags.split(',')
            for field in expected_fields:
                assert field in account_values, f"Missing expected account value: {field}"
                logger.info(f"Validated account value {field}: {account_values[field]}")
            
        finally:
            # Cancel account updates if needed
            if 'req_id' in locals() and req_id > 0:
                logger.info(f"Cancelling account summary request {req_id}")
                self.gateway.cancel_account_summary(req_id)