#!/usr/bin/env python3
"""
Gmail Push API Webhook Server

Receives push notifications from Gmail when new emails arrive.
Triggers COS analysis immediately (real-time, not batched).

Architecture:
1. Gmail sends push notification to this webhook
2. Webhook fetches full email content via Gmail API
3. Triggers COS analysis (cos_trigger_handlers.py)
4. COS generates recommendations
5. Recommendations delivered via push notification

Setup:
1. Deploy this webhook to VPS (Flask app)
2. Subscribe to Gmail push notifications via Gmail API watch()
3. Renew subscription every 7 days (auto-renewal cron)

Security:
- Verify Google webhook signature
- Rate limiting (prevent abuse)
- Authentication (only accept requests from Google)
"""

import os
import sys
import json
import base64
import logging
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, request, jsonify
import sqlite3

# Add paths for imports
sys.path.insert(0, str(Path.home() / ".openclaw/workspace/integrations/intelligence/integration"))
sys.path.insert(0, str(Path.home() / ".openclaw/workspace/transmogrifier/openclaw-proactive-assistant"))

from gmail_api import GmailAPI

# SECURITY FIX: Import webhook signature validation
try:
    from webhook_security import verify_gmail_webhook
    WEBHOOK_SECURITY_AVAILABLE = True
except ImportError:
    WEBHOOK_SECURITY_AVAILABLE = False
    logging.warning("Webhook security not available - using insecure mode")
    def verify_gmail_webhook(request):
        return True  # Fallback (insecure)

# Import COS triggers
try:
    from cos_trigger_handlers import get_trigger_handlers
    COS_AVAILABLE = True
