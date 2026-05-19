#!/usr/bin/env python3
"""
Universal Calendar API - Multi-Provider Support

Unified interface for:
- Google Calendar
- Microsoft Calendar (Outlook, Exchange, Office 365)

All providers expose same methods with same output format.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# Provider-specific imports
from google_calendar_api import GoogleCalendarAPI
from microsoft_graph_api import MicrosoftGraphAPI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UniversalCalendarAPI:
    """
    Universal calendar API that works with any provider.
    
    Auto-detects provider from email domain or explicit provider param.
    Exposes unified interface across all providers.
    """
    
    DOMAIN_MAPPING = {
        'gmail.com': 'google',
        'googlemail.com': 'google',
        'outlook.com': 'microsoft',
        'hotmail.com': 'microsoft',
        'live.com': 'microsoft',
        'office365.com': 'microsoft',
    }
    
    def __init__(self, 
                 email: str,
                 provider: Optional[str] = None,
                 token_file: Optional[Path] = None):
        """
        Initialize universal calendar API.
        
        Args:
            email: User's email address
            provider: 'google' or 'microsoft' (auto-detected if None)
            token_file: Path to OAuth token file (optional)
        """
        self.email = email
        self.provider = provider or self._detect_provider(email)
        self.backend = None
        
        # Initialize provider-specific backend
        if self.provider == 'google':
            self.backend = GoogleCalendarAPI(
                email=email,
                token_file=token_file or self._default_token_file('google')
            )
        
        elif self.provider == 'microsoft':
            self.backend = MicrosoftGraphAPI(
                email=email,
                token_file=token_file or self._default_token_file('microsoft')
            )
        
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
        
        logger.info(f"[Universal Calendar] Initialized {self.provider} backend for {email}")
    
    def _detect_provider(self, email: str) -> str:
        """Auto-detect provider from email domain."""
        domain = email.split('@')[-1].lower()
        
        if domain in self.DOMAIN_MAPPING:
            return self.DOMAIN_MAPPING[domain]
        
        # Default to Google for unknown domains (many use Google Workspace)
        logger.warning(f"Unknown domain {domain}, defaulting to Google Calendar")
        return 'google'
    
    def _default_token_file(self, provider: str) -> Path:
        """Get default token file path for provider."""
        base_path = Path.home() / '.openclaw/workspace/transmogrifier/openclaw-proactive-assistant/config'
        
        if provider == 'google':
            email_safe = self.email.replace('@', '_at_').replace('.', '_')
            account_token = base_path / f'token_{email_safe}.json'
            if account_token.exists():
                return account_token
            return base_path / 'token.json'
        
        elif provider == 'microsoft':
            email_safe = self.email.replace('@', '_at_').replace('.', '_')
            account_token = base_path / f'token_{email_safe}_microsoft.json'
            if account_token.exists():
                return account_token
            return base_path / 'token_microsoft.json'
        
        return base_path / 'token.json'
    
    # =========================================================================
    # UNIFIED INTERFACE - All providers implement these methods
    # =========================================================================
    
    def get_all_events_30_days(self, calendar_id: str = 'primary', max_results: int = 500) -> List[Dict]:
        """
        Get ALL events from last 30 days (past + future, 60-day window).
        
        Returns:
            List of events in standard format:
            {
                'id': str,
                'calendar_id': str,
                'summary': str,
                'description': str,
                'start': str (ISO format),
                'end': str (ISO format),
                'location': str,
                'attendees': List[str],
                'recurring_event_id': str,
                'organizer': str,
                'created': str,
                'updated': str,
                'status': str,
                '_provider': 'google'|'microsoft',
                '_email': str
            }
        """
        if not self.backend:
            logger.error("[Universal Calendar] No backend initialized")
            return []
        
        return self.backend.get_all_events_30_days(calendar_id=calendar_id, max_results=max_results)
    
    def detect_recurring_patterns(self, events: List[Dict]) -> Dict[str, Dict]:
        """
        Detect recurring meeting patterns.
        
        Returns:
            {
                'recurring_id': {
                    'summary': str,
                    'occurrence_count': int,
                    'first_occurrence': str,
                    'last_occurrence': str,
                    'attendees': List[str],
                    'organizer': str
                },
                ...
            }
        """
        if not self.backend:
            return {}
        
        return self.backend.detect_recurring_patterns(events)
    
    def analyze_meeting_frequency(self, events: List[Dict]) -> Dict[str, int]:
        """
        Count meetings per contact.
        
        Returns:
            {
                'contact@email.com': 15,  # meetings
                ...
            }
        """
        if not self.backend:
            return {}
        
        return self.backend.analyze_meeting_frequency(events)
    
    def find_focus_time_gaps(self, events: List[Dict], min_gap_hours: float = 2.0) -> List[Dict]:
        """
        Find large gaps in calendar (potential focus time).
        
        Returns:
            [
                {
                    'start': datetime,
                    'end': datetime,
                    'duration_hours': float,
                    'before_event': str,
                    'after_event': str
                },
                ...
            ]
        """
        if not self.backend:
            return []
        
        return self.backend.find_focus_time_gaps(events, min_gap_hours=min_gap_hours)
    
    def detect_conflicts(self, events: List[Dict]) -> List[Dict]:
        """
        Detect overlapping events (double-booked).
        
        Returns:
            [
                {
                    'event_1': str,
                    'event_2': str,
                    'time_1': str,
                    'time_2': str
                },
                ...
            ]
        """
        if not self.backend:
            return []
        
        return self.backend.detect_conflicts(events)


class UniversalCalendarManager:
    """
    Manage multiple calendar accounts across providers.
    
    Loads accounts from oauth_tokens.db and provides unified access.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize calendar manager.
        
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
            logger.warning(f"[Calendar Manager] Database not found: {self.db_path}")
            return
        
        import sqlite3
        import tempfile
        
        # Load OAuth credentials
        creds_path = Path.home() / '.openclaw/workspace/transmogrifier/openclaw-proactive-assistant/config/credentials.json'
        client_id = None
        client_secret = None
        
        if creds_path.exists():
            with open(creds_path) as f:
                creds_data = json.load(f)
                client_id = creds_data.get('installed', {}).get('client_id')
                client_secret = creds_data.get('installed', {}).get('client_secret')
        
        if not client_id or not client_secret:
            logger.error("[Calendar Manager] OAuth credentials not found")
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
                provider = 'google' if account_type == 'gmail' else 'microsoft'
                
                # Create temp token file
                token_data = {
                    'token': access_token,
                    'refresh_token': refresh_token,
                    'id_token': id_token,
                    'token_uri': 'https://oauth2.googleapis.com/token',
                    'client_id': client_id,
                    'client_secret': client_secret
                }
                
                temp_token = Path(tempfile.gettempdir()) / f'openclaw_cal_token_{account_id}.json'
                with open(temp_token, 'w') as f:
                    json.dump(token_data, f)
                
                # Initialize universal API
                api = UniversalCalendarAPI(email=email, provider=provider, token_file=temp_token)
                
                self.accounts[account_id] = {
                    'email': email,
                    'provider': provider,
                    'api': api
                }
                
                logger.info(f"[Calendar Manager] Loaded account: {email} ({provider})")
                
            except Exception as e:
                logger.error(f"[Calendar Manager] Failed to load {email}: {e}")
        
        logger.info(f"[Calendar Manager] Loaded {len(self.accounts)} active accounts")
    
    def get_account(self, email: str) -> Optional[UniversalCalendarAPI]:
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
    
    def get_all_events_across_accounts(self, max_per_account: int = 200) -> Dict[str, List[Dict]]:
        """
        Fetch events from ALL active accounts.
        
        Returns:
            {
                'user@gmail.com': [events...],
                'user@outlook.com': [events...],
                ...
            }
        """
        all_events = {}
        
        for account_id, account in self.accounts.items():
            email = account['email']
            api = account['api']
            
            try:
                events = api.get_all_events_30_days(max_results=max_per_account)
                all_events[email] = events
                logger.info(f"[Calendar Manager] {email}: {len(events)} events")
            except Exception as e:
                logger.error(f"[Calendar Manager] Failed to fetch events from {email}: {e}")
                all_events[email] = []
        
        return all_events
    
    def get_all_events(self, days_ahead: int = 2) -> List[Dict]:
        """
        Get events from ALL accounts (backward compatibility method).
        
        Args:
            days_ahead: Days to look ahead
        
        Returns:
            Combined list of events from all accounts
        """
        all_events_dict = self.get_all_events_across_accounts(max_per_account=100)
        
        # Flatten to single list
        all_events = []
        for events in all_events_dict.values():
            all_events.extend(events)
        
        # Filter to days_ahead window
        from datetime import datetime, timedelta
        now = datetime.now()
        cutoff = now + timedelta(days=days_ahead)
        
        filtered = []
        for event in all_events:
            start_str = event.get('start', '')
            try:
                if 'T' in start_str:
                    start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                else:
                    start_time = datetime.fromisoformat(start_str)
                
                if now <= start_time <= cutoff:
                    filtered.append(event)
            except:
                # If can't parse, include it
                filtered.append(event)
        
        return filtered
    
    def get_combined_meeting_frequency(self, top_n: int = 30) -> List[Dict]:
        """
        Get meeting frequency across ALL accounts.
        
        Returns:
            [
                {
                    'contact': str,
                    'meeting_count': int,
                    'accounts': List[str]
                },
                ...
            ]
        """
        all_contacts = {}
        
        for account_id, account in self.accounts.items():
            email = account['email']
            api = account['api']
            
            try:
                events = api.get_all_events_30_days(max_results=200)
                contact_freq = api.analyze_meeting_frequency(events)
                
                for contact, count in contact_freq.items():
                    if contact in all_contacts:
                        all_contacts[contact]['meeting_count'] += count
                        all_contacts[contact]['accounts'].append(email)
                    else:
                        all_contacts[contact] = {
                            'contact': contact,
                            'meeting_count': count,
                            'accounts': [email]
                        }
                
            except Exception as e:
                logger.error(f"[Calendar Manager] Failed to analyze {email}: {e}")
        
        sorted_contacts = sorted(
            all_contacts.values(),
            key=lambda c: c['meeting_count'],
            reverse=True
        )
        
        return sorted_contacts[:top_n]


