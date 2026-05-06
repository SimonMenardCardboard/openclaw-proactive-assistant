#!/usr/bin/env python3
"""
Preference Extraction Engine

Extracts user preferences from email/calendar patterns and stores in context DB.

Categories:
1. Calendar preferences (meeting times, durations)
2. Communication preferences (response style, formality)
3. Work style preferences (focus time, breaks)
4. Location preferences (office vs remote)

Confidence scoring: 0.0-1.0
- 1 occurrence: 0.3
- 2-3 occurrences: 0.6
- 4+ occurrences: 0.9
"""

import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import sqlite3

# Preference patterns (category, key, pattern, value_extractor)
PREFERENCE_PATTERNS = [
    # Calendar preferences
    ('calendar', 'no_meetings_before', r'(hate|don\'t like|avoid|prefer not to have).*(early|morning) (meetings?|calls?)', lambda m: '10:00'),
    ('calendar', 'no_meetings_after', r'(hate|don\'t like|avoid|prefer not to have).*(late|evening|after \d+(?:pm|:00)) (meetings?|calls?)', lambda m: '16:00'),
    ('calendar', 'prefer_meetings_before', r'prefer.*(morning|early|before \d+(?:am|:00)) (meetings?|calls?)', lambda m: '10:00'),
    ('calendar', 'prefer_meetings_after', r'prefer.*(afternoon|after \d+(?:pm|:00)) (meetings?|calls?)', lambda m: '14:00'),
    ('calendar', 'no_meetings_on', r'(don\'t schedule|no meetings?|keep.*(free|clear)).*(monday|tuesday|wednesday|thursday|friday)s?', lambda m: m.group(2).lower()),
    ('calendar', 'short_meetings_only', r'(let\'s|can we) (keep it|make it) (short|brief|quick|15|30) (min|minutes?)', lambda m: '30'),
    ('calendar', 'prefer_video_off', r'(camera|video) (off|disabled)|prefer.*(no|without) (camera|video)', lambda m: 'true'),
    
    # Work style preferences
    ('work_style', 'focus_time', r'(focus|deep work|concentrate|heads down).*(morning|afternoon|between \d+)', lambda m: m.group(2)),
    ('work_style', 'no_interruptions', r'(please )?(don\'t|do not) (interrupt|disturb|ping).*(morning|afternoon|when)', lambda m: 'true'),
    ('work_style', 'async_first', r'prefer.*(async|email|slack).*(instead of|rather than|over) (meetings?|calls?)', lambda m: 'true'),
    
    # Communication preferences
    ('communication', 'prefer_email', r'(send|email|reach).*(via|through|by) email', lambda m: 'true'),
    ('communication', 'prefer_phone', r'(call|phone|reach).*(via|through|by) (phone|cell)', lambda m: 'true'),
    ('communication', 'prefer_text', r'(text|sms|message) (me|is better|preferred)', lambda m: 'true'),
    ('communication', 'response_time_casual', r'(no rush|take your time|whenever you can|when you get a chance)', lambda m: '24h'),
    
    # Location preferences  
    ('location', 'prefer_remote', r'(work|working|prefer).*(remote|from home|WFH)', lambda m: 'true'),
    ('location', 'prefer_office', r'(work|working|prefer).*(office|in person|on site)', lambda m: 'true'),
    ('location', 'prefer_hybrid', r'(hybrid|mix|some.*(remote|office)|office.*some)', lambda m: 'true'),
]

# Calendar pattern detection (inferred from behavior)
CALENDAR_BEHAVIOR_PATTERNS = {
    'typical_meeting_duration': 'Most meetings are X minutes',
    'typical_start_time': 'Most meetings start at X:00',
    'typical_day_structure': 'Meetings cluster in morning/afternoon',
    'buffer_between_meetings': 'Prefer X minutes between meetings',
}


