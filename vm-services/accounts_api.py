#!/usr/bin/env python3
"""
Transmogrifier VM - Account Management API

Handles OAuth and IMAP account connections for individual users.
Each VM runs this service to manage its owner's email/calendar accounts.

Endpoints:
- POST /api/accounts/add - Add OAuth or IMAP account
- GET /api/accounts/list - List connected accounts
- DELETE /api/accounts/remove/:id - Remove account
- GET /api/oauth/google/start - Start Google OAuth
- GET /api/oauth/google/callback - Handle Google OAuth callback
- GET /api/oauth/microsoft/start - Start Microsoft OAuth  
- GET /api/oauth/microsoft/callback - Handle Microsoft OAuth callback
"""

import json
import os
import sqlite3
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

# Database setup
DB_PATH = os.path.expanduser('~/.openclaw/data/accounts.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# OAuth credentials (set via environment or config)
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
MICROSOFT_CLIENT_ID = os.getenv('MICROSOFT_CLIENT_ID', '')
MICROSOFT_CLIENT_SECRET = os.getenv('MICROSOFT_CLIENT_SECRET', '')

# This VM's public URL (set during provisioning)
PUBLIC_URL = os.getenv('PUBLIC_URL', 'http://localhost:8008')

def init_db():
    """Initialize accounts database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            type TEXT NOT NULL,
            email TEXT,
            display_name TEXT,
            
            -- OAuth fields
            access_token TEXT,
            refresh_token TEXT,
            token_expires_at INTEGER,
            
            -- IMAP fields
            imap_host TEXT,
            imap_port INTEGER,
            imap_username TEXT,
            imap_password TEXT,
            imap_ssl BOOLEAN,
            
            -- CalDAV fields
            caldav_url TEXT,
            caldav_username TEXT,
            caldav_password TEXT,
            
            -- Metadata
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_sync_at TEXT,
            sync_enabled BOOLEAN DEFAULT 1,
            
            UNIQUE(provider, email)
        )
    ''')
    
    conn.commit()
    conn.close()

def generate_account_id(provider, email):
    """Generate deterministic account ID"""
    return hashlib.sha256(f"{provider}:{email}".encode()).hexdigest()[:16]

@app.route('/api/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({'status': 'healthy', 'service': 'accounts-api'})

@app.route('/api/accounts/add', methods=['POST'])
def add_account():
    """Add OAuth or IMAP account"""
    data = request.json
    
    provider = data.get('provider')
    account_type = data.get('type')  # 'oauth' or 'imap' or 'caldav'
    email = data.get('email', '')
    
    if not provider or not account_type:
        return jsonify({'error': 'provider and type required'}), 400
    
    # Generate account ID
    account_id = generate_account_id(provider, email)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    now = datetime.utcnow().isoformat()
    
    try:
        if account_type == 'oauth':
            # OAuth account (Google, Microsoft)
            c.execute('''
                INSERT OR REPLACE INTO accounts (
                    id, provider, type, email, access_token, refresh_token,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                account_id,
                provider,
                'oauth',
                email,
                data.get('access_token'),
                data.get('refresh_token'),
                now,
                now
            ))
            
        elif account_type == 'imap':
            # IMAP account (iCloud, Fastmail, ProtonMail, Custom)
            c.execute('''
                INSERT OR REPLACE INTO accounts (
                    id, provider, type, email, 
                    imap_host, imap_port, imap_username, imap_password, imap_ssl,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                account_id,
                provider,
                'imap',
                email,
                data.get('imap_host'),
                data.get('imap_port', 993),
                data.get('imap_username', email),
                data.get('imap_password'),
                data.get('imap_ssl', True),
                now,
                now
            ))
            
        elif account_type == 'caldav':
            # CalDAV account
            c.execute('''
                INSERT OR REPLACE INTO accounts (
                    id, provider, type, email,
                    caldav_url, caldav_username, caldav_password,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                account_id,
                provider,
                'caldav',
                email,
                data.get('caldav_url'),
                data.get('caldav_username', email),
                data.get('caldav_password'),
                now,
                now
            ))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'account_id': account_id,
            'provider': provider,
            'email': email
        })
        
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
        
    finally:
        conn.close()

@app.route('/api/accounts/list', methods=['GET'])
def list_accounts():
    """List all connected accounts"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('''
        SELECT 
            id, provider, type, email, display_name,
            created_at, updated_at, last_sync_at, sync_enabled
        FROM accounts
        ORDER BY created_at DESC
    ''')
    
    accounts = []
    for row in c.fetchall():
        accounts.append({
            'id': row['id'],
            'provider': row['provider'],
            'type': row['type'],
            'email': row['email'],
            'display_name': row['display_name'],
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
            'last_sync_at': row['last_sync_at'],
            'sync_enabled': bool(row['sync_enabled']),
        })
    
    conn.close()
    
    return jsonify({'accounts': accounts})

@app.route('/api/accounts/remove/<account_id>', methods=['DELETE'])
def remove_account(account_id):
    """Remove an account"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('DELETE FROM accounts WHERE id = ?', (account_id,))
    
    if c.rowcount == 0:
        conn.close()
        return jsonify({'error': 'Account not found'}), 404
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'account_id': account_id})

@app.route('/api/accounts/toggle/<account_id>', methods=['POST'])
def toggle_sync(account_id):
    """Enable/disable sync for an account"""
    data = request.json
    enabled = data.get('enabled', True)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        UPDATE accounts 
        SET sync_enabled = ?, updated_at = ?
        WHERE id = ?
    ''', (enabled, datetime.utcnow().isoformat(), account_id))
    
    if c.rowcount == 0:
        conn.close()
        return jsonify({'error': 'Account not found'}), 404
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'account_id': account_id, 'sync_enabled': enabled})

