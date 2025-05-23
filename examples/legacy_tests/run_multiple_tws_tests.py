#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Multi-test TWS Launcher

This script demonstrates how to run multiple TWS tests simultaneously
by using different client IDs for each connection.
"""

import logging
import sys
import threading
import time
import subprocess
import os
import concurrent.futures
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("multi_test_launcher")

def run_test_with_client_id(test_script, client_id, additional_args=None):
    """
    Run a test script with a specific client ID.
    
    Args:
        test_script: Path to the test script
        client_id: Client ID to use for the connection
        additional_args: Optional list of additional arguments
        
    Returns:
        Tuple of (success, output)
    """
    if additional_args is None:
        additional_args = []
        
    cmd = [sys.executable, test_script, "--client-id", str(client_id)] + additional_args
    logger.info(f"Running: {' '.join(cmd)}")
    
    try:
        # Run the process and capture output
        start_time = time.time()
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Read output in real-time
        output_lines = []
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                output_lines.append(line.strip())
                # Print with client ID prefix
                print(f"[Client {client_id}] {line.strip()}")
                
        # Get return code
        return_code = process.wait()
        duration = time.time() - start_time
        
        success = return_code == 0
        status = "✅ Success" if success else "❌ Failed"
        logger.info(f"Test with client ID {client_id} completed: {status} (Duration: {duration:.2f}s)")
        
        return success, output_lines
    
    except Exception as e:
        logger.error(f"Error running test with client ID {client_id}: {str(e)}")
        return False, [str(e)]

def main():
    """Run multiple TWS tests in parallel."""
    parser = argparse.ArgumentParser(description="Run multiple TWS tests in parallel")
    parser.add_argument("--test-script", type=str, default="/home/pangasa/IBKR/simple_direct_test.py",
                      help="Path to the test script to run")
    parser.add_argument("--count", type=int, default=3,
                      help="Number of concurrent tests to run")
    parser.add_argument("--delay", type=float, default=1.0,
                      help="Delay between starting tests (in seconds)")
    parser.add_argument("--start-id", type=int, default=1,
                      help="Starting client ID")
    args = parser.parse_args()
    
    # Verify the test script exists
    if not os.path.isfile(args.test_script):
        logger.error(f"Test script not found: {args.test_script}")
        return False
    
    logger.info(f"Starting {args.count} instances of {args.test_script}")
    
    # Add --client-id argument support to the test script if needed
    # This requires modifying simple_direct_test.py to accept command line arguments
    
    # Run tests with different client IDs
    results = []
    
    # Sequential start with delay
    for i in range(args.count):
        client_id = args.start_id + i
        logger.info(f"Starting test {i+1}/{args.count} with client ID {client_id}")
        
        # Start the test in a separate thread
        t = threading.Thread(
            target=lambda: results.append(run_test_with_client_id(args.test_script, client_id))
        )
        t.start()
        
        # Add delay between test starts
        if i < args.count - 1:
            time.sleep(args.delay)
    
    # Wait for all tests to complete
    main_thread = threading.main_thread()
    for t in threading.enumerate():
        if t is not main_thread:
            t.join()
    
    # Print summary
    successful = sum(1 for success, _ in results if success)
    logger.info(f"All tests completed: {successful}/{len(results)} successful")
    
    return all(success for success, _ in results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)