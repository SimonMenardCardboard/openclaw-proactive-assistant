#!/usr/bin/env python3
"""
Auto-Renewal Cron for Gmail/Calendar Watch Subscriptions
Renews push notification subscriptions before they expire
Run every 6 hours via cron
"""

import os
import sys
import json
import sqlite3
import logging
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

# Setup logging
log_path = Path.home() / '.openclaw/workspace/integrations/intelligence/webhooks/auto_renewal.log'
log_path.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [AUTO-RENEWAL] %(message)s',
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database
OAUTH_DB = Path.home() / '.openclaw/workspace/integrations/intelligence/webhooks/oauth_tokens.db'
WEBHOOK_DB = Path.home() / '.openclaw/workspace/integrations/intelligence/webhooks/webhook_state.db'


class WatchRenewal:
    """Gmail/Calendar watch subscription renewal"""
    
    def __init__(self):
        self._init_database()
    
    def _init_database(self):
        """Initialize watch subscriptions table"""
        conn = sqlite3.connect(str(WEBHOOK_DB))
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watch_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_email TEXT NOT NULL,
                watch_type TEXT NOT NULL,
                subscription_id TEXT,
                resource_id TEXT,
                expiration_timestamp INTEGER,
                last_renewed TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(account_email, watch_type)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_oauth_accounts(self) -> List[Dict]:
        """Get all OAuth accounts (Gmail, Outlook)"""
        conn = sqlite3.connect(str(OAUTH_DB))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT account_id, email, account_type, access_token, refresh_token
            FROM oauth_tokens
            WHERE account_type IN ('gmail', 'outlook')
              AND access_token IS NOT NULL
        ''')
        
        accounts = []
        for row in cursor.fetchall():
            accounts.append({
                'account_id': row[0],
                'email': row[1],
                'account_type': row[2],
                'access_token': row[3],
                'refresh_token': row[4]
            })
        
        conn.close()
        return accounts
    
    def refresh_access_token(self, account: Dict) -> Optional[str]:
        """Refresh OAuth access token"""
        if account['account_type'] != 'gmail':
            # TODO: Implement for Outlook
            return None
        
        # Gmail token refresh
        try:
            credentials_path = Path.home() / '.openclaw/workspace/integrations/intelligence/setup/oauth_credentials.json'
            
            if not credentials_path.exists():
                logger.error(f"OAuth credentials not found: {credentials_path}")
                return None
            
            with open(credentials_path) as f:
                creds = json.load(f)
            
            client_id = creds['installed']['client_id']
            client_secret = creds['installed']['client_secret']
            
            response = requests.post('https://oauth2.googleapis.com/token', data={
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': account['refresh_token'],
                'grant_type': 'refresh_token'
            })
            
            if response.status_code == 200:
                data = response.json()
                new_access_token = data['access_token']
                
                # Update database
                conn = sqlite3.connect(str(OAUTH_DB))
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE oauth_tokens
                    SET access_token = ?
                    WHERE account_id = ?
                ''', (new_access_token, account['account_id']))
                
                conn.commit()
                conn.close()
                
                logger.info(f"Refreshed token for {account['email']}")
                return new_access_token
            
            else:
                logger.error(f"Token refresh failed: {response.status_code} {response.text}")
                return None
        
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return None
    
    def renew_gmail_watch(self, account: Dict) -> bool:
        """Renew Gmail push notification watch"""
        access_token = account['access_token']
        
        # Refresh token if needed
        if not access_token:
            access_token = self.refresh_access_token(account)
        
        if not access_token:
            return False
        
        try:
            # Get webhook URL from ngrok
            ngrok_url_file = Path.home() / '.openclaw/workspace/integrations/intelligence/setup/ngrok_url.txt'
            
            if not ngrok_url_file.exists():
                logger.error("ngrok URL not found")
                return False
            
            ngrok_url = ngrok_url_file.read_text().strip()
            
            # Gmail watch endpoint
            url = 'https://gmail.googleapis.com/gmail/v1/users/me/watch'
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Read GCP config for topic name
            gcp_config_path = Path.home() / '.openclaw/workspace/integrations/intelligence/setup/gcp_config.json'
            
            if gcp_config_path.exists():
                with open(gcp_config_path) as f:
                    gcp_config = json.load(f)
                    topic_name = gcp_config.get('gmail_topic', 'projects/openclaw-cos/topics/gmail-push-notifications')
            else:
                topic_name = 'projects/openclaw-cos/topics/gmail-push-notifications'
            
            payload = {
                'labelIds': ['INBOX'],
                'topicName': topic_name
            }
            
            response = requests.post(url, headers=headers, json=payload)
            
            if response.status_code in [200, 201]:
                data = response.json()
                
                # Save subscription info
                conn = sqlite3.connect(str(WEBHOOK_DB))
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO watch_subscriptions
                    (account_email, watch_type, subscription_id, resource_id, 
                     expiration_timestamp, last_renewed)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    account['email'],
                    'gmail',
                    data.get('historyId'),
                    None,
                    data.get('expiration'),
                    datetime.now().isoformat()
                ))
                
                conn.commit()
                conn.close()
                
                logger.info(f"✅ Renewed Gmail watch for {account['email']}")
                return True
            
            else:
                logger.error(f"Gmail watch renewal failed: {response.status_code} {response.text}")
                return False
        
        except Exception as e:
            logger.error(f"Gmail watch renewal error: {e}")
            return False
    
    def renew_calendar_watch(self, account: Dict) -> bool:
        """Renew Calendar push notification watch"""
        access_token = account['access_token']
        
        # Refresh token if needed
        if not access_token:
            access_token = self.refresh_access_token(account)
        
        if not access_token:
            return False
        
        try:
            # Get webhook URL
            ngrok_url_file = Path.home() / '.openclaw/workspace/integrations/intelligence/setup/ngrok_url.txt'
            
            if not ngrok_url_file.exists():
                logger.error("ngrok URL not found")
                return False
            
            ngrok_url = ngrok_url_file.read_text().strip()
            webhook_url = f"{ngrok_url}/calendar/webhook"
            
            # Calendar watch endpoint
            url = 'https://www.googleapis.com/calendar/v3/calendars/primary/events/watch'
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Generate unique channel ID
            import uuid
            channel_id = f"calendar-{account['email']}-{uuid.uuid4().hex[:8]}"
            
            payload = {
                'id': channel_id,
                'type': 'web_hook',
                'address': webhook_url,
                'expiration': int((datetime.now() + timedelta(days=7)).timestamp() * 1000)  # 7 days
            }
            
            response = requests.post(url, headers=headers, json=payload)
            
            if response.status_code in [200, 201]:
                data = response.json()
                
                # Save subscription info
                conn = sqlite3.connect(str(WEBHOOK_DB))
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO watch_subscriptions
                    (account_email, watch_type, subscription_id, resource_id,
                     expiration_timestamp, last_renewed)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    account['email'],
                    'calendar',
                    channel_id,
                    data.get('resourceId'),
                    data.get('expiration'),
                    datetime.now().isoformat()
                ))
                
                conn.commit()
                conn.close()
                
                logger.info(f"✅ Renewed Calendar watch for {account['email']}")
                return True
            
            else:
                logger.error(f"Calendar watch renewal failed: {response.status_code} {response.text}")
                return False
        
        except Exception as e:
            logger.error(f"Calendar watch renewal error: {e}")
            return False
    
    def renew_all(self):
        """Renew all watch subscriptions"""
        logger.info("=== Starting Watch Renewal ===")
        
        accounts = self.get_oauth_accounts()
        
        if not accounts:
            logger.info("No OAuth accounts configured")
            return
        
        logger.info(f"Found {len(accounts)} OAuth accounts")
        
        for account in accounts:
            try:
                # Renew Gmail watch
                self.renew_gmail_watch(account)
                
                # Renew Calendar watch
                self.renew_calendar_watch(account)
            
            except Exception as e:
                logger.error(f"Error renewing for {account['email']}: {e}")
        
        logger.info("=== Watch Renewal Complete ===")
    
    def check_expiring_subscriptions(self) -> List[Dict]:
        """Get subscriptions expiring in next 24 hours"""
        conn = sqlite3.connect(str(WEBHOOK_DB))
        cursor = conn.cursor()
        
        # 24 hours from now (in milliseconds)
        threshold = int((datetime.now() + timedelta(hours=24)).timestamp() * 1000)
        
        cursor.execute('''
            SELECT account_email, watch_type, expiration_timestamp, last_renewed
            FROM watch_subscriptions
            WHERE expiration_timestamp < ?
        ''', (threshold,))
        
        expiring = []
        for row in cursor.fetchall():
            expiring.append({
                'account_email': row[0],
                'watch_type': row[1],
                'expiration_timestamp': row[2],
                'last_renewed': row[3]
            })
        
        conn.close()
        return expiring


def main():
    """Main entry point"""
    renewal = WatchRenewal()
    
    # Check for expiring subscriptions
    expiring = renewal.check_expiring_subscriptions()
    
    if expiring:
        logger.warning(f"Found {len(expiring)} expiring subscriptions")
        for sub in expiring:
            exp_dt = datetime.fromtimestamp(sub['expiration_timestamp'] / 1000)
            logger.warning(f"  {sub['account_email']} {sub['watch_type']} expires at {exp_dt}")
    
    # Renew all
    renewal.renew_all()


if __name__ == '__main__':
    sys.exit(main())
