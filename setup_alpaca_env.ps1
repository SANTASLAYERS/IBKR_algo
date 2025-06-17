# Alpaca Environment Setup Script
# This script helps you set up the required environment variables for Alpaca

Write-Host "Alpaca Trading System - Environment Setup" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host ""

# Check if running with actual credentials
$useRealCredentials = Read-Host "Do you want to use real Alpaca credentials? (yes/no)"

if ($useRealCredentials -eq "yes") {
    # Prompt for Alpaca credentials
    Write-Host ""
    Write-Host "Please enter your Alpaca credentials:" -ForegroundColor Yellow
    Write-Host "You can find these in your Alpaca dashboard at https://app.alpaca.markets" -ForegroundColor Cyan
    Write-Host ""
    
    $apiKey = Read-Host "Enter your Alpaca API Key" -AsSecureString
    $secretKey = Read-Host "Enter your Alpaca Secret Key" -AsSecureString
    
    # Convert secure strings to plain text
    $apiKeyPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($apiKey))
    $secretKeyPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secretKey))
    
    # Set environment variables
    $env:ALPACA_API_KEY = $apiKeyPlain
    $env:ALPACA_SECRET_KEY = $secretKeyPlain
    $env:ALPACA_TRADING_MODE = "paper"
    
    Write-Host ""
    Write-Host "Environment variables set successfully!" -ForegroundColor Green
    Write-Host "Using paper trading mode for safety." -ForegroundColor Yellow
    
} else {
    Write-Host ""
    Write-Host "To run the tests with actual Alpaca connection, you need to provide real credentials." -ForegroundColor Red
    Write-Host "You can get free paper trading credentials from: https://app.alpaca.markets" -ForegroundColor Yellow
    exit 1
}

# Verify the setup
Write-Host ""
Write-Host "Verifying setup..." -ForegroundColor Cyan

if ($env:ALPACA_API_KEY -and $env:ALPACA_SECRET_KEY) {
    Write-Host "✓ ALPACA_API_KEY is set" -ForegroundColor Green
    Write-Host "✓ ALPACA_SECRET_KEY is set" -ForegroundColor Green
    Write-Host "✓ ALPACA_TRADING_MODE is set to: $env:ALPACA_TRADING_MODE" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can now run the tests!" -ForegroundColor Green
    Write-Host "Use: python test_unified_fill_manager_integration.py" -ForegroundColor Yellow
} else {
    Write-Host "✗ Environment variables not properly set" -ForegroundColor Red
    exit 1
} 