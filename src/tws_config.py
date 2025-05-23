#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TWS Configuration Management

Configuration class for TWS connections and behavior settings.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class TWSConfig:
    """
    Configuration class for TWS connection and behavior settings.
    """
    # Connection settings
    host: str = "127.0.0.1"
    port: int = 7497  # Default to TWS paper trading
    client_id: int = 1
    
    # Account settings
    account_id: str = ""
    
    # Timeouts and behavior
    connection_timeout: float = 10.0  # Seconds to wait for initial connection
    request_timeout: float = 30.0     # Seconds to wait for request responses
    
    # Trading mode
    trading_mode: str = "paper"  # 'paper' or 'live'
    
    @classmethod
    def from_env(cls) -> 'TWSConfig':
        """
        Create configuration from environment variables.
        
        Returns:
            TWSConfig: Configuration loaded from environment
        """
        return cls(
            host=os.environ.get("TWS_HOST", "127.0.0.1"),
            port=int(os.environ.get("TWS_PORT", "7497")),
            client_id=int(os.environ.get("TWS_CLIENT_ID", "1")),
            account_id=os.environ.get("TWS_ACCOUNT", ""),
            trading_mode=os.environ.get("TWS_TRADING_MODE", "paper"),
        )
    
    def validate(self) -> bool:
        """
        Validate configuration settings.
        
        Returns:
            bool: True if configuration is valid
        """
        if not isinstance(self.host, str) or not self.host:
            return False
            
        if not isinstance(self.port, int) or self.port <= 0:
            return False
            
        if not isinstance(self.client_id, int) or self.client_id < 0:
            return False
            
        if self.trading_mode not in ["paper", "live"]:
            return False
            
        return True
    
    def __str__(self) -> str:
        """String representation of the configuration."""
        return (
            f"TWSConfig(host={self.host}, port={self.port}, "
            f"client_id={self.client_id}, trading_mode={self.trading_mode})"
        ) 