#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration test runner for TWS tests.

This script runs integration tests using the TWS conftest.py,
which connects to TWS once at the beginning and disconnects at the end.

Usage:
    python3 run_integration_tests.py [pytest options]

Example:
    python3 run_integration_tests.py -v

The script automatically sets the necessary environment variables for WSL2
connectivity if no IB_HOST is specified.
"""

import os
import sys
import subprocess
import shutil
import tempfile
from pathlib import Path

# Set default environment variables if not already set
if "IB_HOST" not in os.environ:
    # Check if we're in WSL
    is_wsl = os.path.exists('/proc/sys/fs/binfmt_misc/WSLInterop')
    host = "172.28.64.1" if is_wsl else "127.0.0.1"
    os.environ["IB_HOST"] = host
    print(f"Setting IB_HOST={host}")

if "IB_PORT" not in os.environ:
    os.environ["IB_PORT"] = "7497"  # TWS paper trading port
    print(f"Setting IB_PORT=7497")

if "IB_CLIENT_ID" not in os.environ:
    os.environ["IB_CLIENT_ID"] = "1"  # Use consistent client ID
    print(f"Setting IB_CLIENT_ID=1")

# Use the existing conftest since we've updated it to use the correct TWS settings
target_conftest = Path("tests/integration/conftest.py")

# Backup the original conftest if it exists
backup_needed = target_conftest.exists()
backup_file = None

if backup_needed:
    backup_file = tempfile.mktemp(suffix=".py")
    print(f"Backing up original conftest to {backup_file}")
    shutil.copy(target_conftest, backup_file)

try:
    # We're now using the existing conftest.py which has been updated
    print(f"Using updated conftest from {target_conftest}")

    # Construct pytest command
    pytest_args = ["pytest",
                   "-xvs",  # x=exit on first failure, v=verbose, s=no capture
                  ]

    # Add any additional args
    pytest_args.extend(sys.argv[1:])

    # Add specific test path if no test path specified
    if all(arg.startswith("-") for arg in sys.argv[1:]):
        pytest_args.append("tests/integration")

    print(f"\nRunning: {' '.join(pytest_args)}")
    print(f"Using TWS at {os.environ['IB_HOST']}:{os.environ['IB_PORT']}")
    print("-" * 60)

    # Run the tests
    result = subprocess.run(pytest_args)

finally:
    # No need to restore as we're now using the updated conftest directly
    pass

sys.exit(result.returncode if 'result' in locals() else 1)