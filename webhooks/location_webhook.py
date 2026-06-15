#!/usr/bin/env python3
"""
Location Webhook Receiver

Receives GPS updates from mobile apps (iOS/Android) and stores in location database.

Endpoint: POST /api/location/update
Auth: Bearer token (user-specific)
Rate limit: 60 requests/minute per user

Usage:
    python3 location_webhook.py --port 5005
"""

from flask import Flask, request, jsonify
from pathlib import Path
import sys
import logging
import json
from datetime import datetime

# Add location_tracking to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'location_tracking'))

try:
    from location_db import LocationDB
    LOCATION_DB_AVAILABLE = True
except ImportError:
    LOCATION_DB_AVAILABLE = False
    print("⚠️  location_db not available")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize database
if LOCATION_DB_AVAILABLE:
    location_db = LocationDB()
else:
    location_db = None

import os
import sqlite3

# Location tokens are validated against the user database.
# Set LOCATION_DB_PATH env var or fall back to default proactive system DB.
_LOCATION_TOKEN_DB = os.getenv(
    'LOCATION_TOKEN_DB',
    str(Path(__file__).parent.parent / 'data' / 'users.db')
)

def _get_user_by_location_token(token: str):
    """Look up user email by location_token in the DB. Returns email or None."""
    try:
        conn = sqlite3.connect(_LOCATION_TOKEN_DB)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            'SELECT email FROM users WHERE location_token = ? AND status = ?',
            (token, 'active')
        ).fetchone()
        conn.close()
        return row['email'] if row else None
    except Exception as e:
        logging.warning(f'location_token DB lookup failed: {e}')
        return None

# Legacy static map removed — tokens now validated via DB (_get_user_by_location_token)

# Rate limiting (simple in-memory)
from collections import defaultdict
import time

rate_limit_data = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 60  # requests per window


def check_rate_limit(user_email: str) -> bool:
    """Check if user is within rate limit"""
    now = time.time()
    
    # Clean old requests
    rate_limit_data[user_email] = [
        t for t in rate_limit_data[user_email] 
        if now - t < RATE_LIMIT_WINDOW
    ]
    
    # Check limit
    if len(rate_limit_data[user_email]) >= RATE_LIMIT_MAX:
        return False
    
    # Add new request
    rate_limit_data[user_email].append(now)
    return True


