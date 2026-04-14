#!/usr/bin/env python3
"""
Initialize V8 databases
"""

import sqlite3
from pathlib import Path

def init_databases():
    """Create V8 database tables"""
    v8_dir = Path.home() / '.openclaw' / 'v8'
    v8_dir.mkdir(parents=True, exist_ok=True)
    
    # Intelligence database
    intelligence_db = v8_dir / 'intelligence.db'
    conn = sqlite3.connect(intelligence_db)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT NOT NULL,
            pattern_data TEXT NOT NULL,
            frequency INTEGER DEFAULT 1,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS optimizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_id INTEGER,
            optimization_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            time_saved_ms INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pattern_id) REFERENCES patterns(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    
    # Approvals database
    approvals_db = v8_dir / 'approvals.db'
    conn = sqlite3.connect(approvals_db)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proposals (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            impact TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_at TIMESTAMP,
            rejected_at TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    
    print(f"✅ Databases initialized in {v8_dir}")

if __name__ == '__main__':
    init_databases()
