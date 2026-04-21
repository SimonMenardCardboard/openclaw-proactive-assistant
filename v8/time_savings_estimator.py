#!/usr/bin/env python3
"""
Time Savings Estimator

Calculates estimated and actual time savings for V8 optimizations.

Before deployment: Estimates based on pattern frequency and typical time costs
After deployment: Measures actual usage and calculates real time saved
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional


class TimeSavingsEstimator:
    """Estimate and measure time savings for optimizations"""
    
    def __init__(self, db_path: Path = None):
        if db_path is None:
            db_path = Path(__file__).parent / 'time_savings.db'
        
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize time savings tracking database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS time_savings (
                optimization_id TEXT PRIMARY KEY,
                pattern_type TEXT,
                estimated_per_use_seconds REAL,
                estimated_weekly_seconds REAL,
                actual_weekly_seconds REAL,
                usage_count INTEGER DEFAULT 0,
                deployed_at TIMESTAMP,
                last_measured_at TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                optimization_id TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                savings_seconds REAL,
                FOREIGN KEY (optimization_id) REFERENCES time_savings(optimization_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def estimate_savings(self, pattern: Dict) -> Dict:
        """
        Estimate time savings before deployment.
        
        Returns:
            {
                'per_use_seconds': float,
                'weekly_seconds': float,
                'weekly_minutes': float,
                'weekly_hours': float,
                'confidence': float
            }
        """
        pattern_type = pattern.get('type')
        occurrences = pattern.get('count', pattern.get('occurrences', 0))
        observation_weeks = pattern.get('observation_weeks', 1)
        
        # Calculate occurrences per week
        occurrences_per_week = occurrences / observation_weeks if observation_weeks > 0 else occurrences
        
        # Estimate time saved per use based on pattern type
        per_use_seconds = self._estimate_per_use_savings(pattern_type, pattern)
        
        # Calculate weekly savings
        weekly_seconds = per_use_seconds * occurrences_per_week
        
        return {
            'per_use_seconds': per_use_seconds,
            'weekly_seconds': weekly_seconds,
            'weekly_minutes': weekly_seconds / 60,
            'weekly_hours': weekly_seconds / 3600,
            'confidence': pattern.get('confidence', 0.0)
        }
    
    def _estimate_per_use_savings(self, pattern_type: str, pattern: Dict) -> float:
        """Estimate time saved per use of optimization (in seconds)"""
        
        if pattern_type == 'command_retry':
            # Retry: saves time on manual retry attempts
            # Typical: 10-30 seconds to notice failure + retype command
            avg_retry_time = 20
            avg_retries = pattern.get('parameters', {}).get('max_retries', 3) / 2  # Average retries needed
            return avg_retry_time * avg_retries  # ~40 seconds
        
        elif pattern_type == 'dir_navigation':
            # Directory navigation: saves typing long paths
            # Typical: 5-15 seconds to type path or navigate
            avg_navigation_time = 10
            return avg_navigation_time
        
        elif pattern_type == 'multi_command':
            # Multi-command workflow: saves typing + context switching
            command_count = len(pattern.get('commands', []))
            typing_time_per_command = 5  # seconds
            context_switch_cost = 10  # mental overhead between steps
            return (typing_time_per_command * command_count) + context_switch_cost
        
        elif pattern_type == 'cache_operation':
            # Cache: saves redundant computation/fetching
            # Typical: 5-60 seconds depending on what's cached
            avg_cache_hit_time = 30
            return avg_cache_hit_time
        
        elif pattern_type == 'deduplication':
            # Deduplication: prevents redundant notifications/actions
            # Typical: 5-10 seconds to read/dismiss duplicate
            avg_duplicate_handling_time = 7
            return avg_duplicate_handling_time
        
        elif pattern_type == 'email_template':
            # Email template: saves drafting common emails
            # Typical: 2-5 minutes to compose from scratch
            avg_draft_time = 180  # 3 minutes
            return avg_draft_time
        
        elif pattern_type == 'email_shortcut':
            # Email shortcut: saves looking up recipient address
            # Typical: 10-30 seconds to find/autocomplete address
            avg_lookup_time = 15
            return avg_lookup_time
        
        elif pattern_type == 'email_schedule':
            # Email batching: saves context switch cost
            # Typical: 5 minutes per email interruption avoided
            avg_interruption_cost = 300  # 5 minutes
            return avg_interruption_cost
        
        elif pattern_type == 'meeting_automation':
            # Meeting automation: saves prep/follow-up tasks
            # Typical: 5-15 minutes per meeting
            avg_meeting_overhead = 600  # 10 minutes
            return avg_meeting_overhead
        
        elif pattern_type == 'focus_block':
            # Focus block: protects deep work time
            # Typical: reclaims 1-2 hours per block
            duration_hours = pattern.get('duration', 60) / 60  # Convert minutes to hours
            return duration_hours * 3600  # hours to seconds
        
        elif pattern_type == 'meeting_workflow':
            # Meeting workflow optimization: reduces meeting time
            # Typical: 10-30 minutes per meeting
            avg_meeting_reduction = 900  # 15 minutes
            return avg_meeting_reduction
        
        elif pattern_type == 'workflow_sequence':
            # Workflow sequence: automates multi-step process
            # Typical: 1-5 minutes depending on complexity
            step_count = len(pattern.get('steps', pattern.get('commands', [])))
            avg_time_per_step = 20  # seconds
            return step_count * avg_time_per_step
        
        else:
            # Default: conservative estimate
            return 30  # 30 seconds
    
    def record_deployment(self, optimization_id: str, pattern: Dict, estimated_savings: Dict):
        """Record estimated savings when optimization is deployed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO time_savings
            (optimization_id, pattern_type, estimated_per_use_seconds, 
             estimated_weekly_seconds, deployed_at, last_measured_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            optimization_id,
            pattern.get('type'),
            estimated_savings['per_use_seconds'],
            estimated_savings['weekly_seconds'],
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def record_usage(self, optimization_id: str):
        """Record each time an optimization is used"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get per-use savings estimate
        cursor.execute("""
            SELECT estimated_per_use_seconds 
            FROM time_savings 
            WHERE optimization_id = ?
        """, (optimization_id,))
        
        row = cursor.fetchone()
        if row:
            per_use_seconds = row[0]
            
            # Record usage event
            cursor.execute("""
                INSERT INTO usage_events (optimization_id, savings_seconds)
                VALUES (?, ?)
            """, (optimization_id, per_use_seconds))
            
            # Update usage count
            cursor.execute("""
                UPDATE time_savings
                SET usage_count = usage_count + 1,
                    last_measured_at = ?
                WHERE optimization_id = ?
            """, (datetime.now().isoformat(), optimization_id))
            
            conn.commit()
        
        conn.close()
    
    def measure_actual_savings(self, optimization_id: str) -> Optional[Dict]:
        """
        Measure actual time saved since deployment.
        
        Returns:
            {
                'estimated_weekly': float,
                'actual_weekly': float,
                'accuracy': float,  # actual / estimated
                'usage_count': int,
                'weeks_deployed': float
            }
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get deployment info
        cursor.execute("""
            SELECT estimated_weekly_seconds, deployed_at, usage_count, estimated_per_use_seconds
            FROM time_savings
            WHERE optimization_id = ?
        """, (optimization_id,))
        
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        
        estimated_weekly, deployed_at, usage_count, per_use_seconds = row
        
        # Calculate weeks since deployment
        deployed_time = datetime.fromisoformat(deployed_at)
        weeks_deployed = (datetime.now() - deployed_time).total_seconds() / (7 * 24 * 3600)
        
        if weeks_deployed == 0:
            weeks_deployed = 0.01  # Avoid division by zero
        
        # Calculate actual weekly savings
        total_actual_seconds = usage_count * per_use_seconds
        actual_weekly = total_actual_seconds / weeks_deployed
        
        # Update database
        cursor.execute("""
            UPDATE time_savings
            SET actual_weekly_seconds = ?,
                last_measured_at = ?
            WHERE optimization_id = ?
        """, (actual_weekly, datetime.now().isoformat(), optimization_id))
        
        conn.commit()
        conn.close()
        
        # Calculate accuracy
        accuracy = (actual_weekly / estimated_weekly) if estimated_weekly > 0 else 0.0
        
        return {
            'estimated_weekly_seconds': estimated_weekly,
            'estimated_weekly_minutes': estimated_weekly / 60,
            'actual_weekly_seconds': actual_weekly,
            'actual_weekly_minutes': actual_weekly / 60,
            'accuracy': accuracy,
            'usage_count': usage_count,
            'weeks_deployed': weeks_deployed
        }
    
    def get_total_savings(self, weeks: int = 1) -> Dict:
        """Get total time saved across all optimizations"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all optimizations deployed within the time window
        cutoff_date = (datetime.now() - timedelta(weeks=weeks)).isoformat()
        
        cursor.execute("""
            SELECT optimization_id, estimated_weekly_seconds, actual_weekly_seconds
            FROM time_savings
            WHERE deployed_at >= ?
        """, (cutoff_date,))
        
        rows = cursor.fetchall()
        conn.close()
        
        total_estimated = sum(row[1] for row in rows if row[1])
        total_actual = sum(row[2] for row in rows if row[2])
        
        return {
            'total_optimizations': len(rows),
            'total_estimated_seconds': total_estimated,
            'total_estimated_hours': total_estimated / 3600,
            'total_actual_seconds': total_actual,
            'total_actual_hours': total_actual / 3600,
            'weeks': weeks
        }
    
    def get_leaderboard(self, limit: int = 10) -> list:
        """Get top optimizations by actual time saved"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT optimization_id, pattern_type, actual_weekly_seconds, usage_count
            FROM time_savings
            WHERE actual_weekly_seconds IS NOT NULL
            ORDER BY actual_weekly_seconds DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        leaderboard = []
        for row in rows:
            leaderboard.append({
                'optimization_id': row[0],
                'pattern_type': row[1],
                'actual_weekly_seconds': row[2],
                'actual_weekly_minutes': row[2] / 60,
                'usage_count': row[3]
            })
        
        return leaderboard


# CLI interface for testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Time Savings Estimator")
    parser.add_argument("action", choices=["estimate", "measure", "total", "leaderboard"])
    parser.add_argument("--optimization-id", help="Optimization ID")
    parser.add_argument("--pattern-type", help="Pattern type")
    parser.add_argument("--occurrences", type=int, default=10, help="Number of occurrences")
    parser.add_argument("--weeks", type=int, default=1, help="Observation weeks")
    
    args = parser.parse_args()
    
    estimator = TimeSavingsEstimator()
    
    if args.action == "estimate":
        pattern = {
            'type': args.pattern_type,
            'count': args.occurrences,
            'observation_weeks': args.weeks
        }
        result = estimator.estimate_savings(pattern)
        print(f"Estimated savings for {args.pattern_type}:")
        print(f"  Per use: {result['per_use_seconds']:.0f} seconds")
        print(f"  Weekly: {result['weekly_minutes']:.1f} minutes ({result['weekly_hours']:.2f} hours)")
    
    elif args.action == "measure":
        if not args.optimization_id:
            print("Error: --optimization-id required")
        else:
            result = estimator.measure_actual_savings(args.optimization_id)
            if result:
                print(f"Actual savings for {args.optimization_id}:")
                print(f"  Estimated: {result['estimated_weekly_minutes']:.1f} min/week")
                print(f"  Actual: {result['actual_weekly_minutes']:.1f} min/week")
                print(f"  Accuracy: {result['accuracy']:.0%}")
                print(f"  Usage: {result['usage_count']} times in {result['weeks_deployed']:.1f} weeks")
            else:
                print(f"No data for {args.optimization_id}")
    
    elif args.action == "total":
        result = estimator.get_total_savings(weeks=args.weeks)
        print(f"Total savings (last {args.weeks} week(s)):")
        print(f"  Optimizations: {result['total_optimizations']}")
        print(f"  Estimated: {result['total_estimated_hours']:.2f} hours/week")
        print(f"  Actual: {result['total_actual_hours']:.2f} hours/week")
    
    elif args.action == "leaderboard":
        results = estimator.get_leaderboard(limit=10)
        print("Top optimizations by time saved:")
        for i, item in enumerate(results, 1):
            print(f"  {i}. {item['optimization_id']}: {item['actual_weekly_minutes']:.1f} min/week ({item['usage_count']} uses)")
