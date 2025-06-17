#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Quick start script for the Alpaca Trading System.

This script provides a simple way to start the trading system
with minimal configuration.
"""

import sys
import os
import subprocess
from pathlib import Path


def check_environment():
    """Check if required environment variables are set."""
    required_vars = [
        'ALPACA_API_KEY', 'ALPACA_SECRET_KEY',
        'API_BASE_URL', 'API_KEY'
    ]
    
    missing = []
    for var in required_vars:
        if not os.environ.get(var):
            missing.append(var)
    
    if missing:
        print("Missing required environment variables:")
        for var in missing:
            print(f"   - {var}")
        print("\n💡 Please set these in your .env file or environment")
        return False
    
    return True


def check_alpaca_connection():
    """Check if Alpaca API is accessible."""
    print("🔍 Testing Alpaca connection...")
    
    try:
        # Run the Alpaca connection test
        result = subprocess.run(
            [sys.executable, "test_alpaca_connection.py"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print("Alpaca connection test passed")
            return True
        else:
            print("Alpaca connection test failed")
            print("Make sure your API credentials are correct")
            return False
            
    except Exception as e:
        print(f"Error testing Alpaca connection: {e}")
        return False


def main():
    """Main entry point."""
    print("Alpaca Trading System - Quick Start")
    print("=" * 50)
    
    # Check environment
    if not check_environment():
        print("\nWARNING: Please configure your environment first!")
        return 1
    
    # Check Alpaca connection
    if not check_alpaca_connection():
        print("\nWARNING: Please check:")
        print("   1. Your Alpaca API credentials are correct")
        print("   2. You have internet connectivity")
        print("   3. Alpaca services are operational")
        return 1
    
    print("\nAll checks passed! Starting trading system...")
    print("-" * 50)
    
    # Start the main trading app
    subprocess.run([sys.executable, "main_trading_app.py"])
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 