#!/usr/bin/env python3
"""
Push Notification Service - Send proactive alerts to mobile devices

Supports:
- FCM (Firebase Cloud Messaging) for Android
- APNs (Apple Push Notification service) for iOS

Use cases:
- V6 autonomous actions ("Auth token refreshed")
- V7 healing events ("Tunnel restarted automatically")
- Email alerts ("3 important emails need attention")
- Calendar reminders ("Meeting in 10 minutes")
- System alerts ("Disk space low")
"""

import os
import json
import sqlite3
import requests
from datetime import datetime

# Paths
DEVICES_DB = os.path.expanduser('~/.openclaw/data/accounts.db')
NOTIFICATIONS_DB = os.path.expanduser('~/workspace/data/notifications.db')

# FCM/APNs config (to be set via environment or config file)
FCM_SERVER_KEY = os.environ.get('FCM_SERVER_KEY', '')
APNS_KEY_PATH = os.environ.get('APNS_KEY_PATH', '')
APNS_KEY_ID = os.environ.get('APNS_KEY_ID', '')
APNS_TEAM_ID = os.environ.get('APNS_TEAM_ID', '')

def init_notifications_db():
    """Initialize notifications tracking database"""
    conn = sqlite3.connect(NOTIFICATIONS_DB)
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            notification_type TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            data TEXT,
            sent_at TEXT NOT NULL,
            delivered BOOLEAN DEFAULT 0,
            read BOOLEAN DEFAULT 0
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS push_tokens (
            device_id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            push_token TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

init_notifications_db()

def register_push_token(device_id, platform, push_token):
    """Register/update push token for a device"""
    try:
        conn = sqlite3.connect(NOTIFICATIONS_DB)
        c = conn.cursor()
        
        c.execute('''
            INSERT OR REPLACE INTO push_tokens (device_id, platform, push_token, updated_at)
            VALUES (?, ?, ?, ?)
        ''', (device_id, platform, push_token, datetime.utcnow().isoformat()))
        
        conn.commit()
        conn.close()
        
        return True
    except Exception as e:
        print(f"Error registering push token: {e}")
        return False

def get_push_token(device_id):
    """Get push token for a device"""
    try:
        conn = sqlite3.connect(NOTIFICATIONS_DB)
        c = conn.cursor()
        
        c.execute('SELECT platform, push_token FROM push_tokens WHERE device_id = ?', (device_id,))
        result = c.fetchone()
        
        conn.close()
        
        if result:
            return {'platform': result[0], 'token': result[1]}
        return None
    except Exception as e:
        print(f"Error getting push token: {e}")
        return None

def send_fcm_notification(push_token, title, body, data=None):
    """Send notification via Firebase Cloud Messaging (Android)"""
    if not FCM_SERVER_KEY:
        print("FCM_SERVER_KEY not configured")
        return False
    
    try:
        url = 'https://fcm.googleapis.com/fcm/send'
        headers = {
            'Authorization': f'key={FCM_SERVER_KEY}',
            'Content-Type': 'application/json',
        }
        
        payload = {
            'to': push_token,
            'notification': {
                'title': title,
                'body': body,
                'sound': 'default',
            },
            'data': data or {},
            'priority': 'high',
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            print(f"FCM notification sent successfully")
            return True
        else:
            print(f"FCM error: {response.status_code} {response.text}")
            return False
    except Exception as e:
        print(f"Error sending FCM notification: {e}")
        return False

def send_apns_notification(push_token, title, body, data=None):
    """Send notification via Apple Push Notification service (iOS)"""
    # TODO: Implement APNs using PyAPNs2 or similar
    # For now, return False (not implemented)
    print("APNs not yet implemented")
    return False

def send_notification(device_id, notification_type, title, body, data=None):
    """
    Send push notification to a device
    
    Args:
        device_id: Device ID from accounts.db
        notification_type: Type of notification (v6_action, v7_healing, email_alert, etc.)
        title: Notification title
        body: Notification body
        data: Optional data payload
    
    Returns:
        bool: Success or failure
    """
    try:
        # Get push token
        push_info = get_push_token(device_id)
        
        if not push_info:
            print(f"No push token for device {device_id}")
            return False
        
        platform = push_info['platform']
        push_token = push_info['token']
        
        # Send based on platform
        if platform == 'android':
            success = send_fcm_notification(push_token, title, body, data)
        elif platform == 'ios':
            success = send_apns_notification(push_token, title, body, data)
        else:
            print(f"Unknown platform: {platform}")
            success = False
        
        # Log notification
        conn = sqlite3.connect(NOTIFICATIONS_DB)
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO notifications (device_id, notification_type, title, body, data, sent_at, delivered)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            device_id,
            notification_type,
            title,
            body,
            json.dumps(data) if data else None,
            datetime.utcnow().isoformat(),
            1 if success else 0
        ))
        
        conn.commit()
        conn.close()
        
        return success
    except Exception as e:
        print(f"Error sending notification: {e}")
        return False

def broadcast_notification(notification_type, title, body, data=None):
    """
    Send notification to all registered devices
    
    Useful for system-wide alerts
    """
    try:
        conn = sqlite3.connect(NOTIFICATIONS_DB)
        c = conn.cursor()
        
        c.execute('SELECT device_id FROM push_tokens')
        devices = [row[0] for row in c.fetchall()]
        
        conn.close()
        
        results = []
        for device_id in devices:
            success = send_notification(device_id, notification_type, title, body, data)
            results.append({'device_id': device_id, 'success': success})
        
        return results
    except Exception as e:
        print(f"Error broadcasting notification: {e}")
        return []

def notify_v6_action(action_description):
    """Convenience function for V6 autonomous actions"""
    return broadcast_notification(
        'v6_action',
        '🤖 Autonomous Action',
        action_description,
        {'type': 'v6', 'action': action_description}
    )

def notify_v7_healing(healing_description):
    """Convenience function for V7 self-healing events"""
    return broadcast_notification(
        'v7_healing',
        '🩹 System Healed',
        healing_description,
        {'type': 'v7', 'event': healing_description}
    )

def notify_email_alert(unread_count, important_count):
    """Convenience function for email alerts"""
    title = '📧 New Emails'
    body = f'{unread_count} unread ({important_count} important)'
    
    return broadcast_notification(
        'email_alert',
        title,
        body,
        {'type': 'email', 'unread': unread_count, 'important': important_count}
    )

def notify_calendar_reminder(event_title, minutes_until):
    """Convenience function for calendar reminders"""
    title = '📅 Upcoming Meeting'
    body = f'{event_title} in {minutes_until} minutes'
    
    return broadcast_notification(
        'calendar_reminder',
        title,
        body,
        {'type': 'calendar', 'event': event_title, 'minutes': minutes_until}
    )

if __name__ == '__main__':
    # Test
    print("Push notification service initialized")
    print(f"FCM configured: {bool(FCM_SERVER_KEY)}")
    print(f"APNs configured: {bool(APNS_KEY_PATH and APNS_KEY_ID and APNS_TEAM_ID)}")
