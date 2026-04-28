#!/usr/bin/env python3
"""
Proactive Email Integration
Monitors inbox and queues notifications for important/urgent messages
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict
import logging
import re

sys.path.insert(0, str(Path(__file__).parent))
from proactive_queue import ProactiveQueue

# V8 email connector
sys.path.insert(0, str(Path(__file__).parent / "v8_meta_learning"))
try:
    from email_calendar_connector import EmailCalendarConnector
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    logging.warning("Email connector not available")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProactiveEmail:
    """Proactive email insights and urgent message detection."""
    
    URGENT_KEYWORDS = [
        'urgent', 'asap', 'emergency', 'critical', 'important',
        'deadline', 'time-sensitive', 'respond immediately',
        'action required', 'needs attention'
    ]
    
    IMPORTANT_SENDERS = [
        '@legalmensch.com',  # Work email
        'noreply@tulane.edu'  # School
    ]
    
    def __init__(self, user_id: str = 'default'):
        self.user_id = user_id
        self.queue = ProactiveQueue()
        
        # Use multi-provider email connector
        try:
            from multi_provider_email import MultiProviderEmailConnector
            self.connector = MultiProviderEmailConnector(user_id=user_id)
        except Exception as e:
            logger.warning(f"Multi-provider email init failed: {e}")
            self.connector = None
        
        # Track notified messages
        self.notified_messages = set()
    
    def check_inbox(self, hours_back: int = 1):
        """Check inbox for important unread messages."""
        if not self.connector:
            logger.warning("Email connector not available")
            return
        
        try:
            # Get recent unread messages from ALL connected accounts
            messages = self.connector.get_all_unread_messages(hours_back=hours_back)
            
            for msg in messages:
                msg_id = msg.get('id')
                if msg_id in self.notified_messages:
                    continue
                
                # Analyze importance
                importance = self._assess_importance(msg)
                
                if importance['score'] >= 7:
                    # High importance - notify
                    self._queue_important_email(msg, importance)
                    self.notified_messages.add(msg_id)
            
            logger.info(f"Checked inbox: {len(messages)} unread, {len([m for m in messages if self._assess_importance(m)['score'] >= 7])} important")
            
        except Exception as e:
            logger.error(f"Error checking inbox: {e}", exc_info=True)
    
    def _assess_importance(self, message: Dict) -> Dict:
        """
        Assess message importance on 0-10 scale.
        
        Factors:
        - Urgent keywords (+3)
        - Important sender (+2)
        - Short response time expected (+2)
        - Attachments (+1)
        - CC'd to multiple people (+1)
        """
        score = 0
        reasons = []
        
        subject = message.get('subject', '').lower()
        body = message.get('body', '').lower()
        sender = message.get('from', '').lower()
        
        # Check urgent keywords
        for keyword in self.URGENT_KEYWORDS:
            if keyword in subject or keyword in body:
                score += 3
                reasons.append(f"Contains '{keyword}'")
                break
        
        # Check important senders
        for domain in self.IMPORTANT_SENDERS:
            if domain in sender:
                score += 2
                reasons.append(f"From {domain}")
                break
        
        # Short response time
        if any(word in subject or word in body for word in ['today', 'asap', 'eod']):
            score += 2
            reasons.append("Needs quick response")
        
        # Has attachments
        if message.get('attachments'):
            score += 1
            reasons.append("Has attachments")
        
        # Multiple recipients
        if len(message.get('to', [])) > 2:
            score += 1
            reasons.append("Multiple recipients")
        
        return {
            'score': min(score, 10),
            'reasons': reasons
        }
    
    def _queue_important_email(self, message: Dict, importance: Dict):
        """Queue notification for important email."""
        sender = message.get('from', 'Unknown')
        subject = message.get('subject', '(No subject)')
        
        # Extract sender name
        sender_match = re.search(r'([^<]+)', sender)
        sender_name = sender_match.group(1).strip() if sender_match else sender
        
        priority = 2 if importance['score'] >= 8 else 3
        
        message_text = f"📧 **Important email from {sender_name}**\n\n"
        message_text += f"Subject: _{subject}_\n\n"
        
        if importance['reasons']:
            message_text += "Why: " + ", ".join(importance['reasons'][:2])
        
        self.queue.add(
            source='email',
            message=message_text,
            priority=priority,
            context={
                'message_id': message.get('id'),
                'sender': sender,
                'subject': subject,
                'importance_score': importance['score']
            }
        )
        
        logger.info(f"Queued important email: {subject}")


if __name__ == '__main__':
    # Test email integration
    email = ProactiveEmail()
    email.check_inbox(hours_back=2)
    
    stats = email.queue.stats()
    print(f"\n📊 Queue: {stats['pending']} pending, {stats['delivered']} delivered")
