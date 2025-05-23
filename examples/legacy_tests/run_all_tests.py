#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Comprehensive Test Runner

This script runs the complete test suite:
1. Unit tests (via pytest)
2. Integration tests (via pytest with markers)
3. Connection tests (TWS connectivity)

Results are collected and summarized in a failure report.
"""

import os
import sys
import subprocess
import time
import logging
import argparse
import tempfile
import concurrent.futures
from datetime import datetime
from pathlib import Path
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_suite_runner")

class TestRunner:
    """Test runner that executes test suites and collects results."""
    
    def __init__(self, base_dir=None, output_dir=None, parallel=True, max_workers=4):
        """Initialize test runner."""
        self.base_dir = base_dir or Path('/home/pangasa/IBKR')
        self.output_dir = output_dir or Path(tempfile.gettempdir()) / f"test_results_{int(time.time())}"
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.parallel = parallel
        self.max_workers = max_workers
        self.results = {
            "unit_tests": {"success": False, "failures": [], "skipped": [], "details": {}},
            "integration_tests": {"success": False, "failures": [], "skipped": [], "details": {}},
            "connection_tests": {"success": False, "failures": [], "details": {}},
        }
        
    def run_command(self, cmd, label, env=None, cwd=None):
        """Run a command and capture output."""
        logger.info(f"Running {label}: {' '.join(cmd)}")
        
        start_time = time.time()
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env or os.environ.copy(),
            cwd=cwd or self.base_dir
        )
        
        output_lines = []
        for line in process.stdout:
            line = line.rstrip()
            output_lines.append(line)
            print(f"[{label}] {line}")
            
        return_code = process.wait()
        duration = time.time() - start_time
        
        # Save output to file
        output_file = Path(self.output_dir) / f"{label.replace(' ', '_').lower()}.log"
        with open(output_file, 'w') as f:
            f.write('\n'.join(output_lines))
            
        return {
            "success": return_code == 0,
            "return_code": return_code,
            "duration": duration,
            "output": output_lines,
            "output_file": str(output_file)
        }
        
    def run_unit_tests(self):
        """Run unit tests using pytest."""
        logger.info("Starting unit tests...")
        
        cmd = [
            sys.executable, "-m", "pytest", 
            "-v",                           # Verbose output
            "--no-header",                  # No pytest header
            "-k", "not integration",        # Exclude integration tests
            "--tb=native",                  # Native traceback style
            "-p", "no:warnings",            # Disable warning capture
            f"--junitxml={self.output_dir}/unit_results.xml"  # JUnit XML output
        ]
        
        result = self.run_command(cmd, "Unit Tests", cwd=self.base_dir)
        self.results["unit_tests"]["success"] = result["success"]
        self.results["unit_tests"]["details"] = result
        
        # Parse output to extract failures
        for line in result["output"]:
            if " FAILED " in line:
                self.results["unit_tests"]["failures"].append(line.strip())
            elif " SKIPPED " in line:
                self.results["unit_tests"]["skipped"].append(line.strip())
                
        return result["success"]
    
    def run_integration_tests(self):
        """Run integration tests using pytest."""
        logger.info("Starting integration tests...")
        
        cmd = [
            sys.executable, "-m", "pytest", 
            "-v",                          # Verbose output
            "--no-header",                 # No pytest header
            "-k", "integration",           # Only run integration tests
            "--tb=native",                 # Native traceback style
            "-p", "no:warnings",           # Disable warning capture 
            f"--junitxml={self.output_dir}/integration_results.xml"  # JUnit XML output
        ]
        
        result = self.run_command(cmd, "Integration Tests", cwd=self.base_dir)
        self.results["integration_tests"]["success"] = result["success"]
        self.results["integration_tests"]["details"] = result
        
        # Parse output to extract failures
        for line in result["output"]:
            if " FAILED " in line:
                self.results["integration_tests"]["failures"].append(line.strip())
            elif " SKIPPED " in line:
                self.results["integration_tests"]["skipped"].append(line.strip())
                
        return result["success"]
    
    def run_connection_test(self, test_file, client_id):
        """Run a single connection test."""
        if not os.path.exists(test_file):
            logger.error(f"Test file not found: {test_file}")
            return {"success": False, "error": "File not found"}
            
        # Run the connection test
        cmd = [
            sys.executable, 
            test_file,
            "--client-id", str(client_id)
        ]
        
        label = f"Connection Test {os.path.basename(test_file)} (Client {client_id})"
        return self.run_command(cmd, label, cwd=os.path.dirname(test_file))
    
    def run_connection_tests(self):
        """Run connection tests."""
        logger.info("Starting connection tests...")
        
        # List of connection test scripts to run
        test_files = [
            str(self.base_dir / "simple_direct_test.py"),
        ]
        
        if self.parallel and len(test_files) > 1:
            # Run connection tests in parallel
            all_results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(self.max_workers, len(test_files))) as executor:
                futures = {}
                for i, test_file in enumerate(test_files):
                    client_id = i + 1
                    future = executor.submit(self.run_connection_test, test_file, client_id)
                    futures[future] = (test_file, client_id)
                
                # Wait for completion
                for future in concurrent.futures.as_completed(futures):
                    test_file, client_id = futures[future]
                    try:
                        result = future.result()
                        all_results.append((test_file, client_id, result))
                    except Exception as e:
                        logger.error(f"Error in connection test {test_file} (Client {client_id}): {str(e)}")
                        all_results.append((test_file, client_id, {"success": False, "error": str(e)}))
        else:
            # Run connection tests sequentially
            all_results = []
            for i, test_file in enumerate(test_files):
                client_id = i + 1
                result = self.run_connection_test(test_file, client_id)
                all_results.append((test_file, client_id, result))
                
        # Process results
        success = True
        for test_file, client_id, result in all_results:
            test_name = os.path.basename(test_file)
            if not result.get("success", False):
                success = False
                self.results["connection_tests"]["failures"].append(f"{test_name} (Client {client_id})")
            
            self.results["connection_tests"]["details"][f"{test_name}_{client_id}"] = result
            
        self.results["connection_tests"]["success"] = success
        return success
    
    def run_all(self):
        """Run all test suites."""
        logger.info("Starting complete test suite run...")
        start_time = time.time()
        
        # Run each test suite
        unit_success = self.run_unit_tests()
        integration_success = self.run_integration_tests()
        connection_success = self.run_connection_tests()
        
        # Calculate overall result
        overall_success = unit_success and integration_success and connection_success
        duration = time.time() - start_time
        
        # Add summary to results
        self.results["overall"] = {
            "success": overall_success,
            "duration": duration,
            "timestamp": datetime.now().isoformat(),
        }
        
        # Save results to JSON file
        results_file = Path(self.output_dir) / "test_results.json"
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
            
        # Generate failure report
        self.generate_failure_report()
        
        logger.info(f"All tests completed in {duration:.2f} seconds")
        logger.info(f"Overall result: {'SUCCESS' if overall_success else 'FAILURE'}")
        logger.info(f"Results saved to: {self.output_dir}")
        
        return overall_success
    
    def generate_failure_report(self):
        """Generate a failure report."""
        report_file = Path(self.output_dir) / "failure_report.txt"
        
        with open(report_file, 'w') as f:
            f.write("# Test Suite Failure Report\n\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")
            
            # Overall summary
            f.write("## Overall Summary\n\n")
            f.write(f"- Unit Tests: {'PASSED' if self.results['unit_tests']['success'] else 'FAILED'}\n")
            f.write(f"- Integration Tests: {'PASSED' if self.results['integration_tests']['success'] else 'FAILED'}\n")
            f.write(f"- Connection Tests: {'PASSED' if self.results['connection_tests']['success'] else 'FAILED'}\n")
            f.write(f"- Total Duration: {self.results['overall']['duration']:.2f} seconds\n\n")
            
            # Unit test failures
            f.write("## Unit Test Failures\n\n")
            if self.results["unit_tests"]["failures"]:
                for failure in self.results["unit_tests"]["failures"]:
                    f.write(f"- {failure}\n")
            else:
                f.write("No unit test failures.\n")
            f.write("\n")
            
            # Integration test failures
            f.write("## Integration Test Failures\n\n")
            if self.results["integration_tests"]["failures"]:
                for failure in self.results["integration_tests"]["failures"]:
                    f.write(f"- {failure}\n")
            else:
                f.write("No integration test failures.\n")
            f.write("\n")
            
            # Connection test failures
            f.write("## Connection Test Failures\n\n")
            if self.results["connection_tests"]["failures"]:
                for failure in self.results["connection_tests"]["failures"]:
                    f.write(f"- {failure}\n")
            else:
                f.write("No connection test failures.\n")
            f.write("\n")
            
            # Skipped tests
            f.write("## Skipped Tests\n\n")
            skipped_unit = self.results["unit_tests"]["skipped"]
            skipped_integration = self.results["integration_tests"]["skipped"]
            
            if skipped_unit or skipped_integration:
                if skipped_unit:
                    f.write("### Unit Tests\n\n")
                    for skipped in skipped_unit:
                        f.write(f"- {skipped}\n")
                    f.write("\n")
                
                if skipped_integration:
                    f.write("### Integration Tests\n\n")
                    for skipped in skipped_integration:
                        f.write(f"- {skipped}\n")
                    f.write("\n")
            else:
                f.write("No skipped tests.\n")
        
        logger.info(f"Failure report generated: {report_file}")
        return report_file

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run the complete test suite")
    parser.add_argument("--output-dir", type=str, help="Directory to store test results")
    parser.add_argument("--sequential", action="store_true", help="Run tests sequentially (no parallelism)")
    parser.add_argument("--max-workers", type=int, default=4, help="Maximum number of parallel workers")
    return parser.parse_args()

def main():
    """Main entry point."""
    args = parse_args()
    
    # Create and run test suite
    runner = TestRunner(
        output_dir=args.output_dir,
        parallel=not args.sequential,
        max_workers=args.max_workers
    )
    
    success = runner.run_all()
    
    # Print the failure report
    report_file = Path(runner.output_dir) / "failure_report.txt"
    if os.path.exists(report_file):
        print("\n--- Test Failure Report ---\n")
        with open(report_file, 'r') as f:
            print(f.read())
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())