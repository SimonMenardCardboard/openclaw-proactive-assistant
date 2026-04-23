#!/usr/bin/env python3
"""
File Sync API - Full File Storage & Access

Receives full file uploads from devices
Stores files on VM for cross-device access
Enables file download from any device

Storage: ~/workspace/synced_files/<device_id>/<path>
"""

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import json
import hashlib
import shutil
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Storage paths
SYNC_ROOT = Path.home() / 'workspace' / 'synced_files'
CHUNKS_ROOT = Path.home() / 'workspace' / 'sync_chunks'
METADATA_DB = Path.home() / 'workspace' / 'data' / 'sync_metadata.json'

# Create directories
SYNC_ROOT.mkdir(parents=True, exist_ok=True)
CHUNKS_ROOT.mkdir(parents=True, exist_ok=True)
METADATA_DB.parent.mkdir(parents=True, exist_ok=True)

def load_metadata():
    """Load sync metadata from disk"""
    if METADATA_DB.exists():
        with open(METADATA_DB, 'r') as f:
            return json.load(f)
    return {'files': {}}

def save_metadata(metadata):
    """Save sync metadata to disk"""
    with open(METADATA_DB, 'w') as f:
        json.dump(metadata, f, indent=2)

@app.route('/api/sync/upload', methods=['POST'])
def upload_file():
    """
    Upload file to VM
    
    POST /api/sync/upload
    Form Data:
    - file: file content
    - path: remote path
    - device_id: device ID
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        remote_path = request.form.get('path')
        device_id = request.form.get('device_id')
        
        if not remote_path or not device_id:
            return jsonify({'error': 'path and device_id required'}), 400
        
        # Calculate file hash
        file_data = file.read()
        file_hash = hashlib.sha256(file_data).hexdigest()
        file_size = len(file_data)
        
        # Save file
        file_path = SYNC_ROOT / secure_filename(remote_path.lstrip('/'))
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'wb') as f:
            f.write(file_data)
        
        # Update metadata
        metadata = load_metadata()
        metadata['files'][remote_path] = {
            'device_id': device_id,
            'local_path': str(file_path),
            'size': file_size,
            'hash': file_hash,
            'uploaded_at': datetime.utcnow().isoformat(),
        }
        save_metadata(metadata)
        
        print(f"✅ Uploaded: {remote_path} ({file_size} bytes)")
        
        return jsonify({
            'success': True,
            'path': remote_path,
            'size': file_size,
            'hash': file_hash
        })
        
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sync/upload-chunk', methods=['POST'])
def upload_chunk():
    """
    Upload file chunk (for large files)
    
    POST /api/sync/upload-chunk
    Form Data:
    - chunk: chunk data
    - path: remote path
    - chunk_index: chunk number
    - total_chunks: total chunks
    - device_id: device ID
    """
    try:
        if 'chunk' not in request.files:
            return jsonify({'error': 'No chunk provided'}), 400
        
        chunk = request.files['chunk']
        remote_path = request.form.get('path')
        chunk_index = int(request.form.get('chunk_index'))
        total_chunks = int(request.form.get('total_chunks'))
        device_id = request.form.get('device_id')
        
        # Save chunk
        chunk_dir = CHUNKS_ROOT / secure_filename(remote_path.lstrip('/'))
        chunk_dir.mkdir(parents=True, exist_ok=True)
        
        chunk_path = chunk_dir / f'chunk_{chunk_index}'
        chunk.save(str(chunk_path))
        
        print(f"📦 Saved chunk {chunk_index + 1}/{total_chunks} for {remote_path}")
        
        # Check if all chunks received
        chunks_received = len(list(chunk_dir.glob('chunk_*')))
        
        if chunks_received == total_chunks:
            # Reassemble file
            print(f"🔨 Reassembling {remote_path}...")
            
            final_path = SYNC_ROOT / secure_filename(remote_path.lstrip('/'))
            final_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(final_path, 'wb') as final_file:
                for i in range(total_chunks):
                    chunk_file = chunk_dir / f'chunk_{i}'
                    with open(chunk_file, 'rb') as cf:
                        final_file.write(cf.read())
            
            # Calculate hash
            with open(final_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            
            file_size = final_path.stat().st_size
            
            # Update metadata
            metadata = load_metadata()
            metadata['files'][remote_path] = {
                'device_id': device_id,
                'local_path': str(final_path),
                'size': file_size,
                'hash': file_hash,
                'uploaded_at': datetime.utcnow().isoformat(),
            }
            save_metadata(metadata)
            
            # Cleanup chunks
            shutil.rmtree(chunk_dir)
            
            print(f"✅ Reassembled: {remote_path} ({file_size} bytes)")
            
            return jsonify({
                'success': True,
                'complete': True,
                'path': remote_path,
                'size': file_size,
                'hash': file_hash
            })
        else:
            return jsonify({
                'success': True,
                'complete': False,
                'chunks_received': chunks_received,
                'total_chunks': total_chunks
            })
        
    except Exception as e:
        print(f"Chunk upload error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sync/download', methods=['GET'])
def download_file():
    """
    Download file from VM
    
    GET /api/sync/download?path=/device_id/folder/file.pdf
    
    Returns file content
    """
    try:
        remote_path = request.args.get('path')
        
        if not remote_path:
            return jsonify({'error': 'path required'}), 400
        
        # Get file metadata
        metadata = load_metadata()
        file_meta = metadata['files'].get(remote_path)
        
        if not file_meta:
            return jsonify({'error': 'File not found'}), 404
        
        local_path = Path(file_meta['local_path'])
        
        if not local_path.exists():
            return jsonify({'error': 'File not found on disk'}), 404
        
        print(f"📥 Downloading: {remote_path}")
        
        return send_file(
            str(local_path),
            as_attachment=True,
            download_name=os.path.basename(remote_path)
        )
        
    except Exception as e:
        print(f"Download error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sync/files', methods=['GET'])
def list_synced_files():
    """
    List all synced files
    
    GET /api/sync/files?device=device_id
    
    Returns list of synced files
    """
    try:
        device_filter = request.args.get('device')
        
        metadata = load_metadata()
        files = []
        
        for path, info in metadata['files'].items():
            if device_filter and info['device_id'] != device_filter:
                continue
            
            files.append({
                'path': path,
                'device_id': info['device_id'],
                'size': info['size'],
                'hash': info['hash'],
                'uploaded_at': info['uploaded_at'],
            })
        
        return jsonify({
            'success': True,
            'files': files,
            'count': len(files)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sync/delete', methods=['DELETE'])
def delete_file():
    """
    Delete synced file
    
    DELETE /api/sync/delete?path=/device_id/folder/file.pdf
    """
    try:
        remote_path = request.args.get('path')
        
        if not remote_path:
            return jsonify({'error': 'path required'}), 400
        
        metadata = load_metadata()
        file_meta = metadata['files'].get(remote_path)
        
        if not file_meta:
            return jsonify({'error': 'File not found'}), 404
        
        # Delete file
        local_path = Path(file_meta['local_path'])
        if local_path.exists():
            local_path.unlink()
        
        # Remove from metadata
        del metadata['files'][remote_path]
        save_metadata(metadata)
        
        print(f"🗑️ Deleted: {remote_path}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sync/stats', methods=['GET'])
def get_sync_stats():
    """
    Get sync statistics
    
    GET /api/sync/stats
    """
    try:
        metadata = load_metadata()
        
        total_size = sum(f['size'] for f in metadata['files'].values())
        devices = set(f['device_id'] for f in metadata['files'].values())
        
        # Get disk usage
        disk_usage = shutil.disk_usage(SYNC_ROOT)
        
        return jsonify({
            'success': True,
            'stats': {
                'total_files': len(metadata['files']),
                'total_size': total_size,
                'devices': len(devices),
                'disk_free': disk_usage.free,
                'disk_total': disk_usage.total,
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('FILE_SYNC_PORT', 8011))
    print(f"☁️  File Sync API starting on port {port}...")
    print(f"📁 Storage: {SYNC_ROOT}")
    app.run(host='0.0.0.0', port=port, debug=False)
