#!/usr/bin/env python3
"""
Google Calendar API Implementation
Full OAuth support + 30-day analysis
"""

import json
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


class GoogleCalendarAPI:
    """Google Calendar API with OAuth2 authentication + 30-day analysis."""
    
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
                token=token_data.get('token'),
                refresh_token=token_data.get('refresh_token'),
                token_uri='https://oauth2.googleapis.com/token',
                client_id=token_data.get('client_id'),
                client_secret=token_data.get('client_secret')
            )
            
            self.service = build('calendar', 'v3', credentials=creds)
            logger.info(f"[Google Calendar] Authenticated: {self.email}")
            
        except Exception as e:
            logger.error(f"[Google Calendar] Auth failed for {self.email}: {e}")
            self.service = None
    
    def get_all_events_30_days(self, calendar_id: str = 'primary', max_results: int = 500) -> List[Dict]:
        """Get ALL events from last 30 days (past + future)."""
        if not self.service:
            logger.error("[Google Calendar] Not authenticated")
            return []
        
        try:
            # 30 days ago to 30 days future (60-day window)
            time_min = datetime.utcnow() - timedelta(days=30)
            time_max = datetime.utcnow() + timedelta(days=30)
            
            logger.info(f"[Google Calendar] Fetching events ({time_min.date()} to {time_max.date()})...")
            
            all_events = []
            page_token = None
            
            while len(all_events) < max_results:
                events_result = self.service.events().list(
                    calendarId=calendar_id,
                    timeMin=time_min.isoformat() + 'Z',
                    timeMax=time_max.isoformat() + 'Z',
                    maxResults=min(max_results - len(all_events), 250),
                    singleEvents=True,
                    orderBy='startTime',
                    pageToken=page_token
                ).execute()
                
                events = events_result.get('items', [])
                if not events:
                    break
                
                for event in events:
                    all_events.append(self._parse_event(event, calendar_id))
                
                page_token = events_result.get('nextPageToken')
                if not page_token:
                    break
            
            logger.info(f"[Google Calendar] Fetched {len(all_events)} events")
            return all_events
            
        except HttpError as e:
            logger.error(f"[Google Calendar] Error fetching events: {e}")
            return []
    
    def _parse_event(self, event: Dict, calendar_id: str) -> Dict:
        """Parse Google Calendar event to standard format."""
        return {
            'id': event.get('id'),
            'calendar_id': calendar_id,
            'summary': event.get('summary', '(No title)'),
            'description': event.get('description', ''),
            'start': event['start'].get('dateTime', event['start'].get('date')),
            'end': event['end'].get('dateTime', event['end'].get('date')),
            'location': event.get('location', ''),
            'attendees': [a.get('email') for a in event.get('attendees', [])],
            'recurring_event_id': event.get('recurringEventId'),
            'organizer': event.get('organizer', {}).get('email', ''),
            'created': event.get('created'),
            'updated': event.get('updated'),
            'status': event.get('status', 'confirmed'),
            '_provider': 'google',
            '_email': self.email
        }
    
    def detect_recurring_patterns(self, events: List[Dict]) -> Dict[str, List[Dict]]:
        """Detect recurring meeting patterns."""
        recurring_groups = defaultdict(list)
        
        for event in events:
            recurring_id = event.get('recurring_event_id')
            if recurring_id:
                recurring_groups[recurring_id].append(event)
        
        # Analyze patterns
        patterns = {}
        for recurring_id, occurrences in recurring_groups.items():
            if len(occurrences) < 2:
                continue
            
            # Get pattern summary
            first = occurrences[0]
            patterns[recurring_id] = {
                'summary': first['summary'],
                'occurrence_count': len(occurrences),
                'first_occurrence': first['start'],
                'last_occurrence': occurrences[-1]['start'],
                'attendees': first['attendees'],
                'organizer': first['organizer']
            }
        
        return patterns
    
    def analyze_meeting_frequency(self, events: List[Dict]) -> Dict[str, int]:
        """Count meetings per contact (attendees)."""
        contact_meetings = defaultdict(int)
        
        for event in events:
            attendees = event.get('attendees', [])
            for attendee in attendees:
                if attendee != self.email:  # Skip self
                    contact_meetings[attendee] += 1
        
        return dict(contact_meetings)
    
    def find_focus_time_gaps(self, events: List[Dict], min_gap_hours: float = 2.0) -> List[Dict]:
        """Find large gaps in calendar (potential focus time)."""
        if not events:
            return []
        
        # Sort by start time
        sorted_events = sorted(events, key=lambda e: e['start'])
        
        gaps = []
        for i in range(len(sorted_events) - 1):
            current_end = self._parse_datetime(sorted_events[i]['end'])
            next_start = self._parse_datetime(sorted_events[i + 1]['start'])
            
            if current_end and next_start:
                gap_hours = (next_start - current_end).total_seconds() / 3600
                
                if gap_hours >= min_gap_hours:
                    gaps.append({
                        'start': current_end,
                        'end': next_start,
                        'duration_hours': gap_hours,
                        'before_event': sorted_events[i]['summary'],
                        'after_event': sorted_events[i + 1]['summary']
                    })
        
        return gaps
    
    def detect_conflicts(self, events: List[Dict]) -> List[Dict]:
        """Detect overlapping events (double-booked)."""
        if not events:
            return []
        
        conflicts = []
        sorted_events = sorted(events, key=lambda e: e['start'])
        
        for i in range(len(sorted_events)):
            for j in range(i + 1, len(sorted_events)):
                event_a = sorted_events[i]
                event_b = sorted_events[j]
                
                start_a = self._parse_datetime(event_a['start'])
                end_a = self._parse_datetime(event_a['end'])
                start_b = self._parse_datetime(event_b['start'])
                end_b = self._parse_datetime(event_b['end'])
                
                if not all([start_a, end_a, start_b, end_b]):
                    continue
                
                # Check for overlap
                if start_a < end_b and start_b < end_a:
                    conflicts.append({
                        'event_1': event_a['summary'],
                        'event_2': event_b['summary'],
                        'time_1': f"{start_a} - {end_a}",
                        'time_2': f"{start_b} - {end_b}"
                    })
        
        return conflicts
    
    def _parse_datetime(self, dt_str: str) -> Optional[datetime]:
        """Parse datetime string (handles both dateTime and date formats)."""
        try:
            if 'T' in dt_str:
                # Has time component
                return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            else:
                # Date only
                return datetime.fromisoformat(dt_str)
        except Exception as e:
            logger.warning(f"[Google Calendar] Failed to parse datetime: {dt_str}")
            return None


