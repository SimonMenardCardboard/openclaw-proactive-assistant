#!/usr/bin/env python3
"""
Intelligence → Proactive Queue Integration

Connects intelligence layer (contacts, tasks, relationships)
to the proactive queue for user notifications.

Runs periodically to check for:
- VIP contact activity
- Urgent tasks
- Follow-up suggestions
- Relationship insights
"""

from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict
import sys

sys.path.insert(0, str(Path(__file__).parent))

from proactive_intelligence import ProactiveIntelligence
from proactive_queue import ProactiveQueue


class IntelligenceQueueBridge:
    """Bridge between intelligence layer and proactive queue."""
    
    def __init__(self):
        self.intelligence = ProactiveIntelligence()
        self.queue = ProactiveQueue()
    
    def push_urgent_tasks(self) -> int:
        """
        Push urgent tasks to queue.
        
        Returns:
            Number of tasks pushed
        """
        pending = self.intelligence.tasks.get_pending_tasks(limit=50, min_confidence=0.6)
        
        pushed = 0
        for task in pending:
            # Only push priority 1-2 (urgent/high)
            if task['priority'] <= 2:
                # Check if deadline is soon
                if task['deadline']:
                    deadline = datetime.fromisoformat(task['deadline']) if isinstance(task['deadline'], str) else task['deadline']
                    days_until = (deadline - datetime.now()).days
                    
                    if days_until <= 1:
                        # Urgent deadline
                        self.queue.add(
                            source='intelligence-tasks',
                            message=f"🚨 Urgent task: {task['title']} (due in {days_until} days)",
                            priority=1,
                            context={
                                'type': 'urgent_task',
                                'task_id': task['id'],
                                'deadline': str(deadline),
                                'contact': task.get('contact_email')
                            }
                        )
                        pushed += 1
                    elif days_until <= 3:
                        # High priority deadline
                        self.queue.add(
                            source='intelligence-tasks',
                            message=f"⚠️ Task due soon: {task['title']} (due in {days_until} days)",
                            priority=2,
                            context={
                                'type': 'high_priority_task',
                                'task_id': task['id'],
                                'deadline': str(deadline)
                            }
                        )
                        pushed += 1
        
        return pushed
    
    def push_follow_up_suggestions(self) -> int:
        """
        Push follow-up suggestions to queue.
        
        Returns:
            Number of suggestions pushed
        """
        followups = self.intelligence.scorer.get_follow_up_suggestions(
            days_threshold=14,
            min_score=70.0,  # Only high-importance contacts
            limit=10
        )
        
        pushed = 0
        for f in followups:
            days = f['days_since_contact']
            
            # Push suggestion
            self.queue.add(
                source='intelligence-followups',
                message=f"💬 Follow up with {f['email']} ({days} days since last contact)",
                priority=3,  # Normal priority
                context={
                    'type': 'follow_up',
                    'email': f['email'],
                    'importance': f['importance_score'],
                    'days_since': days
                }
            )
            pushed += 1
        
        return pushed
    
    def push_vip_alerts(self) -> int:
        """
        Push VIP contact alerts.
        
        Returns:
            Number of alerts pushed
        """
        vips = self.intelligence.scorer.get_vips(min_score=85.0, limit=5)
        
        # This would typically be triggered by new email/meeting from VIP
        # For now, just track VIPs (don't spam)
        
        return 0  # Don't push VIP alerts automatically
    
    def sync_intelligence_to_queue(self) -> Dict:
        """
        Full sync: push all intelligence to queue.
        
        Returns:
            Sync stats
        """
        print("🧠 Syncing intelligence → proactive queue...")
        
        # Push urgent tasks
        print("  📋 Checking urgent tasks...")
        tasks_pushed = self.push_urgent_tasks()
        
        # Push follow-ups
        print("  💬 Checking follow-ups...")
        followups_pushed = self.push_follow_up_suggestions()
        
        # VIPs (don't auto-push)
        vips_pushed = 0
        
        print(f"\n✅ Intelligence sync complete:")
        print(f"  • {tasks_pushed} urgent tasks")
        print(f"  • {followups_pushed} follow-ups")
        
        return {
            'tasks_pushed': tasks_pushed,
            'followups_pushed': followups_pushed,
            'vips_pushed': vips_pushed,
            'total': tasks_pushed + followups_pushed + vips_pushed
        }


def run_intelligence_sync():
    """Main entry point for periodic intelligence sync."""
    bridge = IntelligenceQueueBridge()
    result = bridge.sync_intelligence_to_queue()
    
    if result['total'] > 0:
        print(f"\n📬 Pushed {result['total']} recommendations to queue")
    else:
        print("\n✅ No new recommendations")
    
    return result


if __name__ == "__main__":
    run_intelligence_sync()
