#!/usr/bin/env python3
"""
Context Database Migration

Adds new columns to support Memory Layer features:
- contacts: role, company, relationship
- tasks table (if not exists)
"""

import sqlite3
from pathlib import Path

def migrate():
    """Run database migrations."""
    db_path = Path.home() / ".openclaw/workspace/transmogrifier/openclaw-proactive-assistant/proactive_system/context.db"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Running context database migrations...")
    print("=" * 80)
    
    # 1. Add columns to contacts table (if not exist)
    try:
        cursor.execute("ALTER TABLE contacts ADD COLUMN role TEXT")
        print("✅ Added 'role' column to contacts")
    except sqlite3.OperationalError:
        print("⏭️  'role' column already exists")
    
    try:
        cursor.execute("ALTER TABLE contacts ADD COLUMN company TEXT")
        print("✅ Added 'company' column to contacts")
    except sqlite3.OperationalError:
        print("⏭️  'company' column already exists")
    
    try:
        cursor.execute("ALTER TABLE contacts ADD COLUMN relationship TEXT")
        print("✅ Added 'relationship' column to contacts")
    except sqlite3.OperationalError:
        print("⏭️  'relationship' column already exists")
    
    # 2. Create tasks table (if not exists)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            priority INTEGER DEFAULT 3,
            deadline TIMESTAMP,
            source TEXT,
            contact_email TEXT,
            completed BOOLEAN DEFAULT 0,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("✅ Tasks table ready")
    
    conn.commit()
    conn.close()
    
    print("\n✅ All migrations complete!")

if __name__ == '__main__':
    migrate()
