#!/usr/bin/env python3
"""
Task Extractor - Transmogrifier MVP

Automatically detects action items in emails using NLP patterns.

Detects:
- Explicit requests ("Can you...", "Please...", "Could you...")
- Action verbs ("Review", "Send", "Update", "Check", "Follow up")
- Deadlines ("by Friday", "EOD", "ASAP", "before the meeting")
- Assignments ("You need to...", "Don't forget to...")

NOT AI-powered (yet) - uses pattern matching for speed/cost.
Can upgrade to LLM later for better accuracy.
"""

import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class ExtractedTask:
    """Extracted task from email."""
    text: str
    deadline: Optional[datetime]
    deadline_text: Optional[str]
    priority: int  # 1=high, 2=medium, 3=low
    confidence: float  # 0.0-1.0
    context: str  # Surrounding text for verification
    source_type: str  # 'explicit_request', 'action_verb', 'deadline_mention'


class TaskExtractor:
    """Extract action items from email text."""
    
    # Explicit request patterns
    REQUEST_PATTERNS = [
        r'(?:can|could|would) you (?:please )?(.{5,100}?)[.?]',
        r'please (.{5,100}?)[.?]',
        r'(?:would appreciate if|need you to) (.{5,100}?)[.?]',
        r"(?:don't forget to|remember to|make sure (?:you|to)) (.{5,100}?)[.?]",
        r'you (?:need|should|must) (?:to )?(.{5,100}?)[.?]',
    ]
    
    # Action verbs that indicate tasks
    ACTION_VERBS = [
        'review', 'send', 'update', 'check', 'follow up', 'schedule',
        'confirm', 'prepare', 'complete', 'submit', 'approve', 'sign',
        'respond', 'reply', 'call', 'email', 'contact', 'reach out',
        'create', 'draft', 'write', 'edit', 'revise', 'finalize'
    ]
    
    # Deadline patterns
    DEADLINE_PATTERNS = [
        (r'by (tomorrow|eod|end of (?:day|week)|friday|monday|tuesday|wednesday|thursday)', 'relative'),
        (r'by (\d{1,2}/\d{1,2})', 'date'),
        (r'(asap|urgent|immediately)', 'urgent'),
        (r'before (the meeting|our call|next week)', 'relative'),
        (r'within (\d+) (?:day|hour|week)s?', 'duration'),
    ]
    
    # Priority indicators
    HIGH_PRIORITY = ['urgent', 'asap', 'critical', 'important', 'immediately']
    LOW_PRIORITY = ['when you can', 'no rush', 'whenever', 'at some point']
    
    def __init__(self, context_db_path: Optional[Path] = None):
        """
        Initialize task extractor.
        
        Args:
            context_db_path: Path to context database
        """
        if context_db_path is None:
            context_db_path = Path.home() / ".openclaw/workspace/integrations/intelligence/data/context.db"
        
        self.db_path = Path(context_db_path)
        self._init_database()
    
    def _init_database(self):
        """Create tasks table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS extracted_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_email_id TEXT,
                source_email_subject TEXT,
                source_email_from TEXT,
                task_text TEXT NOT NULL,
                deadline TIMESTAMP,
                deadline_text TEXT,
                priority INTEGER DEFAULT 2,
                confidence REAL DEFAULT 0.0,
                context TEXT,
                source_type TEXT,
                status TEXT DEFAULT 'pending',
                auto_extracted BOOLEAN DEFAULT 1,
                user_confirmed BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                dismissed_at TIMESTAMP
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_extracted_tasks_status ON extracted_tasks(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_extracted_tasks_deadline ON extracted_tasks(deadline)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_extracted_tasks_source ON extracted_tasks(source_email_id)')
        
        conn.commit()
        conn.close()
    
    def extract_from_email(self, email: Dict) -> List[ExtractedTask]:
        """
        Extract tasks from an email.
        
        Args:
            email: Email dict with 'subject', 'body', 'from'
            
        Returns:
            List of extracted tasks
        """
        subject = email.get('subject', '')
        body = email.get('body', '')
        
        # Combine subject + body for analysis
        text = f"{subject}\n\n{body}"
        
        tasks = []
        
        # 1. Extract explicit requests
        for pattern in self.REQUEST_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                task_text = match.group(1).strip()
                
                # Skip if too short or looks like noise
                if len(task_text) < 10 or self._is_noise(task_text):
                    continue
                
                # Get context (surrounding text)
                context_start = max(0, match.start() - 50)
                context_end = min(len(text), match.end() + 50)
                context = text[context_start:context_end]
                
                # Extract deadline if mentioned
                deadline, deadline_text = self._extract_deadline(task_text)
                
                # Determine priority
                priority = self._determine_priority(task_text)
                
                tasks.append(ExtractedTask(
                    text=self._clean_task_text(task_text),
                    deadline=deadline,
                    deadline_text=deadline_text,
                    priority=priority,
                    confidence=0.8,  # High confidence for explicit requests
                    context=context,
                    source_type='explicit_request'
                ))
        
        # 2. Extract action verb patterns
        for verb in self.ACTION_VERBS:
            # Pattern: "You should [verb] ..." or "Please [verb] ..."
            pattern = rf'\b(?:you (?:should|need to|must)|please) {verb} (.{{10,100}}?)[.?!]'
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                task_text = f"{verb.title()} {match.group(1).strip()}"
                
                if self._is_noise(task_text):
                    continue
                
                context_start = max(0, match.start() - 50)
                context_end = min(len(text), match.end() + 50)
                context = text[context_start:context_end]
                
                deadline, deadline_text = self._extract_deadline(task_text)
                priority = self._determine_priority(task_text)
                
                tasks.append(ExtractedTask(
                    text=self._clean_task_text(task_text),
                    deadline=deadline,
                    deadline_text=deadline_text,
                    priority=priority,
                    confidence=0.6,  # Medium confidence for action verbs
                    context=context,
                    source_type='action_verb'
                ))
        
        # Deduplicate similar tasks
        tasks = self._deduplicate_tasks(tasks)
        
        return tasks
    
    def _extract_deadline(self, text: str) -> Tuple[Optional[datetime], Optional[str]]:
        """
        Extract deadline from text.
        
        Args:
            text: Text to search
            
        Returns:
            (deadline datetime, deadline text)
        """
        text_lower = text.lower()
        
        for pattern, deadline_type in self.DEADLINE_PATTERNS:
            match = re.search(pattern, text_lower)
            
            if match:
                deadline_text = match.group(0)
                
                if deadline_type == 'urgent':
                    # ASAP = today EOD
                    deadline = datetime.now().replace(hour=17, minute=0, second=0)
                
                elif deadline_type == 'relative':
                    deadline_str = match.group(1)
                    
                    if 'tomorrow' in deadline_str:
                        deadline = datetime.now() + timedelta(days=1)
                    elif 'eod' in deadline_str or 'end of day' in deadline_str:
                        deadline = datetime.now().replace(hour=17, minute=0, second=0)
                    elif 'end of week' in deadline_str:
                        # Next Friday 5 PM
                        days_until_friday = (4 - datetime.now().weekday()) % 7
                        deadline = datetime.now() + timedelta(days=days_until_friday)
                        deadline = deadline.replace(hour=17, minute=0, second=0)
                    elif 'monday' in deadline_str:
                        days_until = (0 - datetime.now().weekday()) % 7
                        deadline = datetime.now() + timedelta(days=days_until)
                    elif 'friday' in deadline_str:
                        days_until = (4 - datetime.now().weekday()) % 7
                        deadline = datetime.now() + timedelta(days=days_until)
                    else:
                        deadline = None
                
                elif deadline_type == 'duration':
                    duration = int(match.group(1))
                    if 'hour' in text_lower:
                        deadline = datetime.now() + timedelta(hours=duration)
                    elif 'day' in text_lower:
                        deadline = datetime.now() + timedelta(days=duration)
                    elif 'week' in text_lower:
                        deadline = datetime.now() + timedelta(weeks=duration)
                    else:
                        deadline = None
                
                elif deadline_type == 'date':
                    # Simple date parsing (M/D)
                    try:
                        month, day = map(int, match.group(1).split('/'))
                        year = datetime.now().year
                        deadline = datetime(year, month, day, 17, 0)
                    except:
                        deadline = None
                
                else:
                    deadline = None
                
                return (deadline, deadline_text)
        
        return (None, None)
    
    def _determine_priority(self, text: str) -> int:
        """
        Determine task priority from text.
        
        Args:
            text: Task text
            
        Returns:
            Priority (1=high, 2=medium, 3=low)
        """
        text_lower = text.lower()
        
        # Check for high priority indicators
        if any(indicator in text_lower for indicator in self.HIGH_PRIORITY):
            return 1
        
        # Check for low priority indicators
        if any(indicator in text_lower for indicator in self.LOW_PRIORITY):
            return 3
        
        # Default: medium
        return 2
    
    def _clean_task_text(self, text: str) -> str:
        """Clean up extracted task text."""
        # Remove trailing punctuation
        text = text.rstrip('.?!')
        
        # Capitalize first letter
        if text:
            text = text[0].upper() + text[1:]
        
        # Limit length
        if len(text) > 200:
            text = text[:197] + '...'
        
        return text
    
    def _is_noise(self, text: str) -> bool:
        """Check if extracted text is likely noise."""
        # Too short
        if len(text) < 10:
            return True
        
        # Common noise patterns
        noise_patterns = [
            r'^(thanks|thank you|regards|best)',
            r'^(see|talk|speak) (?:you|to you)',
            r'^(let me know|lmk)',
        ]
        
        for pattern in noise_patterns:
            if re.match(pattern, text.lower()):
                return True
        
        return False
    
    def _deduplicate_tasks(self, tasks: List[ExtractedTask]) -> List[ExtractedTask]:
        """Remove duplicate/similar tasks."""
        if not tasks:
            return tasks
        
        # Sort by confidence (highest first)
        tasks = sorted(tasks, key=lambda t: t.confidence, reverse=True)
        
        unique_tasks = []
        seen_texts = set()
        
        for task in tasks:
            # Normalize text for comparison
            normalized = task.text.lower().strip()
            
            # Check if similar task already added
            is_duplicate = False
            for seen in seen_texts:
                if self._texts_similar(normalized, seen):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_tasks.append(task)
                seen_texts.add(normalized)
        
        return unique_tasks
    
    def _texts_similar(self, text1: str, text2: str, threshold: float = 0.7) -> bool:
        """Check if two task texts are similar."""
        # Simple similarity: check if one is substring of other
        if text1 in text2 or text2 in text1:
            return True
        
        # Word overlap
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return False
        
        overlap = len(words1 & words2)
        total = len(words1 | words2)
        
        similarity = overlap / total if total > 0 else 0
        
        return similarity >= threshold
    
    def save_tasks(self, email_id: str, email: Dict, tasks: List[ExtractedTask]) -> int:
        """
        Save extracted tasks to database.
        
        Args:
            email_id: Email message ID
            email: Email dict (for metadata)
            tasks: Extracted tasks
            
        Returns:
            Number of tasks saved
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        saved = 0
        
        for task in tasks:
            cursor.execute('''
                INSERT INTO extracted_tasks
                (source_email_id, source_email_subject, source_email_from,
                 task_text, deadline, deadline_text, priority, confidence,
                 context, source_type, status, auto_extracted, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                email_id,
                email.get('subject', ''),
                email.get('from', ''),
                task.text,
                task.deadline,
                task.deadline_text,
                task.priority,
                task.confidence,
                task.context,
                task.source_type,
                'pending',
                True,
                datetime.now()
            ))
            
            saved += 1
        
        conn.commit()
        conn.close()
        
        return saved
    
    def get_pending_tasks(self, min_confidence: float = 0.5, limit: int = 50) -> List[Dict]:
        """
        Get pending tasks (not confirmed, not dismissed).
        
        Args:
            min_confidence: Minimum confidence threshold
            limit: Max tasks to return
            
        Returns:
            List of task dicts
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, source_email_id, source_email_subject, source_email_from,
                   task_text, deadline, deadline_text, priority, confidence,
                   context, source_type, created_at
            FROM extracted_tasks
            WHERE status = 'pending'
              AND user_confirmed = 0
              AND dismissed_at IS NULL
              AND confidence >= ?
            ORDER BY priority ASC, deadline ASC, created_at DESC
            LIMIT ?
        ''', (min_confidence, limit))
        
        tasks = []
        
        for row in cursor.fetchall():
            tasks.append({
                'id': row[0],
                'source_email_id': row[1],
                'source_email_subject': row[2],
                'source_email_from': row[3],
                'task_text': row[4],
                'deadline': row[5],
                'deadline_text': row[6],
                'priority': row[7],
                'confidence': row[8],
                'context': row[9],
                'source_type': row[10],
                'created_at': row[11]
            })
        
        conn.close()
        
        return tasks
    
    def confirm_task(self, task_id: int) -> bool:
        """Mark task as confirmed by user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE extracted_tasks
            SET user_confirmed = 1, status = 'confirmed'
            WHERE id = ?
        ''', (task_id,))
        
        conn.commit()
        conn.close()
        
        return cursor.rowcount > 0
    
    def dismiss_task(self, task_id: int) -> bool:
        """Mark task as dismissed by user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE extracted_tasks
            SET dismissed_at = ?, status = 'dismissed'
            WHERE id = ?
        ''', (datetime.now(), task_id))
        
        conn.commit()
        conn.close()
        
        return cursor.rowcount > 0
    
    def complete_task(self, task_id: int) -> bool:
        """Mark task as completed."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE extracted_tasks
            SET completed_at = ?, status = 'completed'
            WHERE id = ?
        ''', (datetime.now(), task_id))
        
        conn.commit()
        conn.close()
        
        return cursor.rowcount > 0