class PreferenceExtractor:
    """Extract and store user preferences from communications."""
    
    def __init__(self, context_db_path: Optional[Path] = None):
        """
        Initialize preference extractor.
        
        Args:
            context_db_path: Path to context database
        """
        if context_db_path is None:
            context_db_path = Path.home() / ".openclaw/workspace/transmogrifier/openclaw-proactive-assistant/proactive_system/context.db"
        
        self.context_db_path = Path(context_db_path)
        self._init_db()
    
    def _init_db(self):
        """Initialize preferences table if not exists."""
        conn = sqlite3.connect(self.context_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                source TEXT,
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_confirmed TIMESTAMP,
                UNIQUE(category, key)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def extract_from_email(self, email: Dict) -> List[Dict]:
        """
        Extract preferences from a single email.
        
        Args:
            email: Email dict with subject, body, from, date
            
        Returns:
            List of extracted preferences
        """
        text = f"{email.get('subject', '')} {email.get('body', '')}"
        source = f"email:{email.get('from', 'unknown')}:{email.get('date', 'unknown')}"
        
        preferences = []
        
        for category, key, pattern, value_extractor in PREFERENCE_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                try:
                    value = value_extractor(match)
                    
                    preferences.append({
                        'category': category,
                        'key': key,
                        'value': value,
                        'confidence': 0.6,  # Single email = medium confidence
                        'source': source
                    })
                except Exception:
                    continue
        
        return preferences
    
    def extract_from_emails(self, emails: List[Dict]) -> List[Dict]:
        """
        Extract preferences from multiple emails.
        
        Args:
            emails: List of email dicts
            
        Returns:
            List of extracted preferences with aggregated confidence
        """
        all_preferences = []
        
        for email in emails:
            prefs = self.extract_from_email(email)
            all_preferences.extend(prefs)
        
        # Aggregate by (category, key)
        aggregated = {}
        
        for pref in all_preferences:
            key = (pref['category'], pref['key'])
            
            if key not in aggregated:
                aggregated[key] = {
                    'category': pref['category'],
                    'key': pref['key'],
                    'value': pref['value'],
                    'confidence': pref['confidence'],
                    'source': pref['source'],
                    'count': 1
                }
            else:
                # Increase confidence with multiple occurrences
                aggregated[key]['count'] += 1
                # Cap confidence at 0.95
                aggregated[key]['confidence'] = min(0.95, 0.3 + (aggregated[key]['count'] * 0.2))
                aggregated[key]['source'] += f"; {pref['source']}"
        
        return list(aggregated.values())
    
    def infer_from_calendar(self, events: List[Dict]) -> List[Dict]:
        """
        Infer preferences from calendar patterns.
        
        Args:
            events: List of calendar events
            
        Returns:
            List of inferred preferences
        """
        if not events:
            return []
        
        preferences = []
        
        # Analyze meeting start times
        start_hours = []
        for event in events:
            try:
                start = self._parse_datetime(event['start'])
                start_hours.append(start.hour)
            except Exception:
                continue
        
        if start_hours:
            # Most common start hour
            from collections import Counter
            most_common_hour = Counter(start_hours).most_common(1)[0][0]
            
            if most_common_hour < 10:
                preferences.append({
                    'category': 'calendar',
                    'key': 'typical_start_time',
                    'value': f"{most_common_hour}:00",
                    'confidence': 0.7,
                    'source': f"calendar_pattern:{len(events)}_events"
                })
        
        # Detect no-meeting days
        day_counts = [0] * 7  # Mon-Sun
        for event in events:
            try:
                start = self._parse_datetime(event['start'])
                day_counts[start.weekday()] += 1
            except Exception:
                continue
        
        # If a day has significantly fewer meetings
        if day_counts:
            avg_meetings = sum(day_counts) / len([d for d in day_counts if d > 0])
            days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            
            for day_idx, count in enumerate(day_counts[:5]):  # Weekdays only
                if count < avg_meetings * 0.3 and count < 2:  # <30% of average
                    preferences.append({
                        'category': 'calendar',
                        'key': 'no_meetings_on',
                        'value': days[day_idx],
                        'confidence': 0.8,
                        'source': f"calendar_pattern:{count}_meetings_on_{days[day_idx]}"
                    })
        
        # Analyze meeting durations
        durations = []
        for event in events:
            try:
                start = self._parse_datetime(event['start'])
                end = self._parse_datetime(event['end'])
                duration_mins = (end - start).total_seconds() / 60
                durations.append(duration_mins)
            except Exception:
                continue
        
        if durations:
            from collections import Counter
            most_common_duration = Counter(durations).most_common(1)[0][0]
            
            preferences.append({
                'category': 'calendar',
                'key': 'typical_meeting_duration',
                'value': f"{int(most_common_duration)}",
                'confidence': 0.7,
                'source': f"calendar_pattern:{len(durations)}_events"
            })
        
        return preferences
    
    def save_preferences(self, preferences: List[Dict]):
        """
        Save preferences to database.
        
        Args:
            preferences: List of preference dicts
        """
        conn = sqlite3.connect(self.context_db_path)
        cursor = conn.cursor()
        
        for pref in preferences:
            # Check if preference exists
            cursor.execute('''
                SELECT confidence, source FROM preferences
                WHERE category = ? AND key = ?
            ''', (pref['category'], pref['key']))
            
            existing = cursor.fetchone()
            
            if existing:
                old_confidence = existing[0]
                new_confidence = max(old_confidence, pref['confidence'])
                
                # Update with higher confidence
                cursor.execute('''
                    UPDATE preferences
                    SET value = ?, confidence = ?, source = ?, last_confirmed = CURRENT_TIMESTAMP
                    WHERE category = ? AND key = ?
                ''', (pref['value'], new_confidence, pref['source'], pref['category'], pref['key']))
            else:
                # Insert new preference
                cursor.execute('''
                    INSERT INTO preferences (category, key, value, confidence, source)
                    VALUES (?, ?, ?, ?, ?)
                ''', (pref['category'], pref['key'], pref['value'], pref['confidence'], pref['source']))
        
        conn.commit()
        conn.close()
    
    def get_preferences(self, category: Optional[str] = None, min_confidence: float = 0.5) -> List[Dict]:
        """
        Get stored preferences.
        
        Args:
            category: Filter by category (None = all)
            min_confidence: Minimum confidence threshold
            
        Returns:
            List of preferences
        """
        conn = sqlite3.connect(self.context_db_path)
        cursor = conn.cursor()
        
        if category:
            cursor.execute('''
                SELECT category, key, value, confidence, source, extracted_at
                FROM preferences
                WHERE category = ? AND confidence >= ?
                ORDER BY confidence DESC
            ''', (category, min_confidence))
        else:
            cursor.execute('''
                SELECT category, key, value, confidence, source, extracted_at
                FROM preferences
                WHERE confidence >= ?
                ORDER BY category, confidence DESC
            ''', (min_confidence,))
        
        preferences = []
        for row in cursor.fetchall():
            preferences.append({
                'category': row[0],
                'key': row[1],
                'value': row[2],
                'confidence': row[3],
                'source': row[4],
                'extracted_at': row[5]
            })
        
        conn.close()
        return preferences
    
    def _parse_datetime(self, dt_str: str) -> datetime:
        """Parse datetime string."""
        if isinstance(dt_str, datetime):
            return dt_str
        
        for fmt in ['%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S']:
            try:
                return datetime.strptime(dt_str, fmt)
            except ValueError:
                continue
        
        return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))