# Backward compatibility alias for existing code
MultiProviderCalendarConnector = UniversalCalendarManager


if __name__ == '__main__':
    print("\n" + "="*60)
    print("Universal Calendar API - Multi-Account Test")
    print("="*60 + "\n")
    
    # Test multi-account manager
    manager = UniversalCalendarManager()
    
    accounts = manager.get_all_accounts()
    print(f"📅 Active calendar accounts: {len(accounts)}\n")
    
    for account in accounts:
        print(f"  • {account['email']} ({account['provider']})")
    print()
    
    # Test combined analysis
    print("[1/3] Fetching events from all calendars...")
    all_events = manager.get_all_events_across_accounts(max_per_account=100)
    
    total_events = sum(len(events) for events in all_events.values())
    print(f"✅ Fetched {total_events} events across {len(all_events)} calendars\n")
    
    for email, events in all_events.items():
        print(f"  • {email}: {len(events)} events")
    print()
    
    # Test meeting frequency
    print("[2/3] Analyzing meeting frequency across all accounts...")
    frequent = manager.get_combined_meeting_frequency(top_n=10)
    print(f"✅ Found {len(frequent)} frequent meeting contacts\n")
    
    print("Most frequent meeting contacts:")
    for i, contact_info in enumerate(frequent, 1):
        accounts_str = ", ".join(contact_info['accounts'][:2])  # Show first 2
        if len(contact_info['accounts']) > 2:
            accounts_str += f" +{len(contact_info['accounts'])-2} more"
        
        print(f"  {i}. {contact_info['contact']}")
        print(f"     Meetings: {contact_info['meeting_count']}")
        print(f"     Accounts: {accounts_str}")
        print()
    
    # Test focus time detection
    print("[3/3] Finding focus time gaps...")
    total_gaps = 0
    for email, events in all_events.items():
        if not events:
            continue
        
        api = manager.get_account(email)
        if api:
            gaps = api.find_focus_time_gaps(events, min_gap_hours=2.0)
            total_gaps += len(gaps)
            
            if gaps:
                print(f"\n{email}: {len(gaps)} gaps (≥2h)")
                for gap in gaps[:2]:
                    print(f"  • {gap['duration_hours']:.1f}h: {gap['start']} - {gap['end']}")
    
    print(f"\n✅ Found {total_gaps} total focus time gaps\n")
    
    print("="*60)
    print("✅ Test complete!")
    print("="*60 + "\n")
