#!/usr/bin/env python3
"""
OpenClaw V8 Minimal Daemon

Ultra-simple daemon for production:
- Monitors shell history for patterns
- Logs detected patterns
- No dependencies, no auto-optimization (yet)

This is a foundation - customers can enable full V8 later via upgrade.
"""

import time
import logging
import signal
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

# Logging
LOG_DIR = Path.home() / '.openclaw' / 'v8' / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'v8_daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('v8.minimal')


class V8MinimalDaemon:
    """Minimal V8 daemon - pattern detection only."""
    
    def __init__(self, interval_minutes: int = 30):
        self.interval_seconds = interval_minutes * 60
        self.running = False
        self.db_path = Path.home() / '.openclaw' / 'v8' / 'intelligence.db'
        self.cycles = 0
        
        logger.info(f"V8 Minimal Daemon initialized (interval={interval_minutes}m)")
    
    def check_oauth_configured(self):
        """Check if OAuth credentials are configured"""
        creds_dir = Path.home() / '.openclaw' / 'proactive' / 'credentials'
        token_file = creds_dir / 'google_token.json'
        return token_file.exists()
    
    def detect_email_patterns(self):
        """Detect patterns in email (if OAuth configured)"""
        if not self.check_oauth_configured():
            return []
        
        try:
            from email_pattern_analyzer_multi import MultiAccountEmailAnalyzer
            analyzer = MultiAccountEmailAnalyzer()
            patterns = analyzer.analyze_patterns()
            return patterns
        except Exception as e:
            logger.debug(f"Email pattern detection failed: {e}")
            return []
    
    def detect_calendar_patterns(self):
        """Detect patterns in calendar (if OAuth configured)"""
        if not self.check_oauth_configured():
            return []
        
        try:
            from multi_account_calendar_analyzer import MultiAccountCalendarAnalyzer
            analyzer = MultiAccountCalendarAnalyzer()
            patterns = analyzer.analyze_patterns()
            return patterns
        except Exception as e:
            logger.debug(f"Calendar pattern detection failed: {e}")
            return []
    
    def detect_shell_patterns(self):
        """Detect patterns in shell history"""
        try:
            history_file = Path.home() / '.zsh_history'
            if not history_file.exists():
                history_file = Path.home() / '.bash_history'
            
            if not history_file.exists():
                logger.debug("No shell history file found")
                return []
            
            # Read last 100 commands
            with open(history_file, 'rb') as f:
                lines = f.readlines()[-100:]
            
            commands = []
            for line in lines:
                try:
                    # Parse zsh history format
                    if b':' in line and b';' in line:
                        cmd = line.split(b';', 1)[1].decode('utf-8', errors='ignore').strip()
                    else:
                        cmd = line.decode('utf-8', errors='ignore').strip()
                    
                    if cmd and not cmd.startswith('#'):
                        commands.append(cmd)
                except:
                    continue
            
            # Find patterns (commands used 3+ times)
            command_counts = Counter(commands)
            patterns = [(cmd, count) for cmd, count in command_counts.items() if count >= 3]
            
            return patterns
            
        except Exception as e:
            logger.error(f"Failed to detect patterns: {e}")
            return []
    
    def save_patterns(self, patterns):
        """Save detected patterns to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for pattern, frequency in patterns:
                cursor.execute('''
                    INSERT OR REPLACE INTO patterns 
                    (pattern_type, pattern_data, frequency, last_seen)
                    VALUES (?, ?, ?, ?)
                ''', ('shell_command', pattern, frequency, datetime.now(timezone.utc).isoformat()))
            
            conn.commit()
            conn.close()
            logger.info(f"Saved {len(patterns)} patterns to database")
            
        except Exception as e:
            logger.error(f"Failed to save patterns: {e}")
    
    def run_cycle(self):
        """Run one learning cycle"""
        cycle_start = datetime.now(timezone.utc)
        logger.info(f"━━━ V8 CYCLE #{self.cycles + 1} ━━━")
        
        try:
            # Detect patterns from multiple sources
            all_patterns = []
            
            # Shell patterns (always enabled)
            shell_patterns = self.detect_shell_patterns()
            all_patterns.extend(shell_patterns)
            
            # Email patterns (if OAuth configured)
            if self.check_oauth_configured():
                email_patterns = self.detect_email_patterns()
                all_patterns.extend(email_patterns)
                
                calendar_patterns = self.detect_calendar_patterns()
                all_patterns.extend(calendar_patterns)
                
                logger.info(f"OAuth enabled: scanned email + calendar")
            
            if all_patterns:
                logger.info(f"Found {len(all_patterns)} patterns:")
                for pattern_item in all_patterns[:5]:  # Show top 5
                    if isinstance(pattern_item, tuple):
                        cmd, count = pattern_item
                        logger.info(f"  {count}× {cmd[:60]}...")
                    else:
                        logger.info(f"  {pattern_item}")
                
                # Save shell patterns (tuple format)
                shell_only = [p for p in all_patterns if isinstance(p, tuple)]
                if shell_only:
                    self.save_patterns(shell_only)
            else:
                logger.info("No patterns detected this cycle")
            
            self.cycles += 1
            elapsed = (datetime.now(timezone.utc) - cycle_start).total_seconds()
            logger.info(f"Cycle complete in {elapsed:.1f}s")
            
        except Exception as e:
            logger.error(f"Cycle failed: {e}", exc_info=True)
    
    def start(self):
        """Start daemon"""
        logger.info("Starting V8 minimal daemon...")
        self.running = True
        
        # Signal handlers
        signal.signal(signal.SIGTERM, lambda sig, frame: self.stop())
        signal.signal(signal.SIGINT, lambda sig, frame: self.stop())
        
        logger.info(f"V8 daemon running (interval: {self.interval_seconds}s)")
        
        # Main loop
        while self.running:
            self.run_cycle()
            
            if self.running:
                logger.info(f"Sleeping {self.interval_seconds}s until next cycle...")
                time.sleep(self.interval_seconds)
        
        logger.info("V8 daemon stopped")
    
    def stop(self):
        """Stop daemon"""
        logger.info("Stopping V8 daemon...")
        self.running = False


def main():
    """Entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='OpenClaw V8 Minimal Daemon')
    parser.add_argument('--interval', type=int, default=30,
                       help='Check interval in minutes (default: 30)')
    
    args = parser.parse_args()
    
    daemon = V8MinimalDaemon(interval_minutes=args.interval)
    daemon.start()


if __name__ == '__main__':
    main()
