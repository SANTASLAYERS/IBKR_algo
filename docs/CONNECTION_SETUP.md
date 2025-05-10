# Interactive Brokers Connection Setup Guide

This guide covers different methods to connect to Interactive Brokers from your development environment, with special focus on WSL2 and Docker configurations.

## Table of Contents
- [IB Gateway Configuration](#ib-gateway-configuration)
- [WSL2 Connection](#wsl2-connection)
- [Docker Setup](#docker-setup)
- [Troubleshooting](#troubleshooting)

## IB Gateway Configuration

To ensure your IB Gateway is properly configured for API access, follow these steps:

### API Settings Configuration

1. In IB Gateway, go to **Settings** > **API** > **Settings**

2. Ensure the following settings are configured:
   - **Enable ActiveX and Socket Clients**: Must be checked
   - **Socket port**: Set to 4002 for Paper Trading or 4001 for Live Trading
   - **Allow connections from localhost only**: Uncheck this to allow connections from other hosts, including WSL
   - **Read-Only API**: Only if you don't need to place orders
   - **Trusted IPs**: If configured, ensure your WSL IP range is included

### Testing Configuration on Windows

Create a simple Python script on your Windows host to verify IB Gateway is correctly configured:

```python
# Save as test_gateway.py on your Windows system
import asyncio
import sys
from pathlib import Path
import os

# Add the parent directory to the path so we can import from src
sys.path.append(str(Path(__file__).parent.parent))

from src.gateway import IBGateway, IBGatewayConfig
from src.error_handler import ErrorHandler

async def test_gateway():
    # Create configuration
    config = IBGatewayConfig(
        host="127.0.0.1",
        port=4002,
        client_id=1,
        trading_mode="paper",
        heartbeat_timeout=10.0,
        heartbeat_interval=5.0
    )

    # Create error handler
    error_handler = ErrorHandler()

    # Create gateway
    gateway = IBGateway(config, error_handler)

    try:
        # Connect to IB Gateway
        print(f"Connecting to IB Gateway on localhost...")
        connected = await gateway.connect_gateway()

        # Verify connection
        if connected and gateway.is_connected():
            print("✅ Successfully connected to IB Gateway!")

            # Get managed accounts
            accounts = gateway.get_managed_accounts()
            print(f"Managed accounts: {accounts}")

            return True
        else:
            print("❌ Failed to connect to IB Gateway")
            return False
    except Exception as e:
        print(f"❌ Error connecting to IB Gateway: {e}")
        return False
    finally:
        # Disconnect
        if gateway.is_connected():
            gateway.disconnect()
            print("Disconnected from IB Gateway")

if __name__ == "__main__":
    # Ensure we can connect locally first
    success = asyncio.run(test_gateway())
    sys.exit(0 if success else 1)
```

Run this script on your Windows host to verify API connectivity is working locally before attempting to connect from WSL.

### Firewall Configuration

Make sure Windows Firewall allows incoming connections to the IB Gateway port:

1. Open **Windows Defender Firewall with Advanced Security**
2. Click on **Inbound Rules** in the left panel
3. Click **New Rule...** in the right panel
4. Select **Port** and click Next
5. Select **TCP** and enter **4002** (or 4001 for Live Trading) in "Specific local ports"
6. Select **Allow the connection** and click Next
7. Apply the rule to all network profiles (Domain, Private, Public)
8. Name the rule "IB Gateway API" and click Finish

## WSL2 Connection

When running the IBKR connection code in WSL2 (Windows Subsystem for Linux 2) and trying to connect to IB Gateway running on the Windows host, you need to use the correct IP address.

### Finding the Right IP Address

In WSL2, there are different ways to reach the Windows host:

1. **Use the WSL2 Gateway IP** (most reliable):
   ```bash
   # Find your WSL gateway IP
   ip route | grep default
   # Example output: default via 172.28.64.1 dev eth0
   ```
   The IP after "default via" (e.g., 172.28.64.1) is your Windows host from WSL's perspective.

2. **Use the Windows Host LAN IP** (sometimes works):
   ```powershell
   # Run in Windows PowerShell
   ipconfig
   # Look for IPv4 Address under your main adapter
   ```

### Connection Code

Use the appropriate IP in your connection code:

```python
# In your Python code, use the WSL gateway IP
config = IBGatewayConfig(
    host="172.28.64.1",  # WSL gateway IP to reach Windows
    port=4002,           # Paper trading port (4001 for live)
    client_id=1
)
gateway = IBGateway(config, error_handler)
await gateway.connect_gateway()
```

### Testing the Connection

```bash
# Test TCP connectivity to the port
nc -zv 172.28.64.1 4002
# If successful, you should see "Connection to 172.28.64.1 4002 port [tcp/*] succeeded!"

# Run the connection test script
python3 test_gateway_connectivity.py --host 172.28.64.1 --port 4002
```

## Docker Setup

Rather than connecting to IB Gateway running on the Windows host, running IB Gateway in a Docker container within WSL2 can provide a simpler, self-contained solution.

### Prerequisites

1. Docker installed in your WSL2 environment
2. Interactive Brokers credentials (username and password)

### Setting Up IB Gateway Docker Container

There are several Docker images available for IB Gateway. One popular option is maintained by the community:

```bash
# Pull the latest image
docker pull ghcr.io/gnzsnz/ib-gateway:stable

# Run the container with your credentials
docker run -d \
  --name ib-gateway \
  -p 4002:4002 \
  -e TWS_USERID=your_username \
  -e TWS_PASSWORD=your_password \
  -e TRADING_MODE=paper \
  ghcr.io/gnzsnz/ib-gateway:stable
```

### Verifying the Container

Check if the container is running:

```bash
docker ps
```

View the logs to make sure it started correctly:

```bash
docker logs -f ib-gateway
```

### Connecting to the Dockerized IB Gateway

From your Python code in WSL2, you can now connect to the dockerized IB Gateway using localhost:

```python
# Connect to IB Gateway running in Docker
from src.gateway import IBGateway, IBGatewayConfig
from src.error_handler import ErrorHandler

# Create configuration for local Docker container
config = IBGatewayConfig(
    host="127.0.0.1",  # localhost works since both client and server are in WSL2
    port=4002,         # Paper trading port
    client_id=1
)

# Create error handler and gateway
error_handler = ErrorHandler()
gateway = IBGateway(config, error_handler)

# Connect to the gateway
await gateway.connect_gateway()
```

You can test the connection using our test script:

```bash
python test_gateway_connectivity.py --host 127.0.0.1 --port 4002
```

### Container Configuration Options

The Docker container supports various environment variables for configuration:

| Variable | Description | Default |
|----------|-------------|---------|
| `TWS_USERID` | IB account username | - |
| `TWS_PASSWORD` | IB account password | - |
| `TRADING_MODE` | Mode (paper/live) | `paper` |
| `VNC_SERVER_PASSWORD` | Password for VNC access | `password` |
| `READ_ONLY` | Read-only API access | `yes` |
| `ALIAS` | Account alias for subaccounts | - |

### Persisting Settings

To persist IB Gateway settings across container restarts, you can mount a volume:

```bash
docker run -d \
  --name ib-gateway \
  -p 4002:4002 \
  -v ib-gateway-settings:/home/ibgateway/ibgateway/jts \
  -e TWS_USERID=your_username \
  -e TWS_PASSWORD=your_password \
  ghcr.io/gnzsnz/ib-gateway:stable
```

### Accessing the IB Gateway UI (Optional)

The Docker container includes a VNC server that allows you to access the IB Gateway UI:

1. Install a VNC client in WSL2 or on your Windows host
2. Connect to `localhost:5900` (from WSL2) or your WSL2 IP on port 5900 (from Windows)
3. Use the password you set with `VNC_SERVER_PASSWORD` (default: `password`)

## Troubleshooting

### Common Connection Issues

1. **Connection Failed**: Ensure IB Gateway is running and API is enabled
2. **Timeout Error**: Check Windows Firewall settings
3. **API Not Authorized**: Make sure "Enable ActiveX and Socket Clients" is checked
4. **Wrong IP Address**: Confirm you're using the correct IP to reach Windows from WSL

### Network Diagnostics

1. Check if you can ping the Windows host from WSL2:
   ```bash
   ping <windows-host-lan-ip>
   ```

2. Try a basic TCP connection test:
   ```bash
   telnet <windows-host-lan-ip> 4002
   ```

3. Make sure your Windows host address hasn't changed (DHCP might assign a new IP):
   ```powershell
   # Run this in Windows PowerShell
   ipconfig
   ```

4. For connections timing out, try increasing the timeout in your code:
   ```python
   # In your connection code, increase the timeout
   config = IBGatewayConfig(
       host="172.28.64.1",
       port=4002,
       client_id=1,
       heartbeat_timeout=30.0  # Increase timeout to 30 seconds
   )
   ```