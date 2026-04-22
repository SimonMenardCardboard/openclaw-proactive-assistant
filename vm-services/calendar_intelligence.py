#!/usr/bin/env python3
"""
Calendar Intelligence - Analyze calendar via OAuth

Features:
- Next 24h events
- Meeting prep suggestions
- Conflict detection
- Travel time calculations
- Free/busy analysis
"""

import os
import json
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Paths
GOOGLE_TOKEN_PATH = os.path.expanduser('~/workspace/integrations/direct_api/token.json')
GOOGLE_TOKEN_PATH_2 = os.path.expanduser('~/workspace/integrations/direct_api/token_simon_at_legalmensch_com.json')

def load_google_credentials():
    """Load Google OAuth credentials"""
    creds = None
    
    token_paths = [GOOGLE_TOKEN_PATH, GOOGLE_TOKEN_PATH_2]
    
    for token_path in token_paths:
        if os.path.exists(token_path):
            try:
                creds = Credentials.from_authorized_user_file(token_path)
                
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    with open(token_path, 'w') as token:
                        token.write(creds.to_json())
                
                if creds and creds.valid:
                    return creds
            except Exception as e:
                print(f"Error loading {token_path}: {e}")
                continue
    
    return None

def get_calendar_events(hours=24):
    """Fetch calendar events for next N hours"""
    try:
        creds = load_google_credentials()
        if not creds:
            return None
        
        service = build('calendar', 'v3', credentials=creds)
        
        # Time range
        now = datetime.utcnow()
        time_min = now.isoformat() + 'Z'
        time_max = (now + timedelta(hours=hours)).isoformat() + 'Z'
        
        # Fetch events
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            maxResults=20,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        return events
    except HttpError as error:
        print(f'Calendar API error: {error}')
        return None
    except Exception as e:
        print(f'Error: {e}')
        return None

def extract_event_data(event):
    """Extract relevant data from calendar event"""
    try:
        summary = event.get('summary', 'No title')
        location = event.get('location', '')
        description = event.get('description', '')
        
        # Parse start time
        start = event.get('start', {})
        start_datetime = start.get('dateTime', start.get('date'))
        
        if start_datetime:
            if 'T' in start_datetime:
                # DateTime
                start_dt = datetime.fromisoformat(start_datetime.replace('Z', '+00:00'))
            else:
                # Date only (all-day event)
                start_dt = datetime.fromisoformat(start_datetime)
        else:
            start_dt = datetime.now()
        
        # Parse end time
        end = event.get('end', {})
        end_datetime = end.get('dateTime', end.get('date'))
        
        if end_datetime:
            if 'T' in end_datetime:
                end_dt = datetime.fromisoformat(end_datetime.replace('Z', '+00:00'))
            else:
                end_dt = datetime.fromisoformat(end_datetime)
        else:
            end_dt = start_dt + timedelta(hours=1)
        
        # Duration
        duration_minutes = int((end_dt - start_dt).total_seconds() / 60)
        
        # Attendees
        attendees = event.get('attendees', [])
        attendee_emails = [a.get('email') for a in attendees if a.get('email')]
        
        # Meeting link (Zoom, Meet, Teams)
        meeting_link = None
        if 'hangoutLink' in event:
            meeting_link = event['hangoutLink']
        elif 'zoom.us' in description.lower():
            import re
            zoom_match = re.search(r'https://[^\s]+zoom\.us/[^\s]+', description)
            if zoom_match:
                meeting_link = zoom_match.group(0)
        
        return {
            'id': event.get('id'),
            'summary': summary,
            'location': location,
            'description': description[:200],  # First 200 chars
            'start': start_dt.isoformat(),
            'end': end_dt.isoformat(),
            'duration_minutes': duration_minutes,
            'attendees': attendee_emails,
            'meeting_link': meeting_link,
            'all_day': 'date' in start and 'T' not in start_datetime,
        }
    except Exception as e:
        print(f"Error extracting event data: {e}")
        return None

