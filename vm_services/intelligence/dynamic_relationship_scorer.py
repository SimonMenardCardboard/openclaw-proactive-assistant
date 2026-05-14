#!/usr/bin/env python3
"""
Dynamic Relationship Scorer

Learns relationship importance from actual user behavior:
- Who you reply to quickly = important
- Who you meet with often = important  
- Who you email frequently = important
- Adapts per-user (law firm vs personal communication patterns)

Integrates with unified contacts system.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import statistics

class DynamicRelationshipScorer:
    """Dynamic relationship scoring with behavior learning."""
    
    def __init__(self, context_db_path: Optional[Path] = None):
        """
        Initialize dynamic scorer.
        
        Args:
            context_db_path: Path to context database (default: auto-detect)
        """
        if context_db_path is None:
            context_db_path = Path.home() / ".openclaw/workspace/integrations/intelligence/data/context.db"
        
        self.db_path = Path(context_db_path)
        self._init_database()
    
    def _init_database(self):
        """Create dynamic scoring tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Communication events (detailed logs)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS communication_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                event_type TEXT NOT NULL,  -- email_sent, email_received, meeting_attended
                subject TEXT,
                timestamp TIMESTAMP NOT NULL,
                response_time_minutes INTEGER,  -- for replies
                is_group BOOLEAN DEFAULT 0,
                metadata TEXT,  -- JSON
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Relationship scores (calculated from events)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dynamic_relationship_scores (
                email TEXT PRIMARY KEY,
                importance_score REAL DEFAULT 0.0,
                recency_score REAL DEFAULT 0.0,
                frequency_score REAL DEFAULT 0.0,
                responsiveness_score REAL DEFAULT 0.0,
                meeting_score REAL DEFAULT 0.0,
                
                -- Stats
                total_emails_sent INTEGER DEFAULT 0,
                total_emails_received INTEGER DEFAULT 0,
                total_meetings INTEGER DEFAULT 0,
                avg_response_time_minutes REAL,
                last_contact TIMESTAMP,
                first_contact TIMESTAMP,
                
                -- Adaptive weights (learned per user)
                weight_recency REAL DEFAULT 0.25,
                weight_frequency REAL DEFAULT 0.30,
                weight_responsiveness REAL DEFAULT 0.25,
                weight_meeting REAL DEFAULT 0.20,
                
                calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # User behavior profile (learns communication patterns)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_behavior_profile (
                profile_key TEXT PRIMARY KEY,
                profile_value REAL,
                confidence REAL DEFAULT 0.0,
                sample_size INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Follow-up suggestions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS follow_up_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                suggestion_type TEXT NOT NULL,  -- no_contact, slow_reply, missed_meeting
                days_since_contact INTEGER,
                importance_score REAL,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                dismissed_at TIMESTAMP,
                acted_on_at TIMESTAMP
            )
        ''')
        
        # Indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_comm_events_email ON communication_events(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_comm_events_timestamp ON communication_events(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_follow_ups_email ON follow_up_suggestions(email)')
        
        conn.commit()
        conn.close()
    
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
        
        # Recalculate score for this contact
        self.calculate_score(to_email)
        
        return event_id
    
    def log_email_received(self, from_email: str, subject: str = None,
                          timestamp: Optional[datetime] = None) -> int:
        """
        Log an incoming email.
        
        Args:
            from_email: Sender email
            subject: Email subject
            timestamp: When received (default: now)
            
        Returns:
            Event ID
        """
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
        
        # Recalculate score
        self.calculate_score(from_email)
        
        return event_id
    
    def log_meeting(self, attendee_email: str, subject: str = None,
                   timestamp: Optional[datetime] = None) -> int:
        """
        Log a meeting with an attendee.
        
        Args:
            attendee_email: Attendee email
            subject: Meeting subject
            timestamp: When meeting occurred (default: now)
            
        Returns:
            Event ID
        """
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
        
        # Recalculate score
        self.calculate_score(attendee_email)
        
        return event_id
    
    def calculate_score(self, email: str) -> float:
        """
        Calculate dynamic importance score for a contact.
        
        Args:
            email: Contact email
            
        Returns:
            Importance score (0-100)
        """
        email = email.lower()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all communication events for this contact
        cursor.execute('''
            SELECT event_type, timestamp, response_time_minutes
            FROM communication_events
            WHERE email = ?
            ORDER BY timestamp DESC
        ''', (email,))
        
        events = cursor.fetchall()
        
        if not events:
            conn.close()
            return 0.0
        
        # Calculate component scores
        now = datetime.now()
        
        # 1. Recency Score (0-100)
        # Most recent contact
        last_contact = datetime.fromisoformat(events[0][1])
        days_since = (now - last_contact).days
        
        if days_since <= 1:
            recency_score = 100.0
        elif days_since <= 7:
            recency_score = 90.0
        elif days_since <= 14:
            recency_score = 70.0
        elif days_since <= 30:
            recency_score = 50.0
        elif days_since <= 90:
            recency_score = 25.0
        else:
            recency_score = max(10.0, 100.0 - (days_since / 365.0 * 90.0))
        
        # 2. Frequency Score (0-100)
        # Count emails in last 30/90 days
        thirty_days_ago = now - timedelta(days=30)
        ninety_days_ago = now - timedelta(days=90)
        
        emails_30d = sum(1 for e in events if datetime.fromisoformat(e[1]) >= thirty_days_ago)
        emails_90d = sum(1 for e in events if datetime.fromisoformat(e[1]) >= ninety_days_ago)
        
        # Normalize to weekly rate
        emails_per_week = emails_30d / 4.0
        
        if emails_per_week >= 5:
            frequency_score = 100.0
        elif emails_per_week >= 2:
            frequency_score = 80.0
        elif emails_per_week >= 1:
            frequency_score = 60.0
        elif emails_per_week >= 0.5:
            frequency_score = 40.0
        else:
            frequency_score = max(20.0, emails_per_week * 20.0)
        
        # 3. Responsiveness Score (0-100)
        # Average reply time (for emails you sent)
        sent_events = [e for e in events if e[0] == 'email_sent']
        response_times = [e[2] for e in sent_events if e[2] is not None]
        
        if response_times:
            avg_response = statistics.mean(response_times)
            
            if avg_response <= 60:  # < 1 hour
                responsiveness_score = 100.0
            elif avg_response <= 240:  # < 4 hours
                responsiveness_score = 85.0
            elif avg_response <= 1440:  # < 1 day
                responsiveness_score = 70.0
            elif avg_response <= 4320:  # < 3 days
                responsiveness_score = 50.0
            else:
                responsiveness_score = 30.0
        else:
            # No response time data, use neutral score
            responsiveness_score = 50.0
        
        # 4. Meeting Score (0-100)
        # Meetings are higher-touch than emails
        meeting_events = [e for e in events if e[0] == 'meeting_attended']
        meetings_30d = sum(1 for e in meeting_events if datetime.fromisoformat(e[1]) >= thirty_days_ago)
        
        meetings_per_week = meetings_30d / 4.0
        
        if meetings_per_week >= 2:
            meeting_score = 100.0
        elif meetings_per_week >= 1:
            meeting_score = 85.0
        elif meetings_per_week >= 0.5:
            meeting_score = 70.0
        elif meetings_per_week > 0:
            meeting_score = 50.0
        else:
            meeting_score = 0.0
        
        # Get adaptive weights (learned from user behavior)
        cursor.execute('''
            SELECT weight_recency, weight_frequency, weight_responsiveness, weight_meeting
            FROM dynamic_relationship_scores
            WHERE email = ?
        ''', (email,))
        
        weights = cursor.fetchone()
        
        if weights:
            w_recency, w_frequency, w_responsiveness, w_meeting = weights
        else:
            # Default weights
            w_recency = 0.25
            w_frequency = 0.30
            w_responsiveness = 0.25
            w_meeting = 0.20
        
        # Calculate weighted total
        total_score = (
            recency_score * w_recency +
            frequency_score * w_frequency +
            responsiveness_score * w_responsiveness +
            meeting_score * w_meeting
        )
        
        # Count stats
        total_sent = sum(1 for e in events if e[0] == 'email_sent')
        total_received = sum(1 for e in events if e[0] == 'email_received')
        total_meetings = len(meeting_events)
        
        first_contact = datetime.fromisoformat(events[-1][1])
        
        avg_response = statistics.mean(response_times) if response_times else None
        
        # Update or insert score
        cursor.execute('''
            INSERT OR REPLACE INTO dynamic_relationship_scores
            (email, importance_score, recency_score, frequency_score, 
             responsiveness_score, meeting_score,
             total_emails_sent, total_emails_received, total_meetings,
             avg_response_time_minutes, last_contact, first_contact,
             weight_recency, weight_frequency, weight_responsiveness, weight_meeting,
             calculated_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            email, total_score, recency_score, frequency_score,
            responsiveness_score, meeting_score,
            total_sent, total_received, total_meetings,
            avg_response, last_contact, first_contact,
            w_recency, w_frequency, w_responsiveness, w_meeting,
            now, now
        ))
        
        conn.commit()
        
        # Also update unified_contacts table if it exists
        try:
            cursor.execute('''
                UPDATE unified_contacts
                SET importance_score = ?, 
                    total_emails = ?,
                    total_meetings = ?,
                    last_contact = ?,
                    updated_at = ?
                WHERE primary_email = ? OR id IN (
                    SELECT unified_contact_id FROM contact_emails WHERE email = ?
                )
            ''', (total_score, total_sent + total_received, total_meetings, 
                  last_contact, now, email, email))
            conn.commit()
        except sqlite3.OperationalError:
            # unified_contacts table doesn't exist, skip
            pass
        
        conn.close()
        
        return total_score
    
    def recalculate_all_scores(self) -> int:
        """
        Recalculate scores for all contacts with communication history.
        
        Returns:
            Number of contacts scored
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT DISTINCT email FROM communication_events')
        emails = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        
        for email in emails:
            self.calculate_score(email)
        
        return len(emails)
    
    def get_follow_up_suggestions(self, min_importance: float = 40.0, 
                                  days_threshold: int = 14) -> List[Dict]:
        """
        Get contacts that need follow-up.
        
        Args:
            min_importance: Minimum importance score to suggest
            days_threshold: Days since last contact to trigger suggestion
            
        Returns:
            List of follow-up suggestions
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Find important contacts you haven't contacted recently
        cutoff_date = datetime.now() - timedelta(days=days_threshold)
        
        cursor.execute('''
            SELECT email, importance_score, last_contact,
                   total_emails_sent, total_emails_received, total_meetings
            FROM dynamic_relationship_scores
            WHERE importance_score >= ?
              AND last_contact < ?
            ORDER BY importance_score DESC
        ''', (min_importance, cutoff_date))
        
        suggestions = []
        
        for row in cursor.fetchall():
            email, importance, last_contact, sent, received, meetings = row
            
            days_since = (datetime.now() - datetime.fromisoformat(last_contact)).days
            
            # Get contact name from unified_contacts
            cursor.execute('''
                SELECT primary_name, company, relationship
                FROM unified_contacts
                WHERE primary_email = ? OR id IN (
                    SELECT unified_contact_id FROM contact_emails WHERE email = ?
                )
            ''', (email, email))
            
            contact_info = cursor.fetchone()
            
            if contact_info:
                name, company, relationship = contact_info
            else:
                name = email.split('@')[0].replace('.', ' ').title()
                company = None
                relationship = None
            
            # Create suggestion message
            if days_since >= 30:
                urgency = "high"
                message = f"Haven't contacted {name} in {days_since} days (important contact)"
            elif days_since >= 14:
                urgency = "medium"
                message = f"It's been {days_since} days since you contacted {name}"
            else:
                urgency = "low"
                message = f"Check in with {name}?"
            
            suggestions.append({
                'email': email,
                'name': name,
                'company': company,
                'relationship': relationship,
                'importance_score': importance,
                'days_since_contact': days_since,
                'last_contact': last_contact,
                'urgency': urgency,
                'message': message,
                'stats': {
                    'emails_sent': sent,
                    'emails_received': received,
                    'meetings': meetings
                }
            })
        
        conn.close()
        
        return suggestions
    
    def get_top_relationships(self, limit: int = 20) -> List[Dict]:
        """
        Get top relationships by importance score.
        
        Args:
            limit: Max results
            
        Returns:
            List of top relationships
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT email, importance_score, recency_score, frequency_score,
                   responsiveness_score, meeting_score,
                   total_emails_sent, total_emails_received, total_meetings,
                   last_contact
            FROM dynamic_relationship_scores
            ORDER BY importance_score DESC
            LIMIT ?
        ''', (limit,))
        
        relationships = []
        
        for row in cursor.fetchall():
            email = row[0]
            
            # Get contact name
            cursor.execute('''
                SELECT primary_name, company, role, relationship
                FROM unified_contacts
                WHERE primary_email = ? OR id IN (
                    SELECT unified_contact_id FROM contact_emails WHERE email = ?
                )
            ''', (email, email))
            
            contact_info = cursor.fetchone()
            
            if contact_info:
                name, company, role, relationship = contact_info
            else:
                name = email.split('@')[0].replace('.', ' ').title()
                company = role = relationship = None
            
            relationships.append({
                'email': email,
                'name': name,
                'company': company,
                'role': role,
                'relationship': relationship,
                'importance_score': row[1],
                'recency_score': row[2],
                'frequency_score': row[3],
                'responsiveness_score': row[4],
                'meeting_score': row[5],
                'total_emails_sent': row[6],
                'total_emails_received': row[7],
                'total_meetings': row[8],
                'last_contact': row[9]
            })
        
        conn.close()
        
        return relationships
    
    def import_from_gmail_sent(self, account: str = "lacrosseguy76665@gmail.com", 
                              days_back: int = 90) -> int:
        """
        Import communication history from Gmail sent messages.
        
        Args:
            account: Gmail account
            days_back: Days of history to import
            
        Returns:
            Number of events imported
        """
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent))
            from gmail_api import GmailAPI
            
            # Determine token file
            token_file = Path.home() / ".openclaw/tokens/default_google_personal.json"
            
            gmail = GmailAPI(email=account, token_file=token_file)
            sent_emails = gmail.get_sent_messages(days_back=days_back, max_results=1000)
            
            imported = 0
            
            for email in sent_emails:
                # Extract recipient
                to_field = email.get('to', '')
                
                # Simple email extraction (can use regex for production)
                if '<' in to_field and '>' in to_field:
                    to_email = to_field.split('<')[1].split('>')[0].strip().lower()
                else:
                    to_email = to_field.strip().lower()
                
                if not to_email or '@' not in to_email:
                    continue
                
                # Parse timestamp
                try:
                    date_str = email.get('date', '')
                    timestamp = datetime.fromisoformat(date_str) if date_str else datetime.now()
                except:
                    timestamp = datetime.now()
                
                # Log event
                self.log_email_sent(
                    to_email=to_email,
                    subject=email.get('subject'),
                    timestamp=timestamp
                )
                
                imported += 1
            
            return imported
            
        except Exception as e:
            print(f"Error importing from Gmail: {e}")
            return 0


if __name__ == '__main__':
    # Test dynamic scorer
    scorer = DynamicRelationshipScorer()
    
    print("Dynamic Relationship Scorer Test")
    print("=" * 80)
    
    # Import from Gmail
    print("\n1. Importing communication history from Gmail...")
    imported = scorer.import_from_gmail_sent(days_back=180)
    print(f"   Imported {imported} sent emails")
    
    # Recalculate all scores
    print("\n2. Calculating relationship scores...")
    scored = scorer.recalculate_all_scores()
    print(f"   Scored {scored} contacts")
    
    # Show top relationships
    print("\n3. Top 10 Relationships:")
    print("-" * 80)
    top = scorer.get_top_relationships(limit=10)
    
    for i, rel in enumerate(top, 1):
        print(f"\n{i}. {rel['name']} ({rel['email']})")
        print(f"   Score: {rel['importance_score']:.1f}/100")
        if rel.get('company'):
            print(f"   Company: {rel['company']}")
        print(f"   Emails: {rel['total_emails_sent']} sent, {rel['total_emails_received']} received")
        if rel['total_meetings'] > 0:
            print(f"   Meetings: {rel['total_meetings']}")
        print(f"   Last contact: {rel['last_contact']}")
    
    # Show follow-up suggestions
    print("\n4. Follow-up Suggestions:")
    print("-" * 80)
    suggestions = scorer.get_follow_up_suggestions(min_importance=50.0, days_threshold=14)
    
    if suggestions:
        for sug in suggestions[:5]:
            print(f"\n⚠️  {sug['urgency'].upper()}: {sug['message']}")
            if sug.get('company'):
                print(f"   Company: {sug['company']}")
            print(f"   Importance: {sug['importance_score']:.1f}/100")
            print(f"   Last contact: {sug['last_contact']}")
    else:
        print("   No follow-ups needed!")