if __name__ == '__main__':
    # Test task extractor
    extractor = TaskExtractor()
    
    print("Task Extractor Test")
    print("=" * 80)
    
    # Test emails
    test_emails = [
        {
            'id': 'test1',
            'from': 'ross@legalmensch.com',
            'subject': 'Q2 Review',
            'body': '''Hi Simon,

Can you please send me the Q2 financials by EOD Friday? We need to review them before the board meeting.

Also, don't forget to update the project timeline. Let me know if you have any questions.

Thanks,
Ross'''
        },
        {
            'id': 'test2',
            'from': 'alice@client.com',
            'subject': 'Contract Update',
            'body': '''Simon,

Please review the attached contract and send your feedback by 5/20. This is urgent - we need to finalize before the deadline.

Could you also schedule a call with the team next week?

Best,
Alice'''
        },
        {
            'id': 'test3',
            'from': 'newsletter@example.com',
            'subject': 'Weekly Newsletter',
            'body': '''Check out this week's top articles!

Read more about productivity tips and latest tech news.

Unsubscribe here.'''
        }
    ]
    
    total_extracted = 0
    
    for email in test_emails:
        print(f"\n📧 Email: {email['subject']}")
        print(f"   From: {email['from']}")
        print()
        
        # Extract tasks
        tasks = extractor.extract_from_email(email)
        
        if tasks:
            print(f"   Extracted {len(tasks)} task(s):")
            
            for task in tasks:
                priority_emoji = {1: '🔴', 2: '🟡', 3: '🟢'}
                emoji = priority_emoji.get(task.priority, '⚪')
                
                print(f"\n   {emoji} {task.text}")
                print(f"      Confidence: {task.confidence:.0%}")
                print(f"      Source: {task.source_type}")
                
                if task.deadline:
                    print(f"      Deadline: {task.deadline.strftime('%Y-%m-%d %H:%M')} ({task.deadline_text})")
                
                print(f"      Context: ...{task.context[:60]}...")
            
            # Save tasks
            saved = extractor.save_tasks(email['id'], email, tasks)
            total_extracted += saved
        
        else:
            print("   No tasks detected")
    
    print(f"\n" + "=" * 80)
    print(f"Total tasks extracted: {total_extracted}")
    
    # Show pending tasks
    print(f"\nPending Tasks (needs user confirmation):")
    print("-" * 80)
    
    pending = extractor.get_pending_tasks(min_confidence=0.5)
    
    for task in pending:
        priority_emoji = {1: '🔴', 2: '🟡', 3: '🟢'}
        emoji = priority_emoji.get(task['priority'], '⚪')
        
        print(f"\n{emoji} {task['task_text']}")
        print(f"   From: {task['source_email_subject']} ({task['source_email_from']})")
        print(f"   Confidence: {task['confidence']:.0%}")
        
        if task['deadline']:
            print(f"   Deadline: {task['deadline']}")
