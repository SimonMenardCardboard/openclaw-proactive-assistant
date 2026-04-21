#!/usr/bin/env python3
"""
Chief of Staff V8 Integration Adapter

Integrates the new Chief of Staff intelligence (NLU, Relationships, Goals, Recommendations)
into the existing V8 meta-learning system.

New Pattern Sources:
- Email → Person → Relationship → Task (4-layer intelligence)
- Meeting → Attendees → Projects (multi-person context)
- Task progress → Blockers → Dependencies (goal intelligence)
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Add Chief of Staff modules to path
workspace_dir = Path.home() / "workspace" / "integrations" / "intelligence"
code_dir = Path.home() / ".openclaw" / "workspace" / "integrations" / "intelligence"

sys.path.insert(0, str(code_dir / "integration"))
sys.path.insert(0, str(code_dir / "proactive"))

try:
    from chief_of_staff_integration import ChiefOfStaffIntegration
    from recommendation_engine import RecommendationEngine, RecommendationType
    COS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Chief of Staff not available: {e}")
    COS_AVAILABLE = False


class ChiefOfStaffV8Adapter:
    """Adapter to feed Chief of Staff intelligence into V8 pattern detection."""
    
    def __init__(self):
        self.enabled = COS_AVAILABLE
        
        if self.enabled:
            try:
                self.cos = ChiefOfStaffIntegration()
                self.recommender = RecommendationEngine()
                print("✅ Chief of Staff integration enabled")
            except Exception as e:
                print(f"⚠️ Chief of Staff initialization failed: {e}")
                self.enabled = False
        else:
            print("ℹ️ Chief of Staff integration disabled (modules not available)")
    
    def analyze_email_intelligence(self, limit: int = 50) -> Dict:
        """Extract V8-compatible patterns from email/person data."""
        if not self.enabled:
            return {'patterns': [], 'source': 'chief_of_staff_email', 'count': 0}
        
        patterns = []
        
        try:
            # Get top relationships
            top_people = self.cos.relationships.get_top_relationships(limit=20)
            
            for person_data in top_people:
                person_id = person_data['person_id']
                person = self.cos.people.get_person(person_id)
                
                if not person:
                    continue
                
                # Get communication patterns
                freq = self.cos.comms.get_frequency_stats(person_id)
                comm_patterns = self.cos.comms.get_patterns(person_id)
                
                # Pattern 1: High-frequency communication (potential automation)
                if freq and freq.get('emails_per_week', 0) > 3:
                    patterns.append({
                        'type': 'high_frequency_communication',
                        'confidence': min(freq['emails_per_week'] / 10.0, 1.0),
                        'person': person['name'],
                        'person_id': person_id,
                        'frequency': freq['emails_per_week'],
                        'suggestion': f"Auto-categorize emails from {person['name']}",
                        'v8_category': 'email_workflow',
                        'automation_potential': 'high'
                    })
                
                # Pattern 2: Time-based communication preference
                if comm_patterns.get('time_preference'):
                    time_pref = comm_patterns['time_preference']
                    patterns.append({
                        'type': 'communication_timing',
                        'confidence': time_pref.get('confidence', 0.0),
                        'person': person['name'],
                        'person_id': person_id,
                        'preferred_time': time_pref.get('preferred'),
                        'suggestion': f"Send emails to {person['name']} during {time_pref.get('preferred')}",
                        'v8_category': 'scheduling',
                        'automation_potential': 'medium'
                    })
                
                # Pattern 3: Slow response times (follow-up reminder)
                if freq and freq.get('avg_response_time_minutes'):
                    avg_response = freq['avg_response_time_minutes']
                    if avg_response > 1440:  # > 1 day
                        patterns.append({
                            'type': 'slow_responder',
                            'confidence': 0.8,
                            'person': person['name'],
                            'person_id': person_id,
                            'avg_response_hours': avg_response / 60,
                            'suggestion': f"Auto-follow-up with {person['name']} after {int(avg_response/60)} hours",
                            'v8_category': 'follow_up',
                            'automation_potential': 'high'
                        })
            
        except Exception as e:
            print(f"Error analyzing email intelligence: {e}")
        
        return {
            'patterns': patterns,
            'source': 'chief_of_staff_email',
            'count': len(patterns),
            'timestamp': datetime.now().isoformat()
        }
    
    def analyze_goal_intelligence(self) -> Dict:
        """Extract V8-compatible patterns from goal/task data."""
        if not self.enabled:
            return {'patterns': [], 'source': 'chief_of_staff_goals', 'count': 0}
        
        patterns = []
        
        try:
            # Get active tasks
            active_tasks = self.cos.goals.get_active_tasks(limit=50)
            
            # Pattern 1: Recurring task titles (automation opportunity)
            task_titles = {}
            for task in active_tasks:
                # Extract base title (remove dates, numbers)
                base_title = task['title'].lower()
                task_titles[base_title] = task_titles.get(base_title, 0) + 1
            
            for title, count in task_titles.items():
                if count >= 3:  # Appears 3+ times
                    patterns.append({
                        'type': 'recurring_task',
                        'confidence': min(count / 10.0, 1.0),
                        'task_title': title,
                        'occurrence_count': count,
                        'suggestion': f"Create template for '{title}'",
                        'v8_category': 'task_automation',
                        'automation_potential': 'high'
                    })
            
            # Pattern 2: Blocked tasks (dependency bottleneck)
            blocked = self.cos.goals.get_blocked_items()
            if len(blocked) > 2:
                patterns.append({
                    'type': 'blocker_bottleneck',
                    'confidence': 0.9,
                    'blocked_count': len(blocked),
                    'suggestion': "Review blocked tasks for dependency optimization",
                    'v8_category': 'workflow_optimization',
                    'automation_potential': 'medium'
                })
            
            # Pattern 3: Overdue tasks (priority/deadline management)
            overdue = self.cos.goals.get_overdue_items()
            if len(overdue) > 3:
                patterns.append({
                    'type': 'deadline_management',
                    'confidence': 0.8,
                    'overdue_count': len(overdue),
                    'suggestion': "Auto-adjust deadlines or reprioritize",
                    'v8_category': 'priority_management',
                    'automation_potential': 'high'
                })
            
            # Pattern 4: Task mapping success rate
            # Count how many activities are successfully mapped
            # (This would require tracking, placeholder for now)
            
        except Exception as e:
            print(f"Error analyzing goal intelligence: {e}")
        
        return {
            'patterns': patterns,
            'source': 'chief_of_staff_goals',
            'count': len(patterns),
            'timestamp': datetime.now().isoformat()
        }
    
    def get_proactive_recommendations(self, event_type: str, event_data: Dict) -> List[Dict]:
        """Generate proactive recommendations for V8 to surface."""
        if not self.enabled:
            return []
        
        try:
            # Route to appropriate recommendation generator
            if event_type == 'email_received':
                return self.recommender.on_email_received(**event_data)
            
            elif event_type == 'meeting_scheduled':
                return self.recommender.on_meeting_scheduled(**event_data)
            
            elif event_type == 'task_updated':
                return self.recommender.on_task_updated(**event_data)
            
            elif event_type == 'deadline_check':
                return self.recommender.on_deadline_approaching()
            
            elif event_type == 'activity_detected':
                return self.recommender.on_activity_detected(**event_data)
            
            else:
                return []
        
        except Exception as e:
            print(f"Error generating recommendations: {e}")
            return []
    
    def get_v8_compatible_patterns(self) -> Dict:
        """
        Get all Chief of Staff patterns in V8-compatible format.
        Called by auto_optimizer.py to include COS intelligence.
        """
        all_patterns = {
            'timestamp': datetime.now().isoformat(),
            'sources': [],
            'total_patterns': 0
        }
        
        # Email/relationship intelligence
        email_intel = self.analyze_email_intelligence()
        all_patterns['sources'].append(email_intel)
        all_patterns['total_patterns'] += email_intel['count']
        
        # Goal/task intelligence
        goal_intel = self.analyze_goal_intelligence()
        all_patterns['sources'].append(goal_intel)
        all_patterns['total_patterns'] += goal_intel['count']
        
        return all_patterns
    
    def process_v6_action_with_cos(self, action_type: str, action_data: Dict) -> Optional[Dict]:
        """
        Process V6 executor action through Chief of Staff intelligence.
        Returns enriched context + recommendations.
        """
        if not self.enabled:
            return None
        
        enrichment = {
            'action_type': action_type,
            'timestamp': datetime.now().isoformat(),
            'people_context': [],
            'task_context': [],
            'recommendations': []
        }
        
        try:
            # Email-related actions
            if 'email' in action_type.lower():
                # Extract email metadata
                sender_email = action_data.get('sender_email')
                if sender_email:
                    person_id = self.cos.people.find_person_by_email(sender_email)
                    if person_id:
                        person = self.cos.people.get_person(person_id)
                        freq = self.cos.comms.get_frequency_stats(person_id)
                        score = self.cos.relationships.calculate_score(person_id)
                        
                        enrichment['people_context'].append({
                            'person_id': person_id,
                            'name': person['name'],
                            'company': person.get('company'),
                            'relationship_score': score,
                            'emails_per_week': freq.get('emails_per_week', 0) if freq else 0
                        })
                
                # Generate recommendations
                if sender_email and action_data.get('subject'):
                    recs = self.recommender.on_email_received(
                        sender_email=sender_email,
                        sender_name=action_data.get('sender_name', 'Unknown'),
                        subject=action_data.get('subject', ''),
                        body=action_data.get('body', '')
                    )
                    enrichment['recommendations'] = recs
            
            # Task-related actions
            elif 'task' in action_type.lower():
                task_id = action_data.get('task_id')
                if task_id:
                    task = self.cos.goals.get_item(task_id)
                    if task:
                        enrichment['task_context'].append({
                            'task_id': task_id,
                            'title': task['title'],
                            'progress': task['progress_percentage'],
                            'status': task['status']
                        })
        
        except Exception as e:
            print(f"Error processing V6 action with COS: {e}")
        
        return enrichment if (enrichment['people_context'] or 
                             enrichment['task_context'] or 
                             enrichment['recommendations']) else None


def integrate_with_v8():
    """
    Integration point for V8 auto_optimizer.py
    
    Add this to auto_optimizer.py:
    
    from chief_of_staff_adapter import ChiefOfStaffV8Adapter
    
    cos_adapter = ChiefOfStaffV8Adapter()
    
    # In the pattern detection loop:
    cos_patterns = cos_adapter.get_v8_compatible_patterns()
    all_patterns['sources'].append(cos_patterns)
    """
    
    adapter = ChiefOfStaffV8Adapter()
    
    if adapter.enabled:
        print("\n=== Chief of Staff V8 Integration Test ===\n")
        
        # Test pattern extraction
        print("1. Email/Relationship Patterns:")
        email_patterns = adapter.analyze_email_intelligence(limit=10)
        print(f"   Found {email_patterns['count']} patterns")
        for pattern in email_patterns['patterns'][:3]:
            print(f"   - {pattern['type']}: {pattern['suggestion']}")
        
        print("\n2. Goal/Task Patterns:")
        goal_patterns = adapter.analyze_goal_intelligence()
        print(f"   Found {goal_patterns['count']} patterns")
        for pattern in goal_patterns['patterns'][:3]:
            print(f"   - {pattern['type']}: {pattern['suggestion']}")
        
        print("\n3. V8-Compatible Output:")
        v8_patterns = adapter.get_v8_compatible_patterns()
        print(f"   Total patterns: {v8_patterns['total_patterns']}")
        print(f"   Sources: {len(v8_patterns['sources'])}")
        
        print("\n✅ Chief of Staff V8 integration ready")
        print("\nNext steps:")
        print("1. Add import to auto_optimizer.py:")
        print("   from chief_of_staff_adapter import ChiefOfStaffV8Adapter")
        print("2. Initialize in auto_optimizer.py:")
        print("   cos_adapter = ChiefOfStaffV8Adapter()")
        print("3. Add to pattern sources:")
        print("   cos_patterns = cos_adapter.get_v8_compatible_patterns()")
    
    else:
        print("❌ Chief of Staff integration unavailable")


if __name__ == "__main__":
    integrate_with_v8()
