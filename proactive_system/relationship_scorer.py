#!/usr/bin/env python3
"""
Relationship Scorer (Merged Intelligence Layer)

Dynamic behavioral relationship scoring system.
Learns importance from user behavior:
- Reply speed (faster = more important)
- Email frequency (more = more important)
- Meeting frequency (more = more important)
- Recency (recent contact = more important)

Merged from vm_services/intelligence/ into proactive_system/
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import statistics


class RelationshipScorer:
    """Calculate importance scores from communication patterns."""
    
    def __init__(self, context_db_path: Optional[Path] = None):
        """
        Initialize relationship scorer.
        
        Args:
            context_db_path: Path to context database
        """
        if context_db_path is None:
            context_db_path = Path(__file__).parent / "context.db"
        
        self.db_path = Path(context_db_path)
    
    def log_email_sent(self, to_email: str, subject: str = None, 
                       timestamp: Optional[datetime] = None,
                       response_time_minutes: Optional[int] = None) -> int:
        """
        Log an outgoing email.
        
        Args:
            to_email: Recipient email
            subject: Email subject
            timestamp: When sent (default: now)
            response_time_minutes: If this is a reply, how long it took
            
        Returns:
            Event ID
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO communication_events 
            (email, event_type, subject, timestamp, response_time_minutes)
            VALUES (?, ?, ?, ?, ?)
        ''', (to_email.lower(), 'email_sent', subject, timestamp, response_time_minutes))
        
        event_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return event_id
    
    def log_email_received(self, from_email: str, subject: str = None,
                          timestamp: Optional[datetime] = None) -> int:
        """Log an incoming email."""
        if timestamp is None:
            timestamp = datetime.now()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO communication_events 
            (email, event_type, subject, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (from_email.lower(), 'email_received', subject, timestamp))
        
        event_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return event_id
    
    def log_meeting(self, attendee_email: str, subject: str = None,
                   timestamp: Optional[datetime] = None) -> int:
        """Log a calendar meeting."""
        if timestamp is None:
            timestamp = datetime.now()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO communication_events 
            (email, event_type, subject, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (attendee_email.lower(), 'meeting_attended', subject, timestamp))
        
        event_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return event_id
    
    def calculate_score(self, email: str, days_lookback: int = 90) -> Dict:
        """
        Calculate importance score for a contact.
        
        Args:
            email: Contact email
            days_lookback: How many days to analyze
            
        Returns:
            Dict with scores and stats
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = datetime.now() - timedelta(days=days_lookback)
        
        # Get all communication events
        cursor.execute('''
            SELECT event_type, timestamp, response_time_minutes
            FROM communication_events
            WHERE email = ? AND timestamp >= ?
            ORDER BY timestamp DESC
        ''', (email.lower(), cutoff))
        
        events = cursor.fetchall()
        
        if not events:
            return {
                'importance_score': 0.0,
                'recency_score': 0.0,
                'frequency_score': 0.0,
                'responsiveness_score': 0.0,
                'meeting_score': 0.0
            }
        
        # Calculate component scores
        recency_score = self._calculate_recency(events)
        frequency_score = self._calculate_frequency(events, days_lookback)
        responsiveness_score = self._calculate_responsiveness(events)
        meeting_score = self._calculate_meetings(events, days_lookback)
        
        # Weighted importance (tunable)
        importance_score = (
            0.25 * recency_score +
            0.30 * frequency_score +
            0.25 * responsiveness_score +
            0.20 * meeting_score
        )
        
        # Store in database
        cursor.execute('''
            INSERT OR REPLACE INTO dynamic_relationship_scores
            (email, importance_score, recency_score, frequency_score, 
             responsiveness_score, meeting_score, calculated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (email.lower(), importance_score, recency_score, frequency_score,
              responsiveness_score, meeting_score, datetime.now()))
        
        conn.commit()
        conn.close()
        
        return {
            'importance_score': round(importance_score, 2),
            'recency_score': round(recency_score, 2),
            'frequency_score': round(frequency_score, 2),
            'responsiveness_score': round(responsiveness_score, 2),
            'meeting_score': round(meeting_score, 2)
        }
    
    def _calculate_recency(self, events: List[Tuple]) -> float:
        """Score based on how recently you communicated (0-100)."""
        if not events:
            return 0.0
        
        # Most recent event
        most_recent = datetime.fromisoformat(events[0][1])
        days_ago = (datetime.now() - most_recent).days
        
        # Exponential decay: 100 at 0 days, 50 at 30 days, ~0 at 180 days
        if days_ago == 0:
            return 100.0
        
        score = 100 * (0.5 ** (days_ago / 30))
        return min(100.0, max(0.0, score))
    
    def _calculate_frequency(self, events: List[Tuple], days: int) -> float:
        """Score based on communication frequency (0-100)."""
        if not events:
            return 0.0
        
        total_events = len(events)
        
        # emails per week
        emails_per_week = (total_events / days) * 7
        
        # Score: 0-1/week=0-20, 1-3/week=20-60, 3-7/week=60-90, 7+=90-100
        if emails_per_week >= 7:
            score = 90 + min(10, emails_per_week - 7)
        elif emails_per_week >= 3:
            score = 60 + ((emails_per_week - 3) / 4) * 30
        elif emails_per_week >= 1:
            score = 20 + ((emails_per_week - 1) / 2) * 40
        else:
            score = emails_per_week * 20
        
        return min(100.0, max(0.0, score))
    
    def _calculate_responsiveness(self, events: List[Tuple]) -> float:
        """Score based on how quickly you reply (0-100)."""
        # Extract response times
        response_times = [e[2] for e in events if e[2] is not None]
        
        if not response_times:
            return 50.0  # Neutral if no response data
        
        avg_response_minutes = statistics.mean(response_times)
        
        # Score: <15min=100, <1hr=90, <4hr=70, <1day=50, <1week=20, >1week=0
        if avg_response_minutes < 15:
            return 100.0
        elif avg_response_minutes < 60:
            return 90.0
        elif avg_response_minutes < 240:
            return 70.0
        elif avg_response_minutes < 1440:  # 1 day
            return 50.0
        elif avg_response_minutes < 10080:  # 1 week
            return 20.0
        else:
            return 0.0
    
    def _calculate_meetings(self, events: List[Tuple], days: int) -> float:
        """Score based on meeting frequency (0-100)."""
        meeting_count = sum(1 for e in events if e[0] == 'meeting_attended')
        
        if meeting_count == 0:
            return 0.0
        
        meetings_per_month = (meeting_count / days) * 30
        
        # Score: 0=0, 1/mo=30, 2/mo=50, 4/mo=70, 8/mo=90, 12+/mo=100
        if meetings_per_month >= 12:
            return 100.0
        elif meetings_per_month >= 8:
            return 90.0
        elif meetings_per_month >= 4:
            return 70.0
        elif meetings_per_month >= 2:
            return 50.0
        elif meetings_per_month >= 1:
            return 30.0
        else:
            return meetings_per_month * 30
    
    def get_vips(self, min_score: float = 70.0, limit: int = 50) -> List[Dict]:
        """
        Get VIP contacts (high importance).
        
        Args:
            min_score: Minimum importance score
            limit: Max results
            
        Returns:
            List of VIP contacts with scores
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT email, importance_score, recency_score, frequency_score,
                   responsiveness_score, meeting_score
            FROM dynamic_relationship_scores
            WHERE importance_score >= ?
            ORDER BY importance_score DESC
            LIMIT ?
        ''', (min_score, limit))
        
        vips = []
        for row in cursor.fetchall():
            vips.append({
                'email': row[0],
                'importance_score': row[1],
                'recency_score': row[2],
                'frequency_score': row[3],
                'responsiveness_score': row[4],
                'meeting_score': row[5]
            })
        
        conn.close()
        return vips
    
    def get_follow_up_suggestions(self, days_threshold: int = 14, 
                                  min_score: float = 60.0,
                                  limit: int = 20) -> List[Dict]:
        """
        Get contacts you should follow up with.
        
        Args:
            days_threshold: Haven't contacted in N days
            min_score: Minimum importance score
            limit: Max results
            
        Returns:
            List of follow-up suggestions
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = datetime.now() - timedelta(days=days_threshold)
        
        # Find important contacts with no recent contact
        cursor.execute('''
            SELECT 
                s.email,
                s.importance_score,
                MAX(e.timestamp) as last_contact,
                JULIANDAY('now') - JULIANDAY(MAX(e.timestamp)) as days_since
            FROM dynamic_relationship_scores s
            JOIN communication_events e ON e.email = s.email
            WHERE s.importance_score >= ?
            GROUP BY s.email
            HAVING MAX(e.timestamp) < ?
            ORDER BY s.importance_score DESC, days_since DESC
            LIMIT ?
        ''', (min_score, cutoff, limit))
        
        suggestions = []
        for row in cursor.fetchall():
            suggestions.append({
                'email': row[0],
                'importance_score': row[1],
                'last_contact': row[2],
                'days_since_contact': int(row[3])
            })
        
        conn.close()
        return suggestions
    
    def recalculate_all(self, days_lookback: int = 90):
        """Recalculate scores for all contacts with communication history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all unique emails from communication events
        cursor.execute('''
            SELECT DISTINCT email
            FROM communication_events
            WHERE timestamp >= ?
        ''', (datetime.now() - timedelta(days=days_lookback),))
        
        emails = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        print(f"♻️  Recalculating scores for {len(emails)} contacts...")
        
        for i, email in enumerate(emails, 1):
            self.calculate_score(email, days_lookback)
            if i % 50 == 0:
                print(f"  {i}/{len(emails)}...")
        
        print(f"✅ Recalculated {len(emails)} contact scores")


if __name__ == "__main__":
    # Demo usage
    scorer = RelationshipScorer()
    
    # Recalculate all scores
    scorer.recalculate_all(days_lookback=90)
    
    # Get VIPs
    vips = scorer.get_vips(min_score=70.0, limit=10)
    print(f"\n🌟 VIP Contacts (score >= 70):")
    for vip in vips:
        print(f"  {vip['email']}: {vip['importance_score']:.1f}")
    
    # Get follow-up suggestions
    followups = scorer.get_follow_up_suggestions(days_threshold=14, min_score=60.0)
    print(f"\n📬 Follow-up Suggestions ({len(followups)}):")
    for f in followups[:5]:
        print(f"  {f['email']}: {f['days_since_contact']} days (score {f['importance_score']:.1f})")
