#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Run TWS integration tests using a persistent connection.

This script runs integration tests that all share a single TWS connection,
avoiding the connection/disconnection overhead between tests.
"""

import os
import sys
import logging
import subprocess
import argparse
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("run_persistent_tests")

def setup_environment():
    """Set up environment variables for testing."""
    # Set the TWS connection parameters
    env_vars = {
        "IB_HOST": "172.28.64.1",  # WSL-to-Windows host IP
        "IB_PORT": "7497",          # TWS paper trading port
        "IB_CLIENT_ID": "1",        # Fixed client ID
        "PYTHONPATH": str(Path(__file__).parent)  # Ensure project root is in path
    }
    
    # Update environment
    for key, value in env_vars.items():
        os.environ[key] = value
        logger.info(f"Set environment variable: {key}={value}")
    
    return env_vars

def run_tests(test_files=None, verbose=True, exit_on_failure=True):
    """Run the specified test files with pytest."""
    # Default test directory if no files specified
    if test_files is None:
        test_files = ["tests/integration/test_persistent_connection.py"]
    
    # Build pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Add verbosity flags
    if verbose:
        cmd.extend(["-v", "--log-cli-level=INFO"])
    
    # Add test files
    cmd.extend(test_files)
    
    logger.info(f"Running tests with command: {' '.join(cmd)}")
    
    # Run tests
    result = subprocess.run(cmd)
    
    # Check result
    if result.returncode != 0 and exit_on_failure:
        logger.error(f"Tests failed with return code: {result.returncode}")
        sys.exit(result.returncode)
    
    return result.returncode == 0

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run TWS integration tests with persistent connection")
    parser.add_argument("test_files", nargs="*", help="Test files to run (default: all integration tests)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--no-exit", action="store_true", help="Don't exit on test failure")
    
    args = parser.parse_args()
    
    # Set up environment
    setup_environment()
    
    # Run tests
    success = run_tests(
        test_files=args.test_files or None,
        verbose=args.verbose,
        exit_on_failure=not args.no_exit
    )
    
    if success:
        logger.info("All tests passed successfully!")
    else:
        logger.error("Some tests failed")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())