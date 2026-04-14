#!/usr/bin/env python3
"""
Multi-Account Calendar Analyzer for V8

Analyzes calendar patterns across multiple accounts:
- Google Calendar (via gog)
- Outlook/Exchange Calendar (via Calendar.app SQLite)

Detects:
1. Recurring event patterns
2. Time blocking patterns
3. Pre/post-event workflows
4. Meeting prep patterns
"""

import subprocess
import json
import sqlite3
from pathlib import Path
from collections import defaultdict, Counter
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import re
import sys

# Add path for Microsoft Graph connector
sys.path.insert(0, str(Path(__file__).parent))
try:
    from microsoft_graph_connector import MicrosoftGraphConnector
    GRAPH_AVAILABLE = True
except ImportError:
    GRAPH_AVAILABLE = False


class MultiAccountCalendarAnalyzer:
    """Analyze calendar patterns across Google and Outlook calendars"""
    
    def __init__(self):
        self.accounts = {
            'google_personal': {
                'type': 'google',
                'email': 'lacrosseguy76665@gmail.com',
                'calendar_id': 'primary'
            },
            'google_work': {
                'type': 'google',
                'email': 'simon@legalmensch.com',
                'calendar_id': 'primary'
            },
            'calendar_app_all': {
                'type': 'calendar_app',
                'email': 'all',  # Gets all calendars including Tulane
                'applescript_path': Path(__file__).parent / 'fetch_calendar_events_simple.applescript'
            }
        }
        
        # Add Microsoft Graph calendar if available
        if GRAPH_AVAILABLE:
            self.accounts['microsoft_graph'] = {
                'type': 'microsoft_graph',
                'email': 'all'  # Gets all Microsoft calendars
            }
        
        self.min_occurrences = 3
        self.lookback_days = 90  # Longer for calendar (need recurring patterns)
    
    def analyze_all_accounts(self) -> Dict[str, List[Dict]]:
        """Analyze patterns across all calendar accounts"""
        all_events = []
        
        for account_name, config in self.accounts.items():
            print(f"📅 Analyzing {account_name} ({config['email']})...")
            
            try:
                if config['type'] == 'google':
                    events = self._fetch_google_events(config)
                elif config['type'] == 'calendar_app':
                    events = self._fetch_calendar_app_events(config)
                elif config['type'] == 'microsoft_graph':
                    events = self._fetch_microsoft_graph_events(config)
                else:
                    continue
                
                # Tag with account
                for event in events:
                    event['account'] = account_name
                    event['account_email'] = config['email']
                
                all_events.extend(events)
                print(f"   Found {len(events)} events")
            
            except Exception as e:
                print(f"   ⚠️  Error: {e}")
        
        print(f"\n📊 Total events analyzed: {len(all_events)}")
        
        # Detect patterns
        patterns = self._detect_patterns(all_events)
        
        return patterns
    
    def _fetch_google_events(self, config: Dict) -> List[Dict]:
        """Fetch events from Google Calendar via gog"""
        events = []
        
        # Get events from last 90 days
        start_date = (datetime.now() - timedelta(days=self.lookback_days)).strftime('%Y-%m-%d')
        
        cmd = [
            'gog', 'calendar', 'events',
            '--account', config['email'],
            config['calendar_id'],
            '--max', '200'  # Get up to 200 future events
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # Parse table output
                lines = result.stdout.strip().split('\n')
                
                for line in lines:
                    # Skip header, page token, empty lines
                    if not line or line.startswith('#') or line.startswith('ID'):
                        continue
                    
                    # Parse table: ID START END SUMMARY
                    parts = line.split(None, 3)  # Split on whitespace, max 4 parts
                    if len(parts) >= 4:
                        event_id, start, end, summary = parts
                        
                        events.append({
                            'id': event_id,
                            'summary': summary,
                            'description': '',
                            'start': start,
                            'end': end,
                            'attendees': [],
                            'recurrence': []
                        })
        
        except Exception as e:
            print(f"   Google Calendar fetch error: {e}")
        
        return events
    
    def _fetch_microsoft_graph_events(self, config: Dict) -> List[Dict]:
        """Fetch calendar events from Microsoft Graph API"""
        events = []
        
        try:
            connector = MicrosoftGraphConnector()
            
            # Fetch calendar events
            event_list = connector.get_calendar_events(max_results=200, days_back=self.lookback_days)
            
            for evt in event_list:
                events.append({
                    'id': evt.get('id'),
                    'summary': evt.get('subject', ''),
                    'description': evt.get('bodyPreview', ''),
                    'start': evt.get('start', {}).get('dateTime', ''),
                    'end': evt.get('end', {}).get('dateTime', ''),
                    'attendees': [a.get('emailAddress', {}).get('address', '') 
                                 for a in evt.get('attendees', [])],
                    'recurrence': evt.get('recurrence', [])
                })
        
        except Exception as e:
            print(f"   Microsoft Graph error: {e}")
            print(f"   (Run microsoft_graph_connector.py to authenticate)")
        
        return events
    
    def _fetch_calendar_app_events(self, config: Dict) -> List[Dict]:
        """Fetch events from macOS Calendar.app via AppleScript"""
        events = []
        applescript_path = config.get('applescript_path')
        
        if not applescript_path or not applescript_path.exists():
            print(f"   AppleScript not found: {applescript_path}")
            return events
        
        try:
            # Run AppleScript to fetch events
            result = subprocess.run(
                ['osascript', str(applescript_path), str(self.lookback_days)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and result.stderr:
                # Parse TSV output from stderr (AppleScript log goes to stderr)
                lines = result.stderr.strip().split('\n')
                
                for line in lines:
                    if not line or not '\t' in line:
                        continue
                    
                    try:
                        parts = line.split('\t')
                        if len(parts) >= 4:
                            summary, start, end, calendar_name = parts[:4]
                            
                            events.append({
                                'id': '',
                                'summary': summary.strip(),
                                'description': '',
                                'start': start.strip(),
                                'end': end.strip(),
                                'calendar_name': calendar_name.strip(),
                                'attendees': [],
                                'recurrence': []
                            })
                    except Exception:
                        continue
        
        except Exception as e:
            print(f"   Calendar.app fetch error: {e}")
        
        return events
    
    def _detect_patterns(self, events: List[Dict]) -> Dict[str, List[Dict]]:
        """Detect calendar workflow patterns"""
        patterns = {
            'recurring_titles': self._detect_recurring_titles(events),
            'time_blocks': self._detect_time_blocks(events),
            'meeting_types': self._detect_meeting_types(events)
        }
        
        return patterns
    
    def _detect_recurring_titles(self, events: List[Dict]) -> List[Dict]:
        """Detect events with similar titles (recurring meetings)"""
        # Normalize titles
        normalized = defaultdict(list)
        
        for event in events:
            title = event['summary']
            
            # Remove dates, numbers
            title = re.sub(r'\d{4}-\d{2}-\d{2}', '', title)
            title = re.sub(r'\d{1,2}/\d{1,2}', '', title)
            title = re.sub(r'#\d+', '', title)
            
            # Normalize whitespace
            title = ' '.join(title.split()).strip()
            
            if title:
                normalized[title.lower()].append(event)
        
        patterns = []
        for norm_title, event_list in normalized.items():
            if len(event_list) >= self.min_occurrences:
                patterns.append({
                    'type': 'recurring_event',
                    'title': norm_title,
                    'count': len(event_list),
                    'accounts': list(set(e['account'] for e in event_list)),
                    'confidence': min(0.95, 0.75 + (len(event_list) / 15)),
                    'description': f"Recurring event '{norm_title}' ({len(event_list)} times)",
                    'examples': event_list[:3]
                })
        
        return sorted(patterns, key=lambda x: x['count'], reverse=True)[:10]
    
    def _detect_time_blocks(self, events: List[Dict]) -> List[Dict]:
        """Detect consistent time blocking patterns"""
        # Group by weekday + hour
        blocks = defaultdict(list)
        
        for event in events:
            if event['start']:
                try:
                    dt = datetime.fromisoformat(event['start'].replace('Z', '+00:00'))
                    weekday = dt.strftime('%A')
                    hour = dt.hour
                    
                    key = f"{weekday}_{hour}"
                    blocks[key].append(event)
                except:
                    pass
        
        patterns = []
        for key, block_events in blocks.items():
            if len(block_events) >= 4:  # Appears 4+ times
                weekday, hour = key.split('_')
                patterns.append({
                    'type': 'time_block',
                    'weekday': weekday,
                    'hour': int(hour),
                    'count': len(block_events),
                    'confidence': min(0.90, 0.70 + (len(block_events) / 10)),
                    'description': f"Time block: {weekday} at {hour}:00 ({len(block_events)} occurrences)"
                })
        
        return sorted(patterns, key=lambda x: x['count'], reverse=True)[:5]
    
    def _detect_meeting_types(self, events: List[Dict]) -> List[Dict]:
        """Detect types of meetings by keywords in titles"""
        keywords = {
            'client': ['client', 'customer'],
            'team': ['team', 'standup', 'sync'],
            'training': ['training', 'workout', 'gym', 'exercise'],
            'one_on_one': ['1:1', '1-on-1', 'one-on-one'],
            'interview': ['interview', 'screening'],
            'review': ['review', 'retrospective', 'retro']
        }
        
        type_counts = defaultdict(list)
        
        for event in events:
            title_lower = event['summary'].lower()
            for meeting_type, kw_list in keywords.items():
                if any(kw in title_lower for kw in kw_list):
                    type_counts[meeting_type].append(event)
        
        patterns = []
        for meeting_type, event_list in type_counts.items():
            if len(event_list) >= self.min_occurrences:
                patterns.append({
                    'type': 'meeting_category',
                    'category': meeting_type,
                    'count': len(event_list),
                    'confidence': min(0.85, 0.65 + (len(event_list) / 20)),
                    'description': f"{meeting_type.replace('_', ' ').title()} meetings ({len(event_list)} times)"
                })
        
        return sorted(patterns, key=lambda x: x['count'], reverse=True)


def main():
    """Test multi-account calendar analyzer"""
    analyzer = MultiAccountCalendarAnalyzer()
    
    print("="*60)
    print("MULTI-ACCOUNT CALENDAR ANALYSIS")
    print("="*60)
    print()
    
    patterns = analyzer.analyze_all_accounts()
    
    for category, pattern_list in patterns.items():
        if pattern_list:
            print(f"\n{category.upper().replace('_', ' ')} ({len(pattern_list)}):")
            for i, pattern in enumerate(pattern_list[:3], 1):
                print(f"\n{i}. {pattern['description']}")
                print(f"   Confidence: {pattern['confidence']:.0%}")
                if 'accounts' in pattern:
                    print(f"   Accounts: {', '.join(pattern['accounts'])}")


if __name__ == '__main__':
    main()
