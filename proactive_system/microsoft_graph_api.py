#!/usr/bin/env python3
"""
Microsoft Graph API Implementation
Full OAuth support for Outlook email and calendar
"""

import json
import requests
from pathlib import Path
from typing import List, Dict
from datetime import datetime, timedelta
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
            'from': msg.get('from', {}).get('emailAddress', {}).get('address', ''),
            'to': ', '.join([r['emailAddress']['address'] for r in msg.get('toRecipients', [])]),
            'subject': msg.get('subject', ''),
            'date': msg.get('receivedDateTime', ''),
            'snippet': msg.get('bodyPreview', ''),
            'body': msg.get('body', {}).get('content', ''),
            '_provider': 'microsoft',
            '_email': self.email
        }
    
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
    # Test Microsoft Graph API
    token_file = Path.home() / '.openclaw/tokens/default_microsoft_work.json'
    
    if token_file.exists():
        graph = MicrosoftGraphAPI(email='simon@legalmensch.com', token_file=token_file)
        
        # Test email
        emails = graph.get_unread_emails(hours_back=24)
        print(f"\n📧 Unread emails: {len(emails)}")
        for email in emails[:3]:
            print(f"  • {email['from']}: {email['subject']}")
        
        # Test calendar
        events = graph.get_calendar_events(days_ahead=2)
        print(f"\n📅 Upcoming events: {len(events)}")
        for event in events[:3]:
            print(f"  • {event['summary']} at {event['start']['dateTime']}")
    else:
        print(f"⚠️  Token file not found: {token_file}")
        print("Run Microsoft OAuth flow to create token")