if __name__ == '__main__':
    import tempfile
    
    print("\n" + "="*60)
    print("Google Calendar API - 30-Day Analysis Test")
    print("="*60 + "\n")
    
    # Use Transmogrifier OAuth token
    token_file = Path.home() / '.openclaw/workspace/transmogrifier/openclaw-proactive-assistant/config/default_google_personal.json'
    
    if not token_file.exists():
        print(f"❌ Token file not found: {token_file}")
        print("   This test requires Transmogrifier OAuth tokens")
        exit(1)
    
    cal = GoogleCalendarAPI(email='lacrosseguy76665@gmail.com', token_file=token_file)
    
    # Test 1: Fetch 30-day events
    print("[1/4] Fetching events from last 30 days...")
    events = cal.get_all_events_30_days(max_results=100)
    print(f"✅ Fetched {len(events)} events\n")
    
    if events:
        print("Sample events:")
        for event in events[:3]:
            print(f"  • {event['summary']}")
            print(f"    Start: {event['start']}")
            print(f"    Attendees: {len(event['attendees'])}")
            print()
    
    # Test 2: Detect recurring patterns
    print("[2/4] Detecting recurring patterns...")
    patterns = cal.detect_recurring_patterns(events)
    print(f"✅ Found {len(patterns)} recurring meeting series\n")
    
    if patterns:
        print("Recurring meetings:")
        for pattern in list(patterns.values())[:3]:
            print(f"  • {pattern['summary']}")
            print(f"    Occurrences: {pattern['occurrence_count']}")
            print()
    
    # Test 3: Meeting frequency
    print("[3/4] Analyzing meeting frequency per contact...")
    contact_freq = cal.analyze_meeting_frequency(events)
    sorted_contacts = sorted(contact_freq.items(), key=lambda x: x[1], reverse=True)
    print(f"✅ Analyzed {len(contact_freq)} contacts\n")
    
    if sorted_contacts:
        print("Most frequent meeting contacts:")
        for email, count in sorted_contacts[:5]:
            print(f"  • {email}: {count} meetings")
        print()
    
    # Test 4: Find focus time gaps
    print("[4/4] Finding focus time gaps...")
    gaps = cal.find_focus_time_gaps(events, min_gap_hours=2.0)
    print(f"✅ Found {len(gaps)} gaps (≥2h)\n")
    
    if gaps:
        print("Large calendar gaps (focus time):")
        for gap in gaps[:3]:
            print(f"  • {gap['duration_hours']:.1f}h gap")
            print(f"    {gap['start']} - {gap['end']}")
            print()
    
    print("="*60)
    print("✅ Test complete!")
    print("="*60 + "\n")
