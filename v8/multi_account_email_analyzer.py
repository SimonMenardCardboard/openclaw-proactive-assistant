#!/usr/bin/env python3
"""
Multi-Account Email Analyzer for V8

Analyzes email patterns across multiple accounts:
- Gmail (via gog)
- Outlook/Exchange (via Mail.app SQLite)

Detects:
1. Similar email templates (repeated subjects/content)
2. Recipient frequency patterns
3. Time-based patterns (weekly emails, etc.)
4. Cross-account patterns (same email sent from different accounts)
"""

import subprocess
import json
import sqlite3
from pathlib import Path
from collections import defaultdict, Counter
from typing import List, Dict, Optional
import re
from datetime import datetime, timedelta
import sys

# Add path for Microsoft Graph connector
sys.path.insert(0, str(Path(__file__).parent))
try:
    from microsoft_graph_connector import MicrosoftGraphConnector
    GRAPH_AVAILABLE = True
except ImportError:
    GRAPH_AVAILABLE = False


class MultiAccountEmailAnalyzer:
    """Analyze email patterns across Gmail and Outlook accounts"""
    
    def __init__(self):
        self.accounts = {
            'gmail_personal': {
                'type': 'gmail',
                'email': 'lacrosseguy76665@gmail.com',
                'gog_account': 'lacrosseguy76665@gmail.com'
            },
            'gmail_work': {
                'type': 'gmail',
                'email': 'simon@legalmensch.com',
                'gog_account': 'simon@legalmensch.com'
            },
            'outlook_school_mailapp': {
                'type': 'mail_app',
                'email': 'tmenard1@tulane.edu',
                'db_path': Path.home() / 'Library/Mail/V10/MailData/Envelope Index'
            }
        }
        
        # Add Microsoft Graph account if available
        if GRAPH_AVAILABLE:
            self.accounts['microsoft_graph'] = {
                'type': 'microsoft_graph',
                'email': 'all'  # Gets all Microsoft accounts user authenticated
            }
        
        self.min_occurrences = 3  # Pattern must appear 3+ times
        self.lookback_days = 30
    
    def analyze_all_accounts(self) -> Dict[str, List[Dict]]:
        """Analyze patterns across all email accounts"""
        all_emails = []
        
        for account_name, config in self.accounts.items():
            print(f"📧 Analyzing {account_name} ({config['email']})...")
            
            try:
                if config['type'] == 'gmail':
                    emails = self._fetch_gmail_emails(config)
                elif config['type'] == 'mail_app':
                    emails = self._fetch_mail_app_emails(config)
                elif config['type'] == 'microsoft_graph':
                    emails = self._fetch_microsoft_graph_emails(config)
                else:
                    continue
                
                # Tag with account
                for email in emails:
                    email['account'] = account_name
                    email['account_email'] = config['email']
                
                all_emails.extend(emails)
                print(f"   Found {len(emails)} emails")
            
            except Exception as e:
                print(f"   ⚠️  Error: {e}")
        
        print(f"\n📊 Total emails analyzed: {len(all_emails)}")
        
        # Detect patterns
        patterns = self._detect_patterns(all_emails)
        
        return patterns
    
    def _fetch_gmail_emails(self, config: Dict) -> List[Dict]:
        """Fetch emails from Gmail via gog"""
        emails = []
        
        # Use messages search with in:sent query
        # Get last 30 days of sent emails
        after_date = (datetime.now() - timedelta(days=self.lookback_days)).strftime('%Y/%m/%d')
        query = f"in:sent after:{after_date}"
        
        cmd = [
            'gog', 'gmail', 'messages', 'search',
            '--account', config['gog_account'],
            query,
            '--max', '100'
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # Parse table output (gog doesn't always support --json)
                lines = result.stdout.strip().split('\n')
                
                for line in lines:
                    # Skip header and empty lines
                    if not line or 'ID' in line or line.startswith('---'):
                        continue
                    
                    # Try to extract ID and Subject (basic parsing)
                    # Format varies, but ID is usually first field
                    parts = line.split(None, 1)
                    if len(parts) >= 2:
                        msg_id, rest = parts
                        
                        # Extract subject (simplified - may need better parsing)
                        subject = rest if rest else ''
                        
                        emails.append({
                            'id': msg_id,
                            'subject': subject,
                            'from': config['email'],  # We know it's from this account
                            'to': '',
                            'date': '',
                            'labels': ['SENT']
                        })
        
        except Exception as e:
            print(f"   Gmail fetch error: {e}")
        
        return emails
    
    def _fetch_microsoft_graph_emails(self, config: Dict) -> List[Dict]:
        """Fetch emails from Microsoft Graph API (Outlook/Exchange)"""
        emails = []
        
        try:
            connector = MicrosoftGraphConnector()
            
            # Fetch sent emails
            messages = connector.get_emails(max_results=100, folder='sentitems')
            
            for msg in messages:
                emails.append({
                    'id': msg.get('id'),
                    'subject': msg.get('subject', ''),
                    'from': msg.get('from', {}).get('emailAddress', {}).get('address', config['email']),
                    'to': ', '.join([r.get('emailAddress', {}).get('address', '') 
                                    for r in msg.get('toRecipients', [])]),
                    'date': msg.get('sentDateTime', ''),
                    'labels': []
                })
        
        except Exception as e:
            print(f"   Microsoft Graph error: {e}")
            print(f"   (Run microsoft_graph_connector.py to authenticate)")
        
        return emails
    
    def _fetch_mail_app_emails(self, config: Dict) -> List[Dict]:
        """Fetch emails from macOS Mail.app SQLite database"""
        emails = []
        db_path = config['db_path']
        
        if not db_path.exists():
            print(f"   Mail.app database not found: {db_path}")
            return emails
        
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cursor = conn.cursor()
            
            # Get sent emails from last 30 days
            cutoff = int((datetime.now() - timedelta(days=self.lookback_days)).timestamp())
            
            cursor.execute("""
                SELECT 
                    messages.ROWID,
                    subjects.subject,
                    addresses.address as sender,
                    messages.date_sent
                FROM messages
                LEFT JOIN subjects ON messages.subject = subjects.ROWID
                LEFT JOIN addresses ON messages.sender = addresses.ROWID
                WHERE messages.date_sent > ?
                AND messages.mailbox IN (
                    SELECT ROWID FROM mailboxes WHERE url LIKE '%Sent%'
                )
                ORDER BY messages.date_sent DESC
                LIMIT 100
            """, (cutoff,))
            
            for row in cursor.fetchall():
                emails.append({
                    'id': str(row[0]),
                    'subject': row[1] or '',
                    'from': row[2] or config['email'],
                    'to': '',  # Would need to join recipients table
                    'date': datetime.fromtimestamp(row[3]).isoformat() if row[3] else '',
                    'labels': []
                })
            
            conn.close()
        
        except Exception as e:
            print(f"   Mail.app fetch error: {e}")
        
        return emails
    
    def _detect_patterns(self, emails: List[Dict]) -> Dict[str, List[Dict]]:
        """Detect email workflow patterns"""
        patterns = {
            'similar_subjects': self._detect_similar_subjects(emails),
            'frequent_recipients': self._detect_frequent_recipients(emails),
            'time_patterns': self._detect_time_patterns(emails),
            'cross_account': self._detect_cross_account_patterns(emails)
        }
        
        return patterns
    
    def _detect_similar_subjects(self, emails: List[Dict]) -> List[Dict]:
        """Detect emails with similar subject lines"""
        # Normalize subjects (remove Re:, Fwd:, dates, numbers)
        normalized = defaultdict(list)
        
        for email in emails:
            subject = email['subject']
            
            # Remove common prefixes
            subject = re.sub(r'^(Re|RE|Fwd|FWD):\s*', '', subject)
            
            # Remove dates (YYYY-MM-DD, MM/DD/YYYY, etc.)
            subject = re.sub(r'\d{4}-\d{2}-\d{2}', '', subject)
            subject = re.sub(r'\d{1,2}/\d{1,2}/\d{2,4}', '', subject)
            
            # Remove numbers
            subject = re.sub(r'\d+', '', subject)
            
            # Normalize whitespace
            subject = ' '.join(subject.split()).strip()
            
            if subject:
                normalized[subject.lower()].append(email)
        
        patterns = []
        for norm_subject, email_list in normalized.items():
            if len(email_list) >= self.min_occurrences:
                patterns.append({
                    'type': 'similar_subject',
                    'template': norm_subject,
                    'count': len(email_list),
                    'accounts': list(set(e['account'] for e in email_list)),
                    'confidence': min(0.95, 0.70 + (len(email_list) / 20)),
                    'description': f"Email template '{norm_subject}' sent {len(email_list)} times",
                    'examples': email_list[:3]
                })
        
        return sorted(patterns, key=lambda x: x['count'], reverse=True)[:10]
    
    def _detect_frequent_recipients(self, emails: List[Dict]) -> List[Dict]:
        """Detect frequently emailed recipients"""
        # Note: Gmail search results may not have 'to' field
        # This would work better with full message fetch
        
        recipients = Counter()
        for email in emails:
            to = email.get('to', '')
            if to:
                recipients[to] += 1
        
        patterns = []
        for recipient, count in recipients.most_common(10):
            if count >= self.min_occurrences:
                patterns.append({
                    'type': 'frequent_recipient',
                    'recipient': recipient,
                    'count': count,
                    'confidence': min(0.90, 0.65 + (count / 30)),
                    'description': f"Frequent emails to {recipient} ({count} times)"
                })
        
        return patterns
    
    def _detect_time_patterns(self, emails: List[Dict]) -> List[Dict]:
        """Detect time-based email patterns (weekly, daily, etc.)"""
        # Group by weekday and hour
        by_weekday = defaultdict(list)
        by_hour = defaultdict(list)
        
        for email in emails:
            if email['date']:
                try:
                    dt = datetime.fromisoformat(email['date'].replace('Z', '+00:00'))
                    weekday = dt.strftime('%A')
                    hour = dt.hour
                    
                    by_weekday[weekday].append(email)
                    by_hour[hour].append(email)
                except:
                    pass
        
        patterns = []
        
        # Weekly patterns (same day of week)
        for day, day_emails in by_weekday.items():
            if len(day_emails) >= self.min_occurrences:
                patterns.append({
                    'type': 'weekly_pattern',
                    'day': day,
                    'count': len(day_emails),
                    'confidence': min(0.85, 0.60 + (len(day_emails) / 15)),
                    'description': f"Sends emails on {day} ({len(day_emails)} times)"
                })
        
        # Time-of-day patterns
        for hour, hour_emails in by_hour.items():
            if len(hour_emails) >= 5:
                patterns.append({
                    'type': 'time_pattern',
                    'hour': hour,
                    'count': len(hour_emails),
                    'confidence': min(0.80, 0.55 + (len(hour_emails) / 20)),
                    'description': f"Sends emails around {hour}:00 ({len(hour_emails)} times)"
                })
        
        return sorted(patterns, key=lambda x: x['count'], reverse=True)[:5]
    
    def _detect_cross_account_patterns(self, emails: List[Dict]) -> List[Dict]:
        """Detect patterns that span multiple accounts"""
        # Find similar subjects sent from different accounts
        subject_to_accounts = defaultdict(set)
        
        for email in emails:
            norm_subject = re.sub(r'^(Re|RE|Fwd|FWD):\s*', '', email['subject']).lower().strip()
            if norm_subject:
                subject_to_accounts[norm_subject].add(email['account'])
        
        patterns = []
        for subject, accounts in subject_to_accounts.items():
            if len(accounts) >= 2:
                patterns.append({
                    'type': 'cross_account',
                    'subject': subject,
                    'accounts': list(accounts),
                    'confidence': 0.75,
                    'description': f"Email '{subject}' sent from {len(accounts)} different accounts"
                })
        
        return patterns[:5]


def main():
    """Test multi-account email analyzer"""
    analyzer = MultiAccountEmailAnalyzer()
    
    print("="*60)
    print("MULTI-ACCOUNT EMAIL ANALYSIS")
    print("="*60)
    print()
    
    patterns = analyzer.analyze_all_accounts()
    
    for category, pattern_list in patterns.items():
        if pattern_list:
            print(f"\n{category.upper().replace('_', ' ')} ({len(pattern_list)}):")
            for i, pattern in enumerate(pattern_list[:3], 1):
                print(f"\n{i}. {pattern['description']}")
                print(f"   Confidence: {pattern['confidence']:.0%}")
                if 'accounts' in pattern:
                    print(f"   Accounts: {', '.join(pattern['accounts'])}")


if __name__ == '__main__':
    main()
