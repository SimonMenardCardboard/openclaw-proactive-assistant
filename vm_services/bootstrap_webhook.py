#!/usr/bin/env python3
"""
Bootstrap Webhook - Triggers onboarding when app completes OAuth
Called by Transmogrifier mobile/desktop apps after user OAuth
"""

import sys
import asyncio
import logging
from pathlib import Path
from flask import Flask, request, jsonify

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent / 'onboarding'))
sys.path.insert(0, str(Path(__file__).parent.parent / 'proactive_system'))

from bootstrap import BootstrapOnboarding
from oauth_webhook import webhook_handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route('/onboarding/oauth-complete', methods=['POST'])
def oauth_complete():
    """
    Called by mobile/desktop app when user completes OAuth.
    Triggers bootstrap onboarding on VM.
    """
    data = request.json
    
    user_id = data.get('user_id')
    provider = data.get('provider')  # 'google', 'microsoft'
    oauth_tokens = data.get('oauth_tokens')
    
    if not all([user_id, provider]):
        return jsonify({'error': 'Missing user_id or provider'}), 400
    
    logger.info(f"OAuth complete: {user_id} → {provider}")
    
    # Check if first OAuth
    if webhook_handler.is_first_oauth_complete(user_id):
        logger.info(f"First OAuth for {user_id} - triggering bootstrap")
        
        # Trigger bootstrap asynchronously
        try:
            # Store OAuth tokens for data pull
            _store_oauth_tokens(user_id, provider, oauth_tokens)
            
            # Run bootstrap in background
            asyncio.create_task(
                webhook_handler.on_oauth_complete(user_id, provider, oauth_tokens)
            )
            
            return jsonify({
                'status': 'success',
                'message': 'Bootstrap onboarding started',
                'bootstrap_status': 'in_progress',
                'eta_hours': 2
            })
            
        except Exception as e:
            logger.error(f"Bootstrap trigger failed: {e}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500
    else:
        logger.info(f"Additional OAuth for {user_id} - bootstrap already triggered")
        
        # Still store tokens
        if oauth_tokens:
            _store_oauth_tokens(user_id, provider, oauth_tokens)
        
        return jsonify({
            'status': 'success',
            'message': 'OAuth credentials stored',
            'bootstrap_status': webhook_handler.get_bootstrap_status(user_id)
        })


@app.route('/onboarding/status/<user_id>', methods=['GET'])
def bootstrap_status(user_id: str):
    """Check bootstrap onboarding status for a user."""
    
    status = webhook_handler.get_bootstrap_status(user_id)
    
    # Get recommendation count
    import sqlite3
    from pathlib import Path
    
    db_path = Path(__file__).parent.parent / 'proactive_system/proactive_queue.db'
    
    recommendations_queued = 0
    recommendations_delivered = 0
    
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*), SUM(delivered)
            FROM proactive_queue
            WHERE source IN ('bootstrap', 'onboarding')
            AND json_extract(context, '$.user_id') = ?
        """, (user_id,))
        
        result = cursor.fetchone()
        if result:
            recommendations_queued = result[0] or 0
            recommendations_delivered = result[1] or 0
        
        conn.close()
    
    return jsonify({
        'user_id': user_id,
        'bootstrap_status': status,
        'recommendations': {
            'queued': recommendations_queued,
            'delivered': recommendations_delivered,
            'pending': recommendations_queued - recommendations_delivered
        },
        'status_info': {
            'not_started': 'User has not completed OAuth',
            'in_progress': 'Analyzing last 30 days, recommendations coming soon',
            'complete': 'Bootstrap complete, recommendations delivered',
            'failed': 'Bootstrap failed, check logs'
        }.get(status, 'Unknown')
    })


@app.route('/health', methods=['GET'])
def health():
    """Health check."""
    return jsonify({
        'status': 'healthy',
        'service': 'bootstrap-webhook'
    })


def _store_oauth_tokens(user_id: str, provider: str, tokens: dict):
    """Store OAuth tokens for later use by bootstrap data pull."""
    import json
    from pathlib import Path
    
    if not tokens:
        return
    
    # Store in user's config directory
    config_dir = Path.home() / '.openclaw/config/users' / user_id
    config_dir.mkdir(parents=True, exist_ok=True)
    
    token_file = config_dir / f'{provider}_tokens.json'
    
    with open(token_file, 'w') as f:
        json.dump(tokens, f, indent=2)
    
    logger.info(f"Stored {provider} OAuth tokens for {user_id}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Bootstrap Webhook Service')
    parser.add_argument('--port', type=int, default=8101, help='API port')
    parser.add_argument('--host', default='0.0.0.0', help='Bind host')
    
    args = parser.parse_args()
    
    logger.info(f"🚀 Bootstrap webhook starting on {args.host}:{args.port}")
    
    app.run(host=args.host, port=args.port, debug=False)
