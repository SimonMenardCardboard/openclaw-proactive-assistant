#!/usr/bin/env python3
"""
Multi-Provider Calendar Connector
Supports Google Calendar, Microsoft Calendar, iCloud Calendar
Aggregates and deduplicates events across all accounts
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GoogleCalendarConnector:
    """Google Calendar via OAuth."""
    
    def __init__(self, email_addr: str, token_file: Path):
        self.email = email_addr
        self.token_file = token_file
        self.provider = 'google'
        
        # Use existing v8 connector if available
        sys.path.insert(0, str(Path(__file__).parent / 'v8_meta_learning'))
        try:
            from email_calendar_connector import EmailCalendarConnector
            self.connector = EmailCalendarConnector(email=email_addr, token_file=token_file)
            self.connector.authenticate()
        except Exception as e:
            logger.warning(f"Could not init Google Calendar connector: {e}")
            self.connector = None
    
    def get_events(self, days_ahead: int = 2) -> List[Dict]:
        """Get upcoming events."""
        if not self.connector:
            return []
        
        try:
            events = self.connector.get_calendar_events(days_ahead=days_ahead)
            logger.info(f"[Google Calendar] {self.email}: {len(events)} events")
            return events
        except Exception as e:
            logger.error(f"[Google Calendar] Failed: {e}")
            return []


class MicrosoftCalendarConnector:
    """Microsoft Calendar via OAuth."""
    
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
    
    def get_events(self, days_ahead: int = 2) -> List[Dict]:
        """Get upcoming events."""
        if not self.api:
            return []
        
        return self.api.get_calendar_events(days_ahead=days_ahead)


class iCloudCalendarConnector:
    """iCloud Calendar via CalDAV."""
    
    def __init__(self, email_addr: str, config_file: Path):
        self.email = email_addr
        self.config_file = config_file
        self.provider = 'icloud'
        
        # Use iCloud CalDAV
        try:
            from icloud_caldav import iCloudCalDAV
            self.api = iCloudCalDAV(email=email_addr, config_file=config_file)
        except Exception as e:
            logger.warning(f"iCloud CalDAV init failed: {e}")
            self.api = None
    
    def get_events(self, days_ahead: int = 2) -> List[Dict]:
        """Get upcoming events."""
        if not self.api:
            return []
        
        return self.api.get_calendar_events(days_ahead=days_ahead)


class MultiProviderCalendarConnector:
    """Aggregates calendar events from multiple providers."""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.connectors = []
        
        # Load user preferences
        from user_preferences import UserPreferences
        prefs = UserPreferences(user_id)
        
        token_dir = Path.home() / '.openclaw/tokens'
        
        # Google Calendar accounts
        for account in prefs.get_accounts('google', feature='calendar'):
            token_file = token_dir / account['token_file']
            if token_file.exists():
                self.connectors.append({
                    'provider': 'google',
                    'email': account['email'],
                    'label': account['label'],
                    'connector': GoogleCalendarConnector(account['email'], token_file)
                })
        
        # Microsoft Calendar accounts
        for account in prefs.get_accounts('microsoft', feature='calendar'):
            token_file = token_dir / account['token_file']
            if token_file.exists():
                self.connectors.append({
                    'provider': 'microsoft',
                    'email': account['email'],
                    'label': account['label'],
                    'connector': MicrosoftCalendarConnector(account['email'], token_file)
                })
        
        # iCloud Calendar accounts
        for account in prefs.get_accounts('icloud', feature='calendar'):
            config_file = token_dir / account['token_file']
            if config_file.exists():
                self.connectors.append({
                    'provider': 'icloud',
                    'email': account['email'],
                    'label': account['label'],
                    'connector': iCloudCalendarConnector(account['email'], config_file)
                })
        
        logger.info(f"✅ Initialized {len(self.connectors)} calendar connectors for {user_id}")
    
    def get_all_events(self, days_ahead: int = 2) -> List[Dict]:
        """Get events from ALL connected calendars."""
        all_events = []
        
        for conn in self.connectors:
            try:
                logger.info(f"📅 Checking {conn['label']} ({conn['email']})")
                events = conn['connector'].get_events(days_ahead=days_ahead)
                
                # Tag with account info
                for event in events:
                    event['_account_label'] = conn['label']
                    event['_account_email'] = conn['email']
                    event['_provider'] = conn['provider']
                
                all_events.extend(events)
                
            except Exception as e:
                logger.error(f"❌ Failed to check {conn['label']}: {e}")
        
        # Deduplicate
        unique_events = self._deduplicate_events(all_events)
        
        logger.info(f"📊 Total: {len(all_events)} events, {len(unique_events)} unique")
        return unique_events
    
    def _deduplicate_events(self, events: List[Dict]) -> List[Dict]:
        """Remove duplicate events (same event from multiple calendars)."""
        seen = {}
        unique = []
        
        for event in events:
            # Dedupe key: title + start time + location
            start_time = event.get('start', {})
            if isinstance(start_time, dict):
                start_time = start_time.get('dateTime', start_time.get('date', ''))
            
            key = (
                event.get('summary', '').lower().strip(),
                str(start_time),
                event.get('location', '').lower().strip()
            )
            
            if key not in seen or not key[0]:  # Keep if new or no title
                seen[key] = event
                unique.append(event)
                
                # Log if duplicate detected
                if key in seen and key != seen[key]:
                    logger.debug(f"Deduplicated: {event.get('summary')} from {event.get('_account_label')}")
        
        return unique


if __name__ == '__main__':
    # Test multi-provider calendar
    connector = MultiProviderCalendarConnector(user_id='test_user')
    
    events = connector.get_all_events(days_ahead=2)
    
    print(f"\n📅 Found {len(events)} unique events")
    for event in events[:10]:
        print(f"  • [{event.get('_account_label')}] {event.get('summary', 'No title')}")
