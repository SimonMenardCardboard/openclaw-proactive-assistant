#!/usr/bin/env python3
"""
Daily Intelligence Report

Orchestrates email, calendar, and location analysis → generates actionable digest.
Delivers via Telegram at 8 AM daily.

Usage:
    ./daily_intelligence_report.py [--dry-run] [--days-back 7]
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Add paths
WORKSPACE = Path.home() / '.openclaw/workspace'
sys.path.insert(0, str(WORKSPACE / 'integrations/intelligence/v8_meta_learning'))
sys.path.insert(0, str(WORKSPACE / 'integrations/direct_api'))

from universal_email_analyzer import UniversalEmailAnalyzer
from universal_calendar_analyzer import UniversalCalendarAnalyzer
from generate_optimizations import generate_optimizations

# Telegram setup
TELEGRAM_CHAT_ID = "8451730454"  # Simon's Telegram


class DailyIntelligenceReport:
    """Generate and deliver daily intelligence digest"""
    
    def __init__(self, days_back=7, dry_run=False):
        self.days_back = days_back
        self.dry_run = dry_run
        self.report_data = {}
        
    def run(self):
        """Generate full intelligence report"""
        print("🐯 Generating Daily Intelligence Report...\n")
        
        # 1. Email Analysis
        print("📧 Analyzing email patterns...")
        email_patterns = self._analyze_email()
        
        # 2. Calendar Analysis  
        print("\n📅 Analyzing calendar patterns...")
        calendar_patterns = self._analyze_calendar()
        
        # 3. Location Analysis (placeholder - pattern detector not built yet)
        print("\n📍 Location analysis...")
        location_patterns = self._analyze_location()
        
        # 4. Generate Optimizations
        print("\n⚡ Generating optimizations...")
        optimizations = self._generate_optimizations(email_patterns, calendar_patterns, location_patterns)
        
        # 5. Check V8 Proposals
        print("\n🤖 Checking V8 proposals...")
        v8_status = self._check_v8_proposals()
        
        # 6. Format Report
        print("\n📝 Formatting report...")
        report = self._format_report(email_patterns, calendar_patterns, location_patterns, optimizations, v8_status)
        
        # 7. Deliver
        if self.dry_run:
            print("\n" + "="*60)
            print("DRY RUN - Report preview:")
            print("="*60)
            print(report)
            print("="*60)
        else:
            # When run via OpenClaw cron with delivery.mode="announce",
            # just print the report and the cron system will deliver it
            print(report)
        
        return report
    
    def _analyze_email(self) -> Dict:
        """Run email analysis"""
        try:
            analyzer = UniversalEmailAnalyzer(days_back=self.days_back)
            analyzer.analyze_all()
            
            # Return key stats
            combined = analyzer.patterns.get('combined', {})
            return {
                'total_emails': analyzer.patterns.get('total_emails', 0),
                'accounts': len(analyzer.patterns.get('sources', [])),
                'top_senders': combined.get('top_senders', [])[:3],
                'peak_hour': combined.get('peak_hour', 'Unknown'),
                'newsletters': combined.get('newsletters', {}).get('detected', 0),
                'newsletter_percentage': combined.get('newsletters', {}).get('percentage', 0),
                'full_patterns': analyzer.patterns
            }
        except Exception as e:
            print(f"⚠️  Email analysis failed: {e}")
            return {'error': str(e)}
    
    def _analyze_calendar(self) -> Dict:
        """Run calendar analysis"""
        try:
            analyzer = UniversalCalendarAnalyzer(days_back=self.days_back, days_ahead=30)
            analyzer.analyze()
            
            patterns = analyzer.patterns.get('patterns', {})
            return {
                'total_events': analyzer.patterns.get('total_events', 0),
                'business_hours_utilization': patterns.get('business_hours_utilization', {}).get('percentage', 0),
                'back_to_back_percentage': patterns.get('back_to_back_meetings', {}).get('percentage', 0),
                'avg_duration_minutes': patterns.get('meeting_duration', {}).get('average', 0),
                'peak_day': patterns.get('day_distribution', {}).get('peak_day', 'Unknown'),
                'peak_hour': patterns.get('time_distribution', {}).get('peak_hour', 'Unknown'),
                'recurring_percentage': patterns.get('event_types', {}).get('recurring_percentage', 0),
                'full_patterns': analyzer.patterns
            }
        except Exception as e:
            print(f"⚠️  Calendar analysis failed: {e}")
            return {'error': str(e)}
    
    def _analyze_location(self) -> Dict:
        """Run location analysis (placeholder)"""
        # Location pattern detector not built yet
        # Will be implemented in Week 1-2
        return {
            'status': 'pending',
            'message': 'Location pattern detection coming soon'
        }
    
    def _generate_optimizations(self, email_patterns: Dict, calendar_patterns: Dict, location_patterns: Dict) -> List[Dict]:
        """Generate optimization recommendations"""
        try:
            # Combine patterns for optimization generator
            combined_patterns = {
                'total_emails': email_patterns.get('total_emails', 0),
                'combined': email_patterns.get('full_patterns', {}).get('combined', {}),
                'calendar': calendar_patterns.get('full_patterns', {}),
                'location': location_patterns
            }
            
            optimizations = generate_optimizations(combined_patterns)
            
            # Sort by priority and estimated time savings
            optimizations.sort(key=lambda x: (
                {'high': 0, 'medium': 1, 'low': 2}.get(x.get('priority', 'low'), 3),
                -x.get('estimated_time_saved_minutes_per_week', 0)
            ))
            
            return optimizations
        except Exception as e:
            print(f"⚠️  Optimization generation failed: {e}")
            return []
    
    def _check_v8_proposals(self) -> Dict:
        """Check V8 auto-generated proposals status"""
        try:
            # Read V8 approval database
            import sqlite3
            db_path = WORKSPACE / 'integrations/intelligence/v8_meta_learning/approvals.db'
            
            if not db_path.exists():
                return {'pending': 0, 'approved': 0, 'deployed': 0}
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Count by status
            cursor.execute("SELECT status, COUNT(*) FROM proposals GROUP BY status")
            status_counts = dict(cursor.fetchall())
            
            conn.close()
            
            return {
                'pending': status_counts.get('pending', 0),
                'approved': status_counts.get('approved', 0),
                'deployed': status_counts.get('deployed', 0),
                'implemented': status_counts.get('implemented', 0)
            }
        except Exception as e:
            print(f"⚠️  V8 status check failed: {e}")
            return {}
    
    def _format_report(self, email: Dict, calendar: Dict, location: Dict, optimizations: List[Dict], v8: Dict) -> str:
        """Format intelligence report for Telegram"""
        
        report = "🐯 *Daily Intelligence Report*\n"
        report += f"_{datetime.now().strftime('%A, %B %d, %Y')}_\n\n"
        
        # Email Section
        if 'error' not in email:
            report += "📧 *EMAIL* (Last 7 days)\n"
            report += f"• {email['total_emails']:,} emails across {email['accounts']} accounts\n"
            
            if email.get('peak_hour'):
                report += f"• Peak hour: {email['peak_hour']} (batch checking recommended)\n"
            
            if email.get('newsletters', 0) > 0:
                report += f"• {email['newsletters']} newsletters detected ({email['newsletter_percentage']:.1f}%)\n"
            
            if email.get('top_senders'):
                report += f"• Top sender: {email['top_senders'][0]['email']} ({email['top_senders'][0]['count']} emails)\n"
            
            report += "\n"
        
        # Calendar Section
        if 'error' not in calendar:
            report += "📅 *CALENDAR* (Next 30 days)\n"
            report += f"• {calendar['total_events']} events scheduled\n"
            
            if calendar.get('business_hours_utilization', 0) > 0:
                util = calendar['business_hours_utilization']
                emoji = "🚨" if util > 85 else "⚠️" if util > 70 else "✅"
                report += f"• {emoji} Business hours utilization: {util:.1f}%\n"
            
            if calendar.get('back_to_back_percentage', 0) > 0:
                report += f"• {calendar['back_to_back_percentage']:.1f}% back-to-back meetings (no breaks)\n"
            
            if calendar.get('avg_duration_minutes', 0) > 0:
                hours = calendar['avg_duration_minutes'] / 60
                report += f"• Average meeting: {hours:.1f} hours\n"
            
            if calendar.get('peak_day'):
                report += f"• Busiest day: {calendar['peak_day']}\n"
            
            report += "\n"
        
        # Location Section
        if location.get('status') == 'pending':
            report += "📍 *LOCATION*\n"
            report += f"• {location['message']}\n\n"
        
        # Optimizations Section
        if optimizations:
            # Calculate total time savings
            total_savings_min = sum(opt.get('estimated_time_saved_minutes_per_week', 0) for opt in optimizations)
            total_savings_hours = total_savings_min / 60
            
            report += f"⚡ *RECOMMENDED OPTIMIZATIONS* ({total_savings_hours:.1f} hrs/week)\n\n"
            
            # Show top 5 optimizations
            for i, opt in enumerate(optimizations[:5], 1):
                priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(opt.get('priority', 'low'), "⚪")
                time_saved = opt.get('estimated_time_saved_minutes_per_week', 0)
                
                report += f"{priority_emoji} *{opt['title']}*\n"
                report += f"   → Impact: {opt.get('impact', 'N/A')}\n"
                
                if time_saved > 0:
                    if time_saved >= 60:
                        report += f"   → Saves: {time_saved/60:.1f} hrs/week\n"
                    else:
                        report += f"   → Saves: {time_saved} min/week\n"
                
                report += "\n"
            
            if len(optimizations) > 5:
                report += f"_{len(optimizations) - 5} more optimizations available_\n\n"
        
        # V8 Proposals Section
        if v8:
            pending = v8.get('pending', 0)
            implemented = v8.get('implemented', 0)
            
            if pending > 0 or implemented > 0:
                report += "🤖 *V8 AUTO-OPTIMIZATIONS*\n"
                
                if pending > 0:
                    report += f"• {pending} proposals awaiting review\n"
                    report += f"  Type `v8-proposals` to review\n"
                
                if implemented > 0:
                    report += f"• ✅ {implemented} optimizations active\n"
                
                report += "\n"
        
        # Footer
        report += "_Reply with optimization # to implement, or 'v8-proposals' to review auto-generated code_"
        
        return report
    
    def _deliver_telegram(self, message: str):
        """Send report via Telegram (using subprocess to call openclaw CLI)"""
        try:
            import subprocess
            import tempfile
            
            # Write message to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(message)
                temp_file = f.name
            
            try:
                # Use openclaw CLI to send message
                # This will use the configured Telegram bot
                result = subprocess.run(
                    ['openclaw', 'telegram', 'send', TELEGRAM_CHAT_ID, '--file', temp_file],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    print("✅ Message sent to Telegram")
                else:
                    print(f"⚠️  Telegram send failed: {result.stderr}")
                    print("   Falling back to stdout...")
                    print(message)
            finally:
                # Clean up temp file
                Path(temp_file).unlink(missing_ok=True)
            
        except Exception as e:
            print(f"⚠️  Telegram delivery error: {e}")
            print("   Report generated but not sent.")
            print(message)


def main():
    parser = argparse.ArgumentParser(description='Generate daily intelligence report')
    parser.add_argument('--dry-run', action='store_true', help='Print report without sending')
    parser.add_argument('--days-back', type=int, default=7, help='Days of email history to analyze')
    
    args = parser.parse_args()
    
    reporter = DailyIntelligenceReport(days_back=args.days_back, dry_run=args.dry_run)
    reporter.run()


if __name__ == '__main__':
    main()
