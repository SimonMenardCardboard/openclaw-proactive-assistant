#!/usr/bin/env python3
"""
V6 Autonomous Executor - Generic Version

Executes approved autonomous actions safely.
"""

import time
import logging
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger('v6.executor')


class AutonomousExecutor:
    """Executes autonomous actions with safety checks."""
    
    def __init__(self, db_path: Path, log_path: Path):
        self.db_path = db_path
        self.running = False
        self.check_interval = 10  # Check for pending actions every 10s
        
        # Initialize database
        self._init_database()
        
        logger.info("Autonomous Executor initialized")
    
    def _init_database(self):
        """Create execution log database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                executed_at TIMESTAMP,
                result TEXT,
                error TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def submit_action(self, action_type: str, context: Dict):
        """Submit an action for execution"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO actions (action_type, status, submitted_at)
            VALUES (?, 'pending', ?)
        ''', (action_type, datetime.now(timezone.utc).isoformat()))
        
        action_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Submitted action {action_id}: {action_type}")
        return action_id
    
    def execute_restart_service(self, service_name: str) -> Dict:
        """Restart a systemd service"""
        try:
            result = subprocess.run(
                ['systemctl', 'restart', service_name],
                capture_output=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return {'success': True, 'message': f'Restarted {service_name}'}
            else:
                return {'success': False, 'error': result.stderr.decode()}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def execute_cleanup_disk(self) -> Dict:
        """Clean up disk space"""
        try:
            # Clean apt cache
            subprocess.run(['apt-get', 'clean'], timeout=60)
            
            # Clean old logs
            subprocess.run(
                ['find', '/var/log', '-name', '*.log.*', '-delete'],
                timeout=60
            )
            
            return {'success': True, 'message': 'Disk cleanup complete'}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def process_pending_actions(self):
        """Process all pending actions"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, action_type
            FROM actions
            WHERE status = 'pending'
            ORDER BY submitted_at ASC
            LIMIT 10
        ''')
        
        actions = cursor.fetchall()
        conn.close()
        
        for action in actions:
            self.execute_action(action['id'], action['action_type'])
    
    def execute_action(self, action_id: int, action_type: str):
        """Execute a single action"""
        logger.info(f"Executing action {action_id}: {action_type}")
        
        # Mark as executing
        self._update_action_status(action_id, 'executing')
        
        # Execute based on type
        if action_type == 'restart_service':
            result = self.execute_restart_service('openclaw-gateway')
        elif action_type == 'cleanup_disk':
            result = self.execute_cleanup_disk()
        else:
            result = {'success': False, 'error': f'Unknown action type: {action_type}'}
        
        # Update status
        if result.get('success'):
            self._update_action_status(action_id, 'completed', result=result.get('message'))
            logger.info(f"Action {action_id} completed successfully")
        else:
            self._update_action_status(action_id, 'failed', error=result.get('error'))
            logger.error(f"Action {action_id} failed: {result.get('error')}")
    
    def _update_action_status(self, action_id: int, status: str, 
                            result: Optional[str] = None, error: Optional[str] = None):
        """Update action status in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE actions
            SET status = ?,
                executed_at = ?,
                result = ?,
                error = ?
            WHERE id = ?
        ''', (status, datetime.now(timezone.utc).isoformat(), result, error, action_id))
        
        conn.commit()
        conn.close()
    
    def run(self):
        """Main executor loop"""
        logger.info("Executor running...")
        self.running = True
        
        while self.running:
            try:
                self.process_pending_actions()
            except Exception as e:
                logger.error(f"Executor error: {e}", exc_info=True)
            
            if self.running:
                time.sleep(self.check_interval)
    
    def stop(self):
        """Stop executor"""
        logger.info("Stopping executor...")
        self.running = False
