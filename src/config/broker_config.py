#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Alpaca Broker Configuration

Configuration management for Alpaca Markets integration.
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class TradingConfig:
    """Common trading configuration parameters."""
    
    # Trading parameters
    max_position_size: int = 1000
    max_daily_trades: int = 100
    risk_per_trade: float = 0.02
    default_position_size: int = 12000  # Default allocation per trade
    
    # Timing parameters
    market_open_buffer_minutes: int = 5
    market_close_buffer_minutes: int = 10
    
    # Order defaults
    default_time_in_force: str = "DAY"
    use_extended_hours: bool = False
    
    @classmethod
    def from_env(cls) -> 'TradingConfig':
        """Create TradingConfig from environment variables."""
        return cls(
            max_position_size=int(os.getenv('MAX_POSITION_SIZE', '1000')),
            max_daily_trades=int(os.getenv('MAX_DAILY_TRADES', '100')),
            risk_per_trade=float(os.getenv('RISK_PER_TRADE', '0.02')),
            default_position_size=int(os.getenv('DEFAULT_POSITION_SIZE', '12000')),
            market_open_buffer_minutes=int(os.getenv('MARKET_OPEN_BUFFER_MINUTES', '5')),
            market_close_buffer_minutes=int(os.getenv('MARKET_CLOSE_BUFFER_MINUTES', '10')),
            default_time_in_force=os.getenv('DEFAULT_TIME_IN_FORCE', 'DAY'),
            use_extended_hours=os.getenv('USE_EXTENDED_HOURS', 'false').lower() == 'true'
        )


@dataclass
class AlpacaConfig:
    """Alpaca-specific configuration."""
    
    # API credentials
    api_key: str
    secret_key: str
    
    # Trading mode
    trading_mode: str = "paper"  # "paper" or "live"
    
    # API endpoints (automatically set based on trading mode)
    base_url: Optional[str] = None
    
    def __post_init__(self):
        """Set base URL based on trading mode."""
        if self.trading_mode == "paper":
            self.base_url = "https://paper-api.alpaca.markets"
        else:
            self.base_url = "https://api.alpaca.markets"
    
    @property
    def is_paper_trading(self) -> bool:
        """Check if using paper trading."""
        return self.trading_mode == "paper"
    
    @classmethod
    def from_env(cls) -> 'AlpacaConfig':
        """Create AlpacaConfig from environment variables."""
        api_key = os.getenv('ALPACA_API_KEY')
        secret_key = os.getenv('ALPACA_SECRET_KEY')
        
        if not api_key or not secret_key:
            raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set")
        
        return cls(
            api_key=api_key,
            secret_key=secret_key,
            trading_mode=os.getenv('ALPACA_TRADING_MODE', 'paper')
        )


@dataclass
class BrokerConfig:
    """Main broker configuration."""
    
    # Alpaca configuration
    alpaca: AlpacaConfig
    
    # Common trading configuration
    trading: TradingConfig
    
    @classmethod
    def from_env(cls) -> 'BrokerConfig':
        """Create BrokerConfig from environment variables."""
        return cls(
            alpaca=AlpacaConfig.from_env(),
            trading=TradingConfig.from_env()
        )
    
    def validate(self) -> bool:
        """
        Validate the configuration.
        
        Returns:
            bool: True if configuration is valid
        """
        # Check Alpaca credentials
        if not self.alpaca.api_key or not self.alpaca.secret_key:
            return False
        
        # Validate trading parameters
        if self.trading.max_position_size <= 0:
            return False
        
        if self.trading.risk_per_trade <= 0 or self.trading.risk_per_trade > 1:
            return False
        
        return True 