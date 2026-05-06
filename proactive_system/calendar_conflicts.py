#!/usr/bin/env python3
"""
Calendar Conflict Detection Engine

Detects:
1. Overlapping meetings (double-booking)
2. Focus time violations (meetings during deep work blocks)
3. Travel time conflicts (back-to-back meetings at different locations)
4. Over-scheduled days (too many meetings)
5. No-break marathons (3+ hours continuous meetings)

Suggests fixes where possible.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import sqlite3

# Thresholds
MAX_MEETINGS_PER_DAY = 8
MIN_BREAK_BETWEEN_MEETINGS = 15  # minutes
MARATHON_THRESHOLD_HOURS = 3
FOCUS_TIME_MIN_HOURS = 2


class CalendarConflictDetector:
    """Detect calendar conflicts and scheduling issues."""
    
    def __init__(self, context_db_path: Optional[Path] = None):
        """
        Initialize conflict detector.
        
        Args:
            context_db_path: Path to context database (defaults to standard location)
        """
        if context_db_path is None:
            context_db_path = Path.home() / ".openclaw/workspace/transmogrifier/openclaw-proactive-assistant/proactive_system/context.db"
        
        self.context_db_path = Path(context_db_path)
        
        # Default focus time blocks (can be overridden from preferences)
        self.default_focus_blocks = [
            (9, 11),   # 9am-11am
            (14, 16),  # 2pm-4pm
        ]
    
    def detect_conflicts(self, events: List[Dict], date: Optional[datetime] = None) -> Dict:
        """
        Detect all conflicts for a given day.
        
        Args:
            events: List of calendar events with start/end times
            date: Date to check (defaults to today)
            
        Returns:
            Dict with conflict categories and details
        """
        if date is None:
            date = datetime.now().date()
        
        # Filter events for the target date
        day_events = self._filter_events_by_date(events, date)
        
        conflicts = {
            'date': date.isoformat(),
            'total_meetings': len(day_events),
            'overlapping_meetings': [],
            'focus_time_violations': [],
            'travel_conflicts': [],
            'over_scheduled': False,
            'meeting_marathons': [],
            'no_lunch_break': False,
            'suggestions': []
        }
        
        # 1. Check for overlapping meetings
        overlaps = self._detect_overlapping_meetings(day_events)
        conflicts['overlapping_meetings'] = overlaps
        if overlaps:
            conflicts['suggestions'].append(f"⚠️ {len(overlaps)} double-booking(s) detected - reschedule needed")
        
        # 2. Check focus time violations
        focus_violations = self._detect_focus_time_violations(day_events)
        conflicts['focus_time_violations'] = focus_violations
        if focus_violations:
            conflicts['suggestions'].append(f"💭 {len(focus_violations)} meeting(s) during focus time - consider rescheduling")
        
        # 3. Check travel conflicts
        travel_conflicts = self._detect_travel_conflicts(day_events)
        conflicts['travel_conflicts'] = travel_conflicts
        if travel_conflicts:
            conflicts['suggestions'].append(f"🚗 {len(travel_conflicts)} back-to-back meeting(s) at different locations")
        
        # 4. Check if over-scheduled
        if len(day_events) > MAX_MEETINGS_PER_DAY:
            conflicts['over_scheduled'] = True
            conflicts['suggestions'].append(f"📅 {len(day_events)} meetings today (threshold: {MAX_MEETINGS_PER_DAY}) - consider delegating")
        
        # 5. Check for meeting marathons
        marathons = self._detect_meeting_marathons(day_events)
        conflicts['meeting_marathons'] = marathons
        if marathons:
            conflicts['suggestions'].append(f"⏰ {len(marathons)} meeting marathon(s) detected - schedule breaks")
        
        # 6. Check for lunch break
        if not self._has_lunch_break(day_events):
            conflicts['no_lunch_break'] = True
            conflicts['suggestions'].append("🍽️ No lunch break scheduled - block 12-1pm")
        
        # Conflict severity
        conflicts['severity'] = self._calculate_severity(conflicts)
        
        return conflicts
    
    def get_focus_time_windows(self, events: List[Dict], date: Optional[datetime] = None, min_hours: float = FOCUS_TIME_MIN_HOURS) -> List[Dict]:
        """
        Find available focus time windows (gaps between meetings).
        
        Args:
            events: List of calendar events
            date: Date to check (defaults to today)
            min_hours: Minimum hours for a focus window
            
        Returns:
            List of focus time windows with start/end times
        """
        if date is None:
            date = datetime.now().date()
        
        day_events = self._filter_events_by_date(events, date)
        
        if not day_events:
            # Whole day is free
            return [{
                'start': datetime.combine(date, datetime.min.time().replace(hour=9)),
                'end': datetime.combine(date, datetime.min.time().replace(hour=17)),
                'duration_hours': 8.0,
                'quality': 'excellent'
            }]
        
        # Sort events by start time
        sorted_events = sorted(day_events, key=lambda e: self._parse_datetime(e['start']))
        
        focus_windows = []
        work_start = datetime.combine(date, datetime.min.time().replace(hour=9))
        work_end = datetime.combine(date, datetime.min.time().replace(hour=17))
        
        # Check gap before first meeting
        first_meeting = self._parse_datetime(sorted_events[0]['start'])
        if first_meeting > work_start:
            gap_hours = (first_meeting - work_start).total_seconds() / 3600
            if gap_hours >= min_hours:
                focus_windows.append({
                    'start': work_start,
                    'end': first_meeting,
                    'duration_hours': gap_hours,
                    'quality': self._assess_focus_quality(work_start.hour, first_meeting.hour)
                })
        
        # Check gaps between meetings
        for i in range(len(sorted_events) - 1):
            current_end = self._parse_datetime(sorted_events[i]['end'])
            next_start = self._parse_datetime(sorted_events[i + 1]['start'])
            
            gap_hours = (next_start - current_end).total_seconds() / 3600
            if gap_hours >= min_hours:
                focus_windows.append({
                    'start': current_end,
                    'end': next_start,
                    'duration_hours': gap_hours,
                    'quality': self._assess_focus_quality(current_end.hour, next_start.hour)
                })
        
        # Check gap after last meeting
        last_meeting = self._parse_datetime(sorted_events[-1]['end'])
        if last_meeting < work_end:
            gap_hours = (work_end - last_meeting).total_seconds() / 3600
            if gap_hours >= min_hours:
                focus_windows.append({
                    'start': last_meeting,
                    'end': work_end,
                    'duration_hours': gap_hours,
                    'quality': self._assess_focus_quality(last_meeting.hour, work_end.hour)
                })
        
        return focus_windows
    
    def _filter_events_by_date(self, events: List[Dict], date: datetime.date) -> List[Dict]:
        """Filter events to those occurring on the given date."""
        filtered = []
        for event in events:
            event_start = self._parse_datetime(event['start'])
            if event_start.date() == date:
                filtered.append(event)
        return filtered
    
    def _detect_overlapping_meetings(self, events: List[Dict]) -> List[Dict]:
        """Detect overlapping meetings (double-booking)."""
        overlaps = []
        sorted_events = sorted(events, key=lambda e: self._parse_datetime(e['start']))
        
        for i in range(len(sorted_events)):
            for j in range(i + 1, len(sorted_events)):
                event1 = sorted_events[i]
                event2 = sorted_events[j]
                
                start1 = self._parse_datetime(event1['start'])
                end1 = self._parse_datetime(event1['end'])
                start2 = self._parse_datetime(event2['start'])
                end2 = self._parse_datetime(event2['end'])
                
                # Check for overlap
                if start1 < end2 and start2 < end1:
                    overlaps.append({
                        'event1': event1.get('summary', 'Untitled'),
                        'event2': event2.get('summary', 'Untitled'),
                        'time1': f"{start1.strftime('%I:%M%p')}-{end1.strftime('%I:%M%p')}",
                        'time2': f"{start2.strftime('%I:%M%p')}-{end2.strftime('%I:%M%p')}",
                        'overlap_minutes': self._calculate_overlap_minutes(start1, end1, start2, end2)
                    })
        
        return overlaps
    
    def _detect_focus_time_violations(self, events: List[Dict]) -> List[Dict]:
        """Detect meetings during designated focus time blocks."""
        violations = []
        
        # Load user's focus time preferences (or use defaults)
        focus_blocks = self._get_focus_time_preferences()
        
        for event in events:
            event_start = self._parse_datetime(event['start'])
            event_hour = event_start.hour
            
            for block_start, block_end in focus_blocks:
                if block_start <= event_hour < block_end:
                    violations.append({
                        'meeting': event.get('summary', 'Untitled'),
                        'time': event_start.strftime('%I:%M%p'),
                        'focus_block': f"{block_start}:00-{block_end}:00"
                    })
                    break
        
        return violations
    
    def _detect_travel_conflicts(self, events: List[Dict]) -> List[Dict]:
        """Detect back-to-back meetings at different locations."""
        conflicts = []
        sorted_events = sorted(events, key=lambda e: self._parse_datetime(e['start']))
        
        for i in range(len(sorted_events) - 1):
            current = sorted_events[i]
            next_event = sorted_events[i + 1]
            
            current_end = self._parse_datetime(current['end'])
            next_start = self._parse_datetime(next_event['start'])
            
            # Check if back-to-back (< 15 min gap)
            gap_minutes = (next_start - current_end).total_seconds() / 60
            
            current_location = current.get('location', '').strip()
            next_location = next_event.get('location', '').strip()
            
            if gap_minutes < MIN_BREAK_BETWEEN_MEETINGS and current_location and next_location:
                if current_location.lower() != next_location.lower():
                    conflicts.append({
                        'meeting1': current.get('summary', 'Untitled'),
                        'meeting2': next_event.get('summary', 'Untitled'),
                        'location1': current_location,
                        'location2': next_location,
                        'gap_minutes': gap_minutes,
                        'time': f"{current_end.strftime('%I:%M%p')}-{next_start.strftime('%I:%M%p')}"
                    })
        
        return conflicts
    
    def _detect_meeting_marathons(self, events: List[Dict]) -> List[Dict]:
        """Detect continuous meeting blocks (3+ hours without break)."""
        marathons = []
        sorted_events = sorted(events, key=lambda e: self._parse_datetime(e['start']))
        
        if not sorted_events:
            return marathons
        
        # Group consecutive meetings
        current_marathon = [sorted_events[0]]
        
        for i in range(1, len(sorted_events)):
            prev_end = self._parse_datetime(sorted_events[i - 1]['end'])
            current_start = self._parse_datetime(sorted_events[i]['start'])
            
            gap_minutes = (current_start - prev_end).total_seconds() / 60
            
            if gap_minutes < MIN_BREAK_BETWEEN_MEETINGS:
                current_marathon.append(sorted_events[i])
            else:
                # Check if current marathon qualifies
                if len(current_marathon) >= 2:
                    start = self._parse_datetime(current_marathon[0]['start'])
                    end = self._parse_datetime(current_marathon[-1]['end'])
                    duration_hours = (end - start).total_seconds() / 3600
                    
                    if duration_hours >= MARATHON_THRESHOLD_HOURS:
                        marathons.append({
                            'start_time': start.strftime('%I:%M%p'),
                            'end_time': end.strftime('%I:%M%p'),
                            'duration_hours': duration_hours,
                            'meeting_count': len(current_marathon),
                            'meetings': [m.get('summary', 'Untitled') for m in current_marathon]
                        })
                
                # Start new marathon
                current_marathon = [sorted_events[i]]
        
        # Check final marathon
        if len(current_marathon) >= 2:
            start = self._parse_datetime(current_marathon[0]['start'])
            end = self._parse_datetime(current_marathon[-1]['end'])
            duration_hours = (end - start).total_seconds() / 3600
            
            if duration_hours >= MARATHON_THRESHOLD_HOURS:
                marathons.append({
                    'start_time': start.strftime('%I:%M%p'),
                    'end_time': end.strftime('%I:%M%p'),
                    'duration_hours': duration_hours,
                    'meeting_count': len(current_marathon),
                    'meetings': [m.get('summary', 'Untitled') for m in current_marathon]
                })
        
        return marathons
    
    def _has_lunch_break(self, events: List[Dict]) -> bool:
        """Check if there's a break during lunch hours (11am-2pm)."""
        lunch_start = 11
        lunch_end = 14
        
        for event in events:
            event_start = self._parse_datetime(event['start'])
            event_end = self._parse_datetime(event['end'])
            
            # Check if meeting spans lunch time
            if event_start.hour < lunch_end and event_end.hour > lunch_start:
                # Meeting during lunch - check if it's a break
                summary = event.get('summary', '').lower()
                if 'lunch' in summary or 'break' in summary:
                    return True
                # Occupied during lunch
                return False
        
        return True
    
    def _calculate_severity(self, conflicts: Dict) -> str:
        """Calculate overall conflict severity."""
        critical_count = len(conflicts['overlapping_meetings'])
        high_count = len(conflicts['travel_conflicts'])
        medium_count = len(conflicts['focus_time_violations']) + len(conflicts['meeting_marathons'])
        
        if critical_count > 0:
            return 'CRITICAL'
        elif high_count > 0 or conflicts['over_scheduled']:
            return 'HIGH'
        elif medium_count > 0 or conflicts['no_lunch_break']:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def _get_focus_time_preferences(self) -> List[Tuple[int, int]]:
        """Load user's focus time preferences from context DB."""
        # TODO: Load from preferences table
        # For now, return defaults
        return self.default_focus_blocks
    
    def _assess_focus_quality(self, start_hour: int, end_hour: int) -> str:
        """Assess quality of focus time window."""
        # Morning focus is typically best
        if 8 <= start_hour <= 10:
            return 'excellent'
        elif 10 <= start_hour <= 14:
            return 'good'
        elif 14 <= start_hour <= 16:
            return 'fair'
        else:
            return 'poor'
    
    def _parse_datetime(self, dt_str: str) -> datetime:
        """Parse datetime string."""
        if isinstance(dt_str, datetime):
            return dt_str
        
        # Try common formats
        for fmt in ['%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S']:
            try:
                return datetime.strptime(dt_str, fmt)
            except ValueError:
                continue
        
        # Default fallback
        return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    
    def _calculate_overlap_minutes(self, start1: datetime, end1: datetime, start2: datetime, end2: datetime) -> int:
        """Calculate overlap duration in minutes."""
        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)
        return int((overlap_end - overlap_start).total_seconds() / 60)


