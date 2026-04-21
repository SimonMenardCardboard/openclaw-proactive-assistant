#!/usr/bin/env python3
"""
V8.5 Pattern Analyzer

Analyzes user interactions to discover behavioral patterns.
This is the core intelligence engine that learns:
- Email patterns (VIPs, urgent keywords, response times)
- Calendar patterns (meeting prep, skip patterns, focus time)
- Work patterns (deep work hours, productivity peaks)

Output: per-user pattern models for personalization
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter
import statistics

class UserPatternAnalyzer:
    """
    Analyze user_interactions to discover behavioral patterns.
    
    Core Methods:
    - analyze_email_patterns(): Learn email response behavior
    - analyze_calendar_patterns(): Learn meeting behavior
    - analyze_work_patterns(): Learn productivity patterns
    - predict_priority(): Estimate importance for THIS user
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.min_interactions_for_pattern = 10  # Need at least 10 data points
        
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with JSON support."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # ========================================================================
    # Email Pattern Detection
    # ========================================================================
    
    def analyze_email_patterns(self, user_id: str) -> Dict:
        """
        Analyze email response patterns.
        
        Returns:
        {
            "vip_senders": ["boss@company.com", "client@example.com"],
            "urgent_keywords": ["URGENT", "EOD", "deadline"],
            "avg_response_time_hours": 2.5,
            "response_time_by_sender": {"boss@company.com": 0.5, ...},
            "batch_processor": False,
            "peak_email_hours": ["9-11", "14-16"],
            "ignored_senders": ["newsletter@spam.com"],
            "confidence_score": 0.75
        }
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        patterns = {
            "vip_senders": [],
            "urgent_keywords": [],
            "avg_response_time_hours": None,
            "response_time_by_sender": {},
            "batch_processor": None,
            "peak_email_hours": [],
            "ignored_senders": [],
            "confidence_score": 0.0
        }
        
        # Get all email interactions
        cursor.execute("""
            SELECT event_data, timestamp
            FROM user_interactions
            WHERE user_id = ? AND event_type IN ('email_received', 'email_opened', 'email_replied')
            ORDER BY timestamp
        """, (user_id,))
        
        email_events = cursor.fetchall()
        
        if len(email_events) < self.min_interactions_for_pattern:
            conn.close()
            patterns["confidence_score"] = 0.0
            return patterns
        
        # Parse email events
        emails_received = {}
        response_times = []
        sender_response_times = defaultdict(list)
        opened_emails = set()
        ignored_emails = set()
        hourly_activity = defaultdict(int)
        subject_keywords = Counter()
        
        for row in email_events:
            data = json.loads(row['event_data'])
            event_time = datetime.fromisoformat(row['timestamp'])
            
            if 'email_id' in data:
                email_id = data['email_id']
                
                if data.get('action') == 'received':
                    emails_received[email_id] = {
                        'sender': data.get('sender', ''),
                        'subject': data.get('subject', ''),
                        'received_at': event_time
                    }
                    hourly_activity[event_time.hour] += 1
                    
                    # Extract keywords from subject
                    if 'subject' in data:
                        words = data['subject'].upper().split()
                        for word in words:
                            if len(word) > 3:  # Skip short words
                                subject_keywords[word] += 1
                
                elif data.get('action') == 'opened':
                    opened_emails.add(email_id)
                
                elif data.get('action') == 'replied':
                    if email_id in emails_received:
                        # Calculate response time
                        received = emails_received[email_id]['received_at']
                        replied = event_time
                        response_time = (replied - received).total_seconds() / 3600  # hours
                        
                        if response_time > 0:
                            response_times.append(response_time)
                            sender = emails_received[email_id]['sender']
                            sender_response_times[sender].append(response_time)
        
        # Detect VIP senders (fast response times)
        vip_threshold = 2.0  # Respond within 2 hours = VIP
        for sender, times in sender_response_times.items():
            if len(times) >= 3:  # At least 3 responses
                avg_time = statistics.mean(times)
                if avg_time < vip_threshold:
                    patterns["vip_senders"].append(sender)
                    patterns["response_time_by_sender"][sender] = round(avg_time, 2)
        
        # Detect ignored senders (never opened/replied)
        all_senders = {email['sender'] for email in emails_received.values()}
        responded_senders = set(sender_response_times.keys())
        potential_ignored = all_senders - responded_senders
        
        # Count how often each sender is ignored
        sender_receive_count = Counter(email['sender'] for email in emails_received.values())
        for sender in potential_ignored:
            if sender_receive_count[sender] >= 3:  # Received at least 3 emails
                patterns["ignored_senders"].append(sender)
        
        # Average response time
        if response_times:
            patterns["avg_response_time_hours"] = round(statistics.mean(response_times), 2)
        
        # Batch vs real-time processor
        if response_times:
            median_response = statistics.median(response_times)
            patterns["batch_processor"] = median_response > 4.0  # >4 hours = batch
        
        # Peak email hours
        if hourly_activity:
            top_hours = sorted(hourly_activity.items(), key=lambda x: x[1], reverse=True)[:3]
            for hour, _ in top_hours:
                if hour < 12:
                    patterns["peak_email_hours"].append(f"{hour}-{hour+2}")
                else:
                    patterns["peak_email_hours"].append(f"{hour-12}-{hour-10}PM")
        
        # Urgent keywords (most common in subjects)
        urgent_candidates = ["URGENT", "ASAP", "EOD", "DEADLINE", "CRITICAL", "IMPORTANT"]
        patterns["urgent_keywords"] = [kw for kw in urgent_candidates if kw in subject_keywords]
        
        # Confidence score based on interaction count
        interaction_count = len(email_events)
        if interaction_count >= 100:
            patterns["confidence_score"] = 0.9
        elif interaction_count >= 50:
            patterns["confidence_score"] = 0.75
        elif interaction_count >= 20:
            patterns["confidence_score"] = 0.6
        else:
            patterns["confidence_score"] = 0.4
        
        conn.close()
        return patterns
    
    # ========================================================================
    # Calendar Pattern Detection
    # ========================================================================
    
    def analyze_calendar_patterns(self, user_id: str) -> Dict:
        """
        Analyze meeting behavior patterns.
        
        Returns:
        {
            "prep_time_needed_minutes": 15,
            "late_meetings": ["Daily standup"],
            "skip_meetings": ["Company all-hands"],
            "focus_time_preferred": ["9-11", "14-16"],
            "back_to_back_tolerance": 3,
            "meeting_type_importance": {"1:1": 0.9, "standup": 0.6},
            "confidence_score": 0.75
        }
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        patterns = {
            "prep_time_needed_minutes": 10,
            "late_meetings": [],
            "skip_meetings": [],
            "focus_time_preferred": [],
            "back_to_back_tolerance": 2,
            "meeting_type_importance": {},
            "confidence_score": 0.0
        }
        
        # Get calendar interactions
        cursor.execute("""
            SELECT event_data, timestamp
            FROM user_interactions
            WHERE user_id = ? AND event_type IN ('meeting_scheduled', 'meeting_joined', 'meeting_skipped')
            ORDER BY timestamp
        """, (user_id,))
        
        meeting_events = cursor.fetchall()
        
        if len(meeting_events) < self.min_interactions_for_pattern:
            conn.close()
            patterns["confidence_score"] = 0.0
            return patterns
        
        # Parse meeting events
        meetings = {}
        late_count = defaultdict(int)
        skip_count = defaultdict(int)
        total_count = defaultdict(int)
        join_times = []
        
        for row in meeting_events:
            data = json.loads(row['event_data'])
            event_time = datetime.fromisoformat(row['timestamp'])
            
            meeting_id = data.get('meeting_id', '')
            meeting_title = data.get('meeting_title', '')
            
            if data.get('action') == 'scheduled':
                meetings[meeting_id] = {
                    'title': meeting_title,
                    'scheduled_time': event_time,
                    'joined_time': None,
                    'skipped': False
                }
                total_count[meeting_title] += 1
            
            elif data.get('action') == 'joined':
                if meeting_id in meetings:
                    meetings[meeting_id]['joined_time'] = event_time
                    scheduled = meetings[meeting_id]['scheduled_time']
                    diff = (event_time - scheduled).total_seconds() / 60  # minutes
                    
                    if diff > 2:  # Joined >2 min late
                        late_count[meeting_title] += 1
                    
                    join_times.append(diff)
            
            elif data.get('action') == 'skipped':
                if meeting_id in meetings:
                    meetings[meeting_id]['skipped'] = True
                    skip_count[meeting_title] += 1
        
        # Detect late meetings
        for title, count in late_count.items():
            if total_count[title] >= 3 and count / total_count[title] > 0.5:
                patterns["late_meetings"].append(title)
        
        # Detect skip meetings
        for title, count in skip_count.items():
            if total_count[title] >= 3 and count / total_count[title] > 0.3:
                patterns["skip_meetings"].append(title)
        
        # Average prep time needed
        if join_times:
            avg_join_delay = statistics.median(join_times)
            patterns["prep_time_needed_minutes"] = max(5, int(abs(avg_join_delay)))
        
        # Meeting type importance (inverse of skip rate)
        for title, total in total_count.items():
            if total >= 3:
                skipped = skip_count.get(title, 0)
                importance = 1.0 - (skipped / total)
                patterns["meeting_type_importance"][title] = round(importance, 2)
        
        # Focus time preferred (gaps between meetings)
        # (Simplified - would need more sophisticated analysis)
        patterns["focus_time_preferred"] = ["9-11", "14-16"]
        
        # Confidence score
        interaction_count = len(meeting_events)
        if interaction_count >= 50:
            patterns["confidence_score"] = 0.8
        elif interaction_count >= 20:
            patterns["confidence_score"] = 0.6
        else:
            patterns["confidence_score"] = 0.4
        
        conn.close()
        return patterns
    
    # ========================================================================
    # Work Pattern Detection
    # ========================================================================
    
    def analyze_work_patterns(self, user_id: str) -> Dict:
        """
        Analyze overall work behavior.
        
        Returns:
        {
            "deep_work_hours": ["9-11", "14-16"],
            "distraction_hours": ["11-12", "16-17"],
            "notification_check_frequency_minutes": 15,
            "stress_triggers": ["rapid_email_influx", "tight_deadlines"],
            "productivity_peak": "9-11",
            "weekend_behavior": "active",  # or "quiet"
            "confidence_score": 0.75
        }
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        patterns = {
            "deep_work_hours": [],
            "distraction_hours": [],
            "notification_check_frequency_minutes": 20,
            "stress_triggers": [],
            "productivity_peak": None,
            "weekend_behavior": "quiet",
            "confidence_score": 0.0
        }
        
        # Get app activity
        cursor.execute("""
            SELECT event_data, timestamp
            FROM user_interactions
            WHERE user_id = ? AND event_type IN ('app_opened', 'app_closed', 'notification_checked')
            ORDER BY timestamp
        """, (user_id,))
        
        activity_events = cursor.fetchall()
        
        if len(activity_events) < self.min_interactions_for_pattern:
            conn.close()
            patterns["confidence_score"] = 0.0
            return patterns
        
        # Parse activity
        hourly_activity = defaultdict(int)
        session_lengths = []
        notification_checks = []
        last_check = None
        
        for row in activity_events:
            data = json.loads(row['event_data'])
            event_time = datetime.fromisoformat(row['timestamp'])
            
            hourly_activity[event_time.hour] += 1
            
            if data.get('action') == 'notification_checked':
                notification_checks.append(event_time)
                if last_check:
                    gap = (event_time - last_check).total_seconds() / 60
                    if 0 < gap < 120:  # Within 2 hours
                        session_lengths.append(gap)
                last_check = event_time
        
        # Deep work hours (high activity, few interruptions)
        if hourly_activity:
            top_hours = sorted(hourly_activity.items(), key=lambda x: x[1], reverse=True)[:2]
            for hour, _ in top_hours:
                end_hour = hour + 2
                if hour < 12:
                    patterns["deep_work_hours"].append(f"{hour}-{end_hour}")
                else:
                    patterns["deep_work_hours"].append(f"{hour-12}-{end_hour-12}PM")
            
            # Productivity peak (most active hour)
            peak_hour = max(hourly_activity.items(), key=lambda x: x[1])[0]
            if peak_hour < 12:
                patterns["productivity_peak"] = f"{peak_hour}-{peak_hour+2}"
            else:
                patterns["productivity_peak"] = f"{peak_hour-12}-{peak_hour-10}PM"
        
        # Notification check frequency
        if session_lengths:
            patterns["notification_check_frequency_minutes"] = int(statistics.median(session_lengths))
        
        # Confidence score
        interaction_count = len(activity_events)
        if interaction_count >= 100:
            patterns["confidence_score"] = 0.8
        elif interaction_count >= 50:
            patterns["confidence_score"] = 0.6
        else:
            patterns["confidence_score"] = 0.4
        
        conn.close()
        return patterns
    
    # ========================================================================
    # Priority Prediction
    # ========================================================================
    
    def predict_priority(self, user_id: str, item: Dict) -> float:
        """
        Predict how important this item is to THIS user.
        
        Args:
            item: {
                'type': 'email' | 'meeting',
                'sender': 'email@example.com',
                'subject': 'Subject line',
                'time': datetime,
                ...
            }
        
        Returns: 0.0 - 1.0 priority score
        """
        # Get user patterns
        email_patterns = self.analyze_email_patterns(user_id)
        
        score = 0.5  # baseline
        
        if item.get('type') == 'email':
            sender = item.get('sender', '')
            subject = item.get('subject', '')
            
            # VIP sender?
            if sender in email_patterns['vip_senders']:
                score += 0.3
            
            # Urgent keywords?
            subject_upper = subject.upper()
            if any(kw in subject_upper for kw in email_patterns['urgent_keywords']):
                score += 0.2
            
            # Ignored sender?
            if sender in email_patterns['ignored_senders']:
                score = 0.1
        
        return min(1.0, max(0.0, score))
    
    # ========================================================================
    # Pattern Storage
    # ========================================================================
    
    def save_patterns(self, user_id: str) -> None:
        """
        Analyze and save all patterns for user.
        """
        email_patterns = self.analyze_email_patterns(user_id)
        calendar_patterns = self.analyze_calendar_patterns(user_id)
        work_patterns = self.analyze_work_patterns(user_id)
        
        # Calculate overall confidence
        confidence = statistics.mean([
            email_patterns['confidence_score'],
            calendar_patterns['confidence_score'],
            work_patterns['confidence_score']
        ])
        
        # Count interactions
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM user_interactions
            WHERE user_id = ?
        """, (user_id,))
        interaction_count = cursor.fetchone()['count']
        
        # Save to database
        cursor.execute("""
            INSERT OR REPLACE INTO user_patterns
            (user_id, email_patterns, calendar_patterns, work_patterns, last_updated, confidence_score, interaction_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            json.dumps(email_patterns),
            json.dumps(calendar_patterns),
            json.dumps(work_patterns),
            datetime.now().isoformat(),
            confidence,
            interaction_count
        ))
        
        conn.commit()
        conn.close()
    
    def get_patterns(self, user_id: str) -> Dict:
        """
        Retrieve saved patterns for user.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT email_patterns, calendar_patterns, work_patterns, confidence_score, last_updated
            FROM user_patterns
            WHERE user_id = ?
        """, (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            'email_patterns': json.loads(row['email_patterns']),
            'calendar_patterns': json.loads(row['calendar_patterns']),
            'work_patterns': json.loads(row['work_patterns']),
            'confidence_score': row['confidence_score'],
            'last_updated': row['last_updated']
        }


if __name__ == '__main__':
    # Test pattern analyzer
    import sys
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'pattern_learning.db'
    user_id = sys.argv[2] if len(sys.argv) > 2 else 'test_user'
    
    analyzer = UserPatternAnalyzer(db_path)
    
    print(f"Analyzing patterns for user: {user_id}\n")
    
    # Analyze email patterns
    print("Email Patterns:")
    email_patterns = analyzer.analyze_email_patterns(user_id)
    print(json.dumps(email_patterns, indent=2))
    
    # Analyze calendar patterns
    print("\nCalendar Patterns:")
    calendar_patterns = analyzer.analyze_calendar_patterns(user_id)
    print(json.dumps(calendar_patterns, indent=2))
    
    # Analyze work patterns
    print("\nWork Patterns:")
    work_patterns = analyzer.analyze_work_patterns(user_id)
    print(json.dumps(work_patterns, indent=2))
    
    # Save patterns
    print("\nSaving patterns...")
    analyzer.save_patterns(user_id)
    print("✓ Patterns saved")
