#!/usr/bin/env python3
"""
V8 Meta-Learning Unit Test Runner
Runs all tests with proper path setup
"""

import sys
import os
from pathlib import Path

# Set up paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
os.chdir(str(project_root))

# Now run the integration test
print("Running V8 Integration Tests...")
print("=" * 60)

exec(open('test_all_components.py').read())
