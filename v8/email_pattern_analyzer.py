#!/usr/bin/env python3
"""
Email Pattern Analyzer

Analyzes Gmail data to detect patterns for V8 optimization.

Patterns detected:
- Sender frequency (who emails you most)
- Reply delay (how fast you respond)
- Archive rate (what gets archived vs kept)
- Time-of-day patterns (when emails arrive/are read)
- Subject patterns (common keywords, newsletters)

Output: JSON for V8 workflow optimizer
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import Dict, List, Any
import re

# Add paths
WORKSPACE = Path.home() / '.openclaw/workspace'
sys.path.insert(0, str(WORKSPACE / 'integrations/direct_api'))

from gmail_api import GmailAPI


class EmailPatternAnalyzer:
    """Analyze email patterns for optimization opportunities"""
    
    def __init__(self, days_back=30):
        """
        Initialize analyzer.
        
        Args:
            days_back: How many days of history to analyze
        """
        self.gmail = GmailAPI()
        self.days_back = days_back
        self.emails = []
        self.patterns = {
            'analyzed_at': datetime.now().isoformat(),
            'period_days': days_back,
            'total_emails': 0,
            'senders': {},
            'reply_delays': {},
            'archive_rate': {},
            'time_patterns': {},
            'subject_patterns': {},
            'label_usage': {},
            'optimizations': []
        }
    
    def analyze(self):
        """Run full analysis pipeline"""
        print(f"📧 Analyzing last {self.days_back} days of email...")
        
        # Fetch emails
        self._fetch_emails()
        
        # Run analyses
        self._analyze_senders()
        self._analyze_reply_delays()
        self._analyze_archive_patterns()
        self._analyze_time_patterns()
        self._analyze_subjects()
        self._analyze_labels()
        
        # Generate optimization recommendations
        self._generate_optimizations()
        
        return self.patterns
    
    def _fetch_emails(self):
        """Fetch email history"""
        cutoff_date = datetime.now() - timedelta(days=self.days_back)
        query = f"after:{cutoff_date.strftime('%Y/%m/%d')}"
        
        print(f"  Fetching emails since {cutoff_date.strftime('%Y-%m-%d')}...")
        message_list = self.gmail.search(query=query, max_results=1000)
        
        print(f"  Fetching full message data for {len(message_list)} emails...")
        self.emails = []
        for i, msg in enumerate(message_list):
            if (i + 1) % 100 == 0:
                print(f"    Progress: {i+1}/{len(message_list)}...")
            
            # Fetch full message
            full_msg = self.gmail.get(msg['id'])
            headers = self.gmail.get_headers(full_msg)
            
            self.emails.append({
                'id': msg['id'],
                'threadId': msg['threadId'],
                'from': headers.get('From', ''),
                'to': headers.get('To', ''),
                'subject': headers.get('Subject', ''),
                'date': headers.get('Date', ''),
                'labelIds': full_msg.get('labelIds', [])
            })
        
        self.patterns['total_emails'] = len(self.emails)
        print(f"  ✓ Loaded {len(self.emails)} full emails")
    
    def _analyze_senders(self):
        """Analyze sender patterns"""
        print("\n  Analyzing sender patterns...")
        
        sender_counts = Counter()
        sender_threads = defaultdict(int)
        
        for email in self.emails:
            # Get sender from headers
            sender = email.get('from', '')
            
            # Extract email address
            email_match = re.search(r'[\w\.-]+@[\w\.-]+', sender)
            if email_match:
                sender_email = email_match.group(0).lower()
                sender_counts[sender_email] += 1
                
                # Count threads (approximate)
                if email.get('threadId'):
                    sender_threads[sender_email] += 1
        
        # Top senders
        top_senders = sender_counts.most_common(20)
        
        self.patterns['senders'] = {
            'top_20': [
                {
                    'email': sender,
                    'count': count,
                    'percentage': round(count / self.patterns['total_emails'] * 100, 1),
                    'threads': sender_threads.get(sender, 0)
                }
                for sender, count in top_senders
            ],
            'unique_senders': len(sender_counts),
            'concentration': round(sum(c for _, c in top_senders[:5]) / self.patterns['total_emails'] * 100, 1)
        }
        
        print(f"    ✓ {len(sender_counts)} unique senders")
        print(f"    ✓ Top 5 account for {self.patterns['senders']['concentration']}% of email")
    
    def _analyze_reply_delays(self):
        """Analyze how fast emails are replied to"""
        print("\n  Analyzing reply patterns...")
        
        # This is approximate - would need thread analysis for accuracy
        # For now, detect sent emails and estimate
        
        sent_query = f"in:sent after:{(datetime.now() - timedelta(days=self.days_back)).strftime('%Y/%m/%d')}"
        sent_emails = self.gmail.search(query=sent_query, max_results=500)
        
        # Calculate rough reply rate
        reply_rate = len(sent_emails) / max(self.patterns['total_emails'], 1)
        
        self.patterns['reply_delays'] = {
            'sent_count': len(sent_emails),
            'reply_rate': round(reply_rate * 100, 1),
            'avg_delay_hours': None,  # Would need thread timing analysis
            'note': 'Detailed reply timing requires thread analysis'
        }
        
        print(f"    ✓ {len(sent_emails)} emails sent ({self.patterns['reply_delays']['reply_rate']}% reply rate)")
    
    def _analyze_archive_patterns(self):
        """Analyze what gets archived vs kept in inbox"""
        print("\n  Analyzing archive patterns...")
        
        # Check inbox vs all mail
        inbox_query = f"in:inbox after:{(datetime.now() - timedelta(days=self.days_back)).strftime('%Y/%m/%d')}"
        inbox_emails = self.gmail.search(query=inbox_query, max_results=1000)
        
        archived_count = self.patterns['total_emails'] - len(inbox_emails)
        archive_rate = archived_count / max(self.patterns['total_emails'], 1)
        
        # Analyze what gets archived
        archived_senders = defaultdict(int)
        inbox_senders = defaultdict(int)
        
        for email in inbox_emails:
            sender = email.get('from', '')
            email_match = re.search(r'[\w\.-]+@[\w\.-]+', sender)
            if email_match:
                inbox_senders[email_match.group(0).lower()] += 1
        
        # Estimate archived senders (emails not in inbox)
        all_senders = {
            re.search(r'[\w\.-]+@[\w\.-]+', e.get('from', '')).group(0).lower()
            for e in self.emails
            if re.search(r'[\w\.-]+@[\w\.-]+', e.get('from', ''))
        }
        
        self.patterns['archive_rate'] = {
            'total_archived': archived_count,
            'archive_percentage': round(archive_rate * 100, 1),
            'inbox_count': len(inbox_emails),
            'likely_auto_archived': []  # Senders with 100% archive rate
        }
        
        # Find senders that are always archived
        for sender in all_senders:
            if sender not in inbox_senders:
                # This sender's emails are never in inbox
                total_from_sender = sum(
                    1 for e in self.emails
                    if re.search(r'[\w\.-]+@[\w\.-]+', e.get('from', ''))
                    and re.search(r'[\w\.-]+@[\w\.-]+', e.get('from', '')).group(0).lower() == sender
                )
                if total_from_sender >= 3:  # At least 3 emails
                    self.patterns['archive_rate']['likely_auto_archived'].append({
                        'sender': sender,
                        'count': total_from_sender
                    })
        
        print(f"    ✓ {archived_count} archived ({self.patterns['archive_rate']['archive_percentage']}%)")
        print(f"    ✓ {len(inbox_emails)} in inbox")
        print(f"    ✓ {len(self.patterns['archive_rate']['likely_auto_archived'])} senders always archived")
    
    def _analyze_time_patterns(self):
        """Analyze when emails arrive and are read"""
        print("\n  Analyzing time patterns...")
        
        hours = defaultdict(int)
        days = defaultdict(int)
        
        for email in self.emails:
            # Parse date from email
            date_str = email.get('date', '')
            if date_str:
                try:
                    # Gmail API returns date in headers
                    # Format: "Mon, 13 Apr 2026 09:15:32 -0700"
                    dt = datetime.strptime(date_str.split(' (')[0], '%a, %d %b %Y %H:%M:%S %z')
                    
                    hours[dt.hour] += 1
                    days[dt.strftime('%A')] += 1
                except:
                    pass
        
        # Find peak hours
        if hours:
            peak_hour = max(hours, key=hours.get)
            peak_day = max(days, key=days.get) if days else 'Unknown'
            
            self.patterns['time_patterns'] = {
                'peak_hour': peak_hour,
                'peak_day': peak_day,
                'hourly_distribution': dict(hours),
                'daily_distribution': dict(days),
                'business_hours_percentage': round(
                    sum(hours.get(h, 0) for h in range(9, 18)) / max(sum(hours.values()), 1) * 100, 1
                )
            }
            
            print(f"    ✓ Peak hour: {peak_hour}:00")
            print(f"    ✓ Peak day: {peak_day}")
            print(f"    ✓ {self.patterns['time_patterns']['business_hours_percentage']}% during business hours")
        else:
            self.patterns['time_patterns'] = {'note': 'Could not parse email dates'}
    
    def _analyze_subjects(self):
        """Analyze subject line patterns"""
        print("\n  Analyzing subject patterns...")
        
        subjects = [email.get('subject', '') for email in self.emails]
        
        # Detect newsletters (common patterns)
        newsletter_patterns = [
            r'newsletter',
            r'digest',
            r'weekly',
            r'daily',
            r'update',
            r'\[.*\]',  # [Newsletter Name]
            r'unsubscribe'
        ]
        
        newsletters = 0
        for subject in subjects:
            subject_lower = subject.lower()
            if any(re.search(pattern, subject_lower) for pattern in newsletter_patterns):
                newsletters += 1
        
        # Common words
        words = []
        for subject in subjects:
            # Remove common words
            words.extend(
                w.lower() for w in re.findall(r'\b\w{4,}\b', subject)
                if w.lower() not in {'from', 'your', 'this', 'that', 'with', 'have', 'been', 'have'}
            )
        
        common_words = Counter(words).most_common(20)
        
        self.patterns['subject_patterns'] = {
            'newsletter_count': newsletters,
            'newsletter_percentage': round(newsletters / max(len(subjects), 1) * 100, 1),
            'common_words': [
                {'word': word, 'count': count}
                for word, count in common_words
            ]
        }
        
        print(f"    ✓ {newsletters} newsletters detected ({self.patterns['subject_patterns']['newsletter_percentage']}%)")
    
    def _analyze_labels(self):
        """Analyze label usage"""
        print("\n  Analyzing label usage...")
        
        labels = Counter()
        
        for email in self.emails:
            email_labels = email.get('labelIds', [])
            for label in email_labels:
                # Skip system labels
                if not label.startswith('Label_'):
                    labels[label] += 1
        
        self.patterns['label_usage'] = {
            'total_labels': len(labels),
            'top_labels': [
                {'label': label, 'count': count}
                for label, count in labels.most_common(10)
            ]
        }
        
        print(f"    ✓ {len(labels)} different labels in use")
    
    def _generate_optimizations(self):
        """Generate optimization recommendations"""
        print("\n  Generating optimization recommendations...")
        
        optimizations = []
        
        # High-volume sender optimization
        if self.patterns['senders']['top_20']:
            top_sender = self.patterns['senders']['top_20'][0]
            if top_sender['percentage'] > 15:
                optimizations.append({
                    'type': 'email_filter',
                    'priority': 'high',
                    'title': f"Auto-filter high-volume sender: {top_sender['email']}",
                    'description': f"{top_sender['email']} sends {top_sender['percentage']}% of your email ({top_sender['count']} in {self.days_back} days)",
                    'action': f"Create filter: from:{top_sender['email']} → auto-label or archive",
                    'impact': f"Reduce inbox clutter by {top_sender['percentage']}%",
                    'confidence': 0.9
                })
        
        # Newsletter auto-archive
        if self.patterns['subject_patterns']['newsletter_percentage'] > 10:
            optimizations.append({
                'type': 'email_filter',
                'priority': 'medium',
                'title': 'Auto-archive newsletters after 7 days',
                'description': f"{self.patterns['subject_patterns']['newsletter_count']} newsletters detected ({self.patterns['subject_patterns']['newsletter_percentage']}% of email)",
                'action': 'Create filter: subject:(newsletter OR digest OR weekly) older_than:7d → archive',
                'impact': f"Auto-cleanup {self.patterns['subject_patterns']['newsletter_count']} newsletters/month",
                'confidence': 0.85
            })
        
        # Already-archived senders
        if len(self.patterns['archive_rate']['likely_auto_archived']) > 3:
            optimizations.append({
                'type': 'email_filter',
                'priority': 'low',
                'title': 'Formalize auto-archive rules',
                'description': f"{len(self.patterns['archive_rate']['likely_auto_archived'])} senders are manually archived 100% of the time",
                'action': 'Create filters to auto-archive these senders',
                'impact': 'Eliminate manual archive clicks',
                'confidence': 0.75,
                'senders': [s['sender'] for s in self.patterns['archive_rate']['likely_auto_archived'][:5]]
            })
        
        # Low reply rate senders (potential unsubscribe candidates)
        # This would need more analysis
        
        self.patterns['optimizations'] = optimizations
        
        print(f"    ✓ {len(optimizations)} optimization opportunities identified")
    
    def save_results(self, output_file=None):
        """Save analysis results to JSON"""
        if output_file is None:
            output_file = Path(__file__).parent / f'email_patterns_{datetime.now().strftime("%Y%m%d")}.json'
        
        with open(output_file, 'w') as f:
            json.dump(self.patterns, f, indent=2)
        
        print(f"\n✓ Results saved to: {output_file}")
        return output_file
    
    def print_summary(self):
        """Print human-readable summary"""
        print("\n" + "=" * 70)
        print("EMAIL PATTERN ANALYSIS SUMMARY")
        print("=" * 70)
        
        print(f"\n📊 Overview:")
        print(f"  Period: Last {self.days_back} days")
        print(f"  Total emails: {self.patterns['total_emails']}")
        print(f"  Unique senders: {self.patterns['senders']['unique_senders']}")
        print(f"  Archive rate: {self.patterns['archive_rate']['archive_percentage']}%")
        
        print(f"\n👥 Top Senders:")
        for sender in self.patterns['senders']['top_20'][:5]:
            print(f"  {sender['email']:40} {sender['count']:4} emails ({sender['percentage']:5.1f}%)")
        
        print(f"\n⏱️  Time Patterns:")
        if 'peak_hour' in self.patterns['time_patterns']:
            print(f"  Peak hour: {self.patterns['time_patterns']['peak_hour']}:00")
            print(f"  Peak day: {self.patterns['time_patterns']['peak_day']}")
            print(f"  Business hours: {self.patterns['time_patterns']['business_hours_percentage']}%")
        
        print(f"\n📰 Newsletters:")
        print(f"  Detected: {self.patterns['subject_patterns']['newsletter_count']} ({self.patterns['subject_patterns']['newsletter_percentage']}%)")
        
        print(f"\n💡 Optimization Opportunities ({len(self.patterns['optimizations'])}):")
        for i, opt in enumerate(self.patterns['optimizations'], 1):
            print(f"\n  {i}. {opt['title']} [{opt['priority'].upper()}]")
            print(f"     {opt['description']}")
            print(f"     Action: {opt['action']}")
            print(f"     Impact: {opt['impact']}")
            print(f"     Confidence: {int(opt['confidence'] * 100)}%")
        
        print("\n" + "=" * 70)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze email patterns for V8 optimization')
    parser.add_argument('--days', type=int, default=30, help='Days of history to analyze (default: 30)')
    parser.add_argument('--output', type=str, help='Output JSON file (default: auto-generated)')
    parser.add_argument('--quiet', action='store_true', help='Suppress summary output')
    
    args = parser.parse_args()
    
    try:
        analyzer = EmailPatternAnalyzer(days_back=args.days)
        patterns = analyzer.analyze()
        
        # Save results
        output_file = analyzer.save_results(args.output)
        
        # Print summary
        if not args.quiet:
            analyzer.print_summary()
        
        return 0
        
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
