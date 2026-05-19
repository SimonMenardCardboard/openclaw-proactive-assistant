#!/usr/bin/env python3
"""
Webhook Registration Script

Registers Gmail Push API and Calendar Watch API webhooks for a user.
Run once per user during VM deployment.

Usage:
    python3 register_webhooks.py --user simon@example.com --domain simon.transmogrifier.app
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path.home() / '.openclaw/workspace/transmogrifier/openclaw-proactive-assistant'))

try:
    from gmail_api import GmailAPI
    from calendar_api import CalendarAPI
    APIS_AVAILABLE = True
except ImportError:
    APIS_AVAILABLE = False
    print("⚠️  Gmail/Calendar APIs not available")


def register_gmail_webhook(user_email: str, webhook_url: str, token_path: str):
    """
    Register Gmail Push API webhook.
    
    Args:
        user_email: User's email address
        webhook_url: Public webhook URL (e.g. https://simon.transmogrifier.app/webhooks/gmail)
        token_path: Path to OAuth token file
    """
    print(f"\n📧 Registering Gmail webhook for {user_email}...")
    
    if not APIS_AVAILABLE:
        print("  ❌ Gmail API not available")
        return False
    
    try:
        gmail = GmailAPI(token_path=token_path)
        
        # Gmail uses Cloud Pub/Sub for push notifications
        # Topic must be created in Google Cloud Console first
        topic_name = f"projects/YOUR_PROJECT_ID/topics/gmail-push-{user_email.replace('@', '-at-')}"
        
        # Watch user's inbox
        request_body = {
            'topicName': topic_name,
            'labelIds': ['INBOX']  # Watch inbox only (can expand to all labels)
        }
        
        response = gmail.service.users().watch(
            userId='me',
            body=request_body
        ).execute()
        
        print(f"  ✅ Gmail webhook registered")
        print(f"     Expires: {datetime.fromtimestamp(int(response['expiration'])/1000).isoformat()}")
        print(f"     History ID: {response['historyId']}")
        
        # Save subscription details
        subscription_file = Path.home() / '.openclaw/workspace/webhooks/gmail_subscription.json'
        subscription_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(subscription_file, 'w') as f:
            json.dump({
                'user_email': user_email,
                'webhook_url': webhook_url,
                'topic_name': topic_name,
                'expiration': response['expiration'],
                'history_id': response['historyId'],
                'registered_at': datetime.now().isoformat()
            }, f, indent=2)
        
        print(f"  📝 Subscription saved to {subscription_file}")
        
        return True
    
    except Exception as e:
        print(f"  ❌ Failed to register Gmail webhook: {e}")
        return False


def register_calendar_webhook(user_email: str, webhook_url: str, token_path: str):
    """
    Register Calendar Watch API webhook.
    
    Args:
        user_email: User's email address
        webhook_url: Public webhook URL (e.g. https://simon.transmogrifier.app/webhooks/calendar)
        token_path: Path to OAuth token file
    """
    print(f"\n📅 Registering Calendar webhook for {user_email}...")
    
    if not APIS_AVAILABLE:
        print("  ❌ Calendar API not available")
        return False
    
    try:
        calendar = CalendarAPI(token_path=token_path)
        
        # Watch primary calendar for changes
        channel_id = f"calendar-{user_email.replace('@', '-at-')}-{int(datetime.now().timestamp())}"
        
        request_body = {
            'id': channel_id,
            'type': 'web_hook',
            'address': webhook_url,
            'expiration': int((datetime.now() + timedelta(days=7)).timestamp() * 1000)  # 7 days
        }
        
        response = calendar.service.events().watch(
            calendarId='primary',
            body=request_body
        ).execute()
        
        print(f"  ✅ Calendar webhook registered")
        print(f"     Channel ID: {response['id']}")
        print(f"     Resource ID: {response['resourceId']}")
        print(f"     Expires: {datetime.fromtimestamp(int(response['expiration'])/1000).isoformat()}")
        
        # Save subscription details
        subscription_file = Path.home() / '.openclaw/workspace/webhooks/calendar_subscription.json'
        subscription_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(subscription_file, 'w') as f:
            json.dump({
                'user_email': user_email,
                'webhook_url': webhook_url,
                'channel_id': response['id'],
                'resource_id': response['resourceId'],
                'expiration': response['expiration'],
                'registered_at': datetime.now().isoformat()
            }, f, indent=2)
        
        print(f"  📝 Subscription saved to {subscription_file}")
        
        return True
    
    except Exception as e:
        print(f"  ❌ Failed to register Calendar webhook: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Register webhooks for a Transmogrifier user")
    parser.add_argument('--user', required=True, help='User email address')
    parser.add_argument('--domain', required=True, help='User VM domain (e.g. simon.transmogrifier.app)')
    parser.add_argument('--gmail-token', default=None, help='Path to Gmail OAuth token')
    parser.add_argument('--calendar-token', default=None, help='Path to Calendar OAuth token')
    parser.add_argument('--skip-gmail', action='store_true', help='Skip Gmail webhook registration')
    parser.add_argument('--skip-calendar', action='store_true', help='Skip Calendar webhook registration')
    
    args = parser.parse_args()
    
    # Default token paths
    if not args.gmail_token:
        args.gmail_token = str(Path.home() / f'.openclaw/workspace/oauth_tokens/{args.user}_gmail_token.json')
    
    if not args.calendar_token:
        args.calendar_token = str(Path.home() / f'.openclaw/workspace/oauth_tokens/{args.user}_calendar_token.json')
    
    print(f"🔗 Webhook Registration for {args.user}")
    print(f"   Domain: {args.domain}")
    print(f"   Gmail token: {args.gmail_token}")
    print(f"   Calendar token: {args.calendar_token}")
    print()
    
    success_count = 0
    
    # Register Gmail webhook
    if not args.skip_gmail:
        gmail_webhook_url = f"https://{args.domain}/webhooks/gmail"
        if register_gmail_webhook(args.user, gmail_webhook_url, args.gmail_token):
            success_count += 1
    
    # Register Calendar webhook
    if not args.skip_calendar:
        calendar_webhook_url = f"https://{args.domain}/webhooks/calendar"
        if register_calendar_webhook(args.user, calendar_webhook_url, args.calendar_token):
            success_count += 1
    
    print()
    print(f"✅ Registered {success_count} webhook(s)")
    
    if success_count > 0:
        print()
        print("⏰ Remember to setup auto-renewal cron:")
        print("   crontab -e")
        print("   0 0 */6 * * cd ~/transmogrifier && python3 webhooks/auto_renewal_cron.py")


if __name__ == '__main__':
    main()
