# Alpaca Broker Configuration

## Overview

The broker configuration system provides centralized configuration management for the Alpaca trading system. It handles API credentials, trading parameters, and system settings through environment variables.

## Configuration Structure

```
BrokerConfig
├── AlpacaConfig (API settings)
│   ├── API credentials
│   ├── Trading mode (paper/live)
│   └── Base URLs
└── TradingConfig (Trading parameters)
    ├── Position sizing
    ├── Risk management
    ├── Timing settings
    └── Order defaults
```

## Environment Variables

### Required Variables

```bash
# Alpaca API Credentials
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here
```

### Optional Variables

```bash
# Trading Mode
ALPACA_TRADING_MODE=paper  # Options: paper, live (default: paper)

# Trading Parameters
MAX_POSITION_SIZE=1000      # Maximum shares per position
MAX_DAILY_TRADES=100        # Maximum trades per day
RISK_PER_TRADE=0.02         # Risk percentage per trade (2%)

# Timing Parameters
MARKET_OPEN_BUFFER_MINUTES=5   # Minutes after market open to start
MARKET_CLOSE_BUFFER_MINUTES=10 # Minutes before market close to stop
DEFAULT_TIME_IN_FORCE=DAY      # Default order time in force
USE_EXTENDED_HOURS=false       # Enable extended hours trading
```

## Configuration Classes

### AlpacaConfig

Manages Alpaca-specific settings:

```python
@dataclass
class AlpacaConfig:
    api_key: str
    secret_key: str
    trading_mode: str = "paper"
    base_url: Optional[str] = None
    
    @property
    def is_paper_trading(self) -> bool:
        return self.trading_mode == "paper"
```

### TradingConfig

Manages trading parameters:

```python
@dataclass
class TradingConfig:
    max_position_size: int = 1000
    max_daily_trades: int = 100
    risk_per_trade: float = 0.02
    market_open_buffer_minutes: int = 5
    market_close_buffer_minutes: int = 10
    default_time_in_force: str = "DAY"
    use_extended_hours: bool = False
```

### BrokerConfig

Main configuration container:

```python
@dataclass
class BrokerConfig:
    alpaca: AlpacaConfig
    trading: TradingConfig
    
    @classmethod
    def from_env(cls) -> 'BrokerConfig':
        return cls(
            alpaca=AlpacaConfig.from_env(),
            trading=TradingConfig.from_env()
        )
```

## Usage Examples

### Loading Configuration

```python
from src.config.broker_config import BrokerConfig

# Load from environment
config = BrokerConfig.from_env()

# Access Alpaca settings
api_key = config.alpaca.api_key
is_paper = config.alpaca.is_paper_trading

# Access trading parameters
max_position = config.trading.max_position_size
risk_per_trade = config.trading.risk_per_trade
```

### Creating Connection

```python
from src.alpaca_connection import AlpacaConnection

# Create connection with config
config = BrokerConfig.from_env()
connection = AlpacaConnection(config.alpaca)

# Connect
await connection.connect()
```

### Validation

```python
config = BrokerConfig.from_env()

# Validate configuration
if config.validate():
    print("Configuration is valid")
else:
    print("Configuration validation failed")
```

## Configuration Validation

The system validates:

1. **API Credentials**
   - Both API key and secret key must be present
   - Non-empty strings required

2. **Trading Parameters**
   - Position size must be positive
   - Risk per trade must be between 0 and 1
   - Valid time in force values

3. **Timing Parameters**
   - Buffer minutes must be non-negative
   - Valid market hours settings

## Best Practices

1. **Security**
   - Never commit API credentials to version control
   - Use environment variables or secure vaults
   - Rotate API keys regularly

2. **Paper Trading**
   - Always test with paper trading first
   - Use separate API keys for paper/live
   - Verify configuration before live trading

3. **Risk Management**
   - Set conservative position sizes
   - Implement daily trade limits
   - Use appropriate risk percentages

4. **Environment Setup**
   - Use `.env` files for local development
   - Use secure environment variables in production
   - Document all configuration options

## Example .env File

```bash
# Alpaca API Configuration
ALPACA_API_KEY=PK...
ALPACA_SECRET_KEY=39...
ALPACA_TRADING_MODE=paper

# Trading Configuration
MAX_POSITION_SIZE=500
MAX_DAILY_TRADES=50
RISK_PER_TRADE=0.01

# Timing Configuration
MARKET_OPEN_BUFFER_MINUTES=10
MARKET_CLOSE_BUFFER_MINUTES=15
DEFAULT_TIME_IN_FORCE=DAY
USE_EXTENDED_HOURS=false

# Logging
LOG_LEVEL=INFO
LOG_FILE=trading.log
```

## Troubleshooting

### Common Issues

1. **Missing API Credentials**
   ```
   ValueError: ALPACA_API_KEY and ALPACA_SECRET_KEY must be set
   ```
   - Ensure environment variables are set
   - Check .env file is loaded

2. **Invalid Trading Mode**
   ```
   ValueError: Trading mode must be 'paper' or 'live'
   ```
   - Verify ALPACA_TRADING_MODE value
   - Default is 'paper' if not set

3. **Validation Failures**
   - Check all numeric parameters are valid
   - Ensure risk parameters are within bounds
   - Verify time in force values

## Migration from IBKR

The configuration system has been simplified from the previous multi-broker setup:

- Removed `BROKER_TYPE` environment variable
- Removed IBKR/TWS configuration options
- Removed broker factory pattern
- Direct Alpaca configuration only

This simplification reduces complexity and focuses the system on Alpaca's capabilities. 