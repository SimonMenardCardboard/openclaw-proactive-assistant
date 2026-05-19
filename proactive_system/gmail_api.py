#!/usr/bin/env python3
"""
Gmail API Implementation
Full OAuth support for Gmail reading + 30-day analysis
"""

import json
import base64
import re
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict
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
    
    def get_all_messages_30_days(self, max_results: int = 500) -> List[Dict]:
        """Get ALL messages from last 30 days (not just unread)."""
        if not self.service:
            logger.error("[Gmail API] Not authenticated")
            return []
        
        try:
            # Calculate 30 days ago timestamp
            after_timestamp = int((datetime.now() - timedelta(days=30)).timestamp())
            
            # Query: all messages after timestamp (no 'is:unread' filter)
            query = f'after:{after_timestamp}'
            
            logger.info(f"[Gmail API] Fetching messages from last 30 days...")
            
            # Fetch messages with pagination
            all_messages = []
            page_token = None
            
            while len(all_messages) < max_results:
                results = self.service.users().messages().list(
                    userId='me',
                    q=query,
                    maxResults=min(100, max_results - len(all_messages)),
                    pageToken=page_token
                ).execute()
                
                messages = results.get('messages', [])
                if not messages:
                    break
                
                # Fetch full details for each message
                for msg in messages:
                    try:
                        msg_data = self.service.users().messages().get(
                            userId='me',
                            id=msg['id'],
                            format='full'
                        ).execute()
                        
                        all_messages.append(self._parse_message(msg_data))
                    except HttpError as e:
                        logger.warning(f"[Gmail API] Failed to fetch message {msg['id']}: {e}")
                        continue
                
                # Check if there are more pages
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            logger.info(f"[Gmail API] Fetched {len(all_messages)} messages from last 30 days")
            return all_messages
            
        except HttpError as e:
            logger.error(f"[Gmail API] Error fetching 30-day messages: {e}")
            return []
    
    def _extract_email(self, email_str: str) -> str:
        """Extract email address from 'Name <email@domain.com>' format."""
        match = re.search(r'<(.+?)>', email_str)
        if match:
            return match.group(1).lower()
        return email_str.lower().strip()
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse email date header into datetime."""
        try:
            # Common email date formats
            formats = [
                '%a, %d %b %Y %H:%M:%S %z',
                '%d %b %Y %H:%M:%S %z',
                '%a, %d %b %Y %H:%M:%S %Z',
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            # Fallback: use current time
            logger.warning(f"[Gmail API] Could not parse date: {date_str}")
            return datetime.now()
            
        except Exception as e:
            logger.error(f"[Gmail API] Date parsing error: {e}")
            return datetime.now()
    
    def analyze_response_times(self, messages: List[Dict]) -> Dict[str, float]:
        """Calculate average response time per contact (in hours)."""
        # Group messages by thread
        threads = defaultdict(list)
        for msg in messages:
            threads[msg['thread_id']].append(msg)
        
        # Sort each thread by date
        for thread_id in threads:
            threads[thread_id].sort(key=lambda m: self._parse_date(m['date']))
        
        # Calculate response times per contact
        contact_responses = defaultdict(list)
        
        for thread_id, thread_messages in threads.items():
            for i in range(len(thread_messages) - 1):
                current_msg = thread_messages[i]
                next_msg = thread_messages[i + 1]
                
                current_from = self._extract_email(current_msg['from'])
                next_from = self._extract_email(next_msg['from'])
                
                # Check if next message is YOUR reply to THEIR email
                if current_from != self.email and next_from == self.email:
                    current_time = self._parse_date(current_msg['date'])
                    next_time = self._parse_date(next_msg['date'])
                    
                    if current_time and next_time:
                        response_hours = (next_time - current_time).total_seconds() / 3600
                        
                        # Filter out unrealistic response times (>7 days = likely not a real response)
                        if 0 < response_hours < 168:  # 7 days
                            contact_responses[current_from].append(response_hours)
        
        # Calculate average response time per contact
        avg_response_times = {}
        for contact, times in contact_responses.items():
            if times:
                avg_response_times[contact] = sum(times) / len(times)
        
        return avg_response_times
    
    def get_important_contacts(self, messages: List[Dict], top_n: int = 20) -> List[Dict]:
        """Score contacts by frequency + your response speed (higher = more important)."""
        # Count emails per contact
        contact_counts = defaultdict(int)
        contact_info = {}
        
        for msg in messages:
            from_email = self._extract_email(msg['from'])
            
            # Skip your own emails
            if from_email == self.email:
                continue
            
            contact_counts[from_email] += 1
            
            # Store contact info (name, first contact, last contact)
            if from_email not in contact_info:
                contact_info[from_email] = {
                    'email': from_email,
                    'name': msg['from'].split('<')[0].strip() if '<' in msg['from'] else from_email,
                    'first_contact': self._parse_date(msg['date']),
                    'last_contact': self._parse_date(msg['date']),
                    'total_emails': 0
                }
            else:
                msg_date = self._parse_date(msg['date'])
                if msg_date < contact_info[from_email]['first_contact']:
                    contact_info[from_email]['first_contact'] = msg_date
                if msg_date > contact_info[from_email]['last_contact']:
                    contact_info[from_email]['last_contact'] = msg_date
            
            contact_info[from_email]['total_emails'] = contact_counts[from_email]
        
        # Get response times
        response_times = self.analyze_response_times(messages)
        
        # Calculate importance score
        scored_contacts = []
        for email, info in contact_info.items():
            frequency_score = contact_counts[email]  # More emails = higher score
            
            # Response time score: faster response = higher importance
            # If avg response is 1h = score 10, if 24h = score 1
            response_score = 0
            if email in response_times:
                avg_hours = response_times[email]
                response_score = max(1, 24 / max(avg_hours, 0.1))  # Inverse relationship
            
            # Combined importance score
            importance_score = frequency_score + (response_score * 2)  # Weight response speed 2×
            
            scored_contacts.append({
                'email': email,
                'name': info['name'],
                'total_emails': contact_counts[email],
                'avg_response_hours': response_times.get(email),
                'importance_score': importance_score,
                'first_contact': info['first_contact'],
                'last_contact': info['last_contact']
            })
        
        # Sort by importance score (descending)
        scored_contacts.sort(key=lambda c: c['importance_score'], reverse=True)
        
        return scored_contacts[:top_n]


if __name__ == '__main__':
    # Test Gmail API - 30-day analysis
    # Always use Transmogrifier OAuth in transmogrifier
    from transmogrifier_oauth import get_transmogrifier_token_path
    
    token_file = get_transmogrifier_token_path('lacrosseguy76665@gmail.com')
    
    if token_file.exists():
        print("\n" + "="*60)
        print("Gmail API - 30-Day Analysis Test")
        print("="*60 + "\n")
        
        gmail = GmailAPI(email='lacrosseguy76665@gmail.com', token_file=token_file)
        
        # Test 1: Fetch 30-day history
        print("[1/3] Fetching messages from last 30 days...")
        messages = gmail.get_all_messages_30_days(max_results=200)
        print(f"✅ Fetched {len(messages)} messages\n")
        
        # Test 2: Analyze response times
        print("[2/3] Analyzing response times...")
        response_times = gmail.analyze_response_times(messages)
        print(f"✅ Analyzed {len(response_times)} contacts\n")
        
        print("📊 Response Time Analysis (Top 10):")
        sorted_contacts = sorted(response_times.items(), key=lambda x: x[1])
        for email, hours in sorted_contacts[:10]:
            if hours < 1:
                time_str = f"{int(hours * 60)}m"
            else:
                time_str = f"{hours:.1f}h"
            print(f"  • {email}: {time_str} avg")
        print()
        
        # Test 3: Get important contacts
        print("[3/3] Scoring contact importance...")
        important = gmail.get_important_contacts(messages, top_n=10)
        print(f"✅ Scored {len(important)} important contacts\n")
        
        print("⭐ Most Important Contacts:")
        for i, contact in enumerate(important, 1):
            response_str = f"{contact['avg_response_hours']:.1f}h avg" if contact['avg_response_hours'] else "N/A"
            print(f"  {i}. {contact['name']}")
            print(f"     Email: {contact['email']}")
            print(f"     Total emails: {contact['total_emails']}")
            print(f"     Your response time: {response_str}")
            print(f"     Importance score: {contact['importance_score']:.1f}")
            print()
        
        print("="*60)
        print("✅ Test complete!")
        print("="*60 + "\n")
        
    else:
        print(f"❌ Token file not found: {token_file}")
        print("   Run auth setup first: python3 ~/.openclaw/workspace/integrations/intelligence/config/auth/setup.py")
