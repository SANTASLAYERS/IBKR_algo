#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from datetime import datetime, timezone
import pytest

from src.minute_data.models import MinuteBar, MinuteBarCollection


class TestMinuteBarModel(unittest.TestCase):
    """Test the MinuteBar data model class."""

    def test_minute_bar_initialization(self):
        """Test MinuteBar can be initialized with proper values."""
        timestamp = datetime.now(timezone.utc)
        bar = MinuteBar(
            symbol="AAPL",
            timestamp=timestamp,
            open_price=150.0,
            high_price=151.0,
            low_price=149.5,
            close_price=150.5,
            volume=1000,
            count=10,
            wap=150.25
        )
        
        self.assertEqual(bar.symbol, "AAPL")
        self.assertEqual(bar.timestamp, timestamp)
        self.assertEqual(bar.open_price, 150.0)
        self.assertEqual(bar.high_price, 151.0)
        self.assertEqual(bar.low_price, 149.5)
        self.assertEqual(bar.close_price, 150.5)
        self.assertEqual(bar.volume, 1000)
        self.assertEqual(bar.count, 10)
        self.assertEqual(bar.wap, 150.25)
    
    def test_minute_bar_validation(self):
        """Test MinuteBar validates input values."""
        timestamp = datetime.now(timezone.utc)
        
        # Invalid high < low
        with pytest.raises(ValueError):
            MinuteBar(
                symbol="AAPL",
                timestamp=timestamp,
                open_price=150.0,
                high_price=149.0,  # High less than low
                low_price=150.0,
                close_price=150.5,
                volume=1000
            )
        
        # Invalid negative volume
        with pytest.raises(ValueError):
            MinuteBar(
                symbol="AAPL",
                timestamp=timestamp,
                open_price=150.0,
                high_price=151.0,
                low_price=149.5,
                close_price=150.5,
                volume=-10  # Negative volume
            )
    
    def test_minute_bar_to_dict(self):
        """Test MinuteBar can be converted to dictionary."""
        timestamp = datetime(2023, 5, 1, 14, 30, 0, tzinfo=timezone.utc)
        bar = MinuteBar(
            symbol="AAPL",
            timestamp=timestamp,
            open_price=150.0,
            high_price=151.0,
            low_price=149.5,
            close_price=150.5,
            volume=1000
        )
        
        bar_dict = bar.to_dict()
        
        self.assertEqual(bar_dict["symbol"], "AAPL")
        self.assertEqual(bar_dict["timestamp"], timestamp.isoformat())
        self.assertEqual(bar_dict["open"], 150.0)
        self.assertEqual(bar_dict["high"], 151.0)
        self.assertEqual(bar_dict["low"], 149.5)
        self.assertEqual(bar_dict["close"], 150.5)
        self.assertEqual(bar_dict["volume"], 1000)
    
    def test_minute_bar_from_dict(self):
        """Test MinuteBar can be created from dictionary."""
        timestamp = datetime(2023, 5, 1, 14, 30, 0, tzinfo=timezone.utc)
        bar_dict = {
            "symbol": "AAPL",
            "timestamp": timestamp.isoformat(),
            "open": 150.0,
            "high": 151.0,
            "low": 149.5,
            "close": 150.5,
            "volume": 1000,
            "count": 10,
            "wap": 150.25
        }
        
        bar = MinuteBar.from_dict(bar_dict)
        
        self.assertEqual(bar.symbol, "AAPL")
        self.assertEqual(bar.timestamp.isoformat(), timestamp.isoformat())
        self.assertEqual(bar.open_price, 150.0)
        self.assertEqual(bar.high_price, 151.0)
        self.assertEqual(bar.low_price, 149.5)
        self.assertEqual(bar.close_price, 150.5)
        self.assertEqual(bar.volume, 1000)
        self.assertEqual(bar.count, 10)
        self.assertEqual(bar.wap, 150.25)


