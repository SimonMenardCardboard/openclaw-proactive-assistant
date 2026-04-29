#!/usr/bin/env python3
"""
Mobile Usage Webhook - Mobile App Activity Tracking

Receives app usage data from mobile apps (iOS/Android).
Stores in SQLite database for V8 pattern learning.

API Endpoints:
- POST /api/usage/mobile - Receive mobile app usage
- GET /api/usage/health - Health check
- GET /api/usage/stats - Usage statistics
"""

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from flask import Flask, request, jsonify
from functools import wraps

# Configuration
WORKSPACE = Path.home() / '.openclaw' / 'workspace'
DB_PATH = WORKSPACE / 'transmogrifier' / 'openclaw-proactive-assistant' / 'app_usage' / 'mobile_usage.db'
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)

# Simple auth decorator
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 401
        
        # TODO: Validate token against user database
        # For now, accept any bearer token
        token = auth_header.split(' ')[1]
        if not token:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(*args, **kwargs)
    return decorated

# Database setup
def init_database():
    """Create database schema if not exists"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Mobile app usage table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mobile_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            app_name TEXT NOT NULL,
            duration_seconds INTEGER NOT NULL,
            platform TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # App categories (for pattern learning)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS app_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_name TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            productivity_score REAL DEFAULT 0.5,
            notes TEXT
        )
    ''')
    
    # Daily summaries (for quick stats)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            date TEXT NOT NULL,
            total_time_seconds INTEGER DEFAULT 0,
            most_used_app TEXT,
            productivity_score REAL DEFAULT 0.5,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, date)
        )
    ''')
    
    # Indexes for performance
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_mobile_usage_user_timestamp 
        ON mobile_usage(user_id, timestamp)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_mobile_usage_app 
        ON mobile_usage(app_name)
    ''')
    
    conn.commit()
    conn.close()
    print(f"✅ Database initialized: {DB_PATH}")

# Database operations
def record_usage(user_id: str, activities: List[Dict]) -> bool:
    """Record batch of app usage activities"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        for activity in activities:
            cursor.execute('''
                INSERT INTO mobile_usage (user_id, app_name, duration_seconds, platform, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                user_id,
                activity['app_name'],
                activity['duration_seconds'],
                activity['platform'],
                activity['timestamp']
            ))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error recording usage: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_usage_stats(user_id: str, days: int = 7) -> Dict:
    """Get usage statistics for user"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Get total time per app (last N days)
    cursor.execute('''
        SELECT app_name, SUM(duration_seconds) as total_seconds
        FROM mobile_usage
        WHERE user_id = ?
          AND datetime(timestamp) > datetime('now', ? || ' days')
        GROUP BY app_name
        ORDER BY total_seconds DESC
        LIMIT 10
    ''', (user_id, -days))
    
    top_apps = [{'app': row[0], 'seconds': row[1]} for row in cursor.fetchall()]
    
    # Get total tracked time
    cursor.execute('''
        SELECT SUM(duration_seconds)
        FROM mobile_usage
        WHERE user_id = ?
          AND datetime(timestamp) > datetime('now', ? || ' days')
    ''', (user_id, -days))
    
    total_seconds = cursor.fetchone()[0] or 0
    
    # Get activity count
    cursor.execute('''
        SELECT COUNT(*)
        FROM mobile_usage
        WHERE user_id = ?
          AND datetime(timestamp) > datetime('now', ? || ' days')
    ''', (user_id, -days))
    
    activity_count = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total_seconds': total_seconds,
        'total_hours': round(total_seconds / 3600, 2),
        'activity_count': activity_count,
        'top_apps': top_apps,
        'days': days,
    }

# API endpoints
@app.route('/api/usage/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'database': 'available' if DB_PATH.exists() else 'missing',
        'last_update': datetime.now().isoformat(),
    })

@app.route('/api/usage/mobile', methods=['POST'])
@require_auth
def record_mobile_usage():
    """
    Receive mobile app usage data
    
    Request body:
    {
        "platform": "ios",
        "activities": [
            {
                "app_name": "Instagram",
                "bundleId": "com.instagram.app",
                "duration_seconds": 300,
                "timestamp": "2026-04-29T14:30:00Z"
            }
        ]
    }
    """
    data = request.json
    
    if not data or 'activities' not in data:
        return jsonify({'error': 'Missing activities'}), 400
    
    activities = data['activities']
    
    # Extract user_id from token (for now, use a default)
    # TODO: Extract from JWT or token lookup
    user_id = 'simon'  # Hardcoded for now
    
    # Record activities
    success = record_usage(user_id, activities)
    
    if not success:
        return jsonify({'error': 'Failed to record usage'}), 500
    
    return jsonify({
        'success': True,
        'recorded': len(activities),
    })

@app.route('/api/usage/stats', methods=['GET'])
@require_auth
def usage_stats():
    """
    Get usage statistics
    
    Query params:
    - days: Number of days to include (default: 7)
    """
    days = int(request.args.get('days', 7))
    
    # TODO: Extract user_id from token
    user_id = 'simon'
    
    stats = get_usage_stats(user_id, days)
    
    return jsonify(stats)

@app.route('/api/usage/apps', methods=['GET'])
@require_auth
def get_apps():
    """Get list of tracked apps with categories"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT DISTINCT app_name
        FROM mobile_usage
        ORDER BY app_name
    ''')
    
    apps = [row[0] for row in cursor.fetchall()]
    
    # Get categories if available
    cursor.execute('SELECT app_name, category, productivity_score FROM app_categories')
    categories = {row[0]: {'category': row[1], 'productivity_score': row[2]} for row in cursor.fetchall()}
    
    conn.close()
    
    return jsonify({
        'apps': apps,
        'categories': categories,
    })

# Main
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Mobile Usage Webhook Server')
    parser.add_argument('--port', type=int, default=5007, help='Port to run on (default: 5007)')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    args = parser.parse_args()
    
    # Initialize database
    init_database()
    
    # Run server
    print(f"Starting App Usage Webhook Server...")
    print(f"  Host: {args.host}")
    print(f"  Port: {args.port}")
    print(f"  Database: {DB_PATH}")
    
    app.run(host=args.host, port=args.port, debug=False)
