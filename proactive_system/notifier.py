#!/usr/bin/env python3
"""
Telegram Notifier - Routes all messages through OpenClaw Gateway
No direct Telegram Bot API calls to prevent message ordering issues
"""

import subprocess
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send notifications via OpenClaw Gateway"""
    
    def __init__(self, telegram_id: str = '8451730454', min_confidence: float = 0.75):
        self.telegram_id = telegram_id
        self.chat_id = telegram_id
        self.min_confidence = min_confidence
        logger.info(f"Telegram notifier initialized (routing through Gateway)")
    
    def send(self, observation: Dict) -> bool:
        """Send single notification via OpenClaw Gateway"""
        message = observation.get('message', str(observation))
        
        try:
            result = subprocess.run([
                '/usr/local/bin/openclaw', 'message', 'send',
                '--target', self.telegram_id,
                '--message', message
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return True
            else:
                logger.error(f"Gateway send failed: {result.stderr}")
                return False
        
        except subprocess.TimeoutExpired:
            logger.error(f"Gateway send timed out after 30s")
            return False
        except Exception as e:
            logger.error(f"Notification error: {e}")
            return False
    
    def send_batch(self, observations: List[Dict]) -> int:
        """Send multiple notifications, return count sent"""
        sent_count = 0
        
        for obs in observations:
            if self.send(obs):
                sent_count += 1
        
        return sent_count
    
    async def send_with_keyboard(self, message: str, keyboard: dict) -> dict:
        """
        Send message with inline keyboard.
        Note: OpenClaw Gateway handles keyboard rendering automatically
        when buttons are detected in the message format.
        """
        # For now, send as plain message
        # OpenClaw Gateway will support --buttons flag in future
        result = subprocess.run([
            '/usr/local/bin/openclaw', 'message', 'send',
            '--target', self.telegram_id,
            '--message', message
        ], capture_output=True, text=True, timeout=30)
        
        return {
            'success': result.returncode == 0,
            'message_id': None
        }
