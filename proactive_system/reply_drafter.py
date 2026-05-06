#!/usr/bin/env python3
"""
Reply Drafter (v1)

Suggests replies to important emails based on:
- Contact relationship history
- Email content analysis
- Previous response patterns
- Context from calendar/tasks

Simple rule-based v1 - can be enhanced with LLM later.
"""

import sys
import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import logging

sys.path.insert(0, str(Path(__file__).parent))

from context_database import ContextDatabase
from universal_email_api import UniversalAccountManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReplyDrafter:
    """Generate suggested replies to important emails."""
    
    # Common question patterns
    QUESTION_PATTERNS = {
        'meeting': r'(can we meet|schedule|available|calendar|coffee)',
        'status': r'(status|update|progress|how.*going)',
        'approval': r'(approve|sign off|review|feedback|thoughts)',
        'information': r'(what|when|where|who|how|which)',
        'confirmation': r'(confirm|verify|check|correct)',
        'help': r'(help|assist|support|trouble|issue|problem)',
    }
    
    # Tone indicators
    URGENT_INDICATORS = ['urgent', 'asap', 'emergency', 'critical', 'immediately']
    CASUAL_INDICATORS = ['thanks', 'hey', 'just checking', 'whenever']
    FORMAL_INDICATORS = ['dear', 'sincerely', 'regards', 'respectfully']
    
    def __init__(self):
        self.db = ContextDatabase()
        self.email_manager = UniversalAccountManager()
    
    def draft_reply(self, message: Dict) -> Optional[Dict]:
        """
        Draft a reply suggestion for an email.
        
        Returns:
            {
                'suggested_reply': str,
                'tone': str,  # 'professional', 'casual', 'urgent'
                'confidence': float,  # 0.0 to 1.0
                'reasoning': str
            }
        """
        try:
            # Extract message details
            from_email = self._extract_email(message.get('from', ''))
            subject = message.get('subject', '').lower()
            body = message.get('body', '').lower()
            
            # Get contact context
            contact = self.db.get_contact(from_email) if from_email else None
            
            # Detect question type
            question_type = self._detect_question_type(subject, body)
            
            # Detect tone
            tone = self._detect_tone(subject, body, contact)
            
            # Generate reply based on question type
            if question_type == 'meeting':
                return self._draft_meeting_reply(message, contact, tone)
            
            elif question_type == 'status':
                return self._draft_status_reply(message, contact, tone)
            
            elif question_type == 'approval':
                return self._draft_approval_reply(message, contact, tone)
            
            elif question_type == 'confirmation':
                return self._draft_confirmation_reply(message, contact, tone)
            
            elif question_type == 'help':
                return self._draft_help_reply(message, contact, tone)
            
            else:
                # Generic acknowledgment
                return self._draft_generic_reply(message, contact, tone)
        
        except Exception as e:
            logger.error(f"Error drafting reply: {e}")
            return None
    
    def _extract_email(self, email_str: str) -> str:
        """Extract email from 'Name <email>' format."""
        match = re.search(r'<(.+?)>', email_str)
        if match:
            return match.group(1).lower()
        return email_str.lower().strip()
    
    def _detect_question_type(self, subject: str, body: str) -> str:
        """Detect the type of question being asked."""
        text = f"{subject} {body}".lower()
        
        for question_type, pattern in self.QUESTION_PATTERNS.items():
            if re.search(pattern, text):
                return question_type
        
        return 'generic'
    
    def _detect_tone(self, subject: str, body: str, contact: Optional[Dict]) -> str:
        """Detect appropriate reply tone."""
        text = f"{subject} {body}".lower()
        
        # Check for urgent
        if any(word in text for word in self.URGENT_INDICATORS):
            return 'urgent'
        
        # Check for formal
        if any(word in text for word in self.FORMAL_INDICATORS):
            return 'professional'
        
        # Check for casual
        if any(word in text for word in self.CASUAL_INDICATORS):
            return 'casual'
        
        # Default based on contact relationship
        if contact:
            # If you email frequently, probably casual
            if contact.get('total_emails', 0) > 20:
                return 'casual'
        
        return 'professional'
    
    def _draft_meeting_reply(self, message: Dict, contact: Optional[Dict], tone: str) -> Dict:
        """Draft reply to meeting request."""
        
        # Check calendar availability (simplified for v1)
        suggestions = [
            "I'd be happy to meet. Let me check my calendar and get back to you with some times.",
            "Thanks for reaching out. I'm available this week - what works best for you?",
            "Let's schedule something. Can you send over a few times that work?"
        ]
        
        if tone == 'urgent':
            reply = "I can make time today or tomorrow if needed. What's urgent?"
        elif tone == 'casual':
            reply = suggestions[1]  # More casual
        else:
            reply = suggestions[0]  # Professional
        
        return {
            'suggested_reply': reply,
            'tone': tone,
            'confidence': 0.7,
            'reasoning': 'Meeting request detected - suggesting availability check'
        }
    
    def _draft_status_reply(self, message: Dict, contact: Optional[Dict], tone: str) -> Dict:
        """Draft reply to status update request."""
        
        if tone == 'urgent':
            reply = "Working on this now - I'll have an update for you within the hour."
        elif tone == 'casual':
            reply = "Making good progress! I'll send a full update later today."
        else:
            reply = "Thank you for checking in. I'm making progress and will send a detailed update by end of day."
        
        return {
            'suggested_reply': reply,
            'tone': tone,
            'confidence': 0.6,
            'reasoning': 'Status request detected - offering timeline for update'
        }
    
    def _draft_approval_reply(self, message: Dict, contact: Optional[Dict], tone: str) -> Dict:
        """Draft reply to approval request."""
        
        reply = "I'll review this and get back to you by [TIME]. Thanks for sending it over."
        
        # Add context based on urgency
        if tone == 'urgent':
            reply = "Reviewing now - I'll have feedback within the hour."
        
        return {
            'suggested_reply': reply,
            'tone': tone,
            'confidence': 0.5,
            'reasoning': 'Approval/review request - suggesting review timeline'
        }
    
    def _draft_confirmation_reply(self, message: Dict, contact: Optional[Dict], tone: str) -> Dict:
        """Draft reply to confirmation request."""
        
        reply = "Yes, that's correct. Let me know if you need anything else."
        
        if tone == 'professional':
            reply = "Confirmed. Please let me know if you have any questions."
        
        return {
            'suggested_reply': reply,
            'tone': tone,
            'confidence': 0.8,
            'reasoning': 'Confirmation request - straightforward acknowledgment'
        }
    
    def _draft_help_reply(self, message: Dict, contact: Optional[Dict], tone: str) -> Dict:
        """Draft reply to help request."""
        
        if tone == 'urgent':
            reply = "On it - let me look into this and get back to you ASAP."
        else:
            reply = "I can help with this. Let me look into it and I'll follow up shortly."
        
        return {
            'suggested_reply': reply,
            'tone': tone,
            'confidence': 0.7,
            'reasoning': 'Help request detected - acknowledging and promising follow-up'
        }
    
    def _draft_generic_reply(self, message: Dict, contact: Optional[Dict], tone: str) -> Dict:
        """Draft generic acknowledgment reply."""
        
        if tone == 'casual':
            reply = "Thanks for the email! I'll take a look and get back to you."
        else:
            reply = "Thank you for your email. I'll review and respond shortly."
        
        # Lower confidence for generic
        return {
            'suggested_reply': reply,
            'tone': tone,
            'confidence': 0.4,
            'reasoning': 'No specific question detected - generic acknowledgment'
        }


