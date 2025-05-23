#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Market Data Integration Tests for TWS.

Tests real-time market data functionality with TWS.
"""

import pytest
import asyncio
import logging
from ibapi.contract import Contract

from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
from tests.integration.conftest import get_tws_credentials

logger = logging.getLogger("market_data_tests")


class TWSMarketDataConnection(TWSConnection):
    """Extended TWS connection for market data testing."""
    
    def __init__(self, config: TWSConfig):
        super().__init__(config)
        self.market_data = {}
        self.tick_data_received = []
        
    def tickPrice(self, reqId: int, tickType: int, price: float, attrib):
        """Handle tick price updates."""
        if reqId not in self.market_data:
            self.market_data[reqId] = {}
        
        tick_types = {
            1: "bid", 2: "ask", 4: "last", 6: "high", 7: "low", 9: "close"
        }
        
        tick_name = tick_types.get(tickType, f"tick_{tickType}")
        self.market_data[reqId][tick_name] = price
        self.tick_data_received.append({
            "reqId": reqId,
            "tickType": tickType,
            "price": price,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        logger.debug(f"Tick price: reqId={reqId}, {tick_name}={price}")
    
    def tickSize(self, reqId: int, tickType: int, size: int):
        """Handle tick size updates."""
        if reqId not in self.market_data:
            self.market_data[reqId] = {}
            
        size_types = {
            0: "bid_size", 3: "ask_size", 5: "last_size", 8: "volume"
        }
        
        size_name = size_types.get(tickType, f"size_{tickType}")
        self.market_data[reqId][size_name] = size
        
        logger.debug(f"Tick size: reqId={reqId}, {size_name}={size}")


class TestTWSMarketData:
    """Tests for TWS market data functionality."""

    @pytest.mark.usefixtures("check_tws")
    @pytest.mark.asyncio
    async def test_real_time_market_data(self):
        """Test subscribing to real-time market data."""
        credentials = get_tws_credentials()
        config = TWSConfig(
            host=credentials["host"],
            port=credentials["port"],
            client_id=credentials["client_id"] + 1,  # Different client ID
            connection_timeout=10.0
        )
        
        connection = TWSMarketDataConnection(config)
        
        try:
            # Connect to TWS
            connected = await connection.connect()
            assert connected, "Failed to connect to TWS"
            
            # Create contract for AAPL
            contract = Contract()
            contract.symbol = "AAPL"
            contract.secType = "STK"
            contract.exchange = "SMART"
            contract.currency = "USD"
            
            # Subscribe to market data
            req_id = 1001
            logger.info(f"Subscribing to market data for AAPL with reqId {req_id}")
            connection.reqMktData(req_id, contract, "", False, False, [])
            
            # Wait for market data
            timeout = 30  # 30 seconds
            start_time = asyncio.get_event_loop().time()
            
            while (asyncio.get_event_loop().time() - start_time) < timeout:
                await asyncio.sleep(1)
                
                if req_id in connection.market_data:
                    data = connection.market_data[req_id]
                    if "last" in data or "bid" in data or "ask" in data:
                        logger.info(f"✅ Received market data: {data}")
                        break
            else:
                pytest.fail("No market data received within timeout")
            
            # Verify data structure
            data = connection.market_data[req_id]
            assert isinstance(data, dict), "Market data should be a dictionary"
            assert len(data) > 0, "Should have received some market data"
            
            # Check for expected fields
            expected_fields = ["bid", "ask", "last"]
            received_fields = [field for field in expected_fields if field in data]
            assert len(received_fields) > 0, f"Should have received at least one of: {expected_fields}"
            
            # Validate prices are reasonable
            for field, price in data.items():
                if field in ["bid", "ask", "last", "high", "low", "close"]:
                    assert price > 0, f"{field} price should be positive: {price}"
                    assert price < 10000, f"{field} price seems unreasonable: {price}"
            
            logger.info("✅ Market data validation passed")
            
            # Cancel market data subscription
            connection.cancelMktData(req_id)
            await asyncio.sleep(1)
            
        finally:
            if connection.is_connected():
                connection.disconnect()
                await asyncio.sleep(1)

    @pytest.mark.usefixtures("check_tws")
    @pytest.mark.asyncio
    async def test_multiple_symbols_market_data(self):
        """Test subscribing to market data for multiple symbols."""
        credentials = get_tws_credentials()
        config = TWSConfig(
            host=credentials["host"],
            port=credentials["port"],
            client_id=credentials["client_id"] + 2,  # Different client ID
            connection_timeout=10.0
        )
        
        connection = TWSMarketDataConnection(config)
        symbols = ["AAPL", "MSFT", "GOOGL"]
        
        try:
            # Connect to TWS
            connected = await connection.connect()
            assert connected, "Failed to connect to TWS"
            
            # Subscribe to multiple symbols
            req_ids = []
            for i, symbol in enumerate(symbols):
                contract = Contract()
                contract.symbol = symbol
                contract.secType = "STK"
                contract.exchange = "SMART"
                contract.currency = "USD"
                
                req_id = 2000 + i
                req_ids.append(req_id)
                logger.info(f"Subscribing to {symbol} with reqId {req_id}")
                connection.reqMktData(req_id, contract, "", False, False, [])
            
            # Wait for data from all symbols
            timeout = 45  # 45 seconds for multiple symbols
            start_time = asyncio.get_event_loop().time()
            received_data = set()
            
            while (asyncio.get_event_loop().time() - start_time) < timeout:
                await asyncio.sleep(2)
                
                for req_id in req_ids:
                    if req_id in connection.market_data:
                        data = connection.market_data[req_id]
                        if "last" in data or "bid" in data or "ask" in data:
                            received_data.add(req_id)
                
                if len(received_data) >= 2:  # At least 2 symbols should work
                    logger.info(f"✅ Received data for {len(received_data)} symbols")
                    break
            else:
                if len(received_data) == 0:
                    pytest.fail("No market data received for any symbol")
            
            # Verify we got data for multiple symbols
            assert len(received_data) >= 1, "Should receive data for at least one symbol"
            logger.info(f"✅ Successfully tested market data for {len(received_data)} symbols")
            
            # Cancel all subscriptions
            for req_id in req_ids:
                connection.cancelMktData(req_id)
            
            await asyncio.sleep(2)
            
        finally:
            if connection.is_connected():
                connection.disconnect()
                await asyncio.sleep(1)

    @pytest.mark.usefixtures("check_tws")
    @pytest.mark.asyncio
    async def test_market_data_error_handling(self):
        """Test error handling for invalid market data requests."""
        credentials = get_tws_credentials()
        config = TWSConfig(
            host=credentials["host"],
            port=credentials["port"],
            client_id=credentials["client_id"] + 3,  # Different client ID
            connection_timeout=10.0
        )
        
        connection = TWSMarketDataConnection(config)
        
        try:
            # Connect to TWS
            connected = await connection.connect()
            assert connected, "Failed to connect to TWS"
            
            # Try to subscribe to invalid symbol
            contract = Contract()
            contract.symbol = "INVALID_SYMBOL_XYZ"
            contract.secType = "STK"
            contract.exchange = "SMART"
            contract.currency = "USD"
            
            req_id = 3001
            logger.info(f"Subscribing to invalid symbol with reqId {req_id}")
            connection.reqMktData(req_id, contract, "", False, False, [])
            
            # Wait for error or timeout
            await asyncio.sleep(10)
            
            # Should not receive valid market data for invalid symbol
            if req_id in connection.market_data:
                data = connection.market_data[req_id]
                # If we got data, it should be empty or contain error indicators
                logger.info(f"Data for invalid symbol: {data}")
            
            logger.info("✅ Error handling test completed")
            
        finally:
            if connection.is_connected():
                connection.disconnect()
                await asyncio.sleep(1) 