# OAuth flows (if credentials are configured)

@app.route('/api/oauth/google/start', methods=['GET'])
def google_oauth_start():
    """Start Google OAuth flow"""
    if not GOOGLE_CLIENT_ID:
        return jsonify({'error': 'Google OAuth not configured'}), 501
    
    redirect_uri = f"{PUBLIC_URL}/api/oauth/google/callback"
    
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope=https://www.googleapis.com/auth/gmail.readonly "
        f"https://www.googleapis.com/auth/calendar.readonly "
        f"https://www.googleapis.com/auth/userinfo.email "
        f"https://www.googleapis.com/auth/userinfo.profile&"
        f"access_type=offline&"
        f"prompt=consent"
    )
    
    return redirect(auth_url)

@app.route('/api/oauth/google/callback', methods=['GET'])
def google_oauth_callback():
    """Handle Google OAuth callback"""
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        return jsonify({'error': error}), 400
    
    if not code:
        return jsonify({'error': 'No code received'}), 400
    
    # Exchange code for tokens
    redirect_uri = f"{PUBLIC_URL}/api/oauth/google/callback"
    
    token_response = requests.post('https://oauth2.googleapis.com/token', data={
        'code': code,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    })
    
    tokens = token_response.json()
    
    if 'error' in tokens:
        return jsonify({'error': tokens['error']}), 400
    
    # Get user email
    userinfo_response = requests.get(
        'https://www.googleapis.com/oauth2/v2/userinfo',
        headers={'Authorization': f"Bearer {tokens['access_token']}"}
    )
    userinfo = userinfo_response.json()
    email = userinfo.get('email', '')
    
    # Save account
    account_id = generate_account_id('google', email)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    
    c.execute('''
        INSERT OR REPLACE INTO accounts (
            id, provider, type, email, access_token, refresh_token,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        account_id, 'google', 'oauth', email,
        tokens['access_token'], tokens.get('refresh_token'),
        now, now
    ))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'provider': 'google',
        'email': email,
        'account_id': account_id
    })

@app.route('/api/oauth/microsoft/start', methods=['GET'])
def microsoft_oauth_start():
    """Start Microsoft OAuth flow"""
    if not MICROSOFT_CLIENT_ID:
        return jsonify({'error': 'Microsoft OAuth not configured'}), 501
    
    redirect_uri = f"{PUBLIC_URL}/api/oauth/microsoft/callback"
    
    auth_url = (
        f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?"
        f"client_id={MICROSOFT_CLIENT_ID}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope=https://graph.microsoft.com/Mail.Read "
        f"https://graph.microsoft.com/Calendars.Read "
        f"https://graph.microsoft.com/User.Read "
        f"offline_access&"
        f"response_mode=query"
    )
    
    return redirect(auth_url)

@app.route('/api/oauth/microsoft/callback', methods=['GET'])
def microsoft_oauth_callback():
    """Handle Microsoft OAuth callback"""
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        return jsonify({'error': error}), 400
    
    if not code:
        return jsonify({'error': 'No code received'}), 400
    
    redirect_uri = f"{PUBLIC_URL}/api/oauth/microsoft/callback"
    
    token_response = requests.post(
        'https://login.microsoftonline.com/common/oauth2/v2.0/token',
        data={
            'code': code,
            'client_id': MICROSOFT_CLIENT_ID,
            'client_secret': MICROSOFT_CLIENT_SECRET,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }
    )
    
    tokens = token_response.json()
    
    if 'error' in tokens:
        return jsonify({'error': tokens['error']}), 400
    
    # Get user email
    userinfo_response = requests.get(
        'https://graph.microsoft.com/v1.0/me',
        headers={'Authorization': f"Bearer {tokens['access_token']}"}
    )
    userinfo = userinfo_response.json()
    email = userinfo.get('mail') or userinfo.get('userPrincipalName', '')
    
    # Save account
    account_id = generate_account_id('microsoft', email)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    
    c.execute('''
        INSERT OR REPLACE INTO accounts (
            id, provider, type, email, access_token, refresh_token,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        account_id, 'microsoft', 'oauth', email,
        tokens['access_token'], tokens.get('refresh_token'),
        now, now
    ))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'provider': 'microsoft',
        'email': email,
        'account_id': account_id
    })

if __name__ == '__main__':
    print("Initializing accounts database...")
    init_db()
    
    print(f"Starting Accounts API on port 8008...")
    print(f"Public URL: {PUBLIC_URL}")
    print(f"Google OAuth: {'Configured' if GOOGLE_CLIENT_ID else 'Not configured'}")
    print(f"Microsoft OAuth: {'Configured' if MICROSOFT_CLIENT_ID else 'Not configured'}")
    
    app.run(host='0.0.0.0', port=8008, debug=False)
