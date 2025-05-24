# TWS Setup Guide

This guide covers setting up Interactive Brokers Trader Workstation (TWS) for use with the TWS Trading Framework on Windows.

## TWS Configuration

### 1. Start TWS

1. **Launch TWS** on your Windows machine
2. **Login** with your Interactive Brokers credentials
3. **Switch to Paper Trading** (recommended for development)
   - Click on the account dropdown
   - Select "Switch to Simulated Trading" if not already in paper trading mode

### 2. Enable API Access

1. In TWS, go to **Global Configuration**
   - File → Global Configuration, or
   - Click the settings gear icon

2. Navigate to **API → Settings**

3. **Configure API Settings**:
   - ✅ Check "Enable ActiveX and Socket Clients"
   - ✅ Check "Allow connections from localhost only" (for security)
   - ✅ Set **Socket port** to `7497` (paper trading) or `7496` (live trading)
   - ✅ Optionally check "Read-Only API" if you only need market data (no trading)

4. **Click "OK"** to save settings

### 3. Test TWS Configuration

**⚠️ IMPORTANT: Do NOT use raw socket tests against TWS!**

Raw socket connections can corrupt TWS internal state and cause connection failures. Instead, use proper IBAPI connections for testing.

**Recommended Testing Approach:**

```python
# test_tws_proper.py
import asyncio
from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection

async def test_tws_connection():
    """Test TWS using proper IBAPI connection."""
    config = TWSConfig(
        host="127.0.0.1",
        port=7497,  # Paper trading port
        client_id=999,  # Unique test client ID
        connection_timeout=5.0
    )
    
    connection = TWSConnection(config)
    
    try:
        print("Testing TWS connection...")
        success = await connection.connect()
        
        if success:
            print("✅ TWS API connection successful!")
            # Test basic functionality
            connection.request_current_time()
            await asyncio.sleep(1)
            return True
        else:
            print("❌ TWS API connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Error testing connection: {e}")
        return False
    finally:
        # Clean disconnect using our fixed disconnect method
        if connection.is_connected():
            connection.disconnect()
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(test_tws_connection())
```

Run the test:
```bash
python test_tws_proper.py
```

## Connection Architecture

### Threading Safety Improvements

The framework includes important threading safety improvements:

1. **Safe Disconnect Pattern**: The `TWSConnection.disconnect()` method uses a non-blocking pattern that prevents thread deadlocks and TWS state corruption.

2. **Daemon Thread Management**: Background threads are properly managed as daemon threads that clean up naturally without requiring explicit joins.

3. **Async-Safe Operations**: All connection operations are designed to work safely with asyncio event loops.

### Key Safety Features

- **No Raw Socket Tests**: Avoid using raw socket connections against TWS as they can corrupt internal state
- **Proper IBAPI Usage**: Always use the IBAPI framework for TWS communication
- **Clean Disconnects**: The disconnect method ensures TWS state remains clean for future connections
- **Connection Timeouts**: Configurable timeouts prevent hanging connections

## Environment Configuration

### 1. Set Environment Variables

Create a `.env` file or set environment variables:

```bash
# Windows Command Prompt
set TWS_HOST=127.0.0.1
set TWS_PORT=7497
set TWS_CLIENT_ID=10
set TWS_ACCOUNT=your_paper_account_id

# Windows PowerShell
$env:TWS_HOST="127.0.0.1"
$env:TWS_PORT="7497"
$env:TWS_CLIENT_ID="10"
$env:TWS_ACCOUNT="your_paper_account_id"

# Linux/Mac/WSL
export TWS_HOST=127.0.0.1
export TWS_PORT=7497
export TWS_CLIENT_ID=10
export TWS_ACCOUNT=your_paper_account_id
```

### 2. Test Framework Connection

```bash
# Test basic connectivity using pytest
python -m pytest tests/integration/test_tws_connection.py::TestTWSConnection::test_tws_connection_to_live_tws -v

# Test connection creation (no TWS required)
python -m pytest tests/integration/test_tws_connection.py::TestTWSConnection::test_tws_connection_creation -v
```

## Port Configuration

| Mode | Port | Usage |
|------|------|-------|
| **Paper Trading** | `7497` | Recommended for development and testing |
| **Live Trading** | `7496` | Production trading (use with extreme caution) |

## Troubleshooting

### Common Issues

#### 1. Connection Refused
**Problem**: `Connection refused` error when trying to connect

**Solutions**:
- Ensure TWS is running and logged in
- Verify API is enabled in TWS settings
- Check that the correct port is configured
- Restart TWS and try again
- **Do NOT use raw socket tests** - they can corrupt TWS state

#### 2. Connection Hangs or Times Out
**Problem**: Connection attempts hang or timeout

**Solutions**:
- Restart TWS to clear any corrupted state
- Use a different client ID
- Ensure no other applications are using the same client ID
- Check that TWS hasn't been corrupted by raw socket tests

#### 3. API Not Enabled
**Problem**: Connection times out or is rejected

**Solutions**:
- Go to TWS Global Configuration → API → Settings
- Ensure "Enable ActiveX and Socket Clients" is checked
- Verify socket port matches your configuration (7497 for paper trading)

#### 4. Client ID Conflicts
**Problem**: "Client ID already in use" error

**Solutions**:
- Use a different `TWS_CLIENT_ID` (try 11, 12, etc.)
- Disconnect other applications using the same client ID
- Wait a few minutes for TWS to release the client ID

### Diagnostic Commands

Check if TWS is listening on the correct port:

```bash
# Windows PowerShell
netstat -an | Select-String ":7497"

# Expected output (if TWS is running):
# TCP    127.0.0.1:7497        0.0.0.0:0              LISTENING
```

**⚠️ DO NOT use telnet or raw socket connections for testing:**
```bash
# ❌ AVOID - These can corrupt TWS state:
# telnet 127.0.0.1 7497
# Test-NetConnection -ComputerName 127.0.0.1 -Port 7497
```

**✅ Instead, use proper IBAPI testing as shown above.**

### Windows Firewall

If you encounter connection issues, ensure Windows Firewall allows TWS:

1. Open **Windows Defender Firewall**
2. Click **Allow an app or feature through Windows Defender Firewall**
3. Find **Trader Workstation** or click **Allow another app...**
4. Browse to your TWS installation and add it
5. Ensure both **Private** and **Public** are checked

## Safety Recommendations

### For Development:
- ✅ **Always use paper trading mode**
- ✅ **Use proper IBAPI connections for testing**
- ✅ **Test with pytest integration tests**
- ✅ **Monitor all trading activity**
- ❌ **Never use raw socket tests against TWS**

### Account Settings:
- ✅ **Set up position limits in TWS**
- ✅ **Configure maximum order sizes**
- ✅ **Enable trading permissions carefully**
- ✅ **Use separate account for API trading**

### For Production:
- ⚠️ **Never run untested code against live accounts**
- ⚠️ **Implement comprehensive risk controls**
- ⚠️ **Have emergency stop procedures**
- ⚠️ **Monitor system health continuously**

## Next Steps

After successful TWS setup:

1. **Run basic tests**: `python -m pytest tests/integration/test_tws_connection.py -v`
2. **Test specific functionality**: Review available tests in `tests/integration/`
3. **Review trading framework documentation**
4. **Start with simple examples**
5. **Gradually add complexity**

Remember: Always start with paper trading and thoroughly test your system before considering live trading. 