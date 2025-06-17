@echo off
echo ========================================
echo Alpaca Trading System Launcher
echo ========================================
echo.
echo ADVANCED FEATURES ENABLED:
echo - ATR-based stop loss and take profit
echo - Dynamic position sizing ($30k allocation)
echo - Custom parameters per ticker
echo - End-of-day closure at 3:59 PM ET
echo - Automatic double-down orders
echo ========================================
echo.

REM Set Alpaca credentials
set ALPACA_API_KEY=PKTY34BVA1M2IN3MNC1J
set ALPACA_SECRET_KEY=39clahOmP4EWEPGgyLd6YyQXifXPYF9dNU6aj7z4
set ALPACA_TRADING_MODE=paper

REM Set Prediction API credentials
set API_BASE_URL=https://toine-todo-list-4ef27f1146af.herokuapp.com/api/v1/
set API_KEY=JrLIxH9EbnN0ydbRK-YDf3ReK6ymnl8JJhSrKM2W3oA

echo Starting trading system...
echo.
echo Alpaca Mode: %ALPACA_TRADING_MODE%
echo API Endpoint: %API_BASE_URL%
echo.
echo Press Ctrl+C to stop the trading system
echo ========================================
echo.

python main_trading_app.py

pause 