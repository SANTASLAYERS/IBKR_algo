#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import unittest

# Add the repository root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Add the mock_ibapi directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'mock_ibapi')))

if __name__ == '__main__':
    # Import the test modules
    import unittest_heartbeat
    
    # Create a test suite
    suite = unittest.TestSuite()
    
    # Add all tests from the modules
    suite.addTest(unittest.makeSuite(unittest_heartbeat.TestHeartbeatMonitor))
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with non-zero code if there were failures
    sys.exit(not result.wasSuccessful())