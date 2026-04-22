#!/usr/bin/env python3
"""
Intelligence API - Exposes V6/V7/V8/V8.5 data to mobile/desktop apps

Endpoints:
- GET /api/intelligence/summary - Recent proactive actions, healing, learning
- GET /api/intelligence/email-summary - Email insights (requires OAuth)
- GET /api/intelligence/calendar-next - Next 24h calendar with prep
- GET /api/intelligence/patterns - V8 learned patterns
- GET /api/intelligence/network - V8.5 federated insights
- GET /api/intelligence/health - System health (V6 + V7)
- POST /api/intelligence/feedback - User feedback on suggestions
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import json
import os
from datetime import datetime, timedelta
import subprocess

app = Flask(__name__)
CORS(app)

# Paths
V6_LOG = os.path.expanduser('~/workspace/logs/proactive_daemon_v2.log')
V7_LOG = os.path.expanduser('~/.openclaw/workspace/logs/self_healing.log')
V8_DB = os.path.expanduser('~/workspace/integrations/intelligence/v8_meta_learning/pattern_db.sqlite')
V85_DB = os.path.expanduser('~/workspace/integrations/intelligence/v8.5_federated/federation_db.sqlite')
FEEDBACK_DB = os.path.expanduser('~/workspace/data/intelligence_feedback.db')

# Initialize feedback database
def init_feedback_db():
    conn = sqlite3.connect(FEEDBACK_DB)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            suggestion_id TEXT NOT NULL,
            feedback TEXT NOT NULL,
            rating INTEGER,
            timestamp TEXT NOT NULL,
            metadata TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_feedback_db()

# Helper: Read recent log entries
def read_recent_logs(logfile, max_lines=50):
    try:
        result = subprocess.run(
            ['tail', '-n', str(max_lines), logfile],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip().split('\n') if result.stdout else []
    except Exception as e:
        print(f"Error reading {logfile}: {e}")
        return []

# Helper: Parse V6 actions from logs
def parse_v6_actions(logs):
    actions = []
    for line in logs:
        if '✅' in line or 'AUTONOMOUS ACTION' in line or 'refresh_auth_token' in line:
            try:
                # Extract timestamp and action
                parts = line.split()
                if len(parts) >= 3:
                    timestamp = ' '.join(parts[:2])
                    action = ' '.join(parts[2:])
                    actions.append({
                        'timestamp': timestamp,
                        'action': action,
                        'type': 'autonomous'
                    })
            except:
                continue
    return actions[-10:]  # Last 10 actions

# Helper: Parse V7 healing events
def parse_v7_healing(logs):
    events = []
    for line in logs:
        if 'REPAIR' in line or 'HEALING' in line or 'restart' in line.lower():
            try:
                parts = line.split()
                if len(parts) >= 3:
                    timestamp = ' '.join(parts[:2])
                    event = ' '.join(parts[2:])
                    events.append({
                        'timestamp': timestamp,
                        'event': event,
                        'type': 'healing'
                    })
            except:
                continue
    return events[-10:]  # Last 10 events

# Helper: Get V8 learned patterns
def get_v8_patterns():
    try:
        if not os.path.exists(V8_DB):
            return []
        
        conn = sqlite3.connect(V8_DB)
        c = conn.cursor()
        
        c.execute('''
            SELECT pattern_type, pattern_data, confidence, last_seen
            FROM patterns
            WHERE confidence > 0.5
            ORDER BY last_seen DESC
            LIMIT 20
        ''')
        
        patterns = []
        for row in c.fetchall():
            patterns.append({
                'type': row[0],
                'data': json.loads(row[1]) if row[1] else {},
                'confidence': row[2],
                'last_seen': row[3]
            })
        
        conn.close()
        return patterns
    except Exception as e:
        print(f"Error reading V8 patterns: {e}")
        return []

# Helper: Get V8.5 network insights
def get_v85_network_insights():
    try:
        if not os.path.exists(V85_DB):
            return {
                'enabled': False,
                'insights': [],
                'peers': 0
            }
        
        conn = sqlite3.connect(V85_DB)
        c = conn.cursor()
        
        # Get federated patterns
        c.execute('''
            SELECT pattern_type, aggregated_data, peer_count, last_update
            FROM federated_patterns
            ORDER BY last_update DESC
            LIMIT 10
        ''')
        
        insights = []
        for row in c.fetchall():
            insights.append({
                'type': row[0],
                'data': json.loads(row[1]) if row[1] else {},
                'peer_count': row[2],
                'last_update': row[3]
            })
        
        # Get peer count
        c.execute('SELECT COUNT(*) FROM peers WHERE active = 1')
        peer_count = c.fetchone()[0]
        
        conn.close()
        
        return {
            'enabled': True,
            'insights': insights,
            'peers': peer_count
        }
    except Exception as e:
        print(f"Error reading V8.5 network: {e}")
        return {
            'enabled': False,
            'insights': [],
            'peers': 0,
            'error': str(e)
        }

@app.route('/api/intelligence/summary', methods=['GET'])
def get_intelligence_summary():
    """
    Complete intelligence summary:
    - V6: Recent autonomous actions
    - V7: Self-healing events
    - V8: Learned patterns
    - V8.5: Network insights
    - System health
    """
    try:
        # Read logs
        v6_logs = read_recent_logs(V6_LOG)
        v7_logs = read_recent_logs(V7_LOG)
        
        # Parse data
        v6_actions = parse_v6_actions(v6_logs)
        v7_healing = parse_v7_healing(v7_logs)
        v8_patterns = get_v8_patterns()
        v85_network = get_v85_network_insights()
        
        # System health
        health = {
            'v6_active': len(v6_actions) > 0,
            'v7_active': len(v7_healing) > 0,
            'v8_active': len(v8_patterns) > 0,
            'v85_active': v85_network['enabled'],
            'last_v6_action': v6_actions[0]['timestamp'] if v6_actions else None,
            'last_v7_healing': v7_healing[0]['timestamp'] if v7_healing else None,
        }
        
        return jsonify({
            'success': True,
            'summary': {
                'v6_autonomous_actions': v6_actions,
                'v7_healing_events': v7_healing,
                'v8_learned_patterns': v8_patterns,
                'v85_network_insights': v85_network,
                'system_health': health,
                'timestamp': datetime.utcnow().isoformat()
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/intelligence/email-summary', methods=['GET'])
def get_email_summary():
    """
    Email intelligence using OAuth tokens
    Requires Google/Microsoft OAuth to be configured
    """
    try:
        # Check for OAuth tokens
        token_files = [
            os.path.expanduser('~/workspace/integrations/direct_api/token.json'),
            os.path.expanduser('~/workspace/integrations/direct_api/token_simon_at_legalmensch_com.json')
        ]
        
        oauth_available = any(os.path.exists(f) for f in token_files)
        
        if not oauth_available:
            return jsonify({
                'success': False,
                'error': 'OAuth not configured',
                'hint': 'Connect your email account in Settings'
            }), 400
        
        # TODO: Implement actual email fetching via OAuth
        # For now, return placeholder
        return jsonify({
            'success': True,
            'email_summary': {
                'unread_count': 0,
                'important_emails': [],
                'upcoming_deadlines': [],
                'suggested_replies': [],
                'oauth_status': 'connected',
                'note': 'Email analysis coming soon'
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/intelligence/calendar-next', methods=['GET'])
def get_calendar_next():
    """
    Next 24h calendar with meeting prep
    Requires Google/Microsoft OAuth
    """
    try:
        # Check for OAuth tokens
        token_files = [
            os.path.expanduser('~/workspace/integrations/direct_api/token.json'),
            os.path.expanduser('~/workspace/integrations/direct_api/token_simon_at_legalmensch_com.json')
        ]
        
        oauth_available = any(os.path.exists(f) for f in token_files)
        
        if not oauth_available:
            return jsonify({
                'success': False,
                'error': 'OAuth not configured',
                'hint': 'Connect your calendar in Settings'
            }), 400
        
        # TODO: Implement actual calendar fetching
        return jsonify({
            'success': True,
            'calendar': {
                'next_24h': [],
                'meeting_prep': [],
                'conflicts': [],
                'travel_time_needed': [],
                'oauth_status': 'connected',
                'note': 'Calendar intelligence coming soon'
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/intelligence/patterns', methods=['GET'])
def get_patterns():
    """
    V8 learned patterns with details
    """
    try:
        patterns = get_v8_patterns()
        
        return jsonify({
            'success': True,
            'patterns': patterns,
            'count': len(patterns),
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/intelligence/network', methods=['GET'])
def get_network():
    """
    V8.5 federated network insights
    """
    try:
        network = get_v85_network_insights()
        
        return jsonify({
            'success': True,
            'network': network,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/intelligence/health', methods=['GET'])
def get_health():
    """
    Overall system health from V6 + V7
    """
    try:
        v6_logs = read_recent_logs(V6_LOG, max_lines=10)
        v7_logs = read_recent_logs(V7_LOG, max_lines=10)
        
        v6_active = len(v6_logs) > 0 and any('✅' in log for log in v6_logs)
        v7_active = len(v7_logs) > 0
        
        # Check if daemons are running
        v6_running = subprocess.run(['pgrep', '-f', 'proactive_daemon'], capture_output=True).returncode == 0
        v7_running = subprocess.run(['pgrep', '-f', 'v7_self_healing'], capture_output=True).returncode == 0
        v8_running = subprocess.run(['pgrep', '-f', 'v8_daemon'], capture_output=True).returncode == 0
        
        return jsonify({
            'success': True,
            'health': {
                'v6': {
                    'running': v6_running,
                    'active': v6_active,
                    'status': 'healthy' if v6_running and v6_active else 'degraded'
                },
                'v7': {
                    'running': v7_running,
                    'active': v7_active,
                    'status': 'healthy' if v7_running and v7_active else 'degraded'
                },
                'v8': {
                    'running': v8_running,
                    'status': 'healthy' if v8_running else 'degraded'
                },
                'overall': 'healthy' if all([v6_running, v7_running, v8_running]) else 'degraded'
            },
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/intelligence/feedback', methods=['POST'])
def post_feedback():
    """
    User feedback on AI suggestions
    
    Body:
    {
        "suggestion_id": "v8_pattern_123",
        "feedback": "helpful" | "not_helpful" | "incorrect",
        "rating": 1-5,
        "metadata": {...}
    }
    """
    try:
        data = request.json
        
        suggestion_id = data.get('suggestion_id')
        feedback = data.get('feedback')
        rating = data.get('rating')
        metadata = json.dumps(data.get('metadata', {}))
        
        if not suggestion_id or not feedback:
            return jsonify({'error': 'suggestion_id and feedback required'}), 400
        
        conn = sqlite3.connect(FEEDBACK_DB)
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO feedback (suggestion_id, feedback, rating, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?)
        ''', (suggestion_id, feedback, rating, datetime.utcnow().isoformat(), metadata))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Feedback recorded'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('INTELLIGENCE_API_PORT', 8009))
    print(f"🧠 Intelligence API starting on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
