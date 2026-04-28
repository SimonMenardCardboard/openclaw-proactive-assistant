#!/usr/bin/env python3
"""
Proactive Coordinator - Master daemon that orchestrates all proactive checks
Runs different checks on different schedules for optimal balance
"""

import time
import logging
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from proactive_queue import ProactiveQueue

# Import all proactive modules
try:
    from proactive_calendar import ProactiveCalendar
    CALENDAR_AVAILABLE = True
except ImportError:
    CALENDAR_AVAILABLE = False

try:
    from proactive_email import ProactiveEmail
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

try:
    from proactive_v8_patterns import ProactivePatternRecommendations
    V8_AVAILABLE = True
except ImportError:
    V8_AVAILABLE = False

# Setup logging
log_file = Path.home() / '.openclaw/workspace/logs/proactive_coordinator.log'
log_file.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [COORDINATOR] %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ProactiveCoordinator:
    """
    Coordinates all proactive intelligence checks.
    
    Schedule:
    - Calendar: Every 15 minutes (catches 2-hour and 10-minute windows)
    - Email: Every 30 minutes (important inbox monitoring)
    - V6/V7: Autonomous (they write to queue on their own)
    """
    
    def __init__(self):
        self.queue = ProactiveQueue()
        
        self.calendar = ProactiveCalendar() if CALENDAR_AVAILABLE else None
        self.email = ProactiveEmail() if EMAIL_AVAILABLE else None
        self.v8_patterns = ProactivePatternRecommendations() if V8_AVAILABLE else None
        
        # Track last run times
        self.last_calendar_check = 0
        self.last_email_check = 0
        self.last_pattern_check = 0
        
        logger.info("🎯 Proactive Coordinator initialized")
        logger.info(f"  Calendar: {'✅ Available' if CALENDAR_AVAILABLE else '❌ Not available'}")
        logger.info(f"  Email: {'✅ Available' if EMAIL_AVAILABLE else '❌ Not available'}")
        logger.info(f"  V8 Patterns: {'✅ Available' if V8_AVAILABLE else '❌ Not available'}")
    
    def run_cycle(self):
        """Run one coordination cycle - check what needs to run."""
        now = time.time()
        
        # Calendar check (every 15 minutes = 900 seconds)
        if self.calendar and (now - self.last_calendar_check) >= 900:
            try:
                logger.info("📅 Running calendar check...")
                self.calendar.check_upcoming_events()
                self.last_calendar_check = now
            except Exception as e:
                logger.error(f"❌ Calendar check failed: {e}", exc_info=True)
        
        # Email check (every 30 minutes = 1800 seconds)
        if self.email and (now - self.last_email_check) >= 1800:
            try:
                logger.info("📧 Running email check...")
                self.email.check_inbox(hours_back=1)
                self.last_email_check = now
            except Exception as e:
                logger.error(f"❌ Email check failed: {e}", exc_info=True)
        
        # V8 pattern recommendations (every 4 hours = 14400 seconds)
        if self.v8_patterns and (now - self.last_pattern_check) >= 14400:
            try:
                logger.info("🧠 Running pattern analysis...")
                self.v8_patterns.check_for_recommendations()
                self.last_pattern_check = now
            except Exception as e:
                logger.error(f"❌ Pattern check failed: {e}", exc_info=True)
        
        # Log queue stats
        stats = self.queue.stats()
        logger.debug(f"📊 Queue: {stats['pending']} pending, {stats['delivered']} delivered")
    
    def run(self, check_interval: int = 60):
        """
        Main loop: run checks on schedule.
        
        Args:
            check_interval: How often to wake up and check if anything needs to run (seconds)
        """
        logger.info(f"🔄 Starting coordinator loop (wake every {check_interval}s)")
        
        while True:
            try:
                self.run_cycle()
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                logger.info("🛑 Shutting down...")
                break
            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}", exc_info=True)
                time.sleep(check_interval)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Proactive coordinator daemon')
    parser.add_argument('--interval', type=int, default=60, help='Check interval (seconds)')
    parser.add_argument('--once', action='store_true', help='Run once and exit (for testing)')
    
    args = parser.parse_args()
    
    coordinator = ProactiveCoordinator()
    
    if args.once:
        logger.info("🧪 Running once (test mode)")
        coordinator.run_cycle()
        stats = coordinator.queue.stats()
        print(f"\n✅ Test complete")
        print(f"📊 Queue: {stats['pending']} pending, {stats['delivered']} delivered")
    else:
        coordinator.run(check_interval=args.interval)
