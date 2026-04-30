#!/usr/bin/env python3
"""
Proactive Telegram Notifier - Production version via OpenClaw Gateway
Polls proactive_queue and delivers autonomously via openclaw message send
"""

import sys
import time
import subprocess
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from proactive_queue import ProactiveQueue

# Setup logging
log_file = Path.home() / '.openclaw/workspace/logs/proactive_telegram.log'
log_file.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [PROACTIVE-TG] %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Delivers proactive recommendations via OpenClaw Gateway."""
    
    def __init__(self, chat_id: str, interval: int = 30):
        self.chat_id = chat_id
        self.interval = interval
        self.queue = ProactiveQueue()
        
        logger.info(f"✅ Telegram notifier started (chat_id: {chat_id}, interval: {interval}s)")
        logger.info(f"📡 Routing through OpenClaw Gateway (no direct Telegram API)")
    
    def send_message(self, message: str) -> bool:
        """Send message via OpenClaw Gateway to maintain proper message ordering."""
        try:
            # Use openclaw message send instead of direct Telegram API
            cmd = ['/usr/local/bin/openclaw', 'message', 'send']
            cmd.extend(['--target', self.chat_id])
            cmd.extend(['--message', message])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"✅ Message delivered via Gateway: {message[:50]}...")
                return True
            else:
                logger.error(f"❌ Gateway send failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Send failed: {e}")
            return False
    
    def process_pending(self):
        """Process only user-facing pending recommendations."""
        pending = self.queue.get_user_facing_pending(limit=5)
        
        if not pending:
            logger.debug("No pending recommendations")
            return
        
        logger.info(f"📬 Processing {len(pending)} pending recommendation(s)")
        
        for rec in pending:
            # Use message as-is (no priority emoji prefix, no source attribution)
            message = rec['message']
            
            if self.send_message(message):
                self.queue.mark_delivered(rec['id'])
                logger.info(f"✅ Delivered #{rec['id']}")
                time.sleep(2)  # Rate limit: max 1 message per 2 seconds
            else:
                logger.warning(f"⚠️  Failed to deliver #{rec['id']}, will retry")
                break  # Stop processing on failure
    
    def run(self):
        """Main loop: poll and deliver."""
        logger.info(f"🔄 Poll loop started (every {self.interval}s)")
        
        while True:
            try:
                self.process_pending()
                time.sleep(self.interval)
                
            except KeyboardInterrupt:
                logger.info("🛑 Shutting down...")
                break
            
            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}")
                time.sleep(10)  # Back off on errors


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Proactive Telegram Notifier (via OpenClaw Gateway)')
    parser.add_argument('--chat-id', required=True, help='Telegram chat ID')
    parser.add_argument('--interval', type=int, default=30, help='Poll interval in seconds')
    
    args = parser.parse_args()
    
    notifier = TelegramNotifier(
        chat_id=args.chat_id,
        interval=args.interval
    )
    
    notifier.run()
