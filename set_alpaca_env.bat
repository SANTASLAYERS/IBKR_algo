@echo off
REM Alpaca Environment Setup
REM Edit this file with your actual Alpaca credentials

REM ===== EDIT THESE VALUES =====
set ALPACA_API_KEY=YOUR_ALPACA_API_KEY_HERE
set ALPACA_SECRET_KEY=YOUR_ALPACA_SECRET_KEY_HERE
set ALPACA_TRADING_MODE=paper
REM =============================

echo Alpaca Environment Variables Set:
echo ALPACA_API_KEY=%ALPACA_API_KEY:~0,10%...
echo ALPACA_SECRET_KEY=%ALPACA_SECRET_KEY:~0,10%...
echo ALPACA_TRADING_MODE=%ALPACA_TRADING_MODE%
echo.
echo Now run: python test_unified_fill_manager_integration.py 