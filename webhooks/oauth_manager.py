#!/usr/bin/env python3
"""
OAuth Token Manager for VPS

Receives OAuth tokens from mobile app and stores them for backend use.
Provides token refresh endpoint.

Endpoints:
- POST /api/oauth/register - Register tokens from mobile app
- POST /api/oauth/refresh - Refresh expired tokens
- GET /api/oauth/status - Check OAuth status for user
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, request, jsonify
# SECURITY FIX: Import webhook signature validation
try:
    from webhook_security import verify_webhook_signature
    WEBHOOK_SECURITY_AVAILABLE = True
except ImportError:
    WEBHOOK_SECURITY_AVAILABLE = False
    import logging
    logging.warning("Webhook security not available - using insecure mode")
    def verify_webhook_signature(request, **kwargs):
        return True  # Fallback (insecure)

import sqlite3
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [OAUTH-MANAGER] %(message)s',
    handlers=[
        logging.FileHandler(Path.home() / '.openclaw/workspace/integrations/intelligence/webhooks/oauth_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Database for storing OAuth tokens
DB_PATH = Path.home() / '.openclaw/workspace/integrations/intelligence/webhooks/oauth_tokens.db'


def init_db():
    """Initialize database for OAuth token storage"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS oauth_tokens (
            account_id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            account_type TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            access_token TEXT NOT NULL,
            refresh_token TEXT,
            id_token TEXT,
            expires_at TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    
    logger.info("OAuth token database initialized")


