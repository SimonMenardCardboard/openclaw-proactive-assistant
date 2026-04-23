#!/usr/bin/env python3
"""
Cross-Device File Search API

Receives file indexes from desktop/mobile devices
Enables searching files across all user devices
Supports file fetch from remote devices
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import json
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Database
DB_PATH = os.path.expanduser('~/.openclaw/data/file_index.db')

def init_db():
    """Initialize file index database"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS file_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            modified_at INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            extension TEXT,
            file_hash TEXT,
            mime_type TEXT,
            indexed_at TEXT NOT NULL,
            UNIQUE(device_id, file_path)
        )
    ''')
    
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_device_id ON file_index(device_id)
    ''')
    
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_file_name ON file_index(file_name)
    ''')
    
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_extension ON file_index(extension)
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS device_status (
            device_id TEXT PRIMARY KEY,
            device_name TEXT NOT NULL,
            last_sync TEXT NOT NULL,
            file_count INTEGER NOT NULL,
            total_size INTEGER NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

@app.route('/api/devices/<device_id>/files/index', methods=['POST'])
def update_file_index(device_id):
    """
    Update file index from a device
    
    POST /api/devices/<device_id>/files/index
    Body: {
        files: [
            {
                name: str,
                path: str,
                size: int,
                modified: int,
                created: int,
                extension: str,
                hash: str,
                mimeType: str
            }
        ],
        device_id: str,
        timestamp: int
    }
    """
    try:
        data = request.json
        files = data.get('files', [])
        
        if not files:
            return jsonify({'error': 'No files provided'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Clear old index for this device
        c.execute('DELETE FROM file_index WHERE device_id = ?', (device_id,))
        
        # Insert new index
        for file in files:
            c.execute('''
                INSERT OR REPLACE INTO file_index 
                (device_id, file_name, file_path, file_size, modified_at, created_at, 
                 extension, file_hash, mime_type, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                device_id,
                file.get('name'),
                file.get('path'),
                file.get('size', 0),
                file.get('modified', 0),
                file.get('created', 0),
                file.get('extension', ''),
                file.get('hash', ''),
                file.get('mimeType', ''),
                datetime.utcnow().isoformat()
            ))
        
        # Update device status
        total_size = sum(f.get('size', 0) for f in files)
        
        c.execute('''
            INSERT OR REPLACE INTO device_status (device_id, device_name, last_sync, file_count, total_size)
            VALUES (?, ?, ?, ?, ?)
        ''', (device_id, device_id, datetime.utcnow().isoformat(), len(files), total_size))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Indexed {len(files)} files from device {device_id}")
        
        return jsonify({
            'success': True,
            'files_indexed': len(files),
            'device_id': device_id
        })
        
    except Exception as e:
        print(f"Error updating file index: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/search/files', methods=['GET'])
def search_files():
    """
    Search files across all devices
    
    GET /api/search/files?q=query&device=device_id&ext=.pdf&limit=50
    
    Returns matching files with device info
    """
    try:
        query = request.args.get('q', '').lower()
        device_filter = request.args.get('device')
        ext_filter = request.args.get('ext')
        limit = int(request.args.get('limit', 50))
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Build SQL query
        sql = '''
            SELECT 
                f.device_id,
                f.file_name,
                f.file_path,
                f.file_size,
                f.modified_at,
                f.extension,
                f.mime_type,
                f.file_hash,
                d.device_name,
                d.last_sync
            FROM file_index f
            LEFT JOIN device_status d ON f.device_id = d.device_id
            WHERE 1=1
        '''
        
        params = []
        
        # Search query in filename
        if query:
            sql += ' AND LOWER(f.file_name) LIKE ?'
            params.append(f'%{query}%')
        
        # Filter by device
        if device_filter:
            sql += ' AND f.device_id = ?'
            params.append(device_filter)
        
        # Filter by extension
        if ext_filter:
            sql += ' AND f.extension = ?'
            params.append(ext_filter)
        
        sql += ' ORDER BY f.modified_at DESC LIMIT ?'
        params.append(limit)
        
        c.execute(sql, params)
        results = c.fetchall()
        
        conn.close()
        
        # Format results
        files = []
        for row in results:
            files.append({
                'device_id': row[0],
                'device_name': row[8] or row[0],
                'name': row[1],
                'path': row[2],
                'size': row[3],
                'modified': row[4],
                'extension': row[5],
                'mime_type': row[6],
                'hash': row[7],
                'last_synced': row[9],
                'available': self.is_device_online(row[0])  # Check if device online
            })
        
        return jsonify({
            'success': True,
            'query': query,
            'results': files,
            'count': len(files)
        })
        
    except Exception as e:
        print(f"Search error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/devices/<device_id>/files/stats', methods=['GET'])
def get_device_stats(device_id):
    """
    Get file index stats for a device
    
    GET /api/devices/<device_id>/files/stats
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Get device status
        c.execute('''
            SELECT device_name, last_sync, file_count, total_size
            FROM device_status
            WHERE device_id = ?
        ''', (device_id,))
        
        result = c.fetchone()
        
        if not result:
            conn.close()
            return jsonify({'error': 'Device not found'}), 404
        
        # Get file type breakdown
        c.execute('''
            SELECT extension, COUNT(*), SUM(file_size)
            FROM file_index
            WHERE device_id = ?
            GROUP BY extension
            ORDER BY COUNT(*) DESC
            LIMIT 10
        ''', (device_id,))
        
        extensions = []
        for row in c.fetchall():
            extensions.append({
                'extension': row[0] or 'none',
                'count': row[1],
                'total_size': row[2]
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'device_id': device_id,
            'device_name': result[0],
            'last_sync': result[1],
            'file_count': result[2],
            'total_size': result[3],
            'extensions': extensions
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/search/files/recent', methods=['GET'])
def get_recent_files():
    """
    Get recently modified files across all devices
    
    GET /api/search/files/recent?limit=20
    """
    try:
        limit = int(request.args.get('limit', 20))
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('''
            SELECT 
                f.device_id,
                f.file_name,
                f.file_path,
                f.file_size,
                f.modified_at,
                f.extension,
                f.mime_type,
                d.device_name
            FROM file_index f
            LEFT JOIN device_status d ON f.device_id = d.device_id
            ORDER BY f.modified_at DESC
            LIMIT ?
        ''', (limit,))
        
        results = c.fetchall()
        conn.close()
        
        files = []
        for row in results:
            files.append({
                'device_id': row[0],
                'device_name': row[7] or row[0],
                'name': row[1],
                'path': row[2],
                'size': row[3],
                'modified': row[4],
                'extension': row[5],
                'mime_type': row[6]
            })
        
        return jsonify({
            'success': True,
            'files': files
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def is_device_online(device_id):
    """
    Check if device is currently online
    TODO: Integrate with device heartbeat system
    """
    # Placeholder - would check last_active from devices table
    return False

if __name__ == '__main__':
    port = int(os.environ.get('FILE_SEARCH_PORT', 8010))
    print(f"🔍 File Search API starting on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