def test_reply_drafter():
    """Test reply drafter with sample emails."""
    drafter = ReplyDrafter()
    
    # Test email 1: Meeting request
    test_email_1 = {
        'from': 'Ross Buntrock <ross@legalmensch.com>',
        'subject': 'Can we schedule a quick call?',
        'body': 'Hey, can we hop on a call this week to discuss the Q2 budget? Let me know what works.',
    }
    
    print("Test 1: Meeting Request")
    print(f"From: {test_email_1['from']}")
    print(f"Subject: {test_email_1['subject']}")
    reply = drafter.draft_reply(test_email_1)
    if reply:
        print(f"Suggested Reply ({reply['tone']}, confidence: {reply['confidence']}):")
        print(f"  {reply['suggested_reply']}")
        print(f"  Reasoning: {reply['reasoning']}")
    print()
    
    # Test email 2: Status request
    test_email_2 = {
        'from': 'Eric Tam <eric@chariotclaims.com>',
        'subject': 'Update on client intake forms',
        'body': 'URGENT: Can you send me a status update on the client intake forms? Need this for the board meeting today.',
    }
    
    print("Test 2: Urgent Status Request")
    print(f"From: {test_email_2['from']}")
    print(f"Subject: {test_email_2['subject']}")
    reply = drafter.draft_reply(test_email_2)
    if reply:
        print(f"Suggested Reply ({reply['tone']}, confidence: {reply['confidence']}):")
        print(f"  {reply['suggested_reply']}")
        print(f"  Reasoning: {reply['reasoning']}")
    print()


if __name__ == '__main__':
    print("\n" + "="*60)
    print("Reply Drafter v1 - Test")
    print("="*60 + "\n")
    
    test_reply_drafter()
    
    print("="*60)
    print("✅ Reply Drafter ready!")
    print("="*60 + "\n")
