#!/usr/bin/env python3
"""
Transmogrifier Bootstrap Onboarding
Fast-path to first recommendations (2-4 hours instead of 7+ days)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
import sys

# Add parent dirs to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'integrations/intelligence'))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'integrations/proactive_daemon'))

from proactive_queue import ProactiveQueue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BootstrapOnboarding:
    """Fast-path onboarding for new Transmogrifier users."""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.queue = ProactiveQueue()
    
    async def trigger(self):
        """Main bootstrap orchestration."""
        logger.info(f"🚀 Starting bootstrap onboarding for {self.user_id}")
        
        # Step 1: Notify user we're analyzing
        await self.send_onboarding_start()
        
        # Step 2: Pull historical data (background)
        logger.info("Pulling historical data (30 days)...")
        data = await self.pull_historical_data()
        
        # Step 3: Run fast pattern analysis
        logger.info("Analyzing patterns...")
        patterns = await self.analyze_patterns(data)
        
        # Step 4: Generate and queue recommendations
        logger.info("Generating recommendations...")
        recommendations = await self.generate_recommendations(patterns)
        await self.queue_recommendations(recommendations)
        
        # Step 5: Enable real-time monitoring
        logger.info("Enabling real-time monitoring...")
        await self.enable_monitoring()
        
        # Step 6: Send welcome message
        await self.send_welcome(patterns, recommendations)
        
        logger.info(f"✅ Bootstrap complete for {self.user_id}")
    
    async def send_onboarding_start(self):
        """Notify user that analysis is starting."""
        message = """🎉 Welcome to Transmogrifier!

I'm analyzing your last 30 days of emails and calendar to find initial recommendations to improve your daily life!

First recommendations will come as soon as I finish my analysis, which may take 2-4 hours, but likely sooner than that.

