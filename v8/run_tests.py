#!/usr/bin/env python3
"""
Test runner for V8 Meta-Learning components.
Runs all unit tests with proper path setup.
"""

import sys
import unittest
from pathlib import Path

# Add parent directory to path so tests can import modules
sys.path.insert(0, str(Path(__file__).parent))

def run_tests():
    """Discover and run all tests."""
    loader = unittest.TestLoader()
    start_dir = Path(__file__).parent / 'tests'
    suite = loader.discover(start_dir, pattern='test_*.py', top_level_dir=Path(__file__).parent)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print(f"Success rate: {(result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100:.1f}%")
    print("=" * 70)
    
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    sys.exit(run_tests())
