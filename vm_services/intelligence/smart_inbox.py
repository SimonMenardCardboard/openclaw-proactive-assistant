#!/usr/bin/env python3
"""
Smart Inbox - Transmogrifier MVP

Priority-sorted unified inbox across all email accounts.

Features:
- Multi-account aggregation (Gmail, Outlook, iCloud)
- Priority scoring (VIP > Important > Normal)
- Behavioral learning (who you reply to quickly = important)
- Email caching (avoid repeated API calls)
- Read/archive sync across devices
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import hashlib

class SmartInbox:
    """Smart inbox with priority sorting."""
    
    def __init__(self, context_db_path: Optional[Path] = None):
        """
        Initialize smart inbox.
        
        Args:
            context_db_path: Path to context database
        """
        if context_db_path is None:
            context_db_path = Path.home() / ".openclaw/workspace/integrations/intelligence/data/context.db"
        
        self.db_path = Path(context_db_path)
        self._init_database()
    
    def _init_database(self):
        """Create inbox cache tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Email cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inbox_cache (
                id TEXT PRIMARY KEY,  -- message_id
                account TEXT NOT NULL,
                thread_id TEXT,
                from_email TEXT NOT NULL,
                from_name TEXT,
                to_email TEXT,
                subject TEXT,
                snippet TEXT,
                body TEXT,
                received_at TIMESTAMP NOT NULL,
                has_attachments BOOLEAN DEFAULT 0,
                
                -- Priority scoring
                priority_score REAL DEFAULT 50.0,
                priority_level TEXT DEFAULT 'normal',  -- vip, important, normal, low
                
                -- State
                is_read BOOLEAN DEFAULT 0,
                is_archived BOOLEAN DEFAULT 0,
                is_snoozed BOOLEAN DEFAULT 0,
                snooze_until TIMESTAMP,
                
                -- Metadata
                labels TEXT,  -- JSON
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # User actions (for learning)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inbox_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id TEXT NOT NULL,
                action TEXT NOT NULL,  -- read, archive, snooze, star, mark_vip
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (email_id) REFERENCES inbox_cache(id)
            )
        ''')
        
        # Indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_inbox_received ON inbox_cache(received_at DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_inbox_priority ON inbox_cache(priority_score DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_inbox_read ON inbox_cache(is_read, received_at DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_inbox_from ON inbox_cache(from_email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_inbox_actions_email ON inbox_actions(email_id)')
        
        conn.commit()
        conn.close()
    
    def sync_emails(self, account: str, emails: List[Dict]) -> int:
        """
        Sync emails to inbox cache.
        
        Args:
            account: Account name (e.g., 'lacrosseguy76665@gmail.com')
            emails: List of email dicts from API
            
        Returns:
            Number of emails synced
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        synced = 0
        
        for email in emails:
            # Generate stable ID
            message_id = email.get('id') or self._generate_id(email)
            
            # Extract fields
            from_field = email.get('from', '')
            from_email = self._extract_email(from_field)
            from_name = self._extract_name(from_field)
            
            to_field = email.get('to', '')
            to_email = self._extract_email(to_field) if to_field else None
            
            subject = email.get('subject', '(no subject)')
            snippet = email.get('snippet', '')
            body = email.get('body', '')
            
            # Parse timestamp
            received_at = email.get('received_at') or datetime.now()
            if isinstance(received_at, str):
                try:
                    received_at = datetime.fromisoformat(received_at)
                except:
                    received_at = datetime.now()
            
            # Check if email already exists
            cursor.execute('SELECT id FROM inbox_cache WHERE id = ?', (message_id,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing
                cursor.execute('''
                    UPDATE inbox_cache
                    SET snippet = ?, body = ?, updated_at = ?
                    WHERE id = ?
                ''', (snippet, body, datetime.now(), message_id))
            else:
                # Insert new
                cursor.execute('''
                    INSERT INTO inbox_cache
                    (id, account, from_email, from_name, to_email, subject, 
                     snippet, body, received_at, cached_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    message_id, account, from_email, from_name, to_email,
                    subject, snippet, body, received_at, datetime.now()
                ))
                
                synced += 1
        
        conn.commit()
        conn.close()
        
        # Recalculate priority scores for new emails
        self.recalculate_priorities()
        
        return synced
    
    def recalculate_priorities(self):
        """Recalculate priority scores for all emails."""
        # Import relationship scorer
        try:
            from dynamic_relationship_scorer import DynamicRelationshipScorer
            scorer = DynamicRelationshipScorer(context_db_path=self.db_path)
        except:
            scorer = None
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all unread emails
        cursor.execute('''
            SELECT id, from_email, subject, received_at
            FROM inbox_cache
            WHERE is_read = 0 AND is_archived = 0
        ''')
        
        emails = cursor.fetchall()
        
        for email_id, from_email, subject, received_at in emails:
            # Calculate priority score (0-100)
            priority_score = 50.0  # Default: medium
            
            # Factor 1: Relationship importance (if available)
            if scorer and from_email:
                rel_score = scorer.calculate_score(from_email)
                # Weight relationship score heavily (60%)
                priority_score = rel_score * 0.6 + priority_score * 0.4
            
            # Factor 2: Recency (newer = slightly higher priority)
            try:
                received_dt = datetime.fromisoformat(received_at) if isinstance(received_at, str) else received_at
                hours_ago = (datetime.now() - received_dt).total_seconds() / 3600
                
                if hours_ago <= 1:
                    recency_boost = 5.0
                elif hours_ago <= 6:
                    recency_boost = 2.0
                else:
                    recency_boost = 0.0
                
                priority_score += recency_boost
            except:
                pass
            
            # Factor 3: Subject keywords (urgent, important)
            subject_lower = subject.lower() if subject else ''
            
            if any(word in subject_lower for word in ['urgent', 'asap', 'important', 'critical']):
                priority_score += 10.0
            
            # Clamp to 0-100
            priority_score = max(0.0, min(100.0, priority_score))
            
            # Determine priority level
            if priority_score >= 70:
                priority_level = 'vip'
            elif priority_score >= 50:
                priority_level = 'important'
            elif priority_score >= 30:
                priority_level = 'normal'
            else:
                priority_level = 'low'
            
            # Update email
            cursor.execute('''
                UPDATE inbox_cache
                SET priority_score = ?, priority_level = ?, updated_at = ?
                WHERE id = ?
            ''', (priority_score, priority_level, datetime.now(), email_id))
        
        conn.commit()
        conn.close()
    
    def get_inbox(self, 
                  account: Optional[str] = None,
                  priority_level: Optional[str] = None,
                  unread_only: bool = True,
                  limit: int = 50) -> List[Dict]:
        """
        Get inbox emails (priority-sorted).
        
        Args:
            account: Filter by account (None = all accounts)
            priority_level: Filter by level ('vip', 'important', 'normal', 'low')
            unread_only: Only show unread emails
            limit: Max emails to return
            
        Returns:
            List of email dicts (sorted by priority then recency)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Build query
        query = '''
            SELECT id, account, from_email, from_name, to_email, subject,
                   snippet, received_at, priority_score, priority_level,
                   is_read, is_archived, has_attachments
            FROM inbox_cache
            WHERE is_archived = 0
        '''
        
        params = []
        
        if unread_only:
            query += ' AND is_read = 0'
        
        if account:
            query += ' AND account = ?'
            params.append(account)
        
        if priority_level:
            query += ' AND priority_level = ?'
            params.append(priority_level)
        
        # Sort by priority (desc), then recency (desc)
        query += ' ORDER BY priority_score DESC, received_at DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        
        emails = []
        
        for row in cursor.fetchall():
            emails.append({
                'id': row[0],
                'account': row[1],
                'from_email': row[2],
                'from_name': row[3],
                'to_email': row[4],
                'subject': row[5],
                'snippet': row[6],
                'received_at': row[7],
                'priority_score': row[8],
                'priority_level': row[9],
                'is_read': bool(row[10]),
                'is_archived': bool(row[11]),
                'has_attachments': bool(row[12])
            })
        
        conn.close()
        
        return emails
    
    def mark_read(self, email_id: str) -> bool:
        """Mark email as read."""
        return self._update_email(email_id, {'is_read': True})
    
    def mark_archived(self, email_id: str) -> bool:
        """Mark email as archived."""
        return self._update_email(email_id, {'is_archived': True})
    
    def snooze(self, email_id: str, until: datetime) -> bool:
        """Snooze email until a specific time."""
        return self._update_email(email_id, {
            'is_snoozed': True,
            'snooze_until': until
        })
    
    def log_action(self, email_id: str, action: str):
        """Log user action for learning."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO inbox_actions (email_id, action, timestamp)
            VALUES (?, ?, ?)
        ''', (email_id, action, datetime.now()))
        
        conn.commit()
        conn.close()
    
    def get_stats(self) -> Dict:
        """Get inbox statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total emails
        cursor.execute('SELECT COUNT(*) FROM inbox_cache WHERE is_archived = 0')
        total = cursor.fetchone()[0]
        
        # Unread emails
        cursor.execute('SELECT COUNT(*) FROM inbox_cache WHERE is_read = 0 AND is_archived = 0')
        unread = cursor.fetchone()[0]
        
        # By priority level
        cursor.execute('''
            SELECT priority_level, COUNT(*)
            FROM inbox_cache
            WHERE is_read = 0 AND is_archived = 0
            GROUP BY priority_level
        ''')
        
        by_priority = dict(cursor.fetchall())
        
        # By account
        cursor.execute('''
            SELECT account, COUNT(*)
            FROM inbox_cache
            WHERE is_read = 0 AND is_archived = 0
            GROUP BY account
        ''')
        
        by_account = dict(cursor.fetchall())
        
        conn.close()
        
        return {
            'total_emails': total,
            'unread_emails': unread,
            'vip': by_priority.get('vip', 0),
            'important': by_priority.get('important', 0),
            'normal': by_priority.get('normal', 0),
            'low': by_priority.get('low', 0),
            'by_account': by_account
        }
    
    def _update_email(self, email_id: str, updates: Dict) -> bool:
        """Update email fields."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        set_clauses = []
        params = []
        
        for key, value in updates.items():
            set_clauses.append(f"{key} = ?")
            params.append(value)
        
        # Always update updated_at
        set_clauses.append("updated_at = ?")
        params.append(datetime.now())
        
        params.append(email_id)
        
        query = f"UPDATE inbox_cache SET {', '.join(set_clauses)} WHERE id = ?"
        
        cursor.execute(query, params)
        
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        
        return success
    
    def _generate_id(self, email: Dict) -> str:
        """Generate stable email ID from content."""
        # Hash from + subject + received_at
        content = f"{email.get('from', '')}{email.get('subject', '')}{email.get('received_at', '')}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _extract_email(self, from_field: str) -> str:
        """Extract email from 'Name <email>' format."""
        import re
        match = re.search(r'<(.+?)>', from_field)
        if match:
            return match.group(1).lower().strip()
        return from_field.lower().strip()
    
    def _extract_name(self, from_field: str) -> str:
        """Extract name from 'Name <email>' format."""
        import re
        match = re.search(r'^([^<]+)\s*<', from_field)
        if match:
            name = match.group(1).strip().strip('"\'')
            return name
        
        # If no name, use email local part
        email = self._extract_email(from_field)
        if '@' in email:
            return email.split('@')[0].replace('.', ' ').title()
        
        return email


if __name__ == '__main__':
    # Test smart inbox
    inbox = SmartInbox()
    
    print("Smart Inbox Test")
    print("=" * 80)
    
    # Test sync (mock emails)
    test_emails = [
        {
            'id': 'msg1',
            'from': 'Ross Buntrock <ross@legalmensch.com>',
            'to': 'simon@legalmensch.com',
            'subject': 'Urgent: Q2 Review',
            'snippet': 'We need to discuss the Q2 financials ASAP...',
            'body': 'Full email body here...',
            'received_at': datetime.now() - timedelta(hours=2)
        },
        {
            'id': 'msg2',
            'from': 'Newsletter <newsletter@example.com>',
            'to': 'simon@legalmensch.com',
            'subject': 'Weekly Newsletter',
            'snippet': 'Top stories this week...',
            'body': 'Newsletter content...',
            'received_at': datetime.now() - timedelta(hours=12)
        },
        {
            'id': 'msg3',
            'from': 'Alice Johnson <alice@client.com>',
            'to': 'simon@legalmensch.com',
            'subject': 'Contract Review',
            'snippet': 'Can you review the attached contract?',
            'body': 'Please review...',
            'received_at': datetime.now() - timedelta(hours=1)
        }
    ]
    
    print(f"\n1. Syncing {len(test_emails)} emails...")
    synced = inbox.sync_emails('simon@legalmensch.com', test_emails)
    print(f"   Synced: {synced} new emails")
    
    # Get stats
    print(f"\n2. Inbox Statistics:")
    print("-" * 80)
    stats = inbox.get_stats()
    
    print(f"   Total: {stats['total_emails']}")
    print(f"   Unread: {stats['unread_emails']}")
    print(f"\n   By Priority:")
    print(f"   🔴 VIP: {stats['vip']}")
    print(f"   🟡 Important: {stats['important']}")
    print(f"   ⚪ Normal: {stats['normal']}")
    print(f"   ⬇️  Low: {stats['low']}")
    
    # Show inbox
    print(f"\n3. Smart Inbox (priority-sorted):")
    print("-" * 80)
    
    emails = inbox.get_inbox(unread_only=True, limit=10)
    
    for email in emails:
        priority_emoji = {
            'vip': '🔴',
            'important': '🟡',
            'normal': '⚪',
            'low': '⬇️'
        }
        emoji = priority_emoji.get(email['priority_level'], '⚪')
        
        # Time ago
        received_dt = datetime.fromisoformat(email['received_at']) if isinstance(email['received_at'], str) else email['received_at']
        hours_ago = (datetime.now() - received_dt).total_seconds() / 3600
        
        if hours_ago < 1:
            time_str = f"{int(hours_ago * 60)} min ago"
        elif hours_ago < 24:
            time_str = f"{int(hours_ago)} hrs ago"
        else:
            time_str = f"{int(hours_ago / 24)} days ago"
        
        print(f"\n{emoji} {email['from_name']} ({time_str})")
        print(f"   {email['subject']}")
        print(f"   {email['snippet'][:80]}...")
        print(f"   Priority: {email['priority_score']:.1f}/100 ({email['priority_level']})")
