#!/usr/bin/env python3
"""Check if the environment variables are set."""

import os

print(f"API_KEY is set: {os.environ.get('API_KEY') is not None}")
print(f"API_BASE_URL is set: {os.environ.get('API_BASE_URL') is not None}")