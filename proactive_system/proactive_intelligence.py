#!/usr/bin/env python3
"""
Proactive Intelligence (Merged from vm_services/intelligence/)

Unified intelligence layer combining:
- Contact unification (fuzzy matching)
- Relationship scoring (behavioral learning)
- Task extraction (with confirm/dismiss)
- Follow-up suggestions

Integration point for all intelligence features.
"""

from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from relationship_scorer import RelationshipScorer
from contact_unifier import ContactUnifier
from task_extractor import TaskExtractor


class ProactiveIntelligence:
    """
    Master intelligence coordinator.
    
    Combines contact, task, and relationship intelligence
    into unified proactive suggestions.
    """
    
    def __init__(self, context_db_path: Optional[Path] = None):
        """
        Initialize intelligence system.
        
        Args:
            context_db_path: Path to context database
        """
        if context_db_path is None:
            context_db_path = Path(__file__).parent / "context.db"
        
        self.db_path = Path(context_db_path)
        
        # Initialize sub-systems
        self.scorer = RelationshipScorer(context_db_path)
        self.unifier = ContactUnifier(context_db_path)
        self.tasks = TaskExtractor()
    
    def get_intelligence_summary(self) -> Dict:
        """
        Get overview of all intelligence.
        
        Returns:
            Dict with VIPs, tasks, follow-ups
        """
        # Get VIP contacts
        vips = self.scorer.get_vips(min_score=70.0, limit=10)
        
        # Get pending tasks
        pending_tasks = self.tasks.get_pending_tasks(limit=20, min_confidence=0.6)
        
        # Get follow-up suggestions
        followups = self.scorer.get_follow_up_suggestions(
            days_threshold=14,
            min_score=60.0,
            limit=10
        )
        
        return {
            'vip_contacts': vips,
            'pending_tasks': pending_tasks,
            'follow_up_suggestions': followups,
            'summary': {
                'vip_count': len(vips),
                'task_count': len(pending_tasks),
                'followup_count': len(followups)
            }
        }
    
    def sync_all_contacts(self, account: str = "lacrosseguy76665@gmail.com", days: int = 90) -> Dict:
        """
        Sync contacts from all sources.
        
        Args:
            account: Email account
            days: Days to look back
            
        Returns:
            Sync stats
        """
        print("📧 Syncing contacts from email headers...")
        email_count = self.unifier.sync_from_email_headers(account, days)
        
        print("🔍 Finding duplicate contacts...")
        duplicates = self.unifier.find_duplicate_contacts(threshold=0.85)
        
        print(f"♻️  Merging {len(duplicates)} duplicate groups...")
        merged = 0
        for group in duplicates:
            self.unifier.merge_contacts(group)
            merged += 1
        
        print("📊 Recalculating relationship scores...")
        self.scorer.recalculate_all(days_lookback=days)
        
        return {
            'contacts_synced': email_count,
            'duplicates_merged': merged,
            'status': 'complete'
        }
    
    def extract_tasks_from_emails(self, account: str = "lacrosseguy76665@gmail.com", 
                                  days: int = 7) -> List[Dict]:
        """
        Extract tasks from recent emails.
        
        Args:
            account: Email account
            days: Days to look back
            
        Returns:
            List of extracted tasks
        """
        # Import email API
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        
        try:
            from universal_email_api import UniversalAccountManager
            
            manager = UniversalAccountManager()
            emails = manager.get_emails(account, days_back=days, max_results=100)
            
            all_tasks = []
            
            for email in emails:
                tasks = self.tasks.extract_from_message(email)
                all_tasks.extend(tasks)
            
            print(f"✅ Extracted {len(all_tasks)} tasks from {len(emails)} emails")
            return all_tasks
            
        except Exception as e:
            print(f"❌ Error extracting tasks: {e}")
            return []
    
    def get_actionable_suggestions(self) -> Dict:
        """
        Get all actionable suggestions for the user.
        
        Returns:
            Dict with categorized suggestions
        """
        intelligence = self.get_intelligence_summary()
        
        suggestions = {
            'urgent_tasks': [],
            'follow_ups': [],
            'vip_activity': []
        }
        
        # Urgent tasks (priority 1-2, deadline soon)
        for task in intelligence['pending_tasks']:
            if task['priority'] <= 2:
                suggestions['urgent_tasks'].append({
                    'type': 'urgent_task',
                    'title': task['title'],
                    'deadline': task['deadline'],
                    'task_id': task['id']
                })
        
        # Follow-ups (important contacts)
        for followup in intelligence['follow_up_suggestions']:
            if followup['days_since_contact'] >= 14:
                suggestions['follow_ups'].append({
                    'type': 'follow_up',
                    'email': followup['email'],
                    'days_since': followup['days_since_contact'],
                    'importance': followup['importance_score']
                })
        
        # VIP activity (contacts you should pay attention to)
        for vip in intelligence['vip_contacts'][:5]:
            suggestions['vip_activity'].append({
                'type': 'vip_contact',
                'email': vip['email'],
                'importance': vip['importance_score']
            })
        
        return suggestions


def run_full_sync():
    """Run complete intelligence sync."""
    print("🧠 Proactive Intelligence - Full Sync\n")
    
    intel = ProactiveIntelligence()
    
    # 1. Sync contacts
    print("=" * 60)
    print("STEP 1: Contact Sync")
    print("=" * 60)
    sync_result = intel.sync_all_contacts(days=90)
    print(f"\n✅ Synced {sync_result['contacts_synced']} contacts")
    print(f"✅ Merged {sync_result['duplicates_merged']} duplicates\n")
    
    # 2. Extract tasks
    print("=" * 60)
    print("STEP 2: Task Extraction")
    print("=" * 60)
    tasks = intel.extract_tasks_from_emails(days=7)
    print(f"\n✅ Extracted {len(tasks)} tasks\n")
    
    # 3. Get intelligence summary
    print("=" * 60)
    print("STEP 3: Intelligence Summary")
    print("=" * 60)
    summary = intel.get_intelligence_summary()
    
    print(f"\n🌟 VIP Contacts ({summary['summary']['vip_count']}):")
    for vip in summary['vip_contacts'][:5]:
        print(f"  • {vip['email']}: {vip['importance_score']:.1f}")
    
    print(f"\n📋 Pending Tasks ({summary['summary']['task_count']}):")
    for task in summary['pending_tasks'][:5]:
        print(f"  • {task['title']} (priority {task['priority']})")
    
    print(f"\n📬 Follow-up Suggestions ({summary['summary']['followup_count']}):")
    for f in summary['follow_up_suggestions'][:5]:
        print(f"  • {f['email']}: {f['days_since_contact']} days (score {f['importance_score']:.1f})")
    
    # 4. Get actionable suggestions
    print("\n" + "=" * 60)
    print("STEP 4: Actionable Suggestions")
    print("=" * 60)
    suggestions = intel.get_actionable_suggestions()
    
    print(f"\n🚨 Urgent Tasks ({len(suggestions['urgent_tasks'])}):")
    for s in suggestions['urgent_tasks'][:3]:
        print(f"  • {s['title']}")
    
    print(f"\n💬 Follow-ups ({len(suggestions['follow_ups'])}):")
    for s in suggestions['follow_ups'][:3]:
        print(f"  • Contact {s['email']} ({s['days_since']} days)")
    
    print("\n✅ Full intelligence sync complete!")


if __name__ == "__main__":
    run_full_sync()
