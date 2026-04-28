#!/usr/bin/env python3
"""
V8 Pattern Learning - Proactive Recommendations
Analyzes user behavior and spontaneously suggests optimizations
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent))
from proactive_queue import ProactiveQueue

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
            
            # Generate recommendations
            self._recommend_email_optimizations(email_patterns)
            self._recommend_calendar_optimizations(calendar_patterns)
            self._recommend_productivity_improvements(work_patterns)
            
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
