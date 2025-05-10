#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from unittest.mock import MagicMock, patch
import asyncio
from datetime import datetime, timezone, timedelta
import pytest

from ibapi.contract import Contract
from ibapi.common import BarData

from src.gateway import IBGateway
from src.config import Config
from src.minute_data.models import MinuteBar, MinuteBarCollection
from src.minute_data.manager import MinuteBarManager


class TestMinuteDataFetching(unittest.TestCase):
    """Test the historical minute data fetching functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = Config(host="127.0.0.1", port=4002, client_id=1)
        
        # Create a mock gateway with required methods mocked
        self.gateway = MagicMock(spec=IBGateway)
        self.gateway.config = self.config
        self.gateway.get_next_request_id.return_value = 123
        
        # Create a minute bar manager with the mock gateway
        self.manager = MinuteBarManager(self.gateway)
        
        # Sample contract
        self.contract = Contract()
        self.contract.symbol = "AAPL"
        self.contract.secType = "STK"
        self.contract.exchange = "SMART"
        self.contract.currency = "USD"
        
        # Sample dates
        self.end_date = datetime.now(timezone.utc)
        self.start_date = self.end_date - timedelta(days=1)
    
    def test_request_historical_minute_data(self):
        """Test requesting historical minute data."""
        # Call the method under test
        req_id = self.manager.request_historical_minute_data(
            contract=self.contract,
            end_date=self.end_date,
            duration="1 D",  # 1 day
            bar_size="1 min"
        )
        
        # Assert the gateway's reqHistoricalData was called correctly
        self.gateway.reqHistoricalData.assert_called_once()
        
        # Check the call arguments
        call_args = self.gateway.reqHistoricalData.call_args[0]
        self.assertEqual(call_args[0], 123)  # Request ID
        self.assertEqual(call_args[1], self.contract)  # Contract
        
        # Assert the right formatting for end date
        # The actual implementation should convert datetime to the format IB expects
        
        # Assert duration and bar size were passed correctly
        self.assertEqual(call_args[3], "1 D")  # Duration
        self.assertEqual(call_args[4], "1 min")  # Bar size
        
        # Assert "TRADES" was used for what to show
        self.assertEqual(call_args[5], "TRADES")
        
        # Assert return value is the request ID
        self.assertEqual(req_id, 123)
    
    @patch('src.minute_data.manager.asyncio.Future')
    def test_request_historical_minute_data_async(self, mock_future):
        """Test requesting historical minute data asynchronously."""
        # Set up the mock future
        future_instance = MagicMock()
        mock_future.return_value = future_instance
        
        # Call the method under test
        future = self.manager.request_historical_minute_data_async(
            contract=self.contract,
            end_date=self.end_date,
            duration="1 D",
            bar_size="1 min"
        )
        
        # Assert gateway's reqHistoricalData was called
        self.gateway.reqHistoricalData.assert_called_once()
        
        # Assert the future was created and stored
        self.assertEqual(future, future_instance)
        self.assertIn(123, self.manager._data_futures)
        self.assertEqual(self.manager._data_futures[123], future_instance)
    
    def test_cancel_historical_data_request(self):
        """Test cancelling a historical data request."""
        # Set up a pending request
        req_id = 123
        self.manager._data_futures[req_id] = MagicMock()
        
        # Call the method under test
        self.manager.cancel_historical_data_request(req_id)
        
        # Assert the gateway's cancelHistoricalData was called
        self.gateway.cancelHistoricalData.assert_called_once_with(req_id)
        
        # Assert the future was completed with a cancellation
        self.manager._data_futures[req_id].cancel.assert_called_once()
        
        # Assert the request was removed from pending requests
        self.assertNotIn(req_id, self.manager._data_futures)
    
    def test_convert_ib_bar_to_minute_bar(self):
        """Test converting IB bar data to MinuteBar."""
        # Create a sample IB BarData
        bar_time = "20230501 14:30:00"
        bar = BarData()
        bar.date = bar_time
        bar.open = 150.0
        bar.high = 151.0
        bar.low = 149.5
        bar.close = 150.5
        bar.volume = 1000
        bar.barCount = 10
        bar.average = 150.25
        
        # Call the method under test
        minute_bar = self.manager._convert_ib_bar_to_minute_bar(
            bar, "AAPL"
        )
        
        # Assert the conversion was correct
        self.assertIsInstance(minute_bar, MinuteBar)
        self.assertEqual(minute_bar.symbol, "AAPL")
        self.assertEqual(minute_bar.open_price, 150.0)
        self.assertEqual(minute_bar.high_price, 151.0)
        self.assertEqual(minute_bar.low_price, 149.5)
        self.assertEqual(minute_bar.close_price, 150.5)
        self.assertEqual(minute_bar.volume, 1000)
        self.assertEqual(minute_bar.count, 10)
        self.assertEqual(minute_bar.wap, 150.25)
        
        # Assert timestamp was converted correctly
        expected_dt = datetime(2023, 5, 1, 14, 30, 0, tzinfo=timezone.utc)
        self.assertEqual(minute_bar.timestamp.year, expected_dt.year)
        self.assertEqual(minute_bar.timestamp.month, expected_dt.month)
        self.assertEqual(minute_bar.timestamp.day, expected_dt.day)
        self.assertEqual(minute_bar.timestamp.hour, expected_dt.hour)
        self.assertEqual(minute_bar.timestamp.minute, expected_dt.minute)


@pytest.mark.asyncio
class TestMinuteDataFetchingAsync:
    """Test the asynchronous aspects of minute data fetching."""
    
    @pytest.fixture
    def setup(self):
        """Set up test fixtures."""
        config = Config(host="127.0.0.1", port=4002, client_id=1)
        
        # Create a mock gateway
        gateway = MagicMock(spec=IBGateway)
        gateway.config = config
        gateway.get_next_request_id.return_value = 123
        
        # Create a minute bar manager
        manager = MinuteBarManager(gateway)
        
        # Sample contract
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        
        return {
            "gateway": gateway,
            "manager": manager,
            "contract": contract
        }
    
    async def test_fetch_minute_bars_async(self, setup):
        """Test fetching minute bars asynchronously."""
        manager = setup["manager"]
        contract = setup["contract"]
        
        # Mock the async request method to return a future we control
        future = asyncio.Future()
        manager.request_historical_minute_data_async = MagicMock(return_value=future)
        
        # Start the fetch operation (it will wait on our future)
        fetch_task = asyncio.create_task(
            manager.fetch_minute_bars(
                contract=contract,
                duration="1 D",
                bar_size="1 min"
            )
        )
        
        # Create sample bars
        bar1 = MinuteBar(
            symbol="AAPL",
            timestamp=datetime(2023, 5, 1, 14, 30, 0, tzinfo=timezone.utc),
            open_price=150.0,
            high_price=151.0,
            low_price=149.5,
            close_price=150.5,
            volume=1000
        )
        
        bar2 = MinuteBar(
            symbol="AAPL",
            timestamp=datetime(2023, 5, 1, 14, 31, 0, tzinfo=timezone.utc),
            open_price=150.5,
            high_price=152.0,
            low_price=150.0,
            close_price=151.5,
            volume=1200
        )
        
        # Create a MinuteBarCollection with our sample bars
        bars = MinuteBarCollection(symbol="AAPL", bars=[bar1, bar2])
        
        # Resolve the future with our sample bars
        future.set_result(bars)
        
        # Now the fetch_task should complete with our bars
        result = await fetch_task
        
        # Assert the result is our bar collection
        assert result.symbol == "AAPL"
        assert len(result) == 2
        assert result[0].timestamp == bar1.timestamp
        assert result[1].timestamp == bar2.timestamp
    
    async def test_minute_bars_error_handling(self, setup):
        """Test error handling in minute bars fetching."""
        manager = setup["manager"]
        contract = setup["contract"]
        
        # Mock the async request method to return a future we control
        future = asyncio.Future()
        manager.request_historical_minute_data_async = MagicMock(return_value=future)
        
        # Start the fetch operation (it will wait on our future)
        fetch_task = asyncio.create_task(
            manager.fetch_minute_bars(
                contract=contract,
                duration="1 D",
                bar_size="1 min"
            )
        )
        
        # Reject the future with an error
        test_error = RuntimeError("IB API error")
        future.set_exception(test_error)
        
        # The fetch task should propagate the error
        with pytest.raises(RuntimeError, match="IB API error"):
            await fetch_task


if __name__ == "__main__":
    unittest.main()