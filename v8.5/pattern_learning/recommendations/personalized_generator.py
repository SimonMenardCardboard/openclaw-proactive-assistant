#!/usr/bin/env python3
"""
V8.5 Personalized Recommendation Generator

Generate recommendations tailored to individual user patterns.
This replaces generic NLU with user-specific intelligence.

Key Features:
- Pattern-based priority scoring
- Context-aware messaging
- Timing optimization
- Personalized actions
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

class PersonalizedRecommendationGenerator:
    """
    Generate recommendations tailored to individual user patterns.
    
    Core Methods:
    - generate_email_recommendation(): Email-specific recs
    - generate_meeting_recommendation(): Calendar-specific recs
    - generate_task_recommendation(): Task-specific recs
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        from pattern_learning.pattern_analyzer import UserPatternAnalyzer
        self.pattern_analyzer = UserPatternAnalyzer(db_path)
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # ========================================================================
    # Email Recommendations
    # ========================================================================
    
    def generate_email_recommendation(self, user_id: str, email: Dict) -> Dict:
        """
        Generate personalized email recommendation.
        
        Args:
            email: {
                'id': 'email_123',
                'sender': 'boss@company.com',
                'subject': 'Q2 Budget Review',
                'received_at': datetime,
                'preview': '...'
            }
        
        Returns:
        {
            "recommendation_id": "rec_456",
            "type": "email",
            "priority": 0.85,
            "urgency": "high",
            "title": "🔴 HIGH PRIORITY: ...",
            "message": "...",
            "reasoning": {...},
            "actions": [...]
        }
        """
        # Get user patterns
        patterns = self.pattern_analyzer.get_patterns(user_id)
        
        if not patterns:
            # No patterns yet - use generic recommendation
            return self._generate_generic_email_rec(email)
        
        email_patterns = patterns['email_patterns']
        calendar_patterns = patterns['calendar_patterns']
        work_patterns = patterns['work_patterns']
        
        # Calculate priority
        priority = self._calculate_email_priority(email, email_patterns)
        
        # Determine urgency
        urgency = 'high' if priority > 0.7 else 'medium' if priority > 0.4 else 'low'
        
        # Generate personalized title
        title = self._generate_email_title(email, email_patterns, priority)
        
        # Generate personalized message
        message = self._generate_email_message(email, email_patterns, calendar_patterns, priority)
        
        # Generate reasoning
        reasoning = self._explain_email_importance(email, email_patterns)
        
        # Generate personalized actions
        actions = self._generate_email_actions(email, email_patterns, calendar_patterns)
        
        return {
            "recommendation_id": f"rec_{email['id']}_{int(datetime.now().timestamp())}",
            "type": "email",
            "priority": round(priority, 2),
            "urgency": urgency,
            "title": title,
            "message": message,
            "reasoning": reasoning,
            "actions": actions,
            "metadata": {
                "email_id": email['id'],
                "sender": email['sender'],
                "subject": email['subject']
            }
        }
    
    def _calculate_email_priority(self, email: Dict, email_patterns: Dict) -> float:
        """
        Calculate user-specific priority for this email.
        """
        score = 0.5  # baseline
        
        sender = email.get('sender', '').lower()
        subject = email.get('subject', '').upper()
        
        # VIP sender?
        vip_senders = [s.lower() for s in email_patterns.get('vip_senders', [])]
        if sender in vip_senders:
            score += 0.3
        
        # Urgent keywords?
        urgent_keywords = email_patterns.get('urgent_keywords', [])
        if any(kw in subject for kw in urgent_keywords):
            score += 0.2
        
        # Ignored sender?
        ignored_senders = [s.lower() for s in email_patterns.get('ignored_senders', [])]
        if sender in ignored_senders:
            score = 0.1
        
        # Fast responder to this sender?
        response_times = email_patterns.get('response_time_by_sender', {})
        if sender in response_times and response_times[sender] < 2.0:  # < 2 hours
            score += 0.15
        
        return min(1.0, max(0.0, score))
    
    def _generate_email_title(self, email: Dict, email_patterns: Dict, priority: float) -> str:
        """
        Generate personalized title with priority indicator.
        """
        sender = email.get('sender', 'Unknown')
        subject = email.get('subject', 'No subject')
        
        # Priority emoji
        if priority > 0.7:
            emoji = "🔴"
            label = "HIGH PRIORITY"
        elif priority > 0.4:
            emoji = "🟡"
            label = "MEDIUM PRIORITY"
        else:
            emoji = "⚪"
            label = "LOW PRIORITY"
        
        # Check if VIP
        is_vip = sender.lower() in [s.lower() for s in email_patterns.get('vip_senders', [])]
        vip_label = " (VIP)" if is_vip else ""
        
        return f"{emoji} {label}: {subject}{vip_label}"
    
    def _generate_email_message(self, email: Dict, email_patterns: Dict, calendar_patterns: Dict, priority: float) -> str:
        """
        Generate personalized message explaining context.
        """
        sender = email.get('sender', 'Unknown')
        preview = email.get('preview', '')[:100]
        
        message = f"Email from {sender}\n\n"
        message += f"{preview}...\n\n"
        
        # Add pattern insights
        vip_senders = [s.lower() for s in email_patterns.get('vip_senders', [])]
        response_times = email_patterns.get('response_time_by_sender', {})
        
        if sender.lower() in vip_senders:
            avg_time = response_times.get(sender.lower(), 0)
            message += f"💡 Pattern: You usually respond to this sender within {avg_time:.1f} hours\n"
        
        # Check calendar for context
        # (Simplified - would integrate with real calendar)
        message += f"\n📅 You have meetings at 2 PM and 4 PM today"
        
        return message
    
    def _explain_email_importance(self, email: Dict, email_patterns: Dict) -> Dict:
        """
        Explain WHY this email is important to THIS user.
        """
        reasons = []
        
        sender = email.get('sender', '').lower()
        subject = email.get('subject', '').upper()
        
        # VIP sender?
        vip_senders = [s.lower() for s in email_patterns.get('vip_senders', [])]
        if sender in vip_senders:
            reasons.append("VIP sender - you always respond quickly")
        
        # Urgent keywords?
        urgent_keywords = email_patterns.get('urgent_keywords', [])
        matched_keywords = [kw for kw in urgent_keywords if kw in subject]
        if matched_keywords:
            reasons.append(f"Urgent keywords: {', '.join(matched_keywords)}")
        
        # Response time pattern
        response_times = email_patterns.get('response_time_by_sender', {})
        if sender in response_times:
            avg_time = response_times[sender]
            reasons.append(f"Your average response time: {avg_time:.1f} hours")
        
        return {
            "why_important": reasons,
            "suggested_timing": self._suggest_email_timing(email_patterns),
            "context_aware": True
        }
    
    def _suggest_email_timing(self, email_patterns: Dict) -> str:
        """
        Suggest when user should respond based on patterns.
        """
        is_batch = email_patterns.get('batch_processor', False)
        peak_hours = email_patterns.get('peak_email_hours', [])
        
        if is_batch and peak_hours:
            return f"Suggested: Process during your peak email hours ({peak_hours[0]})"
        else:
            return "Suggested: Respond within 1 hour"
    
    def _generate_email_actions(self, email: Dict, email_patterns: Dict, calendar_patterns: Dict) -> List[Dict]:
        """
        Generate personalized action buttons.
        """
        actions = []
        
        # Quick reply (for VIP senders)
        sender = email.get('sender', '').lower()
        vip_senders = [s.lower() for s in email_patterns.get('vip_senders', [])]
        
        if sender in vip_senders:
            actions.append({
                "type": "quick_reply",
                "label": "📧 Reply Now",
                "action": "draft_reply",
                "reason": "VIP sender - fast response recommended"
            })
        else:
            actions.append({
                "type": "reply",
                "label": "Reply",
                "action": "open_email"
            })
        
        # Snooze (with smart timing)
        snooze_time = "1 hour" if sender in vip_senders else "3 hours"
        actions.append({
            "type": "snooze",
            "label": f"⏰ Snooze {snooze_time}",
            "action": f"snooze_{snooze_time.replace(' ', '_')}"
        })
        
        # Archive (for non-urgent)
        actions.append({
            "type": "archive",
            "label": "📁 Archive",
            "action": "archive_email"
        })
        
        return actions
    
    def _generate_generic_email_rec(self, email: Dict) -> Dict:
        """
        Generate generic recommendation (cold start - no patterns yet).
        """
        return {
            "recommendation_id": f"rec_{email['id']}_{int(datetime.now().timestamp())}",
            "type": "email",
            "priority": 0.5,
            "urgency": "medium",
            "title": f"New email from {email.get('sender', 'Unknown')}",
            "message": email.get('subject', 'No subject'),
            "reasoning": {
                "why_important": ["New email (learning your patterns...)"],
                "suggested_timing": "Process when convenient",
                "context_aware": False
            },
            "actions": [
                {"type": "open", "label": "Open", "action": "open_email"},
                {"type": "snooze", "label": "Snooze", "action": "snooze_1_hour"}
            ],
            "metadata": {
                "email_id": email['id'],
                "sender": email['sender'],
                "subject": email.get('subject', '')
            }
        }
    
    # ========================================================================
    # Meeting Recommendations
    # ========================================================================
    
    def generate_meeting_recommendation(self, user_id: str, meeting: Dict) -> Dict:
        """
        Generate personalized meeting recommendation.
        
        Args:
            meeting: {
                'id': 'meeting_123',
                'title': 'Q2 Planning',
                'start_time': datetime,
                'attendees': [...],
                'organizer': '...'
            }
        """
        patterns = self.pattern_analyzer.get_patterns(user_id)
        
        if not patterns:
            return self._generate_generic_meeting_rec(meeting)
        
        calendar_patterns = patterns['calendar_patterns']
        
        # Calculate priority
        priority = self._calculate_meeting_priority(meeting, calendar_patterns)
        
        # Check if user tends to skip/be late
        title = meeting.get('title', 'Untitled meeting')
        late_meetings = calendar_patterns.get('late_meetings', [])
        skip_meetings = calendar_patterns.get('skip_meetings', [])
        
        warning = ""
        if title in late_meetings:
            warning = "⚠️ You're often late to this meeting"
        elif title in skip_meetings:
            warning = "⚠️ You often skip this meeting"
        
        # Prep time needed
        prep_time = calendar_patterns.get('prep_time_needed_minutes', 10)
        
        return {
            "recommendation_id": f"rec_{meeting['id']}_{int(datetime.now().timestamp())}",
            "type": "meeting",
            "priority": round(priority, 2),
            "urgency": "high" if priority > 0.7 else "medium",
            "title": f"📅 Upcoming: {title}",
            "message": f"{warning}\n\n💡 Prep time needed: {prep_time} min\n\nStarts in 15 minutes",
            "reasoning": {
                "why_important": self._explain_meeting_importance(meeting, calendar_patterns),
                "prep_time_needed": prep_time
            },
            "actions": [
                {"type": "join", "label": "Join Now", "action": "join_meeting"},
                {"type": "prep", "label": "View Agenda", "action": "view_agenda"}
            ],
            "metadata": {
                "meeting_id": meeting['id'],
                "title": title
            }
        }
    
    def _calculate_meeting_priority(self, meeting: Dict, calendar_patterns: Dict) -> float:
        """
        Calculate user-specific meeting priority.
        """
        title = meeting.get('title', '')
        meeting_importance = calendar_patterns.get('meeting_type_importance', {})
        
        # Check if we have importance score for this meeting type
        for meeting_type, importance in meeting_importance.items():
            if meeting_type.lower() in title.lower():
                return importance
        
        # Default priority
        return 0.6
    
    def _explain_meeting_importance(self, meeting: Dict, calendar_patterns: Dict) -> List[str]:
        """
        Explain why meeting is important.
        """
        reasons = []
        
        title = meeting.get('title', '')
        skip_meetings = calendar_patterns.get('skip_meetings', [])
        
        if title not in skip_meetings:
            reasons.append("You usually attend this meeting")
        
        organizer = meeting.get('organizer', '')
        if organizer:
            reasons.append(f"Organized by {organizer}")
        
        return reasons
    
    def _generate_generic_meeting_rec(self, meeting: Dict) -> Dict:
        """Generic meeting recommendation (cold start)."""
        return {
            "recommendation_id": f"rec_{meeting['id']}_{int(datetime.now().timestamp())}",
            "type": "meeting",
            "priority": 0.6,
            "urgency": "medium",
            "title": f"📅 Upcoming: {meeting.get('title', 'Untitled')}",
            "message": "Meeting starts soon",
            "reasoning": {"why_important": ["Scheduled meeting"]},
            "actions": [
                {"type": "join", "label": "Join", "action": "join_meeting"}
            ],
            "metadata": {"meeting_id": meeting['id']}
        }


if __name__ == '__main__':
    # Test personalized generator
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'pattern_learning.db'
    
    generator = PersonalizedRecommendationGenerator(db_path)
    
    print("Testing Personalized Recommendation Generator\n")
    
    # Test email recommendation
    print("1. Email Recommendation:")
    email = {
        'id': 'email_123',
        'sender': 'boss@company.com',
        'subject': 'URGENT: Q2 Budget Review',
        'received_at': datetime.now(),
        'preview': 'We need to finalize the Q2 budget by EOD...'
    }
    
    rec = generator.generate_email_recommendation('test_user', email)
    print(json.dumps(rec, indent=2, default=str))
    
    # Test meeting recommendation
    print("\n2. Meeting Recommendation:")
    meeting = {
        'id': 'meeting_456',
        'title': '1:1 with Manager',
        'start_time': datetime.now() + timedelta(minutes=15),
        'organizer': 'manager@company.com'
    }
    
    rec = generator.generate_meeting_recommendation('test_user', meeting)
    print(json.dumps(rec, indent=2, default=str))
