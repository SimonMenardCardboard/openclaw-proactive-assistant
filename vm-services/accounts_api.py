#!/usr/bin/env python3
"""
Transmogrifier VM - Account Management + Device Management API

Handles:
- OAuth and IMAP account connections
- Device pairing and management
- Multi-device support for mobile + desktop

Endpoints:
# Accounts
- POST /api/accounts/add - Add OAuth or IMAP account
- GET /api/accounts/list - List connected accounts
- DELETE /api/accounts/remove/:id - Remove account

# Device Management  
- POST /api/devices/generate-code - Generate pairing code
- POST /api/devices/link - Link new device with code
- GET /api/devices/list - List all devices
- DELETE /api/devices/revoke/:id - Revoke device access
- POST /api/devices/update-activity - Update last active

# OAuth (if configured)
- GET /api/oauth/google/start - Start Google OAuth
- GET /api/oauth/google/callback - Handle Google OAuth callback
- GET /api/oauth/microsoft/start - Start Microsoft OAuth  
- GET /api/oauth/microsoft/callback - Handle Microsoft OAuth callback

# Health
- GET /api/health - Health check
"""

import json
import os
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
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
    """Initialize accounts + devices database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Accounts table
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
    
    # Devices table
    c.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY,
            device_name TEXT NOT NULL,
            device_type TEXT NOT NULL,
            platform TEXT,
            token_hash TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            last_active TEXT,
            
            UNIQUE(device_name, created_at)
        )
    ''')
    
    # Pairing codes table
    c.execute('''
        CREATE TABLE IF NOT EXISTS pairing_codes (
            code TEXT PRIMARY KEY,
            expires_at TEXT NOT NULL,
            used BOOLEAN DEFAULT 0,
            created_at TEXT NOT NULL,
            created_by_device TEXT
        )
    ''')
    
    c.execute('CREATE INDEX IF NOT EXISTS idx_pairing_expires ON pairing_codes(expires_at)')
    
    conn.commit()
    conn.close()

def generate_account_id(provider, email):
    """Generate deterministic account ID"""
    return hashlib.sha256(f"{provider}:{email}".encode()).hexdigest()[:16]

def generate_pairing_code():
    """Generate random 6-digit pairing code"""
    return ''.join([str(secrets.randbelow(10)) for _ in range(6)])

def generate_device_token():
    """Generate secure device token"""
    return secrets.token_urlsafe(32)

def hash_token(token):
    """Hash token for storage"""
    return hashlib.sha256(token.encode()).hexdigest()

# === HEALTH CHECK ===

@app.route('/api/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({'status': 'healthy', 'service': 'accounts-api'})

# === DEVICE MANAGEMENT ===

@app.route('/api/devices/generate-code', methods=['POST'])
def generate_device_pairing_code():
    """Generate one-time pairing code for new device"""
    try:
        data = request.json or {}
        device_name = data.get('device_name', 'Unknown')
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        code = generate_pairing_code()
        expires_at = datetime.utcnow() + timedelta(minutes=5)
        
        c.execute('''
            INSERT INTO pairing_codes (code, expires_at, used, created_at, created_by_device)
            VALUES (?, ?, ?, ?, ?)
        ''', (code, expires_at.isoformat(), False, datetime.utcnow().isoformat(), device_name))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Generated pairing code: {code}")
        
        return jsonify({
            'success': True,
            'code': code,
            'expires_at': expires_at.isoformat(),
            'expires_in_seconds': 300
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/devices/link', methods=['POST'])
def link_device():
    """Link new device using pairing code"""
    try:
        data = request.json
        code = data.get('code')
        device_name = data.get('device_name', 'Unknown Device')
        device_type = data.get('device_type', 'mobile')
        platform = data.get('platform', 'unknown')
        
        if not code:
            return jsonify({'error': 'Pairing code required'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('SELECT code, expires_at, used FROM pairing_codes WHERE code = ?', (code,))
        pairing = c.fetchone()
        
        if not pairing:
            conn.close()
            return jsonify({'error': 'Invalid pairing code'}), 400
        
        code_str, expires_at, used = pairing
        
        if used:
            conn.close()
            return jsonify({'error': 'Pairing code already used'}), 400
        
        expires_dt = datetime.fromisoformat(expires_at)
        if datetime.utcnow() > expires_dt:
            conn.close()
            return jsonify({'error': 'Pairing code expired'}), 400
        
        device_token = generate_device_token()
        device_id = 'dev_' + secrets.token_urlsafe(8)
        token_hash = hash_token(device_token)
        
        c.execute('''
            INSERT INTO devices (id, device_name, device_type, platform, token_hash, created_at, last_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (device_id, device_name, device_type, platform, token_hash, 
              datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
        
        c.execute('UPDATE pairing_codes SET used = ? WHERE code = ?', (True, code))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Device linked: {device_name}")
        
        return jsonify({
            'success': True,
            'device_token': device_token,
            'device_id': device_id,
            'vm_url': PUBLIC_URL,
            'device_name': device_name
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/devices/list', methods=['GET'])
def list_devices():
    """List all registered devices"""
    try:
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authorization required'}), 401
        
        device_token = auth_header.replace('Bearer ', '')
        token_hash_val = hash_token(device_token)
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute('''
            SELECT id, device_name, device_type, platform, created_at, last_active, token_hash
            FROM devices
            ORDER BY created_at ASC
        ''')
        
        devices = []
        for row in c.fetchall():
            devices.append({
                'id': row['id'],
                'device_name': row['device_name'],
                'device_type': row['device_type'],
                'platform': row['platform'],
                'created_at': row['created_at'],
                'last_active': row['last_active'],
                'is_current': row['token_hash'] == token_hash_val
            })
        
        conn.close()
        
        return jsonify({'devices': devices})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/devices/revoke/<device_id>', methods=['DELETE'])
def revoke_device(device_id):
    """Revoke a device's access"""
    try:
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authorization required'}), 401
        
        device_token = auth_header.replace('Bearer ', '')
        token_hash_val = hash_token(device_token)
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('SELECT id FROM devices WHERE token_hash = ?', (token_hash_val,))
        if not c.fetchone():
            conn.close()
            return jsonify({'error': 'Invalid token'}), 401
        
        c.execute('SELECT token_hash FROM devices WHERE id = ?', (device_id,))
        target = c.fetchone()
        if target and target[0] == token_hash_val:
            conn.close()
            return jsonify({'error': 'Cannot revoke current device'}), 400
        
        c.execute('DELETE FROM devices WHERE id = ?', (device_id,))
        
        if c.rowcount == 0:
            conn.close()
            return jsonify({'error': 'Device not found'}), 404
        
        conn.commit()
        conn.close()
        
        print(f"✅ Device revoked: {device_id}")
        
        return jsonify({'success': True, 'message': 'Device revoked'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# === ACCOUNT MANAGEMENT ===

@app.route('/api/accounts/add', methods=['POST'])
def add_account():
    """Add OAuth or IMAP account"""
    # [Keep existing implementation]
    pass

@app.route('/api/accounts/list', methods=['GET'])
def list_accounts():
    """List all connected accounts"""
    # [Keep existing implementation]
    pass

@app.route('/api/accounts/remove/<account_id>', methods=['DELETE'])
def remove_account(account_id):
    """Remove an account"""
    # [Keep existing implementation]
    pass

# === OAUTH FLOWS (if configured) ===

# [Keep existing OAuth implementations]

if __name__ == '__main__':
    print("Initializing database...")
    init_db()
    
    print(f"Starting Accounts + Device Management API on port 8008...")
    print(f"Public URL: {PUBLIC_URL}")
    
    app.run(host='0.0.0.0', port=8008, debug=False)
