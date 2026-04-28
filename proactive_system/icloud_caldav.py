#!/usr/bin/env python3
"""
iCloud Calendar via CalDAV
Uses app-specific password for authentication
"""

import json
import caldav
from pathlib import Path
from typing import List, Dict
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class iCloudCalDAV:
    """iCloud Calendar via CalDAV protocol."""
    
    CALDAV_URL = 'https://caldav.icloud.com'
    
    def __init__(self, email: str, config_file: Path):
        self.email = email
        self.config_file = config_file
        self.client = None
        self._connect()
    
    def _connect(self):
        """Connect to iCloud CalDAV."""
        try:
            with open(self.config_file) as f:
                config = json.load(f)
            
            username = config['username']  # Apple ID
            password = config['app_password']  # App-specific password
            
            self.client = caldav.DAVClient(
                url=self.CALDAV_URL,
                username=username,
                password=password
            )
            
            logger.info(f"[iCloud CalDAV] Connected: {self.email}")
            
        except Exception as e:
            logger.error(f"[iCloud CalDAV] Connection failed: {e}")
            self.client = None
    
    def get_calendar_events(self, days_ahead: int = 2) -> List[Dict]:
        """Get upcoming calendar events."""
        if not self.client:
            return []
        
        try:
            principal = self.client.principal()
            calendars = principal.calendars()
            
            # Time range
            start = datetime.now()
            end = start + timedelta(days=days_ahead)
            
            all_events = []
            
            for calendar in calendars:
                events = calendar.date_search(start=start, end=end, expand=True)
                
                for event in events:
                    try:
                        parsed = self._parse_event(event)
                        if parsed:
                            all_events.append(parsed)
                    except Exception as e:
                        logger.debug(f"Failed to parse event: {e}")
            
            logger.info(f"[iCloud CalDAV] {self.email}: {len(all_events)} events")
            return all_events
            
        except Exception as e:
            logger.error(f"[iCloud CalDAV] Error fetching events: {e}")
            return []
    
    def _parse_event(self, event) -> Dict:
        """Parse CalDAV event to standard format."""
        try:
            vevent = event.vobject_instance.vevent
            
            return {
                'id': str(vevent.uid.value) if hasattr(vevent, 'uid') else None,
                'summary': str(vevent.summary.value) if hasattr(vevent, 'summary') else '',
                'description': str(vevent.description.value) if hasattr(vevent, 'description') else '',
                'start': {
                    'dateTime': vevent.dtstart.value.isoformat() if hasattr(vevent, 'dtstart') else None
                },
                'end': {
                    'dateTime': vevent.dtend.value.isoformat() if hasattr(vevent, 'dtend') else None
                },
                'location': str(vevent.location.value) if hasattr(vevent, 'location') else '',
                '_provider': 'icloud',
                '_email': self.email
            }
        except Exception as e:
            logger.debug(f"Error parsing event: {e}")
            return None


if __name__ == '__main__':
    # Test iCloud CalDAV
    config_file = Path.home() / '.openclaw/tokens/default_icloud.json'
    
    if config_file.exists():
        ical = iCloudCalDAV(email='simon@icloud.com', config_file=config_file)
        events = ical.get_calendar_events(days_ahead=2)
        
        print(f"\n📅 iCloud events: {len(events)}")
        for event in events[:5]:
            print(f"  • {event['summary']} at {event['start']['dateTime']}")
    else:
        print(f"⚠️  Config file not found: {config_file}")
        print("\nCreate config:")
        print(json.dumps({
            'username': 'your_apple_id@icloud.com',
            'app_password': 'xxxx-xxxx-xxxx-xxxx'
        }, indent=2))