class TestMinuteBarCollection(unittest.TestCase):
    """Test the MinuteBarCollection class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.timestamp1 = datetime(2023, 5, 1, 14, 30, 0, tzinfo=timezone.utc)
        self.timestamp2 = datetime(2023, 5, 1, 14, 31, 0, tzinfo=timezone.utc)
        
        self.bar1 = MinuteBar(
            symbol="AAPL",
            timestamp=self.timestamp1,
            open_price=150.0,
            high_price=151.0,
            low_price=149.5,
            close_price=150.5,
            volume=1000
        )
        
        self.bar2 = MinuteBar(
            symbol="AAPL",
            timestamp=self.timestamp2,
            open_price=150.5,
            high_price=152.0,
            low_price=150.0,
            close_price=151.5,
            volume=1200
        )
    
    def test_collection_initialization(self):
        """Test MinuteBarCollection can be initialized with bars."""
        collection = MinuteBarCollection(symbol="AAPL", bars=[self.bar1, self.bar2])
        
        self.assertEqual(collection.symbol, "AAPL")
        self.assertEqual(len(collection), 2)
        self.assertEqual(collection[0], self.bar1)
        self.assertEqual(collection[1], self.bar2)
    
    def test_collection_add_bar(self):
        """Test adding bars to collection."""
        collection = MinuteBarCollection(symbol="AAPL")
        
        collection.add_bar(self.bar1)
        self.assertEqual(len(collection), 1)
        
        collection.add_bar(self.bar2)
        self.assertEqual(len(collection), 2)
    
    def test_collection_symbol_validation(self):
        """Test collection validates all bars have same symbol."""
        different_symbol_bar = MinuteBar(
            symbol="MSFT",  # Different symbol
            timestamp=self.timestamp1,
            open_price=250.0,
            high_price=251.0,
            low_price=249.5,
            close_price=250.5,
            volume=500
        )
        
        # Should raise ValueError when adding bar with different symbol
        collection = MinuteBarCollection(symbol="AAPL", bars=[self.bar1])
        with pytest.raises(ValueError):
            collection.add_bar(different_symbol_bar)
    
    def test_collection_timestamp_order(self):
        """Test collection maintains bars in timestamp order."""
        # Add in reverse order
        collection = MinuteBarCollection(symbol="AAPL")
        collection.add_bar(self.bar2)  # Later timestamp
        collection.add_bar(self.bar1)  # Earlier timestamp
        
        # Should be sorted by timestamp
        self.assertEqual(collection[0], self.bar1)
        self.assertEqual(collection[1], self.bar2)
    
    def test_collection_to_dataframe(self):
        """Test collection can be converted to pandas DataFrame."""
        collection = MinuteBarCollection(symbol="AAPL", bars=[self.bar1, self.bar2])
        
        df = collection.to_dataframe()
        
        # Assert DataFrame has correct structure
        self.assertEqual(len(df), 2)
        self.assertTrue("timestamp" in df.columns)
        self.assertTrue("open" in df.columns)
        self.assertTrue("high" in df.columns)
        self.assertTrue("low" in df.columns)
        self.assertTrue("close" in df.columns)
        self.assertTrue("volume" in df.columns)
    
    def test_collection_to_dict(self):
        """Test collection can be converted to dictionary."""
        collection = MinuteBarCollection(symbol="AAPL", bars=[self.bar1, self.bar2])
        
        collection_dict = collection.to_dict()
        
        self.assertEqual(collection_dict["symbol"], "AAPL")
        self.assertEqual(len(collection_dict["bars"]), 2)
        self.assertEqual(collection_dict["bars"][0]["timestamp"], self.timestamp1.isoformat())
        self.assertEqual(collection_dict["bars"][1]["timestamp"], self.timestamp2.isoformat())
    
    def test_collection_from_dict(self):
        """Test collection can be created from dictionary."""
        collection_dict = {
            "symbol": "AAPL",
            "bars": [
                {
                    "symbol": "AAPL",
                    "timestamp": self.timestamp1.isoformat(),
                    "open": 150.0,
                    "high": 151.0,
                    "low": 149.5,
                    "close": 150.5,
                    "volume": 1000
                },
                {
                    "symbol": "AAPL",
                    "timestamp": self.timestamp2.isoformat(),
                    "open": 150.5,
                    "high": 152.0,
                    "low": 150.0,
                    "close": 151.5,
                    "volume": 1200
                }
            ]
        }
        
        collection = MinuteBarCollection.from_dict(collection_dict)
        
        self.assertEqual(collection.symbol, "AAPL")
        self.assertEqual(len(collection), 2)
        self.assertEqual(collection[0].timestamp.isoformat(), self.timestamp1.isoformat())
        self.assertEqual(collection[1].timestamp.isoformat(), self.timestamp2.isoformat())


if __name__ == "__main__":
    unittest.main()