#!/usr/bin/env python3
"""
V8 Pattern Prioritization - Phase 5

Score patterns by potential impact and prioritize deployment.

Scoring factors:
1. Frequency (how often does this pattern occur?)
2. Time savings (how much time saved per use?)
3. Confidence (how sure are we this is a real pattern?)
4. Complexity (simple patterns = lower risk)

Output: Ranked list of patterns by priority score (0-100)
"""

import sys
from pathlib import Path
from typing import Dict, List
from datetime import datetime


class PatternPrioritizer:
    """Calculate priority scores for optimization patterns"""
    
    # Weights for scoring factors (must sum to 1.0)
    WEIGHTS = {
        'frequency': 0.40,      # 40% - How often it happens
        'time_savings': 0.30,   # 30% - Impact per use
        'confidence': 0.20,     # 20% - Pattern reliability
        'complexity': 0.10      # 10% - Risk factor
    }
    
    # Complexity scores by pattern type (higher = simpler/safer)
    COMPLEXITY_SCORES = {
        'command_retry': 10,          # Very simple, low risk
        'email_template': 10,
        'email_shortcut': 10,
        'deduplication': 9,
        'cache_operation': 8,
        'dir_navigation': 8,
        'log_rotation': 7,
        'disk_cleanup': 7,
        'screenshot_organizer': 7,
        'download_cleaner': 7,
        'multi_command': 6,           # Medium complexity
        'workflow_sequence': 6,
        'test_runner': 6,
        'linter_precommit': 6,
        'dependency_update': 5,
        'pomodoro_timer': 5,
        'daily_standup': 5,
        'build_optimization': 4,      # More complex
        'service_restart': 4,
        'health_check': 4,
        'backup_automation': 3,
        'hot_reload': 3,
        'focus_mode': 3,
        'context_switch': 2,          # High complexity
        'duplicate_finder': 2,
        'smart_archiving': 2,
        'file_deduplication': 1,
    }
    
    def calculate_priority(self, pattern: Dict) -> Dict:
        """
        Calculate priority score for a pattern.
        
        Args:
            pattern: {
                'type': str,
                'count': int (occurrences),
                'observation_weeks': int,
                'confidence': float (0-1),
                'estimated_savings_seconds': float,
                ...
            }
        
        Returns:
            {
                'priority_score': float (0-100),
                'frequency_score': float (0-100),
                'time_savings_score': float (0-100),
                'confidence_score': float (0-100),
                'complexity_score': float (0-100),
                'rank': int (set later),
                'recommendation': str
            }
        """
        # Calculate individual scores
        frequency_score = self._score_frequency(pattern)
        time_savings_score = self._score_time_savings(pattern)
        confidence_score = self._score_confidence(pattern)
        complexity_score = self._score_complexity(pattern)
        
        # Weighted total
        priority_score = (
            frequency_score * self.WEIGHTS['frequency'] +
            time_savings_score * self.WEIGHTS['time_savings'] +
            confidence_score * self.WEIGHTS['confidence'] +
            complexity_score * self.WEIGHTS['complexity']
        )
        
        # Generate recommendation
        recommendation = self._get_recommendation(priority_score, pattern)
        
        return {
            'priority_score': priority_score,
            'frequency_score': frequency_score,
            'time_savings_score': time_savings_score,
            'confidence_score': confidence_score,
            'complexity_score': complexity_score,
            'rank': None,  # Set later during sorting
            'recommendation': recommendation
        }
    
    def _score_frequency(self, pattern: Dict) -> float:
        """Score based on how often pattern occurs (0-100)"""
        count = pattern.get('count', pattern.get('occurrences', 0))
        observation_weeks = pattern.get('observation_weeks', 1)
        
        # Calculate occurrences per week
        weekly_freq = count / observation_weeks if observation_weeks > 0 else count
        
        # Scoring scale:
        # 20+/week = 100 points
        # 10/week = 70 points
        # 5/week = 50 points
        # 1/week = 20 points
        # <1/week = 10 points
        
        if weekly_freq >= 20:
            return 100
        elif weekly_freq >= 10:
            return 70 + (weekly_freq - 10) * 3  # 70-100
        elif weekly_freq >= 5:
            return 50 + (weekly_freq - 5) * 4   # 50-70
        elif weekly_freq >= 1:
            return 20 + (weekly_freq - 1) * 7.5 # 20-50
        else:
            return 10 + weekly_freq * 10        # 0-20
    
    def _score_time_savings(self, pattern: Dict) -> float:
        """Score based on time saved per use (0-100)"""
        # Try multiple field names for time savings
        savings_seconds = pattern.get('estimated_savings_seconds', 
                          pattern.get('estimated_per_use_seconds', 0))
        
        # If not found, try to estimate from pattern type
        if savings_seconds == 0:
            savings_seconds = self._estimate_savings_from_type(pattern.get('type'))
        
        # Scoring scale:
        # 300+ sec (5+ min) = 100 points
        # 120 sec (2 min) = 80 points
        # 60 sec (1 min) = 60 points
        # 30 sec = 40 points
        # 10 sec = 20 points
        # <10 sec = 10 points
        
        if savings_seconds >= 300:
            return 100
        elif savings_seconds >= 120:
            return 80 + (savings_seconds - 120) / 180 * 20  # 80-100
        elif savings_seconds >= 60:
            return 60 + (savings_seconds - 60) / 60 * 20    # 60-80
        elif savings_seconds >= 30:
            return 40 + (savings_seconds - 30) / 30 * 20    # 40-60
        elif savings_seconds >= 10:
            return 20 + (savings_seconds - 10) / 20 * 20    # 20-40
        else:
            return 10 + savings_seconds * 1                 # 0-20
    
    def _estimate_savings_from_type(self, pattern_type: str) -> float:
        """Estimate time savings based on pattern type (fallback)"""
        estimates = {
            'command_retry': 40,
            'email_template': 180,
            'email_shortcut': 15,
            'email_schedule': 300,
            'focus_block': 3600,
            'meeting_automation': 600,
            'multi_command': 30,
            'workflow_sequence': 45,
            'log_rotation': 60,
            'disk_cleanup': 120,
            'service_restart': 180,
            'health_check': 300,
            'backup_automation': 600,
            'test_runner': 300,
            'linter_precommit': 180,
            'dependency_update': 120,
            'build_optimization': 600,
            'hot_reload': 600,
            'focus_mode': 1800,
            'context_switch': 120,
            'pomodoro_timer': 1500,
            'daily_standup': 300,
            'duplicate_finder': 300,
            'smart_archiving': 180,
            'screenshot_organizer': 60,
            'download_cleaner': 120,
            'file_deduplication': 600
        }
        
        return estimates.get(pattern_type, 30)  # Default: 30 seconds
    
    def _score_confidence(self, pattern: Dict) -> float:
        """Score based on pattern confidence (0-100)"""
        confidence = pattern.get('confidence', 0.0)
        
        # Convert 0-1 confidence to 0-100 score
        # Apply slight curve to reward high confidence
        score = confidence * 100
        
        if confidence >= 0.95:
            score = 95 + (confidence - 0.95) * 100  # 95-100
        elif confidence >= 0.85:
            score = 85 + (confidence - 0.85) * 100  # 85-95
        
        return min(score, 100)
    
    def _score_complexity(self, pattern: Dict) -> float:
        """Score based on implementation complexity (0-100)"""
        pattern_type = pattern.get('type', 'unknown')
        
        # Get base complexity score (0-10)
        base_score = self.COMPLEXITY_SCORES.get(pattern_type, 5)
        
        # Convert to 0-100 scale
        return base_score * 10
    
    def _get_recommendation(self, priority_score: float, pattern: Dict) -> str:
        """Generate deployment recommendation based on priority score"""
        if priority_score >= 80:
            return "🟢 DEPLOY NOW - High impact, low risk"
        elif priority_score >= 70:
            return "🟡 DEPLOY SOON - Good candidate"
        elif priority_score >= 60:
            return "🟡 REVIEW - Moderate priority"
        elif priority_score >= 50:
            return "🟠 LOW PRIORITY - Deploy if capacity allows"
        else:
            return "🔴 SKIP - Low impact or high risk"
    
    def prioritize_patterns(self, patterns: List[Dict]) -> List[Dict]:
        """
        Score and rank all patterns by priority.
        
        Args:
            patterns: List of pattern dicts
        
        Returns:
            List of patterns with priority scores, sorted by score (descending)
        """
        # Calculate priority for each pattern
        scored = []
        for pattern in patterns:
            priority = self.calculate_priority(pattern)
            
            scored.append({
                'pattern': pattern,
                **priority
            })
        
        # Sort by priority score (descending)
        scored.sort(key=lambda x: x['priority_score'], reverse=True)
        
        # Assign ranks
        for i, item in enumerate(scored, 1):
            item['rank'] = i
        
        return scored
    
    def get_deploy_candidates(self, patterns: List[Dict], threshold: float = 70.0) -> List[Dict]:
        """
        Get patterns that should be deployed (priority >= threshold).
        
        Args:
            patterns: List of pattern dicts
            threshold: Minimum priority score (default: 70)
        
        Returns:
            List of patterns meeting threshold, sorted by priority
        """
        scored = self.prioritize_patterns(patterns)
        
        return [p for p in scored if p['priority_score'] >= threshold]
    
    def print_report(self, patterns: List[Dict], show_all: bool = False):
        """Print prioritization report"""
        scored = self.prioritize_patterns(patterns)
        
        print("\n" + "="*80)
        print("📊 V8 PATTERN PRIORITIZATION REPORT")
        print("="*80)
        print(f"\nTotal patterns analyzed: {len(scored)}")
        
        deploy_now = [p for p in scored if p['priority_score'] >= 80]
        deploy_soon = [p for p in scored if 70 <= p['priority_score'] < 80]
        review = [p for p in scored if 60 <= p['priority_score'] < 70]
        low_priority = [p for p in scored if 50 <= p['priority_score'] < 60]
        skip = [p for p in scored if p['priority_score'] < 50]
        
        print(f"  🟢 Deploy now (≥80): {len(deploy_now)}")
        print(f"  🟡 Deploy soon (70-79): {len(deploy_soon)}")
        print(f"  🟡 Review (60-69): {len(review)}")
        print(f"  🟠 Low priority (50-59): {len(low_priority)}")
        print(f"  🔴 Skip (<50): {len(skip)}")
        
        print("\n" + "-"*80)
        print("TOP PATTERNS BY PRIORITY")
        print("-"*80)
        
        display_count = len(scored) if show_all else min(10, len(scored))
        
        for item in scored[:display_count]:
            pattern = item['pattern']
            print(f"\n#{item['rank']}. {pattern.get('type', 'unknown')} "
                  f"(Score: {item['priority_score']:.0f}/100)")
            print(f"   {item['recommendation']}")
            print(f"   Breakdown:")
            print(f"     • Frequency: {item['frequency_score']:.0f}/100 "
                  f"(weight: {self.WEIGHTS['frequency']:.0%})")
            print(f"     • Time savings: {item['time_savings_score']:.0f}/100 "
                  f"(weight: {self.WEIGHTS['time_savings']:.0%})")
            print(f"     • Confidence: {item['confidence_score']:.0f}/100 "
                  f"(weight: {self.WEIGHTS['confidence']:.0%})")
            print(f"     • Complexity: {item['complexity_score']:.0f}/100 "
                  f"(weight: {self.WEIGHTS['complexity']:.0%})")
        
        if not show_all and len(scored) > display_count:
            print(f"\n... and {len(scored) - display_count} more patterns")
            print("(Use --all to show complete list)")


