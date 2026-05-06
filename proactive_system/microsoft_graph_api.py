#!/usr/bin/env python3
"""
Microsoft Graph API Implementation
Full OAuth support for Outlook email and calendar + 30-day analysis
"""

import json
import re
import requests
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MicrosoftGraphAPI:
    """Microsoft Graph API for Outlook."""
    
    GRAPH_API_ENDPOINT = 'https://graph.microsoft.com/v1.0'
    
    def __init__(self, email: str, token_file: Path):
        self.email = email
        self.token_file = token_file
        self.access_token = None
        self._load_token()
    
    def _load_token(self):
        """Load OAuth token."""
        try:
            with open(self.token_file) as f:
                token_data = json.load(f)
            
            self.access_token = token_data.get('access_token')
            logger.info(f"[Microsoft Graph] Loaded token for {self.email}")
            
        except Exception as e:
            logger.error(f"[Microsoft Graph] Failed to load token: {e}")
    
    def _get_headers(self) -> Dict:
        """Get authorization headers."""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
    
    # Email (Outlook)
    
    def get_unread_emails(self, hours_back: int = 1, max_results: int = 20) -> List[Dict]:
        """Get unread emails from Outlook."""
        if not self.access_token:
            return []
        
        try:
            # Calculate time filter
            after_time = (datetime.now() - timedelta(hours=hours_back)).isoformat() + 'Z'
            
            # Graph API query
            url = f"{self.GRAPH_API_ENDPOINT}/me/messages"
            params = {
                '$filter': f"isRead eq false and receivedDateTime ge {after_time}",
                '$top': max_results,
                '$orderby': 'receivedDateTime DESC',
                '$select': 'id,subject,from,receivedDateTime,bodyPreview,body,toRecipients'
            }
            
            response = requests.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            
            messages = response.json().get('value', [])
            
            parsed = [self._parse_email(msg) for msg in messages]
            
            logger.info(f"[Microsoft Graph] {self.email}: {len(parsed)} unread emails")
            return parsed
            
        except Exception as e:
            logger.error(f"[Microsoft Graph] Error fetching emails: {e}")
            return []
    
    def _parse_email(self, msg: Dict) -> Dict:
        """Parse Outlook message to standard format."""
        return {
            'id': msg.get('id'),
            'thread_id': msg.get('conversationId', msg.get('id')),  # Microsoft uses conversationId
            'from': msg.get('from', {}).get('emailAddress', {}).get('address', ''),
            'to': ', '.join([r['emailAddress']['address'] for r in msg.get('toRecipients', [])]),
            'subject': msg.get('subject', ''),
            'date': msg.get('receivedDateTime', ''),
            'snippet': msg.get('bodyPreview', ''),
            'body': msg.get('body', {}).get('content', ''),
            'labels': [],  # Microsoft doesn't have labels like Gmail
            '_provider': 'microsoft',
            '_email': self.email
        }
    
    def get_all_messages_30_days(self, max_results: int = 500) -> List[Dict]:
        """Get ALL messages from last 30 days (not just unread)."""
        if not self.access_token:
            logger.error("[Microsoft Graph] Not authenticated")
            return []
        
        try:
            # Calculate 30 days ago
            after_time = (datetime.now() - timedelta(days=30)).isoformat() + 'Z'
            
            logger.info(f"[Microsoft Graph] Fetching messages from last 30 days...")
            
            # Fetch messages with pagination
            all_messages = []
            url = f"{self.GRAPH_API_ENDPOINT}/me/messages"
            
            while len(all_messages) < max_results:
                params = {
                    '$filter': f"receivedDateTime ge {after_time}",
                    '$top': min(100, max_results - len(all_messages)),
                    '$orderby': 'receivedDateTime DESC',
                    '$select': 'id,conversationId,subject,from,receivedDateTime,bodyPreview,body,toRecipients'
                }
                
                response = requests.get(url, headers=self._get_headers(), params=params)
                response.raise_for_status()
                
                data = response.json()
                messages = data.get('value', [])
                
                if not messages:
                    break
                
                # Parse messages
                for msg in messages:
                    all_messages.append(self._parse_email(msg))
                
                # Check for next page
                next_link = data.get('@odata.nextLink')
                if not next_link:
                    break
                
                url = next_link
            
            logger.info(f"[Microsoft Graph] Fetched {len(all_messages)} messages from last 30 days")
            return all_messages
            
        except Exception as e:
            logger.error(f"[Microsoft Graph] Error fetching 30-day messages: {e}")
            return []
    
    def _extract_email(self, email_str: str) -> str:
        """Extract email address from string."""
        if not email_str:
            return ''
        return email_str.lower().strip()
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse ISO date string into datetime."""
        try:
            # Microsoft uses ISO format with 'Z' suffix
            if date_str.endswith('Z'):
                return datetime.fromisoformat(date_str[:-1])
            return datetime.fromisoformat(date_str)
        except Exception as e:
            logger.error(f"[Microsoft Graph] Date parsing error: {e}")
            return datetime.now()
    
    def analyze_response_times(self, messages: List[Dict]) -> Dict[str, float]:
        """Calculate average response time per contact (in hours)."""
        # Group messages by conversation (thread)
        conversations = defaultdict(list)
        for msg in messages:
            conversations[msg['thread_id']].append(msg)
        
        # Sort each conversation by date
        for conv_id in conversations:
            conversations[conv_id].sort(key=lambda m: self._parse_date(m['date']))
        
        # Calculate response times per contact
        contact_responses = defaultdict(list)
        
        for conv_id, conv_messages in conversations.items():
            for i in range(len(conv_messages) - 1):
                current_msg = conv_messages[i]
                next_msg = conv_messages[i + 1]
                
                current_from = self._extract_email(current_msg['from'])
                next_from = self._extract_email(next_msg['from'])
                
                # Check if next message is YOUR reply to THEIR email
                if current_from != self.email and next_from == self.email:
                    current_time = self._parse_date(current_msg['date'])
                    next_time = self._parse_date(next_msg['date'])
                    
                    if current_time and next_time:
                        response_hours = (next_time - current_time).total_seconds() / 3600
                        
                        # Filter outliers (>7 days)
                        if 0 < response_hours < 168:
                            contact_responses[current_from].append(response_hours)
        
        # Calculate average per contact
        avg_response_times = {}
        for contact, times in contact_responses.items():
            if times:
                avg_response_times[contact] = sum(times) / len(times)
        
        return avg_response_times
    
    def get_important_contacts(self, messages: List[Dict], top_n: int = 20) -> List[Dict]:
        """Score contacts by frequency + your response speed."""
        # Count emails per contact
        contact_counts = defaultdict(int)
        contact_info = {}
        
        for msg in messages:
            from_email = self._extract_email(msg['from'])
            
            # Skip your own emails
            if from_email == self.email:
                continue
            
            contact_counts[from_email] += 1
            
            # Store contact info
            if from_email not in contact_info:
                contact_info[from_email] = {
                    'email': from_email,
                    'name': msg['from'] if msg['from'] else from_email,
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
            frequency_score = contact_counts[email]
            
            # Response time score
            response_score = 0
            if email in response_times:
                avg_hours = response_times[email]
                response_score = max(1, 24 / max(avg_hours, 0.1))
            
            # Combined importance
            importance_score = frequency_score + (response_score * 2)
            
            scored_contacts.append({
                'email': email,
                'name': info['name'],
                'total_emails': contact_counts[email],
                'avg_response_hours': response_times.get(email),
                'importance_score': importance_score,
                'first_contact': info['first_contact'],
                'last_contact': info['last_contact']
            })
        
        # Sort by importance
        scored_contacts.sort(key=lambda c: c['importance_score'], reverse=True)
        
        return scored_contacts[:top_n]
    
    # Calendar
    
    def get_calendar_events(self, days_ahead: int = 2) -> List[Dict]:
        """Get upcoming calendar events."""
        if not self.access_token:
            return []
        
        try:
            # Time range
            start_time = datetime.now().isoformat() + 'Z'
            end_time = (datetime.now() + timedelta(days=days_ahead)).isoformat() + 'Z'
            
            url = f"{self.GRAPH_API_ENDPOINT}/me/calendarView"
            params = {
                'startDateTime': start_time,
                'endDateTime': end_time,
                '$orderby': 'start/dateTime',
                '$top': 50
            }
            
            response = requests.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            
            events = response.json().get('value', [])
            
            parsed = [self._parse_event(evt) for evt in events]
            
            logger.info(f"[Microsoft Graph] {self.email}: {len(parsed)} calendar events")
            return parsed
            
        except Exception as e:
            logger.error(f"[Microsoft Graph] Error fetching calendar: {e}")
            return []
    
    def _parse_event(self, evt: Dict) -> Dict:
        """Parse Outlook event to standard format."""
        return {
            'id': evt.get('id'),
            'summary': evt.get('subject', ''),
            'description': evt.get('bodyPreview', ''),
            'start': {
                'dateTime': evt.get('start', {}).get('dateTime'),
                'timeZone': evt.get('start', {}).get('timeZone')
            },
            'end': {
                'dateTime': evt.get('end', {}).get('dateTime'),
                'timeZone': evt.get('end', {}).get('timeZone')
            },
            'location': evt.get('location', {}).get('displayName', ''),
            'attendees': [a.get('emailAddress', {}).get('address') for a in evt.get('attendees', [])],
            '_provider': 'microsoft',
            '_email': self.email
        }


if __name__ == '__main__':
    # Test Microsoft Graph API - 30-day analysis
    token_file = Path.home() / '.openclaw/workspace/integrations/direct_api/token_simon_at_legalmensch_com.json'
    
    if not token_file.exists():
        # Try alternate location
        token_file = Path.home() / '.openclaw/tokens/default_microsoft_work.json'
    
    if token_file.exists():
        print("\n" + "="*60)
        print("Microsoft Graph API - 30-Day Analysis Test")
        print("="*60 + "\n")
        
        graph = MicrosoftGraphAPI(email='simon@legalmensch.com', token_file=token_file)
        
        # Test 1: Fetch 30-day history
        print("[1/3] Fetching messages from last 30 days...")
        messages = graph.get_all_messages_30_days(max_results=200)
        print(f"✅ Fetched {len(messages)} messages\n")
        
        # Test 2: Analyze response times
        print("[2/3] Analyzing response times...")
        response_times = graph.analyze_response_times(messages)
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
        important = graph.get_important_contacts(messages, top_n=10)
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
        print("   Run Microsoft OAuth flow to create token")