@app.route('/api/location/update', methods=['POST'])
def update_location():
    """
    Receive location update from mobile app.
    
    Request body:
    {
        "lat": 37.7749,
        "lon": -122.4194,
        "accuracy": 10.5,
        "altitude": 15.0,
        "speed": 0.5,
        "timestamp": "2026-04-29T14:30:00Z",
        "activity": "walking",
        "battery_level": 75
    }
    
    Response:
    {
        "status": "ok",
        "location_id": 123,
        "current_place": {
            "id": 1,
            "name": "Home"
        }
    }
    """
    # Verify auth
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        logging.warning("Missing or invalid Authorization header")
        return jsonify({'error': 'Missing or invalid auth token'}), 401
    
    token = auth_header.replace('Bearer ', '')
    user_email = _get_user_by_location_token(token)
    
    if not user_email:
        logging.warning(f"Invalid token: {token[:10]}...")
        return jsonify({'error': 'Invalid token'}), 401
    
    # Rate limiting
    if not check_rate_limit(user_email):
        logging.warning(f"Rate limit exceeded for {user_email}")
        return jsonify({'error': 'Rate limit exceeded'}), 429
    
    # Check database availability
    if not location_db:
        logging.error("Location database not available")
        return jsonify({'error': 'Service unavailable'}), 503
    
    # Parse request
    data = request.get_json()
    
    if not data or 'lat' not in data or 'lon' not in data:
        logging.warning(f"Missing lat/lon in request from {user_email}")
        return jsonify({'error': 'Missing lat/lon'}), 400
    
    # Validate coordinates
    try:
        lat = float(data['lat'])
        lon = float(data['lon'])
        
        if not (-90 <= lat <= 90):
            return jsonify({'error': 'Invalid latitude (must be -90 to 90)'}), 400
        
        if not (-180 <= lon <= 180):
            return jsonify({'error': 'Invalid longitude (must be -180 to 180)'}), 400
    
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid lat/lon format'}), 400
    
    # Record location
    try:
        location_id = location_db.record_location(
            user_email=user_email,
            lat=lat,
            lon=lon,
            timestamp=data.get('timestamp'),
            accuracy=data.get('accuracy'),
            altitude=data.get('altitude'),
            speed=data.get('speed'),
            activity=data.get('activity'),
            battery_level=data.get('battery_level')
        )
        
        # Check if user is at a known place
        current_place = location_db.get_current_place(user_email)
        
        response = {
            'status': 'ok',
            'location_id': location_id
        }
        
        if current_place:
            response['current_place'] = {
                'id': current_place['id'],
                'name': current_place['name'],
                'category': current_place.get('category')
            }
            
            logging.info(f"Location updated for {user_email}: {lat:.4f}, {lon:.4f} (at {current_place['name']})")
        else:
            logging.info(f"Location updated for {user_email}: {lat:.4f}, {lon:.4f}")
        
        return jsonify(response), 200
    
    except Exception as e:
        logging.error(f"Failed to record location: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/location/places', methods=['GET'])
def get_places():
    """
    Get all places for authenticated user.
    
    Response:
    {
        "places": [
            {
                "id": 1,
                "name": "Home",
                "lat": 37.7749,
                "lon": -122.4194,
                "radius": 100,
                "category": "home",
                "detected_count": 45,
                "last_visit": "2026-04-29T14:30:00"
            }
        ]
    }
    """
    # Auth check (same as above)
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Missing auth'}), 401
    
    token = auth_header.replace('Bearer ', '')
    user_email = _get_user_by_location_token(token)
    
    if not user_email:
        return jsonify({'error': 'Invalid token'}), 401
    
    if not location_db:
        return jsonify({'error': 'Service unavailable'}), 503
    
    try:
        places = location_db.get_places(user_email)
        return jsonify({'places': places}), 200
    except Exception as e:
        logging.error(f"Failed to get places: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/location/history', methods=['GET'])
def get_history():
    """
    Get location history for authenticated user.
    
    Query params:
    - days: Number of days to look back (default: 7)
    - limit: Maximum number of points (default: 100)
    
    Response:
    {
        "locations": [
            {
                "id": 123,
                "lat": 37.7749,
                "lon": -122.4194,
                "accuracy": 10,
                "timestamp": "2026-04-29T14:30:00",
                "activity": "walking"
            }
        ]
    }
    """
    # Auth check
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Missing auth'}), 401
    
    token = auth_header.replace('Bearer ', '')
    user_email = _get_user_by_location_token(token)
    
    if not user_email:
        return jsonify({'error': 'Invalid token'}), 401
    
    if not location_db:
        return jsonify({'error': 'Service unavailable'}), 503
    
    # Parse query params
    days = int(request.args.get('days', 7))
    limit = int(request.args.get('limit', 100))
    
    # Validate
    if days < 1 or days > 90:
        return jsonify({'error': 'days must be 1-90'}), 400
    
    if limit < 1 or limit > 1000:
        return jsonify({'error': 'limit must be 1-1000'}), 400
    
    try:
        locations = location_db.get_location_history(
            user_email=user_email,
            days_back=days,
            limit=limit
        )
        
        return jsonify({'locations': locations}), 200
    except Exception as e:
        logging.error(f"Failed to get history: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/location/health', methods=['GET'])
def health():
    """
    Health check endpoint.
    
    Response:
    {
        "status": "healthy",
        "database": "available",
        "last_update": "2026-04-29T14:30:00"
    }
    """
    response = {
        'status': 'healthy',
        'database': 'available' if location_db else 'unavailable'
    }
    
    # Get timestamp of last location update (any user)
    if location_db:
        try:
            conn = location_db.db_path.parent
            if location_db.db_path.exists():
                # Get most recent location
                import sqlite3
                conn = sqlite3.connect(str(location_db.db_path))
                cursor = conn.cursor()
                cursor.execute('SELECT timestamp FROM locations ORDER BY timestamp DESC LIMIT 1')
                result = cursor.fetchone()
                if result:
                    response['last_update'] = result[0]
                conn.close()
        except Exception as e:
            logging.warning(f"Failed to get last update: {e}")
    
    return jsonify(response), 200


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description="Location Webhook Server")
    parser.add_argument('--port', type=int, default=5005, help='Port to listen on')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    print(f"Starting Location Webhook Server...")
    print(f"  Host: {args.host}")
    print(f"  Port: {args.port}")
    print(f"  Database: {'Available' if location_db else 'Unavailable'}")
    print()
    
    app.run(host=args.host, port=args.port, debug=args.debug)