# CLI interface
if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="V8 Pattern Prioritization")
    parser.add_argument('--patterns-file', help='JSON file with patterns')
    parser.add_argument('--threshold', type=float, default=70.0,
                       help='Minimum priority score for deployment (default: 70)')
    parser.add_argument('--all', action='store_true',
                       help='Show all patterns (not just top 10)')
    parser.add_argument('--test', action='store_true',
                       help='Run with test data')
    
    args = parser.parse_args()
    
    prioritizer = PatternPrioritizer()
    
    if args.test:
        # Test data
        test_patterns = [
            {
                'type': 'command_retry',
                'count': 15,
                'observation_weeks': 1,
                'confidence': 0.92,
                'estimated_savings_seconds': 40
            },
            {
                'type': 'email_template',
                'count': 8,
                'observation_weeks': 1,
                'confidence': 0.88,
                'estimated_savings_seconds': 180
            },
            {
                'type': 'hot_reload',
                'count': 25,
                'observation_weeks': 1,
                'confidence': 0.85,
                'estimated_savings_seconds': 600
            },
            {
                'type': 'file_deduplication',
                'count': 2,
                'observation_weeks': 4,
                'confidence': 0.75,
                'estimated_savings_seconds': 600
            },
            {
                'type': 'log_rotation',
                'count': 12,
                'observation_weeks': 1,
                'confidence': 0.90,
                'estimated_savings_seconds': 60
            }
        ]
        
        prioritizer.print_report(test_patterns, show_all=args.all)
        
        print("\n" + "="*80)
        print(f"DEPLOY CANDIDATES (threshold: {args.threshold})")
        print("="*80)
        
        candidates = prioritizer.get_deploy_candidates(test_patterns, args.threshold)
        
        if candidates:
            for item in candidates:
                print(f"  ✅ {item['pattern']['type']} "
                      f"(priority: {item['priority_score']:.0f})")
        else:
            print(f"  No patterns meet threshold of {args.threshold}")
    
    elif args.patterns_file:
        with open(args.patterns_file) as f:
            patterns = json.load(f)
        
        prioritizer.print_report(patterns, show_all=args.all)
    
    else:
        parser.print_help()
