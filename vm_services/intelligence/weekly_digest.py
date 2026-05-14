#!/usr/bin/env python3
"""
Weekly Digest Generator - Transmogrifier MVP

Combines relationship intelligence, task tracking, and inbox insights
into a weekly summary email/push notification.

Sends every Sunday at 6 PM with:
- People you should reach out to (relationship follow-ups)
- Task burndown (what got done, what's pending)
- Inbox insights (email volume, response time)
- Calendar preview (upcoming week)
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import json

class WeeklyDigestGenerator:
    """Generate weekly digest for users."""
    
    def __init__(self, context_db_path: Optional[Path] = None):
        """
        Initialize digest generator.
        
        Args:
            context_db_path: Path to user's context database
        """
        if context_db_path is None:
            context_db_path = Path.home() / ".openclaw/workspace/integrations/intelligence/data/context.db"
        
        self.db_path = Path(context_db_path)
    
    def generate(self, user_name: str = "there") -> Dict:
        """
        Generate weekly digest.
        
        Args:
            user_name: User's first name for personalization
            
        Returns:
            Digest data dict
        """
        # Import components
        try:
            from dynamic_relationship_scorer import DynamicRelationshipScorer
            from task_extractor import TaskExtractor
            from smart_inbox import SmartInbox
            
            scorer = DynamicRelationshipScorer(context_db_path=self.db_path)
            tasks = TaskExtractor(context_db_path=self.db_path)
            inbox = SmartInbox(context_db_path=self.db_path)
        except Exception as e:
            print(f"Error loading components: {e}")
            return {}
        
        # 1. Relationship Check-ins
        followups = scorer.get_follow_up_suggestions(
            min_importance=50.0,
            days_threshold=21  # 3 weeks
        )
        
        top_relationships = scorer.get_top_relationships(limit=5)
        
        # 2. Task Summary
        pending_tasks = tasks.get_pending_tasks(min_confidence=0.5, limit=50)
        
        # Count completed tasks this week
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        week_ago = datetime.now() - timedelta(days=7)
        
        cursor.execute('''
            SELECT COUNT(*) FROM extracted_tasks
            WHERE status = 'completed'
              AND completed_at >= ?
        ''', (week_ago,))
        
        completed_count = cursor.fetchone()[0]
        
        # Count overdue tasks
        cursor.execute('''
            SELECT COUNT(*) FROM extracted_tasks
            WHERE status IN ('pending', 'confirmed')
              AND deadline IS NOT NULL
              AND deadline < ?
        ''', (datetime.now(),))
        
        overdue_count = cursor.fetchone()[0]
        
        conn.close()
        
        # 3. Inbox Insights
        inbox_stats = inbox.get_stats()
        
        # 4. Calendar Preview (placeholder - needs Calendar API integration)
        calendar_preview = {
            'upcoming_meetings': [],
            'total_hours': 0,
            'busiest_day': None
        }
        
        # Assemble digest
        digest = {
            'user_name': user_name,
            'generated_at': datetime.now().isoformat(),
            'week_ending': datetime.now().strftime('%B %d, %Y'),
            
            # Relationships
            'followups': {
                'count': len(followups),
                'suggestions': followups[:5]  # Top 5
            },
            'top_relationships': {
                'count': len(top_relationships),
                'people': top_relationships
            },
            
            # Tasks
            'tasks': {
                'completed_this_week': completed_count,
                'pending': len(pending_tasks),
                'overdue': overdue_count,
                'pending_tasks': pending_tasks[:5]  # Top 5
            },
            
            # Inbox
            'inbox': {
                'total_unread': inbox_stats['unread_emails'],
                'vip': inbox_stats['vip'],
                'important': inbox_stats['important'],
                'normal': inbox_stats['normal']
            },
            
            # Calendar (placeholder)
            'calendar': calendar_preview,
            
            # Insights
            'insights': self._generate_insights(
                followups=followups,
                completed_count=completed_count,
                inbox_stats=inbox_stats
            )
        }
        
        return digest
    
    def _generate_insights(self, followups: List, completed_count: int, inbox_stats: Dict) -> List[str]:
        """Generate personalized insights."""
        insights = []
        
        # Relationship insights
        if len(followups) > 0:
            high_priority = [f for f in followups if f['urgency'] == 'high']
            if high_priority:
                insights.append(f"You have {len(high_priority)} important relationship(s) that need attention")
        
        # Task insights
        if completed_count > 0:
            insights.append(f"Great job! You completed {completed_count} task(s) this week")
        
        # Inbox insights
        vip_unread = inbox_stats.get('vip', 0)
        if vip_unread > 0:
            insights.append(f"You have {vip_unread} unread VIP email(s) that need attention")
        
        return insights
    
    def format_email(self, digest: Dict) -> str:
        """
        Format digest as HTML email.
        
        Args:
            digest: Digest data
            
        Returns:
            HTML email content
        """
        html = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            font-size: 18px;
        }}
        .section {{
            margin: 20px 0;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }}
        .stat {{
            display: inline-block;
            margin: 10px 15px 10px 0;
            padding: 10px 15px;
            background: white;
            border-radius: 6px;
            font-weight: 600;
        }}
        .item {{
            margin: 10px 0;
            padding: 10px;
            background: white;
            border-left: 4px solid #3498db;
            border-radius: 4px;
        }}
        .urgent {{ border-left-color: #e74c3c; }}
        .medium {{ border-left-color: #f39c12; }}
        .low {{ border-left-color: #95a5a6; }}
        .insight {{
            padding: 12px;
            background: #e8f4f8;
            border-left: 4px solid #3498db;
            margin: 10px 0;
            border-radius: 4px;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #7f8c8d;
            font-size: 12px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <h1>📬 Your Weekly Digest</h1>
    <p>Hey {digest['user_name']},</p>
    <p>Here's your weekly summary for the week ending {digest['week_ending']}.</p>
'''
        
        # Insights
        if digest['insights']:
            html += '<div class="section">'
            html += '<h2>💡 Key Insights</h2>'
            for insight in digest['insights']:
                html += f'<div class="insight">💡 {insight}</div>'
            html += '</div>'
        
        # Relationship Follow-ups
        followups = digest['followups']
        if followups['count'] > 0:
            html += '<div class="section">'
            html += '<h2>👥 People You Should Reach Out To</h2>'
            
            for sug in followups['suggestions']:
                urgency_class = sug['urgency']
                urgency_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(urgency_class, '⚪')
                
                html += f'<div class="item {urgency_class}">'
                html += f'<strong>{urgency_emoji} {sug["name"]}</strong>'
                
                if sug.get('company'):
                    html += f' <span style="color: #7f8c8d;">({sug["company"]})</span>'
                
                html += f'<br>{sug["message"]}'
                html += f'<br><small style="color: #7f8c8d;">Importance: {sug["importance_score"]:.0f}/100</small>'
                html += '</div>'
            
            if followups['count'] > len(followups['suggestions']):
                html += f'<p><em>+ {followups["count"] - len(followups["suggestions"])} more</em></p>'
            
            html += '</div>'
        else:
            html += '<div class="section">'
            html += '<h2>👥 Relationships</h2>'
            html += '<p>✅ You\'re keeping up with all your important contacts! Great job.</p>'
            html += '</div>'
        
        # Top Relationships
        top = digest['top_relationships']
        if top['count'] > 0:
            html += '<div class="section">'
            html += '<h2>⭐ Your Top Relationships This Week</h2>'
            
            for person in top['people'][:3]:  # Top 3
                total_emails = person['total_emails_sent'] + person['total_emails_received']
                
                html += f'<div class="item">'
                html += f'<strong>{person["name"]}</strong>'
                
                if person.get('company'):
                    html += f' <span style="color: #7f8c8d;">({person["company"]})</span>'
                
                html += f'<br>{total_emails} emails'
                
                if person['total_meetings'] > 0:
                    html += f', {person["total_meetings"]} meetings'
                
                html += f'<br><small style="color: #7f8c8d;">Score: {person["importance_score"]:.0f}/100</small>'
                html += '</div>'
            
            html += '</div>'
        
        # Tasks
        task_data = digest['tasks']
        html += '<div class="section">'
        html += '<h2>📋 Tasks</h2>'
        
        html += f'<div class="stat">✅ {task_data["completed_this_week"]} completed</div>'
        html += f'<div class="stat">⏳ {task_data["pending"]} pending</div>'
        
        if task_data['overdue'] > 0:
            html += f'<div class="stat" style="background: #fef5f5; color: #e74c3c;">⚠️ {task_data["overdue"]} overdue</div>'
        
        if task_data['pending_tasks']:
            html += '<h3 style="margin-top: 20px;">Top Pending Tasks:</h3>'
            
            for task in task_data['pending_tasks'][:3]:
                priority_emoji = {1: '🔴', 2: '🟡', 3: '🟢'}.get(task['priority'], '⚪')
                
                html += f'<div class="item">'
                html += f'{priority_emoji} {task["task_text"]}'
                html += f'<br><small style="color: #7f8c8d;">From: {task["source_email_subject"]}</small>'
                
                if task['deadline']:
                    deadline_dt = datetime.fromisoformat(task['deadline'])
                    html += f'<br><small style="color: #e74c3c;">⏰ Due: {deadline_dt.strftime("%b %d")}</small>'
                
                html += '</div>'
        
        html += '</div>'
        
        # Inbox
        inbox_data = digest['inbox']
        html += '<div class="section">'
        html += '<h2>📧 Inbox</h2>'
        
        html += f'<div class="stat">📬 {inbox_data["total_unread"]} unread</div>'
        
        if inbox_data['vip'] > 0:
            html += f'<div class="stat" style="background: #fef5f5; color: #e74c3c;">🔴 {inbox_data["vip"]} VIP</div>'
        
        if inbox_data['important'] > 0:
            html += f'<div class="stat">🟡 {inbox_data["important"]} important</div>'
        
        html += '</div>'
        
        # Footer
        html += '''
    <div class="footer">
        <p>Transmogrifier • Your AI efficiency analyst</p>
        <p>Sent Sunday at 6 PM • <a href="#">Update preferences</a> • <a href="#">Unsubscribe</a></p>
    </div>
</body>
</html>
'''
        
        return html
    
    def format_text(self, digest: Dict) -> str:
        """
        Format digest as plain text.
        
        Args:
            digest: Digest data
            
        Returns:
            Plain text email content
        """
        lines = []
        
        lines.append("📬 YOUR WEEKLY DIGEST")
        lines.append("=" * 60)
        lines.append(f"Week ending {digest['week_ending']}")
        lines.append("")
        lines.append(f"Hey {digest['user_name']},")
        lines.append("")
        
        # Insights
        if digest['insights']:
            lines.append("💡 KEY INSIGHTS")
            lines.append("-" * 60)
            for insight in digest['insights']:
                lines.append(f"  • {insight}")
            lines.append("")
        
        # Follow-ups
        followups = digest['followups']
        if followups['count'] > 0:
            lines.append("👥 PEOPLE YOU SHOULD REACH OUT TO")
            lines.append("-" * 60)
            
            for sug in followups['suggestions']:
                urgency_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(sug['urgency'], '⚪')
                
                lines.append(f"{urgency_emoji} {sug['name']}" + 
                           (f" ({sug['company']})" if sug.get('company') else ""))
                lines.append(f"   {sug['message']}")
                lines.append(f"   Importance: {sug['importance_score']:.0f}/100")
                lines.append("")
        else:
            lines.append("👥 RELATIONSHIPS")
            lines.append("-" * 60)
            lines.append("✅ You're keeping up with all your important contacts!")
            lines.append("")
        
        # Top relationships
        top = digest['top_relationships']
        if top['count'] > 0:
            lines.append("⭐ YOUR TOP RELATIONSHIPS THIS WEEK")
            lines.append("-" * 60)
            
            for person in top['people'][:3]:
                total_emails = person['total_emails_sent'] + person['total_emails_received']
                
                lines.append(f"{person['name']}" + 
                           (f" ({person['company']})" if person.get('company') else ""))
                
                parts = [f"{total_emails} emails"]
                if person['total_meetings'] > 0:
                    parts.append(f"{person['total_meetings']} meetings")
                
                lines.append(f"   {', '.join(parts)}")
                lines.append(f"   Score: {person['importance_score']:.0f}/100")
                lines.append("")
        
        # Tasks
        task_data = digest['tasks']
        lines.append("📋 TASKS")
        lines.append("-" * 60)
        lines.append(f"✅ Completed this week: {task_data['completed_this_week']}")
        lines.append(f"⏳ Pending: {task_data['pending']}")
        
        if task_data['overdue'] > 0:
            lines.append(f"⚠️  Overdue: {task_data['overdue']}")
        
        if task_data['pending_tasks']:
            lines.append("")
            lines.append("Top pending tasks:")
            
            for task in task_data['pending_tasks'][:3]:
                priority_emoji = {1: '🔴', 2: '🟡', 3: '🟢'}.get(task['priority'], '⚪')
                
                lines.append(f"{priority_emoji} {task['task_text']}")
                lines.append(f"   From: {task['source_email_subject']}")
                
                if task['deadline']:
                    deadline_dt = datetime.fromisoformat(task['deadline'])
                    lines.append(f"   Due: {deadline_dt.strftime('%b %d')}")
                
                lines.append("")
        
        # Inbox
        inbox_data = digest['inbox']
        lines.append("📧 INBOX")
        lines.append("-" * 60)
        lines.append(f"📬 {inbox_data['total_unread']} unread")
        
        if inbox_data['vip'] > 0:
            lines.append(f"🔴 {inbox_data['vip']} VIP emails need attention")
        
        if inbox_data['important'] > 0:
            lines.append(f"🟡 {inbox_data['important']} important emails")
        
        lines.append("")
        lines.append("-" * 60)
        lines.append("Transmogrifier • Your AI efficiency analyst")
        lines.append("Sent Sunday at 6 PM")
        
        return "\n".join(lines)


def send_digest_email(to_email: str, digest_html: str, digest_text: str):
    """
    Send digest via email.
    
    Args:
        to_email: Recipient email
        digest_html: HTML content
        digest_text: Plain text content
    """
    # TODO: Implement email sending via SendGrid/AWS SES
    print(f"Would send digest to: {to_email}")
    print("(Email sending not yet implemented)")


def send_digest_push(user_id: str, digest_summary: str):
    """
    Send digest summary via push notification.
    
    Args:
        user_id: User ID
        digest_summary: Brief summary for notification
    """
    # TODO: Implement push via FCM/APNs
    print(f"Would send push to user: {user_id}")
    print(f"Message: {digest_summary}")


if __name__ == '__main__':
    # Test digest generator
    generator = WeeklyDigestGenerator()
    
    print("Weekly Digest Generator Test")
    print("=" * 80)
    
    # Generate digest
    print("\n1. Generating digest...")
    digest = generator.generate(user_name="Simon")
    
    print(f"   Generated at: {digest['generated_at']}")
    print(f"   Follow-ups: {digest['followups']['count']}")
    print(f"   Tasks completed: {digest['tasks']['completed_this_week']}")
    print(f"   Unread emails: {digest['inbox']['total_unread']}")
    
    # Format as text
    print("\n2. Plain Text Version:")
    print("-" * 80)
    text_digest = generator.format_text(digest)
    print(text_digest)
    
    # Save HTML version
    html_digest = generator.format_email(digest)
    
    output_file = Path.home() / ".openclaw/workspace/integrations/intelligence/data/weekly_digest_preview.html"
    with open(output_file, 'w') as f:
        f.write(html_digest)
    
    print(f"\n3. HTML version saved to:")
    print(f"   {output_file}")
    print(f"\n   Open in browser to preview!")