def main():
    """Test preference extraction."""
    extractor = PreferenceExtractor()
    
    # Test emails
    test_emails = [
        {
            'from': 'colleague@example.com',
            'subject': 'Meeting Request',
            'body': "Hey, I hate early meetings. Can we do 2pm instead?",
            'date': '2026-05-06'
        },
        {
            'from': 'boss@example.com',
            'subject': 'Re: Schedule',
            'body': "I prefer morning meetings before 11am. Let's keep it short, 30 minutes max.",
            'date': '2026-05-05'
        },
        {
            'from': 'friend@example.com',
            'subject': 'Quick question',
            'body': "Text me when you're free, no rush!",
            'date': '2026-05-04'
        }
    ]
    
    print("Preference Extraction Test")
    print("=" * 80)
    
    # Extract from emails
    preferences = extractor.extract_from_emails(test_emails)
    
    print(f"\nExtracted {len(preferences)} preferences:\n")
    
    for pref in preferences:
        print(f"{pref['category']}.{pref['key']}: {pref['value']}")
        print(f"  Confidence: {pref['confidence']:.0%}")
        print(f"  Source: {pref['source'][:60]}...")
        print()
    
    # Save to database
    extractor.save_preferences(preferences)
    print(f"✅ Saved {len(preferences)} preferences to database")
    
    # Retrieve
    print("\nStored Preferences:")
    stored = extractor.get_preferences(min_confidence=0.5)
    for pref in stored:
        print(f"  {pref['category']}.{pref['key']} = {pref['value']} ({pref['confidence']:.0%})")


if __name__ == '__main__':
    main()
