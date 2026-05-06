#!/usr/bin/env python3
"""
People Enrichment Engine

Extracts metadata about contacts from email patterns:
1. Roles/Titles (from signatures)
2. Companies/Organizations
3. Relationships (colleague, client, vendor, friend, family)
4. Communication patterns (frequency, topics)
5. VIP detection (frequent + fast response)

Updates contacts table in context database.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import sqlite3

# Role/title patterns (extracted from email signatures)
ROLE_PATTERNS = [
    r'(?:^|\n)([A-Z][a-z]+\s+[A-Z][a-z]+)\s*\n\s*([A-Z][a-zA-Z\s&]+)(?:\n|$)',  # Name\nTitle
    r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s*[|\-]\s*([A-Z][a-zA-Z\s&]+)',  # Name | Title
    r'^([A-Z][a-zA-Z\s&]+)(?:\n|\r)',  # Title on first line
]

# Company patterns
COMPANY_PATTERNS = [
    r'(?:at|@)\s+([A-Z][a-zA-Z\s&]+(?:Inc|LLC|Corp|Ltd)?)',
    r'([A-Z][a-zA-Z\s&]+(?:Inc|LLC|Corp|Ltd)\.?)',
]

# Relationship indicators
RELATIONSHIP_INDICATORS = {
    'colleague': ['team', 'meeting', 'project', 'report', 'deadline', 'standup'],
    'client': ['invoice', 'contract', 'proposal', 'deliverable', 'payment'],
    'vendor': ['quote', 'purchase', 'order', 'supplier', 'delivery'],
    'friend': ['hang out', 'catch up', 'how are you', 'long time', 'drinks', 'dinner'],
    'family': ['mom', 'dad', 'sister', 'brother', 'aunt', 'uncle', 'cousin'],
}

# VIP thresholds
VIP_MIN_EMAILS = 20
VIP_MIN_IMPORTANCE = 40


class PeopleEnrichment:
    """Enrich contact information from email patterns."""
    
    def __init__(self, context_db_path: Optional[Path] = None):
        """
        Initialize people enrichment engine.
        
        Args:
            context_db_path: Path to context database
        """
        if context_db_path is None:
            context_db_path = Path.home() / ".openclaw/workspace/transmogrifier/openclaw-proactive-assistant/proactive_system/context.db"
        
        self.context_db_path = Path(context_db_path)
    
    def enrich_from_email(self, email: Dict) -> Dict:
        """
        Extract enrichment data from a single email.
        
        Args:
            email: Email dict with from, subject, body
            
        Returns:
            Dict with: email, name, role, company, relationship
        """
        from_addr = self._extract_email(email.get('from', ''))
        from_name = self._extract_name(email.get('from', ''))
        body = email.get('body', '')
        subject = email.get('subject', '')
        
        # Extract role from signature
        role = self._extract_role(body)
        
        # Extract company from signature
        company = self._extract_company(body)
        
        # Infer relationship from email content
        relationship = self._infer_relationship(subject, body)
        
        return {
            'email': from_addr,
            'name': from_name,
            'role': role,
            'company': company,
            'relationship': relationship
        }
    
    def enrich_from_emails(self, emails: List[Dict]) -> Dict[str, Dict]:
        """
        Enrich contacts from multiple emails.
        
        Args:
            emails: List of email dicts
            
        Returns:
            Dict mapping email -> enrichment data
        """
        enrichments = {}
        
        for email in emails:
            data = self.enrich_from_email(email)
            email_addr = data['email']
            
            if email_addr not in enrichments:
                enrichments[email_addr] = data
            else:
                # Merge with existing data (prefer non-None values)
                for key, value in data.items():
                    if value and not enrichments[email_addr].get(key):
                        enrichments[email_addr][key] = value
        
        return enrichments
    
    def update_contacts(self, enrichments: Dict[str, Dict]):
        """
        Update contacts table with enrichment data.
        
        Args:
            enrichments: Dict mapping email -> enrichment data
        """
        conn = sqlite3.connect(self.context_db_path)
        cursor = conn.cursor()
        
        for email, data in enrichments.items():
            # Check if contact exists
            cursor.execute('SELECT id FROM contacts WHERE email = ?', (email,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing contact
                updates = []
                params = []
                
                if data.get('name'):
                    updates.append('name = ?')
                    params.append(data['name'])
                
                if data.get('role'):
                    updates.append('role = ?')
                    params.append(data['role'])
                
                if data.get('company'):
                    updates.append('company = ?')
                    params.append(data['company'])
                
                if data.get('relationship'):
                    updates.append('relationship = ?')
                    params.append(data['relationship'])
                
                if updates:
                    params.append(email)
                    cursor.execute(f'''
                        UPDATE contacts
                        SET {', '.join(updates)}
                        WHERE email = ?
                    ''', params)
        
        conn.commit()
        conn.close()
    
    def detect_vips(self, min_emails: int = VIP_MIN_EMAILS, min_importance: float = VIP_MIN_IMPORTANCE):
        """
        Detect and mark VIP contacts.
        
        Args:
            min_emails: Minimum email count
            min_importance: Minimum importance score
        """
        conn = sqlite3.connect(self.context_db_path)
        cursor = conn.cursor()
        
        # Find contacts meeting VIP criteria
        cursor.execute('''
            SELECT email FROM contacts
            WHERE total_emails >= ? AND importance_score >= ?
        ''', (min_emails, min_importance))
        
        vip_emails = [row[0] for row in cursor.fetchall()]
        
        # Mark as VIP
        for email in vip_emails:
            cursor.execute('''
                UPDATE contacts
                SET is_vip = 1
                WHERE email = ?
            ''', (email,))
        
        conn.commit()
        conn.close()
        
        return vip_emails
    
    def _extract_email(self, from_field: str) -> str:
        """Extract email from 'Name <email>' format."""
        match = re.search(r'<(.+?)>', from_field)
        if match:
            return match.group(1).lower().strip()
        return from_field.lower().strip()
    
    def _extract_name(self, from_field: str) -> str:
        """Extract name from 'Name <email>' format."""
        # Try to find name before <email>
        match = re.search(r'^([^<]+)\s*<', from_field)
        if match:
            name = match.group(1).strip()
            # Remove quotes if present
            name = name.strip('"\'')
            return name
        
        # If no <email>, try to extract from email
        email = self._extract_email(from_field)
        if email:
            # Take part before @
            name_part = email.split('@')[0]
            # Replace dots/underscores with spaces and title case
            name = name_part.replace('.', ' ').replace('_', ' ').title()
            return name
        
        return ''
    
    def _extract_role(self, body: str) -> Optional[str]:
        """Extract role/title from email signature."""
        # Look for common signature patterns
        lines = body.split('\n')
        
        # Signatures are usually at the end
        signature_lines = lines[-10:] if len(lines) > 10 else lines
        
        for i, line in enumerate(signature_lines):
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Common title keywords
            title_keywords = ['CEO', 'CTO', 'CFO', 'VP', 'Director', 'Manager', 'Engineer', 
                            'Developer', 'Designer', 'Analyst', 'Consultant', 'Partner',
                            'Attorney', 'Lawyer', 'Counsel', 'Associate', 'Senior', 'Lead',
                            'Chief', 'President', 'Founder', 'Co-Founder']
            
            for keyword in title_keywords:
                if keyword.lower() in line.lower():
                    # Clean up the line
                    role = re.sub(r'^\W+|\W+$', '', line)
                    if 5 < len(role) < 50:  # Reasonable title length
                        return role
        
        return None
    
    def _extract_company(self, body: str) -> Optional[str]:
        """Extract company from email signature."""
        lines = body.split('\n')
        signature_lines = lines[-10:] if len(lines) > 10 else lines
        
        for line in signature_lines:
            line = line.strip()
            
            # Look for company indicators (Inc, LLC, Corp, Ltd)
            for pattern in COMPANY_PATTERNS:
                match = re.search(pattern, line)
                if match:
                    company = match.group(1).strip()
                    if 3 < len(company) < 50:
                        return company
        
        return None
    
    def _infer_relationship(self, subject: str, body: str) -> Optional[str]:
        """Infer relationship type from email content."""
        text = f"{subject} {body}".lower()
        
        # Score each relationship type
        scores = {}
        
        for relationship, keywords in RELATIONSHIP_INDICATORS.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                scores[relationship] = score
        
        # Return highest scoring relationship (if confident)
        if scores:
            best_relationship = max(scores, key=scores.get)
            if scores[best_relationship] >= 2:  # At least 2 keyword matches
                return best_relationship
        
        return None
    
    def get_enriched_contacts(self, limit: int = 50) -> List[Dict]:
        """
        Get enriched contacts.
        
        Args:
            limit: Max contacts to return
            
        Returns:
            List of contact dicts with enrichment data
        """
        conn = sqlite3.connect(self.context_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT email, name, role, company, relationship, is_vip, 
                   importance_score, total_emails, avg_response_hours
            FROM contacts
            WHERE role IS NOT NULL OR company IS NOT NULL OR relationship IS NOT NULL
            ORDER BY importance_score DESC
            LIMIT ?
        ''', (limit,))
        
        contacts = []
        for row in cursor.fetchall():
            contacts.append({
                'email': row[0],
                'name': row[1],
                'role': row[2],
                'company': row[3],
                'relationship': row[4],
                'is_vip': bool(row[5]),
                'importance_score': row[6],
                'total_emails': row[7],
                'avg_response_hours': row[8]
            })
        
        conn.close()
        return contacts


def main():
    """Test people enrichment."""
    enricher = PeopleEnrichment()
    
    # Test emails
    test_emails = [
        {
            'from': 'Sarah Johnson <sarah@acme.com>',
            'subject': 'Q2 Project Update',
            'body': '''Hi,

Here's the latest on the project. Let me know if you have questions.

Best,
Sarah Johnson
Senior Project Manager
Acme Corporation
''',
        },
        {
            'from': 'john.smith@consulting.com',
            'subject': 'Contract Review',
            'body': '''Per our discussion, attached is the contract for your review.

Looking forward to working together.

John Smith
Managing Partner | Smith Consulting LLC
john.smith@consulting.com
''',
        },
    ]
    
    print("People Enrichment Test")
    print("=" * 80)
    
    # Enrich from emails
    enrichments = enricher.enrich_from_emails(test_emails)
    
    print(f"\nExtracted data for {len(enrichments)} contacts:\n")
    
    for email, data in enrichments.items():
        print(f"📧 {email}")
        if data.get('name'):
            print(f"   Name: {data['name']}")
        if data.get('role'):
            print(f"   Role: {data['role']}")
        if data.get('company'):
            print(f"   Company: {data['company']}")
        if data.get('relationship'):
            print(f"   Relationship: {data['relationship']}")
        print()
    
    # Update database
    enricher.update_contacts(enrichments)
    print(f"✅ Updated {len(enrichments)} contacts in database")


if __name__ == '__main__':
    main()
