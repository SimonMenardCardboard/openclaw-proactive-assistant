#!/usr/bin/env python3
"""
V7 File Descriptor Monitor
Detects file descriptor leaks in running processes
"""

import subprocess
from typing import Dict, Optional
from datetime import datetime


class FileDescriptorMonitor:
    """Monitor file descriptor usage for processes."""
    
    def __init__(self, thresholds: Optional[Dict] = None):
        """
        Initialize FD monitor.
        
        Args:
            thresholds: Dict with 'file_descriptors' config
        """
        if thresholds and 'file_descriptors' in thresholds:
            fd_config = thresholds['file_descriptors']
            self.warning_threshold = fd_config.get('warning_threshold', 100)
            self.critical_threshold = fd_config.get('critical_threshold', 500)
            self.monitored_processes = fd_config.get('monitored_processes', [])
        else:
            self.warning_threshold = 100
            self.critical_threshold = 500
            self.monitored_processes = []
    
    def check_process(self, process_name: str) -> Dict:
        """
        Check file descriptor count for a process.
        
        Args:
            process_name: Process name to check
            
        Returns:
            Dict with status, fd_count, and optional action
        """
        try:
            # Get process PID
            result = subprocess.run(
                ['pgrep', '-f', process_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if not result.stdout.strip():
                return {
                    'status': 'not_running',
                    'message': f'Process not found: {process_name}'
                }
            
            pid = result.stdout.strip().split()[0]
            
            # Count file descriptors using lsof
            result = subprocess.run(
                ['lsof', '-p', pid],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # Count lines (minus header)
            fd_count = len(result.stdout.strip().split('\n')) - 1
            
            if fd_count > self.critical_threshold:
                return {
                    'status': 'critical',
                    'action': 'restart_process',
                    'fd_count': fd_count,
                    'threshold': self.critical_threshold,
                    'message': f'{process_name} has {fd_count} FDs (critical: {self.critical_threshold})'
                }
            elif fd_count > self.warning_threshold:
                return {
                    'status': 'warning',
                    'action': 'monitor_closely',
                    'fd_count': fd_count,
                    'threshold': self.warning_threshold,
                    'message': f'{process_name} has {fd_count} FDs (warning: {self.warning_threshold})'
                }
            else:
                return {
                    'status': 'ok',
                    'fd_count': fd_count
                }
        
        except subprocess.TimeoutExpired:
            return {
                'status': 'error',
                'message': f'Timeout checking {process_name}'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Error checking {process_name}: {e}'
            }
    
    def check_all(self) -> Dict[str, Dict]:
        """
        Check all monitored processes.
        
        Returns:
            Dict mapping process_name to status dict
        """
        results = {}
        
        for process_name in self.monitored_processes:
            results[process_name] = self.check_process(process_name)
        
        return results


def main():
    """Test FD monitor."""
    import json
    from pathlib import Path
    
    # Load threshold config
    config_file = Path.home() / '.openclaw/workspace/integrations/intelligence/v7_threshold_config.json'
    
    if config_file.exists():
        with open(config_file) as f:
            thresholds = json.load(f)
    else:
        thresholds = None
    
    monitor = FileDescriptorMonitor(thresholds)
    
    print(f"File Descriptor Monitor Test")
    print(f"Warning threshold: {monitor.warning_threshold}")
    print(f"Critical threshold: {monitor.critical_threshold}")
    print(f"Monitored processes: {monitor.monitored_processes}")
    print()
    
    if monitor.monitored_processes:
        results = monitor.check_all()
        
        for process_name, status in results.items():
            print(f"\n{process_name}:")
            for key, value in status.items():
                print(f"  {key}: {value}")
    else:
        print("No processes configured for monitoring")
        print("\nTesting with proactive_telegram_notifier:")
        result = monitor.check_process('proactive_telegram_notifier')
        for key, value in result.items():
            print(f"  {key}: {value}")


if __name__ == '__main__':
    main()
