#!/usr/bin/env python3
"""
Task Extractor

Automatically detects and extracts action items from emails:
- "Can you..."
- "Please..."
- "Could you..."
- "Need you to..."
- Deadlines mentioned
- Follow-up requests

Stores in context_database tasks table.
"""

import sys
import re
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging

sys.path.insert(0, str(Path(__file__).parent))

from context_database import ContextDatabase
from universal_email_api import UniversalAccountManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskExtractor:
    """Extract action items and tasks from emails."""
    
    # Action request patterns
    ACTION_PATTERNS = [
        r'can you ([^.?!]+)',
        r'could you ([^.?!]+)',
        r'please ([^.?!]+)',
        r'would you ([^.?!]+)',
        r'need you to ([^.?!]+)',
        r'i need ([^.?!]+)',
        r'action required:?\s*([^.?!]+)',
        r'to[-\s]do:?\s*([^.?!]+)',
        r'task:?\s*([^.?!]+)',
    ]
    
    # Deadline patterns
    DEADLINE_PATTERNS = [
        (r'by (today|tomorrow)', 0, 1),  # relative days
        (r'by (monday|tuesday|wednesday|thursday|friday|saturday|sunday)', None, None),  # specific day
        (r'by (\d{1,2}/\d{1,2})', None, None),  # date format
        (r'due (today|tomorrow)', 0, 1),
        (r'deadline:?\s*(\w+)', None, None),
        (r'by end of (day|week|month)', 0, 7),
        (r'by eod', 0, 0),  # end of day = today
        (r'asap', 0, 0),  # ASAP = today
    ]
    
    # Priority keywords
    HIGH_PRIORITY = ['urgent', 'asap', 'critical', 'emergency', 'important']
    
    def __init__(self):
        self.db = ContextDatabase()
        self.email_manager = UniversalAccountManager()
    
    def extract_from_message(self, message: Dict) -> List[Dict]:
        """
        Extract tasks from an email message.
        
        Returns:
            List of tasks:
            [
                {
                    'title': str,
                    'description': str,
                    'deadline': datetime,
                    'priority': int,  # 1-5
                    'source': str,  # email_id
                    'contact_email': str
                },
                ...
            ]
        """
        tasks = []
        
        subject = message.get('subject', '')
        body = message.get('body', '')
        from_email = self._extract_email(message.get('from', ''))
        message_id = message.get('id', '')
        
        # Combine subject and body for analysis
        text = f"{subject}\\n{body}"
        
        # Extract action items
        for pattern in self.ACTION_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                task_text = match.group(1).strip()
                
                # Clean up task text
                task_text = self._clean_task_text(task_text)
                
                if len(task_text) < 5 or len(task_text) > 200:
                    continue  # Too short or too long
                
                # Detect deadline
                deadline = self._extract_deadline(text)
                
                # Detect priority
                priority = self._detect_priority(subject, body)
                
                tasks.append({
                    'title': task_text[:100],  # Truncate title
                    'description': subject,
                    'deadline': deadline,
                    'priority': priority,
                    'source': f"email_{message_id}",
                    'contact_email': from_email
                })
        
        # Deduplicate similar tasks
        tasks = self._deduplicate_tasks(tasks)
        
        return tasks
    
    def extract_and_store(self, message: Dict) -> int:
        """Extract tasks and store in database. Returns count of tasks stored."""
        tasks = self.extract_from_message(message)
        
        stored_count = 0
        for task in tasks:
            try:
                task_id = self.db.add_task(
                    title=task['title'],
                    description=task['description'],
                    deadline=task['deadline'].isoformat() if task['deadline'] else None,
                    priority=task['priority'],
                    source=task['source'],
                    contact_email=task['contact_email']
                )
                
                logger.info(f"Stored task: {task['title']} (ID: {task_id})")
                stored_count += 1
                
            except Exception as e:
                logger.error(f"Error storing task: {e}")
        
        return stored_count
    
    def scan_recent_emails(self, hours_back: int = 24) -> int:
        """Scan recent emails for tasks. Returns total tasks found."""
        total_tasks = 0
        
        # Get all unread messages
        messages = self.email_manager.get_all_unread_messages(hours_back=hours_back)
        
        logger.info(f"Scanning {len(messages)} recent emails for tasks...")
        
        for message in messages:
            tasks_count = self.extract_and_store(message)
            total_tasks += tasks_count
        
        return total_tasks
    
    def _extract_email(self, email_str: str) -> str:
        """Extract email from 'Name <email>' format."""
        match = re.search(r'<(.+?)>', email_str)
        if match:
            return match.group(1).lower()
        return email_str.lower().strip()
    
    def _clean_task_text(self, text: str) -> str:
        """Clean up task text."""
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove trailing punctuation
        text = text.rstrip('.?!')
        
        # Capitalize first letter
        if text:
            text = text[0].upper() + text[1:]
        
        return text
    
    def _extract_deadline(self, text: str) -> Optional[datetime]:
        """Extract deadline from text."""
        text_lower = text.lower()
        
        for pattern, days_from_now, days_alt in self.DEADLINE_PATTERNS:
            match = re.search(pattern, text_lower)
            
            if match:
                if days_from_now is not None:
                    # Relative deadline
                    if match.group(1) == 'today':
                        return datetime.now()
                    elif match.group(1) == 'tomorrow':
                        return datetime.now() + timedelta(days=1)
                    else:
                        return datetime.now() + timedelta(days=days_from_now)
                
                # For specific days/dates, default to 1 week out
                # (More sophisticated date parsing would go here)
                return datetime.now() + timedelta(days=7)
        
        return None
    
    def _detect_priority(self, subject: str, body: str) -> int:
        """
        Detect priority level 1-5.
        1 = highest, 5 = lowest
        """
        text = f"{subject} {body}".lower()
        
        # Check for high priority keywords
        if any(word in text for word in self.HIGH_PRIORITY):
            return 1
        
        # Check for deadline indicators
        if 'today' in text or 'eod' in text or 'asap' in text:
            return 1
        
        if 'tomorrow' in text or 'urgent' in text:
            return 2
        
        # Default to normal priority
        return 3
    
    def _deduplicate_tasks(self, tasks: List[Dict]) -> List[Dict]:
        """Remove duplicate/similar tasks."""
        if not tasks:
            return []
        
        unique_tasks = []
        seen_titles = set()
        
        for task in tasks:
            title_normalized = task['title'].lower().strip()
            
            if title_normalized not in seen_titles:
                unique_tasks.append(task)
                seen_titles.add(title_normalized)
        
        return unique_tasks
    
    def confirm_task(self, task_id: int) -> bool:
        """
        User confirms a task is real.
        Logs action for learning.
        
        Args:
            task_id: Task ID to confirm
            
        Returns:
            Success boolean
        """
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Update task status
            cursor.execute('''
                UPDATE tasks
                SET status = 'confirmed'
                WHERE id = ?
            ''', (task_id,))
            
            # Log action for learning
            cursor.execute('''
                INSERT INTO task_actions (task_id, action)
                VALUES (?, 'confirmed')
            ''', (task_id,))
            
            conn.commit()
            logger.info(f"✅ Task {task_id} confirmed")
            return True
            
        except Exception as e:
            logger.error(f"Error confirming task {task_id}: {e}")
            return False
    
    def dismiss_task(self, task_id: int) -> bool:
        """
        User dismisses a task as incorrect.
        Logs action for learning (improve extraction).
        
        Args:
            task_id: Task ID to dismiss
            
        Returns:
            Success boolean
        """
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Update task status
            cursor.execute('''
                UPDATE tasks
                SET status = 'dismissed'
                WHERE id = ?
            ''', (task_id,))
            
            # Log action for learning
            cursor.execute('''
                INSERT INTO task_actions (task_id, action)
                VALUES (?, 'dismissed')
            ''', (task_id,))
            
            conn.commit()
            logger.info(f"❌ Task {task_id} dismissed")
            return True
            
        except Exception as e:
            logger.error(f"Error dismissing task {task_id}: {e}")
            return False
    
    def complete_task(self, task_id: int) -> bool:
        """
        Mark a task as completed.
        
        Args:
            task_id: Task ID to complete
            
        Returns:
            Success boolean
        """
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Mark completed
            cursor.execute('''
                UPDATE tasks
                SET completed = 1, completed_at = ?, status = 'completed'
                WHERE id = ?
            ''', (datetime.now(), task_id))
            
            # Log action
            cursor.execute('''
                INSERT INTO task_actions (task_id, action)
                VALUES (?, 'completed')
            ''', (task_id,))
            
            conn.commit()
            logger.info(f"✅ Task {task_id} completed")
            return True
            
        except Exception as e:
            logger.error(f"Error completing task {task_id}: {e}")
            return False
    
    def get_pending_tasks(self, limit: int = 50, min_confidence: float = 0.5) -> List[Dict]:
        """
        Get pending tasks for user review.
        
        Args:
            limit: Max tasks to return
            min_confidence: Minimum confidence score
            
        Returns:
            List of pending tasks
        """
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, title, description, priority, deadline, 
                       source, contact_email, confidence
                FROM tasks
                WHERE status = 'pending' AND confidence >= ?
                ORDER BY priority ASC, deadline ASC
                LIMIT ?
            ''', (min_confidence, limit))
            
            tasks = []
            for row in cursor.fetchall():
                tasks.append({
                    'id': row[0],
                    'title': row[1],
                    'description': row[2],
                    'priority': row[3],
                    'deadline': row[4],
                    'source': row[5],
                    'contact_email': row[6],
                    'confidence': row[7]
                })
            
            return tasks
            
        except Exception as e:
            logger.error(f"Error getting pending tasks: {e}")
            return []


def test_task_extractor():
    """Test task extractor with sample emails."""
    extractor = TaskExtractor()
    
    # Test email 1: Action request with deadline
    test_email_1 = {
        'id': 'test_1',
        'from': 'Ross Buntrock <ross@legalmensch.com>',
        'subject': 'Can you review the Q2 budget?',
        'body': 'Hey, can you review the Q2 budget and send me your feedback by EOD tomorrow? Thanks!',
    }
    
    print("Test 1: Action Request with Deadline")
    print(f"From: {test_email_1['from']}")
    print(f"Subject: {test_email_1['subject']}")
    tasks = extractor.extract_from_message(test_email_1)
    print(f"Tasks extracted: {len(tasks)}")
    for task in tasks:
        print(f"  • {task['title']}")
        print(f"    Priority: {task['priority']}, Deadline: {task['deadline']}")
    print()
    
    # Test email 2: Multiple action items
    test_email_2 = {
        'id': 'test_2',
        'from': 'Eric Tam <eric@chariotclaims.com>',
        'subject': 'URGENT: Client intake tasks',
        'body': 'Can you please update the client intake forms by today? Also, I need you to send the billing report to accounting ASAP. Thanks!',
    }
    
    print("Test 2: Multiple Urgent Actions")
    print(f"From: {test_email_2['from']}")
    print(f"Subject: {test_email_2['subject']}")
    tasks = extractor.extract_from_message(test_email_2)
    print(f"Tasks extracted: {len(tasks)}")
    for task in tasks:
        print(f"  • {task['title']}")
        print(f"    Priority: {task['priority']}, Deadline: {task['deadline']}")
    print()


if __name__ == '__main__':
    print("\n" + "="*60)
    print("Task Extractor - Test")
    print("="*60 + "\n")
    
    test_task_extractor()
    
    print("="*60)
    print("✅ Task Extractor ready!")
    print("="*60 + "\n")
