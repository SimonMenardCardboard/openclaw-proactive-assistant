#!/usr/bin/env python3
"""
Email Priority Scoring Engine

Scores emails based on:
1. Contact importance (from context DB)
2. Response time patterns (are you overdue?)
3. Urgency keywords detection
4. Deadline extraction

Priority Levels:
- CRITICAL: VIP overdue + urgency keywords
- HIGH: Important contact overdue OR urgency keywords
- MEDIUM: Regular contact with deadline
- LOW: Everything else
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import sqlite3

# Urgency keyword patterns
URGENCY_KEYWORDS = [
    r'\bURGENT\b',
    r'\bASAP\b',
    r'\bimmediate(ly)?\b',
    r'\basap\b',
    r'\btime[- ]sensitive\b',
    r'\bdeadline\b',
    r'\bby (tomorrow|today|end of day|EOD|COB)\b',
    r'\bneed(s)? (this|response|answer) (today|tomorrow|ASAP)\b',
    r'\bpriority\b',
    r'\bcritical\b',
]

# Deadline extraction patterns
DEADLINE_PATTERNS = [
    r'due (today|tomorrow|by ([A-Z][a-z]+ \d{1,2}))',
    r'deadline:?\s*([A-Z][a-z]+ \d{1,2})',
    r'by (tomorrow|today|end of day|EOD|COB)',
    r'need(s)? by ([A-Z][a-z]+ \d{1,2})',
    r'expires?\s*([A-Z][a-z]+ \d{1,2})',
]

class EmailPriorityScorer:
    """Score email priority for intelligent inbox triage."""
    
    def __init__(self, context_db_path: Optional[Path] = None):
        """
        Initialize priority scorer.
        
        Args:
            context_db_path: Path to context database (defaults to standard location)
        """
        if context_db_path is None:
            context_db_path = Path.home() / ".openclaw/workspace/transmogrifier/openclaw-proactive-assistant/proactive_system/context.db"
        
        self.context_db_path = Path(context_db_path)
    
    def score_email(self, email: Dict) -> Dict:
        """
        Score a single email.
        
        Args:
            email: Email dict with keys: from, subject, body, date
            
        Returns:
            Dict with: priority_level, priority_score, reasons, deadline, is_overdue
        """
        from_addr = self._extract_email(email.get('from', ''))
        subject = email.get('subject', '')
        body = email.get('body', '')
        email_date = email.get('date')
        
        score = 0
        reasons = []
        
        # 1. Contact importance (0-50 points)
        contact_info = self._get_contact_info(from_addr)
        if contact_info:
            importance = contact_info.get('importance_score', 0)
            score += min(importance, 50)
            
            if importance > 40:
                reasons.append(f"VIP contact (importance: {importance:.1f})")
            elif importance > 20:
                reasons.append(f"Important contact (importance: {importance:.1f})")
            
            # Check if overdue
            avg_response_hours = contact_info.get('avg_response_hours')
            if avg_response_hours and email_date:
                hours_since = self._hours_since(email_date)
                if hours_since > avg_response_hours * 1.5:
                    score += 20
                    reasons.append(f"Overdue (you usually reply in {avg_response_hours:.1f}h, it's been {hours_since:.1f}h)")
        
        # 2. Urgency keywords (0-30 points)
        urgency_count = 0
        for pattern in URGENCY_KEYWORDS:
            if re.search(pattern, subject, re.IGNORECASE) or re.search(pattern, body, re.IGNORECASE):
                urgency_count += 1
        
        if urgency_count > 0:
            urgency_score = min(urgency_count * 10, 30)
            score += urgency_score
            reasons.append(f"Urgency keywords ({urgency_count} found)")
        
        # 3. Deadline detection (0-20 points)
        deadline = self._extract_deadline(subject + " " + body)
        if deadline:
            days_until = (deadline - datetime.now()).days
            
            if days_until <= 0:
                score += 20
                reasons.append(f"Deadline today or passed")
            elif days_until == 1:
                score += 15
                reasons.append(f"Deadline tomorrow")
            elif days_until <= 3:
                score += 10
                reasons.append(f"Deadline in {days_until} days")
        
        # Determine priority level
        if score >= 70:
            priority_level = "CRITICAL"
        elif score >= 40:
            priority_level = "HIGH"
        elif score >= 20:
            priority_level = "MEDIUM"
        else:
            priority_level = "LOW"
        
        return {
            'priority_level': priority_level,
            'priority_score': score,
            'reasons': reasons,
            'deadline': deadline.isoformat() if deadline else None,
            'from_email': from_addr,
            'subject': subject,
            'contact_info': contact_info
        }
    
    def score_emails(self, emails: List[Dict]) -> List[Dict]:
        """
        Score multiple emails and sort by priority.
        
        Args:
            emails: List of email dicts
            
        Returns:
            Sorted list of scored emails (highest priority first)
        """
        scored = []
        for email in emails:
            score_result = self.score_email(email)
            score_result['original_email'] = email
            scored.append(score_result)
        
        # Sort by priority score (descending)
        scored.sort(key=lambda x: x['priority_score'], reverse=True)
        
        return scored
    
    def get_priority_summary(self, emails: List[Dict]) -> Dict:
        """
        Get summary of email priorities.
        
        Args:
            emails: List of email dicts
            
        Returns:
            Summary dict with counts by priority level
        """
        scored = self.score_emails(emails)
        
        summary = {
            'CRITICAL': [],
            'HIGH': [],
            'MEDIUM': [],
            'LOW': []
        }
        
        for email_score in scored:
            level = email_score['priority_level']
            summary[level].append(email_score)
        
        return {
            'total': len(emails),
            'critical_count': len(summary['CRITICAL']),
            'high_count': len(summary['HIGH']),
            'medium_count': len(summary['MEDIUM']),
            'low_count': len(summary['LOW']),
            'critical_emails': summary['CRITICAL'],
            'high_emails': summary['HIGH'],
            'medium_emails': summary['MEDIUM'],
            'low_emails': summary['LOW']
        }
    
    def _get_contact_info(self, email: str) -> Optional[Dict]:
        """Get contact info from context database."""
        if not self.context_db_path.exists():
            return None
        
        try:
            conn = sqlite3.connect(self.context_db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT email, importance_score, avg_response_hours, total_emails, is_vip
                FROM contacts
                WHERE email = ?
            ''', (email,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'email': row[0],
                    'importance_score': row[1],
                    'avg_response_hours': row[2],
                    'total_emails': row[3],
                    'is_vip': bool(row[4])
                }
            
            return None
            
        except Exception:
            return None
    
    def _extract_email(self, from_field: str) -> str:
        """Extract email from 'Name <email>' format."""
        match = re.search(r'<([^>]+)>', from_field)
        if match:
            return match.group(1).lower()
        return from_field.lower()
    
    def _hours_since(self, email_date: str) -> float:
        """Calculate hours since email was received."""
        try:
            if isinstance(email_date, str):
                # Try parsing common formats
                for fmt in ['%a, %d %b %Y %H:%M:%S %z', '%Y-%m-%dT%H:%M:%S%z']:
                    try:
                        dt = datetime.strptime(email_date, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    return 0
            else:
                dt = email_date
            
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
            delta = now - dt
            return delta.total_seconds() / 3600
            
        except Exception:
            return 0
    
    def _extract_deadline(self, text: str) -> Optional[datetime]:
        """Extract deadline from text."""
        for pattern in DEADLINE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Try to parse the deadline
                try:
                    deadline_str = match.group(1)
                    
                    if 'today' in deadline_str.lower():
                        return datetime.now().replace(hour=23, minute=59, second=59)
                    elif 'tomorrow' in deadline_str.lower():
                        return datetime.now() + timedelta(days=1)
                    else:
                        # Try parsing date
                        return datetime.strptime(deadline_str, '%B %d')
                except Exception:
                    continue
        
        return None


def main():
    """Test email priority scoring."""
    scorer = EmailPriorityScorer()
    
    # Test emails
    test_emails = [
        {
            'from': 'john@example.com',
            'subject': 'URGENT: Need response by EOD',
            'body': 'This is time-sensitive. Deadline today.',
            'date': (datetime.now() - timedelta(hours=2)).isoformat()
        },
        {
            'from': 'sarah@example.com',
            'subject': 'Quick question',
            'body': 'When you have a moment...',
            'date': (datetime.now() - timedelta(hours=1)).isoformat()
        },
    ]
    
    print("Email Priority Scoring Test")
    print("=" * 80)
    
    for email in test_emails:
        result = scorer.score_email(email)
        print(f"\nFrom: {email['from']}")
        print(f"Subject: {email['subject']}")
        print(f"Priority: {result['priority_level']} (score: {result['priority_score']})")
        print(f"Reasons: {', '.join(result['reasons']) if result['reasons'] else 'None'}")
    
    print("\n\nPriority Summary:")
    summary = scorer.get_priority_summary(test_emails)
    print(f"Total: {summary['total']}")
    print(f"Critical: {summary['critical_count']}")
    print(f"High: {summary['high_count']}")
    print(f"Medium: {summary['medium_count']}")
    print(f"Low: {summary['low_count']}")


if __name__ == '__main__':
    main()
