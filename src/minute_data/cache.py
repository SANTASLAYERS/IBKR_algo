#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Caching mechanism for minute bar data.
"""

import os
import json
import time
import shutil
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Any, Union

from ibapi.contract import Contract

from .models import MinuteBarCollection


logger = logging.getLogger(__name__)


class MinuteDataCache:
    """
    Cache for storing and retrieving minute bar data.
    """
    
    def __init__(self, cache_dir: str = None, max_size_mb: float = 100.0):
        """
        Initialize the minute data cache.
        
        Args:
            cache_dir: Directory to store cache files (defaults to ~/.ibkr_minute_cache)
            max_size_mb: Maximum cache size in megabytes
        """
        if cache_dir is None:
            home_dir = os.path.expanduser("~")
            cache_dir = os.path.join(home_dir, ".ibkr_minute_cache")
            
        self.cache_dir = cache_dir
        self.max_size_bytes = max_size_mb * 1024 * 1024
        
        # Create cache directory if it doesn't exist
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
    
    def generate_cache_key(
        self,
        contract: Contract,
        end_date: datetime,
        duration: str,
        bar_size: str
    ) -> str:
        """
        Generate a unique cache key for the given parameters.
        
        Args:
            contract: Contract for the data
            end_date: End date for the data
            duration: Duration string (e.g., "1 D")
            bar_size: Bar size string (e.g., "1 min")
            
        Returns:
            Unique cache key as string
        """
        # Format the end date
        date_str = end_date.strftime("%Y%m%d")
        
        # Normalize duration and bar_size by replacing spaces with underscores
        duration_norm = duration.replace(" ", "_")
        bar_size_norm = bar_size.replace(" ", "_")
        
        # Generate key
        key = f"{contract.symbol}_{contract.secType}_{contract.exchange}_{contract.currency}"
        key += f"_{duration_norm}_{bar_size_norm}_{date_str}"
        
        return key
    
    def _get_cache_file_path(self, key: str) -> str:
        """
        Get the file path for a cache key.
        
        Args:
            key: Cache key
            
        Returns:
            Full path to the cache file
        """
        return os.path.join(self.cache_dir, f"{key}.json")
    
    def exists(self, key: str) -> bool:
        """
        Check if a key exists in the cache and is not expired.
        
        Args:
            key: Cache key
            
        Returns:
            True if the key exists and is not expired, False otherwise
        """
        file_path = self._get_cache_file_path(key)
        
        if not os.path.exists(file_path):
            return False
            
        # Check if the cache entry is expired
        try:
            with open(file_path, 'r') as f:
                metadata = json.loads(f.readline())
                
            if "expiration" in metadata and metadata["expiration"] < time.time():
                # The entry is expired
                return False
                
            return True
            
        except (json.JSONDecodeError, IOError):
            # If there's an error reading the file, consider it doesn't exist
            return False
    
    def store(
        self, 
        key: str, 
        data: MinuteBarCollection,
        expiration_seconds: Optional[int] = None
    ) -> bool:
        """
        Store data in the cache.
        
        Args:
            key: Cache key
            data: MinuteBarCollection to store
            expiration_seconds: Optional expiration time in seconds
            
        Returns:
            True if successful, False otherwise
        """
        file_path = self._get_cache_file_path(key)
        
        try:
            # Convert the collection to a dictionary
            data_dict = data.to_dict()
            
            # Add metadata
            metadata = {
                "timestamp": time.time(),
                "symbol": data.symbol,
                "count": len(data)
            }
            
            if expiration_seconds is not None:
                metadata["expiration"] = time.time() + expiration_seconds
            
            # Check cache size before writing
            estimated_size = len(json.dumps(metadata)) + len(json.dumps(data_dict))
            
            if estimated_size > self.max_size_bytes:
                logger.warning(
                    f"Cache entry too large ({estimated_size / 1024 / 1024:.2f} MB) "
                    f"for key {key}, max size is {self.max_size_bytes / 1024 / 1024:.2f} MB"
                )
                return False
            
            # Write the data to the cache file
            with open(file_path, 'w') as f:
                # Write metadata and data
                json.dump(metadata, f)
                f.write("\n")
                json.dump(data_dict, f, indent=2)
                
            return True
            
        except Exception as e:
            logger.error(f"Error storing data in cache: {str(e)}")
            return False
    
    def retrieve(self, key: str) -> Optional[MinuteBarCollection]:
        """
        Retrieve data from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            MinuteBarCollection if found and not expired, None otherwise
        """
        if not self.exists(key):
            return None
            
        file_path = self._get_cache_file_path(key)
        
        try:
            with open(file_path, 'r') as f:
                # Read metadata and data
                metadata = json.loads(f.readline())
                data_dict = json.loads(f.read())
            
            # Check expiration
            if "expiration" in metadata and metadata["expiration"] < time.time():
                # The entry is expired
                return None
            
            # Create and return the MinuteBarCollection
            return MinuteBarCollection.from_dict(data_dict)
            
        except Exception as e:
            logger.error(f"Error retrieving data from cache: {str(e)}")
            return None
    
    def clear(self) -> None:
        """Clear all cache entries."""
        for filename in os.listdir(self.cache_dir):
            file_path = os.path.join(self.cache_dir, filename)
            if os.path.isfile(file_path) and filename.endswith('.json'):
                try:
                    os.remove(file_path)
                except OSError as e:
                    logger.error(f"Error removing cache file {file_path}: {str(e)}")
    
    def clear_expired(self) -> int:
        """
        Clear expired cache entries.
        
        Returns:
            Number of entries cleared
        """
        count = 0
        current_time = time.time()
        
        for filename in os.listdir(self.cache_dir):
            if not filename.endswith('.json'):
                continue
                
            file_path = os.path.join(self.cache_dir, filename)
            
            try:
                with open(file_path, 'r') as f:
                    metadata = json.loads(f.readline())
                
                if "expiration" in metadata and metadata["expiration"] < current_time:
                    # The entry is expired
                    os.remove(file_path)
                    count += 1
                    
            except (json.JSONDecodeError, IOError, OSError) as e:
                logger.error(f"Error checking/removing cache file {file_path}: {str(e)}")
        
        return count
    
    def get_size(self) -> int:
        """
        Get the current size of the cache in bytes.
        
        Returns:
            Cache size in bytes
        """
        total_size = 0
        
        for dirpath, _, filenames in os.walk(self.cache_dir):
            for filename in filenames:
                if filename.endswith('.json'):
                    file_path = os.path.join(dirpath, filename)
                    total_size += os.path.getsize(file_path)
        
        return total_size
    
    def trim_to_max_size(self) -> int:
        """
        Trim the cache to the maximum size by removing oldest entries first.
        
        Returns:
            Number of entries removed
        """
        if self.get_size() <= self.max_size_bytes:
            return 0
            
        # Get all cache files with their timestamps
        files = []
        
        for filename in os.listdir(self.cache_dir):
            if not filename.endswith('.json'):
                continue
                
            file_path = os.path.join(self.cache_dir, filename)
            
            try:
                with open(file_path, 'r') as f:
                    metadata = json.loads(f.readline())
                    
                timestamp = metadata.get("timestamp", 0)
                files.append((file_path, timestamp))
                
            except (json.JSONDecodeError, IOError):
                # If we can't read the timestamp, assume it's very old
                files.append((file_path, 0))
        
        # Sort by timestamp (oldest first)
        files.sort(key=lambda x: x[1])
        
        # Remove files until we're under the size limit
        count = 0
        current_size = self.get_size()
        
        for file_path, _ in files:
            if current_size <= self.max_size_bytes:
                break
                
            try:
                file_size = os.path.getsize(file_path)
                os.remove(file_path)
                current_size -= file_size
                count += 1
                
            except OSError as e:
                logger.error(f"Error removing cache file {file_path}: {str(e)}")
        
        return count