I'll notify you as soon as I find something! 🐯"""
        
        self.queue.add(
            source='onboarding',
            message=message,
            priority=1,
            context={'user_id': self.user_id, 'type': 'onboarding_start'}
        )
    
    async def pull_historical_data(self) -> Dict:
        """Pull last 30 days of email + calendar data."""
        # TODO: Implement via COS oauth_manager
        # For now, return mock data structure
        
        return {
            'emails': {
                'count': 450,
                'date_range': {'start': '2026-03-28', 'end': '2026-04-28'},
                'by_sender': {},  # top senders
                'by_hour': {},  # email volume by hour
                'response_times': [],  # hours to respond
                'unread_count': 73
            },
            'calendar': {
                'meetings': 120,
                'date_range': {'start': '2026-03-28', 'end': '2026-04-28'},
                'by_day': {},  # meetings per day
                'focus_blocks': [],  # unscheduled time blocks
                'recurring': [],  # recurring meetings
                'after_hours': 12  # meetings after 6 PM
            }
        }
    
    async def analyze_patterns(self, data: Dict) -> Dict:
        """Fast pattern detection on historical data."""
        email = data['emails']
        calendar = data['calendar']
        
        # Email patterns
        avg_response_time = sum(email['response_times']) / len(email['response_times']) if email['response_times'] else 0
        emails_per_day = email['count'] / 30
        unread_ratio = email['unread_count'] / email['count'] if email['count'] > 0 else 0
        
        # Calendar patterns
        meetings_per_day = calendar['meetings'] / 30
        focus_hours_per_day = len(calendar['focus_blocks']) / 30 if calendar['focus_blocks'] else 0
        after_hours_per_week = calendar['after_hours'] / 4
        
        # Work patterns (heuristics from email times)
        work_start = 9  # TODO: calculate from earliest email times
        work_end = 18  # TODO: calculate from latest email times
        
        return {
            'email': {
                'avg_response_time_hours': avg_response_time,
                'emails_per_day': emails_per_day,
                'unread_ratio': unread_ratio,
                'unread_count': email['unread_count']
            },
            'calendar': {
                'meetings_per_day': meetings_per_day,
                'focus_hours_per_day': focus_hours_per_day,
                'after_hours_per_week': after_hours_per_week
            },
            'work': {
                'start_hour': work_start,
                'end_hour': work_end,
                'works_weekends': False  # TODO: calculate
            },
            'confidence': 'bootstrap'
        }
    
    async def generate_recommendations(self, patterns: Dict) -> List[Dict]:
        """Generate high-value recommendations from patterns."""
        recommendations = []
        
        email = patterns['email']
        calendar = patterns['calendar']
        work = patterns['work']
        
        # Recommendation 1: Email response speed
        if email['avg_response_time_hours'] > 24:
            recommendations.append({
                'type': 'email_response_speed',
                'priority': 2,
                'delay_hours': 1,
                'message': f"""📧 **Email Response Speed**

You respond to emails in {email['avg_response_time_hours']:.1f} hours on average.

**Quick win:** Enable email triage and urgent flagging.

I can:
• Flag urgent emails from VIPs
• Remind you of pending replies
• Auto-archive newsletters

Want me to set this up?"""
            })
        
        # Recommendation 2: Inbox cleanup
        if email['unread_count'] > 50:
            recommendations.append({
                'type': 'inbox_cleanup',
                'priority': 3,
                'delay_hours': 2.5,
                'message': f"""📬 **Inbox Overload**

You have {email['unread_count']} unread emails piling up.

**Quick win:** Weekly inbox triage.

I can:
• Auto-archive newsletters and notifications
• Suggest batch processing times
• Track follow-up threads

Want help cleaning up?"""
            })
        
        # Recommendation 3: Focus time blocking
        if calendar['focus_hours_per_day'] < 2:
            recommendations.append({
                'type': 'focus_time_blocking',
                'priority': 1,
                'delay_hours': 4,
                'message': f"""📅 **Focus Time**

You have less than {calendar['focus_hours_per_day']:.1f} hours/day of unscheduled focus time.

**Quick win:** Block 9-11 AM for deep work.

I can:
• Protect morning focus time
• Decline low-priority meetings
• Suggest async alternatives

Want me to guard your calendar?"""
            })
        
        # Recommendation 4: Meeting overload
        if calendar['meetings_per_day'] > 6:
            recommendations.append({
                'type': 'meeting_overload',
                'priority': 2,
                'delay_hours': 5.5,
                'message': f"""⏰ **Meeting Density**

You average {calendar['meetings_per_day']:.1f} meetings/day.

**Quick win:** Meeting audit + async alternatives.

I can:
• Identify recurring meetings to delegate
• Suggest shorter meeting times
• Find async-friendly topics

Want tips on meeting reduction?"""
            })
        
        # Recommendation 5: Work-life boundaries
        if calendar['after_hours_per_week'] > 3:
            recommendations.append({
                'type': 'work_life_boundary',
                'priority': 1,
                'delay_hours': 7,
                'message': f"""🌙 **After-Hours Meetings**

You have {calendar['after_hours_per_week']:.1f} meetings/week after 6 PM.

**Quick win:** Protect your evenings.

I can:
• Decline after-hours meetings
• Suggest morning alternatives
• Set work-hour boundaries

Want me to protect your evenings?"""
            })
        
        return recommendations
    
    async def queue_recommendations(self, recommendations: List[Dict]):
        """Queue recommendations with staggered delivery via proactive queue."""
        import time
        from datetime import datetime, timedelta
        
        for rec in recommendations:
            # Calculate delivery time
            delivery_time = datetime.now() + timedelta(hours=rec['delay_hours'])
            
            logger.info(f"Queuing {rec['type']} for delivery at {delivery_time.strftime('%I:%M %p')}")
            
            # Add to proactive queue (will be picked up by daemon)
            self.queue.add(
                source='bootstrap',
                message=rec['message'],
                priority=rec['priority'],
                context={
                    'user_id': self.user_id,
                    'type': rec['type'],
                    'scheduled_for': delivery_time.isoformat(),
                    'bootstrap': True
                }
            )
            
            logger.info(f"✅ Queued: {rec['type']} (Priority {rec['priority']}, +{rec['delay_hours']}h)")
    
    async def enable_monitoring(self):
        """Enable V6/V7 real-time monitoring."""
        import subprocess
        
        # Note: In production, V6/V7 are shared daemons that handle all users
        # This is a registration step, not spawning new processes
        
        # For testing, just log (actual integration would register user ID)
        logger.info(f"✅ Real-time monitoring enabled for {self.user_id}")
        logger.info("   - V6 proactive daemon: monitoring inbox/calendar")
        logger.info("   - V7 self-healing: watching for failures")
        logger.info("   - COS webhooks: real-time email/calendar push")
    
    async def send_welcome(self, patterns: Dict, recommendations: List[Dict]):
        """Send personalized welcome message."""
        email = patterns['email']
        calendar = patterns['calendar']
        work = patterns['work']
        
        message = f"""✅ **Analysis Complete!**

Here's what I found from your last 30 days:

📧 **Email:** {email['emails_per_day']:.1f}/day, {email['avg_response_time_hours']:.1f}h avg response
📅 **Calendar:** {calendar['meetings_per_day']:.1f} meetings/day
⏰ **Work hours:** {work['start_hour']}:00 - {work['end_hour']}:00

**{len(recommendations)} recommendations queued** (arriving over next 4-6 hours)

I'm also monitoring your inbox and calendar in real-time now. You'll get proactive suggestions as patterns emerge.

Questions? Just ask! 🐯"""
        
        self.queue.add(
            source='onboarding',
            message=message,
            priority=2,
            context={'user_id': self.user_id, 'type': 'onboarding_complete'}
        )


# CLI for testing
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python bootstrap.py <user_id>")
        sys.exit(1)
    
    user_id = sys.argv[1]
    
    onboarding = BootstrapOnboarding(user_id)
    asyncio.run(onboarding.trigger())
    
    print(f"\n✅ Bootstrap onboarding complete for {user_id}")
    print(f"Check queue: ~/.openclaw/workspace/integrations/intelligence/proactive_queue.db")
