#!/usr/bin/env python3
"""
Simple test script to verify live API connectivity using direct requests.
"""

import os
import requests
import json

def test_api_connection():
    """Test API connection with direct requests."""
    
    # Get environment variables
    api_key = os.environ.get('API_KEY')
    base_url = os.environ.get('API_BASE_URL')
    
    if not api_key:
        print("Error: API_KEY environment variable not set")
        return False
        
    if not base_url:
        print("Error: API_BASE_URL environment variable not set")
        return False
    
    print(f"Testing API connection to: {base_url}")
    print(f"Using API key: {api_key[:8]}...")
    
    # Test status endpoint
    try:
        headers = {"X-API-Key": api_key}
        status_url = f"{base_url.rstrip('/')}/status"
        
        print(f"\nTesting status endpoint: {status_url}")
        response = requests.get(status_url, headers=headers, timeout=10)
        
        print(f"Status code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"Response: {json.dumps(data, indent=2)}")
                return True
            except json.JSONDecodeError:
                print(f"Response content (not JSON): {response.text[:500]}")
                return False
        else:
            print(f"Error response: {response.text[:500]}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return False
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_api_connection()
    if success:
        print("\n✅ API connection test PASSED")
    else:
        print("\n❌ API connection test FAILED") 