@app.route('/api/oauth/register', methods=['POST'])
def register_tokens():
    """
    Register OAuth tokens from mobile app (multi-account support).
    
    Mobile app sends tokens after successful Google Sign-In.
    VPS stores tokens for backend use (Gmail/Calendar APIs).
    
    Payload:
    {
        "accountId": "gmail_1713571200000",
        "email": "user@gmail.com",
        "type": "gmail",
        "accessToken": "ya29...",
        "refreshToken": "1//...",
        "idToken": "eyJ...",
        "expiresAt": 1713571200000
    }
    """
    # SECURITY FIX: Verify webhook signature
    if WEBHOOK_SECURITY_AVAILABLE:
        if not verify_webhook_signature(request):
            from flask import jsonify
            return jsonify({'error': 'Unauthorized'}), 401
    

    try:
        data = request.get_json()
        
        account_id = data.get('accountId')
        email = data.get('email')
        account_type = data.get('type', 'gmail')
        access_token = data.get('accessToken')
        refresh_token = data.get('refreshToken')
        id_token = data.get('idToken')
        expires_at = data.get('expiresAt')
        
        if not account_id or not email or not access_token or not expires_at:
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Convert expires_at from milliseconds to ISO format
        expires_at_dt = datetime.fromtimestamp(expires_at / 1000)
        
        # Check if IMAP credentials provided
        imap_host = data.get('imapHost')
        imap_port = data.get('imapPort')
        imap_username = data.get('imapUsername')
        imap_password = data.get('imapPassword')
        
        # Store tokens in database
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        if imap_host:  # IMAP account
            cursor.execute('''
                INSERT OR REPLACE INTO oauth_tokens 
                (account_id, email, account_type, access_token, expires_at, updated_at,
                 imap_host, imap_port, imap_username, imap_password)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (account_id, email, account_type, access_token, expires_at_dt.isoformat(),
                  datetime.now().isoformat(), imap_host, imap_port, imap_username, imap_password))
        else:  # OAuth account
            cursor.execute('''
                INSERT OR REPLACE INTO oauth_tokens 
                (account_id, email, account_type, access_token, refresh_token, id_token, expires_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (account_id, email, account_type, access_token, refresh_token, id_token, 
                  expires_at_dt.isoformat(), datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Registered OAuth tokens for {email} (account_id: {account_id})")
        
        # AUTO-SUBSCRIBE to push notifications (production flow)
        if account_type == 'gmail' and not imap_host:
            try:
                import requests
                
                # Subscribe to Gmail push
                gmail_resp = requests.post(
                    'http://localhost:5001/api/gmail/subscribe',
                    json={
                        'email_account': email,
                        'topic_name': 'projects/openclaw-cos-1776663186/topics/gmail-push-notifications'
                    },
                    timeout=5
                )
                
                if gmail_resp.status_code == 200:
                    logger.info(f"Auto-subscribed Gmail push for {email}")
                else:
                    logger.warning(f"Gmail push subscription failed: {gmail_resp.status_code}")
                
                # Subscribe to Calendar push
                cal_resp = requests.post(
                    'http://localhost:5002/api/calendar/subscribe',
                    json={
                        'email_account': email,
                        'calendar_id': 'primary',
                        'webhook_url': 'https://outgrow-overkill-regress.ngrok-free.dev/api/calendar/webhook'
                    },
                    timeout=5
                )
                
                if cal_resp.status_code == 200:
                    logger.info(f"Auto-subscribed Calendar push for {email}")
                else:
                    logger.warning(f"Calendar push subscription failed: {cal_resp.status_code}")
                    
            except Exception as e:
                logger.error(f"Auto-subscription failed: {e}")
        
        return jsonify({
            'status': 'registered',
            'accountId': account_id,
            'email': email,
            'expiresAt': expires_at_dt.isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Register tokens error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/oauth/refresh', methods=['POST'])
def refresh_tokens():
    """
    Refresh expired OAuth tokens.
    
    Mobile app calls this when tokens are expired.
    VPS uses refresh token to get new access token.
    
    Payload:
    {
        "refreshToken": "1//..."
    }
    """
    # SECURITY FIX: Verify webhook signature
    if WEBHOOK_SECURITY_AVAILABLE:
        if not verify_webhook_signature(request):
            from flask import jsonify
            return jsonify({'error': 'Unauthorized'}), 401
    

    try:
        data = request.get_json()
        
        refresh_token = data.get('refreshToken')
        
        if not refresh_token:
            return jsonify({'error': 'Missing refreshToken'}), 400
        
        # Use Google OAuth2 library to refresh token
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=os.environ.get('GOOGLE_CLIENT_ID'),
            client_secret=os.environ.get('GOOGLE_CLIENT_SECRET')
        )
        
        # Refresh
        creds.refresh(Request())
        
        # Return new tokens
        return jsonify({
            'accessToken': creds.token,
            'idToken': creds.id_token,
            'expiresAt': int(creds.expiry.timestamp() * 1000) if creds.expiry else None
        }), 200
        
    except Exception as e:
        logger.error(f"Refresh tokens error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/oauth/status', methods=['GET'])
def oauth_status():
    """
    Check OAuth status for user.
    
    Query params:
    - email: user@gmail.com
    
    Returns:
    - authenticated: true/false
    - expiresAt: ISO timestamp (if authenticated)
    """
    try:
        email = request.args.get('email')
        
        if not email:
            return jsonify({'error': 'Missing email'}), 400
        
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute('SELECT access_token, expires_at FROM oauth_tokens WHERE email = ?', (email,))
        result = cursor.fetchone()
        
        conn.close()
        
        if not result:
            return jsonify({
                'authenticated': False,
                'email': email
            }), 200
        
        access_token, expires_at = result
        expires_at_dt = datetime.fromisoformat(expires_at)
        
        is_expired = expires_at_dt < datetime.now()
        
        return jsonify({
            'authenticated': not is_expired,
            'email': email,
            'expiresAt': expires_at,
            'expired': is_expired
        }), 200
        
    except Exception as e:
        logger.error(f"OAuth status error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/accounts/<account_id>/toggle', methods=['POST'])
def toggle_account(account_id):
    """
    Enable/disable account (stops/resumes COS analysis).
    
    Payload:
    {
        "enabled": false
    }
    """
    # SECURITY FIX: Verify webhook signature
    if WEBHOOK_SECURITY_AVAILABLE:
        if not verify_webhook_signature(request):
            from flask import jsonify
            return jsonify({'error': 'Unauthorized'}), 401
    

    try:
        data = request.get_json()
        enabled = data.get('enabled', True)
        
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute('UPDATE oauth_tokens SET enabled = ? WHERE account_id = ?', 
                       (1 if enabled else 0, account_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Account {account_id} {'enabled' if enabled else 'disabled'}")
        
        return jsonify({
            'status': 'updated',
            'accountId': account_id,
            'enabled': enabled
        }), 200
        
    except Exception as e:
        logger.error(f"Toggle account error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/accounts/<account_id>', methods=['DELETE'])
def delete_account(account_id):
    """
    Remove account completely (deletes OAuth tokens).
    """
    # SECURITY FIX: Verify webhook signature
    if WEBHOOK_SECURITY_AVAILABLE:
        if not verify_webhook_signature(request):
            from flask import jsonify
            return jsonify({'error': 'Unauthorized'}), 401
    

    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM oauth_tokens WHERE account_id = ?', (account_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Account {account_id} deleted")
        
        return jsonify({
            'status': 'deleted',
            'accountId': account_id
        }), 200
        
    except Exception as e:
        logger.error(f"Delete account error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat()
    }), 200


if __name__ == '__main__':
    init_db()
    
    port = int(os.environ.get('OAUTH_MANAGER_PORT', 5003))
    
    logger.info(f"Starting OAuth manager on port {port}")
    
    app.run(host='0.0.0.0', port=port, debug=False)
