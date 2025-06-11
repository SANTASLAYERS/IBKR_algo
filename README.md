# Multi-Ticker IB Trading Framework

A sophisticated automated trading system for Interactive Brokers (IB) that integrates with external prediction APIs to execute trades based on market signals. The framework supports multiple tickers, complex order management, and real-time position tracking.

## 🚀 Key Features

- **Multi-Ticker Support**: Trade multiple symbols simultaneously with isolated position management
- **API Integration**: Seamless integration with prediction signal APIs (BUY/SELL/SHORT signals)
- **Advanced Order Management**: 
  - Automatic stop-loss and take-profit orders
  - Scale-in capabilities with profit triggers
  - ATR-based dynamic stop placement
  - Double-down order support
- **Position Management**: Real-time tracking with P&L monitoring
- **Event-Driven Architecture**: Responsive, decoupled system design
- **Rule Engine**: Flexible condition-action framework for trading strategies
- **Risk Management**: Built-in position sizing and exposure controls

## 📋 Prerequisites

- Python 3.8 or higher
- Interactive Brokers TWS or IB Gateway
- IB API enabled in TWS/Gateway
- Valid IB account with appropriate permissions

## 🛠️ Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ib-trading-framework.git
cd ib-trading-framework
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
# TWS Connection
TWS_HOST=127.0.0.1
TWS_PORT=7497  # 7496 for live trading
TWS_CLIENT_ID=1

# API Configuration
API_KEY=your_api_key_here
API_ENDPOINT=https://api.example.com/predictions

# Trading Parameters
DEFAULT_POSITION_SIZE=10000
MAX_POSITION_SIZE=50000
STOP_LOSS_PCT=0.03
TAKE_PROFIT_PCT=0.08

# Risk Management
MAX_DAILY_LOSS=1000
MAX_POSITIONS=10
```

### Trading Rules Configuration

Edit `config/trading_rules.yaml`:

```yaml
rules:
  - name: "High Confidence Buy"
    condition:
      type: "signal"
      signal: "BUY"
      min_confidence: 0.80
    action:
      type: "create_position"
      side: "BUY"
      stop_loss_pct: 0.03
      take_profit_pct: 0.08
      
  - name: "Scale In on Profit"
    condition:
      type: "position_profit"
      min_profit_pct: 0.02
    action:
      type: "scale_in"
      scale_pct: 0.50
```

## 🚀 Usage

### Starting the Trading System

```bash
python main.py
```

### Running in Test Mode

```bash
python main.py --test-mode
```

### Monitoring Positions

```bash
python scripts/monitor_positions.py
```

## 📊 Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  API Monitor    │────▶│  Rule Engine     │────▶│ Order Manager   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                       │                         │
         ▼                       ▼                         ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Event Bus     │     │ Position Tracker │     │ TWS Connection  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

### Core Components

1. **API Monitor**: Polls external API for trading signals
2. **Event Bus**: Central communication hub using publish-subscribe pattern
3. **Rule Engine**: Evaluates conditions and executes trading actions
4. **Position Tracker**: Maintains real-time position state and P&L
5. **Order Manager**: Handles order creation, submission, and lifecycle
6. **TWS Connection**: Manages connection to Interactive Brokers

## 📝 Trading Workflow

1. **Signal Reception**: API monitor receives prediction signals (BUY/SELL/SHORT)
2. **Event Emission**: Signals converted to events and published on event bus
3. **Rule Evaluation**: Rule engine evaluates conditions against current state
4. **Action Execution**: Matching rules trigger trading actions
5. **Order Creation**: Orders created with automatic stop/target placement
6. **Position Tracking**: Positions monitored and updated in real-time
7. **Risk Management**: Automatic position closure on stop/target hits

## 🔧 Advanced Features

### Linked Order Management

The system automatically manages related orders:

```python
# Entry order with automatic protective orders
action = LinkedCreateOrderAction(
    symbol="AAPL",
    quantity=100,
    side="BUY",
    auto_create_stops=True,
    stop_loss_pct=0.03,
    take_profit_pct=0.08
)
```

### ATR-Based Stops

Dynamic stop placement using Average True Range:

```python
action = LinkedCreateOrderAction(
    symbol="AAPL",
    quantity=100,
    side="BUY",
    auto_create_stops=True,
    atr_stop_multiplier=2.0,    # 2x ATR for stop
    atr_target_multiplier=4.0   # 4x ATR for target
)
```

### Position Reversal

Automatic handling of opposing signals:

- **Same Side Signal**: Ignored (prevents duplicate positions)
- **Opposite Side Signal**: Closes current position, opens new opposite position
- **Automatic Position Cleanup**: Clean state management for new trades

## 📊 Monitoring and Logging

### Log Files

- `logs/trading.log`: Main trading activity log
- `logs/orders.log`: Detailed order execution log
- `logs/positions.log`: Position tracking and P&L log
- `logs/errors.log`: Error and exception log

### Real-time Monitoring

```bash
# Watch trading activity
tail -f logs/trading.log

# Monitor positions
python scripts/position_dashboard.py

# Check system health
python scripts/health_check.py
```

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test module
pytest tests/test_order_management.py

# Run with coverage
pytest --cov=src tests/
```

### Integration Tests

```bash
# Test TWS connection
python tests/integration/test_tws_connection.py

# Test order execution (paper trading)
python tests/integration/test_order_execution.py
```

## 🚨 Risk Management

### Built-in Safeguards

- **Position Limits**: Maximum positions per symbol and total
- **Daily Loss Limits**: Automatic trading halt on max daily loss
- **Order Validation**: Pre-submission validation of all orders
- **Duplicate Prevention**: Prevents multiple positions on same symbol/side
- **Error Recovery**: Automatic reconnection and state recovery

### Best Practices

1. **Always test in paper trading** before live deployment
2. **Set conservative position sizes** initially
3. **Monitor logs actively** during initial deployment
4. **Use stop losses** on all positions
5. **Implement daily loss limits**
6. **Regular backup** of configuration and logs

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This software is for educational purposes only. Trading involves substantial risk of loss and is not suitable for all investors. Past performance is not indicative of future results. Always test thoroughly in a paper trading environment before using real money.

## 🆘 Support

- **Documentation**: See the `docs/` directory for detailed documentation
- **Issues**: Report bugs via GitHub Issues
- **Discussions**: Join our Discord server for community support

## 🔄 Recent Updates

- **v2.1.0**: Unified Fill Manager - Centralized handling of all fills with automatic protective order updates
- **v2.0.0**: Complete position management overhaul - PositionTracker as single source of truth
- **v1.9.0**: Added ATR-based dynamic stop placement
- **v1.8.0**: Implemented position reversal logic
- **v1.7.0**: Enhanced order linking system
- **v1.6.0**: Added double-down order support