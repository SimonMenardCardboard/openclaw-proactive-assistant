#!/usr/bin/env python3
"""
Universal Email API - Multi-Provider Support

Unified interface for:
- Gmail (Google Workspace)
- Microsoft (Outlook, Exchange, Office 365)
- IMAP (Yahoo, ProtonMail, custom domains)

All providers expose same methods with same output format.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# Provider-specific imports
from gmail_api import GmailAPI
from microsoft_graph_api import MicrosoftGraphAPI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UniversalEmailAPI:
    """
    Universal email API that works with any provider.
    
    Auto-detects provider from email domain or explicit provider param.
    Exposes unified interface across all providers.
    """
    
    # Domain to provider mapping
    DOMAIN_MAPPING = {
        'gmail.com': 'gmail',
        'googlemail.com': 'gmail',
        'outlook.com': 'microsoft',
        'hotmail.com': 'microsoft',
        'live.com': 'microsoft',
        'office365.com': 'microsoft',
        # Add more as needed
    }
    
    def __init__(self, 
                 email: str, 
                 provider: Optional[str] = None,
                 token_file: Optional[Path] = None,
                 credentials: Optional[Dict] = None):
        """
        Initialize universal email API.
        
        Args:
            email: User's email address
            provider: 'gmail', 'microsoft', or 'imap' (auto-detected if None)
            token_file: Path to OAuth token file (optional)
            credentials: Dict with provider-specific credentials (optional)
        """
        self.email = email
        self.provider = provider or self._detect_provider(email)
        self.backend = None
        
        # Initialize provider-specific backend
        if self.provider == 'gmail':
            self.backend = GmailAPI(email=email, token_file=token_file or self._default_token_file('gmail'))
        
        elif self.provider == 'microsoft':
            self.backend = MicrosoftGraphAPI(email=email, token_file=token_file or self._default_token_file('microsoft'))
        
        elif self.provider == 'imap':
            # IMAP requires host/port/password
            if credentials:
                from imap_email_api import ImapEmailAPI
                self.backend = ImapEmailAPI(
                    email=email,
                    imap_host=credentials.get('imap_host'),
                    imap_port=credentials.get('imap_port', 993),
                    password=credentials.get('password')
                )
            else:
                raise ValueError("IMAP provider requires credentials dict with 'imap_host' and 'password'")
        
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
        
        logger.info(f"[Universal Email] Initialized {self.provider} backend for {email}")
    
    def _detect_provider(self, email: str) -> str:
        """Auto-detect provider from email domain."""
        domain = email.split('@')[-1].lower()
        
        # Check known domains
        if domain in self.DOMAIN_MAPPING:
            return self.DOMAIN_MAPPING[domain]
        
        # Check if it's a known Google Workspace domain (custom domain using Gmail)
        # This requires checking MX records or user configuration
        # For now, default to IMAP for unknown domains
        logger.warning(f"Unknown domain {domain}, defaulting to IMAP")
        return 'imap'
    
    def _default_token_file(self, provider: str) -> Path:
        """Get default token file path for provider."""
        base_path = Path.home() / '.openclaw/workspace/integrations/intelligence/config'
        
        if provider == 'gmail':
            # Try account-specific token first
            email_safe = self.email.replace('@', '_at_').replace('.', '_')
            account_token = base_path / f'token_{email_safe}.json'
            if account_token.exists():
                return account_token
            
            # Fall back to default token
            return base_path / 'token.json'
        
        elif provider == 'microsoft':
            # Try account-specific token
            email_safe = self.email.replace('@', '_at_').replace('.', '_')
            account_token = base_path / f'token_{email_safe}_microsoft.json'
            if account_token.exists():
                return account_token
            
            # Fall back to default
            return base_path / 'token_microsoft.json'
        
        return base_path / 'token.json'
    
    # =========================================================================
    # UNIFIED INTERFACE - All providers implement these methods
    # =========================================================================
    
    def get_all_messages_30_days(self, max_results: int = 500) -> List[Dict]:
        """
        Get ALL messages from last 30 days (unified across providers).
        
        Returns:
            List of messages in standard format:
            {
                'id': str,
                'thread_id': str (Gmail) or conversation_id (Microsoft),
                'from': str,
                'to': str,
                'subject': str,
                'date': str (ISO format),
                'snippet': str (preview),
                'body': str (full text),
                'labels': List[str] (provider-specific),
                '_provider': 'gmail'|'microsoft'|'imap',
                '_email': str (account email)
            }
        """
        if not self.backend:
            logger.error("[Universal Email] No backend initialized")
            return []
        
        return self.backend.get_all_messages_30_days(max_results=max_results)
    
    def get_unread_messages(self, hours_back: int = 1, max_results: int = 20) -> List[Dict]:
        """
        Get unread messages from last N hours.
        
        Returns same format as get_all_messages_30_days()
        """
        if not self.backend:
            return []
        
        return self.backend.get_unread_messages(hours_back=hours_back, max_results=max_results)
    
    def analyze_response_times(self, messages: List[Dict]) -> Dict[str, float]:
        """
        Calculate average response time per contact (in hours).
        
        Returns:
            {
                'contact@email.com': 4.2,  # hours
                ...
            }
        """
        if not self.backend:
            return {}
        
        return self.backend.analyze_response_times(messages)
    
    def get_important_contacts(self, messages: List[Dict], top_n: int = 20) -> List[Dict]:
        """
        Score contacts by importance (frequency + response speed).
        
        Returns:
            [
                {
                    'email': str,
                    'name': str,
                    'total_emails': int,
                    'avg_response_hours': float,
                    'importance_score': float,
                    'first_contact': datetime,
                    'last_contact': datetime
                },
                ...
            ]
        """
        if not self.backend:
            return []
        
        return self.backend.get_important_contacts(messages, top_n=top_n)
    
    def send_message(self, to: str, subject: str, body: str, cc: Optional[str] = None) -> bool:
        """
        Send email (unified across providers).
        
        Args:
            to: Recipient email
            subject: Email subject
            body: Email body (plain text or HTML)
            cc: CC recipients (optional)
        
        Returns:
            True if sent successfully
        """
        if not self.backend:
            return False
        
        return self.backend.send_message(to=to, subject=subject, body=body, cc=cc)
    
    def mark_as_read(self, message_id: str) -> bool:
        """Mark message as read."""
        if not self.backend:
            return False
        
        return self.backend.mark_as_read(message_id)
    
    def mark_as_unread(self, message_id: str) -> bool:
        """Mark message as unread."""
        if not self.backend:
            return False
        
        return self.backend.mark_as_unread(message_id)
    
    def get_thread(self, thread_id: str) -> List[Dict]:
        """Get all messages in a thread/conversation."""
        if not self.backend:
            return []
        
        return self.backend.get_thread(thread_id)


class UniversalAccountManager:
    """
    Manage multiple email accounts across providers.
    
    Loads accounts from oauth_tokens.db and provides unified access.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize account manager.
        
        Args:
            db_path: Path to oauth_tokens.db (auto-detected if None)
        """
        if db_path is None:
            db_path = Path.home() / '.openclaw/workspace/integrations/intelligence/webhooks/oauth_tokens.db'
        
        self.db_path = db_path
        self.accounts = {}
        self._load_accounts()
    
    def _load_accounts(self):
        """Load all active accounts from database."""
        if not self.db_path.exists():
            logger.warning(f"[Account Manager] Database not found: {self.db_path}")
            return
        
        import sqlite3
        from pathlib import Path
        import json
        import tempfile
        
        # Load OAuth client credentials from Transmogrifier OAuth credentials file
        creds_path = Path.home() / '.openclaw/workspace/integrations/intelligence/config/credentials.json'
        client_id = None
        client_secret = None
        
        if creds_path.exists():
            with open(creds_path) as f:
                creds_data = json.load(f)
                client_id = creds_data.get('installed', {}).get('client_id')
                client_secret = creds_data.get('installed', {}).get('client_secret')
        
        if not client_id or not client_secret:
            logger.error("[Account Manager] OAuth credentials not found")
            return
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT account_id, email, account_type, access_token, refresh_token, id_token
            FROM oauth_tokens 
            WHERE enabled = 1
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        for account_id, email, account_type, access_token, refresh_token, id_token in rows:
            try:
                # Map account_type to provider
                provider = 'gmail' if account_type == 'gmail' else 'microsoft'
                
                # Create temporary token file from database tokens
                token_data = {
                    'token': access_token,
                    'refresh_token': refresh_token,
                    'id_token': id_token,
                    'token_uri': 'https://oauth2.googleapis.com/token',
                    'client_id': client_id,
                    'client_secret': client_secret
                }
                
                # Write to temp file for backend API
                temp_token = Path(tempfile.gettempdir()) / f'openclaw_token_{account_id}.json'
                with open(temp_token, 'w') as f:
                    json.dump(token_data, f)
                
                # Initialize universal API with temp token file
                api = UniversalEmailAPI(email=email, provider=provider, token_file=temp_token)
                
                self.accounts[account_id] = {
                    'email': email,
                    'provider': provider,
                    'api': api
                }
                
                logger.info(f"[Account Manager] Loaded account: {email} ({provider})")
                
            except Exception as e:
                logger.error(f"[Account Manager] Failed to load {email}: {e}")
        
        logger.info(f"[Account Manager] Loaded {len(self.accounts)} active accounts")
    
    def get_account(self, email: str) -> Optional[UniversalEmailAPI]:
        """Get API instance for specific email account."""
        for account in self.accounts.values():
            if account['email'] == email:
                return account['api']
        return None
    
    def get_all_accounts(self) -> List[Dict]:
        """Get list of all active accounts."""
        return [
            {
                'account_id': account_id,
                'email': account['email'],
                'provider': account['provider']
            }
            for account_id, account in self.accounts.items()
        ]
    
    def get_all_messages_across_accounts(self, max_per_account: int = 200) -> Dict[str, List[Dict]]:
        """
        Fetch messages from ALL active accounts.
        
        Returns:
            {
                'user@gmail.com': [messages...],
                'user@outlook.com': [messages...],
                ...
            }
        """
        all_messages = {}
        
        for account_id, account in self.accounts.items():
            email = account['email']
            api = account['api']
            
            try:
                messages = api.get_all_messages_30_days(max_results=max_per_account)
                all_messages[email] = messages
                logger.info(f"[Account Manager] {email}: {len(messages)} messages")
            except Exception as e:
                logger.error(f"[Account Manager] Failed to fetch messages from {email}: {e}")
                all_messages[email] = []
        
        return all_messages
    
    def get_all_unread_messages(self, hours_back: int = 1) -> List[Dict]:
        """
        Get unread messages from ALL accounts (backward compatibility method).
        
        Args:
            hours_back: Hours to look back
        
        Returns:
            Combined list of unread messages from all accounts
        """
        all_unread = []
        
        for account_id, account in self.accounts.items():
            email = account['email']
            api = account['api']
            
            try:
                unread = api.get_unread_messages(hours_back=hours_back, max_results=50)
                all_unread.extend(unread)
            except Exception as e:
                logger.error(f"[Account Manager] Failed to fetch unread from {email}: {e}")
        
        return all_unread
    
    def get_combined_important_contacts(self, top_n: int = 30) -> List[Dict]:
        """
        Get important contacts across ALL accounts.
        
        Combines contact importance scores across accounts.
        """
        all_contacts = {}
        
        for account_id, account in self.accounts.items():
            email = account['email']
            api = account['api']
            
            try:
                # Fetch messages for this account
                messages = api.get_all_messages_30_days(max_results=200)
                
                # Get important contacts
                contacts = api.get_important_contacts(messages, top_n=top_n)
                
                # Merge with all_contacts (sum scores if contact appears in multiple accounts)
                for contact in contacts:
                    contact_email = contact['email']
                    
                    if contact_email in all_contacts:
                        # Contact exists in multiple accounts - combine scores
                        all_contacts[contact_email]['importance_score'] += contact['importance_score']
                        all_contacts[contact_email]['total_emails'] += contact['total_emails']
                        all_contacts[contact_email]['accounts'].append(email)
                    else:
                        # New contact
                        contact['accounts'] = [email]
                        all_contacts[contact_email] = contact
                
            except Exception as e:
                logger.error(f"[Account Manager] Failed to analyze contacts from {email}: {e}")
        
        # Sort by combined importance score
        sorted_contacts = sorted(
            all_contacts.values(),
            key=lambda c: c['importance_score'],
            reverse=True
        )
        
        return sorted_contacts[:top_n]


# Backward compatibility alias for existing code
MultiProviderEmailConnector = UniversalAccountManager


if __name__ == '__main__':
    print("\n" + "="*60)
    print("Universal Email API - Multi-Account Test")
    print("="*60 + "\n")
    
    # Test multi-account manager
    manager = UniversalAccountManager()
    
    accounts = manager.get_all_accounts()
    print(f"📧 Active accounts: {len(accounts)}\n")
    
    for account in accounts:
        print(f"  • {account['email']} ({account['provider']})")
    print()
    
    # Test combined analysis
    print("[1/2] Fetching messages from all accounts...")
    all_messages = manager.get_all_messages_across_accounts(max_per_account=100)
    
    total_messages = sum(len(msgs) for msgs in all_messages.values())
    print(f"✅ Fetched {total_messages} messages across {len(all_messages)} accounts\n")
    
    for email, messages in all_messages.items():
        print(f"  • {email}: {len(messages)} messages")
    print()
    
    # Test combined contact importance
    print("[2/2] Analyzing important contacts across all accounts...")
    important = manager.get_combined_important_contacts(top_n=10)
    print(f"✅ Found {len(important)} important contacts\n")
    
    print("⭐ Most Important Contacts (All Accounts):")
    for i, contact in enumerate(important, 1):
        response_str = f"{contact['avg_response_hours']:.1f}h" if contact.get('avg_response_hours') else "N/A"
        accounts_str = ", ".join(contact['accounts'])
        
        print(f"  {i}. {contact['name']}")
        print(f"     Email: {contact['email']}")
        print(f"     Total emails: {contact['total_emails']}")
        print(f"     Your response time: {response_str}")
        print(f"     Importance score: {contact['importance_score']:.1f}")
        print(f"     Accounts: {accounts_str}")
        print()
    
    print("="*60)
    print("✅ Test complete!")
    print("="*60 + "\n")
