#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TWS Integration Test Runner

Provides safe, progressive testing of the TWS trading system.
"""

import os
import sys
import argparse
import subprocess
import logging
from typing import List, Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_runner")


class TWSTestRunner:
    """Test runner for TWS integration tests."""
    
    def __init__(self):
        self.test_levels = {
            "basic": {
                "name": "Basic Connectivity",
                "description": "Safe tests - only connectivity, no trading",
                "tests": [
                    "tests/integration/test_basic_tws_connection.py",
                    "tests/integration/test_tws_connection.py",
                ],
                "safety": "SAFE",
                "requires_tws": True,
                "requires_order_flag": False
            },
            "market_data": {
                "name": "Market Data Integration", 
                "description": "Read-only market data tests",
                "tests": [
                    "tests/integration/test_market_data_tws.py",
                ],
                "safety": "SAFE", 
                "requires_tws": True,
                "requires_order_flag": False
            },
            "orders": {
                "name": "Order Placement",
                "description": "⚠️  PLACES REAL ORDERS (paper trading only!)",
                "tests": [
                    "tests/integration/test_order_placement_tws.py",
                ],
                "safety": "CAUTION",
                "requires_tws": True,
                "requires_order_flag": True
            },
            "e2e": {
                "name": "End-to-End Workflows",
                "description": "Complete system integration tests",
                "tests": [
                    "tests/integration/test_e2e_trading_workflow.py",
                ],
                "safety": "SAFE",
                "requires_tws": True,
                "requires_order_flag": False
            },
            "all": {
                "name": "All Integration Tests",
                "description": "Complete test suite (includes order placement!)",
                "tests": [
                    "tests/integration/",
                ],
                "safety": "CAUTION",
                "requires_tws": True,
                "requires_order_flag": True
            }
        }
    
    def check_prerequisites(self, level: str) -> Dict[str, bool]:
        """Check if prerequisites are met for test level."""
        test_config = self.test_levels[level]
        results = {}
        
        # Check TWS connection
        if test_config["requires_tws"]:
            results["tws_available"] = self._check_tws_connection()
        else:
            results["tws_available"] = True
            
        # Check order test flag
        if test_config["requires_order_flag"]:
            results["order_flag_set"] = self._check_order_flag()
        else:
            results["order_flag_set"] = True
            
        # Check environment variables
        results["env_configured"] = self._check_environment()
        
        return results
    
    def _check_tws_connection(self) -> bool:
        """Check if TWS is available."""
        import socket
        
        host = os.environ.get("TWS_HOST", "127.0.0.1")
        port = int(os.environ.get("TWS_PORT", "7497"))
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def _check_order_flag(self) -> bool:
        """Check if order tests are enabled."""
        return os.environ.get("TWS_ENABLE_ORDER_TESTS", "").lower() == "true"
    
    def _check_environment(self) -> bool:
        """Check if environment is properly configured."""
        required_vars = ["TWS_HOST", "TWS_PORT", "TWS_CLIENT_ID"]
        return all(os.environ.get(var) for var in required_vars)
    
    def print_test_levels(self):
        """Print available test levels."""
        print("\nAvailable Test Levels:")
        print("=" * 60)
        
        for level, config in self.test_levels.items():
            safety_color = "\033[92m" if config["safety"] == "SAFE" else "\033[93m"
            reset_color = "\033[0m"
            
            print(f"\n{level.upper()}: {config['name']}")
            print(f"  Description: {config['description']}")
            print(f"  Safety: {safety_color}{config['safety']}{reset_color}")
            print(f"  Tests: {len(config['tests'])} test file(s)")
    
    def run_tests(self, level: str, verbose: bool = False, stop_on_failure: bool = True) -> bool:
        """Run tests for specified level."""
        if level not in self.test_levels:
            logger.error(f"Unknown test level: {level}")
            return False
            
        test_config = self.test_levels[level]
        
        # Check prerequisites
        logger.info(f"Checking prerequisites for {test_config['name']}...")
        prereqs = self.check_prerequisites(level)
        
        for check, passed in prereqs.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            logger.info(f"  {check}: {status}")
        
        if not all(prereqs.values()):
            logger.error("Prerequisites not met. Cannot run tests.")
            return False
        
        # Show safety warning for dangerous tests
        if test_config["safety"] == "CAUTION":
            print("\n" + "⚠️ " * 20)
            print("WARNING: These tests place REAL ORDERS in TWS!")
            print("Ensure you are using PAPER TRADING ONLY!")
            print("⚠️ " * 20)
            
            response = input("\nType 'I UNDERSTAND' to proceed: ")
            if response != "I UNDERSTAND":
                print("Test execution cancelled.")
                return False
        
        # Run tests
        logger.info(f"Running {test_config['name']} tests...")
        
        success = True
        for test_file in test_config["tests"]:
            logger.info(f"Running: {test_file}")
            
            cmd = ["python", "-m", "pytest", test_file]
            if verbose:
                cmd.append("-v")
            if stop_on_failure:
                cmd.append("-x")
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info(f"✅ {test_file} PASSED")
                else:
                    logger.error(f"❌ {test_file} FAILED")
                    if verbose:
                        print("STDOUT:", result.stdout)
                        print("STDERR:", result.stderr)
                    success = False
                    
                    if stop_on_failure:
                        break
                        
            except Exception as e:
                logger.error(f"Error running {test_file}: {e}")
                success = False
                if stop_on_failure:
                    break
        
        return success
    
    def setup_environment(self):
        """Help user setup environment."""
        print("\nEnvironment Setup Guide:")
        print("=" * 50)
        
        print("\n1. Set environment variables:")
        print("   export TWS_HOST=127.0.0.1")
        print("   export TWS_PORT=7497")
        print("   export TWS_CLIENT_ID=10")
        print("   export TWS_ACCOUNT=your_paper_account")
        
        print("\n2. For order placement tests:")
        print("   export TWS_ENABLE_ORDER_TESTS=true")
        
        print("\n3. Ensure TWS is running:")
        print("   - Start Trader Workstation")
        print("   - Use paper trading account")
        print("   - Enable API in Global Configuration")
        print("   - Set socket port to 7497")
        
        print("\n4. Test connectivity:")
        print("   python run_integration_tests.py basic")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="TWS Integration Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_integration_tests.py basic              # Safe connectivity tests
  python run_integration_tests.py market_data        # Market data tests  
  python run_integration_tests.py orders --verbose   # Order placement tests (CAUTION!)
  python run_integration_tests.py --list             # Show available test levels
  python run_integration_tests.py --setup            # Show setup guide
        """
    )
    
    parser.add_argument(
        "level",
        nargs="?",
        help="Test level to run (basic, market_data, orders, e2e, all)"
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available test levels"
    )
    
    parser.add_argument(
        "--setup",
        action="store_true", 
        help="Show environment setup guide"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose test output"
    )
    
    parser.add_argument(
        "--continue-on-failure",
        action="store_true",
        help="Continue running tests even if some fail"
    )
    
    args = parser.parse_args()
    
    runner = TWSTestRunner()
    
    if args.list:
        runner.print_test_levels()
        return
    
    if args.setup:
        runner.setup_environment()
        return
    
    if not args.level:
        print("Error: Test level required")
        parser.print_help()
        return
    
    # Run tests
    success = runner.run_tests(
        args.level,
        verbose=args.verbose,
        stop_on_failure=not args.continue_on_failure
    )
    
    if success:
        logger.info("🎉 All tests completed successfully!")
    else:
        logger.error("💥 Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main() 