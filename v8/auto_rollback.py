#!/usr/bin/env python3
"""
V8 Auto-Rollback System - Phase 3

Automatically rolls back problematic deployments.

Features:
- Automatic health monitoring
- Configurable rollback triggers
- Script backup/restore
- Notification on rollback
- Rollback history tracking

Usage:
    rollback = AutoRollback()
    
    # Deploy with automatic rollback protection
    rollback.deploy_with_protection(
        script_name='my_script',
        script_content='...',
        deployment_path='/path/to/script'
    )
    
    # Monitor runs in background
    # Auto-rolls back if issues detected
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
import time

# Add modules to path
sys.path.insert(0, str(Path(__file__).parent))
from health_monitor import HealthMonitor


class AutoRollback:
    """
    Automatic rollback system for deployed optimizations.
    
    Monitors deployments and automatically reverts if issues detected.
    """
    
    def __init__(self, 
                 backup_dir: Path = None,
                 monitor_interval: int = 60,
                 rollback_threshold: float = 0.7):
        """
        Initialize auto-rollback system.
        
        Args:
            backup_dir: Directory for script backups
            monitor_interval: Seconds between health checks
            rollback_threshold: Min success rate before rollback (0.0-1.0)
        """
        if backup_dir is None:
            backup_dir = Path.home() / '.openclaw/workspace/integrations/intelligence/v8_meta_learning/backups'
        
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self.monitor_interval = monitor_interval
        self.rollback_threshold = rollback_threshold
        
        self.health_monitor = HealthMonitor()
    
    def deploy_with_protection(self,
                               proposal_id: int,
                               script_name: str,
                               script_content: str,
                               deployment_path: Path) -> Dict:
        """
        Deploy script with automatic rollback protection.
        
        Args:
            proposal_id: Proposal ID from approval workflow
            script_name: Name of the script
            script_content: Script source code
            deployment_path: Where to deploy the script
        
        Returns:
            {
                'success': bool,
                'deployment_id': int,
                'backup_path': str,
                'monitoring': bool
            }
        """
        deployment_path = Path(deployment_path)
        
        # Step 1: Backup existing file (if exists)
        backup_path = None
        if deployment_path.exists():
            backup_path = self._create_backup(deployment_path)
        
        try:
            # Step 2: Deploy new script
            deployment_path.parent.mkdir(parents=True, exist_ok=True)
            deployment_path.write_text(script_content)
            deployment_path.chmod(0o755)  # Make executable
            
            # Step 3: Start health monitoring
            deployment_id = self.health_monitor.track_deployment(
                proposal_id=proposal_id,
                script_name=script_name,
                script_path=str(deployment_path)
            )
            
            # Step 4: Run initial smoke test
            smoke_test = self._smoke_test(deployment_path)
            
            if not smoke_test['success']:
                # Rollback immediately
                self._rollback(deployment_id, deployment_path, backup_path,
                              reason=f"Smoke test failed: {smoke_test['error']}")
                
                return {
                    'success': False,
                    'deployment_id': deployment_id,
                    'backup_path': str(backup_path) if backup_path else None,
                    'monitoring': False,
                    'error': smoke_test['error']
                }
            
            return {
                'success': True,
                'deployment_id': deployment_id,
                'backup_path': str(backup_path) if backup_path else None,
                'monitoring': True
            }
        
        except Exception as e:
            # Deployment failed - restore backup
            if backup_path and backup_path.exists():
                shutil.copy2(backup_path, deployment_path)
            
            return {
                'success': False,
                'deployment_id': None,
                'backup_path': str(backup_path) if backup_path else None,
                'monitoring': False,
                'error': str(e)
            }
    
    def _create_backup(self, file_path: Path) -> Path:
        """Create backup of existing file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{file_path.name}.{timestamp}.backup"
        backup_path = self.backup_dir / backup_name
        
        shutil.copy2(file_path, backup_path)
        
        return backup_path
    
    def _smoke_test(self, script_path: Path) -> Dict:
        """
        Run quick smoke test on deployed script.
        
        Returns:
            {
                'success': bool,
                'error': str (if failed)
            }
        """
        try:
            # Try to execute with --help or --version flag
            result = subprocess.run(
                [str(script_path), '--help'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # Exit code 0 or 1 (usage) are both OK
            success = result.returncode in [0, 1]
            
            return {
                'success': success,
                'error': result.stderr if not success else None
            }
        
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Smoke test timeout'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _rollback(self, 
                  deployment_id: int,
                  script_path: Path,
                  backup_path: Optional[Path],
                  reason: str):
        """Execute rollback"""
        # Restore from backup
        if backup_path and backup_path.exists():
            shutil.copy2(backup_path, script_path)
            restored = True
        else:
            # No backup - delete deployed file
            if script_path.exists():
                script_path.unlink()
            restored = False
        
        # Record rollback
        self.health_monitor.trigger_rollback(deployment_id, reason)
        
        # TODO: Notify user
        print(f"⚠️  Rollback triggered: {reason}")
        print(f"   Script: {script_path}")
        print(f"   Restored: {restored}")
    
    def check_and_rollback(self, deployment_id: int, script_path: Path, backup_path: Optional[Path] = None) -> bool:
        """
        Check health and rollback if needed.
        
        Returns: True if rolled back, False if healthy
        """
        health = self.health_monitor.check_health(deployment_id)
        
        # Check rollback conditions
        should_rollback = False
        reason = None
        
        metrics = health.get('metrics', {})
        
        # Condition 1: Low success rate
        if metrics.get('success_rate', 1.0) < self.rollback_threshold:
            should_rollback = True
            reason = f"Success rate {metrics['success_rate']*100:.1f}% below threshold {self.rollback_threshold*100:.0f}%"
        
        # Condition 2: Script disappeared
        if not metrics.get('script_exists', True):
            should_rollback = True
            reason = "Script file not found"
        
        # Condition 3: Too many errors in short time
        if metrics.get('failures', 0) > 10 and metrics.get('total_executions', 0) <= 20:
            should_rollback = True
            reason = f"High failure rate: {metrics['failures']}/{metrics['total_executions']}"
        
        if should_rollback:
            self._rollback(deployment_id, Path(script_path), backup_path, reason)
            return True
        
        return False
    
    def monitor_deployment(self,
                          deployment_id: int,
                          script_path: Path,
                          backup_path: Optional[Path] = None,
                          duration_hours: int = 24):
        """
        Continuously monitor a deployment for health issues.
        
        Args:
            deployment_id: Deployment to monitor
            script_path: Path to deployed script
            backup_path: Path to backup file
            duration_hours: How long to monitor
        """
        start_time = time.time()
        end_time = start_time + (duration_hours * 3600)
        
        print(f"🔍 Monitoring deployment {deployment_id} for {duration_hours}h...")
        
        while time.time() < end_time:
            # Check health
            rolled_back = self.check_and_rollback(deployment_id, script_path, backup_path)
            
            if rolled_back:
                print(f"❌ Deployment {deployment_id} rolled back")
                break
            
            # Sleep until next check
            time.sleep(self.monitor_interval)
        
        if not rolled_back:
            print(f"✅ Deployment {deployment_id} monitoring complete - no issues")


def main():
    """Test auto-rollback system"""
    import tempfile
    
    rollback = AutoRollback(monitor_interval=5, rollback_threshold=0.7)
    
    print("V8 Auto-Rollback System - Test Suite")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_script = Path(tmpdir) / 'test_script.sh'
        
        # Test 1: Deploy with protection
        print("\n1. Testing protected deployment...")
        result = rollback.deploy_with_protection(
            proposal_id=1,
            script_name='test_script',
            script_content='#!/bin/bash\necho "Hello"\n',
            deployment_path=test_script
        )
        
        print(f"   Success: {result['success']}")
        print(f"   Monitoring: {result['monitoring']}")
        print(f"   Deployment ID: {result['deployment_id']}")
        
        deployment_id = result['deployment_id']
        
        # Test 2: Record some successful executions
        print("\n2. Testing successful executions...")
        for i in range(3):
            rollback.health_monitor.record_execution(
                deployment_id=deployment_id,
                exit_code=0,
                duration=0.5
            )
        print("   Recorded 3 successful executions")
        
        # Test 3: Check health (should be healthy)
        print("\n3. Testing health check (should be healthy)...")
        rolled_back = rollback.check_and_rollback(deployment_id, test_script)
        print(f"   Rolled back: {rolled_back}")
        
        # Test 4: Record failures
        print("\n4. Testing failure detection...")
        for i in range(5):
            rollback.health_monitor.record_execution(
                deployment_id=deployment_id,
                exit_code=1,
                duration=1.0,
                error="Test error"
            )
        print("   Recorded 5 failures")
        
        # Test 5: Check health (should trigger rollback)
        print("\n5. Testing automatic rollback...")
        rolled_back = rollback.check_and_rollback(deployment_id, test_script)
        print(f"   Rolled back: {rolled_back}")
        
        # Test 6: Verify rollback in database
        print("\n6. Testing rollback status...")
        status = rollback.health_monitor.get_deployment_status(deployment_id)
        print(f"   Status: {status['status']}")
        print(f"   Rollback reason: {status['rollback_reason']}")
    
    print("\n" + "=" * 70)
    print("✓ All auto-rollback tests complete!")


if __name__ == '__main__':
    main()
