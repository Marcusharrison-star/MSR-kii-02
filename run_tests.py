#!/usr/bin/env python3
"""Test runner for EcoGen Diagnostics."""
import sys
import unittest
import os

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    tests_dir = os.path.join(current_dir, "tests")
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Load specific test modules by file path to handle non-standard directory listing environments
    import importlib.util
    for test_file in ["test_analysis.py", "test_api.py"]:
        test_path = os.path.join(tests_dir, test_file)
        if os.path.exists(test_path):
            spec = importlib.util.spec_from_file_location(test_file[:-3], test_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            suite.addTests(loader.loadTestsFromModule(mod))
            
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
