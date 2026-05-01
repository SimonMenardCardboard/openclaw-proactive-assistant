#!/usr/bin/env python3
"""
Universal Notifier - Supports multiple notification backends

Modes:
1. Telegram Bot API (for Hobbes Prime / personal use)
2. In-App Notifications (for Transmogrifier customers)
3. Push Notifications (APNs/FCM for mobile apps)

Auto-detects mode based on:
- Environment variables (NOTIFICATION_MODE)
- Config files
- Available credentials
"""

import requests
import logging
import os
import json
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class UniversalNotifier:
    """Send notifications via multiple backends"""
    
    def __init__(self, user_id: str = '8451730454', min_confidence: float = 0.75):
        self.user_id = user_id
        self.min_confidence = min_confidence
        
        # Detect notification mode
        self.mode = self._detect_mode()
        
        # Initialize backend
        if self.mode == 'telegram':
            self._init_telegram()
        elif self.mode == 'in_app':
            self._init_in_app()
        elif self.mode == 'push':
            self._init_push()
        else:
            logger.warning(f"Unknown notification mode: {self.mode}")
            self.api_url = None
    
    def _detect_mode(self) -> str:
        """Auto-detect which notification backend to use"""
        # Explicit mode from environment
        explicit_mode = os.getenv('NOTIFICATION_MODE')
        if explicit_mode:
            return explicit_mode.lower()
        
        # Check for Telegram bot token
        if os.getenv('TELEGRAM_BOT_TOKEN'):
            return 'telegram'
        
        # Check for in-app notification database
        in_app_db = Path.home() / '.transmogrifier/notifications.db'
        if in_app_db.exists():
            return 'in_app'
        
        # Check for push notification credentials
        if os.getenv('APNS_KEY_PATH') or os.getenv('FCM_SERVER_KEY'):
            return 'push'
        
        # Check config files
        try:
            config_path = Path.home() / '.openclaw/config/config.json'
            if config_path.exists():
                with open(config_path) as f:
                    config = json.load(f)
                    if config.get('channels', {}).get('telegram', {}).get('botToken'):
                        return 'telegram'
        except:
            pass
        
        # Default to in-app for Transmogrifier
        return 'in_app'
    
    def _init_telegram(self):
        """Initialize Telegram Bot API"""
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not token:
            # Try config files
            config_paths = [
                Path.home() / '.openclaw/config/config.json',
                Path.home() / '.openclaw/.env',
            ]
            
            for config_path in config_paths:
                if config_path.suffix == '.env' and config_path.exists():
                    with open(config_path) as f:
                        for line in f:
                            if line.startswith('TELEGRAM_BOT_TOKEN='):
                                token = line.split('=', 1)[1].strip().strip('"\'')
                                break
        
        if token:
            self.api_url = f"https://api.telegram.org/bot{token}"
            logger.info(f"Telegram notifier initialized (direct API)")
        else:
            logger.warning("Telegram bot token not found - notifications disabled")
            self.api_url = None
    
    def _init_in_app(self):
        """Initialize in-app notification system (Transmogrifier)"""
        # In-app notifications write to local database
        # The mobile/desktop app polls this database
        self.notifications_db = Path.home() / '.transmogrifier/notifications.db'
        self.notifications_db.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize SQLite database
        import sqlite3
        conn = sqlite3.connect(self.notifications_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                title TEXT,
                message TEXT NOT NULL,
                priority INTEGER DEFAULT 3,
                delivered BOOLEAN DEFAULT 0,
                read BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        
        self.api_url = str(self.notifications_db)
        logger.info(f"In-app notifier initialized: {self.notifications_db}")
    
    def _init_push(self):
        """Initialize push notifications (APNs/FCM)"""
        # For future: push notifications to mobile devices
        logger.info("Push notification support coming soon")
        self.api_url = None
    
    def send(self, observation: Dict) -> bool:
        """Send notification via active backend"""
        message = observation.get('message', str(observation))
        
        if self.mode == 'telegram':
            return self._send_telegram(message)
        elif self.mode == 'in_app':
            return self._send_in_app(message, observation)
        elif self.mode == 'push':
            return self._send_push(message, observation)
        else:
            logger.warning(f"Cannot send notification - no backend configured")
            return False
    
    def _send_telegram(self, message: str) -> bool:
        """Send via Telegram Bot API"""
        if not self.api_url:
            return False
        
        try:
            response = requests.post(
                f"{self.api_url}/sendMessage",
                json={
                    'chat_id': self.user_id,
                    'text': message,
                    'parse_mode': 'Markdown',
                    'disable_web_page_preview': True
                },
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"✓ Telegram message sent")
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Telegram error: {e}")
            return False
    
    def _send_in_app(self, message: str, observation: Dict) -> bool:
        """Send via in-app notification database"""
        try:
            import sqlite3
            from datetime import datetime
            
            conn = sqlite3.connect(self.notifications_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO notifications (user_id, title, message, priority, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                self.user_id,
                observation.get('title', 'Notification'),
                message,
                observation.get('priority', 3),
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✓ In-app notification queued")
            return True
        except Exception as e:
            logger.error(f"In-app notification error: {e}")
            return False
    
    def _send_push(self, message: str, observation: Dict) -> bool:
        """Send via push notifications (APNs/FCM)"""
        # Future implementation
        logger.warning("Push notifications not yet implemented")
        return False
    
    def send_batch(self, observations: List[Dict]) -> int:
        """Send multiple notifications"""
        sent_count = 0
        for obs in observations:
            if self.send(obs):
                sent_count += 1
        return sent_count
    
    def send_text(self, message: str) -> bool:
        """Send plain text message"""
        return self.send({'message': message})


# Alias for backward compatibility
TelegramNotifier = UniversalNotifier


def send_notification(message: str, user_id: str = None) -> bool:
    """Simple function to send a notification"""
    notifier = UniversalNotifier(user_id=user_id or '8451730454')
    return notifier.send_text(message)
