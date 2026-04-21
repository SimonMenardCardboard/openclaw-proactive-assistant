#!/usr/bin/env python3
"""
V8.5 Context-Aware Delivery

Deliver recommendations at the RIGHT TIME based on user context.

Context Factors:
- In meeting? Only deliver high-priority
- Focus time? Only deliver critical
- Driving/exercising? Defer all
- Battery low? Defer heavy analysis
- User historically ignores now? Wait
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional

class ContextAwareDelivery:
    """
    Decide WHEN to deliver recommendations based on context.
    
    Core Methods:
    - should_deliver_now(): Decide if rec should be sent now
    - get_user_context(): Get current user state
    - defer_until(): Calculate when to deliver later
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # ========================================================================
    # Delivery Decision
    # ========================================================================
    
    def should_deliver_now(self, user_id: str, recommendation: Dict) -> Tuple[bool, str]:
        """
        Decide if recommendation should be delivered NOW or deferred.
        
        Args:
            recommendation: {
                'type': 'email' | 'meeting' | 'task',
                'priority': 0.0-1.0,
                'urgency': 'low' | 'medium' | 'high'
            }
        
        Returns: (should_deliver: bool, reason: str)
        """
        context = self.get_user_context(user_id)
        priority = recommendation.get('priority', 0.5)
        
        # Critical priority (>0.9) - always deliver
        if priority >= 0.9:
            return (True, "Critical priority - immediate delivery")
        
        # In meeting? Only high priority
        if context.get('in_meeting'):
            if priority > 0.7:
                return (True, "High priority during meeting")
            else:
                meeting_end = context.get('meeting_end_time')
                return (False, f"User in meeting, defer until {meeting_end}")
        
        # Focus time? Only critical
        if context.get('focus_time'):
            if priority > 0.8:
                return (True, "Very high priority during focus time")
            else:
                return (False, "User in focus time, defer until break")
        
        # Driving? Defer all (safety first)
        if context.get('activity') == 'driving':
            return (False, "User driving, safety first - defer")
        
        # Exercising? Defer non-urgent
        if context.get('activity') == 'exercising':
            if priority > 0.8:
                return (True, "Critical priority - deliver anyway")
            else:
                return (False, "User exercising, defer")
        
        # Sleeping / quiet hours?
        if context.get('quiet_hours'):
            if priority > 0.9:
                return (True, "Critical priority - override quiet hours")
            else:
                wake_time = context.get('wake_time', '08:00')
                return (False, f"Quiet hours active, defer until {wake_time}")
        
        # User historically ignores at this time?
        if context.get('user_ignores_now'):
            if priority > 0.75:
                return (True, "High priority - deliver anyway")
            else:
                next_active = context.get('next_active_time', 'later')
                return (False, f"User typically ignores now, defer until {next_active}")
        
        # Battery low? Defer non-urgent
        if context.get('battery_level') and context.get('battery_level') < 20:
            if priority > 0.8:
                return (True, "High priority - battery warning shown")
            else:
                return (False, "Low battery, deferring to save power")
        
        # Network poor? Defer heavy content
        if context.get('network_quality') == 'poor':
            if recommendation.get('type') == 'email' and priority > 0.6:
                return (True, "Email notification only (poor network)")
            else:
                return (False, "Poor network, defer heavy content")
        
        # All clear - deliver
        return (True, "Context suitable for delivery")
    
    # ========================================================================
    # Context Detection
    # ========================================================================
    
    def get_user_context(self, user_id: str) -> Dict:
        """
        Get current user context.
        
        Returns:
        {
            "in_meeting": bool,
            "meeting_end_time": datetime,
            "focus_time": bool,
            "activity": "driving" | "exercising" | "stationary",
            "quiet_hours": bool,
            "wake_time": "08:00",
            "user_ignores_now": bool,
            "next_active_time": "09:00",
            "battery_level": 45,
            "network_quality": "good" | "poor"
        }
        """
        context = {
            "in_meeting": False,
            "meeting_end_time": None,
            "focus_time": False,
            "activity": "stationary",
            "quiet_hours": False,
            "wake_time": "08:00",
            "user_ignores_now": False,
            "next_active_time": None,
            "battery_level": None,
            "network_quality": "good"
        }
        
        now = datetime.now()
        
        # Check if in meeting (from calendar)
        in_meeting, meeting_end = self._check_in_meeting(user_id, now)
        context["in_meeting"] = in_meeting
        context["meeting_end_time"] = meeting_end
        
        # Check if focus time (from learned patterns)
        context["focus_time"] = self._check_focus_time(user_id, now)
        
        # Check quiet hours
        context["quiet_hours"] = self._check_quiet_hours(now)
        
        # Check if user ignores at this time (from historical data)
        ignores, next_active = self._check_user_ignores_now(user_id, now)
        context["user_ignores_now"] = ignores
        context["next_active_time"] = next_active
        
        # Battery/network would come from device API in production
        # For now, these are placeholders
        
        return context
    
    def _check_in_meeting(self, user_id: str, now: datetime) -> Tuple[bool, Optional[str]]:
        """
        Check if user is currently in a meeting.
        
        Returns: (in_meeting, meeting_end_time)
        """
        # In production, this would query actual calendar
        # For now, simulate based on user interactions
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Check recent meeting join events
        cursor.execute("""
            SELECT event_data, timestamp
            FROM user_interactions
            WHERE user_id = ? 
              AND event_type = 'meeting_joined'
              AND datetime(timestamp) > datetime('now', '-2 hours')
            ORDER BY timestamp DESC
            LIMIT 1
        """, (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            data = json.loads(row['event_data'])
            meeting_duration = data.get('duration_minutes', 60)
            join_time = datetime.fromisoformat(row['timestamp'])
            meeting_end = join_time + timedelta(minutes=meeting_duration)
            
            if now < meeting_end:
                return (True, meeting_end.strftime('%H:%M'))
        
        return (False, None)
    
    def _check_focus_time(self, user_id: str, now: datetime) -> bool:
        """
        Check if current time is user's focus time.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT work_patterns FROM user_patterns WHERE user_id = ?
        """, (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return False
        
        work_patterns = json.loads(row['work_patterns'])
        deep_work_hours = work_patterns.get('deep_work_hours', [])
        
        current_hour = now.hour
        
        # Check if current hour is in deep work hours
        for time_range in deep_work_hours:
            # Parse "9-11" or "14-16"
            if '-' in time_range:
                start, end = time_range.split('-')
                start_hour = int(start.replace('PM', '')) + (12 if 'PM' in start else 0)
                end_hour = int(end.replace('PM', '')) + (12 if 'PM' in end else 0)
                
                if start_hour <= current_hour < end_hour:
                    return True
        
        return False
    
    def _check_quiet_hours(self, now: datetime) -> bool:
        """
        Check if current time is in quiet hours.
        """
        hour = now.hour
        
        # Default quiet hours: 11 PM - 8 AM
        if hour >= 23 or hour < 8:
            return True
        
        return False
    
    def _check_user_ignores_now(self, user_id: str, now: datetime) -> Tuple[bool, Optional[str]]:
        """
        Check if user historically ignores notifications at this time.
        
        Returns: (ignores_now, next_active_time)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        current_hour = now.hour
        
        # Get interaction frequency by hour
        cursor.execute("""
            SELECT 
                CAST(strftime('%H', timestamp) AS INTEGER) as hour,
                COUNT(*) as count
            FROM user_interactions
            WHERE user_id = ? 
              AND event_type IN ('notification_checked', 'recommendation_clicked')
              AND datetime(timestamp) > datetime('now', '-30 days')
            GROUP BY hour
        """, (user_id,))
        
        hourly_activity = {row['hour']: row['count'] for row in cursor.fetchall()}
        conn.close()
        
        if not hourly_activity:
            return (False, None)
        
        # If current hour has very low activity, user likely ignores
        current_activity = hourly_activity.get(current_hour, 0)
        avg_activity = sum(hourly_activity.values()) / len(hourly_activity)
        
        if current_activity < avg_activity * 0.3:  # Less than 30% of average
            # Find next active hour
            for offset in range(1, 24):
                next_hour = (current_hour + offset) % 24
                if hourly_activity.get(next_hour, 0) > avg_activity * 0.7:
                    return (True, f"{next_hour:02d}:00")
            
            return (True, "later")
        
        return (False, None)
    
    # ========================================================================
    # Defer Logic
    # ========================================================================
    
    def defer_until(self, user_id: str, recommendation: Dict) -> datetime:
        """
        Calculate when to deliver deferred recommendation.
        
        Returns: datetime when recommendation should be delivered
        """
        context = self.get_user_context(user_id)
        now = datetime.now()
        
        # If in meeting, defer until meeting ends
        if context.get('in_meeting') and context.get('meeting_end_time'):
            meeting_end = context.get('meeting_end_time')
            # Parse "HH:MM"
            hour, minute = map(int, meeting_end.split(':'))
            defer_time = now.replace(hour=hour, minute=minute)
            if defer_time < now:
                defer_time += timedelta(days=1)
            return defer_time
        
        # If focus time, defer 2 hours
        if context.get('focus_time'):
            return now + timedelta(hours=2)
        
        # If quiet hours, defer until wake time
        if context.get('quiet_hours'):
            wake_hour = 8  # Default 8 AM
            wake_time = now.replace(hour=wake_hour, minute=0)
            if wake_time < now:
                wake_time += timedelta(days=1)
            return wake_time
        
        # If user ignores now, defer to next active time
        if context.get('user_ignores_now') and context.get('next_active_time'):
            next_active = context.get('next_active_time')
            if next_active != 'later':
                hour = int(next_active.split(':')[0])
                defer_time = now.replace(hour=hour, minute=0)
                if defer_time < now:
                    defer_time += timedelta(days=1)
                return defer_time
        
        # Default: defer 1 hour
        return now + timedelta(hours=1)


if __name__ == '__main__':
    # Test context-aware delivery
    import sys
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'pattern_learning.db'
    
    delivery = ContextAwareDelivery(db_path)
    
    print("Testing Context-Aware Delivery\n")
    
    user_id = 'test_user'
    
    # Get user context
    print("1. User Context:")
    context = delivery.get_user_context(user_id)
    print(json.dumps(context, indent=2, default=str))
    
    # Test delivery decision
    print("\n2. Delivery Decision:")
    
    # High priority email
    rec = {
        'type': 'email',
        'priority': 0.85,
        'urgency': 'high'
    }
    
    should_deliver, reason = delivery.should_deliver_now(user_id, rec)
    print(f"High Priority Email:")
    print(f"  Deliver: {should_deliver}")
    print(f"  Reason: {reason}")
    
    # Low priority notification
    rec = {
        'type': 'task',
        'priority': 0.3,
        'urgency': 'low'
    }
    
    should_deliver, reason = delivery.should_deliver_now(user_id, rec)
    print(f"\nLow Priority Task:")
    print(f"  Deliver: {should_deliver}")
    print(f"  Reason: {reason}")
    
    if not should_deliver:
        defer_time = delivery.defer_until(user_id, rec)
        print(f"  Defer until: {defer_time}")
