#!/usr/bin/env python3
"""
Shared Direct Telegram Notifier
Bypasses OpenClaw Gateway to avoid stuck processes

Used by:
- V6 Proactive Daemon
- V7 Self-Healing Daemon
- V8 Meta-Learning
- Approval Handler
- All notification systems
"""

import requests
import logging
import os
import json
from typing import Dict, List, Optional
from pathlib import Path

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
    
    def _get_bot_token(self) -> Optional[str]:
        """Get Telegram bot token from environment or OpenClaw config"""
        # Try environment variable first
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        if token:
            return token
        
        # Try OpenClaw config (multiple possible locations)
        config_paths = [
            Path.home() / '.openclaw/config/config.json',
            Path.home() / '.openclaw/gateway/config.json',
            Path('/usr/local/lib/node_modules/openclaw/config/config.json'),
        ]
        
        for config_path in config_paths:
            try:
                if config_path.exists():
                    with open(config_path) as f:
                        config = json.load(f)
                        
                        # Try multiple config paths
                        token = (
                            config.get('telegram', {}).get('botToken') or
                            config.get('telegram', {}).get('bot_token') or
                            config.get('channels', {}).get('telegram', {}).get('botToken') or
                            config.get('channels', {}).get('telegram', {}).get('token')
                        )
                        
                        if token:
                            logger.debug(f"Found bot token in {config_path}")
                            return token
            except Exception as e:
                logger.debug(f"Could not load config from {config_path}: {e}")
        
        # Try environment file
        env_path = Path.home() / '.openclaw/.env'
        if env_path.exists():
            try:
                with open(env_path) as f:
                    for line in f:
                        if line.startswith('TELEGRAM_BOT_TOKEN='):
                            return line.split('=', 1)[1].strip().strip('"\'')
            except Exception as e:
                logger.debug(f"Could not load .env: {e}")
        
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
    
    def send_text(self, message: str) -> bool:
        """Send plain text message"""
        return self.send({'message': message})
    
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


# Simple function interface for scripts
def send_telegram_message(message: str, chat_id: str = '8451730454') -> bool:
    """Simple function to send a Telegram message"""
    notifier = TelegramNotifier(telegram_id=chat_id)
    return notifier.send_text(message)
