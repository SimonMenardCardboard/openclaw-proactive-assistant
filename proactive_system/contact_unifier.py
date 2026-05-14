#!/usr/bin/env python3
"""
Contact Unifier (Merged Intelligence Layer)

Multi-source contact sync with fuzzy deduplication:
- Syncs from Google, Microsoft, email headers
- Fuzzy name matching (85% similarity threshold)
- One person → multiple emails
- Source tracking

Merged from vm_services/intelligence/ into proactive_system/
"""

import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from difflib import SequenceMatcher
import json

# Fuzzy matching threshold for names (0.0 - 1.0)
NAME_SIMILARITY_THRESHOLD = 0.85


class ContactUnifier:
    """Unified contact management with fuzzy deduplication."""
    
    def __init__(self, context_db_path: Optional[Path] = None):
        """
        Initialize contact unifier.
        
        Args:
            context_db_path: Path to context database
        """
        if context_db_path is None:
            context_db_path = Path(__file__).parent / "context.db"
        
        self.db_path = Path(context_db_path)
    
    def fuzzy_match_names(self, name1: str, name2: str) -> float:
        """
        Calculate similarity between two names.
        
        Args:
            name1: First name
            name2: Second name
            
        Returns:
            Similarity score 0.0-1.0
        """
        if not name1 or not name2:
            return 0.0
        
        # Normalize
        n1 = name1.lower().strip()
        n2 = name2.lower().strip()
        
        if n1 == n2:
            return 1.0
        
        # Use difflib for fuzzy matching
        return SequenceMatcher(None, n1, n2).ratio()
    
    def find_duplicate_contacts(self, threshold: float = NAME_SIMILARITY_THRESHOLD) -> List[List[str]]:
        """
        Find contacts that are likely duplicates.
        
        Args:
            threshold: Similarity threshold (0.0-1.0)
            
        Returns:
            List of duplicate groups [[email1, email2], ...]
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all contacts with names
        cursor.execute('''
            SELECT email, primary_name
            FROM unified_contacts
            WHERE primary_name IS NOT NULL AND primary_name != ''
        ''')
        
        contacts = cursor.fetchall()
        conn.close()
        
        duplicates = []
        checked = set()
        
        for i, (email1, name1) in enumerate(contacts):
            if email1 in checked:
                continue
            
            group = [email1]
            
            for email2, name2 in contacts[i+1:]:
                if email2 in checked:
                    continue
                
                similarity = self.fuzzy_match_names(name1, name2)
                
                if similarity >= threshold:
                    group.append(email2)
                    checked.add(email2)
            
            if len(group) > 1:
                duplicates.append(group)
                for email in group:
                    checked.add(email)
        
        return duplicates
    
    def merge_contacts(self, email_group: List[str], primary_email: Optional[str] = None) -> int:
        """
        Merge multiple contact records into one.
        
        Args:
            email_group: List of emails to merge
            primary_email: Which email to use as primary (default: first)
            
        Returns:
            Unified contact ID
        """
        if not email_group:
            return None
        
        if primary_email is None:
            primary_email = email_group[0]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get primary contact
        cursor.execute('''
            SELECT id, primary_name, company, role, importance_score
            FROM unified_contacts
            WHERE primary_email = ?
        ''', (primary_email,))
        
        primary = cursor.fetchone()
        
        if not primary:
            # Create new unified contact
            cursor.execute('''
                INSERT INTO unified_contacts (primary_email, primary_name)
                VALUES (?, ?)
            ''', (primary_email, primary_email.split('@')[0].replace('.', ' ').title()))
            
            unified_id = cursor.lastrowid
        else:
            unified_id = primary[0]
        
        # Link all emails to this unified contact
        for email in email_group:
            cursor.execute('''
                INSERT OR REPLACE INTO contact_emails
                (unified_contact_id, email, is_primary)
                VALUES (?, ?, ?)
            ''', (unified_id, email, 1 if email == primary_email else 0))
        
        conn.commit()
        conn.close()
        
        return unified_id
    
    def sync_from_email_headers(self, account: str = "lacrosseguy76665@gmail.com", days: int = 90) -> int:
        """
        Extract contacts from email headers.
        
        Args:
            account: Email account to scan
            days: Number of days to look back
            
        Returns:
            Number of contacts discovered
        """
        # Import from existing proactive_system
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        
        try:
            from universal_email_api import UniversalAccountManager
            
            manager = UniversalAccountManager()
            emails = manager.get_emails(account, days_back=days, max_results=500)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            discovered = set()
            
            for email in emails:
                from_addr = self._extract_email(email.get('from', ''))
                from_name = self._extract_name(email.get('from', ''))
                
                if from_addr and from_addr not in discovered:
                    # Create or update unified contact
                    cursor.execute('''
                        INSERT OR IGNORE INTO unified_contacts
                        (primary_email, primary_name, first_contact)
                        VALUES (?, ?, ?)
                    ''', (from_addr, from_name, datetime.now()))
                    
                    # Link email
                    cursor.execute('SELECT id FROM unified_contacts WHERE primary_email = ?', (from_addr,))
                    contact_id = cursor.fetchone()[0]
                    
                    cursor.execute('''
                        INSERT OR IGNORE INTO contact_emails
                        (unified_contact_id, email, source, source_account, is_primary)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (contact_id, from_addr, 'email_headers', account, 1))
                    
                    discovered.add(from_addr)
            
            conn.commit()
            conn.close()
            
            print(f"✅ Discovered {len(discovered)} contacts from email headers")
            return len(discovered)
            
        except Exception as e:
            print(f"❌ Error syncing email contacts: {e}")
            return 0
    
    def get_all_contacts_for_person(self, email: str) -> List[str]:
        """
        Get all email addresses for a person.
        
        Args:
            email: Any email address for this person
            
        Returns:
            List of all emails
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Find unified contact ID
        cursor.execute('''
            SELECT unified_contact_id
            FROM contact_emails
            WHERE email = ?
        ''', (email,))
        
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return [email]
        
        unified_id = result[0]
        
        # Get all emails for this contact
        cursor.execute('''
            SELECT email
            FROM contact_emails
            WHERE unified_contact_id = ?
        ''', (unified_id,))
        
        emails = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return emails
    
    def _extract_email(self, from_field: str) -> str:
        """Extract email from 'Name <email>' format."""
        match = re.search(r'<(.+?)>', from_field)
        if match:
            return match.group(1).lower().strip()
        return from_field.lower().strip()
    
    def _extract_name(self, from_field: str) -> str:
        """Extract name from 'Name <email>' format."""
        match = re.search(r'^([^<]+)\s*<', from_field)
        if match:
            name = match.group(1).strip().strip('"\'')
            return name
        
        email = self._extract_email(from_field)
        if email:
            name_part = email.split('@')[0]
            return name_part.replace('.', ' ').replace('_', ' ').title()
        
        return ''


if __name__ == "__main__":
    # Demo usage
    unifier = ContactUnifier()
    
    # Find duplicates
    duplicates = unifier.find_duplicate_contacts(threshold=0.85)
    print(f"\n🔍 Found {len(duplicates)} duplicate groups:")
    for group in duplicates[:5]:
        print(f"  {group}")
    
    # Sync from email headers
    count = unifier.sync_from_email_headers(days=90)
    print(f"\n✅ Synced {count} contacts from email headers")
