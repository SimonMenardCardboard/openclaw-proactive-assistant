#!/usr/bin/env python3
"""
Morning Briefing Generator

Generates personalized daily briefings using:
- Context database (stored intelligence)
- Universal Email API (live email data)
- Universal Calendar API (live calendar data)

Delivers via Telegram.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import logging

# Add current dir to path
sys.path.insert(0, str(Path(__file__).parent))

from context_database import ContextDatabase
from universal_email_api import UniversalAccountManager as EmailManager
from universal_calendar_api import UniversalCalendarManager as CalendarManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [BRIEFING] %(message)s'
)
logger = logging.getLogger(__name__)


class MorningBriefing:
    """Generate personalized morning briefings."""
    
    def __init__(self):
        self.db = ContextDatabase()
        self.email_manager = EmailManager()
        self.cal_manager = CalendarManager()
    
    def generate(self) -> str:
        """Generate complete morning briefing."""
        logger.info("Generating morning briefing...")
        
        sections = []
        
        # Header
        now = datetime.now()
        greeting = self._get_greeting(now)
        sections.append(f"{greeting}\n")
        
        # Email section
        email_section = self._generate_email_section()
        if email_section:
            sections.append(email_section)
        
        # Calendar section
        calendar_section = self._generate_calendar_section()
        if calendar_section:
            sections.append(calendar_section)
        
        # Focus time section
        focus_section = self._generate_focus_time_section()
        if focus_section:
            sections.append(focus_section)
        
        # Tasks section
        tasks_section = self._generate_tasks_section()
        if tasks_section:
            sections.append(tasks_section)
        
        briefing = "\n".join(sections)
        logger.info(f"Briefing generated ({len(briefing)} chars)")
        
        return briefing
    
    def _get_greeting(self, now: datetime) -> str:
        """Get time-appropriate greeting."""
        hour = now.hour
        
        if hour < 12:
            return "🌅 Good morning!"
        elif hour < 17:
            return "☀️ Good afternoon!"
        else:
            return "🌆 Good evening!"
    
    def _generate_email_section(self) -> str:
        """Generate email priority section."""
        logger.info("Analyzing email...")
        
        # Get top contacts from context DB
        top_contacts = self.db.get_top_contacts(limit=10)
        
        if not top_contacts:
            return None
        
        # Get unread messages across all accounts
        all_unread = []
        
        for account in self.email_manager.get_all_accounts():
            email = account['email']
            api = self.email_manager.get_account(email)
            
            if not api:
                continue
            
            unread = api.get_unread_messages(hours_back=24, max_results=50)
            
            # Score each unread by contact importance
            for msg in unread:
                from_addr = self._extract_email(msg['from'])
                
                # Find contact in top contacts
                contact = next((c for c in top_contacts if c['email'] == from_addr), None)
                
                if contact:
                    msg['importance_score'] = contact['importance_score']
                    msg['avg_response_hours'] = contact.get('avg_response_hours')
                    msg['contact_name'] = contact['name']
                    msg['account'] = email
                else:
                    msg['importance_score'] = 0
                    msg['avg_response_hours'] = None
                    msg['contact_name'] = from_addr
                    msg['account'] = email
                
                all_unread.append(msg)
        
        if not all_unread:
            return "📧 **Email:** All caught up! ✅\n"
        
        # Sort by importance
        all_unread.sort(key=lambda m: m['importance_score'], reverse=True)
        
        # Build section
        lines = [f"📧 **Email** ({len(all_unread)} unread):\n"]
        
        # High priority (top 3)
        high_priority = [m for m in all_unread if m['importance_score'] > 30][:3]
        
        if high_priority:
            lines.append("**High Priority:**")
            for msg in high_priority:
                name = msg['contact_name']
                subject = msg['subject'][:50]
                
                # Check if response is overdue
                if msg.get('avg_response_hours') and msg['avg_response_hours'] < 12:
                    lines.append(f"  ⚠️ **{name}**: {subject}")
                    lines.append(f"     (You usually reply in {msg['avg_response_hours']:.1f}h)")
                else:
                    lines.append(f"  • **{name}**: {subject}")
            lines.append("")
        
        # Show total by account
        by_account = {}
        for msg in all_unread:
            account = msg['account']
            by_account[account] = by_account.get(account, 0) + 1
        
        if len(by_account) > 1:
            lines.append("**By Account:**")
            for account, count in by_account.items():
                account_short = account.split('@')[0]
                lines.append(f"  • {account_short}: {count} unread")
            lines.append("")
        
        return "\n".join(lines)
    
    def _generate_calendar_section(self) -> str:
        """Generate calendar section."""
        logger.info("Analyzing calendar...")
        
        # Get today's events across all calendars
        all_events = self.cal_manager.get_all_events_across_accounts(max_per_account=50)
        
        # Filter to today only
        today_events = []
        today = datetime.now().date()
        
        for account_email, events in all_events.items():
            for event in events:
                event_start = self._parse_datetime(event['start'])
                if event_start and event_start.date() == today:
                    event['account'] = account_email
                    today_events.append(event)
        
        if not today_events:
            return "📅 **Calendar:** No meetings today ✨\n"
        
        # Sort by start time
        today_events.sort(key=lambda e: self._parse_datetime(e['start']))
        
        # Build section
        lines = [f"📅 **Calendar** ({len(today_events)} meetings today):\n"]
        
        for event in today_events[:5]:  # Show first 5
            start_time = self._parse_datetime(event['start'])
            summary = event['summary']
            attendees_count = len(event.get('attendees', []))
            
            time_str = start_time.strftime('%I:%M%p').lstrip('0').lower()
            
            if attendees_count > 0:
                lines.append(f"  • **{time_str}**: {summary} ({attendees_count} attendees)")
            else:
                lines.append(f"  • **{time_str}**: {summary}")
        
        if len(today_events) > 5:
            lines.append(f"  ... and {len(today_events) - 5} more")
        
        lines.append("")
        
        # Check for conflicts
        conflicts = []
        for account_email, events in all_events.items():
            api = self.cal_manager.get_account(account_email)
            if api:
                account_conflicts = api.detect_conflicts(events)
                conflicts.extend(account_conflicts)
        
        if conflicts:
            lines.append("**⚠️ Conflicts Detected:**")
            for conflict in conflicts[:2]:  # Show first 2
                lines.append(f"  • {conflict['event_1']} overlaps with {conflict['event_2']}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _generate_focus_time_section(self) -> str:
        """Generate focus time section."""
        logger.info("Analyzing focus time...")
        
        # Get today's events
        all_events = self.cal_manager.get_all_events_across_accounts(max_per_account=50)
        
        # Combine all today's events
        today_events = []
        today = datetime.now().date()
        
        for events in all_events.values():
            for event in events:
                event_start = self._parse_datetime(event['start'])
                if event_start and event_start.date() == today:
                    today_events.append(event)
        
        if not today_events:
            return None
        
        # Find gaps
        gaps = []
        for account_email, events in all_events.items():
            api = self.cal_manager.get_account(account_email)
            if api:
                account_gaps = api.find_focus_time_gaps(events, min_gap_hours=2.0)
                
                # Filter to today only
                for gap in account_gaps:
                    if gap['start'].date() == today:
                        gaps.append(gap)
        
        if not gaps:
            return None
        
        # Sort by duration
        gaps.sort(key=lambda g: g['duration_hours'], reverse=True)
        
        # Build section
        lines = ["🎯 **Focus Time:**\n"]
        
        best_gap = gaps[0]
        start_time = best_gap['start'].strftime('%I:%M%p').lstrip('0').lower()
        end_time = best_gap['end'].strftime('%I:%M%p').lstrip('0').lower()
        duration = best_gap['duration_hours']
        
        lines.append(f"  • **{start_time} - {end_time}** ({duration:.1f}h clear)")
        lines.append(f"    Perfect for deep work ✨")
        lines.append("")
        
        return "\n".join(lines)
    
    def _generate_tasks_section(self) -> str:
        """Generate tasks section."""
        tasks = self.db.get_pending_tasks(limit=5)
        
        if not tasks:
            return None
        
        lines = [f"✅ **Tasks** ({len(tasks)} pending):\n"]
        
        for task in tasks[:3]:
            title = task['title']
            deadline = task.get('deadline')
            
            if deadline:
                deadline_dt = datetime.fromisoformat(deadline)
                if deadline_dt.date() == datetime.now().date():
                    lines.append(f"  🔴 **{title}** (due today)")
                else:
                    lines.append(f"  • {title}")
            else:
                lines.append(f"  • {title}")
        
        if len(tasks) > 3:
            lines.append(f"  ... and {len(tasks) - 3} more")
        
        lines.append("")
        
        return "\n".join(lines)
    
    def _extract_email(self, email_str: str) -> str:
        """Extract email from 'Name <email>' format."""
        import re
        match = re.search(r'<(.+?)>', email_str)
        if match:
            return match.group(1).lower()
        return email_str.lower().strip()
    
    def _parse_datetime(self, dt_str: str):
        """Parse datetime string."""
        try:
            if 'T' in dt_str:
                return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            else:
                return datetime.fromisoformat(dt_str)
        except:
            return None


def send_telegram_notification(message: str, chat_id: str = "8451730454"):
    """Send notification via Telegram."""
    try:
        import requests
        import os
        
        # Get bot token from environment
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        
        if not bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set, printing to stdout instead")
            print("\n" + "="*60)
            print("BRIEFING (would be sent to Telegram):")
            print("="*60)
            print(message)
            print("="*60 + "\n")
            return False
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'Markdown'
        }
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        logger.info(f"✅ Sent to Telegram (chat_id: {chat_id})")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
        # Print to stdout as fallback
        print("\n" + "="*60)
        print("BRIEFING:")
        print("="*60)
        print(message)
        print("="*60 + "\n")
        return False


def main():
    """Generate and deliver morning briefing."""
    print("\n" + "="*60)
    print("Morning Briefing Generator")
    print("="*60 + "\n")
    
    # Generate briefing
    briefing_gen = MorningBriefing()
    briefing = briefing_gen.generate()
    
    # Send via Telegram
    send_telegram_notification(briefing)
    
    print("\n✅ Briefing complete!\n")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"Briefing generation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
