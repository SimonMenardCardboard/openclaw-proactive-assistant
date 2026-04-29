#!/usr/bin/env python3
"""
System Message Logger
Processes non-user-facing messages from proactive queue and writes to log file.
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from proactive_queue import ProactiveQueue

# Setup logging
log_file = Path.home() / '.openclaw/workspace/logs/system_queue.log'
log_file.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)-8s] [%(source)-15s] %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('system_queue')


class SystemLogger:
    """Writes system messages to structured log file."""
    
    def __init__(self, interval: int = 60):
        self.queue = ProactiveQueue()
        self.interval = interval
        self.running = False
        
        logger.info("✅ System logger started")
    
    def process_pending(self):
        """Process system messages to log file."""
        
        # Get only system messages (user_facing = 0)
        pending = self.queue.get_system_pending(limit=100)
        
        if not pending:
            return
        
        logger.info(f"📝 Processing {len(pending)} system message(s)")
        
        for rec in pending:
            # Map priority to log level
            priority = rec['priority']
            source = rec['source']
            message = rec['message']
            
            # Create structured log entry
            extra = {'source': source}
            
            if priority == 1:
                logger.critical(message, extra=extra)
            elif priority == 2:
                logger.error(message, extra=extra)
            elif priority == 3:
                logger.warning(message, extra=extra)
            else:
                logger.info(message, extra=extra)
            
            # Mark as delivered
            self.queue.mark_delivered(rec['id'])
        
        logger.info(f"✅ Logged {len(pending)} system message(s)")
    
    def run(self):
        """Main loop: process system messages every interval."""
        self.running = True
        logger.info(f"🔄 System logger loop started (every {self.interval}s)")
        
        while self.running:
            try:
                self.process_pending()
                time.sleep(self.interval)
                
            except KeyboardInterrupt:
                logger.info("🛑 Shutting down...")
                self.running = False
                break
            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}", exc_info=True)
                time.sleep(self.interval)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='System message logger')
    parser.add_argument('--interval', type=int, default=60, help='Check interval (seconds)')
    
    args = parser.parse_args()
    
    system_logger = SystemLogger(interval=args.interval)
    system_logger.run()
