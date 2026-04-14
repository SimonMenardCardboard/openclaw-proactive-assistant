#!/usr/bin/env python3
"""
V6 Proactive Daemon - Generic Version

Monitors system health and submits autonomous actions:
- Auth token expiry
- Service health
- System resources

NO personal integrations (WHOOP, forms, etc.)
"""

import time
import logging
import signal
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from executor import AutonomousExecutor

# Logging
LOG_DIR = Path.home() / '.openclaw' / 'proactive' / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'v6_daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('v6.daemon')


class V6ProactiveDaemon:
    """Generic proactive monitoring daemon."""
    
    def __init__(self, interval_seconds: int = 60):
        self.interval = interval_seconds
        self.running = False
        
        # Database
        self.db_path = Path.home() / '.openclaw' / 'proactive' / 'v6' / 'execution_log.db'
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Executor
        executor_log = LOG_DIR / 'executor.log'
        self.executor = AutonomousExecutor(self.db_path, executor_log)
        
        # Stats
        self.cycles = 0
        self.actions_submitted = 0
        
        logger.info(f"V6 Daemon initialized (interval={interval_seconds}s)")
    
    def check_auth_tokens(self):
        """Check for expired auth tokens"""
        # Check OpenClaw tokens
        config_dir = Path.home() / '.openclaw'
        if not config_dir.exists():
            return []
        
        issues = []
        
        # Check for token files that might be expired
        # This is a placeholder - actual implementation would check token expiry
        logger.debug("Checking auth tokens...")
        
        return issues
    
    def check_services(self):
        """Check critical services are running"""
        import subprocess
        
        issues = []
        
        # Check OpenClaw gateway
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'openclaw.*gateway'],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                issues.append({
                    'type': 'service_down',
                    'service': 'openclaw-gateway',
                    'action': 'restart_service'
                })
                logger.warning("OpenClaw gateway not running")
        except Exception as e:
            logger.error(f"Failed to check service: {e}")
        
        return issues
    
    def check_disk_space(self):
        """Check disk space"""
        import shutil
        
        issues = []
        
        try:
            stat = shutil.disk_usage(Path.home())
            percent_used = (stat.used / stat.total) * 100
            
            if percent_used > 90:
                issues.append({
                    'type': 'disk_space_low',
                    'percent_used': percent_used,
                    'action': 'cleanup_disk'
                })
                logger.warning(f"Disk space {percent_used:.1f}% used")
        except Exception as e:
            logger.error(f"Failed to check disk: {e}")
        
        return issues
    
    def run_cycle(self):
        """Run one monitoring cycle"""
        cycle_start = datetime.now(timezone.utc)
        logger.info(f"━━━ V6 CYCLE #{self.cycles + 1} ━━━")
        
        try:
            # Run checks
            issues = []
            issues.extend(self.check_auth_tokens())
            issues.extend(self.check_services())
            issues.extend(self.check_disk_space())
            
            # Submit actions for issues
            for issue in issues:
                action_type = issue['action']
                logger.info(f"Submitting action: {action_type}")
                self.executor.submit_action(action_type, issue)
                self.actions_submitted += 1
            
            if not issues:
                logger.info("No issues detected")
            
            self.cycles += 1
            elapsed = (datetime.now(timezone.utc) - cycle_start).total_seconds()
            logger.info(f"Cycle complete in {elapsed:.1f}s")
            
        except Exception as e:
            logger.error(f"Cycle failed: {e}", exc_info=True)
    
    def start(self):
        """Start daemon"""
        logger.info("Starting V6 daemon...")
        self.running = True
        
        # Signal handlers
        signal.signal(signal.SIGTERM, lambda sig, frame: self.stop())
        signal.signal(signal.SIGINT, lambda sig, frame: self.stop())
        
        logger.info(f"V6 daemon running (interval: {self.interval}s)")
        
        # Start executor in background
        import threading
        executor_thread = threading.Thread(target=self.executor.run, daemon=True)
        executor_thread.start()
        
        # Main loop
        while self.running:
            self.run_cycle()
            
            if self.running:
                time.sleep(self.interval)
        
        logger.info("V6 daemon stopped")
    
    def stop(self):
        """Stop daemon"""
        logger.info("Stopping V6 daemon...")
        self.running = False
        self.executor.stop()


def main():
    """Entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='V6 Proactive Daemon')
    parser.add_argument('--interval', type=int, default=60,
                       help='Check interval in seconds (default: 60)')
    
    args = parser.parse_args()
    
    daemon = V6ProactiveDaemon(interval_seconds=args.interval)
    daemon.start()


if __name__ == '__main__':
    main()