def analyze_event(event_data):
    """Analyze event and generate prep suggestions"""
    analysis = {
        'needs_prep': False,
        'prep_suggestions': [],
        'needs_travel': False,
        'travel_time_minutes': 0,
        'conflicts': [],
    }
    
    summary = event_data.get('summary', '').lower()
    duration = event_data.get('duration_minutes', 0)
    attendees = event_data.get('attendees', [])
    location = event_data.get('location', '').lower()
    
    # Meeting prep needed?
    meeting_keywords = ['interview', 'presentation', 'review', 'demo', 'pitch']
    if any(keyword in summary for keyword in meeting_keywords):
        analysis['needs_prep'] = True
        analysis['prep_suggestions'].append('Review meeting materials')
        analysis['prep_suggestions'].append('Prepare talking points')
    
    # External meeting?
    if len(attendees) > 2:
        analysis['needs_prep'] = True
        analysis['prep_suggestions'].append('Review attendee profiles')
    
    # Travel needed?
    if location and any(keyword in location for keyword in ['office', 'building', 'street', 'ave']):
        analysis['needs_travel'] = True
        # Estimate travel time (simplified)
        if 'office' in location:
            analysis['travel_time_minutes'] = 30
        else:
            analysis['travel_time_minutes'] = 45
        analysis['prep_suggestions'].append(f'Leave {analysis["travel_time_minutes"]} min early for travel')
    
    # Long meeting?
    if duration > 60:
        analysis['prep_suggestions'].append('Block focus time before/after')
    
    return analysis

def detect_conflicts(events_data):
    """Detect overlapping events"""
    conflicts = []
    
    for i, event1 in enumerate(events_data):
        for event2 in events_data[i+1:]:
            start1 = datetime.fromisoformat(event1['start'])
            end1 = datetime.fromisoformat(event1['end'])
            start2 = datetime.fromisoformat(event2['start'])
            end2 = datetime.fromisoformat(event2['end'])
            
            # Check overlap
            if start1 < end2 and start2 < end1:
                conflicts.append({
                    'event1': event1['summary'],
                    'event2': event2['summary'],
                    'time': start1.strftime('%I:%M %p'),
                })
    
    return conflicts

def generate_calendar_summary(events):
    """Generate intelligence summary from calendar"""
    if not events:
        return {
            'next_24h': [],
            'meeting_prep': [],
            'conflicts': [],
            'travel_time_needed': [],
            'free_time': 'All day free',
            'busy_periods': []
        }
    
    events_data = []
    meeting_prep = []
    travel_needed = []
    
    for event in events:
        event_data = extract_event_data(event)
        if not event_data:
            continue
        
        events_data.append(event_data)
        
        # Analyze event
        analysis = analyze_event(event_data)
        event_data['analysis'] = analysis
        
        # Meeting prep
        if analysis['needs_prep']:
            meeting_prep.append({
                'event': event_data['summary'],
                'time': datetime.fromisoformat(event_data['start']).strftime('%I:%M %p'),
                'suggestions': analysis['prep_suggestions']
            })
        
        # Travel needed
        if analysis['needs_travel']:
            travel_needed.append({
                'event': event_data['summary'],
                'location': event_data['location'],
                'travel_time': analysis['travel_time_minutes'],
                'leave_by': (datetime.fromisoformat(event_data['start']) - 
                            timedelta(minutes=analysis['travel_time_minutes'])).strftime('%I:%M %p')
            })
    
    # Detect conflicts
    conflicts = detect_conflicts(events_data)
    
    # Calculate busy periods
    busy_periods = []
    for event in events_data:
        if not event['all_day']:
            start_time = datetime.fromisoformat(event['start']).strftime('%I:%M %p')
            end_time = datetime.fromisoformat(event['end']).strftime('%I:%M %p')
            busy_periods.append(f"{start_time} - {end_time}")
    
    return {
        'next_24h': events_data,
        'meeting_prep': meeting_prep,
        'conflicts': conflicts,
        'travel_time_needed': travel_needed,
        'free_time': 'Limited' if len(events_data) > 3 else 'Mostly free',
        'busy_periods': busy_periods,
        'oauth_status': 'connected',
        'last_check': datetime.utcnow().isoformat(),
    }

def get_calendar_intelligence():
    """Main function to get calendar intelligence"""
    try:
        events = get_calendar_events(hours=24)
        
        if events is None:
            return {
                'success': False,
                'error': 'OAuth not configured or expired',
                'hint': 'Please reconnect your calendar in Settings'
            }
        
        summary = generate_calendar_summary(events)
        
        return {
            'success': True,
            'calendar': summary
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

if __name__ == '__main__':
    # Test
    result = get_calendar_intelligence()
    print(json.dumps(result, indent=2))
