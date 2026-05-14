#!/usr/bin/env python3
"""
Intelligence Telegram Notifier

Sends intelligence recommendations via Telegram with proper formatting.
Integrates with existing Telegram infrastructure.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add common to path
sys.path.insert(0, str(Path.home() / ".openclaw/workspace/integrations/common"))

try:
    from telegram_notifier_direct import TelegramNotifier
    _telegram_available = True
except ImportError:
    _telegram_available = False
    TelegramNotifier = None


class IntelligenceTelegramNotifier:
    """Send intelligence notifications via Telegram."""
    
    def __init__(self, chat_id: str):
        """
        Initialize notifier.
        
        Args:
            chat_id: Telegram chat ID
        """
        self.chat_id = chat_id
        
        # Initialize Telegram notifier
        if _telegram_available:
            self.notifier = TelegramNotifier(telegram_id=chat_id)
        else:
            self.notifier = None
    
    def _send(self, message: str) -> bool:
        """Send message via Telegram."""
        if self.notifier:
            return self.notifier.send_text(message)
        else:
            # Fallback: print to console
            print(f"[Telegram → {self.chat_id}]")
            print(message)
            print()
            return True
    
    def send_weekly_digest(self, digest_data: Dict, user_name: str = "there"):
        """
        Send weekly digest via Telegram.
        
        Args:
            digest_data: Digest data from WeeklyDigestGenerator
            user_name: User's first name
        """
        message = self._format_weekly_digest(digest_data, user_name)
        return self._send(message)
    
    def send_task_notification(self, tasks: List[Dict], urgent_only: bool = False):
        """
        Send task extraction notification.
        
        Args:
            tasks: List of extracted tasks
            urgent_only: Only send urgent tasks
        """
        if urgent_only:
            tasks = [t for t in tasks if t['priority'] == 1]
        
        if not tasks:
            return None
        
        message = self._format_task_notification(tasks)
        return self._send(message)
    
    def send_followup_suggestion(self, suggestion: Dict):
        """
        Send single follow-up suggestion.
        
        Args:
            suggestion: Follow-up suggestion dict
        """
        message = self._format_followup(suggestion)
        return self._send(message)
    
    def send_followup_summary(self, suggestions: List[Dict]):
        """
        Send weekly follow-up summary.
        
        Args:
            suggestions: List of follow-up suggestions
        """
        message = self._format_followup_summary(suggestions)
        return self._send(message)
    
    def send_vip_email_alert(self, email: Dict):
        """
        Send VIP email alert.
        
        Args:
            email: VIP email dict from smart inbox
        """
        message = self._format_vip_email(email)
        return self._send(message)
    
    def send_vip_email_batch(self, emails: List[Dict]):
        """
        Send batch VIP email alert.
        
        Args:
            emails: List of VIP emails
        """
        message = self._format_vip_email_batch(emails)
        return self._send(message)
    
    # ========== Formatting Methods ==========
    
    def _format_weekly_digest(self, digest_data: Dict, user_name: str) -> str:
        """Format weekly digest for Telegram."""
        lines = []
        
        lines.append("📬 *Your Weekly Digest*")
        lines.append(f"Week ending {digest_data['week_ending']}")
        lines.append("")
        
        # Insights
        if digest_data.get('insights'):
            lines.append("💡 *Key Insights*")
            for insight in digest_data['insights']:
                lines.append(f"  • {insight}")
            lines.append("")
        
        # Follow-ups
        followups = digest_data.get('followups', {})
        if followups.get('count', 0) > 0:
            lines.append("👥 *People You Should Reach Out To*")
            
            for sug in followups['suggestions'][:3]:  # Top 3
                urgency_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(sug['urgency'], '⚪')
                
                name_line = f"{urgency_emoji} *{sug['name']}*"
                if sug.get('company'):
                    name_line += f" ({sug['company']})"
                lines.append(name_line)
                
                lines.append(f"  {sug['message']}")
                lines.append("")
        
        # Top relationships
        top = digest_data.get('top_relationships', {})
        if top.get('count', 0) > 0 and top.get('people'):
            lines.append("⭐ *Your Top Relationships*")
            
            for person in top['people'][:3]:  # Top 3
                total_emails = person.get('total_emails_sent', 0) + person.get('total_emails_received', 0)
                
                name_line = f"• *{person['name']}*"
                if person.get('company'):
                    name_line += f" ({person['company']})"
                lines.append(name_line)
                
                stats = []
                if total_emails > 0:
                    stats.append(f"{total_emails} emails")
                if person.get('total_meetings', 0) > 0:
                    stats.append(f"{person['total_meetings']} meetings")
                
                if stats:
                    lines.append(f"  {', '.join(stats)}")
            
            lines.append("")
        
        # Tasks
        task_data = digest_data.get('tasks', {})
        lines.append("📋 *Tasks*")
        lines.append(f"  ✅ Completed: {task_data.get('completed_this_week', 0)}")
        lines.append(f"  ⏳ Pending: {task_data.get('pending', 0)}")
        
        if task_data.get('overdue', 0) > 0:
            lines.append(f"  ⚠️ Overdue: {task_data['overdue']}")
        
        lines.append("")
        
        # Inbox
        inbox_data = digest_data.get('inbox', {})
        lines.append("📧 *Inbox*")
        lines.append(f"  📬 {inbox_data.get('total_unread', 0)} unread")
        
        if inbox_data.get('vip', 0) > 0:
            lines.append(f"  🔴 {inbox_data['vip']} VIP emails")
        
        if inbox_data.get('important', 0) > 0:
            lines.append(f"  🟡 {inbox_data['important']} important emails")
        
        return "\n".join(lines)
    
    def _format_task_notification(self, tasks: List[Dict]) -> str:
        """Format task extraction notification."""
        priority_emoji = {1: '🔴', 2: '🟡', 3: '🟢'}
        
        lines = []
        
        high_priority = [t for t in tasks if t['priority'] == 1]
        
        if high_priority:
            lines.append(f"🔴 *{len(high_priority)} Urgent Task(s) Extracted*")
        else:
            lines.append(f"📋 *{len(tasks)} Task(s) Extracted from Emails*")
        
        lines.append("")
        
        for task in tasks[:5]:  # Top 5
            emoji = priority_emoji.get(task['priority'], '⚪')
            
            lines.append(f"{emoji} {task['task_text']}")
            
            if task.get('deadline'):
                from datetime import datetime
                try:
                    deadline_dt = datetime.fromisoformat(task['deadline'])
                    lines.append(f"  ⏰ Due: {deadline_dt.strftime('%b %d')}")
                except:
                    pass
            
            lines.append(f"  From: {task['source_email_subject']}")
            lines.append("")
        
        if len(tasks) > 5:
            lines.append(f"_+ {len(tasks) - 5} more tasks_")
            lines.append("")
        
        lines.append("Tap to review and confirm tasks.")
        
        return "\n".join(lines)
    
    def _format_followup(self, suggestion: Dict) -> str:
        """Format single follow-up suggestion."""
        urgency_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(suggestion['urgency'], '⚪')
        
        lines = []
        
        lines.append(f"{urgency_emoji} *Relationship Check-in*")
        lines.append("")
        
        name_line = suggestion['name']
        if suggestion.get('company'):
            name_line += f" ({suggestion['company']})"
        lines.append(f"*{name_line}*")
        
        lines.append("")
        lines.append(suggestion['message'])
        lines.append("")
        
        lines.append(f"Importance: {suggestion['importance_score']:.0f}/100")
        lines.append(f"Days since contact: {suggestion['days_since_contact']}")
        
        return "\n".join(lines)
    
    def _format_followup_summary(self, suggestions: List[Dict]) -> str:
        """Format weekly follow-up summary."""
        lines = []
        
        lines.append("👥 *Weekly Relationship Check-in*")
        lines.append("")
        lines.append("People you should reach out to:")
        lines.append("")
        
        for sug in suggestions[:5]:  # Top 5
            urgency_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(sug['urgency'], '⚪')
            
            name_line = f"{urgency_emoji} *{sug['name']}*"
            if sug.get('company'):
                name_line += f" ({sug['company']})"
            lines.append(name_line)
            
            lines.append(f"  {sug['days_since_contact']} days since last contact")
            lines.append(f"  Importance: {sug['importance_score']:.0f}/100")
            lines.append("")
        
        if len(suggestions) > 5:
            lines.append(f"_+ {len(suggestions) - 5} more people_")
        
        return "\n".join(lines)
    
    def _format_vip_email(self, email: Dict) -> str:
        """Format single VIP email alert."""
        lines = []
        
        lines.append("🔴 *VIP Email*")
        lines.append("")
        lines.append(f"From: *{email['from_name']}*")
        lines.append(f"Subject: {email['subject']}")
        lines.append("")
        
        snippet = email.get('snippet', '')
        if snippet:
            lines.append(snippet[:150])
        
        return "\n".join(lines)
    
    def _format_vip_email_batch(self, emails: List[Dict]) -> str:
        """Format batch VIP email alert."""
        lines = []
        
        lines.append(f"🔴 *{len(emails)} VIP Email(s) Need Attention*")
        lines.append("")
        
        for email in emails[:5]:  # Top 5
            lines.append(f"• *{email['from_name']}*")
            lines.append(f"  {email['subject']}")
        
        if len(emails) > 5:
            lines.append("")
            lines.append(f"_+ {len(emails) - 5} more VIP emails_")
        
        return "\n".join(lines)


if __name__ == '__main__':
    # Test notifier
    notifier = IntelligenceTelegramNotifier(chat_id="8451730454")
    
    print("Intelligence Telegram Notifier Test")
    print("=" * 80)
    
    # Test task notification
    print("\n1. Task Notification:")
    print("-" * 80)
    
    test_tasks = [
        {
            'task_text': 'Send Q2 financials by EOD Friday',
            'priority': 1,
            'deadline': '2026-05-16T17:00:00',
            'source_email_subject': 'Q2 Review'
        },
        {
            'task_text': 'Review contract and send feedback',
            'priority': 2,
            'deadline': '2026-05-20T17:00:00',
            'source_email_subject': 'Contract Update'
        }
    ]
    
    notifier.send_task_notification(test_tasks)
    
    # Test follow-up suggestion
    print("\n2. Follow-up Suggestion:")
    print("-" * 80)
    
    test_followup = {
        'name': 'Alice Johnson',
        'company': 'Acme Corp',
        'urgency': 'high',
        'message': "Haven't contacted Alice Johnson in 32 days (important contact)",
        'importance_score': 78.5,
        'days_since_contact': 32
    }
    
    notifier.send_followup_suggestion(test_followup)
    
    # Test VIP email
    print("\n3. VIP Email Alert:")
    print("-" * 80)
    
    test_email = {
        'from_name': 'Ross Buntrock',
        'subject': 'Urgent: Q2 Review',
        'snippet': 'We need to discuss the Q2 financials ASAP before the board meeting...'
    }
    
    notifier.send_vip_email_alert(test_email)
    
    print("\n" + "=" * 80)
    print("✅ Telegram notifier ready!")
