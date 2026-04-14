#!/usr/bin/env python3
"""
Universal Email/Calendar Connector

Tries Graph API first (best experience), falls back to IMAP/Exchange if blocked.

For Transmogrifier & Cardboard Legal production use.

Authentication flow:
1. Try Microsoft Graph API (OAuth device code)
   - Best: supports read/write, modern auth, multi-account
   - Works for: Personal Outlook, most Office 365, small business
   
2. Fallback to IMAP/Exchange (password-based)
   - When: Enterprise IT blocks third-party apps (error 53003)
   - Works for: University accounts, strict enterprise policies
   - Tradeoff: Requires password storage, read-only for some features

Usage:
    connector = EmailCalendarConnector(email="user@company.com")
    
    if connector.authenticate():
        emails = connector.get_recent_emails()
        events = connector.get_calendar_events()
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional, Literal
import json

# Import both connectors
sys.path.insert(0, str(Path(__file__).parent))
from microsoft_graph_connector import MicrosoftGraphConnector
from tulane_exchange_connector import TulaneConnector


class EmailCalendarConnector:
    """
    Smart connector that tries Graph API first, falls back to IMAP/Exchange.
    
    Production-ready for Transmogrifier & Cardboard Legal.
    """
    
    def __init__(self, email: str, token_file: Path = None):
        """
        Initialize connector for a specific email account.
        
        Args:
            email: Email address to connect (user@domain.com)
            token_file: Optional custom token storage path
        """
        self.email = email
        self.auth_method: Optional[Literal['graph', 'imap']] = None
        self.graph_connector = None
        self.imap_connector = None
        
        # Setup token file
        if token_file is None:
            safe_email = email.replace('@', '_at_').replace('.', '_')
            token_file = Path.home() / f'.openclaw/workspace/integrations/intelligence/tokens/{safe_email}.json'
        
        self.token_file = token_file
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
    
    def authenticate(self, prefer_graph: bool = True) -> bool:
        """
        Authenticate with best available method.
        
        Args:
            prefer_graph: Try Graph API first (recommended)
        
        Returns:
            True if authentication succeeded
        """
        if prefer_graph:
            print(f"Attempting Microsoft Graph API authentication for {self.email}...")
            if self._try_graph_auth():
                self.auth_method = 'graph'
                print("✓ Using Microsoft Graph API (full read/write access)")
                return True
            
            print("Graph API failed (tenant may block third-party apps)")
            print("Falling back to IMAP/Exchange...")
        
        # Fallback to IMAP
        if self._try_imap_auth():
            self.auth_method = 'imap'
            print("✓ Using IMAP/Exchange (read-only, password-based)")
            return True
        
        print("✗ All authentication methods failed")
        return False
    
    def _try_graph_auth(self) -> bool:
        """Try Microsoft Graph API authentication"""
        try:
            self.graph_connector = MicrosoftGraphConnector(token_file=self.token_file)
            
            # Check if already authenticated
            if self.graph_connector.access_token:
                # Validate token still works
                try:
                    self.graph_connector.get_recent_emails(count=1)
                    return True
                except:
                    pass  # Token expired, need to re-auth
            
            # Run device code flow
            return self.graph_connector.authenticate_device_code()
            
        except Exception as e:
            print(f"Graph API error: {e}")
            return False
    
    def _try_imap_auth(self) -> bool:
        """Try IMAP/Exchange authentication"""
        try:
            # Create connector with matching email
            connector_class = type('DynamicIMAPConnector', (TulaneConnector,), {
                'EMAIL': self.email,
                'KEYCHAIN_SERVICE': f'openclaw-{self.email}'
            })
            
            self.imap_connector = connector_class()
            return self.imap_connector.authenticate()
            
        except Exception as e:
            print(f"IMAP error: {e}")
            return False
    
    def get_recent_emails(self, count: int = 10) -> List[Dict]:
        """Get recent emails using active connector"""
        if self.auth_method == 'graph':
            return self.graph_connector.get_recent_emails(count=count)
        elif self.auth_method == 'imap':
            return self.imap_connector.get_recent_emails(count=count)
        else:
            raise RuntimeError("Not authenticated - call authenticate() first")
    
    def get_calendar_events(self, days_ahead: int = 7) -> List[Dict]:
        """Get calendar events using active connector"""
        if self.auth_method == 'graph':
            return self.graph_connector.get_calendar_events(days_ahead=days_ahead)
        elif self.auth_method == 'imap':
            return self.imap_connector.get_calendar_events(days_ahead=days_ahead)
        else:
            raise RuntimeError("Not authenticated - call authenticate() first")
    
    def get_auth_status(self) -> Dict:
        """Get current authentication status"""
        return {
            'email': self.email,
            'authenticated': self.auth_method is not None,
            'method': self.auth_method,
            'capabilities': {
                'read_email': True,
                'read_calendar': True,
                'write_email': self.auth_method == 'graph',
                'write_calendar': self.auth_method == 'graph',
                'auto_rules': self.auth_method == 'graph'
            }
        }


def main():
    """Test connector with a specific email"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 email_calendar_connector.py user@domain.com")
        print("")
        print("Examples:")
        print("  python3 email_calendar_connector.py tmenard1@tulane.edu")
        print("  python3 email_calendar_connector.py simon@legalmensch.com")
        return 1
    
    email = sys.argv[1]
    
    print("=" * 70)
    print("EMAIL/CALENDAR CONNECTOR TEST")
    print("=" * 70)
    print(f"Account: {email}")
    print("")
    
    connector = EmailCalendarConnector(email=email)
    
    if connector.authenticate():
        print("")
        status = connector.get_auth_status()
        print("Authentication Status:")
        print(f"  Method: {status['method'].upper()}")
        print(f"  Read Email: {status['capabilities']['read_email']}")
        print(f"  Write Email: {status['capabilities']['write_email']}")
        print(f"  Read Calendar: {status['capabilities']['read_calendar']}")
        print(f"  Write Calendar: {status['capabilities']['write_calendar']}")
        print("")
        
        # Test email
        print("Fetching recent emails...")
        emails = connector.get_recent_emails(count=5)
        print(f"✓ Found {len(emails)} emails")
        for email_item in emails[:3]:
            subject = email_item.get('subject', 'No subject')
            print(f"  - {subject[:60]}")
        
        print("")
        
        # Test calendar
        print("Fetching calendar events...")
        events = connector.get_calendar_events(days_ahead=7)
        print(f"✓ Found {len(events)} upcoming events")
        for event in events[:3]:
            subject = event.get('subject', 'No subject')
            print(f"  - {subject[:60]}")
        
        print("")
        print("=" * 70)
        print("SUCCESS!")
        print("")
        print("For V8 integration:")
        print("  from email_calendar_connector import EmailCalendarConnector")
        print(f"  connector = EmailCalendarConnector('{email}')")
        print("  connector.authenticate()")
        print("")
        
        return 0
    else:
        print("")
        print("=" * 70)
        print("AUTHENTICATION FAILED")
        print("=" * 70)
        print("")
        print("Troubleshooting:")
        print("1. Graph API: Check tenant allows third-party apps")
        print("2. IMAP: Verify password/2FA settings")
        print("3. Exchange: Contact IT for app-specific password")
        return 1


if __name__ == '__main__':
    sys.exit(main())
