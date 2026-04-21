#!/usr/bin/env python3
"""
Email Workflow Tracker - V8 Phase 1 Breadth Expansion

Analyzes email patterns to discover optimization opportunities:
- High-frequency senders (should filter/auto-archive)
- Response time patterns (which emails actually need quick replies)
- Email batching opportunities (checking too frequently?)
- Thread patterns (emails that always lead to meetings)

Goal: Find 5-10 email workflow optimizations
"""

import sqlite3
import json
import subprocess
from pathlib import Path
from typing import List, Dict
from datetime import datetime, timedelta
from collections import Counter, defaultdict


class EmailWorkflowTracker:
    """Track email patterns for optimization opportunities"""
    
    def __init__(self, db_path: Path = None):
        if db_path is None:
            db_path = Path.home() / '.openclaw/workspace/integrations/intelligence/v8_meta_learning/universal_workflows.db'
        
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize email workflow tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE,
                from_addr TEXT,
                to_addr TEXT,
                subject TEXT,
                received_at TEXT,
                read_at TEXT,
                replied_at TEXT,
                archived_at TEXT,
                has_attachments INTEGER,
                thread_id TEXT,
                tracked_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT,
                description TEXT,
                data TEXT,
                occurrences INTEGER,
                time_impact_minutes INTEGER,
                detected_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def fetch_recent_emails(self, days: int = 7) -> List[Dict]:
        """Fetch recent emails via gog CLI"""
        try:
            # Use gog to search recent Gmail messages (30 days for better pattern detection)
            result = subprocess.run(
                ['gog', 'gmail', 'search', 'newer_than:30d', 
                 '--account', 'lacrosseguy76665@gmail.com', '--json'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                # gog returns {threads: [...]} structure
                return data.get('threads', [])
            else:
                print(f"Error fetching emails: {result.stderr}")
                return []
                
        except Exception as e:
            print(f"Email fetch error: {e}")
            return []
    
    def track_emails(self, emails: List[Dict]):
        """Store emails for pattern analysis"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for email in emails:
            try:
                # Parse thread data from gog output
                thread_id = email.get('id', '')
                from_addr = self._extract_email(email.get('from', ''))
                subject = email.get('subject', 'No Subject')
                received = email.get('date', '')  # gog gives us formatted date
                
                # Convert date string to ISO
                received_dt = None
                if received:
                    try:
                        # Format: "2026-04-11 11:36"
                        dt = datetime.strptime(received, '%Y-%m-%d %H:%M')
                        received_dt = dt.isoformat()
                    except:
                        pass
                
                # Check if read/replied
                labels = email.get('labels', [])
                is_read = 'UNREAD' not in labels
                
                # Store thread as email entry
                cursor.execute("""
                    INSERT OR REPLACE INTO email_messages 
                    (message_id, from_addr, subject, received_at, read_at, thread_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (thread_id, from_addr, subject, received_dt, 
                      received_dt if is_read else None, thread_id))
                
            except Exception as e:
                print(f"Error tracking email {email.get('id', 'unknown')}: {e}")
        
        conn.commit()
        conn.close()
    
    def _extract_email(self, from_field: str) -> str:
        """Extract email address from 'Name <email>' format"""
        if '<' in from_field and '>' in from_field:
            return from_field.split('<')[1].split('>')[0]
        return from_field
    
    def detect_patterns(self) -> List[Dict]:
        """Analyze emails for optimization opportunities"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        patterns = []
        
        # Pattern 1: High-frequency low-value senders
        cursor.execute("""
            SELECT from_addr, COUNT(*) as count
            FROM email_messages
            WHERE received_at >= datetime('now', '-7 days')
            GROUP BY from_addr
            HAVING count >= 10
            ORDER BY count DESC
            LIMIT 10
        """)
        
        high_freq_senders = cursor.fetchall()
        if high_freq_senders:
            total_emails = sum(count for _, count in high_freq_senders)
            patterns.append({
                'type': 'high_frequency_senders',
                'description': f'{len(high_freq_senders)} senders sent {total_emails} emails in 7 days',
                'data': json.dumps([{'sender': s, 'count': c} for s, c in high_freq_senders[:5]]),
                'occurrences': len(high_freq_senders),
                'time_impact': total_emails * 0.5,  # 30sec per email
                'optimization': 'Create filters: auto-archive newsletters, categorize notifications'
            })
        
        # Pattern 2: Unread backlog
        cursor.execute("""
            SELECT COUNT(*) 
            FROM email_messages 
            WHERE read_at IS NULL
            AND received_at < datetime('now', '-3 days')
        """)
        
        unread_count = cursor.fetchone()[0]
        if unread_count > 20:
            patterns.append({
                'type': 'unread_backlog',
                'description': f'{unread_count} emails unread for >3 days',
                'data': json.dumps({'count': unread_count}),
                'occurrences': unread_count,
                'time_impact': 30,  # 30min to process backlog
                'optimization': 'Declare email bankruptcy, archive all >7 days old'
            })
        
        # Pattern 3: Same-day response expectation
        cursor.execute("""
            SELECT COUNT(*) 
            FROM email_messages 
            WHERE read_at IS NOT NULL
            AND replied_at IS NOT NULL
            AND date(read_at) = date(replied_at)
        """)
        
        same_day_replies = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM email_messages WHERE replied_at IS NOT NULL")
        total_replies = cursor.fetchone()[0]
        
        if total_replies > 0:
            same_day_pct = (same_day_replies / total_replies) * 100
            if same_day_pct > 80:
                patterns.append({
                    'type': 'same_day_response_pressure',
                    'description': f'{same_day_pct:.0f}% of emails replied same-day',
                    'data': json.dumps({'same_day': same_day_replies, 'total': total_replies}),
                    'occurrences': same_day_replies,
                    'time_impact': 60,  # 1hr/week from constant email checking
                    'optimization': 'Batch email processing: check 3x/day instead of constantly'
                })
        
        # Pattern 4: Newsletter overload
        cursor.execute("""
            SELECT COUNT(*) 
            FROM email_messages 
            WHERE subject LIKE '%newsletter%'
            OR subject LIKE '%digest%'
            OR subject LIKE '%update%'
            OR from_addr LIKE '%noreply%'
        """)
        
        newsletter_count = cursor.fetchone()[0]
        if newsletter_count > 30:
            patterns.append({
                'type': 'newsletter_overload',
                'description': f'{newsletter_count} newsletters/automated emails',
                'data': json.dumps({'count': newsletter_count}),
                'occurrences': newsletter_count,
                'time_impact': newsletter_count * 0.25,  # 15sec per newsletter
                'optimization': 'Unsubscribe from unused newsletters, use Unroll.me'
            })
        
        # Store detected patterns
        for pattern in patterns:
            cursor.execute("""
                INSERT INTO email_patterns 
                (pattern_type, description, data, occurrences, time_impact_minutes)
                VALUES (?, ?, ?, ?, ?)
            """, (
                pattern['type'],
                pattern['description'],
                pattern['data'],
                pattern['occurrences'],
                pattern['time_impact']
            ))
        
        conn.commit()
        conn.close()
        
        return patterns
    
    def generate_report(self) -> str:
        """Generate optimization report"""
        print("📧 Fetching recent emails...")
        emails = self.fetch_recent_emails()
        print(f"   Found {len(emails)} emails\n")
        
        if emails:
            print("📊 Tracking emails...")
            self.track_emails(emails)
            print("   Emails stored\n")
        
        print("🔍 Analyzing patterns...")
        patterns = self.detect_patterns()
        
        if not patterns:
            return "✅ No email optimization opportunities detected"
        
        report = "📧 EMAIL WORKFLOW OPTIMIZATION OPPORTUNITIES\n"
        report += "=" * 60 + "\n\n"
        
        total_time_saved = sum(p['time_impact'] for p in patterns)
        
        for i, pattern in enumerate(patterns, 1):
            report += f"{i}. {pattern['description']}\n"
            report += f"   Time Impact: {pattern['time_impact']:.0f} min saved\n"
            report += f"   Optimization: {pattern['optimization']}\n\n"
        
        report += f"Total Time Savings: {total_time_saved:.0f} min/week\n"
        report += f"Optimizations Found: {len(patterns)}\n"
        
        return report


if __name__ == '__main__':
    tracker = EmailWorkflowTracker()
    
    print("🔍 Analyzing email workflow patterns...")
    report = tracker.generate_report()
    print("\n" + report)
