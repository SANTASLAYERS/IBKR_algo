#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from unittest.mock import MagicMock, patch
import asyncio
from datetime import datetime, timezone
import pytest

from ibapi.common import BarData

from src.gateway import IBGateway
from src.config import Config
from src.minute_data.models import MinuteBar, MinuteBarCollection
from src.minute_data.manager import MinuteBarManager


class TestHistoricalDataCallbacks(unittest.TestCase):
    """Test handling of IB API callbacks for historical data."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = Config(host="127.0.0.1", port=4002, client_id=1)
        
        # Create a patched gateway that won't try to connect to IB
        patcher = patch('src.gateway.IBGateway', autospec=True)
        self.MockGateway = patcher.start()
        self.addCleanup(patcher.stop)
        
        self.gateway = self.MockGateway(self.config)
        
        # Create a MinuteBarManager with our mocked gateway
        self.manager = MinuteBarManager(self.gateway)
        
        # Set up a test request ID and future
        self.req_id = 123
        self.future = asyncio.Future()
        self.manager._data_futures[self.req_id] = self.future
        
        # Set the symbol for this request
        self.symbol = "AAPL"
        self.manager._request_symbols[self.req_id] = self.symbol
    
    def create_test_bar(self, time_str, open_val, high_val, low_val, close_val, volume_val):
        """Helper to create test BarData objects."""
        bar = BarData()
        bar.date = time_str
        bar.open = open_val
        bar.high = high_val
        bar.low = low_val
        bar.close = close_val
        bar.volume = volume_val
        bar.barCount = 10
        bar.average = (open_val + high_val + low_val + close_val) / 4
        return bar
    
    def test_historical_data_callback(self):
        """Test handling of historicalData callbacks."""
        # Create a test bar
        bar = self.create_test_bar(
            "20230501 14:30:00", 150.0, 151.0, 149.5, 150.5, 1000
        )
        
        # Call the callback
        self.manager.historicalData(self.req_id, bar)
        
        # Assert the bar was added to the temporary storage
        self.assertIn(self.req_id, self.manager._temp_bars)
        self.assertEqual(len(self.manager._temp_bars[self.req_id]), 1)
        
        # The future should not be resolved yet
        self.assertFalse(self.future.done())
    
    def test_historical_data_end_callback(self):
        """Test handling of historicalDataEnd callbacks."""
        # Add some test bars to the temporary storage
        self.manager._temp_bars[self.req_id] = []
        
        bar1 = self.create_test_bar(
            "20230501 14:30:00", 150.0, 151.0, 149.5, 150.5, 1000
        )
        self.manager.historicalData(self.req_id, bar1)
        
        bar2 = self.create_test_bar(
            "20230501 14:31:00", 150.5, 152.0, 150.0, 151.5, 1200
        )
        self.manager.historicalData(self.req_id, bar2)
        
        # Call the end callback
        self.manager.historicalDataEnd(self.req_id, "20230501 14:30:00", "20230501 14:31:00")
        
        # Assert the future was resolved with a MinuteBarCollection
        self.assertTrue(self.future.done())
        
        # Get the result from the future
        collection = self.future.result()
        
        # Verify it's a MinuteBarCollection with the right bars
        self.assertIsInstance(collection, MinuteBarCollection)
        self.assertEqual(collection.symbol, self.symbol)
        self.assertEqual(len(collection), 2)
        
        # Check that the temporary storage was cleaned up
        self.assertNotIn(self.req_id, self.manager._temp_bars)
        self.assertNotIn(self.req_id, self.manager._data_futures)
        self.assertNotIn(self.req_id, self.manager._request_symbols)
    
    def test_error_callback(self):
        """Test handling of error callbacks for historical data requests."""
        # Call the error callback with an error for our request
        self.manager.error(self.req_id, 162, "Historical data request pacing violation")
        
        # Assert the future was completed with an exception
        self.assertTrue(self.future.done())
        
        # Check that the exception contains the error message
        with self.assertRaises(Exception) as context:
            self.future.result()
        
        self.assertTrue("Historical data request pacing violation" in str(context.exception))
        
        # Check that the temporary storage was cleaned up
        self.assertNotIn(self.req_id, self.manager._temp_bars)
        self.assertNotIn(self.req_id, self.manager._data_futures)
        self.assertNotIn(self.req_id, self.manager._request_symbols)
    
    def test_handle_empty_results(self):
        """Test handling of empty results in historicalDataEnd."""
        # No bars added, but end callback received
        self.manager.historicalDataEnd(self.req_id, "", "")
        
        # Assert the future was resolved with an empty collection
        self.assertTrue(self.future.done())
        collection = self.future.result()
        
        self.assertIsInstance(collection, MinuteBarCollection)
        self.assertEqual(collection.symbol, self.symbol)
        self.assertEqual(len(collection), 0)


class TestCallbackIntegration(unittest.TestCase):
    """Test the integration of callbacks with the IBGateway class."""
    
    @patch('src.gateway.IBGateway', autospec=True)
    def test_gateway_integration(self, MockGateway):
        """Test that callbacks are properly connected to the gateway."""
        config = Config(host="127.0.0.1", port=4002, client_id=1)
        gateway = MockGateway(config)
        
        # Initialize MinuteBarManager with the gateway
        manager = MinuteBarManager(gateway)
        
        # Verify the callback methods were added to the gateway
        # This would happen in the __init__ method of MinuteBarManager
        self.assertEqual(gateway.historicalData, manager.historicalData)
        self.assertEqual(gateway.historicalDataEnd, manager.historicalDataEnd)


if __name__ == "__main__":
    unittest.main()