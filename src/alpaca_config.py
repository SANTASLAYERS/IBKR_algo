#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Alpaca Configuration Management

Configuration class for Alpaca connections and behavior settings.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class AlpacaConfig:
    """
    Configuration class for Alpaca connection and behavior settings.
    """
    # API credentials
    api_key: str = ""
    secret_key: str = ""
    
    # Base URLs
    base_url: str = "https://paper-api.alpaca.markets"  # Default to paper trading
    data_url: str = "https://data.alpaca.markets"
    
    # Trading mode
    trading_mode: str = "paper"  # 'paper' or 'live'
    
    # Timeouts and behavior
    connection_timeout: float = 10.0  # Seconds to wait for initial connection
    request_timeout: float = 30.0     # Seconds to wait for request responses
    
    # Rate limiting
    max_requests_per_minute: int = 200  # Alpaca's rate limit
    
    @classmethod
    def from_env(cls) -> 'AlpacaConfig':
        """
        Create configuration from environment variables.
        
        Returns:
            AlpacaConfig: Configuration loaded from environment
        """
        trading_mode = os.environ.get("ALPACA_TRADING_MODE", "paper")
        
        # Set base URL based on trading mode
        if trading_mode == "live":
            base_url = "https://api.alpaca.markets"
        else:
            base_url = "https://paper-api.alpaca.markets"
        
        return cls(
            api_key=os.environ.get("ALPACA_API_KEY", ""),
            secret_key=os.environ.get("ALPACA_SECRET_KEY", ""),
            base_url=os.environ.get("ALPACA_BASE_URL", base_url),
            data_url=os.environ.get("ALPACA_DATA_URL", "https://data.alpaca.markets"),
            trading_mode=trading_mode,
        )
    
    @property
    def is_paper_trading(self) -> bool:
        """Check if configured for paper trading."""
        return self.trading_mode == "paper" or "paper" in self.base_url
    
    def validate(self) -> bool:
        """
        Validate configuration settings.
        
        Returns:
            bool: True if configuration is valid
        """
        if not self.api_key or not isinstance(self.api_key, str):
            return False
            
        if not self.secret_key or not isinstance(self.secret_key, str):
            return False
            
        if not self.base_url or not isinstance(self.base_url, str):
            return False
            
        if self.trading_mode not in ["paper", "live"]:
            return False
            
        return True
    
    def __str__(self) -> str:
        """String representation of the configuration."""
        # Don't expose secret key in string representation
        masked_key = f"{self.api_key[:4]}...{self.api_key[-4:]}" if len(self.api_key) > 8 else "***"
        return (
            f"AlpacaConfig(api_key={masked_key}, "
            f"base_url={self.base_url}, trading_mode={self.trading_mode})"
        ) 