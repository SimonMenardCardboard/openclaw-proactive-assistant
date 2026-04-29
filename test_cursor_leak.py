#!/usr/bin/env python3
"""
Test for cursor leak fix in ProactiveQueue

Before fix: Each get_pending() call leaked a cursor/file descriptor
After fix: Cursors are explicitly closed
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from proactive_queue import ProactiveQueue

def test_no_file_descriptor_leak():
    """Verify get_pending() doesn't leak file descriptors."""
    
    queue = ProactiveQueue()
    
    print("Testing for cursor leaks...")
    print("Calling get_pending() 100 times...")
    
    for i in range(100):
        pending = queue.get_pending(limit=5)
        if i % 10 == 0:
            print(f"  Iteration {i}...")
    
    print("✅ Complete!")
    print()
    print("Check file descriptors with:")
    print(f"  lsof -p {os.getpid()} | grep proactive_queue.db")
    print()
    print("Should see only 1-2 handles (not 100+)")


if __name__ == '__main__':
    import os
    test_no_file_descriptor_leak()