def main():
    """Test calendar conflict detection."""
    detector = CalendarConflictDetector()
    
    # Test events
    today = datetime.now().date()
    test_events = [
        {
            'summary': 'Team Standup',
            'start': datetime.combine(today, datetime.min.time().replace(hour=9, minute=0)).isoformat(),
            'end': datetime.combine(today, datetime.min.time().replace(hour=9, minute=30)).isoformat(),
            'location': 'Office'
        },
        {
            'summary': 'Client Meeting',
            'start': datetime.combine(today, datetime.min.time().replace(hour=10, minute=0)).isoformat(),
            'end': datetime.combine(today, datetime.min.time().replace(hour=11, minute=0)).isoformat(),
            'location': 'Downtown Office'
        },
        {
            'summary': 'Another Meeting',
            'start': datetime.combine(today, datetime.min.time().replace(hour=10, minute=30)).isoformat(),  # Overlap!
            'end': datetime.combine(today, datetime.min.time().replace(hour=11, minute=30)).isoformat(),
            'location': 'Office'
        },
    ]
    
    print("Calendar Conflict Detection Test")
    print("=" * 80)
    
    conflicts = detector.detect_conflicts(test_events)
    
    print(f"\nDate: {conflicts['date']}")
    print(f"Total Meetings: {conflicts['total_meetings']}")
    print(f"Severity: {conflicts['severity']}")
    
    if conflicts['overlapping_meetings']:
        print(f"\n⚠️ Double-Bookings ({len(conflicts['overlapping_meetings'])}):")
        for overlap in conflicts['overlapping_meetings']:
            print(f"  - {overlap['event1']} @ {overlap['time1']}")
            print(f"    overlaps with")
            print(f"    {overlap['event2']} @ {overlap['time2']}")
    
    if conflicts['suggestions']:
        print(f"\n💡 Suggestions:")
        for suggestion in conflicts['suggestions']:
            print(f"  {suggestion}")
    
    print("\n\n🎯 Focus Time Windows:")
    focus_windows = detector.get_focus_time_windows(test_events)
    for window in focus_windows:
        print(f"  {window['start'].strftime('%I:%M%p')}-{window['end'].strftime('%I:%M%p')} ({window['duration_hours']:.1f}h) - {window['quality']}")


if __name__ == '__main__':
    main()
