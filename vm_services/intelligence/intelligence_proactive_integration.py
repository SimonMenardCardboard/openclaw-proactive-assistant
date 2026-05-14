#!/usr/bin/env python3
"""
Intelligence Layer → Proactive Messaging Integration

Integrates all intelligence features with existing proactive messaging system:
- Weekly digest → Telegram (Sunday 6 PM)
- Task notifications → Telegram with inline buttons
- Follow-up suggestions → Telegram messages
- VIP email alerts → Telegram/push notifications

Designed to work with existing:
- proactive_queue.py
- proactive_telegram_notifier.py
- proactive_daemon_v2.py
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from dynamic_relationship_scorer import DynamicRelationshipScorer
from task_extractor import TaskExtractor
from smart_inbox import SmartInbox
from weekly_digest import WeeklyDigestGenerator


class IntelligenceProactiveIntegration:
    """Bridge between intelligence layer and proactive messaging."""
    
    def __init__(self, user_id: str, telegram_chat_id: str):
        """
        Initialize integration.
        
        Args:
            user_id: User identifier
            telegram_chat_id: Telegram chat ID for notifications
        """
        self.user_id = user_id
        self.telegram_chat_id = telegram_chat_id
        
        # User-specific database
        db_path = Path.home() / f".openclaw/workspace/data/users/{user_id}/context.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize intelligence components
        self.relationships = DynamicRelationshipScorer(context_db_path=db_path)
        self.tasks = TaskExtractor(context_db_path=db_path)
        self.inbox = SmartInbox(context_db_path=db_path)
        self.digest = WeeklyDigestGenerator(context_db_path=db_path)
    
    # ========== Proactive Queue Integration ==========
    
    def queue_weekly_digest(self, user_name: str = "there"):
        """
        Queue weekly digest for Telegram delivery.
        
        Should be called: Sunday 6 PM
        """
        # Generate digest
        digest_data = self.digest.generate(user_name=user_name)
        
        # Format for Telegram
        message = self._format_digest_telegram(digest_data)
        
        # Queue for delivery
        return {
            'type': 'weekly_digest',
            'priority': 2,  # Medium priority
            'message': message,
            'delivery': 'telegram',
            'telegram_chat_id': self.telegram_chat_id
        }
    
    def queue_task_notifications(self, min_confidence: float = 0.6):
        """
        Queue task extraction notifications.
        
        Should be called: When new emails arrive
        """
        pending_tasks = self.tasks.get_pending_tasks(min_confidence=min_confidence, limit=10)
        
        if not pending_tasks:
            return []
        
        # Group by priority
        high_priority = [t for t in pending_tasks if t['priority'] == 1]
        
        notifications = []
        
        # Urgent tasks: immediate notification
        if high_priority:
            message = f"🔴 *{len(high_priority)} urgent task(s) extracted from emails*\n\n"
            
            for task in high_priority[:3]:  # Top 3
                message += f"• {task['task_text']}\n"
                if task['deadline']:
                    deadline_dt = datetime.fromisoformat(task['deadline'])
                    message += f"  ⏰ Due: {deadline_dt.strftime('%b %d')}\n"
                message += f"  From: {task['source_email_subject']}\n\n"
            
            message += f"Tap to review and confirm tasks."
            
            notifications.append({
                'type': 'task_extraction',
                'priority': 1,  # High priority
                'message': message,
                'delivery': 'telegram',
                'telegram_chat_id': self.telegram_chat_id,
                'context': {'tasks': high_priority}
            })
        
        # All pending: daily digest
        elif len(pending_tasks) >= 3:
            message = f"📋 *{len(pending_tasks)} tasks extracted from emails*\n\n"
            message += "Review and confirm in your task list."
            
            notifications.append({
                'type': 'task_summary',
                'priority': 3,  # Low priority (daily digest)
                'message': message,
                'delivery': 'telegram',
                'telegram_chat_id': self.telegram_chat_id
            })
        
        return notifications
    
    def queue_followup_suggestions(self, days_threshold: int = 21, min_importance: float = 60.0):
        """
        Queue relationship follow-up suggestions.
        
        Should be called: Monday morning (weekly check-in)
        """
        followups = self.relationships.get_follow_up_suggestions(
            min_importance=min_importance,
            days_threshold=days_threshold
        )
        
        if not followups:
            return []
        
        # Group by urgency
        high_urgency = [f for f in followups if f['urgency'] == 'high']
        medium_urgency = [f for f in followups if f['urgency'] == 'medium']
        
        notifications = []
        
        # High urgency: immediate
        if high_urgency:
            for sug in high_urgency[:2]:  # Top 2
                message = f"🔴 *Relationship Check-in*\n\n"
                message += f"{sug['message']}\n\n"
                
                if sug.get('company'):
                    message += f"Company: {sug['company']}\n"
                
                message += f"Importance: {sug['importance_score']:.0f}/100\n"
                message += f"Days since contact: {sug['days_since_contact']}"
                
                notifications.append({
                    'type': 'relationship_followup',
                    'priority': 1,
                    'message': message,
                    'delivery': 'telegram',
                    'telegram_chat_id': self.telegram_chat_id,
                    'context': sug
                })
        
        # Medium urgency: weekly summary
        if medium_urgency and not high_urgency:
            message = f"👥 *Weekly Relationship Check-in*\n\n"
            message += f"People you should reach out to:\n\n"
            
            for sug in medium_urgency[:3]:  # Top 3
                message += f"• {sug['name']}"
                if sug.get('company'):
                    message += f" ({sug['company']})"
                message += f"\n  {sug['days_since_contact']} days since last contact\n"
            
            notifications.append({
                'type': 'relationship_summary',
                'priority': 2,
                'message': message,
                'delivery': 'telegram',
                'telegram_chat_id': self.telegram_chat_id
            })
        
        return notifications
    
    def queue_vip_email_alerts(self):
        """
        Queue VIP email alerts.
        
        Should be called: When new emails arrive (real-time)
        """
        # Get VIP unread emails
        vip_emails = self.inbox.get_inbox(
            priority_level='vip',
            unread_only=True,
            limit=5
        )
        
        if not vip_emails:
            return []
        
        notifications = []
        
        # Batch VIP emails (don't spam for each one)
        if len(vip_emails) == 1:
            email = vip_emails[0]
            message = f"🔴 *VIP Email*\n\n"
            message += f"From: {email['from_name']}\n"
            message += f"Subject: {email['subject']}\n\n"
            message += email['snippet'][:100]
            
            notifications.append({
                'type': 'vip_email',
                'priority': 1,
                'message': message,
                'delivery': 'push',  # Push notification for real-time
                'telegram_chat_id': self.telegram_chat_id
            })
        
        elif len(vip_emails) > 1:
            message = f"🔴 *{len(vip_emails)} VIP emails need attention*\n\n"
            
            for email in vip_emails[:3]:  # Top 3
                message += f"• {email['from_name']}: {email['subject']}\n"
            
            if len(vip_emails) > 3:
                message += f"\n+ {len(vip_emails) - 3} more"
            
            notifications.append({
                'type': 'vip_email_batch',
                'priority': 1,
                'message': message,
                'delivery': 'telegram',
                'telegram_chat_id': self.telegram_chat_id
            })
        
        return notifications
    
    # ========== Telegram Formatting ==========
    
    def _format_digest_telegram(self, digest_data: Dict) -> str:
        """Format weekly digest for Telegram."""
        lines = []
        
        lines.append("📬 *Your Weekly Digest*")
        lines.append(f"Week ending {digest_data['week_ending']}\n")
        
        # Insights
        if digest_data['insights']:
            lines.append("💡 *Key Insights*")
            for insight in digest_data['insights']:
                lines.append(f"  • {insight}")
            lines.append("")
        
        # Follow-ups
        followups = digest_data['followups']
        if followups['count'] > 0:
            lines.append("👥 *People You Should Reach Out To*")
            
            for sug in followups['suggestions'][:3]:  # Top 3
                urgency_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(sug['urgency'], '⚪')
                
                lines.append(f"{urgency_emoji} {sug['name']}")
                if sug.get('company'):
                    lines.append(f"    {sug['company']}")
                lines.append(f"    {sug['message']}")
            
            lines.append("")
        
        # Top relationships
        top = digest_data['top_relationships']
        if top['count'] > 0:
            lines.append("⭐ *Your Top Relationships*")
            
            for person in top['people'][:3]:  # Top 3
                total_emails = person['total_emails_sent'] + person['total_emails_received']
                
                lines.append(f"• {person['name']}")
                if person.get('company'):
                    lines.append(f"    {person['company']}")
                
                parts = [f"{total_emails} emails"]
                if person['total_meetings'] > 0:
                    parts.append(f"{person['total_meetings']} meetings")
                
                lines.append(f"    {', '.join(parts)}")
            
            lines.append("")
        
        # Tasks
        task_data = digest_data['tasks']
        lines.append("📋 *Tasks*")
        lines.append(f"  ✅ Completed: {task_data['completed_this_week']}")
        lines.append(f"  ⏳ Pending: {task_data['pending']}")
        
        if task_data['overdue'] > 0:
            lines.append(f"  ⚠️ Overdue: {task_data['overdue']}")
        
        lines.append("")
        
        # Inbox
        inbox_data = digest_data['inbox']
        lines.append("📧 *Inbox*")
        lines.append(f"  📬 {inbox_data['total_unread']} unread")
        
        if inbox_data['vip'] > 0:
            lines.append(f"  🔴 {inbox_data['vip']} VIP")
        
        if inbox_data['important'] > 0:
            lines.append(f"  🟡 {inbox_data['important']} important")
        
        return "\n".join(lines)


# ========== Integration with Existing Proactive System ==========

def add_intelligence_to_proactive_queue(user_id: str, telegram_chat_id: str):
    """
    Add intelligence recommendations to proactive queue.
    
    Call this from proactive daemon cron jobs.
    """
    integration = IntelligenceProactiveIntegration(user_id, telegram_chat_id)
    
    # Import existing proactive queue
    import sys
    sys.path.insert(0, str(Path.home() / ".openclaw/workspace/integrations/intelligence"))
    from proactive_queue import queue_recommendation
    
    # Queue follow-up suggestions (Monday morning)
    if datetime.now().weekday() == 0:  # Monday
        followups = integration.queue_followup_suggestions()
        for notification in followups:
            queue_recommendation(
                type=notification['type'],
                priority=notification['priority'],
                message=notification['message'],
                context=notification.get('context', {})
            )
    
    # Queue weekly digest (Sunday evening)
    if datetime.now().weekday() == 6 and datetime.now().hour >= 18:  # Sunday 6 PM
        digest = integration.queue_weekly_digest(user_name="Simon")
        queue_recommendation(
            type=digest['type'],
            priority=digest['priority'],
            message=digest['message'],
            context={}
        )
    
    # Queue task notifications (when new emails)
    # (This would be triggered by email webhook, not cron)
    
    # Queue VIP email alerts (when new emails)
    # (This would be triggered by email webhook, not cron)


if __name__ == '__main__':
    # Test integration
    integration = IntelligenceProactiveIntegration(
        user_id="test_user",
        telegram_chat_id="8451730454"
    )
    
    print("Intelligence → Proactive Integration Test")
    print("=" * 80)
    
    # Test weekly digest
    print("\n1. Weekly Digest (Telegram format):")
    print("-" * 80)
    digest = integration.queue_weekly_digest(user_name="Simon")
    print(digest['message'])
    print()
    
    # Test follow-up suggestions
    print("\n2. Follow-up Suggestions:")
    print("-" * 80)
    followups = integration.queue_followup_suggestions(days_threshold=14)
    
    if followups:
        for notification in followups:
            print(f"Type: {notification['type']}")
            print(f"Priority: {notification['priority']}")
            print(f"Message:\n{notification['message']}")
            print()
    else:
        print("No follow-ups needed")
    
    # Test task notifications
    print("\n3. Task Notifications:")
    print("-" * 80)
    tasks = integration.queue_task_notifications()
    
    if tasks:
        for notification in tasks:
            print(f"Type: {notification['type']}")
            print(f"Priority: {notification['priority']}")
            print(f"Message:\n{notification['message']}")
            print()
    else:
        print("No pending tasks")
    
    print("\n" + "=" * 80)
    print("✅ Integration ready for proactive daemon!")
