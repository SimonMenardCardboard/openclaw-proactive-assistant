#!/usr/bin/env python3
"""
Proactive Calendar Integration
Monitors upcoming events and queues intelligent meeting prep notifications
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict
import logging

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))
from proactive_queue import ProactiveQueue

# V8 calendar connector
sys.path.insert(0, str(Path(__file__).parent / "v8_meta_learning"))
try:
    from email_calendar_connector import EmailCalendarConnector
    CALENDAR_AVAILABLE = True
except ImportError:
    CALENDAR_AVAILABLE = False
    logging.warning("Calendar connector not available")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProactiveCalendar:
    """Proactive calendar notifications and meeting prep."""
    
    def __init__(self, user_id: str = 'default'):
        self.user_id = user_id
        self.queue = ProactiveQueue()
        
        # Use universal calendar API (backward compatible)
        try:
            from universal_calendar_api import UniversalCalendarManager
            self.calendar = UniversalCalendarManager()
        except Exception as e:
            logger.warning(f"Calendar connector init failed: {e}")
            self.calendar = None
        
        # Load context database for contact intelligence
        try:
            from context_database import ContextDatabase
            self.context_db = ContextDatabase()
        except Exception as e:
            logger.warning(f"Context DB init failed: {e}")
            self.context_db = None
        
        # Track what we've already notified about
        self.notified_events = set()
    
    def check_upcoming_events(self):
        """Check for upcoming events and queue appropriate notifications."""
        if not self.calendar:
            logger.warning("Calendar not available")
            return
        
        try:
            # Get next 2 days of events from ALL connected calendars
            events = self.calendar.get_all_events(days_ahead=2)
            
            now = datetime.now()
            
            for event in events:
                event_id = event.get('id')
                if event_id in self.notified_events:
                    continue  # Already notified
                
                # Parse event time
                start_time = self._parse_time(event.get('start'))
                if not start_time:
                    continue
                
                time_until = start_time - now
                hours_until = time_until.total_seconds() / 3600
                
                # Notification windows
                if 1.5 <= hours_until <= 2.5:
                    # 2-hour heads up
                    self._queue_meeting_prep(event, hours_until)
                    self.notified_events.add(event_id)
                
                elif 0.08 <= hours_until <= 0.15:
                    # 5-10 min warning
                    self._queue_starting_soon(event, hours_until)
                    self.notified_events.add(event_id)
            
            logger.info(f"Checked {len(events)} events, notified for {len(self.notified_events)} new ones")
            
            # Check for conflicts (NEW)
            self._check_conflicts()
            
        except Exception as e:
            logger.error(f"Error checking calendar: {e}", exc_info=True)
    
    def _check_conflicts(self):
        """Check for calendar conflicts and notify (NEW - integrated from universal API)."""
        if not self.calendar:
            return
        
        try:
            # Get all events across accounts
            all_events_dict = self.calendar.get_all_events_across_accounts(max_per_account=100)
            
            # Check conflicts per account
            for email, events in all_events_dict.items():
                if not events:
                    continue
                
                api = self.calendar.get_account(email)
                if not api:
                    continue
                
                conflicts = api.detect_conflicts(events)
                
                for conflict in conflicts:
                    conflict_id = f"{conflict['event_1']}_{conflict['event_2']}"
                    
                    if conflict_id in self.notified_events:
                        continue
                    
                    # Queue conflict notification
                    self.queue.add_recommendation(
                        f"⚠️ **Calendar Conflict Detected**\n\n"
                        f"• {conflict['event_1']}\n"
                        f"  {conflict['time_1']}\n\n"
                        f"• {conflict['event_2']}\n"
                        f"  {conflict['time_2']}\n\n"
                        f"You're double-booked on {email.split('@')[0]}.",
                        priority=1,  # High priority
                        context={'conflict': conflict, 'account': email}
                    )
                    
                    self.notified_events.add(conflict_id)
                    logger.info(f"Queued conflict notification for {email}")
        
        except Exception as e:
            logger.debug(f"Error checking conflicts: {e}")
    
    def _queue_meeting_prep(self, event: Dict, hours_until: float):
        """Queue 2-hour meeting prep notification."""
        title = event.get('summary', 'Meeting')
        
        message = f"📅 **{title}** in ~2 hours\n\n"
        
        # Add location if available
        if event.get('location'):
            message += f"📍 {event['location']}\n"
        
        # Add attendees count if available
        attendees = event.get('attendees', [])
        if attendees:
            message += f"👥 {len(attendees)} attendee{'s' if len(attendees) > 1 else ''}\n"
            
            # Add contact intelligence from context DB (NEW)
            if self.context_db and len(attendees) <= 5:
                message += "\n**Attendees:**\n"
                for attendee_email in attendees[:5]:
                    try:
                        contact = self.context_db.get_contact(attendee_email)
                        if contact:
                            name = contact.get('name', attendee_email)
                            total_emails = contact.get('total_emails', 0)
                            meetings = contact.get('meeting_count', 0)
                            
                            if total_emails > 10 or meetings > 5:
                                message += f"• {name}"
                                if total_emails > 20:
                                    message += f" ({total_emails} emails)"
                                if meetings > 10:
                                    message += f" (frequent collaborator)"
                                message += "\n"
                            else:
                                message += f"• {name}\n"
                        else:
                            # New contact - first meeting
                            message += f"• {attendee_email.split('@')[0]} (new contact)\n"
                    except Exception as e:
                        logger.debug(f"Error loading contact intel: {e}")
        
        # Check if prep materials needed
        description = event.get('description', '').lower()
        if any(word in description for word in ['prep', 'review', 'read', 'materials']):
            message += "\n💡 _Looks like prep might be needed_"
        
        self.queue.add(
            source='calendar',
            message=message,
            priority=3,  # Medium - useful but not urgent
            context={
                'event_id': event.get('id'),
                'event_title': title,
                'hours_until': hours_until,
                'notification_type': 'prep'
            }
        )
        
        logger.info(f"Queued 2-hour prep for: {title}")
    
    def _queue_starting_soon(self, event: Dict, hours_until: float):
        """Queue 5-10 minute warning."""
        title = event.get('summary', 'Meeting')
        mins = int(hours_until * 60)
        
        message = f"⏰ **{title}** starting in ~{mins} minutes"
        
        if event.get('location'):
            message += f"\n📍 {event['location']}"
        
        self.queue.add(
            source='calendar',
            message=message,
            priority=2,  # High - starting soon
            context={
                'event_id': event.get('id'),
                'event_title': title,
                'minutes_until': mins,
                'notification_type': 'starting_soon'
            }
        )
        
        logger.info(f"Queued starting-soon for: {title}")
    
    def _parse_time(self, time_str) -> datetime:
        """Parse event time string to datetime."""
        if not time_str:
            return None
        
        try:
            # Try ISO format
            if isinstance(time_str, dict):
                time_str = time_str.get('dateTime') or time_str.get('date')
            
            if 'T' in str(time_str):
                # Has time component
                return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            else:
                # All-day event
                return datetime.fromisoformat(time_str)
        except Exception as e:
            logger.warning(f"Failed to parse time: {time_str} - {e}")
            return None


if __name__ == '__main__':
    # Test calendar integration
    calendar = ProactiveCalendar()
    calendar.check_upcoming_events()
    
    # Show queue stats
    stats = calendar.queue.stats()
    print(f"\n📊 Queue: {stats['pending']} pending, {stats['delivered']} delivered")
