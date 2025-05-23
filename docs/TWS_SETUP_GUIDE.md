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

### 3. Test API Configuration

Create a simple test to verify TWS is properly configured:

```python
# test_tws_setup.py
import socket

def test_tws_connection():
    """Test if TWS API is accessible."""
    host = "127.0.0.1"
    port = 7497  # Paper trading port
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print("✅ TWS API is accessible!")
            return True
        else:
            print("❌ Cannot connect to TWS API")
            return False
    except Exception as e:
        print(f"❌ Error testing connection: {e}")
        return False

if __name__ == "__main__":
    test_tws_connection()
```

Run the test:
```bash
python test_tws_setup.py
```

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
# Test basic connectivity
python run_integration_tests.py basic

# Test market data (safe)
python run_integration_tests.py market_data
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

#### 2. API Not Enabled
**Problem**: Connection times out or is rejected

**Solutions**:
- Go to TWS Global Configuration → API → Settings
- Ensure "Enable ActiveX and Socket Clients" is checked
- Verify socket port matches your configuration (7497 for paper trading)

#### 3. Wrong Port
**Problem**: Using wrong port number

**Solutions**:
- Paper trading: Use port `7497`
- Live trading: Use port `7496`
- Check TWS API settings to confirm port number

#### 4. Client ID Conflicts
**Problem**: "Client ID already in use" error

**Solutions**:
- Use a different `TWS_CLIENT_ID` (try 11, 12, etc.)
- Disconnect other applications using the same client ID
- Wait a few minutes for TWS to release the client ID

### Diagnostic Commands

Check if TWS is listening on the correct port:

```bash
# Windows Command Prompt
netstat -an | findstr :7497

# Windows PowerShell
netstat -an | Select-String ":7497"

# Expected output (if TWS is running):
# TCP    127.0.0.1:7497        0.0.0.0:0              LISTENING
```

Test socket connection:
```bash
# Using telnet (if available)
telnet 127.0.0.1 7497

# Using PowerShell
Test-NetConnection -ComputerName 127.0.0.1 -Port 7497
```

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
- ✅ **Test with small amounts**
- ✅ **Run integration tests first**
- ✅ **Monitor all trading activity**

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

1. **Run basic tests**: `python run_integration_tests.py basic`
2. **Test market data**: `python run_integration_tests.py market_data`
3. **Review trading framework documentation**
4. **Start with simple examples**
5. **Gradually add complexity**

Remember: Always start with paper trading and thoroughly test your system before considering live trading. 