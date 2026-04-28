#!/usr/bin/env python3
"""
Proactive Telegram Notifier - Production version using direct Telegram Bot API
Polls proactive_queue and delivers autonomously
"""

import sys
import time
import requests
import json
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
    """Delivers proactive recommendations via Telegram Bot API."""
    
    def __init__(self, bot_token: str, chat_id: str, interval: int = 30):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.interval = interval
        self.queue = ProactiveQueue()
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        logger.info(f"✅ Telegram notifier started (chat_id: {chat_id}, interval: {interval}s)")
    
    def send_message(self, message: str) -> bool:
        """Send message via Telegram Bot API."""
        try:
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }
            
            response = requests.post(self.api_url, json=payload, timeout=10)
            
            if response.status_code == 200 and response.json().get('ok'):
                logger.info(f"✅ Message delivered: {message[:50]}...")
                return True
            else:
                logger.error(f"❌ Telegram API error: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Send failed: {e}")
            return False
    
    def process_pending(self):
        """Process all pending recommendations."""
        pending = self.queue.get_pending(limit=5)
        
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
                logger.error(f"❌ Error in main loop: {e}", exc_info=True)
                time.sleep(self.interval)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Proactive Telegram notifier')
    parser.add_argument('--bot-token', required=True, help='Telegram bot token')
    parser.add_argument('--chat-id', required=True, help='Telegram chat ID')
    parser.add_argument('--interval', type=int, default=30, help='Poll interval (seconds)')
    
    args = parser.parse_args()
    
    notifier = TelegramNotifier(
        bot_token=args.bot_token,
        chat_id=args.chat_id,
        interval=args.interval
    )
    
    notifier.run()
