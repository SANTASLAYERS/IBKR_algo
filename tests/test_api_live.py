#!/usr/bin/env python3
"""
Simple test script to verify live API connectivity.
Reads API key and base URL from .env file or command line arguments.
"""

import os
import sys
import json
import argparse
import requests
from api_client import (
    ApiClient, 
    StatusEndpoint, 
    TickersEndpoint
)

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

def test_direct_request(base_url, api_key):
    """Test API with direct requests."""
    print("\n--- Testing with direct requests ---")
    
    # Try a direct request to the base URL
    try:
        headers = {"X-API-Key": api_key}
        print(f"Making a GET request to {base_url}")
        response = requests.get(base_url, headers=headers)
        print(f"Status code: {response.status_code}")
        print(f"Response content: {response.text[:200]}...")
    except Exception as e:
        print(f"Direct request error: {str(e)}")
    
    # Try the status endpoint
    try:
        status_url = f"{base_url.rstrip('/')}/status"
        print(f"\nMaking a GET request to {status_url}")
        response = requests.get(status_url, headers=headers)
        print(f"Status code: {response.status_code}")
        print(f"Response content: {response.text[:200]}...")
    except Exception as e:
        print(f"Status endpoint error: {str(e)}")

def main():
    """Test API client with live connection."""
    # Load environment variables from .env file
    load_env_file()
    
    # Parse command line arguments (these will override .env settings)
    parser = argparse.ArgumentParser(description="Test API client connectivity")
    parser.add_argument("--api-key", help="API key for authentication")
    parser.add_argument("--base-url", help="API base URL")
    args = parser.parse_args()
    
    # Get API credentials, prioritizing command line args over environment variables
    api_key = args.api_key or os.environ.get('API_KEY')
    base_url = args.base_url or os.environ.get('API_BASE_URL')
    
    # Validate credentials
    if not api_key:
        print("Error: API key is not set. Please provide it via --api-key argument or in the .env file.")
        sys.exit(1)
        
    if not base_url:
        print("Error: API base URL is not set. Please provide it via --base-url argument or in the .env file.")
        sys.exit(1)
    
    print("Testing API client with live connection...")
    print(f"Using API base URL: {base_url}")
    print(f"Using API key: {api_key[:4]}...{api_key[-4:] if len(api_key) > 8 else ''}")
    
    # First, try with direct requests to check basic connectivity
    test_direct_request(base_url, api_key)
    
    try:
        # Create API client
        client = ApiClient(base_url=base_url, api_key=api_key)
        
        print("\n--- Testing with API client ---")
        
        # Test status endpoint
        status = StatusEndpoint(client)
        print("\nFetching API status...")
        try:
            status_data = status.get_status()
            print(f"API Status Response: {status_data}")
        except Exception as e:
            print(f"Error with status endpoint: {str(e)}")
        
        # Test tickers endpoint
        tickers = TickersEndpoint(client)
        print("\nFetching supported tickers...")
        try:
            ticker_list = tickers.get_tickers()
            print(f"Supported Tickers Response: {ticker_list}")
        except Exception as e:
            print(f"Error with tickers endpoint: {str(e)}")
        
    except Exception as e:
        print(f"\nError with API client: {str(e)}")
    finally:
        # Close the client if it was created
        if 'client' in locals():
            client.close()
            
    print("\nAPI testing completed.")

if __name__ == "__main__":
    main()