#!/usr/bin/env python3
"""
Populate Context Database from Universal APIs

Fetches data from all email and calendar accounts and populates context.db
with extracted intelligence.

Run this:
- On first setup (initial population)
- Daily (incremental updates)
- After adding new accounts
"""

import sys
from pathlib import Path
from datetime import datetime
import logging

# Add current dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from context_database import ContextDatabase
from universal_email_api import UniversalAccountManager as EmailManager
from universal_calendar_api import UniversalCalendarManager as CalendarManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [POPULATE] %(message)s'
)
logger = logging.getLogger(__name__)


def populate_contacts_from_email(db: ContextDatabase, email_manager: EmailManager):
    """Populate contacts table from email analysis."""
    logger.info("Populating contacts from email...")
    
    # Get combined important contacts across all accounts
    important_contacts = email_manager.get_combined_important_contacts(top_n=100)
    
    for contact in important_contacts:
        db.upsert_contact(
            email=contact['email'],
            name=contact['name'],
            total_emails=contact['total_emails'],
            avg_response_hours=contact.get('avg_response_hours'),
            importance_score=contact['importance_score'],
            first_contact=contact.get('first_contact'),
            last_contact=contact.get('last_contact'),
            accounts=contact.get('accounts', [])
        )
    
    logger.info(f"✅ Populated {len(important_contacts)} contacts from email")
    return len(important_contacts)


def populate_contacts_from_calendar(db: ContextDatabase, cal_manager: CalendarManager):
    """Update contacts with meeting frequency from calendar."""
    logger.info("Updating contacts with meeting frequency...")
    
    # Get combined meeting frequency
    meeting_freq = cal_manager.get_combined_meeting_frequency(top_n=100)
    
    updated = 0
    for contact_info in meeting_freq:
        contact_email = contact_info['contact']
        
        # Check if contact exists
        existing = db.get_contact(contact_email)
        
        if existing:
            # Update with meeting count
            db.upsert_contact(
                email=contact_email,
                meeting_count=contact_info['meeting_count']
            )
            updated += 1
        else:
            # Create new contact from calendar data
            db.upsert_contact(
                email=contact_email,
                name=contact_email.split('@')[0],  # Use email username as name
                meeting_count=contact_info['meeting_count'],
                accounts=contact_info.get('accounts', [])
            )
            updated += 1
    
    logger.info(f"✅ Updated {updated} contacts with meeting frequency")
    return updated


def populate_recurring_meetings(db: ContextDatabase, cal_manager: CalendarManager):
    """Populate recurring meetings table."""
    logger.info("Populating recurring meetings...")
    
    all_events = cal_manager.get_all_events_across_accounts(max_per_account=200)
    
    total_meetings = 0
    
    for account_email, events in all_events.items():
        if not events:
            continue
        
        # Get API for this account
        api = cal_manager.get_account(account_email)
        if not api:
            continue
        
        # Detect recurring patterns
        patterns = api.detect_recurring_patterns(events)
        
        for recurring_id, pattern in patterns.items():
            db.upsert_recurring_meeting(
                recurring_id=recurring_id,
                summary=pattern['summary'],
                occurrence_count=pattern['occurrence_count'],
                organizer=pattern['organizer'],
                attendees=pattern['attendees'],
                first_occurrence=pattern['first_occurrence'],
                last_occurrence=pattern['last_occurrence'],
                accounts=[account_email]
            )
            total_meetings += 1
    
    logger.info(f"✅ Populated {total_meetings} recurring meetings")
    return total_meetings


def populate_focus_time_patterns(db: ContextDatabase, cal_manager: CalendarManager):
    """Analyze and populate focus time patterns."""
    logger.info("Analyzing focus time patterns...")
    
    # This is more complex - would analyze historical gaps by day/hour
    # For now, just log that it's not implemented yet
    logger.info("⏳ Focus time pattern analysis - TODO")
    return 0


def log_sync_status(db: ContextDatabase, email_count: int, calendar_count: int, meetings_count: int):
    """Log sync operation for all accounts."""
    # Log email sync
    db.log_sync('contacts_email', 'all_accounts', email_count, 'success')
    
    # Log calendar sync
    db.log_sync('contacts_calendar', 'all_accounts', calendar_count, 'success')
    db.log_sync('recurring_meetings', 'all_accounts', meetings_count, 'success')


def main():
    """Main population workflow."""
    print("\n" + "="*60)
    print("Populate Context Database")
    print("="*60 + "\n")
    
    # Initialize
    db = ContextDatabase()
    email_manager = EmailManager()
    cal_manager = CalendarManager()
    
    email_accounts = email_manager.get_all_accounts()
    cal_accounts = cal_manager.get_all_accounts()
    
    print(f"📧 Email accounts: {len(email_accounts)}")
    print(f"📅 Calendar accounts: {len(cal_accounts)}\n")
    
    # Step 1: Populate contacts from email
    print("[1/4] Populating contacts from email...")
    email_count = populate_contacts_from_email(db, email_manager)
    print()
    
    # Step 2: Update contacts with calendar meeting frequency
    print("[2/4] Updating contacts with meeting frequency...")
    calendar_count = populate_contacts_from_calendar(db, cal_manager)
    print()
    
    # Step 3: Populate recurring meetings
    print("[3/4] Populating recurring meetings...")
    meetings_count = populate_recurring_meetings(db, cal_manager)
    print()
    
    # Step 4: Log sync
    print("[4/4] Logging sync status...")
    log_sync_status(db, email_count, calendar_count, meetings_count)
    print("✅ Sync logged\n")
    
    # Summary
    print("="*60)
    print("Population Complete")
    print("="*60)
    print(f"Contacts populated: {email_count}")
    print(f"Contacts updated (meetings): {calendar_count}")
    print(f"Recurring meetings: {meetings_count}")
    print()
    
    # Show top contacts
    print("Top 5 Contacts by Importance:")
    top_contacts = db.get_top_contacts(limit=5)
    for i, contact in enumerate(top_contacts, 1):
        response_str = f"{contact['avg_response_hours']:.1f}h" if contact.get('avg_response_hours') else "N/A"
        print(f"  {i}. {contact['name']} ({contact['email']})")
        print(f"     Emails: {contact['total_emails']}, Meetings: {contact['meeting_count']}")
        print(f"     Response time: {response_str}")
        print(f"     Importance: {contact['importance_score']:.1f}")
        print()
    
    print("="*60 + "\n")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"Population failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
