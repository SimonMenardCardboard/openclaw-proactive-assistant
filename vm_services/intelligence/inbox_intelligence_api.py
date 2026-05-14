#!/usr/bin/env python3
"""
Inbox Intelligence API
Port: 8013

Provides smart inbox with priority sorting
for Transmogrifier mobile/desktop apps.

Integrates with existing intelligenceApi.ts:
- getSmartInbox()
- getVIPInbox()
- markRead(emailId)
- archiveEmail(emailId)
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
from pathlib import Path

# Add intelligence modules to path
sys.path.insert(0, str(Path(__file__).parent))

from smart_inbox import SmartInbox

app = Flask(__name__)
CORS(app)

# Initialize service
inbox_service = SmartInbox()


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'service': 'inbox-intelligence',
        'port': 8013
    })


@app.route('/api/inbox', methods=['GET'])
def get_inbox():
    """
    Get smart inbox with priority sorting.
    
    Query params:
        unread_only: Filter unread (default: false)
        limit: Max results (default: 50)
    
    Returns:
        Priority-sorted emails
    """
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    limit = int(request.args.get('limit', 50))
    
    try:
        emails = inbox_service.get_inbox(
            unread_only=unread_only,
            limit=limit
        )
        
        # Format for mobile/desktop
        results = []
        for email in emails:
            results.append({
                'message_id': email['message_id'],
                'from_name': email['from_name'],
                'from_email': email['from_email'],
                'subject': email['subject'],
                'snippet': email['snippet'],
                'priority_score': email['priority_score'],
                'priority_level': email['priority_level'],
                'is_vip': email['priority_level'] == 'vip',
                'received_at': email['received_at'],
                'read': email.get('read', False)
            })
        
        return jsonify(results)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/inbox/vip', methods=['GET'])
def get_vip_inbox():
    """
    Get VIP emails only.
    
    Query params:
        limit: Max results (default: 20)
    
    Returns:
        VIP emails
    """
    limit = int(request.args.get('limit', 20))
    
    try:
        emails = inbox_service.get_vip_inbox(limit=limit)
        
        # Format for mobile/desktop
        results = []
        for email in emails:
            results.append({
                'message_id': email['message_id'],
                'from_name': email['from_name'],
                'from_email': email['from_email'],
                'subject': email['subject'],
                'snippet': email['snippet'],
                'priority_score': email['priority_score'],
                'priority_level': 'vip',
                'is_vip': True,
                'received_at': email['received_at'],
                'read': email.get('read', False)
            })
        
        return jsonify(results)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/inbox/stats', methods=['GET'])
def get_inbox_stats():
    """
    Get inbox statistics.
    
    Returns:
        Inbox stats (unread, VIP, important, etc.)
    """
    try:
        stats = inbox_service.get_stats()
        return jsonify(stats)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/inbox/<string:message_id>/read', methods=['POST'])
def mark_read(message_id):
    """
    Mark email as read.
    
    Returns:
        Success status
    """
    try:
        result = inbox_service.mark_read(message_id)
        
        return jsonify({
            'success': True,
            'message_id': message_id,
            'read': True
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/inbox/<string:message_id>/archive', methods=['POST'])
def archive_email(message_id):
    """
    Archive email.
    
    Returns:
        Success status
    """
    try:
        result = inbox_service.archive(message_id)
        
        return jsonify({
            'success': True,
            'message_id': message_id,
            'archived': True
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/inbox/sync', methods=['POST'])
def sync_inbox():
    """
    Sync emails to inbox cache.
    
    Request body:
        account: Account ID
        emails: List of emails to sync
    
    Returns:
        Sync status
    """
    data = request.json
    
    if not data or 'account' not in data or 'emails' not in data:
        return jsonify({'error': 'Account and emails required'}), 400
    
    try:
        synced = inbox_service.sync_emails(data['account'], data['emails'])
        
        return jsonify({
            'success': True,
            'synced': synced
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("Inbox Intelligence API starting on port 8013...")
    app.run(host='0.0.0.0', port=8013, debug=False)
