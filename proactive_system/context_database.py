#!/usr/bin/env python3
"""
Context Database - Intelligence Layer

Stores extracted intelligence from emails and calendars:
- Contacts (importance, response times, meeting frequency)
- Recurring meetings
- Focus time patterns
- Preferences extracted from communications
- Tasks/action items
- Shopping lists

Populated from Universal Email + Calendar APIs.
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ContextDatabase:
    """Context database for storing intelligence extracted from email/calendar."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize context database.
        
        Args:
            db_path: Path to context.db (defaults to standard location)
        """
        if db_path is None:
            db_path = Path.home() / '.openclaw/workspace/transmogrifier/context.db'
        
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_schema()
        logger.info(f"[Context DB] Initialized: {self.db_path}")
    
    def _init_schema(self):
        """Initialize database schema."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Contacts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contacts (
                email TEXT PRIMARY KEY,
                name TEXT,
                total_emails INTEGER DEFAULT 0,
                avg_response_hours REAL,
                importance_score REAL DEFAULT 0.0,
                meeting_count INTEGER DEFAULT 0,
                first_contact TIMESTAMP,
                last_contact TIMESTAMP,
                accounts TEXT,  -- JSON list of accounts where contact appears
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Recurring meetings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recurring_meetings (
                recurring_id TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                occurrence_count INTEGER DEFAULT 0,
                organizer TEXT,
                attendees TEXT,  -- JSON
                first_occurrence TIMESTAMP,
                last_occurrence TIMESTAMP,
                accounts TEXT,  -- JSON
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Focus time patterns table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS focus_time_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day_of_week INTEGER,  -- 0=Monday, 6=Sunday
                hour_of_day INTEGER,  -- 0-23
                avg_gap_hours REAL,
                frequency INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(day_of_week, hour_of_day)
            )
        ''')
        
        # Preferences table (extracted from emails/calendar)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,  -- food, meeting_time, location, etc
                preference TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,  -- 0.0 to 1.0
                source TEXT,  -- email, calendar, manual
                evidence TEXT,  -- JSON with supporting data
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tasks/action items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                deadline TIMESTAMP,
                priority INTEGER DEFAULT 3,  -- 1=high, 3=normal, 5=low
                status TEXT DEFAULT 'pending',  -- pending, in_progress, completed
                source TEXT,  -- email_id, calendar_id, manual
                contact_email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        ''')
        
        # Shopping lists table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shopping_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item TEXT NOT NULL,
                category TEXT,  -- groceries, household, personal, etc
                recurring BOOLEAN DEFAULT 0,
                frequency_days INTEGER,  -- how often to buy (for recurring)
                last_purchased TIMESTAMP,
                source TEXT,  -- email, manual
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed BOOLEAN DEFAULT 0
            )
        ''')
        
        # Sync log table (track when data was last synced)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_type TEXT NOT NULL,  -- email, calendar, contacts
                account_email TEXT,
                last_sync TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                items_processed INTEGER DEFAULT 0,
                status TEXT DEFAULT 'success'  -- success, partial, failed
            )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("[Context DB] Schema initialized")
    
    # =========================================================================
    # CONTACTS
    # =========================================================================
    
    def upsert_contact(self, email: str, **kwargs):
        """Insert or update contact."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Check if exists
        cursor.execute('SELECT email FROM contacts WHERE email = ?', (email,))
        exists = cursor.fetchone() is not None
        
        if exists:
            # Update
            set_clauses = []
            values = []
            
            for key, value in kwargs.items():
                if key == 'accounts' and isinstance(value, list):
                    value = json.dumps(value)
                set_clauses.append(f"{key} = ?")
                values.append(value)
            
            set_clauses.append("updated_at = ?")
            values.append(datetime.now().isoformat())
            values.append(email)
            
            query = f"UPDATE contacts SET {', '.join(set_clauses)} WHERE email = ?"
            cursor.execute(query, values)
        else:
            # Insert
            fields = ['email'] + list(kwargs.keys()) + ['created_at', 'updated_at']
            placeholders = ['?'] * len(fields)
            
            values = [email]
            for key, value in kwargs.items():
                if key == 'accounts' and isinstance(value, list):
                    value = json.dumps(value)
                values.append(value)
            
            values.extend([datetime.now().isoformat(), datetime.now().isoformat()])
            
            query = f"INSERT INTO contacts ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
            cursor.execute(query, values)
        
        conn.commit()
        conn.close()
    
    def get_contact(self, email: str) -> Optional[Dict]:
        """Get contact by email."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM contacts WHERE email = ?', (email,))
        row = cursor.fetchone()
        
        conn.close()
        
        if not row:
            return None
        
        columns = [desc[0] for desc in cursor.description]
        contact = dict(zip(columns, row))
        
        # Parse JSON fields
        if contact.get('accounts'):
            contact['accounts'] = json.loads(contact['accounts'])
        
        return contact
    
    def get_top_contacts(self, limit: int = 20) -> List[Dict]:
        """Get top contacts by importance score."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM contacts 
            ORDER BY importance_score DESC 
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        conn.close()
        
        contacts = []
        for row in rows:
            contact = dict(zip(columns, row))
            if contact.get('accounts'):
                contact['accounts'] = json.loads(contact['accounts'])
            contacts.append(contact)
        
        return contacts
    
    # =========================================================================
    # RECURRING MEETINGS
    # =========================================================================
    
    def upsert_recurring_meeting(self, recurring_id: str, **kwargs):
        """Insert or update recurring meeting."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Check if exists
        cursor.execute('SELECT recurring_id FROM recurring_meetings WHERE recurring_id = ?', (recurring_id,))
        exists = cursor.fetchone() is not None
        
        if exists:
            # Update
            set_clauses = []
            values = []
            
            for key, value in kwargs.items():
                if key in ['attendees', 'accounts'] and isinstance(value, list):
                    value = json.dumps(value)
                set_clauses.append(f"{key} = ?")
                values.append(value)
            
            set_clauses.append("updated_at = ?")
            values.append(datetime.now().isoformat())
            values.append(recurring_id)
            
            query = f"UPDATE recurring_meetings SET {', '.join(set_clauses)} WHERE recurring_id = ?"
            cursor.execute(query, values)
        else:
            # Insert
            fields = ['recurring_id'] + list(kwargs.keys()) + ['created_at', 'updated_at']
            placeholders = ['?'] * len(fields)
            
            values = [recurring_id]
            for key, value in kwargs.items():
                if key in ['attendees', 'accounts'] and isinstance(value, list):
                    value = json.dumps(value)
                values.append(value)
            
            values.extend([datetime.now().isoformat(), datetime.now().isoformat()])
            
            query = f"INSERT INTO recurring_meetings ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
            cursor.execute(query, values)
        
        conn.commit()
        conn.close()
    
    def get_recurring_meetings(self, limit: int = 50) -> List[Dict]:
        """Get all recurring meetings."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM recurring_meetings ORDER BY occurrence_count DESC LIMIT ?', (limit,))
        
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        conn.close()
        
        meetings = []
        for row in rows:
            meeting = dict(zip(columns, row))
            if meeting.get('attendees'):
                meeting['attendees'] = json.loads(meeting['attendees'])
            if meeting.get('accounts'):
                meeting['accounts'] = json.loads(meeting['accounts'])
            meetings.append(meeting)
        
        return meetings
    
    # =========================================================================
    # TASKS
    # =========================================================================
    
    def add_task(self, title: str, **kwargs):
        """Add a new task."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        fields = ['title'] + list(kwargs.keys()) + ['created_at', 'updated_at']
        placeholders = ['?'] * len(fields)
        
        values = [title]
        values.extend(kwargs.values())
        values.extend([datetime.now().isoformat(), datetime.now().isoformat()])
        
        query = f"INSERT INTO tasks ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
        cursor.execute(query, values)
        
        task_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        return task_id
    
    def get_pending_tasks(self, limit: int = 50) -> List[Dict]:
        """Get pending tasks ordered by priority and deadline."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM tasks 
            WHERE status IN ('pending', 'in_progress')
            ORDER BY priority ASC, deadline ASC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        conn.close()
        
        return [dict(zip(columns, row)) for row in rows]
    
    # =========================================================================
    # SYNC LOGGING
    # =========================================================================
    
    def log_sync(self, sync_type: str, account_email: str, items_processed: int, status: str = 'success'):
        """Log sync operation."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO sync_log (sync_type, account_email, items_processed, status, last_sync)
            VALUES (?, ?, ?, ?, ?)
        ''', (sync_type, account_email, items_processed, status, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_last_sync(self, sync_type: str, account_email: str) -> Optional[datetime]:
        """Get last sync time for account/type."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT last_sync FROM sync_log
            WHERE sync_type = ? AND account_email = ?
            ORDER BY last_sync DESC
            LIMIT 1
        ''', (sync_type, account_email))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return datetime.fromisoformat(row[0])
        return None


if __name__ == '__main__':
    print("\n" + "="*60)
    print("Context Database - Schema Test")
    print("="*60 + "\n")
    
    # Initialize
    db = ContextDatabase()
    print("✅ Database initialized\n")
    
    # Test: Add contact
    print("[1/4] Testing contact upsert...")
    db.upsert_contact(
        'sarah@example.com',
        name='Sarah Johnson',
        total_emails=42,
        avg_response_hours=4.2,
        importance_score=62.5,
        meeting_count=8,
        accounts=['personal@gmail.com', 'work@company.com']
    )
    print("✅ Contact added\n")
    
    # Test: Get contact
    contact = db.get_contact('sarah@example.com')
    print("Contact retrieved:")
    print(f"  Name: {contact['name']}")
    print(f"  Importance: {contact['importance_score']}")
    print(f"  Accounts: {contact['accounts']}")
    print()
    
    # Test: Add recurring meeting
    print("[2/4] Testing recurring meeting upsert...")
    db.upsert_recurring_meeting(
        'weekly-standup-123',
        summary='Weekly Team Standup',
        occurrence_count=12,
        organizer='manager@company.com',
        attendees=['team1@company.com', 'team2@company.com'],
        accounts=['work@company.com']
    )
    print("✅ Recurring meeting added\n")
    
    # Test: Add task
    print("[3/4] Testing task creation...")
    task_id = db.add_task(
        'Follow up with Sarah',
        description='Q2 budget review',
        deadline=(datetime.now()).isoformat(),
        priority=1,
        contact_email='sarah@example.com'
    )
    print(f"✅ Task created (ID: {task_id})\n")
    
    # Test: Get pending tasks
    tasks = db.get_pending_tasks()
    print(f"Pending tasks: {len(tasks)}")
    if tasks:
        print(f"  • {tasks[0]['title']}")
    print()
    
    # Test: Sync logging
    print("[4/4] Testing sync logging...")
    db.log_sync('email', 'personal@gmail.com', 200, 'success')
    last_sync = db.get_last_sync('email', 'personal@gmail.com')
    print(f"✅ Sync logged: {last_sync}\n")
    
    print("="*60)
    print("✅ All tests passed!")
    print("="*60 + "\n")
