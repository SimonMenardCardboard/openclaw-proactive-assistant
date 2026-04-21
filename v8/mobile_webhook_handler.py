#!/usr/bin/env python3
"""
Mobile Webhook Handler - V8 Meta-Learning

Receives activity data from iOS/Android companion apps via webhook POST.
Stores data in cross_device.db for pattern detection.

Endpoint: POST /api/v8/mobile_activity
Payload: {
    "device_id": str,
    "device_type": "ios" | "android",
    "activities": [{
        "timestamp": ISO8601,
        "app_name": str,
        "screen_title": str (optional),
        "activity_type": str,
        "duration": int (seconds),
        "metadata": {}
    }]
}
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from pathlib import Path
import sqlite3
import json
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mobile_webhook')

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests

# Database path
DB_PATH = Path.home() / '.openclaw/workspace/integrations/intelligence/v8_meta_learning/cross_device.db'

# Device ID authentication (simple token-based)
ALLOWED_DEVICES = {}  # Will load from config


def init_db():
    """Ensure cross_device.db has the right schema"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create tables if they don't exist (matches observer schema)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS observed_devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_name TEXT UNIQUE NOT NULL,
            device_type TEXT NOT NULL,
            host TEXT NOT NULL,
            port INTEGER,
            protocol TEXT,
            consent_given INTEGER DEFAULT 1,
            last_observed TEXT,
            observation_count INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            app_name TEXT,
            window_title TEXT,
            action_type TEXT,
            duration_sec INTEGER,
            metadata TEXT,
            FOREIGN KEY (device_id) REFERENCES observed_devices(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")


def get_or_create_device(device_name: str, device_type: str) -> int:
    """Get device ID or create new device entry"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if device exists
    cursor.execute('SELECT id FROM observed_devices WHERE device_name = ?', (device_name,))
    row = cursor.fetchone()
    
    if row:
        device_id = row[0]
    else:
        # Create new device
        cursor.execute('''
            INSERT INTO observed_devices 
            (device_name, device_type, host, protocol, consent_given)
            VALUES (?, ?, ?, ?, 1)
        ''', (device_name, device_type, 'mobile_webhook', 'webhook'))
        
        device_id = cursor.lastrowid
        logger.info(f"Created new device: {device_name} ({device_type}) with ID {device_id}")
    
    conn.commit()
    conn.close()
    
    return device_id


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'service': 'mobile_webhook_handler'})


@app.route('/api/v8/mobile_activity', methods=['POST'])
def receive_mobile_activity():
    """Receive activity data from mobile apps"""
    try:
        data = request.json
        
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data provided'}), 400
        
        # Validate required fields
        device_name = data.get('device_id') or data.get('device_name')
        device_type = data.get('device_type', 'unknown')
        activities = data.get('activities', [])
        
        if not device_name:
            return jsonify({'status': 'error', 'message': 'Missing device_id/device_name'}), 400
        
        if not activities:
            return jsonify({'status': 'error', 'message': 'No activities provided'}), 400
        
        # Get or create device
        device_id = get_or_create_device(device_name, device_type)
        
        # Store activities
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        stored_count = 0
        for activity in activities:
            try:
                cursor.execute('''
                    INSERT INTO activity_observations 
                    (device_id, timestamp, app_name, window_title, action_type, duration_sec, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    device_id,
                    activity.get('timestamp', datetime.now().isoformat()),
                    activity.get('app_name', 'unknown'),
                    activity.get('screen_title', ''),
                    activity.get('activity_type', 'usage'),
                    activity.get('duration', 0),
                    json.dumps(activity.get('metadata', {}))
                ))
                stored_count += 1
            except Exception as e:
                logger.error(f"Failed to store activity: {e}")
        
        # Update device stats
        cursor.execute('''
            UPDATE observed_devices
            SET last_observed = ?,
                observation_count = observation_count + ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), stored_count, device_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Stored {stored_count} activities from {device_name} ({device_type})")
        
        return jsonify({
            'status': 'recorded',
            'device_id': device_id,
            'device_name': device_name,
            'count': stored_count
        })
    
    except Exception as e:
        logger.error(f"Error processing mobile activity: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/v8/devices', methods=['GET'])
def list_devices():
    """List registered devices"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, device_name, device_type, last_observed, observation_count
            FROM observed_devices
            ORDER BY last_observed DESC
        ''')
        
        devices = []
        for row in cursor.fetchall():
            devices.append({
                'id': row[0],
                'name': row[1],
                'type': row[2],
                'last_seen': row[3],
                'observations': row[4]
            })
        
        conn.close()
        
        return jsonify({'devices': devices})
    
    except Exception as e:
        logger.error(f"Error listing devices: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/v8/stats', methods=['GET'])
def get_stats():
    """Get webhook statistics"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Total devices
        cursor.execute('SELECT COUNT(*) FROM observed_devices')
        device_count = cursor.fetchone()[0]
        
        # Total observations
        cursor.execute('SELECT COUNT(*) FROM activity_observations')
        observation_count = cursor.fetchone()[0]
        
        # Recent activity (last 24h)
        cursor.execute('''
            SELECT COUNT(*) FROM activity_observations
            WHERE timestamp >= datetime('now', '-1 day')
        ''')
        recent_count = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'total_devices': device_count,
            'total_observations': observation_count,
            'last_24h': recent_count
        })
    
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


def main():
    """Main entry point"""
    # Initialize database
    init_db()
    
    # Start Flask server
    port = 8768
    logger.info(f"Starting mobile webhook handler on port {port}")
    logger.info("Endpoints:")
    logger.info("  POST   /api/v8/mobile_activity - Receive activity data")
    logger.info("  GET    /api/v8/devices - List devices")
    logger.info("  GET    /api/v8/stats - Get statistics")
    logger.info("  GET    /health - Health check")
    
    app.run(host='0.0.0.0', port=port, debug=False)


if __name__ == '__main__':
    main()
