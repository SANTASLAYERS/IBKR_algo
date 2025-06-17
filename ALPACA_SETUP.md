# Alpaca Credentials Setup Guide

## Getting Your Alpaca Credentials

1. **Sign up for a free Alpaca account** at https://app.alpaca.markets
2. **Navigate to your API keys** in the Alpaca dashboard
3. **Generate API keys** for paper trading (recommended for testing)

## Setting Up Environment Variables

You have three options:

### Option 1: Create a .env file (Recommended)
Create a `.env` file in the project root with:
```
ALPACA_API_KEY=your_actual_api_key_here
ALPACA_SECRET_KEY=your_actual_secret_key_here
ALPACA_TRADING_MODE=paper
```

### Option 2: Use the setup script (Interactive)
Run the PowerShell setup script:
```powershell
.\setup_alpaca_env.ps1
```
This will prompt you for your credentials securely.

### Option 3: Edit and run the batch file
1. Edit `set_alpaca_env.bat` with your credentials
2. Run it in your terminal: `set_alpaca_env.bat`
3. Then run the tests in the same terminal session

### Option 4: Set manually in PowerShell
```powershell
$env:ALPACA_API_KEY="your_api_key"
$env:ALPACA_SECRET_KEY="your_secret_key"
$env:ALPACA_TRADING_MODE="paper"
```

## Running the Tests

Once credentials are set:
```bash
python test_unified_fill_manager_integration.py
```

## Running the Main App

```bash
python main_trading_app.py
```

## Important Notes

- Always use **paper trading** mode for testing
- Keep your credentials secure - never commit them to git
- The `.env` file is already in `.gitignore` for safety
- API keys can be regenerated anytime in your Alpaca dashboard

## Troubleshooting

If you get "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set":
1. Verify your credentials are correct
2. Make sure you're in the right terminal/session
3. Check that the .env file is in the project root
4. Try setting the variables manually as shown above 