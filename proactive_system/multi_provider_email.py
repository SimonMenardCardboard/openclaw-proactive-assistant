#!/usr/bin/env python3
"""
Multi-Provider Email Connector
Supports Gmail (OAuth), Microsoft (OAuth), and IMAP (username/password)
"""

import json
import imaplib
import email
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GmailConnector:
    """Gmail via OAuth."""
    
    def __init__(self, email_addr: str, token_file: Path):
        self.email = email_addr
        self.token_file = token_file
        self.provider = 'google'
        
        # Use Gmail API
        try:
            from gmail_api import GmailAPI
            self.api = GmailAPI(email=email_addr, token_file=token_file)
        except Exception as e:
            logger.warning(f"Gmail API init failed: {e}")
            self.api = None
    
    def get_unread_messages(self, hours_back: int = 1) -> List[Dict]:
        """Get unread messages from last N hours."""
        if not self.api:
            return []
        
        return self.api.get_unread_messages(hours_back=hours_back)


class MicrosoftConnector:
    """Microsoft Outlook via OAuth."""
    
    def __init__(self, email_addr: str, token_file: Path):
        self.email = email_addr
        self.token_file = token_file
        self.provider = 'microsoft'
        
        # Use Microsoft Graph API
        try:
            from microsoft_graph_api import MicrosoftGraphAPI
            self.api = MicrosoftGraphAPI(email=email_addr, token_file=token_file)
        except Exception as e:
            logger.warning(f"Microsoft Graph init failed: {e}")
            self.api = None
    
    def get_unread_messages(self, hours_back: int = 1) -> List[Dict]:
        """Get unread messages from last N hours."""
        if not self.api:
            return []
        
        return self.api.get_unread_emails(hours_back=hours_back)


class IMAPConnector:
    """Generic IMAP connector for any provider."""
    
    def __init__(self, email_addr: str, config_file: Path):
        self.email = email_addr
        self.config_file = config_file
        self.provider = 'imap'
        
        # Load IMAP config
        with open(config_file) as f:
            config = json.load(f)
        
        self.imap_server = config['imap_server']
        self.imap_port = config.get('imap_port', 993)
        self.username = config['username']
        self.password = config['password']
        self.use_ssl = config.get('use_ssl', True)
    
    def get_unread_messages(self, hours_back: int = 1) -> List[Dict]:
        """Get unread messages from last N hours via IMAP."""
        messages = []
        
        try:
            # Connect to IMAP server
            if self.use_ssl:
                mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            else:
                mail = imaplib.IMAP4(self.imap_server, self.imap_port)
            
            mail.login(self.username, self.password)
            mail.select('INBOX')
            
            # Search for unread messages
            since_date = (datetime.now() - timedelta(hours=hours_back)).strftime('%d-%b-%Y')
            _, message_numbers = mail.search(None, 'UNSEEN', f'SINCE {since_date}')
            
            for num in message_numbers[0].split()[:20]:  # Limit to 20 messages
                _, msg_data = mail.fetch(num, '(RFC822)')
                
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        messages.append({
                            'id': num.decode(),
                            'from': msg.get('From', ''),
                            'subject': msg.get('Subject', ''),
                            'date': msg.get('Date', ''),
                            'body': self._get_body(msg),
                            '_source_provider': 'imap',
                            '_source_email': self.email
                        })
            
            mail.close()
            mail.logout()
            
            logger.info(f"[IMAP] {self.email}: Found {len(messages)} unread")
            
        except Exception as e:
            logger.error(f"[IMAP] Failed to check {self.email}: {e}")
        
        return messages
    
    def _get_body(self, msg) -> str:
        """Extract message body."""
        body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        body = part.get_payload(decode=True).decode()
                        break
                    except:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode()
            except:
                pass
        
        return body[:500]  # First 500 chars


class MultiProviderEmailConnector:
    """Aggregates email from multiple providers for a user."""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.connectors = []
        
        # Load user preferences
        from user_preferences import UserPreferences
        prefs = UserPreferences(user_id)
        
        # Initialize connectors for all email-enabled accounts
        token_dir = Path.home() / '.openclaw/tokens'
        
        # Google accounts
        for account in prefs.get_accounts('google', feature='email'):
            token_file = token_dir / account['token_file']
            if token_file.exists():
                self.connectors.append({
                    'provider': 'google',
                    'email': account['email'],
                    'label': account['label'],
                    'connector': GmailConnector(account['email'], token_file)
                })
        
        # Microsoft accounts
        for account in prefs.get_accounts('microsoft', feature='email'):
            token_file = token_dir / account['token_file']
            if token_file.exists():
                self.connectors.append({
                    'provider': 'microsoft',
                    'email': account['email'],
                    'label': account['label'],
                    'connector': MicrosoftConnector(account['email'], token_file)
                })
        
        # IMAP accounts
        for account in prefs.get_accounts('imap', feature='email'):
            config_file = token_dir / account['token_file']
            if config_file.exists():
                self.connectors.append({
                    'provider': 'imap',
                    'email': account['email'],
                    'label': account['label'],
                    'connector': IMAPConnector(account['email'], config_file)
                })
        
        logger.info(f"✅ Initialized {len(self.connectors)} email connectors for {user_id}")
    
    def get_all_unread_messages(self, hours_back: int = 1) -> List[Dict]:
        """Get unread messages from ALL connected accounts."""
        all_messages = []
        
        for conn in self.connectors:
            try:
                logger.info(f"📧 Checking {conn['label']} ({conn['email']})")
                messages = conn['connector'].get_unread_messages(hours_back)
                
                # Tag with account info
                for msg in messages:
                    msg['_account_label'] = conn['label']
                    msg['_account_email'] = conn['email']
                
                all_messages.extend(messages)
                
            except Exception as e:
                logger.error(f"❌ Failed to check {conn['label']}: {e}")
        
        logger.info(f"📊 Total unread: {len(all_messages)} from {len(self.connectors)} accounts")
        return all_messages


if __name__ == '__main__':
    # Test multi-provider email
    connector = MultiProviderEmailConnector(user_id='test_user')
    
    messages = connector.get_all_unread_messages(hours_back=24)
    
    print(f"\n📬 Found {len(messages)} total unread messages")
    for msg in messages[:5]:
        print(f"  • [{msg.get('_account_label')}] {msg.get('from', 'Unknown')}: {msg.get('subject', 'No subject')}")
