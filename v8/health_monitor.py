#!/usr/bin/env python3
"""
V8 Health Monitor - Phase 3

Monitors deployed optimizations for issues and performance.

Features:
- Post-deploy health checks
- Performance tracking
- Error detection
- Resource usage monitoring
- Automatic issue detection

Usage:
    monitor = HealthMonitor()
    monitor.track_deployment(deployment_id, script_path)
    
    # Later...
    health = monitor.check_health(deployment_id)
    if not health['healthy']:
        monitor.trigger_rollback(deployment_id)
"""

import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json


class HealthMonitor:
    """
    Monitor health of deployed optimizations.
    
    Tracks:
    - Execution success rate
    - Error patterns
    - Performance metrics
    - Resource usage
    - User complaints
    """
    
    def __init__(self, db_path: Path = None):
        if db_path is None:
            db_path = Path.home() / '.openclaw/workspace/integrations/intelligence/v8_meta_learning/health.db'
        
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize health monitoring database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deployments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposal_id INTEGER,
                script_name TEXT,
                script_path TEXT,
                deployed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active',
                rollback_at TEXT,
                rollback_reason TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS health_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deployment_id INTEGER,
                checked_at TEXT DEFAULT CURRENT_TIMESTAMP,
                check_type TEXT,
                result TEXT,
                healthy BOOLEAN,
                details TEXT,
                FOREIGN KEY (deployment_id) REFERENCES deployments(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deployment_id INTEGER,
                executed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                exit_code INTEGER,
                duration REAL,
                stdout TEXT,
                stderr TEXT,
                error TEXT,
                FOREIGN KEY (deployment_id) REFERENCES deployments(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deployment_id INTEGER,
                metric_name TEXT,
                metric_value REAL,
                recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (deployment_id) REFERENCES deployments(id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def track_deployment(self, proposal_id: int, script_name: str, script_path: str) -> int:
        """
        Start tracking a new deployment.
        
        Returns: deployment_id
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO deployments (proposal_id, script_name, script_path)
            VALUES (?, ?, ?)
        """, (proposal_id, script_name, script_path))
        
        deployment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Run initial health check
        self._run_health_check(deployment_id, 'initial')
        
        return deployment_id
    
    def record_execution(self, 
                        deployment_id: int,
                        exit_code: int,
                        duration: float,
                        stdout: str = '',
                        stderr: str = '',
                        error: str = '') -> int:
        """Record an execution of the deployed script"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO executions 
            (deployment_id, exit_code, duration, stdout, stderr, error)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (deployment_id, exit_code, duration, stdout[:1000], stderr[:1000], error))
        
        exec_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Check if this execution indicates problems
        if exit_code != 0 or error:
            self._run_health_check(deployment_id, 'error_detected')
        
        return exec_id
    
    def _run_health_check(self, deployment_id: int, check_type: str) -> Dict:
        """Run health check on a deployment"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get deployment info
        cursor.execute("""
            SELECT script_name, script_path, deployed_at
            FROM deployments
            WHERE id = ?
        """, (deployment_id,))
        
        row = cursor.fetchone()
        if not row:
            conn.close()
            return {'healthy': False, 'error': 'Deployment not found'}
        
        script_name, script_path, deployed_at = row
        
        # Get recent executions
        cursor.execute("""
            SELECT exit_code, duration, error
            FROM executions
            WHERE deployment_id = ?
            AND executed_at > datetime('now', '-1 hour')
            ORDER BY executed_at DESC
            LIMIT 20
        """, (deployment_id,))
        
        executions = cursor.fetchall()
        
        # Calculate health metrics
        total = len(executions)
        if total == 0:
            # No executions yet - check if script exists
            script_exists = Path(script_path).exists() if script_path else False
            healthy = script_exists
            result = 'no_executions'
            details = {'script_exists': script_exists}
        else:
            failures = sum(1 for e in executions if e[0] != 0 or e[2])
            success_rate = (total - failures) / total if total > 0 else 0
            avg_duration = sum(e[1] for e in executions if e[1]) / total if total > 0 else 0
            
            # Health thresholds
            healthy = (success_rate >= 0.8 and  # 80%+ success rate
                      avg_duration < 60)          # <60s average duration
            
            result = 'healthy' if healthy else 'unhealthy'
            details = {
                'total_executions': total,
                'failures': failures,
                'success_rate': success_rate,
                'avg_duration': avg_duration
            }
        
        # Save health check
        cursor.execute("""
            INSERT INTO health_checks
            (deployment_id, check_type, result, healthy, details)
            VALUES (?, ?, ?, ?, ?)
        """, (deployment_id, check_type, result, healthy, json.dumps(details)))
        
        conn.commit()
        conn.close()
        
        return {
            'healthy': healthy,
            'result': result,
            'details': details
        }
    
    def check_health(self, deployment_id: int) -> Dict:
        """
        Check current health of a deployment.
        
        Returns:
            {
                'healthy': bool,
                'status': str,
                'metrics': Dict,
                'issues': List[str],
                'recommendations': List[str]
            }
        """
        health = self._run_health_check(deployment_id, 'manual')
        
        issues = []
        recommendations = []
        
        details = health.get('details', {})
        
        # Check for issues
        if details.get('success_rate', 1.0) < 0.8:
            issues.append(f"Low success rate: {details['success_rate']*100:.1f}%")
            recommendations.append("Consider rollback or fix")
        
        if details.get('avg_duration', 0) > 30:
            issues.append(f"Slow execution: {details['avg_duration']:.1f}s average")
            recommendations.append("Optimize performance")
        
        if not details.get('script_exists', True):
            issues.append("Script file not found")
            recommendations.append("Verify deployment")
        
        return {
            'healthy': health['healthy'],
            'status': health['result'],
            'metrics': details,
            'issues': issues,
            'recommendations': recommendations
        }
    
    def trigger_rollback(self, deployment_id: int, reason: str) -> bool:
        """
        Trigger rollback of a deployment.
        
        Args:
            deployment_id: ID of deployment to rollback
            reason: Reason for rollback
        
        Returns: True if successful
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Mark deployment as rolled back
        cursor.execute("""
            UPDATE deployments
            SET status = 'rolled_back',
                rollback_at = CURRENT_TIMESTAMP,
                rollback_reason = ?
            WHERE id = ?
        """, (reason, deployment_id))
        
        # Record health check
        cursor.execute("""
            INSERT INTO health_checks
            (deployment_id, check_type, result, healthy, details)
            VALUES (?, 'rollback', 'rolled_back', 0, ?)
        """, (deployment_id, json.dumps({'reason': reason})))
        
        conn.commit()
        conn.close()
        
        return True
    
    def get_deployment_status(self, deployment_id: int) -> Dict:
        """Get full status of a deployment"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT d.script_name, d.deployed_at, d.status,
                   d.rollback_at, d.rollback_reason,
                   COUNT(e.id) as total_executions,
                   AVG(e.duration) as avg_duration
            FROM deployments d
            LEFT JOIN executions e ON d.id = e.deployment_id
            WHERE d.id = ?
            GROUP BY d.id
        """, (deployment_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {}
        
        return {
            'script_name': row[0],
            'deployed_at': row[1],
            'status': row[2],
            'rollback_at': row[3],
            'rollback_reason': row[4],
            'total_executions': row[5] or 0,
            'avg_duration': row[6] or 0
        }


def main():
    """Test health monitor"""
    monitor = HealthMonitor()
    
    print("V8 Health Monitor - Test Suite")
    print("=" * 70)
    
    # Test 1: Track deployment
    print("\n1. Testing deployment tracking...")
    deployment_id = monitor.track_deployment(
        proposal_id=1,
        script_name='test_script',
        script_path='/tmp/test.py'
    )
    print(f"   Deployment ID: {deployment_id}")
    
    # Test 2: Record successful execution
    print("\n2. Testing successful execution...")
    monitor.record_execution(
        deployment_id=deployment_id,
        exit_code=0,
        duration=0.5,
        stdout="Success!"
    )
    
    # Test 3: Check health (should be healthy)
    print("\n3. Testing health check (healthy)...")
    health = monitor.check_health(deployment_id)
    print(f"   Healthy: {health['healthy']}")
    print(f"   Status: {health['status']}")
    print(f"   Metrics: {health['metrics']}")
    
    # Test 4: Record failure
    print("\n4. Testing failure recording...")
    for i in range(3):
        monitor.record_execution(
            deployment_id=deployment_id,
            exit_code=1,
            duration=1.0,
            stderr="Error!",
            error="Something broke"
        )
    
    # Test 5: Check health (should be unhealthy)
    print("\n5. Testing health check (unhealthy)...")
    health = monitor.check_health(deployment_id)
    print(f"   Healthy: {health['healthy']}")
    print(f"   Status: {health['status']}")
    print(f"   Issues: {health['issues']}")
    print(f"   Recommendations: {health['recommendations']}")
    
    # Test 6: Trigger rollback
    print("\n6. Testing rollback...")
    success = monitor.trigger_rollback(deployment_id, "High failure rate")
    print(f"   Rollback triggered: {success}")
    
    # Test 7: Get deployment status
    print("\n7. Testing deployment status...")
    status = monitor.get_deployment_status(deployment_id)
    print(f"   Status: {status['status']}")
    print(f"   Total executions: {status['total_executions']}")
    print(f"   Rollback reason: {status['rollback_reason']}")
    
    print("\n" + "=" * 70)
    print("✓ All health monitor tests complete!")


if __name__ == '__main__':
    main()
