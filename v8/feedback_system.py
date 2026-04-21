#!/usr/bin/env python3
"""
V8 Feedback System - Phase 4

Track user feedback on deployed optimizations.
Auto-rollback patterns with high failure rates.
Update quality scores based on actual usage.

Flow:
1. Optimization runs (via wrapper script)
2. Prompt user for feedback (👍/👎)
3. Store feedback in database
4. Check rollback threshold (>30% negative)
5. Update quality score
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, List


class FeedbackSystem:
    """Track and analyze user feedback on optimizations"""
    
    def __init__(self, db_path: Path = None):
        if db_path is None:
            db_path = Path(__file__).parent / 'feedback.db'
        
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize feedback database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                optimization_id TEXT NOT NULL,
                feedback_type TEXT NOT NULL,  -- 'positive', 'negative', 'neutral'
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (optimization_id) REFERENCES optimizations(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quality_scores (
                optimization_id TEXT PRIMARY KEY,
                positive_count INTEGER DEFAULT 0,
                negative_count INTEGER DEFAULT 0,
                neutral_count INTEGER DEFAULT 0,
                total_feedback INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0.0,
                quality_score REAL DEFAULT 0.0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                rollback_flagged BOOLEAN DEFAULT FALSE,
                rollback_reason TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rollback_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                optimization_id TEXT NOT NULL,
                reason TEXT,
                negative_rate REAL,
                total_feedback INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def record_feedback(self, optimization_id: str, feedback_type: str, details: str = None) -> bool:
        """
        Record user feedback for an optimization.
        
        Args:
            optimization_id: ID of the optimization
            feedback_type: 'positive', 'negative', or 'neutral'
            details: Optional details about the feedback
        
        Returns:
            True if recorded successfully
        """
        if feedback_type not in ['positive', 'negative', 'neutral']:
            print(f"❌ Invalid feedback type: {feedback_type}")
            return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Record feedback
        cursor.execute("""
            INSERT INTO feedback (optimization_id, feedback_type, details)
            VALUES (?, ?, ?)
        """, (optimization_id, feedback_type, details))
        
        conn.commit()
        conn.close()
        
        # Update quality scores
        self._update_quality_score(optimization_id)
        
        # Check if rollback needed
        self._check_rollback_threshold(optimization_id)
        
        return True
    
    def _update_quality_score(self, optimization_id: str):
        """Recalculate quality score based on all feedback"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Count feedback by type
        cursor.execute("""
            SELECT feedback_type, COUNT(*) 
            FROM feedback 
            WHERE optimization_id = ?
            GROUP BY feedback_type
        """, (optimization_id,))
        
        feedback_counts = dict(cursor.fetchall())
        
        positive = feedback_counts.get('positive', 0)
        negative = feedback_counts.get('negative', 0)
        neutral = feedback_counts.get('neutral', 0)
        total = positive + negative + neutral
        
        if total == 0:
            success_rate = 0.0
            quality_score = 0.0
        else:
            # Success rate: positive / (positive + negative)
            # Ignore neutral for success calculation
            if positive + negative > 0:
                success_rate = positive / (positive + negative)
            else:
                success_rate = 0.5  # No strong feedback yet
            
            # Quality score: weighted by total feedback
            # More feedback = more confidence
            confidence_weight = min(total / 10, 1.0)  # Max confidence at 10+ feedback
            quality_score = success_rate * confidence_weight
        
        # Update or insert quality score
        cursor.execute("""
            INSERT INTO quality_scores 
            (optimization_id, positive_count, negative_count, neutral_count, 
             total_feedback, success_rate, quality_score, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(optimization_id) DO UPDATE SET
                positive_count = ?,
                negative_count = ?,
                neutral_count = ?,
                total_feedback = ?,
                success_rate = ?,
                quality_score = ?,
                last_updated = ?
        """, (
            optimization_id, positive, negative, neutral, total,
            success_rate, quality_score, datetime.now().isoformat(),
            positive, negative, neutral, total,
            success_rate, quality_score, datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def _check_rollback_threshold(self, optimization_id: str):
        """Check if optimization should be rolled back due to poor feedback"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get quality score
        cursor.execute("""
            SELECT positive_count, negative_count, total_feedback, success_rate, rollback_flagged
            FROM quality_scores
            WHERE optimization_id = ?
        """, (optimization_id,))
        
        row = cursor.fetchone()
        if not row:
            conn.close()
            return
        
        positive, negative, total, success_rate, already_flagged = row
        
        # Rollback criteria:
        # 1. At least 10 feedback entries (enough data)
        # 2. Negative rate > 30%
        # 3. Not already flagged
        
        if total >= 10 and success_rate < 0.70 and not already_flagged:
            negative_rate = negative / total if total > 0 else 0
            
            # Flag for rollback
            cursor.execute("""
                UPDATE quality_scores
                SET rollback_flagged = TRUE,
                    rollback_reason = ?
                WHERE optimization_id = ?
            """, (
                f"High failure rate: {negative_rate:.0%} negative feedback ({negative}/{total})",
                optimization_id
            ))
            
            # Record rollback event
            cursor.execute("""
                INSERT INTO rollback_history 
                (optimization_id, reason, negative_rate, total_feedback)
                VALUES (?, ?, ?, ?)
            """, (
                optimization_id,
                f"High failure rate: {negative_rate:.0%}",
                negative_rate,
                total
            ))
            
            conn.commit()
            
            print(f"\n⚠️  ROLLBACK FLAGGED: {optimization_id}")
            print(f"Reason: {negative_rate:.0%} negative feedback ({negative}/{total})")
            print(f"Recommendation: Review and disable this optimization")
        
        conn.close()
    
    def get_quality_score(self, optimization_id: str) -> Optional[Dict]:
        """Get current quality score for an optimization"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT positive_count, negative_count, neutral_count, total_feedback,
                   success_rate, quality_score, rollback_flagged, rollback_reason,
                   last_updated
            FROM quality_scores
            WHERE optimization_id = ?
        """, (optimization_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            'positive': row[0],
            'negative': row[1],
            'neutral': row[2],
            'total': row[3],
            'success_rate': row[4],
            'quality_score': row[5],
            'rollback_flagged': bool(row[6]),
            'rollback_reason': row[7],
            'last_updated': row[8]
        }
    
    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Get top optimizations by quality score"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT optimization_id, quality_score, success_rate, total_feedback,
                   positive_count, negative_count
            FROM quality_scores
            WHERE total_feedback >= 5
            ORDER BY quality_score DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        leaderboard = []
        for row in rows:
            leaderboard.append({
                'optimization_id': row[0],
                'quality_score': row[1],
                'success_rate': row[2],
                'total_feedback': row[3],
                'positive': row[4],
                'negative': row[5]
            })
        
        return leaderboard
    
    def get_rollback_candidates(self) -> List[Dict]:
        """Get optimizations flagged for rollback"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT optimization_id, rollback_reason, success_rate, 
                   total_feedback, negative_count, last_updated
            FROM quality_scores
            WHERE rollback_flagged = TRUE
            ORDER BY last_updated DESC
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        candidates = []
        for row in rows:
            candidates.append({
                'optimization_id': row[0],
                'reason': row[1],
                'success_rate': row[2],
                'total_feedback': row[3],
                'negative_count': row[4],
                'flagged_at': row[5]
            })
        
        return candidates
    
    def prompt_feedback(self, optimization_id: str, context: str = None) -> bool:
        """
        Interactive prompt for user feedback.
        
        Args:
            optimization_id: ID of optimization that just ran
            context: Optional context about what happened
        
        Returns:
            True if feedback was recorded
        """
        print(f"\n{'='*60}")
        print(f"💡 Optimization: {optimization_id}")
        if context:
            print(f"Context: {context}")
        print(f"{'='*60}")
        print("\nDid this optimization work as expected?")
        print("  [y] Yes, worked great! 👍")
        print("  [n] No, had issues 👎")
        print("  [s] Skip / Not sure 🤷")
        print("  [q] Quit")
        
        choice = input("\nYour feedback: ").strip().lower()
        
        if choice == 'q':
            return False
        
        if choice == 'y':
            self.record_feedback(optimization_id, 'positive')
            print("✅ Thanks! Marked as working.")
            return True
        
        elif choice == 'n':
            print("\nWhat went wrong?")
            print("  [1] Still failed after retries")
            print("  [2] Took too long")
            print("  [3] Interfered with other commands")
            print("  [4] Other")
            
            issue = input("Issue (1-4): ").strip()
            
            issue_map = {
                '1': 'Still failed after retries',
                '2': 'Took too long',
                '3': 'Interfered with other commands',
                '4': 'Other issue'
            }
            
            details = issue_map.get(issue, 'Unspecified issue')
            
            self.record_feedback(optimization_id, 'negative', details)
            print("✅ Thanks for the feedback. We'll look into this.")
            return True
        
        elif choice == 's':
            self.record_feedback(optimization_id, 'neutral')
            print("✅ Skipped.")
            return True
        
        else:
            print("❌ Invalid choice. Skipping feedback.")
            return False


# CLI interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="V8 Feedback System")
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Record feedback
    record_parser = subparsers.add_parser('record', help='Record feedback')
    record_parser.add_argument('optimization_id', help='Optimization ID')
    record_parser.add_argument('feedback_type', choices=['positive', 'negative', 'neutral'])
    record_parser.add_argument('--details', help='Optional details')
    
    # Get quality score
    score_parser = subparsers.add_parser('score', help='Get quality score')
    score_parser.add_argument('optimization_id', help='Optimization ID')
    
    # Leaderboard
    subparsers.add_parser('leaderboard', help='Show top optimizations')
    
    # Rollback candidates
    subparsers.add_parser('rollback-check', help='Show optimizations flagged for rollback')
    
    # Interactive feedback
    prompt_parser = subparsers.add_parser('prompt', help='Interactive feedback prompt')
    prompt_parser.add_argument('optimization_id', help='Optimization ID')
    prompt_parser.add_argument('--context', help='Context about what happened')
    
    args = parser.parse_args()
    
    feedback = FeedbackSystem()
    
    if args.command == 'record':
        feedback.record_feedback(args.optimization_id, args.feedback_type, args.details)
        print(f"✅ Feedback recorded for {args.optimization_id}")
    
    elif args.command == 'score':
        score = feedback.get_quality_score(args.optimization_id)
        if score:
            print(f"\n📊 Quality Score: {args.optimization_id}")
            print(f"  Success rate: {score['success_rate']:.0%}")
            print(f"  Quality score: {score['quality_score']:.2f}")
            print(f"  Feedback: 👍{score['positive']} 👎{score['negative']} 🤷{score['neutral']}")
            if score['rollback_flagged']:
                print(f"  ⚠️  Flagged for rollback: {score['rollback_reason']}")
        else:
            print(f"❌ No feedback data for {args.optimization_id}")
    
    elif args.command == 'leaderboard':
        leaders = feedback.get_leaderboard(10)
        print("\n🏆 Top Optimizations by Quality Score")
        print("="*60)
        for i, item in enumerate(leaders, 1):
            print(f"{i}. {item['optimization_id']}")
            print(f"   Quality: {item['quality_score']:.2f} | Success: {item['success_rate']:.0%}")
            print(f"   Feedback: 👍{item['positive']} 👎{item['negative']} ({item['total_feedback']} total)")
    
    elif args.command == 'rollback-check':
        candidates = feedback.get_rollback_candidates()
        if candidates:
            print("\n⚠️  Optimizations Flagged for Rollback")
            print("="*60)
            for item in candidates:
                print(f"• {item['optimization_id']}")
                print(f"  Reason: {item['reason']}")
                print(f"  Success rate: {item['success_rate']:.0%}")
                print(f"  Flagged: {item['flagged_at']}")
                print()
        else:
            print("✅ No optimizations flagged for rollback")
    
    elif args.command == 'prompt':
        feedback.prompt_feedback(args.optimization_id, args.context)
    
    else:
        parser.print_help()
