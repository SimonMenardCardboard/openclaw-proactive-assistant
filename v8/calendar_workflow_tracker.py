#!/usr/bin/env python3
"""
Calendar Workflow Tracker - V8 Phase 1 Breadth Expansion

Tracks calendar-related patterns to discover optimization opportunities:
- Meeting prep time (do you always scramble 5min before?)
- Travel time buffers (ever double-booked with no transit time?)
- Focus blocks (are you actually getting uninterrupted time?)
- Context switches (how often do you jump between meeting types?)

Goal: Find 5-10 calendar optimizations by analyzing actual behavior
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
import subprocess


class CalendarWorkflowTracker:
    """Track calendar patterns for optimization opportunities"""
    
    def __init__(self, db_path: Path = None):
        if db_path is None:
            db_path = Path.home() / '.openclaw/workspace/integrations/intelligence/v8_meta_learning/universal_workflows.db'
        
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize calendar workflow tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE,
                title TEXT,
                start_time TEXT,
                end_time TEXT,
                duration_minutes INTEGER,
                attendees INTEGER,
                location TEXT,
                event_type TEXT,
                tracked_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calendar_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT,
                description TEXT,
                occurrences INTEGER,
                time_impact_minutes INTEGER,
                detected_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def fetch_today_events(self) -> List[Dict]:
        """Fetch today's calendar events via Google Calendar API"""
        try:
            # Use gog CLI to get calendar events
            result = subprocess.run(
                ['gog', 'calendar', 'events', 
                 '--account', 'lacrosseguy76665@gmail.com', '--json'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                # gog returns {events: [...]}
                return data.get('events', [])
            else:
                print(f"Error fetching calendar: {result.stderr}")
                return []
                
        except Exception as e:
            print(f"Calendar fetch error: {e}")
            return []
    
    def track_events(self, events: List[Dict]):
        """Store calendar events for pattern analysis"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for event in events:
            try:
                # Parse event data
                event_id = event.get('id', '')
                title = event.get('summary', 'Untitled')
                start = event.get('start', {}).get('dateTime', '')
                end = event.get('end', {}).get('dateTime', '')
                
                # Calculate duration
                if start and end:
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                    duration = int((end_dt - start_dt).total_seconds() / 60)
                else:
                    duration = 0
                
                # Count attendees
                attendees = len(event.get('attendees', []))
                
                # Classify event type
                event_type = self._classify_event(title, attendees, duration)
                
                # Store event
                cursor.execute("""
                    INSERT OR REPLACE INTO calendar_events 
                    (event_id, title, start_time, end_time, duration_minutes, attendees, event_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (event_id, title, start, end, duration, attendees, event_type))
                
            except Exception as e:
                print(f"Error tracking event {event.get('summary', 'unknown')}: {e}")
        
        conn.commit()
        conn.close()
    
    def _classify_event(self, title: str, attendees: int, duration: int) -> str:
        """Classify event type for pattern detection"""
        title_lower = title.lower()
        
        # Meeting types
        if any(word in title_lower for word in ['1:1', 'one-on-one', '1-on-1']):
            return '1on1'
        elif any(word in title_lower for word in ['standup', 'stand-up', 'daily sync']):
            return 'standup'
        elif attendees > 5:
            return 'large_meeting'
        elif attendees > 0:
            return 'small_meeting'
        
        # Focus time
        elif any(word in title_lower for word in ['focus', 'deep work', 'coding', 'writing']):
            return 'focus_block'
        
        # Admin
        elif any(word in title_lower for word in ['lunch', 'break', 'coffee']):
            return 'break'
        elif any(word in title_lower for word in ['travel', 'commute', 'drive']):
            return 'travel'
        
        return 'other'
    
    def detect_patterns(self) -> List[Dict]:
        """Analyze calendar events for optimization opportunities"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        patterns = []
        
        # Pattern 1: Back-to-back meetings (no buffer)
        cursor.execute("""
            SELECT 
                COUNT(*) as occurrences,
                SUM(e1.duration_minutes + e2.duration_minutes) as total_minutes
            FROM calendar_events e1
            JOIN calendar_events e2 ON e1.end_time = e2.start_time
            WHERE e1.event_type != 'break' AND e2.event_type != 'break'
        """)
        
        result = cursor.fetchone()
        if result[0] > 3:
            patterns.append({
                'type': 'back_to_back_meetings',
                'description': f'{result[0]} back-to-back meetings (no buffer)',
                'occurrences': result[0],
                'time_impact': 15 * result[0],  # 15min buffer per transition
                'optimization': 'Add 10-15min buffer between meetings'
            })
        
        # Pattern 2: Long meeting blocks (>3 hours continuous)
        cursor.execute("""
            SELECT COUNT(*) 
            FROM calendar_events 
            WHERE duration_minutes > 180 
            AND event_type IN ('small_meeting', 'large_meeting')
        """)
        
        result = cursor.fetchone()
        if result[0] > 0:
            patterns.append({
                'type': 'long_meeting_blocks',
                'description': f'{result[0]} meetings >3 hours (likely need breaks)',
                'occurrences': result[0],
                'time_impact': 10 * result[0],  # 10min break/hr
                'optimization': 'Split long meetings, add breaks every 90min'
            })
        
        # Pattern 3: Context switches (meeting type changes)
        cursor.execute("""
            SELECT 
                e1.event_type, 
                e2.event_type, 
                COUNT(*) as switches
            FROM calendar_events e1
            JOIN calendar_events e2 ON e1.id = e2.id - 1
            WHERE e1.event_type != e2.event_type
            GROUP BY e1.event_type, e2.event_type
            HAVING switches > 2
        """)
        
        switches = cursor.fetchall()
        if switches:
            total_switches = sum(s[2] for s in switches)
            patterns.append({
                'type': 'context_switching',
                'description': f'{total_switches} context switches (meeting type changes)',
                'occurrences': total_switches,
                'time_impact': 5 * total_switches,  # 5min mental reset
                'optimization': 'Batch similar meeting types together'
            })
        
        # Pattern 4: No focus blocks
        cursor.execute("""
            SELECT COUNT(*) 
            FROM calendar_events 
            WHERE event_type = 'focus_block' 
            AND duration_minutes >= 60
        """)
        
        result = cursor.fetchone()
        if result[0] == 0:
            patterns.append({
                'type': 'no_focus_time',
                'description': 'No dedicated focus blocks (60+ min)',
                'occurrences': 1,
                'time_impact': 120,  # 2hr/day lost to fragmentation
                'optimization': 'Block 2hr focus time daily (9-11 AM or 2-4 PM)'
            })
        
        # Store detected patterns
        for pattern in patterns:
            cursor.execute("""
                INSERT INTO calendar_patterns 
                (pattern_type, description, occurrences, time_impact_minutes)
                VALUES (?, ?, ?, ?)
            """, (
                pattern['type'],
                pattern['description'],
                pattern['occurrences'],
                pattern['time_impact']
            ))
        
        conn.commit()
        conn.close()
        
        return patterns
    
    def generate_report(self) -> str:
        """Generate optimization report"""
        patterns = self.detect_patterns()
        
        if not patterns:
            return "✅ No calendar optimization opportunities detected"
        
        report = "📅 CALENDAR OPTIMIZATION OPPORTUNITIES\n"
        report += "=" * 50 + "\n\n"
        
        total_time_saved = sum(p['time_impact'] for p in patterns)
        
        for i, pattern in enumerate(patterns, 1):
            report += f"{i}. {pattern['description']}\n"
            report += f"   Time Impact: {pattern['time_impact']} min\n"
            report += f"   Optimization: {pattern['optimization']}\n\n"
        
        report += f"Total Time Savings: {total_time_saved} min/week\n"
        report += f"Optimizations Found: {len(patterns)}\n"
        
        return report


if __name__ == '__main__':
    tracker = CalendarWorkflowTracker()
    
    print("📅 Fetching today's calendar events...")
    events = tracker.fetch_today_events()
    print(f"   Found {len(events)} events\n")
    
    if events:
        print("📊 Tracking events...")
        tracker.track_events(events)
        print("   Events stored\n")
    
    print("🔍 Analyzing patterns...")
    report = tracker.generate_report()
    print(report)
