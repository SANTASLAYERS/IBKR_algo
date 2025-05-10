#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Data models for minute bar data.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Union, Any
import json
import bisect

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


class MinuteBar:
    """
    Represents a single minute bar with OHLCV data.
    """
    
    def __init__(
        self, 
        symbol: str,
        timestamp: datetime,
        open_price: float,
        high_price: float,
        low_price: float,
        close_price: float,
        volume: int,
        count: Optional[int] = None,
        wap: Optional[float] = None
    ):
        """
        Initialize a minute bar.
        
        Args:
            symbol: The ticker symbol
            timestamp: Bar timestamp (should be timezone-aware)
            open_price: Opening price
            high_price: Highest price
            low_price: Lowest price
            close_price: Closing price
            volume: Trading volume
            count: Number of trades (optional)
            wap: Weighted average price (optional)
        
        Raises:
            ValueError: If high_price < low_price or volume < 0
        """
        if high_price < low_price:
            raise ValueError("High price must be greater than or equal to low price")
        
        if volume < 0:
            raise ValueError("Volume cannot be negative")
        
        self.symbol = symbol
        self.timestamp = timestamp
        self.open_price = open_price
        self.high_price = high_price
        self.low_price = low_price
        self.close_price = close_price
        self.volume = volume
        self.count = count
        self.wap = wap
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the minute bar to a dictionary.
        
        Returns:
            Dictionary representation of the minute bar
        """
        result = {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "open": self.open_price,
            "high": self.high_price,
            "low": self.low_price,
            "close": self.close_price,
            "volume": self.volume
        }
        
        if self.count is not None:
            result["count"] = self.count
            
        if self.wap is not None:
            result["wap"] = self.wap
            
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MinuteBar':
        """
        Create a MinuteBar from a dictionary.
        
        Args:
            data: Dictionary representation of a minute bar
            
        Returns:
            MinuteBar instance
        """
        # Parse the timestamp
        if isinstance(data["timestamp"], str):
            timestamp = datetime.fromisoformat(data["timestamp"])
        else:
            timestamp = data["timestamp"]
        
        # Create the minute bar
        return cls(
            symbol=data["symbol"],
            timestamp=timestamp,
            open_price=data["open"],
            high_price=data["high"],
            low_price=data["low"],
            close_price=data["close"],
            volume=data["volume"],
            count=data.get("count"),
            wap=data.get("wap")
        )
    
    def __eq__(self, other):
        """Check if two minute bars are equal."""
        if not isinstance(other, MinuteBar):
            return False
            
        return (
            self.symbol == other.symbol and
            self.timestamp == other.timestamp and
            self.open_price == other.open_price and
            self.high_price == other.high_price and
            self.low_price == other.low_price and
            self.close_price == other.close_price and
            self.volume == other.volume and
            self.count == other.count and
            self.wap == other.wap
        )


class MinuteBarCollection:
    """
    Collection of minute bars for a specific symbol.
    """
    
    def __init__(self, symbol: str, bars: Optional[List[MinuteBar]] = None):
        """
        Initialize a collection of minute bars.
        
        Args:
            symbol: Ticker symbol
            bars: Optional list of minute bars to add
        """
        self.symbol = symbol
        self._bars: List[MinuteBar] = []
        
        if bars:
            for bar in bars:
                self.add_bar(bar)
    
    def add_bar(self, bar: MinuteBar) -> None:
        """
        Add a minute bar to the collection.
        
        Args:
            bar: MinuteBar to add
            
        Raises:
            ValueError: If the bar's symbol doesn't match the collection's symbol
        """
        if bar.symbol != self.symbol:
            raise ValueError(
                f"Bar symbol {bar.symbol} doesn't match collection symbol {self.symbol}"
            )
        
        # Insert the bar in the correct timestamp position
        index = bisect.bisect_left(
            [b.timestamp for b in self._bars], 
            bar.timestamp
        )
        
        # Check if the bar already exists at this timestamp
        if (index < len(self._bars) and 
            self._bars[index].timestamp == bar.timestamp):
            # Replace the existing bar
            self._bars[index] = bar
        else:
            # Insert the new bar
            self._bars.insert(index, bar)
    
    def __len__(self) -> int:
        """Get the number of bars in the collection."""
        return len(self._bars)
    
    def __getitem__(self, index: int) -> MinuteBar:
        """Get a bar by index."""
        return self._bars[index]
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the collection to a dictionary.
        
        Returns:
            Dictionary representation of the collection
        """
        return {
            "symbol": self.symbol,
            "bars": [bar.to_dict() for bar in self._bars]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MinuteBarCollection':
        """
        Create a MinuteBarCollection from a dictionary.
        
        Args:
            data: Dictionary representation of a minute bar collection
            
        Returns:
            MinuteBarCollection instance
        """
        collection = cls(symbol=data["symbol"])
        
        for bar_data in data["bars"]:
            bar = MinuteBar.from_dict(bar_data)
            collection.add_bar(bar)
            
        return collection
    
    def to_dataframe(self):
        """
        Convert the collection to a pandas DataFrame.
        
        Returns:
            pandas.DataFrame representation of the collection
            
        Raises:
            ImportError: If pandas is not available
        """
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas is required for DataFrame conversion")
        
        # Extract data for DataFrame
        data = {
            "timestamp": [bar.timestamp for bar in self._bars],
            "open": [bar.open_price for bar in self._bars],
            "high": [bar.high_price for bar in self._bars],
            "low": [bar.low_price for bar in self._bars],
            "close": [bar.close_price for bar in self._bars],
            "volume": [bar.volume for bar in self._bars]
        }
        
        # Add optional fields if they're present in all bars
        if all(bar.count is not None for bar in self._bars):
            data["count"] = [bar.count for bar in self._bars]
            
        if all(bar.wap is not None for bar in self._bars):
            data["wap"] = [bar.wap for bar in self._bars]
        
        # Create and return the DataFrame
        df = pd.DataFrame(data)
        df.set_index("timestamp", inplace=True)
        return df
    
    def to_csv(self) -> str:
        """
        Convert the collection to CSV format.
        
        Returns:
            CSV string representation of the collection
        """
        if PANDAS_AVAILABLE:
            # Use pandas for CSV conversion if available
            return self.to_dataframe().reset_index().to_csv(index=False)
        else:
            # Fallback to manual CSV creation
            headers = ["timestamp", "open", "high", "low", "close", "volume"]
            optional_headers = []
            
            if all(bar.count is not None for bar in self._bars):
                optional_headers.append("count")
                
            if all(bar.wap is not None for bar in self._bars):
                optional_headers.append("wap")
                
            all_headers = headers + optional_headers
            
            # Create CSV header row
            csv = ",".join(all_headers) + "\n"
            
            # Add data rows
            for bar in self._bars:
                row = [
                    bar.timestamp.isoformat(),
                    str(bar.open_price),
                    str(bar.high_price),
                    str(bar.low_price),
                    str(bar.close_price),
                    str(bar.volume)
                ]
                
                if "count" in optional_headers:
                    row.append(str(bar.count))
                    
                if "wap" in optional_headers:
                    row.append(str(bar.wap))
                
                csv += ",".join(row) + "\n"
                
            return csv
    
    def to_json(self) -> str:
        """
        Convert the collection to JSON format.
        
        Returns:
            JSON string representation of the collection
        """
        return json.dumps(self.to_dict(), indent=2)