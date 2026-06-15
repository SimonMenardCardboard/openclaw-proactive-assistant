#!/usr/bin/env python3
"""
VM Push Service - Delivers backend intelligence to mobile/desktop apps
Bridges proactive_queue → FCM/APNs → Transmogrifier apps
"""

import sys
import time
import logging
import json
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Add proactive_system to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'proactive_system'))
from proactive_queue import ProactiveQueue

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PushService:
    """
    Push notification service for Transmogrifier VMs.
    Polls proactive queue and delivers to registered devices.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.queue = ProactiveQueue()
        self.config = self._load_config(config_path)
        self.devices = {}  # {user_id: [device_tokens]} — in-memory cache
        self.devices_db = self._devices_db_path()
        self._ensure_devices_schema()
        self._load_devices_from_db()  # Restore tokens after restart

    def _devices_db_path(self) -> Path:
        import os
        home = os.environ.get(
            'TRANSMOGRIFIER_HOME',
            str(Path.home() / '.openclaw/workspace/integrations/intelligence')
        )
        return Path(home) / 'device_tokens.db'

    def _ensure_devices_schema(self):
        import sqlite3
        conn = sqlite3.connect(self.devices_db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS device_tokens (
                user_id TEXT NOT NULL,
                token TEXT NOT NULL,
                platform TEXT NOT NULL,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, token)
            )
        """)
        conn.commit()
        conn.close()

    def _load_devices_from_db(self):
        import sqlite3
        conn = sqlite3.connect(self.devices_db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT user_id, token, platform, registered_at FROM device_tokens").fetchall()
        conn.close()
        for row in rows:
            uid = row['user_id']
            if uid not in self.devices:
                self.devices[uid] = []
            self.devices[uid].append({
                'token': row['token'],
                'platform': row['platform'],
                'registered_at': row['registered_at']
            })
        if self.devices:
            total = sum(len(v) for v in self.devices.values())
            logger.info(f"Loaded {total} device token(s) from DB across {len(self.devices)} user(s)")
    
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load push service configuration."""
        if config_path and Path(config_path).exists():
            with open(config_path) as f:
                return json.load(f)
        
        # Default config
        return {
            'fcm_server_key': None,  # Firebase Cloud Messaging
            'apns_key_id': None,     # Apple Push Notification Service
            'apns_team_id': None,
            'poll_interval': 30,      # Check queue every 30 seconds
            'batch_size': 10,         # Process 10 notifications per cycle
        }
    
    def register_device(self, user_id: str, device_token: str, platform: str):
        """
        Register a device for push notifications.
        Called by mobile/desktop app after login.
        """
        if user_id not in self.devices:
            self.devices[user_id] = []
        
        device = {
            'token': device_token,
            'platform': platform,  # 'ios', 'android', 'desktop'
            'registered_at': datetime.now().isoformat()
        }
        
        # Avoid duplicates
        existing = [d for d in self.devices[user_id] if d['token'] == device_token]
        if not existing:
            self.devices[user_id].append(device)
            # Persist to DB so tokens survive VM restart
            import sqlite3
            conn = sqlite3.connect(self.devices_db)
            conn.execute("""
                INSERT OR REPLACE INTO device_tokens (user_id, token, platform)
                VALUES (?, ?, ?)
            """, (user_id, device_token, platform))
            conn.commit()
            conn.close()
            logger.info(f"Registered {platform} device for {user_id} (persisted)")

    def unregister_device(self, user_id: str, device_token: str):
        """Remove device registration."""
        if user_id in self.devices:
            self.devices[user_id] = [d for d in self.devices[user_id] if d['token'] != device_token]
            import sqlite3
            conn = sqlite3.connect(self.devices_db)
            conn.execute("DELETE FROM device_tokens WHERE user_id = ? AND token = ?",
                         (user_id, device_token))
            conn.commit()
            conn.close()
            logger.info(f"Unregistered device for {user_id}")
    
    def format_notification(self, queue_item: Dict) -> Dict:
        """
        Format proactive queue item as push notification.
        
        Extracts:
        - Title (first line of message)
        - Body (remaining message)
        - Actions (if present)
        - Priority
        """
        message = queue_item['message']
        lines = message.split('\n')
        
        # Extract title (first line, strip markdown)
        title = lines[0].strip('*#').strip()
        
        # Extract body (remaining lines)
        body = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ''
        
        # Truncate body for preview
        if len(body) > 200:
            body = body[:197] + '...'
        
        return {
            'title': title,
            'body': body,
            'data': {
                'type': queue_item['source'],
                'priority': queue_item['priority'],
                'queue_id': queue_item['id'],
                'timestamp': queue_item['created_at'],
                'full_message': message  # For app to expand
            }
        }
    
    def send_fcm(self, device_token: str, notification: Dict) -> bool:
        """Send via Firebase Cloud Messaging (Android + iOS)."""
        if not self.config['fcm_server_key']:
            logger.warning("FCM not configured - skipping FCM delivery")
            return False
        
        try:
            url = 'https://fcm.googleapis.com/fcm/send'
            headers = {
                'Authorization': f'key={self.config["fcm_server_key"]}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'to': device_token,
                'notification': {
                    'title': notification['title'],
                    'body': notification['body']
                },
                'data': notification['data'],
                'priority': 'high' if notification['data']['priority'] <= 2 else 'normal'
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"FCM sent successfully")
                return True
            else:
                logger.error(f"FCM failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"FCM error: {e}")
            return False
    
    def send_apns(self, device_token: str, notification: Dict) -> bool:
        """Send via Apple Push Notification Service (iOS)."""
        if not self.config['apns_key_id']:
            logger.warning("APNs not configured - skipping APNs delivery")
            return False
        
        # TODO: Implement APNs with proper JWT auth
        # For now, log and return success (will add in production)
        logger.info(f"APNs: Would send to {device_token[:10]}...")
        return True
    
    def send_desktop_websocket(self, user_id: str, notification: Dict) -> bool:
        """Send via WebSocket to desktop app."""
        # Desktop apps maintain WebSocket connection to VM
        # For now, log (will implement WebSocket server)
        logger.info(f"WebSocket: Would send to desktop for {user_id}")
        return True
    
    def deliver_to_user(self, user_id: str, notification: Dict) -> int:
        """
        Deliver notification to all user's devices.
        Returns number of successful deliveries.
        """
        if user_id not in self.devices or not self.devices[user_id]:
            logger.warning(f"No devices registered for {user_id}")
            return 0
        
        delivered = 0
        
        for device in self.devices[user_id]:
            platform = device['platform']
            token = device['token']
            
            success = False
            
            if platform == 'android':
                success = self.send_fcm(token, notification)
            elif platform == 'ios':
                # Try APNs first, fall back to FCM
                success = self.send_apns(token, notification)
                if not success:
                    success = self.send_fcm(token, notification)
            elif platform == 'desktop':
                success = self.send_desktop_websocket(user_id, notification)
            
            if success:
                delivered += 1
        
        return delivered
    
    def process_queue(self) -> int:
        """
        Process pending notifications from proactive queue.
        Returns number of notifications delivered.
        """
        import sqlite3
        
        db_path = Path(__file__).parent.parent / 'proactive_system/proactive_queue.db'
        
        if not db_path.exists():
            logger.warning(f"Queue database not found: {db_path}")
            return 0
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get undelivered items
        cursor.execute("""
            SELECT id, source, message, priority, created_at, context
            FROM proactive_queue
            WHERE delivered = 0
            ORDER BY priority ASC, created_at ASC
            LIMIT ?
        """, (self.config['batch_size'],))
        
        items = cursor.fetchall()
        
        if not items:
            logger.debug("No pending notifications")
            conn.close()
            return 0
        
        logger.info(f"Processing {len(items)} pending notifications")
        
        delivered_count = 0
        
        for item_id, source, message, priority, created_at, context_json in items:
            # Parse context
            context = json.loads(context_json) if context_json else {}
            user_id = context.get('user_id', 'default')
            
            # Format notification
            queue_item = {
                'id': item_id,
                'source': source,
                'message': message,
                'priority': priority,
                'created_at': created_at,
                'context': context
            }
            
            notification = self.format_notification(queue_item)
            
            # Deliver to user's devices
            delivered = self.deliver_to_user(user_id, notification)
            
            if delivered > 0:
                # Mark as delivered
                cursor.execute("""
                    UPDATE proactive_queue
                    SET delivered = 1, delivered_at = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), item_id))
                conn.commit()
                
                delivered_count += 1
                logger.info(f"✅ Delivered notification {item_id} to {delivered} device(s)")
            else:
                logger.warning(f"⚠️  Failed to deliver notification {item_id}")
        
        conn.close()
        
        return delivered_count
    
    def run(self):
        """Main daemon loop."""
        logger.info("🚀 Push service started")
        logger.info(f"   Poll interval: {self.config['poll_interval']}s")
        logger.info(f"   FCM configured: {bool(self.config['fcm_server_key'])}")
        logger.info(f"   APNs configured: {bool(self.config['apns_key_id'])}")
        
        try:
            while True:
                delivered = self.process_queue()
                
                if delivered > 0:
                    logger.info(f"📬 Delivered {delivered} notification(s)")
                
                time.sleep(self.config['poll_interval'])
                
        except KeyboardInterrupt:
            logger.info("Push service stopped by user")
        except Exception as e:
            logger.error(f"Push service error: {e}", exc_info=True)


