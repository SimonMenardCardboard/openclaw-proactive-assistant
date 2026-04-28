#!/usr/bin/env python3
"""
Gmail API Implementation
Full OAuth support for Gmail reading
"""

import json
import base64
from pathlib import Path
from typing import List, Dict
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GmailAPI:
    """Gmail API with OAuth2 authentication."""
    
    def __init__(self, email: str, token_file: Path):
        self.email = email
        self.token_file = token_file
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate using token file."""
        try:
            with open(self.token_file) as f:
                token_data = json.load(f)
            
            creds = Credentials(
                token=token_data.get('access_token'),
                refresh_token=token_data.get('refresh_token'),
                token_uri='https://oauth2.googleapis.com/token',
                client_id=token_data.get('client_id'),
                client_secret=token_data.get('client_secret')
            )
            
            self.service = build('gmail', 'v1', credentials=creds)
            logger.info(f"[Gmail API] Authenticated: {self.email}")
            
        except Exception as e:
            logger.error(f"[Gmail API] Auth failed for {self.email}: {e}")
            self.service = None
    
    def get_unread_messages(self, hours_back: int = 1, max_results: int = 20) -> List[Dict]:
        """Get unread messages from last N hours."""
        if not self.service:
            return []
        
        try:
            # Calculate time filter
            after_timestamp = int((datetime.now() - timedelta(hours=hours_back)).timestamp())
            
            # Search query: unread messages after timestamp
            query = f'is:unread after:{after_timestamp}'
            
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                logger.info(f"[Gmail API] {self.email}: No unread messages")
                return []
            
            # Fetch full message details
            detailed_messages = []
            for msg in messages:
                msg_data = self.service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()
                
                detailed_messages.append(self._parse_message(msg_data))
            
            logger.info(f"[Gmail API] {self.email}: {len(detailed_messages)} unread")
            return detailed_messages
            
        except HttpError as e:
            logger.error(f"[Gmail API] Error fetching messages: {e}")
            return []
    
    def _parse_message(self, msg_data: Dict) -> Dict:
        """Parse Gmail message into standard format."""
        headers = {h['name']: h['value'] for h in msg_data['payload']['headers']}
        
        return {
            'id': msg_data['id'],
            'thread_id': msg_data['threadId'],
            'from': headers.get('From', ''),
            'to': headers.get('To', ''),
            'subject': headers.get('Subject', ''),
            'date': headers.get('Date', ''),
            'snippet': msg_data.get('snippet', ''),
            'body': self._get_body(msg_data['payload']),
            'labels': msg_data.get('labelIds', []),
            '_provider': 'gmail',
            '_email': self.email
        }
    
    def _get_body(self, payload: Dict) -> str:
        """Extract message body from payload."""
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
        
        if 'body' in payload and 'data' in payload['body']:
            return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
        
        return ''


if __name__ == '__main__':
    # Test Gmail API
    token_file = Path.home() / '.openclaw/tokens/default_google_personal.json'
    
    if token_file.exists():
        gmail = GmailAPI(email='lacrosseguy76665@gmail.com', token_file=token_file)
        messages = gmail.get_unread_messages(hours_back=24)
        
        print(f"\n📬 Found {len(messages)} unread messages")
        for msg in messages[:5]:
            print(f"  • From: {msg['from']}")
            print(f"    Subject: {msg['subject']}")
            print(f"    Snippet: {msg['snippet'][:80]}...")
            print()
    else:
        print(f"❌ Token file not found: {token_file}")
