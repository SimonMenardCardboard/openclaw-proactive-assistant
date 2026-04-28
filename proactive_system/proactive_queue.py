#!/usr/bin/env python3
"""
Proactive Queue - Shared state for autonomous recommendations
All background systems (V6/V7/V8/heartbeats/calendar) write here.
COS Notifier reads and delivers via Telegram.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

DB_PATH = Path(__file__).parent / "proactive_queue.db"


class ProactiveQueue:
    """Shared queue for proactive recommendations across all systems."""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._ensure_schema()
    
    def _ensure_schema(self):
        """Ensure database schema exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS proactive_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    priority INTEGER DEFAULT 3,
                    message TEXT NOT NULL,
                    context JSON,
                    delivered BOOLEAN DEFAULT 0,
                    delivered_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_undelivered 
                ON proactive_queue(delivered, priority, created_at)
            """)
    
    def add(self, source: str, message: str, priority: int = 3, context: Optional[Dict] = None):
        """Add a recommendation to the queue."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO proactive_queue (source, message, priority, context)
                VALUES (?, ?, ?, ?)
            """, (source, message, priority, json.dumps(context) if context else None))
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    
    def get_pending(self, limit: int = 10) -> List[Dict]:
        """Get undelivered recommendations, highest priority first."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT id, source, priority, message, context, created_at
                FROM proactive_queue
                WHERE delivered = 0
                ORDER BY priority ASC, created_at ASC
                LIMIT ?
            """, (limit,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row['id'],
                    'source': row['source'],
                    'priority': row['priority'],
                    'message': row['message'],
                    'context': json.loads(row['context']) if row['context'] else {},
                    'created_at': row['created_at']
                })
            return results
    
    def mark_delivered(self, recommendation_id: int):
        """Mark a recommendation as delivered."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE proactive_queue
                SET delivered = 1, delivered_at = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), recommendation_id))
    
    def stats(self) -> Dict:
        """Get queue statistics."""
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN delivered = 0 THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN delivered = 1 THEN 1 ELSE 0 END) as delivered
                FROM proactive_queue
            """).fetchone()
            
            return {
                'total': result[0],
                'pending': result[1] or 0,
                'delivered': result[2] or 0
            }


if __name__ == '__main__':
    import sys
    
    queue = ProactiveQueue()
    
    # Check mode for heartbeats
    if '--check' in sys.argv:
        pending = queue.get_pending(limit=10)
        stats = queue.stats()
        
        print(f"📊 Stats: {stats['pending']} pending, {stats['delivered']} delivered")
        
        if pending:
            print("\n📬 Pending recommendations:")
            for rec in pending:
                priority_emoji = {1: '🚨', 2: '⚡', 3: '💡', 4: 'ℹ️', 5: '📝'}.get(rec['priority'], '💬')
                print(f"  {priority_emoji} [{rec['source']}] {rec['message'][:70]}...")
            
            # Return high-priority count for heartbeat decisions
            high_priority = sum(1 for r in pending if r['priority'] <= 2)
            if high_priority > 0:
                sys.exit(1)  # Signal to heartbeat that urgent items exist
        else:
            print("No pending recommendations")
        
        sys.exit(0)
    
    # Default: add test recommendation
    rec_id = queue.add(
        source='test',
        message='🎯 Proactive queue is now live! Background systems can now send autonomous recommendations.',
        priority=2,
        context={'test': True, 'timestamp': datetime.now().isoformat()}
    )
    
    print(f"✅ Added test recommendation (ID: {rec_id})")
    print(f"📊 Queue stats: {queue.stats()}")
    print(f"\n📬 Pending recommendations:")
    for rec in queue.get_pending():
        print(f"  [{rec['priority']}] {rec['source']}: {rec['message'][:60]}...")
