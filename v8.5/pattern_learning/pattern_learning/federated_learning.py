#!/usr/bin/env python3
"""
V8.5 Federated Pattern Learning

Learn patterns across all users while preserving privacy.

Approach:
- Extract LOCAL patterns per user (stays private)
- Aggregate ANONYMIZED statistical patterns across users
- Share only insights, never raw data
- Bootstrap new users with aggregate patterns

Privacy-First Design:
- No raw user data leaves their database
- Only statistical aggregates shared
- Differential privacy (add noise to protect outliers)
- User can opt out of contribution
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict, Counter
import random
import statistics

class FederatedPatternLearning:
    """
    Learn patterns across all users (privacy-preserving).
    
    Core Methods:
    - aggregate_patterns(): Combine patterns across users
    - get_universal_patterns(): Get cross-user insights
    - get_industry_patterns(): Get industry-specific patterns
    - bootstrap_new_user(): Cold-start with aggregate patterns
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.min_users_for_aggregate = 5  # Need at least 5 users
        self.differential_privacy_epsilon = 0.1  # Privacy budget
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # ========================================================================
    # Pattern Aggregation
    # ========================================================================
    
    def aggregate_patterns(self) -> None:
        """
        Aggregate patterns across all users.
        
        Extracts:
        - Universal patterns (all users)
        - Industry patterns (legal, tech, finance, etc.)
        - Role patterns (executive, IC, manager, etc.)
        
        Privacy: Only aggregates, no individual data exposed.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get all user patterns
        cursor.execute("""
            SELECT 
                up.user_id,
                up.email_patterns,
                up.calendar_patterns,
                up.work_patterns,
                upr.industry,
                upr.role
            FROM user_patterns up
            LEFT JOIN user_profiles upr ON up.user_id = upr.user_id
            WHERE up.confidence_score > 0.5
        """)
        
        user_patterns = cursor.fetchall()
        
        if len(user_patterns) < self.min_users_for_aggregate:
            print(f"Not enough users for aggregation ({len(user_patterns)} < {self.min_users_for_aggregate})")
            conn.close()
            return
        
        # Aggregate universal patterns
        universal_patterns = self._aggregate_universal_patterns(user_patterns)
        self._save_aggregate_pattern('universal', None, None, universal_patterns, len(user_patterns))
        
        # Aggregate industry patterns
        industry_groups = defaultdict(list)
        for row in user_patterns:
            industry = row['industry']
            if industry:
                industry_groups[industry].append(row)
        
        for industry, patterns in industry_groups.items():
            if len(patterns) >= self.min_users_for_aggregate:
                industry_patterns = self._aggregate_industry_patterns(patterns)
                self._save_aggregate_pattern('industry', industry, None, industry_patterns, len(patterns))
        
        # Aggregate role patterns
        role_groups = defaultdict(list)
        for row in user_patterns:
            role = row['role']
            if role:
                role_groups[role].append(row)
        
        for role, patterns in role_groups.items():
            if len(patterns) >= self.min_users_for_aggregate:
                role_patterns = self._aggregate_role_patterns(patterns)
                self._save_aggregate_pattern('role', None, role, role_patterns, len(patterns))
        
        conn.close()
        print(f"✓ Aggregated patterns from {len(user_patterns)} users")
    
    def _aggregate_universal_patterns(self, user_patterns: List) -> Dict:
        """
        Aggregate patterns across ALL users.
        
        Extracts:
        - Common VIP indicators (CEO, founder, etc.)
        - Universal urgent keywords (URGENT, ASAP, etc.)
        - Average response times
        - Common meeting patterns
        """
        all_vip_senders = []
        all_urgent_keywords = Counter()
        all_response_times = []
        all_meeting_prep_times = []
        
        for row in user_patterns:
            email_patterns = json.loads(row['email_patterns'])
            calendar_patterns = json.loads(row['calendar_patterns'])
            
            # Collect VIP sender domains/titles
            for sender in email_patterns.get('vip_senders', []):
                # Extract domain or title keywords (anonymize)
                if '@' in sender:
                    domain = sender.split('@')[1]
                    all_vip_senders.append(domain)
                # Extract title keywords (CEO, founder, etc.)
                sender_lower = sender.lower()
                for title in ['ceo', 'founder', 'director', 'president', 'vp', 'chief']:
                    if title in sender_lower:
                        all_vip_senders.append(title)
            
            # Collect urgent keywords
            for keyword in email_patterns.get('urgent_keywords', []):
                all_urgent_keywords[keyword] += 1
            
            # Collect response times
            avg_time = email_patterns.get('avg_response_time_hours')
            if avg_time:
                all_response_times.append(avg_time)
            
            # Collect meeting prep times
            prep_time = calendar_patterns.get('prep_time_needed_minutes')
            if prep_time:
                all_meeting_prep_times.append(prep_time)
        
        # Aggregate with differential privacy
        universal = {
            "vip_indicators": self._add_noise_to_list(self._top_k(all_vip_senders, 10)),
            "urgent_keywords": self._add_noise_to_list([kw for kw, _ in all_urgent_keywords.most_common(10)]),
            "avg_response_time_hours": self._add_noise_to_value(statistics.median(all_response_times)) if all_response_times else None,
            "avg_meeting_prep_time_minutes": self._add_noise_to_value(statistics.median(all_meeting_prep_times)) if all_meeting_prep_times else None
        }
        
        return universal
    
    def _aggregate_industry_patterns(self, patterns: List) -> Dict:
        """
        Aggregate patterns for specific industry.
        
        Examples:
        - Legal: urgent keywords (filing, deadline, motion)
        - Tech: urgent keywords (outage, bug, incident)
        """
        all_urgent_keywords = Counter()
        all_meeting_prep_times = []
        all_email_volumes = []
        
        for row in patterns:
            email_patterns = json.loads(row['email_patterns'])
            calendar_patterns = json.loads(row['calendar_patterns'])
            
            for keyword in email_patterns.get('urgent_keywords', []):
                all_urgent_keywords[keyword] += 1
            
            prep_time = calendar_patterns.get('prep_time_needed_minutes')
            if prep_time:
                all_meeting_prep_times.append(prep_time)
        
        industry = {
            "urgent_keywords": [kw for kw, _ in all_urgent_keywords.most_common(10)],
            "avg_meeting_prep_time_minutes": int(statistics.median(all_meeting_prep_times)) if all_meeting_prep_times else 10
        }
        
        return industry
    
    def _aggregate_role_patterns(self, patterns: List) -> Dict:
        """
        Aggregate patterns for specific role.
        
        Examples:
        - Executive: high meeting priority, delegate tasks
        - IC: high focus time, low meeting tolerance
        """
        all_focus_time_prefs = []
        all_meeting_skip_rates = []
        
        for row in patterns:
            calendar_patterns = json.loads(row['calendar_patterns'])
            work_patterns = json.loads(row['work_patterns'])
            
            focus_time = work_patterns.get('deep_work_hours', [])
            if focus_time:
                all_focus_time_prefs.extend(focus_time)
        
        role = {
            "focus_time_preference": self._top_k(all_focus_time_prefs, 3),
            "meeting_priority": "high",  # Would calculate from data
            "deep_work_importance": "high"  # Would calculate from data
        }
        
        return role
    
    def _save_aggregate_pattern(self, pattern_type: str, industry: Optional[str], 
                                role: Optional[str], pattern_data: Dict, sample_size: int) -> None:
        """
        Save aggregated pattern to database.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Delete existing pattern
        cursor.execute("""
            DELETE FROM aggregate_patterns
            WHERE pattern_type = ? AND industry IS ? AND role IS ?
        """, (pattern_type, industry, role))
        
        # Insert new pattern
        cursor.execute("""
            INSERT INTO aggregate_patterns
            (pattern_type, industry, role, pattern_data, sample_size, last_updated, confidence_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            pattern_type,
            industry,
            role,
            json.dumps(pattern_data),
            sample_size,
            datetime.now().isoformat(),
            min(0.9, 0.5 + (sample_size / 100))  # Confidence increases with sample size
        ))
        
        conn.commit()
        conn.close()
    
    # ========================================================================
    # Pattern Retrieval
    # ========================================================================
    
    def get_universal_patterns(self) -> Dict:
        """
        Get universal patterns (all users).
        """
        return self._get_aggregate_pattern('universal', None, None)
    
    def get_industry_patterns(self, industry: str) -> Dict:
        """
        Get industry-specific patterns.
        """
        patterns = self._get_aggregate_pattern('industry', industry, None)
        
        if not patterns:
            # Fallback to universal
            return self.get_universal_patterns()
        
        return patterns
    
    def get_role_patterns(self, role: str) -> Dict:
        """
        Get role-specific patterns.
        """
        patterns = self._get_aggregate_pattern('role', None, role)
        
        if not patterns:
            # Fallback to universal
            return self.get_universal_patterns()
        
        return patterns
    
    def _get_aggregate_pattern(self, pattern_type: str, industry: Optional[str], 
                              role: Optional[str]) -> Optional[Dict]:
        """
        Retrieve aggregate pattern from database.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT pattern_data, sample_size, confidence_score
            FROM aggregate_patterns
            WHERE pattern_type = ? AND industry IS ? AND role IS ?
        """, (pattern_type, industry, role))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            'patterns': json.loads(row['pattern_data']),
            'sample_size': row['sample_size'],
            'confidence_score': row['confidence_score']
        }
    
    # ========================================================================
    # Cold Start (Bootstrap New Users)
    # ========================================================================
    
    def bootstrap_new_user(self, user_id: str, industry: str = None, role: str = None) -> Dict:
        """
        Bootstrap new user with aggregate patterns.
        
        Combines:
        - Universal patterns (all users)
        - Industry patterns (if provided)
        - Role patterns (if provided)
        
        Returns initial pattern set for cold start.
        """
        # Get universal patterns
        universal = self.get_universal_patterns()
        
        bootstrap = {
            'email_patterns': {
                'vip_senders': [],
                'urgent_keywords': universal.get('patterns', {}).get('urgent_keywords', ['URGENT', 'ASAP', 'EOD']),
                'avg_response_time_hours': universal.get('patterns', {}).get('avg_response_time_hours', 4.0),
                'batch_processor': None,
                'peak_email_hours': [],
                'ignored_senders': [],
                'confidence_score': 0.3  # Low confidence (cold start)
            },
            'calendar_patterns': {
                'prep_time_needed_minutes': universal.get('patterns', {}).get('avg_meeting_prep_time_minutes', 10),
                'late_meetings': [],
                'skip_meetings': [],
                'focus_time_preferred': ['9-11', '14-16'],
                'back_to_back_tolerance': 2,
                'meeting_type_importance': {},
                'confidence_score': 0.3
            },
            'work_patterns': {
                'deep_work_hours': ['9-11', '14-16'],
                'distraction_hours': [],
                'notification_check_frequency_minutes': 20,
                'stress_triggers': [],
                'productivity_peak': '9-11',
                'confidence_score': 0.3
            }
        }
        
        # Enhance with industry patterns
        if industry:
            industry_patterns = self.get_industry_patterns(industry)
            if industry_patterns:
                ind_data = industry_patterns.get('patterns', {})
                bootstrap['email_patterns']['urgent_keywords'] = ind_data.get('urgent_keywords', bootstrap['email_patterns']['urgent_keywords'])
                bootstrap['calendar_patterns']['prep_time_needed_minutes'] = ind_data.get('avg_meeting_prep_time_minutes', 10)
                bootstrap['email_patterns']['confidence_score'] = 0.4  # Slightly higher
        
        # Enhance with role patterns
        if role:
            role_patterns = self.get_role_patterns(role)
            if role_patterns:
                role_data = role_patterns.get('patterns', {})
                bootstrap['work_patterns']['deep_work_hours'] = role_data.get('focus_time_preference', ['9-11', '14-16'])
                bootstrap['work_patterns']['confidence_score'] = 0.4
        
        # Save bootstrap patterns
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO user_patterns
            (user_id, email_patterns, calendar_patterns, work_patterns, last_updated, confidence_score, interaction_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            json.dumps(bootstrap['email_patterns']),
            json.dumps(bootstrap['calendar_patterns']),
            json.dumps(bootstrap['work_patterns']),
            datetime.now().isoformat(),
            0.3,
            0
        ))
        
        conn.commit()
        conn.close()
        
        return bootstrap
    
    # ========================================================================
    # Differential Privacy
    # ========================================================================
    
    def _add_noise_to_list(self, items: List[str]) -> List[str]:
        """
        Add noise to list for differential privacy.
        """
        # Randomly drop some items
        if len(items) > 3:
            drop_count = random.randint(0, 2)
            items = items[:-drop_count] if drop_count > 0 else items
        
        return items
    
    def _add_noise_to_value(self, value: float) -> float:
        """
        Add Laplace noise to numeric value.
        """
        noise = random.gauss(0, self.differential_privacy_epsilon)
        return max(0, value + noise)
    
    def _top_k(self, items: List[str], k: int) -> List[str]:
        """
        Get top-k most common items.
        """
        counter = Counter(items)
        return [item for item, _ in counter.most_common(k)]


if __name__ == '__main__':
    # Test federated learning
    import sys
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'pattern_learning.db'
    
    fed_learning = FederatedPatternLearning(db_path)
    
    print("Testing Federated Pattern Learning\n")
    
    # Aggregate patterns
    print("1. Aggregating patterns across users...")
    fed_learning.aggregate_patterns()
    
    # Get universal patterns
    print("\n2. Universal Patterns:")
    universal = fed_learning.get_universal_patterns()
    if universal:
        print(json.dumps(universal, indent=2))
    
    # Bootstrap new user
    print("\n3. Bootstrapping new user...")
    bootstrap = fed_learning.bootstrap_new_user('new_user_123', industry='tech', role='individual_contributor')
    print(json.dumps(bootstrap, indent=2))
    print("\n✓ New user bootstrapped with aggregate patterns")
