#!/usr/bin/env python3
"""
Simple test script with path correction to verify live API connectivity.
Reads API key and base URL from .env file.
"""

import os
import sys
import json
import requests
from api_client import ApiClient

def load_env_file(file_path='.env'):
    """Load environment variables from .env file."""
    if not os.path.exists(file_path):
        return
        
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            key, value = line.split('=', 1)
            os.environ[key] = value

def main():
    """Test API client with direct connection."""
    # Load environment variables from .env file
    load_env_file()
    
    # Get API credentials
    api_key = os.environ.get('API_KEY')
    base_url = os.environ.get('API_BASE_URL')
    
    # Validate credentials
    if not api_key:
        print("Error: API_KEY not set in .env file.")
        sys.exit(1)
        
    if not base_url:
        print("Error: API_BASE_URL not set in .env file.")
        sys.exit(1)
    
    print("Testing API client with direct connection...")
    print(f"Using API base URL: {base_url}")
    print(f"Using API key: {api_key[:4]}...{api_key[-4:] if len(api_key) > 8 else ''}")
    
    # Make direct requests without using the ApiClient class
    headers = {"X-API-Key": api_key}
    
    # Test status endpoint
    print("\nTesting status endpoint:")
    status_url = f"{base_url.rstrip('/')}/status"
    try:
        response = requests.get(status_url, headers=headers)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"System Status: {data.get('data', {}).get('system', {}).get('status', 'unknown')}")
            print(f"Market Hours: {data.get('data', {}).get('market', {}).get('is_market_hours', 'unknown')}")
            tickers = data.get('data', {}).get('tickers', [])
            print(f"Tickers: {tickers[:5]}{'...' if len(tickers) > 5 else ''}")
        else:
            print(f"Error response: {response.text}")
    except Exception as e:
        print(f"Error accessing status endpoint: {str(e)}")
    
    # Test tickers endpoint
    print("\nTesting tickers endpoint:")
    tickers_url = f"{base_url.rstrip('/')}/tickers"
    try:
        response = requests.get(tickers_url, headers=headers)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            tickers = data.get('data', {}).get('tickers', [])
            print(f"Tickers: {tickers}")
            print(f"Count: {data.get('data', {}).get('count', 0)}")
        else:
            print(f"Error response: {response.text}")
    except Exception as e:
        print(f"Error accessing tickers endpoint: {str(e)}")
    
    # Analyze the issue with ApiClient
    print("\nAnalyzing ApiClient issue:")
    try:
        # Create ApiClient but intercept its request 
        with ApiClient(base_url=base_url, api_key=api_key) as client:
            # Get the URL it would create
            status_url_from_client = client._build_url('/api/v1/status')
            print(f"ApiClient would request: {status_url_from_client}")
            
            # Compare with the working URL
            print(f"Working direct URL: {status_url}")
            
            # The issue may be that the client is adding '/api/v1' path again
            # Try manually requesting status with the client but fixed path
            print("\nTrying a custom request with the client:")
            try:
                # Remove '/api/v1' from the client path if needed
                fixed_endpoint = 'status' if '/api/v1' in base_url else '/api/v1/status'
                response = client.get(fixed_endpoint)
                print(f"Custom request result: {response}")
            except Exception as e:
                print(f"Custom request error: {str(e)}")
                
    except Exception as e:
        print(f"Error analyzing client: {str(e)}")
    
    print("\nTest completed.")

if __name__ == "__main__":
    main()