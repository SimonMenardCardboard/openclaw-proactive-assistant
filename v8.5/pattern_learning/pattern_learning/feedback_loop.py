#!/usr/bin/env python3
"""
V8.5 Feedback Loop

Close the loop: track recommendation effectiveness and adapt patterns.
Learning cycle:
1. User acts on recommendation (click/dismiss/snooze/complete)
2. Record feedback
3. Update pattern models
4. Measure improvement
5. Repeat

This is what makes the system LEARN from experience.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import statistics

class FeedbackLoop:
    """
    Track recommendation effectiveness and continuously improve.
    
    Core Methods:
    - record_feedback(): Track user action on recommendation
    - update_patterns(): Re-learn patterns from new feedback
    - measure_effectiveness(): Calculate recommendation quality
    - run_ab_test(): Test recommendation variants
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # ========================================================================
    # Feedback Recording
    # ========================================================================
    
    def record_feedback(self, user_id: str, recommendation_id: str, action: str, context: Dict = None) -> None:
        """
        Record user action on recommendation.
        
        Args:
            user_id: User identifier
            recommendation_id: Unique recommendation ID
            action: 'shown' | 'clicked' | 'dismissed' | 'snoozed' | 'completed' | 'ignored'
            context: Optional context data
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        
        if action == 'shown':
            # New recommendation shown
            cursor.execute("""
                INSERT INTO recommendation_effectiveness
                (user_id, recommendation_id, recommendation_type, priority_score, shown_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                user_id,
                recommendation_id,
                context.get('type', 'unknown') if context else 'unknown',
                context.get('priority', 0.5) if context else 0.5,
                timestamp
            ))
        else:
            # Update existing recommendation
            field_map = {
                'clicked': 'clicked_at',
                'dismissed': 'dismissed_at',
                'snoozed': 'snoozed_at',
                'completed': 'completed_at'
            }
            
            if action in field_map:
                field = field_map[action]
                
                # Calculate time to action
                cursor.execute("""
                    SELECT shown_at FROM recommendation_effectiveness
                    WHERE recommendation_id = ?
                """, (recommendation_id,))
                row = cursor.fetchone()
                
                if row:
                    shown_at = datetime.fromisoformat(row['shown_at'])
                    time_to_action = (datetime.now() - shown_at).total_seconds()
                    
                    cursor.execute(f"""
                        UPDATE recommendation_effectiveness
                        SET {field} = ?, time_to_action = ?
                        WHERE recommendation_id = ?
                    """, (timestamp, int(time_to_action), recommendation_id))
                    
                    # Calculate effectiveness score
                    effectiveness = self._calculate_effectiveness(action, time_to_action)
                    cursor.execute("""
                        UPDATE recommendation_effectiveness
                        SET effectiveness_score = ?
                        WHERE recommendation_id = ?
                    """, (effectiveness, recommendation_id))
        
        conn.commit()
        
        # Also record as user interaction
        cursor.execute("""
            INSERT INTO user_interactions
            (user_id, event_type, event_data, timestamp, session_id)
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            f'recommendation_{action}',
            json.dumps({
                'recommendation_id': recommendation_id,
                'action': action,
                **(context or {})
            }),
            timestamp,
            context.get('session_id') if context else None
        ))
        
        conn.commit()
        conn.close()
    
    def _calculate_effectiveness(self, action: str, time_to_action: float) -> float:
        """
        Calculate effectiveness score based on action and timing.
        
        Returns: 0.0 - 1.0
        """
        base_scores = {
            'clicked': 0.8,
            'completed': 1.0,
            'snoozed': 0.5,
            'dismissed': 0.2,
            'ignored': 0.0
        }
        
        score = base_scores.get(action, 0.5)
        
        # Bonus for fast action (< 5 min)
        if action in ['clicked', 'completed'] and time_to_action < 300:
            score += 0.1
        
        # Penalty for slow action (> 1 hour)
        if time_to_action > 3600:
            score -= 0.1
        
        return max(0.0, min(1.0, score))
    
    # ========================================================================
    # Pattern Updates
    # ========================================================================
    
    def update_patterns(self, user_id: str) -> None:
        """
        Re-analyze patterns based on new feedback.
        
        Examples:
        - User always dismisses "newsletter" → deprioritize
        - User always clicks from "boss" → mark as VIP
        - User never acts during "focus time" → adjust timing
        """
        from pattern_analyzer import UserPatternAnalyzer
        
        # Re-run pattern analysis
        analyzer = UserPatternAnalyzer(self.db_path)
        analyzer.save_patterns(user_id)
        
        # Update pattern metrics
        self._update_pattern_metrics(user_id)
    
    def _update_pattern_metrics(self, user_id: str) -> None:
        """
        Calculate and store pattern accuracy metrics.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # VIP detection accuracy
        vip_accuracy = self._measure_vip_accuracy(user_id)
        if vip_accuracy is not None:
            cursor.execute("""
                INSERT INTO pattern_metrics
                (user_id, metric_type, metric_value, measured_at)
                VALUES (?, ?, ?, ?)
            """, (user_id, 'vip_accuracy', vip_accuracy, datetime.now().isoformat()))
        
        # Priority prediction accuracy
        priority_accuracy = self._measure_priority_accuracy(user_id)
        if priority_accuracy is not None:
            cursor.execute("""
                INSERT INTO pattern_metrics
                (user_id, metric_type, metric_value, measured_at)
                VALUES (?, ?, ?, ?)
            """, (user_id, 'priority_accuracy', priority_accuracy, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def _measure_vip_accuracy(self, user_id: str) -> Optional[float]:
        """
        Measure how accurately we detect VIP senders.
        
        Returns: 0.0 - 1.0 accuracy
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get detected VIPs
        cursor.execute("""
            SELECT email_patterns FROM user_patterns WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        
        email_patterns = json.loads(row['email_patterns'])
        detected_vips = set(email_patterns.get('vip_senders', []))
        
        if not detected_vips:
            conn.close()
            return None
        
        # Measure: Are emails from detected VIPs actually clicked more?
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN json_extract(event_data, '$.sender') IN ({})
                    THEN 'vip' ELSE 'non_vip'
                END as sender_type,
                AVG(CASE WHEN clicked_at IS NOT NULL THEN 1.0 ELSE 0.0 END) as click_rate
            FROM recommendation_effectiveness re
            WHERE user_id = ? AND recommendation_type = 'email'
            GROUP BY sender_type
        """.format(','.join('?' * len(detected_vips))), (*detected_vips, user_id))
        
        results = {row['sender_type']: row['click_rate'] for row in cursor.fetchall()}
        conn.close()
        
        if 'vip' in results and 'non_vip' in results:
            # VIP accuracy = how much better VIP click rate is
            vip_click = results['vip']
            non_vip_click = results['non_vip']
            
            if non_vip_click > 0:
                accuracy = min(1.0, vip_click / (non_vip_click + 0.1))
                return accuracy
        
        return None
    
    def _measure_priority_accuracy(self, user_id: str) -> Optional[float]:
        """
        Measure how accurately we predict priority.
        
        Returns: 0.0 - 1.0 accuracy
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get recommendations with priority scores and outcomes
        cursor.execute("""
            SELECT 
                priority_score,
                CASE 
                    WHEN clicked_at IS NOT NULL OR completed_at IS NOT NULL THEN 1
                    WHEN dismissed_at IS NOT NULL THEN 0
                    ELSE NULL
                END as actual_priority
            FROM recommendation_effectiveness
            WHERE user_id = ? AND priority_score IS NOT NULL
        """, (user_id,))
        
        predictions = []
        actuals = []
        
        for row in cursor.fetchall():
            if row['actual_priority'] is not None:
                predictions.append(row['priority_score'])
                actuals.append(row['actual_priority'])
        
        conn.close()
        
        if len(predictions) < 10:
            return None
        
        # Calculate correlation between predicted and actual priority
        # Simplified: percentage of high-priority recs that were acted upon
        high_priority_recs = sum(1 for p in predictions if p > 0.7)
        if high_priority_recs == 0:
            return None
        
        high_priority_correct = sum(1 for p, a in zip(predictions, actuals) if p > 0.7 and a == 1)
        accuracy = high_priority_correct / high_priority_recs
        
        return accuracy
    
    # ========================================================================
    # Effectiveness Measurement
    # ========================================================================
    
    def measure_effectiveness(self, user_id: str, days: int = 7) -> Dict:
        """
        Measure recommendation effectiveness for this user.
        
        Returns:
        {
            "click_rate": 0.35,
            "dismiss_rate": 0.50,
            "snooze_rate": 0.15,
            "avg_time_to_action_seconds": 312,
            "top_effective_types": ["email_vip", "meeting_prep"],
            "least_effective_types": ["newsletter", "calendar_all_day"],
            "improvement_trend": "+12%"  # vs previous period
        }
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(days=days)).isoformat()
        
        # Overall rates
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN clicked_at IS NOT NULL THEN 1 ELSE 0 END) as clicked,
                SUM(CASE WHEN dismissed_at IS NOT NULL THEN 1 ELSE 0 END) as dismissed,
                SUM(CASE WHEN snoozed_at IS NOT NULL THEN 1 ELSE 0 END) as snoozed,
                AVG(time_to_action) as avg_time,
                AVG(effectiveness_score) as avg_effectiveness
            FROM recommendation_effectiveness
            WHERE user_id = ? AND shown_at >= ?
        """, (user_id, since))
        
        row = cursor.fetchone()
        
        metrics = {
            "click_rate": row['clicked'] / row['total'] if row['total'] > 0 else 0.0,
            "dismiss_rate": row['dismissed'] / row['total'] if row['total'] > 0 else 0.0,
            "snooze_rate": row['snoozed'] / row['total'] if row['total'] > 0 else 0.0,
            "avg_time_to_action_seconds": int(row['avg_time']) if row['avg_time'] else 0,
            "avg_effectiveness": round(row['avg_effectiveness'], 2) if row['avg_effectiveness'] else 0.0,
            "top_effective_types": [],
            "least_effective_types": [],
            "improvement_trend": None
        }
        
        # Effectiveness by type
        cursor.execute("""
            SELECT 
                recommendation_type,
                AVG(effectiveness_score) as avg_effectiveness,
                COUNT(*) as count
            FROM recommendation_effectiveness
            WHERE user_id = ? AND shown_at >= ? AND effectiveness_score IS NOT NULL
            GROUP BY recommendation_type
            HAVING count >= 3
            ORDER BY avg_effectiveness DESC
        """, (user_id, since))
        
        type_effectiveness = cursor.fetchall()
        
        if len(type_effectiveness) >= 2:
            metrics["top_effective_types"] = [row['recommendation_type'] for row in type_effectiveness[:2]]
            metrics["least_effective_types"] = [row['recommendation_type'] for row in type_effectiveness[-2:]]
        
        # Improvement trend (compare to previous period)
        previous_since = (datetime.now() - timedelta(days=days*2)).isoformat()
        cursor.execute("""
            SELECT AVG(effectiveness_score) as avg_effectiveness
            FROM recommendation_effectiveness
            WHERE user_id = ? AND shown_at >= ? AND shown_at < ?
        """, (user_id, previous_since, since))
        
        previous_row = cursor.fetchone()
        if previous_row['avg_effectiveness'] and row['avg_effectiveness']:
            improvement = (row['avg_effectiveness'] - previous_row['avg_effectiveness']) / previous_row['avg_effectiveness']
            metrics["improvement_trend"] = f"{improvement*100:+.0f}%"
        
        conn.close()
        return metrics
    
    # ========================================================================
    # A/B Testing
    # ========================================================================
    
    def start_ab_test(self, test_name: str, user_id: str, variant: str) -> None:
        """
        Assign user to A/B test variant.
        
        Args:
            test_name: "recommendation_style_v1" | "timing_strategy_v2" | etc.
            variant: "control" | "variant_a" | "variant_b"
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO ab_tests (test_name, variant, user_id, started_at)
            VALUES (?, ?, ?, ?)
        """, (test_name, variant, user_id, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def record_ab_result(self, test_name: str, user_id: str, success: bool) -> None:
        """
        Record A/B test outcome.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        field = 'success_count' if success else 'failure_count'
        
        cursor.execute(f"""
            UPDATE ab_tests
            SET {field} = {field} + 1
            WHERE test_name = ? AND user_id = ? AND ended_at IS NULL
        """, (test_name, user_id))
        
        conn.commit()
        conn.close()
    
    def get_ab_results(self, test_name: str) -> Dict:
        """
        Get A/B test results.
        
        Returns:
        {
            "control": {"users": 100, "success_rate": 0.35},
            "variant_a": {"users": 100, "success_rate": 0.42},
            "variant_b": {"users": 100, "success_rate": 0.38}
        }
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                variant,
                COUNT(DISTINCT user_id) as users,
                SUM(success_count) as successes,
                SUM(success_count + failure_count) as total
            FROM ab_tests
            WHERE test_name = ?
            GROUP BY variant
        """, (test_name,))
        
        results = {}
        for row in cursor.fetchall():
            results[row['variant']] = {
                'users': row['users'],
                'success_rate': row['successes'] / row['total'] if row['total'] > 0 else 0.0
            }
        
        conn.close()
        return results


if __name__ == '__main__':
    # Test feedback loop
    import sys
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'pattern_learning.db'
    
    feedback = FeedbackLoop(db_path)
    
    print("Testing Feedback Loop\n")
    
    # Simulate recommendation flow
    user_id = 'test_user'
    rec_id = 'rec_123'
    
    print("1. Showing recommendation...")
    feedback.record_feedback(user_id, rec_id, 'shown', {
        'type': 'email',
        'priority': 0.8,
        'sender': 'boss@company.com'
    })
    
    print("2. User clicks recommendation...")
    feedback.record_feedback(user_id, rec_id, 'clicked')
    
    print("3. Measuring effectiveness...")
    metrics = feedback.measure_effectiveness(user_id)
    print(json.dumps(metrics, indent=2))
    
    print("\n4. Updating patterns...")
    feedback.update_patterns(user_id)
    print("✓ Patterns updated")
