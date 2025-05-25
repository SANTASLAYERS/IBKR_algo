#!/usr/bin/env python3
"""
Quick Start Script for Trading System
=====================================

This script validates your environment and starts the trading system.

Usage:
    python start_trading.py
"""

import os
import sys
import subprocess
from pathlib import Path

def check_environment():
    """Check if all required environment variables are set."""
    required_vars = [
        'TWS_HOST', 'TWS_PORT', 'TWS_CLIENT_ID', 'TWS_ACCOUNT',
        'API_BASE_URL', 'API_KEY'
    ]
    
    missing = []
    for var in required_vars:
        if not os.environ.get(var):
            missing.append(var)
    
    if missing:
        print("❌ Missing required environment variables:")
        for var in missing:
            print(f"   - {var}")
        print("\nSet them in your environment or .env file")
        return False
    
    print("✅ All required environment variables are set")
    return True

def check_tws_connection():
    """Check if TWS is accessible."""
    print("🔍 Testing TWS connection...")
    try:
        result = subprocess.run([
            sys.executable, "test_api_connection.py"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ TWS connection test passed")
            return True
        else:
            print("❌ TWS connection test failed")
            print("Make sure TWS is running with API enabled")
            return False
    except Exception as e:
        print(f"❌ Error testing TWS connection: {e}")
        return False

def main():
    """Main entry point."""
    print("🚀 TWS Trading System - Quick Start")
    print("=" * 40)
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Check TWS connection  
    if not check_tws_connection():
        print("\n💡 Make sure:")
        print("   1. TWS is running")
        print("   2. API is enabled in TWS Global Configuration")
        print("   3. Socket port is set to 7497 (paper trading)")
        sys.exit(1)
    
    print("\n🎯 Environment ready!")
    print("🔥 Starting trading system...")
    print("=" * 40)
    
    # Start the main trading application
    try:
        subprocess.run([sys.executable, "main_trading_app.py"])
    except KeyboardInterrupt:
        print("\n🛑 Trading system stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting trading system: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 