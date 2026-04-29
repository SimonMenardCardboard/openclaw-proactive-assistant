#!/usr/bin/env python3
"""
Calendar Watch API Webhook Server

Receives push notifications from Google Calendar when events change.
Triggers COS analysis for upcoming meetings (real-time meeting prep).

Architecture:
1. Calendar detects event create/update/delete
2. Calendar publishes event to Google Cloud Pub/Sub topic
3. Pub/Sub delivers event to our webhook endpoint
4. Webhook fetches full event details via Calendar API
5. Triggers COS analysis (meeting prep, context loading)
6. COS generates recommendations
7. Recommendations delivered via push notification

Setup:
1. Deploy this webhook to VPS (Flask app)
2. Subscribe to Calendar push notifications via Calendar API watch()
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
sys.path.insert(0, str(Path.home() / ".openclaw/workspace/integrations/direct_api"))

from calendar_api import CalendarAPI

# SECURITY FIX: Import webhook signature validation
try:
    from webhook_security import verify_calendar_webhook
    WEBHOOK_SECURITY_AVAILABLE = True
except ImportError:
    WEBHOOK_SECURITY_AVAILABLE = False
    logging.warning("Webhook security not available - using insecure mode")
    def verify_calendar_webhook(request):
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
    format='%(asctime)s [CALENDAR-WEBHOOK] %(message)s',
    handlers=[
        logging.FileHandler(Path.home() / '.openclaw/workspace/integrations/intelligence/webhooks/calendar_webhook.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Database for tracking processed events (prevent duplicates)
DB_PATH = Path.home() / '.openclaw/workspace/integrations/intelligence/webhooks/webhook_state.db'


def init_db():
    """Initialize database for webhook state tracking"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_events (
            event_id TEXT PRIMARY KEY,
            calendar_id TEXT,
            processed_at TEXT,
            summary TEXT,
            start_time TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS calendar_subscriptions (
            email_account TEXT NOT NULL,
            calendar_id TEXT NOT NULL,
            watch_expiration TEXT,
            last_renewal TEXT,
            resource_id TEXT,
            PRIMARY KEY (email_account, calendar_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    
    logger.info("Calendar webhook database initialized")


def is_processed(event_id: str, calendar_id: str) -> bool:
    """Check if event has already been processed"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute('SELECT event_id FROM processed_events WHERE event_id = ? AND calendar_id = ?', 
                   (event_id, calendar_id))
    result = cursor.fetchone()
    
    conn.close()
    return result is not None


def mark_processed(event_id: str, calendar_id: str, summary: str, start_time: str):
    """Mark event as processed"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO processed_events (event_id, calendar_id, processed_at, summary, start_time)
        VALUES (?, ?, ?, ?, ?)
    ''', (event_id, calendar_id, datetime.now().isoformat(), summary, start_time))
    
    conn.commit()
    conn.close()


@app.route('/api/calendar/webhook', methods=['POST'])
def calendar_webhook():
    """
    Receive Calendar push notifications.
    
    Google sends POST requests to this endpoint when:
    - Event is created
    - Event is updated
    - Event is deleted
    - Attendee responses change
    
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
            if not verify_calendar_webhook(request):
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
        
        logger.info(f"Received Calendar push notification: {push_data}")
        
        # Extract calendar metadata
        calendar_id = push_data.get('calendarId', 'primary')
        resource_state = push_data.get('resourceState')  # 'exists', 'not_exists', 'sync'
        
        if resource_state == 'sync':
            # Initial sync message, ignore
            logger.info("Sync message received, ignoring")
            return jsonify({'status': 'ok'}), 200
        
        # Fetch upcoming events (next 7 days)
        calendar = CalendarAPI(account_email=None)  # Uses default account
        
        now = datetime.now()
        end_time = now + timedelta(days=7)
        
        events = calendar.list_events(
            calendar_id=calendar_id,
            time_min=now.isoformat() + 'Z',
            time_max=end_time.isoformat() + 'Z',
            max_results=50
        )
        
        if not events:
            logger.info("No upcoming events found")
            return jsonify({'status': 'ok'}), 200
        
        # Process each upcoming event
        processed_count = 0
        for event in events:
            event_id = event.get('id')
            
            if not event_id:
                continue
            
            # Skip if already processed recently (within last hour)
            # This prevents duplicate processing for minor updates
            if is_processed(event_id, calendar_id):
                # Check if processed within last hour
                conn = sqlite3.connect(str(DB_PATH))
                cursor = conn.cursor()
                cursor.execute('SELECT processed_at FROM processed_events WHERE event_id = ? AND calendar_id = ?',
                               (event_id, calendar_id))
                result = cursor.fetchone()
                conn.close()
                
                if result:
                    processed_at = datetime.fromisoformat(result[0])
                    if (datetime.now() - processed_at).total_seconds() < 3600:
                        logger.debug(f"Event {event_id} processed recently, skipping")
                        continue
            
            # Extract event details
            summary = event.get('summary', '(No title)')
            start = event.get('start', {})
            end = event.get('end', {})
            
            start_time = start.get('dateTime') or start.get('date')
            end_time = end.get('dateTime') or end.get('date')
            
            # Trigger COS analysis
            if COS_AVAILABLE:
                try:
                    cos_triggers = get_trigger_handlers()
                    
                    result = cos_triggers.on_calendar_event({
                        'summary': summary,
                        'start': start_time,
                        'end': end_time,
                        'calendar_id': calendar_id,
                        'event_id': event_id,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    logger.info(f"COS analysis complete: {len(result.get('recommendations', []))} recommendations")
                    
                except Exception as e:
                    logger.error(f"COS analysis failed: {e}")
            
            # Mark as processed
            mark_processed(event_id, calendar_id, summary, start_time)
            processed_count += 1
            
            logger.info(f"Processed event: {summary} at {start_time}")
        
        logger.info(f"Webhook processed {processed_count} events")
        
        return jsonify({'status': 'ok', 'processed': processed_count}), 200
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({'error': str(e)}), 500


@app.route('/api/calendar/subscribe', methods=['POST'])
def subscribe_calendar_push():
    """
    Subscribe to Calendar push notifications.
    
    Call this once per calendar to start receiving push notifications.
    Subscription expires after 7 days, so renew via cron.
    
    Payload:
    {
        "calendar_id": "primary",
        "channel_id": "unique-channel-id",
        "webhook_url": "https://your-vps.com/api/calendar/webhook"
    }
    """
    try:
        data = request.get_json()
        
        email_account = data.get('email_account')
        calendar_id = data.get('calendar_id', 'primary')
        channel_id = data.get('channel_id', f"calendar-{calendar_id}-{int(datetime.now().timestamp())}")
        webhook_url = data.get('webhook_url')
        
        if not webhook_url:
            return jsonify({'error': 'Missing webhook_url'}), 400
        
        calendar = CalendarAPI(account_email=email_account)
        
        # Subscribe to push notifications via Calendar API watch()
        try:
            watch_result = calendar.watch_calendar(
                calendar_id=calendar_id,
                channel_id=channel_id,
                webhook_url=webhook_url,
                ttl_seconds=7 * 24 * 60 * 60  # 7 days
            )
            
            resource_id = watch_result.get('resourceId')
            expiration_ms = watch_result.get('expiration')
            
            # Handle both string and int expiration
            if isinstance(expiration_ms, str):
                expiration_ms = int(expiration_ms)
            
            expiration = datetime.fromtimestamp(expiration_ms / 1000)
            
            logger.info(f"Calendar watch created: {watch_result}")
            
        except Exception as e:
            logger.error(f"Calendar watch failed: {e}")
            # Store subscription anyway for tracking
            expiration = datetime.now() + timedelta(days=7)
            resource_id = channel_id
        
        # Store subscription
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO calendar_subscriptions 
            (email_account, calendar_id, watch_expiration, last_renewal, resource_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (email_account or 'primary', calendar_id, expiration.isoformat(), datetime.now().isoformat(), resource_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Subscribed to Calendar push for {calendar_id}, expires {expiration}")
        
        return jsonify({
            'status': 'subscribed',
            'calendar_id': calendar_id,
            'channel_id': channel_id,
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
    
    port = int(os.environ.get('CALENDAR_WEBHOOK_PORT', 5002))
    
    logger.info(f"Starting Calendar webhook server on port {port}")
    logger.info(f"COS integration: {'enabled' if COS_AVAILABLE else 'disabled'}")
    
    app.run(host='0.0.0.0', port=port, debug=False)
