#!/usr/bin/env python3
"""
Contact Unification System

Pulls contacts from multiple sources (Gmail, Outlook, iCloud, email headers)
and merges duplicates into unified contact records.

Features:
- Multi-source contact sync (Google, Microsoft, email auto-discovery)
- Duplicate detection (email, name fuzzy match, phone)
- Unified contact records (one person → many emails)
- Source tracking (which account/provider each email came from)
- Integration with people_enrichment for metadata
"""

import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from difflib import SequenceMatcher
import json

# Fuzzy matching threshold for names (0.0 - 1.0)
NAME_SIMILARITY_THRESHOLD = 0.85

# Common email domain patterns that likely indicate same organization
SAME_ORG_DOMAINS = ['gmail.com', 'outlook.com', 'hotmail.com', 'yahoo.com', 'icloud.com']


class ContactUnification:
    """Unified contact management across multiple sources."""
    
    def __init__(self, context_db_path: Optional[Path] = None):
        """
        Initialize contact unification system.
        
        Args:
            context_db_path: Path to context database
        """
        if context_db_path is None:
            context_db_path = Path.home() / ".openclaw/workspace/integrations/intelligence/data/context.db"
        
        self.context_db_path = Path(context_db_path)
        self._init_database()
    
    def _init_database(self):
        """Create unified contact tables."""
        conn = sqlite3.connect(self.context_db_path)
        cursor = conn.cursor()
        
        # Unified contacts (master records)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS unified_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                primary_name TEXT NOT NULL,
                primary_email TEXT,
                phone TEXT,
                company TEXT,
                role TEXT,
                relationship TEXT,
                is_vip BOOLEAN DEFAULT 0,
                importance_score REAL DEFAULT 0.0,
                total_emails INTEGER DEFAULT 0,
                total_meetings INTEGER DEFAULT 0,
                first_contact TIMESTAMP,
                last_contact TIMESTAMP,
                notes TEXT,
                metadata TEXT,  -- JSON for additional fields
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Contact emails (one person → many emails)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contact_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unified_contact_id INTEGER NOT NULL,
                email TEXT NOT NULL UNIQUE,
                is_primary BOOLEAN DEFAULT 0,
                source TEXT,  -- 'google', 'microsoft', 'email_headers', 'icloud'
                source_account TEXT,  -- which account this came from
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (unified_contact_id) REFERENCES unified_contacts(id)
            )
        ''')
        
        # Contact sources (track raw source data)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contact_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                source TEXT NOT NULL,  -- 'google', 'microsoft', 'email_headers'
                source_account TEXT,
                raw_data TEXT,  -- JSON of original contact data
                synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(email, source, source_account)
            )
        ''')
        
        # Indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_contact_emails_email ON contact_emails(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_contact_emails_unified ON contact_emails(unified_contact_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_contact_sources_email ON contact_sources(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_unified_contacts_name ON unified_contacts(primary_name)')
        
        conn.commit()
        conn.close()
    
    def sync_google_contacts(self, account: str = "lacrosseguy76665@gmail.com") -> int:
        """
        Sync contacts from Google People API.
        
        Args:
            account: Gmail account to sync
            
        Returns:
            Number of contacts synced
        """
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            
            # Load OAuth token
            token_path = Path.home() / ".openclaw/workspace/integrations/direct_api/token.json"
            if not token_path.exists():
                print(f"⚠️  Token not found: {token_path}")
                return 0
            
            with open(token_path) as f:
                token_data = json.load(f)
            
            creds = Credentials(
                token=token_data['token'],
                refresh_token=token_data.get('refresh_token'),
                token_uri='https://oauth2.googleapis.com/token',
                client_id=token_data.get('client_id'),
                client_secret=token_data.get('client_secret')
            )
            
            service = build('people', 'v1', credentials=creds)
            
            # Fetch all contacts
            results = service.people().connections().list(
                resourceName='people/me',
                pageSize=1000,
                personFields='names,emailAddresses,phoneNumbers,organizations'
            ).execute()
            
            connections = results.get('connections', [])
            
            conn = sqlite3.connect(self.context_db_path)
            cursor = conn.cursor()
            
            synced = 0
            
            for person in connections:
                # Extract data
                names = person.get('names', [])
                emails = person.get('emailAddresses', [])
                phones = person.get('phoneNumbers', [])
                orgs = person.get('organizations', [])
                
                if not emails:
                    continue  # Skip contacts without email
                
                primary_name = names[0]['displayName'] if names else ''
                primary_email = emails[0]['value'] if emails else ''
                phone = phones[0]['value'] if phones else None
                company = orgs[0]['name'] if orgs else None
                role = orgs[0].get('title') if orgs and 'title' in orgs[0] else None
                
                # Store in contact_sources
                cursor.execute('''
                    INSERT OR REPLACE INTO contact_sources (email, source, source_account, raw_data)
                    VALUES (?, ?, ?, ?)
                ''', (primary_email, 'google', account, json.dumps(person)))
                
                # Add to unification (will be processed in merge step)
                synced += 1
            
            conn.commit()
            conn.close()
            
            print(f"✅ Synced {synced} contacts from Google ({account})")
            return synced
            
        except Exception as e:
            print(f"❌ Error syncing Google contacts: {e}")
            return 0
    
    def sync_microsoft_contacts(self, account: str = "simon@legalmensch.com") -> int:
        """
        Sync contacts from Microsoft Graph API.
        
        Args:
            account: Microsoft account to sync
            
        Returns:
            Number of contacts synced
        """
        # TODO: Implement when Microsoft Graph credentials available
        print(f"⚠️  Microsoft contacts sync not yet implemented for {account}")
        return 0
    
    def sync_email_contacts(self, account: str = "lacrosseguy76665@gmail.com", days: int = 90, token_file: Optional[Path] = None) -> int:
        """
        Extract contacts from email headers (from/to/cc).
        
        Args:
            account: Email account to scan
            days: Number of days to look back
            token_file: Path to OAuth token file (auto-detected if None)
            
        Returns:
            Number of contacts discovered
        """
        try:
            # Import gmail_api from existing code
            import sys
            sys.path.insert(0, str(Path(__file__).parent))
            from gmail_api import GmailAPI
            
            # Determine token file if not provided
            if token_file is None:
                token_file = Path.home() / ".openclaw/tokens/default_google_personal.json"
            
            gmail = GmailAPI(email=account, token_file=token_file)
            
            # Fetch recent sent emails (better for contact discovery)
            emails = gmail.get_sent_messages(days_back=days, max_results=500)
            
            conn = sqlite3.connect(self.context_db_path)
            cursor = conn.cursor()
            
            discovered = set()
            
            for email in emails:
                # Extract all email addresses from headers
                from_addr = self._extract_email(email.get('from', ''))
                from_name = self._extract_name(email.get('from', ''))
                
                if from_addr and from_addr not in discovered:
                    # Store in contact_sources
                    cursor.execute('''
                        INSERT OR IGNORE INTO contact_sources (email, source, source_account, raw_data)
                        VALUES (?, ?, ?, ?)
                    ''', (from_addr, 'email_headers', account, json.dumps({
                        'name': from_name,
                        'from': email.get('from', '')
                    })))
                    discovered.add(from_addr)
                
                # Also extract from To/CC if available
                for field in ['to', 'cc']:
                    recipients = email.get(field, [])
                    if isinstance(recipients, str):
                        recipients = [recipients]
                    
                    for recipient in recipients:
                        addr = self._extract_email(recipient)
                        name = self._extract_name(recipient)
                        
                        if addr and addr not in discovered:
                            cursor.execute('''
                                INSERT OR IGNORE INTO contact_sources (email, source, source_account, raw_data)
                                VALUES (?, ?, ?, ?)
                            ''', (addr, 'email_headers', account, json.dumps({
                                'name': name,
                                'from': recipient
                            })))
                            discovered.add(addr)
            
            conn.commit()
            conn.close()
            
            print(f"✅ Discovered {len(discovered)} contacts from email headers ({account})")
            return len(discovered)
            
        except Exception as e:
            print(f"❌ Error syncing email contacts: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    def merge_duplicates(self) -> int:
        """
        Detect and merge duplicate contacts across all sources.
        
        Returns:
            Number of duplicates merged
        """
        conn = sqlite3.connect(self.context_db_path)
        cursor = conn.cursor()
        
        # Get all unique emails from sources
        cursor.execute('SELECT DISTINCT email, source, source_account, raw_data FROM contact_sources')
        all_contacts = cursor.fetchall()
        
        # Group by email (exact matches)
        email_groups = {}
        for email, source, source_account, raw_data in all_contacts:
            if email not in email_groups:
                email_groups[email] = []
            email_groups[email].append({
                'email': email,
                'source': source,
                'source_account': source_account,
                'raw_data': json.loads(raw_data) if raw_data else {}
            })
        
        # Now detect name-based duplicates (fuzzy matching)
        name_to_emails = {}
        for email, contacts in email_groups.items():
            # Get best name from all sources
            names = []
            for contact in contacts:
                raw = contact['raw_data']
                name = raw.get('name') or raw.get('displayName') or self._extract_name(email)
                if name:
                    names.append(self._normalize_name(name))
            
            if names:
                best_name = max(names, key=len)  # Prefer longer names
                
                # Check for fuzzy matches with existing names
                matched = False
                for existing_name in name_to_emails.keys():
                    if self._names_similar(best_name, existing_name):
                        name_to_emails[existing_name].append(email)
                        matched = True
                        break
                
                if not matched:
                    name_to_emails[best_name] = [email]
        
        # Create unified contacts
        merged = 0
        
        for name, emails in name_to_emails.items():
            # Check if unified contact already exists for any of these emails
            cursor.execute('''
                SELECT uc.id FROM unified_contacts uc
                JOIN contact_emails ce ON uc.id = ce.unified_contact_id
                WHERE ce.email IN ({})
            '''.format(','.join('?' * len(emails))), emails)
            
            existing = cursor.fetchone()
            
            if existing:
                unified_id = existing[0]
            else:
                # Create new unified contact
                cursor.execute('''
                    INSERT INTO unified_contacts (primary_name, primary_email, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                ''', (name, emails[0], datetime.now(), datetime.now()))
                
                unified_id = cursor.lastrowid
                merged += 1
            
            # Link all emails to this unified contact
            for email in emails:
                # Get sources for this email
                for contact_list in email_groups.get(email, []):
                    cursor.execute('''
                        INSERT OR IGNORE INTO contact_emails 
                        (unified_contact_id, email, is_primary, source, source_account)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        unified_id,
                        email,
                        1 if email == emails[0] else 0,
                        contact_list['source'],
                        contact_list['source_account']
                    ))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Merged {merged} unified contacts")
        return merged
    
    def enrich_contacts(self):
        """Enrich unified contacts with metadata from email patterns."""
        try:
            from people_enrichment import PeopleEnrichment
            
            enricher = PeopleEnrichment(self.context_db_path)
            
            # Get all contacts from old contacts table
            conn = sqlite3.connect(self.context_db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT email, name, role, company, relationship, is_vip, 
                       importance_score, total_emails
                FROM contacts
            ''')
            
            for row in cursor.fetchall():
                email, name, role, company, relationship, is_vip, importance_score, total_emails = row
                
                # Find unified contact for this email
                cursor.execute('''
                    SELECT unified_contact_id FROM contact_emails
                    WHERE email = ?
                ''', (email,))
                
                result = cursor.fetchone()
                if result:
                    unified_id = result[0]
                    
                    # Update unified contact with enrichment data
                    cursor.execute('''
                        UPDATE unified_contacts
                        SET role = COALESCE(role, ?),
                            company = COALESCE(company, ?),
                            relationship = COALESCE(relationship, ?),
                            is_vip = COALESCE(is_vip, ?),
                            importance_score = COALESCE(importance_score, ?),
                            total_emails = COALESCE(total_emails, ?)
                        WHERE id = ?
                    ''', (role, company, relationship, is_vip, importance_score, total_emails, unified_id))
            
            conn.commit()
            conn.close()
            
            print("✅ Enriched unified contacts with existing metadata")
            
        except Exception as e:
            print(f"⚠️  Error enriching contacts: {e}")
    
    def search_contacts(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search unified contacts.
        
        Args:
            query: Search query (name or email)
            limit: Max results
            
        Returns:
            List of unified contact dicts with all email addresses
        """
        conn = sqlite3.connect(self.context_db_path)
        cursor = conn.cursor()
        
        query_lower = query.lower()
        
        cursor.execute('''
            SELECT DISTINCT uc.id, uc.primary_name, uc.primary_email, uc.phone,
                   uc.company, uc.role, uc.relationship, uc.is_vip,
                   uc.importance_score, uc.total_emails, uc.total_meetings
            FROM unified_contacts uc
            LEFT JOIN contact_emails ce ON uc.id = ce.unified_contact_id
            WHERE LOWER(uc.primary_name) LIKE ? OR LOWER(ce.email) LIKE ?
            ORDER BY uc.importance_score DESC
            LIMIT ?
        ''', (f'%{query_lower}%', f'%{query_lower}%', limit))
        
        results = []
        for row in cursor.fetchall():
            contact_id = row[0]
            
            # Get all emails for this contact
            cursor.execute('''
                SELECT email, is_primary, source, source_account
                FROM contact_emails
                WHERE unified_contact_id = ?
            ''', (contact_id,))
            
            emails = []
            for email_row in cursor.fetchall():
                emails.append({
                    'email': email_row[0],
                    'is_primary': bool(email_row[1]),
                    'source': email_row[2],
                    'source_account': email_row[3]
                })
            
            results.append({
                'id': row[0],
                'name': row[1],
                'primary_email': row[2],
                'phone': row[3],
                'company': row[4],
                'role': row[5],
                'relationship': row[6],
                'is_vip': bool(row[7]),
                'importance_score': row[8],
                'total_emails': row[9],
                'total_meetings': row[10],
                'emails': emails
            })
        
        conn.close()
        return results
    
    def get_contact_by_email(self, email: str) -> Optional[Dict]:
        """
        Get unified contact by any associated email.
        
        Args:
            email: Email address
            
        Returns:
            Unified contact dict or None
        """
        results = self.search_contacts(email, limit=1)
        return results[0] if results else None
    
    def get_stats(self) -> Dict:
        """Get unification statistics."""
        conn = sqlite3.connect(self.context_db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM unified_contacts')
        total_unified = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT email) FROM contact_emails')
        total_emails = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT source) FROM contact_sources')
        total_sources = cursor.fetchone()[0]
        
        cursor.execute('SELECT source, COUNT(*) FROM contact_sources GROUP BY source')
        source_counts = dict(cursor.fetchall())
        
        conn.close()
        
        return {
            'total_unified_contacts': total_unified,
            'total_email_addresses': total_emails,
            'total_sources': total_sources,
            'contacts_per_source': source_counts,
            'deduplication_ratio': f"{total_emails}/{total_unified}" if total_unified > 0 else "N/A"
        }
    
    # Helper methods
    
    def _get_connection(self):
        """Get database connection."""
        return sqlite3.connect(self.context_db_path)
    
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
        
        # If no name found, derive from email
        email = self._extract_email(from_field)
        if '@' in email:
            name_part = email.split('@')[0]
            return name_part.replace('.', ' ').replace('_', ' ').title()
        
        return ''
    
    def _normalize_name(self, name: str) -> str:
        """Normalize name for comparison."""
        # Remove common suffixes
        name = re.sub(r'\s+(Jr\.?|Sr\.?|III|II|IV)$', '', name, flags=re.IGNORECASE)
        # Remove extra whitespace
        name = ' '.join(name.split())
        # Lowercase for comparison
        return name.lower().strip()
    
    def _names_similar(self, name1: str, name2: str) -> bool:
        """Check if two names are similar enough to be the same person."""
        norm1 = self._normalize_name(name1)
        norm2 = self._normalize_name(name2)
        
        # Exact match
        if norm1 == norm2:
            return True
        
        # Check sequence similarity
        similarity = SequenceMatcher(None, norm1, norm2).ratio()
        
        return similarity >= NAME_SIMILARITY_THRESHOLD


def main():
    """Test contact unification."""
    unifier = ContactUnification()
    
    print("Contact Unification System")
    print("=" * 80)
    
    # Sync from sources
    print("\n1. Syncing contacts from sources...")
    # google_count = unifier.sync_google_contacts()  # Requires People API scope
    email_count = unifier.sync_email_contacts()
    
    # Merge duplicates
    print("\n2. Merging duplicates...")
    merged = unifier.merge_duplicates()
    
    # Enrich
    print("\n3. Enriching with metadata...")
    unifier.enrich_contacts()
    
    # Stats
    print("\n4. Statistics:")
    print("-" * 80)
    stats = unifier.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # Search test
    print("\n5. Search test (query: 'simon'):")
    print("-" * 80)
    results = unifier.search_contacts('simon', limit=5)
    for contact in results:
        print(f"\n📧 {contact['name']} ({contact['primary_email']})")
        if contact.get('company'):
            print(f"   Company: {contact['company']}")
        if contact.get('role'):
            print(f"   Role: {contact['role']}")
        print(f"   Email addresses ({len(contact['emails'])}):")
        for email in contact['emails']:
            primary = "⭐" if email['is_primary'] else "  "
            print(f"     {primary} {email['email']} ({email['source']})")


if __name__ == '__main__':
    main()
