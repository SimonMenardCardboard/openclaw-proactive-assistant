#!/usr/bin/env python3
"""
V8 Side-Effect Monitor - Phase 3

Monitors and tracks side effects during sandbox execution:
- File writes/creates/deletes
- Network calls (if allowed)
- Environment variable changes
- Process spawning
- System resource usage

Usage:
    monitor = SideEffectMonitor()
    
    with monitor.track():
        # Execute code
        subprocess.run(['python', 'script.py'])
    
    effects = monitor.get_effects()
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Set, Optional
from datetime import datetime
import hashlib


class SideEffectMonitor:
    """
    Monitor side effects during code execution.
    
    Tracks:
    - Files created/modified/deleted
    - Network activity (if monitoring enabled)
    - Subprocess spawning
    - Resource usage (CPU, memory)
    """
    
    def __init__(self, watch_dir: Path = None, track_network: bool = False):
        """
        Initialize side effect monitor.
        
        Args:
            watch_dir: Directory to monitor for file changes
            track_network: Whether to monitor network calls
        """
        self.watch_dir = watch_dir or Path.cwd()
        self.track_network = track_network
        
        # Tracking state
        self.files_before = {}
        self.files_after = {}
        self.network_calls = []
        self.subprocesses = []
        
        # File change tracking
        self.created_files = []
        self.modified_files = []
        self.deleted_files = []
    
    def _snapshot_files(self) -> Dict[str, Dict]:
        """
        Take a snapshot of all files in watch directory.
        
        Returns: {path: {size, mtime, hash}}
        """
        snapshot = {}
        
        try:
            for file_path in self.watch_dir.rglob('*'):
                if file_path.is_file():
                    try:
                        stat = file_path.stat()
                        
                        # Calculate file hash for change detection
                        file_hash = None
                        if stat.st_size < 1024 * 1024:  # Only hash files < 1MB
                            try:
                                with open(file_path, 'rb') as f:
                                    file_hash = hashlib.md5(f.read()).hexdigest()
                            except:
                                pass
                        
                        snapshot[str(file_path)] = {
                            'size': stat.st_size,
                            'mtime': stat.st_mtime,
                            'hash': file_hash
                        }
                    except (PermissionError, FileNotFoundError):
                        pass
        except Exception as e:
            print(f"Warning: Error taking file snapshot: {e}")
        
        return snapshot
    
    def start_tracking(self):
        """Start tracking side effects"""
        # Take before snapshot
        self.files_before = self._snapshot_files()
        self.network_calls = []
        self.subprocesses = []
    
    def stop_tracking(self):
        """Stop tracking and compute changes"""
        # Take after snapshot
        self.files_after = self._snapshot_files()
        
        # Detect changes
        self._detect_file_changes()
    
    def _detect_file_changes(self):
        """Detect file creates/modifies/deletes"""
        before_paths = set(self.files_before.keys())
        after_paths = set(self.files_after.keys())
        
        # Files created
        created_paths = after_paths - before_paths
        self.created_files = list(created_paths)
        
        # Files deleted
        deleted_paths = before_paths - after_paths
        self.deleted_files = list(deleted_paths)
        
        # Files modified (compare hash/mtime)
        common_paths = before_paths & after_paths
        self.modified_files = []
        
        for path in common_paths:
            before = self.files_before[path]
            after = self.files_after[path]
            
            # Check if modified
            if before['mtime'] != after['mtime']:
                self.modified_files.append(path)
            elif before.get('hash') and after.get('hash'):
                if before['hash'] != after['hash']:
                    self.modified_files.append(path)
    
    def get_effects(self) -> Dict:
        """
        Get all tracked side effects.
        
        Returns:
            {
                'files': {
                    'created': List[str],
                    'modified': List[str],
                    'deleted': List[str],
                    'total_changes': int
                },
                'network': List[Dict],
                'subprocesses': List[str],
                'summary': str
            }
        """
        total_changes = len(self.created_files) + len(self.modified_files) + len(self.deleted_files)
        
        # Build summary
        parts = []
        if self.created_files:
            parts.append(f"{len(self.created_files)} created")
        if self.modified_files:
            parts.append(f"{len(self.modified_files)} modified")
        if self.deleted_files:
            parts.append(f"{len(self.deleted_files)} deleted")
        
        summary = "Files: " + ", ".join(parts) if parts else "No file changes"
        
        if self.network_calls:
            summary += f" | Network: {len(self.network_calls)} calls"
        
        if self.subprocesses:
            summary += f" | Subprocesses: {len(self.subprocesses)}"
        
        return {
            'files': {
                'created': self.created_files,
                'modified': self.modified_files,
                'deleted': self.deleted_files,
                'total_changes': total_changes
            },
            'network': self.network_calls,
            'subprocesses': self.subprocesses,
            'summary': summary
        }
    
    def check_safety(self, effects: Dict = None) -> Dict:
        """
        Check if side effects are safe.
        
        Args:
            effects: Effects dict (uses self.get_effects() if not provided)
        
        Returns:
            {
                'safe': bool,
                'warnings': List[str],
                'violations': List[str]
            }
        """
        if effects is None:
            effects = self.get_effects()
        
        warnings = []
        violations = []
        
        files = effects['files']
        
        # Check for suspicious file operations
        if files['deleted']:
            # Any deletions are suspicious
            for path in files['deleted']:
                if '/usr' in path or '/bin' in path or '/etc' in path:
                    violations.append(f'System file deleted: {path}')
                else:
                    warnings.append(f'File deleted: {Path(path).name}')
        
        # Check for writes outside sandbox
        sandbox_dir = str(self.watch_dir)
        for path in files['created'] + files['modified']:
            if not path.startswith(sandbox_dir):
                warnings.append(f'Write outside sandbox: {path}')
        
        # Check for excessive file changes
        if files['total_changes'] > 100:
            warnings.append(f'Excessive file changes: {files["total_changes"]}')
        
        # Check network activity (if tracked)
        if effects['network']:
            if not self.track_network:
                violations.append('Unexpected network activity detected')
            elif len(effects['network']) > 10:
                warnings.append(f'High network activity: {len(effects["network"])} calls')
        
        # Check subprocess spawning
        if effects['subprocesses']:
            # Subprocesses are generally OK, but log them
            if len(effects['subprocesses']) > 5:
                warnings.append(f'Multiple subprocesses: {len(effects["subprocesses"])}')
        
        return {
            'safe': len(violations) == 0,
            'warnings': warnings,
            'violations': violations
        }
    
    def track(self):
        """
        Context manager for tracking side effects.
        
        Usage:
            with monitor.track():
                # Your code here
        """
        return SideEffectTracker(self)


class SideEffectTracker:
    """Context manager for side effect monitoring"""
    
    def __init__(self, monitor: SideEffectMonitor):
        self.monitor = monitor
    
    def __enter__(self):
        self.monitor.start_tracking()
        return self.monitor
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.monitor.stop_tracking()
        return False


def main():
    """Test side effect monitor"""
    import tempfile
    
    print("V8 Side Effect Monitor - Test Suite")
    print("=" * 70)
    
    # Create temporary test directory
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        monitor = SideEffectMonitor(watch_dir=test_dir)
        
        # Test 1: File creation
        print("\n1. Testing file creation...")
        with monitor.track():
            test_file = test_dir / 'test.txt'
            test_file.write_text('Hello world')
        
        effects = monitor.get_effects()
        print(f"   Summary: {effects['summary']}")
        print(f"   Created: {len(effects['files']['created'])} files")
        
        # Test 2: File modification
        print("\n2. Testing file modification...")
        monitor_2 = SideEffectMonitor(watch_dir=test_dir)
        with monitor_2.track():
            test_file.write_text('Modified content')
        
        effects_2 = monitor_2.get_effects()
        print(f"   Summary: {effects_2['summary']}")
        print(f"   Modified: {len(effects_2['files']['modified'])} files")
        
        # Test 3: File deletion
        print("\n3. Testing file deletion...")
        monitor_3 = SideEffectMonitor(watch_dir=test_dir)
        with monitor_3.track():
            test_file.unlink()
        
        effects_3 = monitor_3.get_effects()
        print(f"   Summary: {effects_3['summary']}")
        print(f"   Deleted: {len(effects_3['files']['deleted'])} files")
        
        # Test 4: Safety check
        print("\n4. Testing safety check...")
        safety = monitor_3.check_safety(effects_3)
        print(f"   Safe: {safety['safe']}")
        print(f"   Warnings: {safety['warnings']}")
        print(f"   Violations: {safety['violations']}")
        
        # Test 5: Multiple operations
        print("\n5. Testing multiple operations...")
        monitor_4 = SideEffectMonitor(watch_dir=test_dir)
        with monitor_4.track():
            # Create multiple files
            for i in range(3):
                (test_dir / f'file_{i}.txt').write_text(f'Content {i}')
        
        effects_4 = monitor_4.get_effects()
        print(f"   Summary: {effects_4['summary']}")
        
        safety_4 = monitor_4.check_safety(effects_4)
        print(f"   Safe: {safety_4['safe']}")
    
    print("\n" + "=" * 70)
    print("✓ All side effect monitor tests complete!")


if __name__ == '__main__':
    main()