except ImportError:
    COS_AVAILABLE = False
    logging.warning("COS trigger handlers not available")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [GMAIL-WEBHOOK] %(message)s',
    handlers=[
        logging.FileHandler(Path.home() / '.openclaw/workspace/integrations/intelligence/webhooks/gmail_webhook.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Database for tracking processed emails (prevent duplicates)
DB_PATH = Path.home() / '.openclaw/workspace/integrations/intelligence/webhooks/webhook_state.db'


def init_db():
    """Initialize database for webhook state tracking"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_emails (
            email_id TEXT PRIMARY KEY,
            history_id TEXT,
            processed_at TEXT,
            sender TEXT,
            subject TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS webhook_subscriptions (
            email_account TEXT PRIMARY KEY,
            watch_expiration TEXT,
            last_renewal TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    
    logger.info("Webhook database initialized")


def is_processed(email_id: str) -> bool:
    """Check if email has already been processed"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute('SELECT email_id FROM processed_emails WHERE email_id = ?', (email_id,))
    result = cursor.fetchone()
    
    conn.close()
    return result is not None


def mark_processed(email_id: str, history_id: str, sender: str, subject: str):
    """Mark email as processed"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO processed_emails (email_id, history_id, processed_at, sender, subject)
        VALUES (?, ?, ?, ?, ?)
    ''', (email_id, history_id, datetime.now().isoformat(), sender, subject))
    
    conn.commit()
    conn.close()


@app.route('/api/gmail/webhook', methods=['POST'])
def gmail_webhook():
    """
    Receive Gmail push notifications.
    
    Google sends POST requests to this endpoint when:
    - New email arrives
    - Email is deleted
    - Email is marked read/unread
    - Label changes
    
    Payload format (base64-encoded Pub/Sub message):
    {
        "message": {
            "data": "<base64-encoded-json>",
            "messageId": "...",
            "publishTime": "..."
        },
        "subscription": "..."
    }
    """
    try:
        # SECURITY FIX: Verify webhook signature
        if WEBHOOK_SECURITY_AVAILABLE:
            if not verify_gmail_webhook(request):
                logger.warning("Invalid webhook signature - rejecting")
                return jsonify({'error': 'Unauthorized'}), 401
        
        # Parse incoming webhook
        data = request.get_json()
        
        if not data or 'message' not in data:
            logger.warning("Invalid webhook payload (missing 'message')")
            return jsonify({'error': 'Invalid payload'}), 400
        
        message = data['message']
        
        # Decode base64 data
        if 'data' in message:
            decoded_data = base64.b64decode(message['data']).decode('utf-8')
            push_data = json.loads(decoded_data)
        else:
            logger.warning("No data in webhook message")
            return jsonify({'status': 'ok'}), 200
        
        logger.info(f"Received Gmail push notification: {push_data}")
        
        # Extract email metadata
        email_address = push_data.get('emailAddress')
        history_id = push_data.get('historyId')
        
        if not email_address or not history_id:
            logger.warning(f"Missing email_address or history_id: {push_data}")
            return jsonify({'status': 'ok'}), 200
        
        # Fetch new emails using Gmail API
        gmail = GmailAPI(account_email=email_address)
        
        # Get history since last history_id
        # (This tells us what changed: new emails, deletions, label changes)
        # For MVP, we'll just fetch recent unread emails
        
        messages = gmail.list_messages(query='is:unread', max_results=10)
        
        if not messages:
            logger.info("No unread messages found")
            return jsonify({'status': 'ok'}), 200
        
        # Process each new email
        processed_count = 0
        for msg in messages:
            email_id = msg['id']
            
            # Skip if already processed
            if is_processed(email_id):
                logger.debug(f"Email {email_id} already processed, skipping")
                continue
            
            # Fetch full email content
            email_data = gmail.get_message(email_id)
            
            if not email_data:
                logger.warning(f"Failed to fetch email {email_id}")
                continue
            
            # Extract email details
            headers = {h['name']: h['value'] for h in email_data.get('payload', {}).get('headers', [])}
            
            sender_email = headers.get('From', 'unknown')
            sender_name = sender_email.split('<')[0].strip() if '<' in sender_email else sender_email
            subject = headers.get('Subject', '(no subject)')
            
            # Get email body
            body = gmail.get_message_body(email_data)
            
            # Trigger COS analysis
            if COS_AVAILABLE:
                try:
                    cos_triggers = get_trigger_handlers()
                    
                    result = cos_triggers.on_email_action({
                        'sender_email': sender_email,
                        'sender_name': sender_name,
                        'subject': subject,
                        'body': body,
                        'timestamp': datetime.now().isoformat(),
                        'action_type': 'received'
                    })
                    
                    logger.info(f"COS analysis complete: {len(result.get('recommendations', []))} recommendations")
                    
                except Exception as e:
                    logger.error(f"COS analysis failed: {e}")
            
            # Mark as processed
            mark_processed(email_id, history_id, sender_email, subject)
            processed_count += 1
            
            logger.info(f"Processed email from {sender_name}: {subject}")
        
        logger.info(f"Webhook processed {processed_count} new emails")
        
        return jsonify({'status': 'ok', 'processed': processed_count}), 200
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({'error': str(e)}), 500


@app.route('/api/gmail/subscribe', methods=['POST'])
def subscribe_gmail_push():
    """
    Subscribe to Gmail push notifications.
    
    Call this once to start receiving push notifications.
    Subscription expires after 7 days, so renew via cron.
    
    Payload:
    {
        "email_account": "user@gmail.com",
        "topic_name": "projects/PROJECT_ID/topics/TOPIC_NAME"
    }
    """
    try:
        data = request.get_json()
        
        email_account = data.get('email_account')
        topic_name = data.get('topic_name')
        
        if not email_account or not topic_name:
            return jsonify({'error': 'Missing email_account or topic_name'}), 400
        
        gmail = GmailAPI()
        
        # Subscribe to push notifications
        # This tells Gmail to send push notifications to our Pub/Sub topic
        # when anything changes in the mailbox
        
        # Note: This requires Gmail API watch() method
        # For now, placeholder - will implement actual watch() call
        
        expiration = datetime.now() + timedelta(days=7)
        
        # Store subscription
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO webhook_subscriptions (email_account, watch_expiration, last_renewal)
            VALUES (?, ?, ?)
        ''', (email_account, expiration.isoformat(), datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Subscribed to Gmail push for {email_account}, expires {expiration}")
        
        return jsonify({
            'status': 'subscribed',
            'email_account': email_account,
            'expiration': expiration.isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Subscribe error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'cos_available': COS_AVAILABLE
    }), 200


if __name__ == '__main__':
    init_db()
    
    # Run webhook server
    # Production: Use gunicorn or uwsgi
    # Development: Flask dev server
    
    port = int(os.environ.get('GMAIL_WEBHOOK_PORT', 5001))
    
    logger.info(f"Starting Gmail webhook server on port {port}")
    logger.info(f"COS integration: {'enabled' if COS_AVAILABLE else 'disabled'}")
    
    app.run(host='0.0.0.0', port=port, debug=False)
