#!/usr/bin/env python3
"""
Transmogrifier API

Unified API interface for all Transmogrifier MVP features.
Ready for FastAPI/Flask integration.

Features:
- Contacts & relationship intelligence
- Task extraction & management
- Smart inbox
- Weekly digest generation
"""

from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# Import all components
from contact_unification import ContactUnification
from dynamic_relationship_scorer import DynamicRelationshipScorer
from task_extractor import TaskExtractor
from smart_inbox import SmartInbox
from weekly_digest import WeeklyDigestGenerator


class TransmogrifierAPI:
    """Unified API for all Transmogrifier features."""
    
    def __init__(self, user_id: str, user_db_path: Optional[Path] = None):
        """
        Initialize API for a specific user.
        
        Args:
            user_id: Unique user identifier
            user_db_path: Path to user's context database
        """
        self.user_id = user_id
        
        # User-specific database (multi-tenant isolation)
        if user_db_path is None:
            user_db_path = Path.home() / f".openclaw/workspace/data/users/{user_id}/context.db"
            user_db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.db_path = user_db_path
        
        # Initialize components
        self.contacts = ContactUnification(context_db_path=self.db_path)
        self.relationships = DynamicRelationshipScorer(context_db_path=self.db_path)
        self.tasks = TaskExtractor(context_db_path=self.db_path)
        self.inbox = SmartInbox(context_db_path=self.db_path)
        self.digest = WeeklyDigestGenerator(context_db_path=self.db_path)
    
    # ========== Contacts API ==========
    
    def search_contacts(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search contacts by name or email.
        
        Args:
            query: Search query
            limit: Max results
            
        Returns:
            List of contact dicts
        """
        return self.contacts.search_contacts(query, limit=limit)
    
    def get_contact(self, email: str) -> Optional[Dict]:
        """Get contact by email."""
        return self.contacts.get_contact_by_email(email)
    
    def get_vips(self, limit: int = 20) -> List[Dict]:
        """Get VIP contacts."""
        # Get top relationships by importance score
        top_rels = self.relationships.get_top_relationships(limit=limit * 2)
        
        # Filter for VIPs (score >= 70)
        vips = [r for r in top_rels if r['importance_score'] >= 70]
        
        return vips[:limit]
    
    def sync_contacts(self, account: str, provider: str = 'gmail') -> int:
        """
        Sync contacts from an email account.
        
        Args:
            account: Email account
            provider: Provider type ('gmail', 'outlook', etc.)
            
        Returns:
            Number of contacts synced
        """
        # Sync based on provider
        if provider == 'gmail':
            # Sync from email headers
            count = self.contacts.sync_email_contacts(account=account, days=180)
        else:
            count = 0
        
        # Merge duplicates
        self.contacts.merge_duplicates()
        
        # Enrich
        self.contacts.enrich_contacts()
        
        return count
    
    # ========== Relationships API ==========
    
    def get_top_relationships(self, limit: int = 20) -> List[Dict]:
        """Get top relationships by importance."""
        return self.relationships.get_top_relationships(limit=limit)
    
    def get_follow_up_suggestions(self, days_threshold: int = 21, min_importance: float = 50.0) -> List[Dict]:
        """Get relationship follow-up suggestions."""
        return self.relationships.get_follow_up_suggestions(
            min_importance=min_importance,
            days_threshold=days_threshold
        )
    
    def get_relationship_score(self, email: str) -> float:
        """Get importance score for a contact."""
        return self.relationships.calculate_score(email)
    
    def log_email_sent(self, to_email: str, subject: str = None, timestamp: datetime = None):
        """Log outgoing email (for relationship tracking)."""
        return self.relationships.log_email_sent(to_email, subject, timestamp)
    
    def log_email_received(self, from_email: str, subject: str = None, timestamp: datetime = None):
        """Log incoming email (for relationship tracking)."""
        return self.relationships.log_email_received(from_email, subject, timestamp)
    
    # ========== Tasks API ==========
    
    def extract_tasks_from_email(self, email: Dict) -> List[Dict]:
        """
        Extract tasks from an email.
        
        Args:
            email: Email dict with 'subject', 'body', 'from'
            
        Returns:
            List of extracted task dicts
        """
        extracted = self.tasks.extract_from_email(email)
        
        # Convert to dicts
        return [
            {
                'text': t.text,
                'deadline': t.deadline.isoformat() if t.deadline else None,
                'deadline_text': t.deadline_text,
                'priority': t.priority,
                'confidence': t.confidence,
                'context': t.context,
                'source_type': t.source_type
            }
            for t in extracted
        ]
    
    def save_extracted_tasks(self, email_id: str, email: Dict) -> int:
        """Extract and save tasks from an email."""
        tasks = self.tasks.extract_from_email(email)
        return self.tasks.save_tasks(email_id, email, tasks)
    
    def get_pending_tasks(self, min_confidence: float = 0.5, limit: int = 50) -> List[Dict]:
        """Get pending tasks (need user confirmation)."""
        return self.tasks.get_pending_tasks(min_confidence=min_confidence, limit=limit)
    
    def confirm_task(self, task_id: int) -> bool:
        """User confirms a task."""
        return self.tasks.confirm_task(task_id)
    
    def dismiss_task(self, task_id: int) -> bool:
        """User dismisses a task."""
        return self.tasks.dismiss_task(task_id)
    
    def complete_task(self, task_id: int) -> bool:
        """Mark task as complete."""
        return self.tasks.complete_task(task_id)
    
    # ========== Inbox API ==========
    
    def sync_inbox(self, account: str, emails: List[Dict]) -> int:
        """
        Sync emails to inbox cache.
        
        Args:
            account: Account name
            emails: List of email dicts from provider API
            
        Returns:
            Number of emails synced
        """
        return self.inbox.sync_emails(account, emails)
    
    def get_inbox(self, 
                  priority_level: Optional[str] = None,
                  unread_only: bool = True,
                  limit: int = 50) -> List[Dict]:
        """
        Get inbox emails (priority-sorted).
        
        Args:
            priority_level: Filter by level ('vip', 'important', 'normal', 'low')
            unread_only: Only unread emails
            limit: Max emails
            
        Returns:
            List of email dicts (sorted by priority)
        """
        return self.inbox.get_inbox(
            priority_level=priority_level,
            unread_only=unread_only,
            limit=limit
        )
    
    def mark_email_read(self, email_id: str) -> bool:
        """Mark email as read."""
        success = self.inbox.mark_read(email_id)
        
        if success:
            self.inbox.log_action(email_id, 'read')
        
        return success
    
    def mark_email_archived(self, email_id: str) -> bool:
        """Mark email as archived."""
        success = self.inbox.mark_archived(email_id)
        
        if success:
            self.inbox.log_action(email_id, 'archive')
        
        return success
    
    def snooze_email(self, email_id: str, until: datetime) -> bool:
        """Snooze email until a time."""
        success = self.inbox.snooze(email_id, until)
        
        if success:
            self.inbox.log_action(email_id, 'snooze')
        
        return success
    
    def get_inbox_stats(self) -> Dict:
        """Get inbox statistics."""
        return self.inbox.get_stats()
    
    # ========== Digest API ==========
    
    def generate_weekly_digest(self, user_name: str = "there") -> Dict:
        """Generate weekly digest data."""
        return self.digest.generate(user_name=user_name)
    
    def get_weekly_digest_html(self, user_name: str = "there") -> str:
        """Get weekly digest as HTML email."""
        digest_data = self.digest.generate(user_name=user_name)
        return self.digest.format_email(digest_data)
    
    def get_weekly_digest_text(self, user_name: str = "there") -> str:
        """Get weekly digest as plain text."""
        digest_data = self.digest.generate(user_name=user_name)
        return self.digest.format_text(digest_data)
    
    # ========== Dashboard API ==========
    
    def get_dashboard(self) -> Dict:
        """
        Get dashboard overview (all key metrics).
        
        Returns:
            Dashboard data dict
        """
        inbox_stats = self.inbox.get_stats()
        pending_tasks = self.tasks.get_pending_tasks(min_confidence=0.5, limit=5)
        followups = self.relationships.get_follow_up_suggestions(
            min_importance=60.0,
            days_threshold=21
        )
        top_rels = self.relationships.get_top_relationships(limit=5)
        
        return {
            'inbox': {
                'total_unread': inbox_stats['unread_emails'],
                'vip_count': inbox_stats['vip'],
                'important_count': inbox_stats['important']
            },
            'tasks': {
                'pending_count': len(pending_tasks),
                'top_tasks': pending_tasks[:3]
            },
            'relationships': {
                'followup_count': len(followups),
                'top_followups': followups[:3],
                'top_people': top_rels[:3]
            }
        }


# ========== Example FastAPI Integration ==========

"""
Example FastAPI app using TransmogrifierAPI:

from fastapi import FastAPI, HTTPException
from transmogrifier_api import TransmogrifierAPI

app = FastAPI()

# User-specific API instance (would come from auth middleware)
def get_api(user_id: str) -> TransmogrifierAPI:
    return TransmogrifierAPI(user_id=user_id)

@app.get("/api/contacts/search")
def search_contacts(q: str, user_id: str, limit: int = 20):
    api = get_api(user_id)
    return api.search_contacts(q, limit=limit)

@app.get("/api/relationships/followups")
def get_followups(user_id: str, days: int = 21, min_score: float = 50.0):
    api = get_api(user_id)
    return api.get_follow_up_suggestions(days_threshold=days, min_importance=min_score)

@app.get("/api/tasks/pending")
def get_pending_tasks(user_id: str, limit: int = 50):
    api = get_api(user_id)
    return api.get_pending_tasks(limit=limit)

@app.get("/api/inbox")
def get_inbox(user_id: str, priority: str = None, limit: int = 50):
    api = get_api(user_id)
    return api.get_inbox(priority_level=priority, limit=limit)

@app.get("/api/dashboard")
def get_dashboard(user_id: str):
    api = get_api(user_id)
    return api.get_dashboard()

@app.get("/api/digest/weekly")
def get_weekly_digest(user_id: str, format: str = "json"):
    api = get_api(user_id)
    
    if format == "html":
        return {"html": api.get_weekly_digest_html(user_name="User")}
    elif format == "text":
        return {"text": api.get_weekly_digest_text(user_name="User")}
    else:
        return api.generate_weekly_digest(user_name="User")
"""


if __name__ == '__main__':
    # Test API
    api = TransmogrifierAPI(user_id="test_user")
    
    print("Transmogrifier API Test")
    print("=" * 80)
    
    # Test dashboard
    print("\n1. Dashboard Overview:")
    print("-" * 80)
    dashboard = api.get_dashboard()
    
    print(f"Inbox:")
    print(f"  Unread: {dashboard['inbox']['total_unread']}")
    print(f"  VIP: {dashboard['inbox']['vip_count']}")
    print(f"  Important: {dashboard['inbox']['important_count']}")
    
    print(f"\nTasks:")
    print(f"  Pending: {dashboard['tasks']['pending_count']}")
    
    print(f"\nRelationships:")
    print(f"  Follow-ups needed: {dashboard['relationships']['followup_count']}")
    
    # Test contact search
    print("\n2. Contact Search (query='ross'):")
    print("-" * 80)
    contacts = api.search_contacts("ross", limit=3)
    
    for contact in contacts:
        print(f"  • {contact['name']} ({contact['primary_email']})")
    
    # Test VIPs
    print("\n3. VIP Contacts:")
    print("-" * 80)
    vips = api.get_vips(limit=5)
    
    if vips:
        for vip in vips:
            print(f"  • {vip['name']} (score: {vip['importance_score']:.0f}/100)")
    else:
        print("  No VIPs yet (need relationship scores >= 70)")
    
    # Test pending tasks
    print("\n4. Pending Tasks:")
    print("-" * 80)
    tasks = api.get_pending_tasks(limit=3)
    
    for task in tasks:
        priority_emoji = {1: '🔴', 2: '🟡', 3: '🟢'}.get(task['priority'], '⚪')
        print(f"  {priority_emoji} {task['task_text']}")
    
    # Test inbox
    print("\n5. Smart Inbox (VIP only):")
    print("-" * 80)
    inbox = api.get_inbox(priority_level='vip', limit=5)
    
    if inbox:
        for email in inbox:
            print(f"  🔴 {email['from_name']}: {email['subject']}")
    else:
        print("  No VIP emails")
    
    print("\n" + "=" * 80)
    print("✅ API ready for FastAPI/Flask integration!")
