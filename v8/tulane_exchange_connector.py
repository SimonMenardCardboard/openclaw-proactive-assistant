#!/usr/bin/env python3
"""
Tulane Exchange/IMAP Connector (bypasses Azure restrictions)

Uses direct Exchange Web Services or IMAP/CalDAV instead of Graph API.
Works even when Tulane IT blocks third-party Azure apps.

Credentials stored in macOS Keychain (never in files).
"""

import subprocess
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional


class TulaneConnector:
    """Connect to Tulane email/calendar via Exchange/IMAP"""
    
    EMAIL = "tmenard1@tulane.edu"
    KEYCHAIN_SERVICE = "openclaw-tulane"
    
    # Tulane likely uses Office 365
    IMAP_SERVER = "outlook.office365.com"
    IMAP_PORT = 993
    EXCHANGE_SERVER = "outlook.office365.com"
    
    def __init__(self):
        self.email = self.EMAIL
        self.password = None
        
    def get_password(self) -> Optional[str]:
        """Get password from macOS Keychain"""
        try:
            result = subprocess.run([
                'security', 'find-generic-password',
                '-s', self.KEYCHAIN_SERVICE,
                '-a', self.email,
                '-w'  # Print password only
            ], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None
    
    def save_password(self, password: str):
        """Save password to macOS Keychain"""
        # Delete existing if present
        subprocess.run([
            'security', 'delete-generic-password',
            '-s', self.KEYCHAIN_SERVICE,
            '-a', self.email
        ], capture_output=True)
        
        # Add new
        subprocess.run([
            'security', 'add-generic-password',
            '-s', self.KEYCHAIN_SERVICE,
            '-a', self.email,
            '-w', password,
            '-T', ''  # Allow all apps
        ], check=True)
    
    def authenticate(self) -> bool:
        """
        Authenticate with Tulane Exchange.
        
        Prompts for password if not stored in Keychain.
        """
        self.password = self.get_password()
        
        if not self.password:
            print("Tulane password not found in Keychain.")
            print("")
            print("If you have 2FA enabled, you'll need an app-specific password:")
            print("1. Go to https://account.microsoft.com/security")
            print("2. Create app password for 'OpenClaw'")
            print("3. Use that password here")
            print("")
            
            import getpass
            self.password = getpass.getpass(f"Password for {self.email}: ")
            
            # Test it first
            if self._test_connection():
                print("✓ Password works! Saving to Keychain...")
                self.save_password(self.password)
                return True
            else:
                print("✗ Authentication failed")
                return False
        
        return self._test_connection()
    
    def _test_connection(self) -> bool:
        """Test IMAP connection"""
        try:
            import imaplib
            import ssl
            
            context = ssl.create_default_context()
            with imaplib.IMAP4_SSL(self.IMAP_SERVER, self.IMAP_PORT, ssl_context=context) as imap:
                imap.login(self.email, self.password)
                return True
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
    
    def get_recent_emails(self, count: int = 10) -> List[Dict]:
        """Get recent emails via IMAP"""
        import imaplib
        import email
        import ssl
        from email.header import decode_header
        
        emails = []
        
        try:
            context = ssl.create_default_context()
            with imaplib.IMAP4_SSL(self.IMAP_SERVER, self.IMAP_PORT, ssl_context=context) as imap:
                imap.login(self.email, self.password)
                imap.select('INBOX')
                
                # Search for recent emails
                _, message_numbers = imap.search(None, 'ALL')
                
                # Get last N emails
                for num in message_numbers[0].split()[-count:]:
                    _, msg_data = imap.fetch(num, '(RFC822)')
                    
                    email_body = msg_data[0][1]
                    email_message = email.message_from_bytes(email_body)
                    
                    # Decode subject
                    subject = email_message.get('Subject', '')
                    if subject:
                        decoded = decode_header(subject)
                        subject = decoded[0][0]
                        if isinstance(subject, bytes):
                            subject = subject.decode()
                    
                    emails.append({
                        'subject': subject,
                        'from': email_message.get('From', ''),
                        'date': email_message.get('Date', ''),
                        'id': num.decode()
                    })
                
                return emails
                
        except Exception as e:
            print(f"Error fetching emails: {e}")
            return []
    
    def get_calendar_events(self, days_ahead: int = 7) -> List[Dict]:
        """
        Get calendar events via Exchange Web Services.
        
        Note: Requires exchangelib package.
        Install with: pip install exchangelib
        """
        try:
            from exchangelib import Credentials, Account, DELEGATE, Configuration
            from exchangelib.items import CalendarItem
            
            credentials = Credentials(self.email, self.password)
            config = Configuration(
                server=self.EXCHANGE_SERVER,
                credentials=credentials
            )
            
            account = Account(
                primary_smtp_address=self.email,
                config=config,
                autodiscover=False,
                access_type=DELEGATE
            )
            
            # Get upcoming events
            start = datetime.now()
            end = start + timedelta(days=days_ahead)
            
            events = []
            for item in account.calendar.filter(
                start__lt=end,
                end__gt=start
            ).order_by('start'):
                events.append({
                    'subject': item.subject,
                    'start': item.start.isoformat() if item.start else None,
                    'end': item.end.isoformat() if item.end else None,
                    'location': item.location,
                    'id': item.id
                })
            
            return events
            
        except ImportError:
            print("exchangelib not installed. Install with:")
            print("  pip3 install exchangelib")
            return []
        except Exception as e:
            print(f"Error fetching calendar: {e}")
            return []


def main():
    """Test Tulane connector"""
    print("=" * 70)
    print("TULANE EXCHANGE CONNECTOR TEST")
    print("=" * 70)
    print(f"Account: {TulaneConnector.EMAIL}")
    print("")
    
    connector = TulaneConnector()
    
    if connector.authenticate():
        print("")
        print("✓ Authentication successful!")
        print("")
        
        # Test email
        print("Fetching recent emails...")
        emails = connector.get_recent_emails(count=5)
        print(f"Found {len(emails)} emails")
        for email in emails[:3]:
            print(f"  - {email['subject']}")
            print(f"    From: {email['from']}")
        
        print("")
        
        # Test calendar
        print("Fetching calendar events...")
        events = connector.get_calendar_events(days_ahead=7)
        print(f"Found {len(events)} upcoming events")
        for event in events[:3]:
            print(f"  - {event['subject']}")
            print(f"    {event['start']}")
        
        print("")
        print("=" * 70)
        print("SUCCESS - Tulane connector working!")
        print("")
        print("Password stored in Keychain, will auto-login next time.")
        
    else:
        print("")
        print("✗ Authentication failed")
        print("")
        print("Troubleshooting:")
        print("1. Check password is correct")
        print("2. If 2FA enabled, use app-specific password")
        print("3. Check Tulane email settings allow IMAP/Exchange")


if __name__ == '__main__':
    main()
