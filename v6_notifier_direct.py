#!/usr/bin/env python3
"""
Telegram Notifier - Direct Bot API
Bypasses OpenClaw Gateway to avoid stuck processes
"""

import requests
import logging
import os
from typing import Dict, List

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send notifications via direct Telegram Bot API"""
    
    def __init__(self, telegram_id: str = '8451730454', min_confidence: float = 0.75):
        self.telegram_id = telegram_id
        self.chat_id = telegram_id
        self.min_confidence = min_confidence
        
        # Get bot token from environment or config
        self.bot_token = self._get_bot_token()
        
        if self.bot_token:
            self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
            logger.info(f"Telegram notifier initialized (direct API)")
        else:
            logger.warning("No Telegram bot token found - notifications disabled")
            self.api_url = None
    
    def _get_bot_token(self) -> str:
        """Get Telegram bot token from environment or OpenClaw config"""
        # Try environment variable first
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        if token:
            return token
        
        # Try OpenClaw config
        try:
            import json
            from pathlib import Path
            
            config_path = Path.home() / '.openclaw/config/config.json'
            if config_path.exists():
                with open(config_path) as f:
                    config = json.load(f)
                    token = config.get('telegram', {}).get('botToken')
                    if token:
                        return token
        except Exception as e:
            logger.debug(f"Could not load config: {e}")
        
        return None
    
    def send(self, observation: Dict) -> bool:
        """Send single notification via Telegram Bot API"""
        if not self.api_url:
            logger.warning("Telegram bot token not configured, skipping notification")
            return False
        
        message = observation.get('message', str(observation))
        
        try:
            response = requests.post(
                f"{self.api_url}/sendMessage",
                json={
                    'chat_id': self.chat_id,
                    'text': message,
                    'parse_mode': 'Markdown',
                    'disable_web_page_preview': True
                },
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"✓ Message sent to Telegram")
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return False
                
        except requests.Timeout:
            logger.error(f"Telegram API timeout after 10s")
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
        """Send message with inline keyboard"""
        if not self.api_url:
            return {'success': False, 'message_id': None}
        
        try:
            response = requests.post(
                f"{self.api_url}/sendMessage",
                json={
                    'chat_id': self.chat_id,
                    'text': message,
                    'parse_mode': 'Markdown',
                    'reply_markup': keyboard
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'message_id': data['result']['message_id']
                }
            else:
                return {'success': False, 'message_id': None}
                
        except Exception as e:
            logger.error(f"Keyboard message error: {e}")
            return {'success': False, 'message_id': None}
