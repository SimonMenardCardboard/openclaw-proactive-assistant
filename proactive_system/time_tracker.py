#!/usr/bin/env python3
"""
Time Tracker - Measure Time Saved by Automation

Tracks time saved by autonomous actions:
- V6 autonomous executions
- V7 self-healing repairs
- Pattern-based automations

Calculates ROI for user's subscription.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Time estimates for common actions (in seconds)
ACTION_TIME_SAVINGS = {
    # V6 autonomous actions
    'refresh_auth_token': 45,  # Manual OAuth refresh takes ~45s
    'restart_tunnel': 30,  # Manual restart takes ~30s
    'restart_launchagent': 25,  # Manual service restart ~25s
    'send_form_reminder': 60,  # Manual reminder compose ~60s
    'send_training_rec': 90,  # Manual workout recommendation ~90s
    
    # V7 self-healing
    'repair_database': 300,  # Manual DB fix ~5 minutes
    'restart_service': 45,  # Service troubleshooting ~45s
    'cleanup_disk': 180,  # Manual cleanup ~3 minutes
    'fix_permissions': 120,  # Permission fixes ~2 minutes
    
    # Email/Calendar intelligence
    'auto_email_response': 120,  # Drafting reply ~2 minutes
    'meeting_prep': 300,  # Meeting prep ~5 minutes
    'contact_followup': 90,  # Follow-up reminder ~90s
    'task_extraction': 30,  # Manual task entry ~30s
    
    # Default
    'default': 60,  # 1 minute for unknown actions
}


class TimeTracker:
    """Track time saved by automation."""
    
    def __init__(self, context_db_path: Optional[Path] = None):
        """
        Initialize time tracker.
        
        Args:
            context_db_path: Path to context database
        """
        if context_db_path is None:
            context_db_path = Path(__file__).parent / "context.db"
        
        self.db_path = Path(context_db_path)
        self._init_database()
    
    def _init_database(self):
        """Create time savings table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS time_savings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                action_type TEXT NOT NULL,
                action_name TEXT NOT NULL,
                time_saved_seconds INTEGER NOT NULL,
                source TEXT NOT NULL,  -- v6, v7, v8, manual
                metadata TEXT,  -- JSON for additional context
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_time_savings_timestamp 
            ON time_savings(timestamp)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_time_savings_source 
            ON time_savings(source)
        ''')
        
        conn.commit()
        conn.close()
    
    def log_time_saved(self, action_name: str, source: str = 'v6', 
                       time_saved_seconds: Optional[int] = None,
                       action_type: Optional[str] = None,
                       metadata: Optional[str] = None) -> int:
        """
        Log time saved by an automated action.
        
        Args:
            action_name: Name of the action (e.g., 'refresh_auth_token')
            source: Source of automation (v6, v7, v8, manual)
            time_saved_seconds: Time saved in seconds (auto-detected if None)
            action_type: Type of action (automation, healing, intelligence)
            metadata: Additional context as JSON string
            
        Returns:
            Record ID
        """
        # Auto-detect time saved if not provided
        if time_saved_seconds is None:
            time_saved_seconds = ACTION_TIME_SAVINGS.get(
                action_name, 
                ACTION_TIME_SAVINGS['default']
            )
        
        # Auto-detect action type if not provided
        if action_type is None:
            if source == 'v6':
                action_type = 'automation'
            elif source == 'v7':
                action_type = 'healing'
            elif source == 'v8':
                action_type = 'intelligence'
            else:
                action_type = 'other'
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO time_savings 
            (timestamp, action_type, action_name, time_saved_seconds, source, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (datetime.now(), action_type, action_name, time_saved_seconds, source, metadata))
        
        record_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        logger.info(f"Logged time saved: {action_name} ({time_saved_seconds}s from {source})")
        
        return record_id
    
    def get_time_saved_summary(self, days_back: int = 7) -> Dict:
        """
        Get summary of time saved.
        
        Args:
            days_back: Number of days to look back
            
        Returns:
            Summary dict with total, by source, by type
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = datetime.now() - timedelta(days=days_back)
        
        # Total time saved
        cursor.execute('''
            SELECT SUM(time_saved_seconds)
            FROM time_savings
            WHERE timestamp >= ?
        ''', (cutoff,))
        
        total_seconds = cursor.fetchone()[0] or 0
        
        # By source
        cursor.execute('''
            SELECT source, SUM(time_saved_seconds), COUNT(*)
            FROM time_savings
            WHERE timestamp >= ?
            GROUP BY source
        ''', (cutoff,))
        
        by_source = {}
        for row in cursor.fetchall():
            by_source[row[0]] = {
                'seconds': row[1],
                'count': row[2],
                'hours': round(row[1] / 3600, 1)
            }
        
        # By type
        cursor.execute('''
            SELECT action_type, SUM(time_saved_seconds), COUNT(*)
            FROM time_savings
            WHERE timestamp >= ?
            GROUP BY action_type
        ''', (cutoff,))
        
        by_type = {}
        for row in cursor.fetchall():
            by_type[row[0]] = {
                'seconds': row[1],
                'count': row[2],
                'hours': round(row[1] / 3600, 1)
            }
        
        # Top actions
        cursor.execute('''
            SELECT action_name, SUM(time_saved_seconds), COUNT(*)
            FROM time_savings
            WHERE timestamp >= ?
            GROUP BY action_name
            ORDER BY SUM(time_saved_seconds) DESC
            LIMIT 5
        ''', (cutoff,))
        
        top_actions = []
        for row in cursor.fetchall():
            top_actions.append({
                'action': row[0],
                'seconds': row[1],
                'count': row[2],
                'hours': round(row[1] / 3600, 1)
            })
        
        conn.close()
        
        return {
            'period_days': days_back,
            'total_seconds': total_seconds,
            'total_hours': round(total_seconds / 3600, 1),
            'total_minutes': round(total_seconds / 60, 1),
            'by_source': by_source,
            'by_type': by_type,
            'top_actions': top_actions
        }
    
    def get_weekly_trend(self, weeks: int = 4) -> List[Dict]:
        """
        Get weekly time savings trend.
        
        Args:
            weeks: Number of weeks to analyze
            
        Returns:
            List of weekly summaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        weekly_data = []
        
        for week in range(weeks):
            week_start = datetime.now() - timedelta(weeks=week+1)
            week_end = datetime.now() - timedelta(weeks=week)
            
            cursor.execute('''
                SELECT SUM(time_saved_seconds), COUNT(*)
                FROM time_savings
                WHERE timestamp >= ? AND timestamp < ?
            ''', (week_start, week_end))
            
            row = cursor.fetchone()
            total_seconds = row[0] or 0
            count = row[1] or 0
            
            weekly_data.append({
                'week': f"Week {weeks - week}",
                'start_date': week_start.strftime('%Y-%m-%d'),
                'end_date': week_end.strftime('%Y-%m-%d'),
                'total_seconds': total_seconds,
                'total_hours': round(total_seconds / 3600, 1),
                'action_count': count
            })
        
        conn.close()
        
        # Reverse so most recent is last
        return list(reversed(weekly_data))
    
    def calculate_roi(self, subscription_cost: float = 75.0, 
                     hourly_value: float = 50.0,
                     days_back: int = 30) -> Dict:
        """
        Calculate ROI for subscription.
        
        Args:
            subscription_cost: Monthly subscription cost ($)
            hourly_value: User's hourly value ($)
            days_back: Period to analyze
            
        Returns:
            ROI metrics
        """
        summary = self.get_time_saved_summary(days_back)
        
        hours_saved = summary['total_hours']
        value_saved = hours_saved * hourly_value
        
        # Annualize if needed
        if days_back < 30:
            multiplier = 30 / days_back
            monthly_hours = hours_saved * multiplier
            monthly_value = value_saved * multiplier
        else:
            monthly_hours = hours_saved
            monthly_value = value_saved
        
        roi_ratio = monthly_value / subscription_cost if subscription_cost > 0 else 0
        roi_percentage = (roi_ratio - 1) * 100
        
        return {
            'period_days': days_back,
            'hours_saved': hours_saved,
            'monthly_hours_saved': round(monthly_hours, 1),
            'subscription_cost': subscription_cost,
            'hourly_value': hourly_value,
            'value_saved': round(value_saved, 2),
            'monthly_value_saved': round(monthly_value, 2),
            'roi_ratio': round(roi_ratio, 1),
            'roi_percentage': round(roi_percentage, 0),
            'cost_per_hour_saved': round(subscription_cost / monthly_hours, 2) if monthly_hours > 0 else 0,
            'break_even': subscription_cost / hourly_value if hourly_value > 0 else 0
        }
    
    def backfill_from_v6_logs(self, days_back: int = 30) -> int:
        """
        Backfill time savings from V6 execution logs.
        
        Args:
            days_back: How many days to backfill
            
        Returns:
            Number of records created
        """
        # Try to find V6 execution log
        workspace = Path.home() / ".openclaw/workspace"
        v6_db = workspace / "integrations/intelligence/autonomous_executor/execution_log.db"
        
        if not v6_db.exists():
            logger.warning(f"V6 execution log not found: {v6_db}")
            return 0
        
        conn = sqlite3.connect(v6_db)
        cursor = conn.cursor()
        
        cutoff = datetime.now() - timedelta(days=days_back)
        
        # Get successful executions
        cursor.execute('''
            SELECT timestamp, action_name
            FROM executions
            WHERE status = 'success' AND timestamp >= ?
        ''', (cutoff,))
        
        executions = cursor.fetchall()
        conn.close()
        
        # Log each execution
        count = 0
        for timestamp, action_name in executions:
            self.log_time_saved(
                action_name=action_name,
                source='v6',
                action_type='automation'
            )
            count += 1
        
        logger.info(f"Backfilled {count} time savings records from V6 logs")
        
        return count


if __name__ == "__main__":
    # Demo usage
    tracker = TimeTracker()
    
    print("\n" + "="*70)
    print("TIME TRACKER - Demo")
    print("="*70 + "\n")
    
    # Backfill from V6 logs
    print("Backfilling from V6 logs...")
    backfilled = tracker.backfill_from_v6_logs(days_back=30)
    print(f"✅ Backfilled {backfilled} records\n")
    
    # Get weekly summary
    print("📊 Last 7 Days Summary:")
    summary = tracker.get_time_saved_summary(days_back=7)
    print(f"  Total time saved: {summary['total_hours']} hours ({summary['total_minutes']} minutes)")
    print(f"\n  By source:")
    for source, data in summary['by_source'].items():
        print(f"    {source}: {data['hours']} hours ({data['count']} actions)")
    
    if summary['top_actions']:
        print(f"\n  Top actions:")
        for action in summary['top_actions']:
            print(f"    {action['action']}: {action['hours']} hours ({action['count']}×)")
    
    # Calculate ROI
    print("\n💰 ROI Analysis (30 days):")
    roi = tracker.calculate_roi(subscription_cost=75.0, hourly_value=50.0, days_back=30)
    print(f"  Subscription: ${roi['subscription_cost']}/month")
    print(f"  Hours saved: {roi['monthly_hours_saved']} hours/month")
    print(f"  Value saved: ${roi['monthly_value_saved']}")
    print(f"  ROI: {roi['roi_ratio']}× ({roi['roi_percentage']}%)")
    print(f"  Cost per hour saved: ${roi['cost_per_hour_saved']}")
    print(f"  Break-even: {roi['break_even']} hours/month")
    
    print("\n" + "="*70)
