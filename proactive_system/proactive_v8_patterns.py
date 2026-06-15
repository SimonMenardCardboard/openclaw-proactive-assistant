#!/usr/bin/env python3
"""
V8 Pattern Learning - Proactive Recommendations
Analyzes user behavior and spontaneously suggests optimizations
V8.5: Includes federated learning via Hobbes Control
"""

import sys
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set

sys.path.insert(0, str(Path(__file__).parent))
from proactive_queue import ProactiveQueue

# V8.5 Federated Learning
sys.path.insert(0, str(Path(__file__).parent / "v8.5_pattern_learning"))
try:
    from hobbes_control_client import HobbesControlClient
    HOBBES_CONTROL_AVAILABLE = True
except ImportError:
    HOBBES_CONTROL_AVAILABLE = False
    logging.warning("Hobbes Control client not available")

# V8.5 pattern learning
sys.path.insert(0, str(Path(__file__).parent / "v8.5_pattern_learning/pattern_learning"))
try:
    from pattern_analyzer import UserPatternAnalyzer
    PATTERN_ANALYZER_AVAILABLE = True
except ImportError:
    PATTERN_ANALYZER_AVAILABLE = False
    logging.warning("Pattern analyzer not available")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProactivePatternRecommendations:
    """Generate spontaneous recommendations from learned patterns."""
    
    def __init__(self, user_id: str = 'default'):
        self.queue = ProactiveQueue()
        self.user_id = user_id
        
        if PATTERN_ANALYZER_AVAILABLE:
            db_path = Path.home() / '.openclaw/workspace/integrations/intelligence/v8.5_pattern_learning/pattern_learning.db'
            self.analyzer = UserPatternAnalyzer(str(db_path))
        else:
            self.analyzer = None
        
        # V8.5: Hobbes Control client for federated learning
        if HOBBES_CONTROL_AVAILABLE:
            self.control_client = HobbesControlClient(user_id=user_id)
        else:
            self.control_client = None
        
        # Track what we've already recommended — persisted to DB so restarts don't re-spam
        self.recommended = self._load_recommended_history()
    
    def _recommended_db_path(self) -> Path:
        from tm_paths import QUEUE_DB
        return QUEUE_DB.parent / 'recommended_history.db'

    def _load_recommended_history(self) -> Set[str]:
        """Load previously recommended types from persistent DB."""
        db = self._recommended_db_path()
        conn = sqlite3.connect(db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recommended_history (
                rec_type TEXT PRIMARY KEY,
                recommended_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        rows = conn.execute("""
            SELECT rec_type FROM recommended_history
            WHERE recommended_at > datetime('now', '-7 days')
        """).fetchall()
        conn.close()
        return {row[0] for row in rows}

    def _mark_recommended(self, rec_type: str):
        """Persist a recommendation type so it won't re-fire after restart."""
        self.recommended.add(rec_type)
        db = self._recommended_db_path()
        conn = sqlite3.connect(db)
        conn.execute("""
            INSERT OR REPLACE INTO recommended_history (rec_type, recommended_at)
            VALUES (?, datetime('now'))
        """, (rec_type,))
        conn.commit()
        conn.close()

    def _get_dismissal_penalty(self, pattern_key: str) -> float:
        """
        Return a confidence penalty based on how many times the user dismissed
        this specific pattern type. Uses rec_type (pattern_key) not source,
        so dismissing email filters doesn't suppress calendar suggestions.
        Each dismissal adds 0.1 (max +0.4).
        """
        try:
            db = self._recommended_db_path().parent / 'dismissed_feedback.db'
            if not db.exists():
                return 0.0
            conn = sqlite3.connect(db)
            count = conn.execute("""
                SELECT COUNT(*) FROM dismissed_feedback
                WHERE rec_type = ?
                AND dismissed_at > datetime('now', '-30 days')
            """, (pattern_key,)).fetchone()[0]
            conn.close()
            return min(count * 0.1, 0.4)
        except Exception:
            return 0.0

    def _get_user_account_age_days(self) -> Optional[float]:
        """Return how many days since the user account was created, or None if unknown."""
        try:
            db_path = Path(DATABASE_PATH) if 'DATABASE_PATH' in dir() else Path('/var/lib/transmogrifier/control_plane.db')
            if not db_path.exists():
                # Fallback: try workspace db
                db_path = Path.home() / '.openclaw/workspace/transmogrifier/transmogrifier.db'
            if not db_path.exists():
                return None
            conn = sqlite3.connect(str(db_path))
            row = conn.execute(
                "SELECT created_at FROM users WHERE id = ? LIMIT 1", (self.user_id,)
            ).fetchone()
            conn.close()
            if not row or not row[0]:
                return None
            created = datetime.fromisoformat(str(row[0]).replace('Z', '+00:00').replace('+00:00', ''))
            return (datetime.utcnow() - created).total_seconds() / 86400
        except Exception:
            return None

    def _is_new_user(self) -> bool:
        """Return True if the user account is less than 7 days old."""
        age = self._get_user_account_age_days()
        return age is not None and age < 7

    def _effective_threshold(self, pattern_key: str, base: float = 0.6) -> float:
        """Confidence threshold raised by dismissal history — per pattern type.
        New users (<7 days) use a reduced base threshold of 0.3 to ensure
        early insights fire before enough data for normal confidence."""
        if self._is_new_user():
            base = 0.3
        return base + self._get_dismissal_penalty(pattern_key)

    def check_for_recommendations(self):
        """Check learned patterns and queue spontaneous recommendations."""
        if not self.analyzer:
            logger.warning("Pattern analyzer not available")
            return
        
        try:
            # Analyze current patterns
            email_patterns = self._get_email_patterns()
            calendar_patterns = self._get_calendar_patterns()
            work_patterns = self._get_work_patterns()
            
            # Generate local recommendations
            self._recommend_email_optimizations(email_patterns)
            self._recommend_calendar_optimizations(calendar_patterns)
            self._recommend_productivity_improvements(work_patterns)
            
            # V8.5: Get federated insights from Hobbes Control
            if self.control_client:
                self._check_federated_insights()
                self._submit_anonymized_patterns(email_patterns, calendar_patterns, work_patterns)
            
            logger.info("Pattern-based recommendations checked")
            
        except Exception as e:
            logger.error(f"Error checking patterns: {e}", exc_info=True)
    
    def _get_email_patterns(self) -> Dict:
        """Get current email patterns."""
        try:
            return self.analyzer.analyze_email_patterns(self.user_id)
        except:
            return {}
    
    def _get_calendar_patterns(self) -> Dict:
        """Get current calendar patterns."""
        try:
            return self.analyzer.analyze_calendar_patterns(self.user_id)
        except:
            return {}
    
    def _get_work_patterns(self) -> Dict:
        """Get current work patterns."""
        try:
            return self.analyzer.analyze_work_patterns(self.user_id)
        except:
            return {}
    
    def _recommend_email_optimizations(self, patterns: Dict):
        """Recommend email workflow improvements."""
        if not patterns or patterns.get('confidence_score', 0) < self._effective_threshold('vip_filters'):
            return
        
        # VIP sender filters
        vips = patterns.get('vip_senders', [])
        if len(vips) >= 3 and 'vip_filters' not in self.recommended:
            early = self._is_new_user()
            prefix = "Early observation — still learning your patterns\n\n" if early else ""
            message = prefix + "💡 *Email insight*\n\n"
            message += f"You consistently respond quickly to {len(vips)} senders. "
            message += "Want me to auto-flag their emails as priority?\n\n"
            message += f"VIPs: {', '.join(vips[:3])}"
            if len(vips) > 3:
                message += f" +{len(vips)-3} more"
            
            self.queue.add(
                source='v8-patterns',
                message=message,
                priority=3,
                context={'recommendation_type': 'vip_filters', 'vips': vips, 'early_insight': early},
                pattern_key='vip_filters'
            )
            self._mark_recommended('vip_filters')
            logger.info("Recommended VIP email filters")
        
        # Batch processing suggestion
        if patterns.get('batch_processor') and 'email_batching' not in self.recommended:
            peak_hours = patterns.get('peak_email_hours', [])
            if peak_hours:
                early = self._is_new_user()
                prefix = "Early observation — still learning your patterns\n\n" if early else ""
                message = prefix + "💡 *Workflow insight*\n\n"
                message += f"You check email in batches around {', '.join(peak_hours)}. "
                message += "Want me to hold non-urgent notifications until then?"
                
                self.queue.add(
                    source='v8-patterns',
                    message=message,
                    priority=3,
                    context={'recommendation_type': 'email_batching', 'peak_hours': peak_hours, 'early_insight': early},
                    pattern_key='email_batching'
                )
                self._mark_recommended('email_batching')
                logger.info("Recommended email batching")
    
    def _recommend_calendar_optimizations(self, patterns: Dict):
        """Recommend calendar workflow improvements."""
        if not patterns or patterns.get('confidence_score', 0) < self._effective_threshold('meeting_prep'):
            return
        
        # Meeting prep time
        prep_patterns = patterns.get('prep_time_by_type', {})
        if prep_patterns and 'meeting_prep' not in self.recommended:
            # Find meetings that need prep
            needs_prep = {k: v for k, v in prep_patterns.items() if v > 15}
            if needs_prep:
                early = self._is_new_user()
                prefix = "Early observation — still learning your patterns\n\n" if early else ""
                message = prefix + "💡 *Calendar insight*\n\n"
                message += "You usually prep 15-30 minutes before certain meetings. "
                message += "Want automatic prep time blocked before them?"
                
                self.queue.add(
                    source='v8-patterns',
                    message=message,
                    priority=3,
                    context={'recommendation_type': 'meeting_prep', 'prep_patterns': prep_patterns, 'early_insight': early},
                pattern_key='meeting_prep'
                )
                self._mark_recommended('meeting_prep')
                logger.info("Recommended meeting prep blocks")
        
        # Focus time
        focus_hours = patterns.get('deep_work_hours', [])
        if len(focus_hours) >= 2 and 'focus_time' not in self.recommended:
            early = self._is_new_user()
            prefix = "Early observation — still learning your patterns\n\n" if early else ""
            message = prefix + "💡 *Productivity insight*\n\n"
            message += f"You're most focused during {', '.join(focus_hours)}. "
            message += "Want me to auto-decline meetings during those hours?"
            
            self.queue.add(
                source='v8-patterns',
                message=message,
                priority=3,
                context={'recommendation_type': 'focus_time', 'focus_hours': focus_hours, 'early_insight': early},
            pattern_key='focus_time'
            )
            self._mark_recommended('focus_time')
            logger.info("Recommended focus time protection")
    
    def _recommend_productivity_improvements(self, patterns: Dict):
        """Recommend productivity optimizations."""
        if not patterns or patterns.get('confidence_score', 0) < self._effective_threshold('focus_time'):
            return
        
        # Context switching
        avg_switches = patterns.get('avg_context_switches_per_hour', 0)
        if avg_switches > 8 and 'reduce_switching' not in self.recommended:
            early = self._is_new_user()
            prefix = "Early observation — still learning your patterns\n\n" if early else ""
            message = prefix + "💡 *Productivity insight*\n\n"
            message += f"You switch tasks ~{int(avg_switches)} times per hour. "
            message += "Research shows 4-6 is optimal. Want tips to reduce context switching?"
            
            self.queue.add(
                source='v8-patterns',
                message=message,
                priority=3,
                context={'recommendation_type': 'reduce_switching', 'current_rate': avg_switches, 'early_insight': early},
            pattern_key='reduce_switching'
            )
            self._mark_recommended('reduce_switching')
            logger.info("Recommended reducing context switching")
        
        # Peak productivity
        peak_hours = patterns.get('peak_productivity_hours', [])
        if len(peak_hours) >= 2 and 'protect_peak' not in self.recommended:
            early = self._is_new_user()
            prefix = "Early observation — still learning your patterns\n\n" if early else ""
            message = prefix + "💡 *Energy insight*\n\n"
            message += f"Your peak productivity is {', '.join(peak_hours)}. "
            message += "Want me to protect this time from meetings and notifications?"
            
            self.queue.add(
                source='v8-patterns',
                message=message,
                priority=3,
                context={'recommendation_type': 'protect_peak', 'peak_hours': peak_hours, 'early_insight': early},
            pattern_key='protect_peak'
            )
            self._mark_recommended('protect_peak')
            logger.info("Recommended protecting peak hours")


if __name__ == '__main__':
    # Test pattern recommendations
    recommender = ProactivePatternRecommendations()
    recommender.check_for_recommendations()
    
    stats = recommender.queue.stats()
    print(f"\n📊 Queue: {stats['pending']} pending, {stats['delivered']} delivered")

    # V8.5: Federated Learning Methods
    
    def _check_federated_insights(self):
        """Get and queue cross-user insights from Hobbes Control."""
        try:
            insights = self.control_client.get_federated_insights()
            
            for insight in insights:
                insight_type = insight.get('type')
                if insight_type in self.recommended:
                    continue  # Already recommended
                
                message = self._format_federated_insight(insight)
                if message:
                    self.queue.add(
                        source='v8.5-federated',
                        message=message,
                        priority=3,
                        context={'insight_type': insight_type, 'federated': True},
                        pattern_key=insight_type
                    )
                    self._mark_recommended(insight_type)
                    logger.info(f"Queued federated insight: {insight_type}")
        
        except Exception as e:
            logger.warning(f"Failed to get federated insights: {e}")
    
    def _format_federated_insight(self, insight: Dict) -> str:
        """Format federated insight as user-friendly message."""
        insight_type = insight.get('type')
        data = insight.get('data', {})
        
        if insight_type == 'email_response_time':
            avg_network = data.get('network_avg_hours', 0)
            user_avg = data.get('user_avg_hours', 0)
            
            if user_avg > avg_network * 1.5:
                return f"💡 *Cross-user insight*\n\nUsers with similar roles respond to emails in {avg_network:.1f} hours on average.\nYou're taking {user_avg:.1f} hours.\n\nWant to adjust notification priority to help you respond faster?"
        
        elif insight_type == 'focus_time_blocking':
            pct = data.get('users_with_focus_blocks', 0)
            hours = data.get('common_hours', '')
            
            if pct > 60:
                return f"💡 *Productivity insight*\n\n{pct}% of productive users block {hours} for deep work.\n\nWant me to protect this time in your calendar?"
        
        elif insight_type == 'meeting_delegation':
            pct = data.get('users_delegating', 0)
            
            if pct > 50:
                return f"💡 *Workflow insight*\n\n{pct}% of users with your meeting load delegate status updates to async.\n\nWant tips on effective delegation?"
        
        return None
    
    def _submit_anonymized_patterns(self, email_patterns: Dict, calendar_patterns: Dict, work_patterns: Dict):
        """Submit anonymized patterns to Hobbes Control for network learning."""
        try:
            patterns = []
            
            # Anonymize and submit email patterns
            submit_threshold = 0.3 if self._is_new_user() else 0.6
            if email_patterns and email_patterns.get('confidence_score', 0) > submit_threshold:
                patterns.append({
                    'type': 'email_response_time',
                    'avg_hours': email_patterns.get('avg_response_time_hours', 0),
                    'confidence': email_patterns.get('confidence_score', 0)
                })
            
            # Anonymize and submit calendar patterns
            if calendar_patterns and calendar_patterns.get('confidence_score', 0) > submit_threshold:
                focus_hours = calendar_patterns.get('deep_work_hours', [])
                if focus_hours:
                    patterns.append({
                        'type': 'focus_time_blocking',
                        'hours': ','.join(focus_hours),
                        'confidence': calendar_patterns.get('confidence_score', 0)
                    })
            
            # Submit patterns (no PII, fully anonymized)
            if patterns:
                self.control_client.submit_patterns(patterns)
                logger.info(f"Submitted {len(patterns)} anonymized patterns")
        
        except Exception as e:
            logger.warning(f"Failed to submit patterns: {e}")