# API Endpoints (Flask integration)
def create_api(push_service: PushService):
    """Create Flask API for device registration."""
    from flask import Flask, request, jsonify
    
    app = Flask(__name__)
    
    @app.route('/devices/register', methods=['POST'])
    def register_device():
        """Register a device for push notifications."""
        data = request.json
        
        user_id = data.get('user_id')
        device_token = data.get('device_token')
        platform = data.get('platform')
        
        if not all([user_id, device_token, platform]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        push_service.register_device(user_id, device_token, platform)
        
        return jsonify({
            'status': 'success',
            'message': 'Device registered'
        })
    
    @app.route('/devices/unregister', methods=['POST'])
    def unregister_device():
        """Unregister a device."""
        data = request.json
        
        user_id = data.get('user_id')
        device_token = data.get('device_token')
        
        if not all([user_id, device_token]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        push_service.unregister_device(user_id, device_token)
        
        return jsonify({
            'status': 'success',
            'message': 'Device unregistered'
        })
    
    @app.route('/health', methods=['GET'])
    def health():
        """Health check endpoint."""
        return jsonify({
            'status': 'healthy',
            'registered_users': len(push_service.devices),
            'total_devices': sum(len(devices) for devices in push_service.devices.values())
        })
    
    return app


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Transmogrifier VM Push Service')
    parser.add_argument('--config', help='Config file path')
    parser.add_argument('--api-port', type=int, default=8100, help='API server port')
    parser.add_argument('--test', action='store_true', help='Test mode (process once)')
    
    args = parser.parse_args()
    
    service = PushService(config_path=args.config)
    
    if args.test:
        # Test mode: process queue once
        print("🧪 Test mode: Processing queue once...")
        delivered = service.process_queue()
        print(f"✅ Delivered {delivered} notification(s)")
    else:
        # Production mode: run daemon
        # Start API server in background thread
        import threading
        
        api_app = create_api(service)
        api_thread = threading.Thread(
            target=lambda: api_app.run(host='0.0.0.0', port=args.api_port, debug=False),
            daemon=True
        )
        api_thread.start()
        
        logger.info(f"API server started on port {args.api_port}")
        
        # Run main daemon loop
        service.run()
