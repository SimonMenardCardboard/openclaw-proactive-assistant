#!/usr/bin/env python3
"""
Digest Intelligence API
Port: 8014

Provides weekly/daily digest generation
for Transmogrifier mobile/desktop apps.

Integrates with existing intelligenceApi.ts:
- getWeeklyDigest()
- getDailyDigest()
- getDashboard()
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
from pathlib import Path

# Add intelligence modules to path
sys.path.insert(0, str(Path(__file__).parent))

from weekly_digest import WeeklyDigestGenerator

app = Flask(__name__)
CORS(app)

# Initialize service
digest_service = WeeklyDigestGenerator()


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'service': 'digest-intelligence',
        'port': 8014
    })


@app.route('/api/digest/weekly', methods=['GET'])
def get_weekly_digest():
    """
    Get weekly digest.
    
    Query params:
        format: Output format (json|html|text, default: json)
        user_name: User's first name (default: 'there')
    
    Returns:
        Weekly digest in requested format
    """
    format_type = request.args.get('format', 'json')
    user_name = request.args.get('user_name', 'there')
    
    try:
        digest_data = digest_service.generate(user_name=user_name)
        
        if format_type == 'html':
            html = digest_service.format_html(digest_data, user_name=user_name)
            return jsonify({'html': html})
        
        elif format_type == 'text':
            text = digest_service.format_text(digest_data, user_name=user_name)
            return jsonify({'text': text})
        
        else:
            return jsonify(digest_data)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/digest/dashboard', methods=['GET'])
def get_dashboard():
    """
    Get dashboard overview.
    
    Returns:
        Dashboard data with all key metrics
    """
    try:
        # Get weekly digest data
        digest_data = digest_service.generate(user_name='')
        
        # Format as dashboard
        dashboard = {
            'inbox': digest_data.get('inbox', {}),
            'tasks': digest_data.get('tasks', {}),
            'relationships': {
                'follow_ups_needed': digest_data.get('followups', {}).get('count', 0),
                'vip_count': len([
                    r for r in digest_data.get('top_relationships', {}).get('people', [])
                    if r.get('importance_score', 0) >= 70
                ])
            },
            'recent_activity': []  # Could add activity log here
        }
        
        return jsonify(dashboard)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/digest/insights', methods=['GET'])
def get_insights():
    """
    Get key insights.
    
    Returns:
        List of insights
    """
    try:
        digest_data = digest_service.generate(user_name='')
        insights = digest_data.get('insights', [])
        
        return jsonify(insights)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("Digest Intelligence API starting on port 8014...")
    app.run(host='0.0.0.0', port=8014, debug=False)
