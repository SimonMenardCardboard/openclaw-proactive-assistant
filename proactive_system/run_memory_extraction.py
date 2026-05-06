#!/usr/bin/env python3
"""
Memory Layer Integration Script

Runs all memory extractors in sequence:
1. Populate contacts from email (30-day history)
2. Extract preferences from emails
3. Extract tasks from emails
4. Parse shopping lists from emails to self
5. Enrich people (roles, companies, relationships)
6. Detect VIPs

Usage:
    python3 run_memory_extraction.py [--days 30]
"""

import sys
from pathlib import Path
import argparse
import logging

sys.path.insert(0, str(Path(__file__).parent))

from context_database import ContextDatabase
from universal_email_api import UniversalAccountManager
from universal_calendar_api import UniversalCalendarManager
from preference_extractor import PreferenceExtractor
from task_extractor import TaskExtractor
from shopping_list_parser import ShoppingListParser
from people_enrichment import PeopleEnrichment

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [MEMORY] %(message)s'
)
logger = logging.getLogger(__name__)


class MemoryExtractor:
    """Orchestrates all memory extraction."""
    
    def __init__(self):
        self.db = ContextDatabase()
        self.email_manager = UniversalAccountManager()
        self.cal_manager = UniversalCalendarManager()
        self.pref_extractor = PreferenceExtractor()
        self.task_extractor = TaskExtractor()
        self.shopping_parser = ShoppingListParser()
        self.people_enricher = PeopleEnrichment()
    
    def run_full_extraction(self, days_back: int = 30):
        """
        Run complete memory extraction.
        
        Args:
            days_back: Days of email history to analyze
        """
        logger.info(f"Starting memory extraction ({days_back} days)")
        logger.info("=" * 80)
        
        # 1. Get all emails
        logger.info("Fetching emails...")
        all_emails = []
        user_email = None
        
        for account in self.email_manager.get_all_accounts():
            email = account['email']
            if not user_email:
                user_email = email
            
            api = self.email_manager.get_account(email)
            if api:
                messages = api.get_all_messages_30_days(max_results=500)
                all_emails.extend(messages)
                logger.info(f"  {email}: {len(messages)} messages")
        
        logger.info(f"Total emails: {len(all_emails)}")
        
        # 2. Extract preferences
        logger.info("\n[1/5] Extracting preferences...")
        preferences = self.pref_extractor.extract_from_emails(all_emails)
        self.pref_extractor.save_preferences(preferences)
        logger.info(f"  ✅ Saved {len(preferences)} preferences")
        
        # 3. Extract tasks
        logger.info("\n[2/5] Extracting tasks...")
        task_count = 0
        for email in all_emails:
            task_count += self.task_extractor.extract_and_store(email)
        logger.info(f"  ✅ Extracted {task_count} tasks")
        
        # 4. Parse shopping lists (only from emails to self)
        logger.info("\n[3/5] Parsing shopping lists...")
        shopping_items = []
        for email in all_emails:
            if user_email:
                items = self.shopping_parser.parse_from_email(email, user_email)
                shopping_items.extend(items)
        
        self.shopping_parser.save_items(shopping_items)
        logger.info(f"  ✅ Found {len(shopping_items)} shopping items")
        
        # 5. Enrich people
        logger.info("\n[4/5] Enriching contact data...")
        enrichments = self.people_enricher.enrich_from_emails(all_emails)
        self.people_enricher.update_contacts(enrichments)
        logger.info(f"  ✅ Enriched {len(enrichments)} contacts")
        
        # 6. Detect VIPs
        logger.info("\n[5/5] Detecting VIP contacts...")
        vips = self.people_enricher.detect_vips()
        logger.info(f"  ✅ Marked {len(vips)} VIP contacts")
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("Memory Extraction Complete!")
        logger.info("=" * 80)
        logger.info(f"  Preferences: {len(preferences)}")
        logger.info(f"  Tasks: {task_count}")
        logger.info(f"  Shopping Items: {len(shopping_items)}")
        logger.info(f"  Enriched Contacts: {len(enrichments)}")
        logger.info(f"  VIPs: {len(vips)}")
        
        return {
            'preferences': len(preferences),
            'tasks': task_count,
            'shopping_items': len(shopping_items),
            'enriched_contacts': len(enrichments),
            'vips': len(vips)
        }


def main():
    """Run memory extraction."""
    parser = argparse.ArgumentParser(description='Memory Layer Extraction')
    parser.add_argument('--days', type=int, default=30, help='Days of history to analyze')
    
    args = parser.parse_args()
    
    extractor = MemoryExtractor()
    results = extractor.run_full_extraction(days_back=args.days)
    
    print("\n✅ Memory extraction complete!")
    print(f"Run again with --days N to analyze different time window")


if __name__ == '__main__':
    main()
