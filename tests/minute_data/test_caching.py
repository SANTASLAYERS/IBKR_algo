#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from unittest.mock import MagicMock, patch, mock_open
import json
import os
from datetime import datetime, timezone, timedelta
import tempfile
import shutil

from ibapi.contract import Contract

from src.gateway import IBGateway
from src.config import Config
from src.minute_data.models import MinuteBar, MinuteBarCollection
from src.minute_data.cache import MinuteDataCache


class TestMinuteDataCache(unittest.TestCase):
    """Test the minute data caching functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for cache files
        self.temp_dir = tempfile.mkdtemp()
        
        # Create the cache with our temp directory
        self.cache = MinuteDataCache(cache_dir=self.temp_dir)
        
        # Sample data for testing
        self.symbol = "AAPL"
        
        # Create sample minute bars
        self.timestamp1 = datetime(2023, 5, 1, 14, 30, 0, tzinfo=timezone.utc)
        self.timestamp2 = datetime(2023, 5, 1, 14, 31, 0, tzinfo=timezone.utc)
        
        self.bar1 = MinuteBar(
            symbol=self.symbol,
            timestamp=self.timestamp1,
            open_price=150.0,
            high_price=151.0,
            low_price=149.5,
            close_price=150.5,
            volume=1000
        )
        
        self.bar2 = MinuteBar(
            symbol=self.symbol,
            timestamp=self.timestamp2,
            open_price=150.5,
            high_price=152.0,
            low_price=150.0,
            close_price=151.5,
            volume=1200
        )
        
        # Create a collection with our bars
        self.collection = MinuteBarCollection(
            symbol=self.symbol, 
            bars=[self.bar1, self.bar2]
        )
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir)
    
    def test_cache_key_generation(self):
        """Test generation of cache keys."""
        # Create a contract
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        
        # Parameters for key generation
        end_date = datetime(2023, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
        duration = "1 D"
        bar_size = "1 min"
        
        # Generate key
        key = self.cache.generate_cache_key(
            contract, end_date, duration, bar_size
        )
        
        # Assert the key format is as expected
        self.assertIn("AAPL", key)
        self.assertIn("STK", key)
        self.assertIn("USD", key)
        self.assertIn("1_D", key)
        self.assertIn("1_min", key)
        self.assertIn("20230501", key)
    
    def test_store_and_retrieve_from_cache(self):
        """Test storing and retrieving data from cache."""
        # Create a key for the test data
        key = "AAPL_STK_SMART_USD_1_D_1_min_20230501"
        
        # Store the data
        self.cache.store(key, self.collection)
        
        # Check the file exists
        cache_file = os.path.join(self.temp_dir, f"{key}.json")
        self.assertTrue(os.path.exists(cache_file))
        
        # Retrieve the data
        retrieved = self.cache.retrieve(key)
        
        # Assert it's a MinuteBarCollection with the right data
        self.assertIsInstance(retrieved, MinuteBarCollection)
        self.assertEqual(retrieved.symbol, self.symbol)
        self.assertEqual(len(retrieved), 2)
        
        # Compare timestamps (converted to isoformat for string comparison)
        self.assertEqual(retrieved[0].timestamp.isoformat(), 
                        self.timestamp1.isoformat())
        self.assertEqual(retrieved[1].timestamp.isoformat(), 
                        self.timestamp2.isoformat())
    
    def test_cache_expiration(self):
        """Test cache expiration functionality."""
        # Create a key for the test data
        key = "AAPL_STK_SMART_USD_1_D_1_min_20230501"
        
        # Store the data with a 1-second expiration
        self.cache.store(key, self.collection, expiration_seconds=1)
        
        # Verify it's in the cache
        self.assertTrue(self.cache.exists(key))
        
        # Wait for expiration
        import time
        time.sleep(1.1)
        
        # Check it's expired
        self.assertFalse(self.cache.exists(key))
        
        # Trying to retrieve should return None
        self.assertIsNone(self.cache.retrieve(key))
    
    def test_cache_file_corruption(self):
        """Test handling of corrupted cache files."""
        # Create a key for the test data
        key = "AAPL_STK_SMART_USD_1_D_1_min_20230501"
        
        # Create a corrupted cache file
        cache_file = os.path.join(self.temp_dir, f"{key}.json")
        with open(cache_file, 'w') as f:
            f.write("This is not valid JSON")
        
        # Attempt to retrieve should return None and not raise exception
        result = self.cache.retrieve(key)
        self.assertIsNone(result)
    
    def test_clear_cache(self):
        """Test clearing the cache."""
        # Store multiple items
        keys = [
            "AAPL_STK_SMART_USD_1_D_1_min_20230501",
            "MSFT_STK_SMART_USD_1_D_1_min_20230501"
        ]
        
        for key in keys:
            self.cache.store(key, self.collection)
            
        # Verify they exist
        for key in keys:
            self.assertTrue(self.cache.exists(key))
        
        # Clear the cache
        self.cache.clear()
        
        # Verify they're gone
        for key in keys:
            self.assertFalse(self.cache.exists(key))
    
    def test_clear_expired(self):
        """Test clearing only expired cache entries."""
        # Store items with different expirations
        key1 = "AAPL_STK_SMART_USD_1_D_1_min_20230501"
        key2 = "MSFT_STK_SMART_USD_1_D_1_min_20230501"
        
        # One that expires quickly
        self.cache.store(key1, self.collection, expiration_seconds=1)
        
        # One that doesn't expire soon
        self.cache.store(key2, self.collection, expiration_seconds=3600)
        
        # Wait for the first to expire
        import time
        time.sleep(1.1)
        
        # Clear expired entries
        self.cache.clear_expired()
        
        # key1 should be gone, key2 should remain
        self.assertFalse(self.cache.exists(key1))
        self.assertTrue(self.cache.exists(key2))
    
    def test_cache_size_limit(self):
        """Test cache enforces size limits."""
        # Set a small cache size limit
        self.cache = MinuteDataCache(
            cache_dir=self.temp_dir,
            max_size_mb=0.001  # 1KB
        )
        
        # Store a large collection that exceeds the limit
        large_collection = MinuteBarCollection(symbol=self.symbol)
        for i in range(100):  # Create many bars to make a large collection
            large_collection.add_bar(MinuteBar(
                symbol=self.symbol,
                timestamp=self.timestamp1 + timedelta(minutes=i),
                open_price=150.0 + i,
                high_price=151.0 + i,
                low_price=149.5 + i,
                close_price=150.5 + i,
                volume=1000 + i
            ))
        
        key = "AAPL_STK_SMART_USD_1_D_1_min_20230501"
        
        # This should not raise an exception but should log a warning
        with self.assertLogs(level='WARNING'):
            self.cache.store(key, large_collection)
        
        # The cache should still work for smaller items
        small_key = "AAPL_small"
        small_collection = MinuteBarCollection(
            symbol=self.symbol,
            bars=[self.bar1]
        )
        
        self.cache.store(small_key, small_collection)
        self.assertTrue(self.cache.exists(small_key))


if __name__ == "__main__":
    unittest.main()