#!/usr/bin/env python3
"""
V8 Pattern Learning - Proactive Recommendations
Analyzes user behavior and spontaneously suggests optimizations
V8.5: Includes federated learning via Hobbes Control
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional

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
        
        # Track what we've already recommended
        self.recommended = set()
    
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
        if not patterns or patterns.get('confidence_score', 0) < 0.6:
            return
        
        # VIP sender filters
        vips = patterns.get('vip_senders', [])
        if len(vips) >= 3 and 'vip_filters' not in self.recommended:
            message = "💡 *Email insight*\n\n"
            message += f"You consistently respond quickly to {len(vips)} senders. "
            message += "Want me to auto-flag their emails as priority?\n\n"
            message += f"VIPs: {', '.join(vips[:3])}"
            if len(vips) > 3:
                message += f" +{len(vips)-3} more"
            
            self.queue.add(
                source='v8-patterns',
                message=message,
                priority=3,
                context={'recommendation_type': 'vip_filters', 'vips': vips}
            )
            self.recommended.add('vip_filters')
            logger.info("Recommended VIP email filters")
        
        # Batch processing suggestion
        if patterns.get('batch_processor') and 'email_batching' not in self.recommended:
            peak_hours = patterns.get('peak_email_hours', [])
            if peak_hours:
                message = "💡 *Workflow insight*\n\n"
                message += f"You check email in batches around {', '.join(peak_hours)}. "
                message += "Want me to hold non-urgent notifications until then?"
                
                self.queue.add(
                    source='v8-patterns',
                    message=message,
                    priority=3,
                    context={'recommendation_type': 'email_batching', 'peak_hours': peak_hours}
                )
                self.recommended.add('email_batching')
                logger.info("Recommended email batching")
    
    def _recommend_calendar_optimizations(self, patterns: Dict):
        """Recommend calendar workflow improvements."""
        if not patterns or patterns.get('confidence_score', 0) < 0.6:
            return
        
        # Meeting prep time
        prep_patterns = patterns.get('prep_time_by_type', {})
        if prep_patterns and 'meeting_prep' not in self.recommended:
            # Find meetings that need prep
            needs_prep = {k: v for k, v in prep_patterns.items() if v > 15}
            if needs_prep:
                message = "💡 *Calendar insight*\n\n"
                message += "You usually prep 15-30 minutes before certain meetings. "
                message += "Want automatic prep time blocked before them?"
                
                self.queue.add(
                    source='v8-patterns',
                    message=message,
                    priority=3,
                    context={'recommendation_type': 'meeting_prep', 'prep_patterns': prep_patterns}
                )
                self.recommended.add('meeting_prep')
                logger.info("Recommended meeting prep blocks")
        
        # Focus time
        focus_hours = patterns.get('deep_work_hours', [])
        if len(focus_hours) >= 2 and 'focus_time' not in self.recommended:
            message = "💡 *Productivity insight*\n\n"
            message += f"You're most focused during {', '.join(focus_hours)}. "
            message += "Want me to auto-decline meetings during those hours?"
            
            self.queue.add(
                source='v8-patterns',
                message=message,
                priority=3,
                context={'recommendation_type': 'focus_time', 'focus_hours': focus_hours}
            )
            self.recommended.add('focus_time')
            logger.info("Recommended focus time protection")
    
    def _recommend_productivity_improvements(self, patterns: Dict):
        """Recommend productivity optimizations."""
        if not patterns or patterns.get('confidence_score', 0) < 0.6:
            return
        
        # Context switching
        avg_switches = patterns.get('avg_context_switches_per_hour', 0)
        if avg_switches > 8 and 'reduce_switching' not in self.recommended:
            message = "💡 *Productivity insight*\n\n"
            message += f"You switch tasks ~{int(avg_switches)} times per hour. "
            message += "Research shows 4-6 is optimal. Want tips to reduce context switching?"
            
            self.queue.add(
                source='v8-patterns',
                message=message,
                priority=3,
                context={'recommendation_type': 'reduce_switching', 'current_rate': avg_switches}
            )
            self.recommended.add('reduce_switching')
            logger.info("Recommended reducing context switching")
        
        # Peak productivity
        peak_hours = patterns.get('peak_productivity_hours', [])
        if len(peak_hours) >= 2 and 'protect_peak' not in self.recommended:
            message = "💡 *Energy insight*\n\n"
            message += f"Your peak productivity is {', '.join(peak_hours)}. "
            message += "Want me to protect this time from meetings and notifications?"
            
            self.queue.add(
                source='v8-patterns',
                message=message,
                priority=3,
                context={'recommendation_type': 'protect_peak', 'peak_hours': peak_hours}
            )
            self.recommended.add('protect_peak')
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
                        context={'insight_type': insight_type, 'federated': True}
                    )
                    self.recommended.add(insight_type)
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
            if email_patterns and email_patterns.get('confidence_score', 0) > 0.6:
                patterns.append({
                    'type': 'email_response_time',
                    'avg_hours': email_patterns.get('avg_response_time_hours', 0),
                    'confidence': email_patterns.get('confidence_score', 0)
                })
            
            # Anonymize and submit calendar patterns
            if calendar_patterns and calendar_patterns.get('confidence_score', 0) > 0.6:
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
