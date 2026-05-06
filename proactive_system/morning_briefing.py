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
from email_priority import EmailPriorityScorer
from calendar_conflicts import CalendarConflictDetector

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
        self.email_scorer = EmailPriorityScorer()
        self.conflict_detector = CalendarConflictDetector()
    
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
        """Generate email priority section with intelligent scoring."""
        logger.info("Analyzing email...")
        
        # Get unread messages across all accounts
        all_unread = []
        
        for account in self.email_manager.get_all_accounts():
            email = account['email']
            api = self.email_manager.get_account(email)
            
            if not api:
                continue
            
            unread = api.get_unread_messages(hours_back=24, max_results=50)
            
            for msg in unread:
                msg['account'] = email
                all_unread.append(msg)
        
        if not all_unread:
            return "📧 **Email:** All caught up! ✅\n"
        
        # Use priority scorer to rank emails
        priority_summary = self.email_scorer.get_priority_summary(all_unread)
        
        # Build section
        lines = [f"📧 **Email** ({priority_summary['total']} unread):\n"]
        
        # Critical emails
        if priority_summary['critical_count'] > 0:
            lines.append("🚨 **CRITICAL:**")
            for email_score in priority_summary['critical_emails'][:3]:
                subject = email_score['subject'][:60]
                reasons = ", ".join(email_score['reasons'][:2])
                lines.append(f"  • {subject}")
                lines.append(f"    {reasons}")
            lines.append("")
        
        # High priority emails
        if priority_summary['high_count'] > 0:
            lines.append("⚠️ **High Priority:**")
            for email_score in priority_summary['high_emails'][:3]:
                subject = email_score['subject'][:60]
                reasons = ", ".join(email_score['reasons'][:2]) if email_score['reasons'] else "Important contact"
                lines.append(f"  • {subject}")
                if reasons:
                    lines.append(f"    {reasons}")
            lines.append("")
        
        # Show total by priority
        if priority_summary['medium_count'] > 0 or priority_summary['low_count'] > 0:
            lines.append("**Summary:**")
            if priority_summary['medium_count'] > 0:
                lines.append(f"  • {priority_summary['medium_count']} medium priority")
            if priority_summary['low_count'] > 0:
                lines.append(f"  • {priority_summary['low_count']} low priority")
            lines.append("")
        
        return "\n".join(lines)
    
    def _generate_calendar_section(self) -> str:
        """Generate calendar section with conflict detection."""
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
        
        # Detect conflicts
        conflicts = self.conflict_detector.detect_conflicts(today_events, today)
        
        # Sort by start time
        today_events.sort(key=lambda e: self._parse_datetime(e['start']))
        
        # Build section
        lines = [f"📅 **Calendar** ({len(today_events)} meetings today)"]
        
        # Show conflicts first if any
        if conflicts['severity'] in ['CRITICAL', 'HIGH']:
            lines.append(f"⚠️ **{conflicts['severity']} Conflicts Detected:**\n")
            for suggestion in conflicts['suggestions'][:3]:
                lines.append(f"  {suggestion}")
            lines.append("")
        elif conflicts['severity'] == 'MEDIUM':
            lines.append(f"⚠️ **Scheduling Notes:**\n")
            for suggestion in conflicts['suggestions'][:2]:
                lines.append(f"  {suggestion}")
            lines.append("")
        else:
            lines.append("\n")
        
        # Show meetings
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
        """Generate focus time section with quality assessment."""
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
        
        # Use conflict detector to find focus time windows
        focus_windows = self.conflict_detector.get_focus_time_windows(today_events, today, min_hours=2.0)
        
        if not focus_windows:
            return None
        
        # Sort by quality then duration
        quality_order = {'excellent': 0, 'good': 1, 'fair': 2, 'poor': 3}
        focus_windows.sort(key=lambda w: (quality_order.get(w['quality'], 99), -w['duration_hours']))
        
        # Build section
        lines = ["🎯 **Focus Time:**\n"]
        
        # Show best window
        best_window = focus_windows[0]
        start_time = best_window['start'].strftime('%I:%M%p').lstrip('0').lower()
        end_time = best_window['end'].strftime('%I:%M%p').lstrip('0').lower()
        duration = best_window['duration_hours']
        quality = best_window['quality']
        
        quality_emoji = {
            'excellent': '✨',
            'good': '👍',
            'fair': '✅',
            'poor': '⏰'
        }
        
        lines.append(f"  • **{start_time} - {end_time}** ({duration:.1f}h) {quality_emoji.get(quality, '')}")
        lines.append(f"    {quality.title()} time for deep work")
        
        # Show second window if available and good quality
        if len(focus_windows) > 1 and focus_windows[1]['quality'] in ['excellent', 'good']:
            second = focus_windows[1]
            start_time = second['start'].strftime('%I:%M%p').lstrip('0').lower()
            end_time = second['end'].strftime('%I:%M%p').lstrip('0').lower()
            duration = second['duration_hours']
            lines.append(f"  • {start_time} - {end_time} ({duration:.1f}h)")
        
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
