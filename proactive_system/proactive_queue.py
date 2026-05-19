#!/usr/bin/env python3
"""
Proactive Queue - Shared state for autonomous recommendations
All background systems (V6/V7/V8/heartbeats/calendar) write here.
Transmogrifier Notifier reads and delivers via Telegram.
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
        """Add a recommendation to the queue with automatic classification."""
        # Classify message type
        message_type = self._classify_message(source)
        user_facing = self._is_user_facing(source, priority)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO proactive_queue (source, message, priority, context, message_type, user_facing)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (source, message, priority, json.dumps(context) if context else None, message_type, user_facing))
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    
    def _classify_message(self, source: str) -> str:
        """Classify message as intelligence or system."""
        intelligence_sources = [
            'v6-executor', 'v7-self-healing', 'v8-pattern',
            'bootstrap', 'email', 'calendar', 'training',
            'recovery', 'nutrition', 'onboarding'
        ]
        
        return 'intelligence' if source in intelligence_sources else 'system'
    
    def _is_user_facing(self, source: str, priority: int) -> bool:
        """Determine if message should go to user channel."""
        # Priority 1 always goes to user
        if priority == 1:
            return True
        
        # System messages go to log only (unless P1)
        system_sources = ['system', 'build', 'github', 'test', 'audit', 'planning']
        if source in system_sources:
            return False
        
        # Intelligence messages go to user
        return True
    
    def get_pending(self, limit: int = 10) -> List[Dict]:
        """Get undelivered recommendations, highest priority first."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT id, source, priority, message, context, created_at, message_type, user_facing
                FROM proactive_queue
                WHERE delivered = 0
                ORDER BY priority ASC, created_at ASC
                LIMIT ?
            """, (limit,))
            
            # Fetch all rows immediately and close cursor
            rows = cursor.fetchall()
            cursor.close()
            
            results = []
            for row in rows:
                results.append({
                    'id': row['id'],
                    'source': row['source'],
                    'priority': row['priority'],
                    'message': row['message'],
                    'context': json.loads(row['context']) if row['context'] else {},
                    'created_at': row['created_at'],
                    'message_type': row['message_type'],
                    'user_facing': row['user_facing']
                })
            return results
    
    def get_user_facing_pending(self, limit: int = 10) -> List[Dict]:
        """Get only user-facing undelivered recommendations."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT id, source, priority, message, context, created_at
                FROM proactive_queue
                WHERE delivered = 0 
                  AND user_facing = 1
                ORDER BY priority ASC, created_at ASC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            cursor.close()
            
            results = []
            for row in rows:
                results.append({
                    'id': row['id'],
                    'source': row['source'],
                    'priority': row['priority'],
                    'message': row['message'],
                    'context': json.loads(row['context']) if row['context'] else {},
                    'created_at': row['created_at']
                })
            return results
    
    def get_system_pending(self, limit: int = 100) -> List[Dict]:
        """Get only system messages (not user-facing)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT id, source, priority, message, created_at
                FROM proactive_queue
                WHERE delivered = 0 
                  AND user_facing = 0
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            cursor.close()
            
            return [dict(row) for row in rows]
    
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
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN delivered = 0 THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN delivered = 1 THEN 1 ELSE 0 END) as delivered
                FROM proactive_queue
            """)
            result = cursor.fetchone()
            cursor.close()
            
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
