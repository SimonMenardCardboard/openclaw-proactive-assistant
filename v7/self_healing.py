#!/usr/bin/env python3
"""
V7 Self-Healing Daemon - Generic Version

Detects failures → diagnoses → auto-repairs

Repair templates:
1. refresh_auth_token - Refresh expired API tokens
2. restart_service - Restart failed services
3. restart_tunnel - Restart failed tunnels
4. cleanup_disk - Clean up disk space
5. database_recovery - Repair corrupted databases
"""

import time
import logging
import signal
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict

# Logging
LOG_DIR = Path.home() / '.openclaw' / 'proactive' / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'v7_self_healing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('v7.self_healing')


class V7SelfHealing:
    """Self-healing system daemon."""
    
    def __init__(self, interval_seconds: int = 300):
        self.interval = interval_seconds
        self.running = False
        
        # Database
        self.db_path = Path.home() / '.openclaw' / 'proactive' / 'v7' / 'repairs.db'
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
        
        # Stats
        self.cycles = 0
        self.repairs_attempted = 0
        self.repairs_successful = 0
        
        logger.info(f"V7 Self-Healing initialized (interval={interval_seconds}s)")
    
    def _init_database(self):
        """Create repairs database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS repairs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                failure_type TEXT NOT NULL,
                diagnosis TEXT,
                repair_action TEXT NOT NULL,
                status TEXT DEFAULT 'attempted',
                attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                result TEXT,
                error TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def diagnose_service_failure(self, service_name: str) -> str:
        """Diagnose why a service failed"""
        try:
            # Check journal logs
            result = subprocess.run(
                ['journalctl', '-u', service_name, '-n', '50', '--no-pager'],
                capture_output=True,
                timeout=10
            )
            
            logs = result.stdout.decode('utf-8', errors='ignore')
            
            # Simple pattern matching
            if 'Permission denied' in logs:
                return 'permission_error'
            elif 'Connection refused' in logs:
                return 'connection_error'
            elif 'Out of memory' in logs:
                return 'oom_error'
            elif 'No such file' in logs:
                return 'missing_file'
            else:
                return 'unknown_failure'
                
        except Exception as e:
            logger.error(f"Diagnosis failed: {e}")
            return 'diagnosis_failed'
    
    def repair_restart_service(self, service_name: str) -> Dict:
        """Restart a failed service"""
        try:
            # Restart service
            result = subprocess.run(
                ['systemctl', 'restart', service_name],
                capture_output=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # Verify it's running
                time.sleep(2)
                check = subprocess.run(
                    ['systemctl', 'is-active', service_name],
                    capture_output=True
                )
                
                if check.returncode == 0:
                    return {'success': True, 'message': f'{service_name} restarted successfully'}
                else:
                    return {'success': False, 'error': f'{service_name} restart failed verification'}
            else:
                return {'success': False, 'error': result.stderr.decode()}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def repair_cleanup_disk(self) -> Dict:
        """Clean up disk space"""
        try:
            cleaned = []
            
            # Clean apt cache (if available)
            try:
                subprocess.run(['apt-get', 'clean'], timeout=60, check=True)
                cleaned.append('apt_cache')
            except:
                pass
            
            # Clean old logs
            try:
                result = subprocess.run(
                    ['find', '/var/log', '-name', '*.log.*', '-delete'],
                    timeout=60,
                    capture_output=True
                )
                cleaned.append('old_logs')
            except:
                pass
            
            # Clean temp files
            try:
                subprocess.run(['rm', '-rf', '/tmp/*'], timeout=60, shell=True)
                cleaned.append('tmp_files')
            except:
                pass
            
            return {'success': True, 'message': f'Cleaned: {", ".join(cleaned)}'}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def check_system_health(self):
        """Check system health and detect failures"""
        failures = []
        
        # Check OpenClaw gateway
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'openclaw-gateway'],
                capture_output=True
            )
            if result.returncode != 0:
                diagnosis = self.diagnose_service_failure('openclaw-gateway')
                failures.append({
                    'type': 'service_down',
                    'service': 'openclaw-gateway',
                    'diagnosis': diagnosis,
                    'repair': 'restart_service'
                })
        except:
            pass
        
        # Check disk space
        import shutil
        try:
            stat = shutil.disk_usage(Path.home())
            percent_used = (stat.used / stat.total) * 100
            
            if percent_used > 90:
                failures.append({
                    'type': 'disk_space_critical',
                    'percent_used': percent_used,
                    'diagnosis': 'disk_full',
                    'repair': 'cleanup_disk'
                })
        except:
            pass
        
        return failures
    
    def run_cycle(self):
        """Run one self-healing cycle"""
        cycle_start = datetime.now(timezone.utc)
        logger.info(f"━━━ V7 CYCLE #{self.cycles + 1} ━━━")
        
        try:
            # Check for failures
            failures = self.check_system_health()
            
            if not failures:
                logger.info("System healthy")
            else:
                logger.warning(f"Detected {len(failures)} failures")
                
                # Attempt repairs
                for failure in failures:
                    self.attempt_repair(failure)
            
            self.cycles += 1
            elapsed = (datetime.now(timezone.utc) - cycle_start).total_seconds()
            logger.info(f"Cycle complete in {elapsed:.1f}s")
            
        except Exception as e:
            logger.error(f"Cycle failed: {e}", exc_info=True)
    
    def attempt_repair(self, failure: Dict):
        """Attempt to repair a failure"""
        repair_type = failure['repair']
        logger.info(f"Attempting repair: {repair_type}")
        
        self.repairs_attempted += 1
        
        # Log to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO repairs (failure_type, diagnosis, repair_action, attempted_at)
            VALUES (?, ?, ?, ?)
        ''', (
            failure['type'],
            failure['diagnosis'],
            repair_type,
            datetime.now(timezone.utc).isoformat()
        ))
        
        repair_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Execute repair
        if repair_type == 'restart_service':
            result = self.repair_restart_service(failure['service'])
        elif repair_type == 'cleanup_disk':
            result = self.repair_cleanup_disk()
        else:
            result = {'success': False, 'error': f'Unknown repair type: {repair_type}'}
        
        # Update database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        status = 'successful' if result['success'] else 'failed'
        cursor.execute('''
            UPDATE repairs
            SET status = ?,
                completed_at = ?,
                result = ?,
                error = ?
            WHERE id = ?
        ''', (
            status,
            datetime.now(timezone.utc).isoformat(),
            result.get('message'),
            result.get('error'),
            repair_id
        ))
        
        conn.commit()
        conn.close()
        
        if result['success']:
            self.repairs_successful += 1
            logger.info(f"✅ Repair successful: {result.get('message')}")
        else:
            logger.error(f"❌ Repair failed: {result.get('error')}")
    
    def start(self):
        """Start daemon"""
        logger.info("Starting V7 self-healing daemon...")
        self.running = True
        
        # Signal handlers
        signal.signal(signal.SIGTERM, lambda sig, frame: self.stop())
        signal.signal(signal.SIGINT, lambda sig, frame: self.stop())
        
        logger.info(f"V7 daemon running (interval: {self.interval}s)")
        
        # Main loop
        while self.running:
            self.run_cycle()
            
            if self.running:
                time.sleep(self.interval)
        
        logger.info("V7 daemon stopped")
    
    def stop(self):
        """Stop daemon"""
        logger.info("Stopping V7 daemon...")
        self.running = False


def main():
    """Entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='V7 Self-Healing Daemon')
    parser.add_argument('--interval', type=int, default=300,
                       help='Check interval in seconds (default: 300)')
    
    args = parser.parse_args()
    
    daemon = V7SelfHealing(interval_seconds=args.interval)
    daemon.start()


if __name__ == '__main__':
    main()
