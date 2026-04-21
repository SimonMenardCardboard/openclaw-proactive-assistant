#!/usr/bin/env python3
"""
Microsoft Graph API Connector

OAuth authentication and API access for:
- Outlook/Exchange email
- Office 365 calendar
- OneDrive (future)

Works for:
- Personal Microsoft accounts (Outlook.com)
- Office 365 / Microsoft 365 accounts
- Exchange Online

Usage:
1. Register app at https://portal.azure.com
2. Set CLIENT_ID and optionally CLIENT_SECRET
3. Run interactive auth once to get refresh token
4. Use refresh token for ongoing access
"""

import json
import webbrowser
from pathlib import Path
from typing import Dict, List, Optional
import subprocess
import urllib.parse
from datetime import datetime, timedelta


class MicrosoftGraphConnector:
    """Connect to Microsoft Graph API for email and calendar"""
    
    # Production client ID (Transmogrifier V8 Production app)
    # Multitenant app - works with any Microsoft/Office 365/EDU account
    CLIENT_ID = "5bb2e8fd-4924-439c-a226-c3a638bf58b6"
    
    AUTHORITY = "https://login.microsoftonline.com/common"
    SCOPES = [
        "Mail.ReadWrite",           # Read + send/archive/filter email
        "Calendars.ReadWrite",       # Read + create/modify calendar events
        "MailboxSettings.ReadWrite", # Configure inbox rules, auto-replies
        "Tasks.ReadWrite",           # Task management (future)
        "offline_access"             # Refresh tokens (required)
    ]
    
    def __init__(self, token_file: Path = None):
        if token_file is None:
            token_file = Path.home() / '.openclaw/workspace/integrations/intelligence/microsoft_graph_token.json'
        
        self.token_file = token_file
        self.access_token = None
        self.refresh_token = None
        
        # Load existing token if available
        self._load_token()
    
    def _load_token(self):
        """Load stored token from file"""
        if self.token_file.exists():
            try:
                with open(self.token_file, 'r') as f:
                    data = json.load(f)
                    self.access_token = data.get('access_token')
                    self.refresh_token = data.get('refresh_token')
            except Exception as e:
                print(f"Error loading token: {e}")
    
    def _save_token(self, token_data: Dict):
        """Save token to file"""
        try:
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f, indent=2)
            
            self.access_token = token_data.get('access_token')
            self.refresh_token = token_data.get('refresh_token')
        except Exception as e:
            print(f"Error saving token: {e}")
    
    def authenticate_device_code(self):
        """
        Authenticate using device code flow (no client secret needed).
        
        This is the simplest auth method:
        1. Shows a code and URL
        2. User visits URL and enters code
        3. Returns access token + refresh token
        """
        # Start device code flow
        device_code_url = f"{self.AUTHORITY}/oauth2/v2.0/devicecode"
        
        data = {
            'client_id': self.CLIENT_ID,
            'scope': ' '.join(self.SCOPES)
        }
        
        # Use curl since we don't have requests library
        result = subprocess.run([
            'curl', '-s', '-X', 'POST',
            device_code_url,
            '-H', 'Content-Type: application/x-www-form-urlencoded',
            '-d', urllib.parse.urlencode(data)
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Device code request failed: {result.stderr}")
        
        device_code_response = json.loads(result.stdout)
        
        print("\n" + "="*60)
        print("MICROSOFT AUTHENTICATION")
        print("="*60)
        print(f"\n1. Visit: {device_code_response['verification_uri']}")
        print(f"2. Enter code: {device_code_response['user_code']}")
        print(f"\nWaiting for authentication...")
        print("="*60 + "\n")
        
        # Poll for token
        token_url = f"{self.AUTHORITY}/oauth2/v2.0/token"
        device_code = device_code_response['device_code']
        interval = device_code_response.get('interval', 5)
        expires_in = device_code_response.get('expires_in', 900)
        
        import time
        start_time = time.time()
        
        while (time.time() - start_time) < expires_in:
            time.sleep(interval)
            
            poll_data = {
                'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
                'client_id': self.CLIENT_ID,
                'device_code': device_code
            }
            
            result = subprocess.run([
                'curl', '-s', '-X', 'POST',
                token_url,
                '-H', 'Content-Type: application/x-www-form-urlencoded',
                '-d', urllib.parse.urlencode(poll_data)
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                continue
            
            token_response = json.loads(result.stdout)
            
            if 'access_token' in token_response:
                print("✅ Authentication successful!\n")
                self._save_token(token_response)
                return True
            
            error = token_response.get('error')
            if error and error != 'authorization_pending':
                raise Exception(f"Authentication failed: {error}")
        
        raise Exception("Authentication timeout")
    
    def refresh_access_token(self):
        """Refresh access token using refresh token"""
        if not self.refresh_token:
            raise Exception("No refresh token available")
        
        token_url = f"{self.AUTHORITY}/oauth2/v2.0/token"
        
        data = {
            'grant_type': 'refresh_token',
            'client_id': self.CLIENT_ID,
            'refresh_token': self.refresh_token,
            'scope': ' '.join(self.SCOPES)
        }
        
        result = subprocess.run([
            'curl', '-s', '-X', 'POST',
            token_url,
            '-H', 'Content-Type: application/x-www-form-urlencoded',
            '-d', urllib.parse.urlencode(data)
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Token refresh failed: {result.stderr}")
        
        token_response = json.loads(result.stdout)
        
        if 'access_token' in token_response:
            self._save_token(token_response)
            return True
        
        raise Exception(f"Token refresh failed: {token_response.get('error')}")
    
    def ensure_token(self):
        """Ensure we have a valid access token"""
        if not self.access_token:
            if self.refresh_token:
                self.refresh_access_token()
            else:
                raise Exception("No token available. Run authenticate_device_code() first.")
    
    def get_emails(self, max_results: int = 100, folder: str = "sentitems") -> List[Dict]:
        """
        Fetch emails from Microsoft Graph API
        
        Args:
            max_results: Max number of emails to return
            folder: Folder to query (inbox, sentitems, drafts, etc.)
        """
        self.ensure_token()
        
        url = f"https://graph.microsoft.com/v1.0/me/mailFolders/{folder}/messages?$top={max_results}"
        
        result = subprocess.run([
            'curl', '-s',
            url,
            '-H', f'Authorization: Bearer {self.access_token}',
            '-H', 'Content-Type: application/json'
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Email fetch failed: {result.stderr}")
        
        response = json.loads(result.stdout)
        
        if 'error' in response:
            # Token might be expired, try refresh
            self.refresh_access_token()
            return self.get_emails(max_results, folder)
        
        return response.get('value', [])
    
    def get_calendar_events(self, max_results: int = 100, days_back: int = 30) -> List[Dict]:
        """
        Fetch calendar events from Microsoft Graph API
        
        Args:
            max_results: Max number of events to return
            days_back: How many days back to query
        """
        self.ensure_token()
        
        # Get events from last N days
        start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%dT%H:%M:%S')
        end_date = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%dT%H:%M:%S')
        
        url = f"https://graph.microsoft.com/v1.0/me/calendarview?startDateTime={start_date}&endDateTime={end_date}&$top={max_results}"
        
        result = subprocess.run([
            'curl', '-s',
            url,
            '-H', f'Authorization: Bearer {self.access_token}',
            '-H', 'Content-Type: application/json',
            '-H', 'Prefer: outlook.timezone="America/Los_Angeles"'
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Calendar fetch failed: {result.stderr}")
        
        response = json.loads(result.stdout)
        
        if 'error' in response:
            # Token might be expired, try refresh
            self.refresh_access_token()
            return self.get_calendar_events(max_results, days_back)
        
        return response.get('value', [])


def main():
    """Test Microsoft Graph connector"""
    connector = MicrosoftGraphConnector()
    
    # Check if we have a token
    if not connector.access_token:
        print("No token found. Starting authentication...")
        print("\nNOTE: You need to register an app first:")
        print("1. Go to https://portal.azure.com")
        print("2. Register new app (Mobile and desktop applications)")
        print("3. Add redirect URI: http://localhost")
        print("4. Copy Application (client) ID")
        print("5. Update CLIENT_ID in this file\n")
        
        if connector.CLIENT_ID == "YOUR_CLIENT_ID_HERE":
            print("❌ Please update CLIENT_ID first!")
            return
        
        connector.authenticate_device_code()
    
    # Test email fetch
    print("📧 Fetching sent emails...")
    try:
        emails = connector.get_emails(max_results=10)
        print(f"   Found {len(emails)} emails")
        
        for email in emails[:3]:
            print(f"   - {email.get('subject', 'No subject')}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test calendar fetch
    print("\n📅 Fetching calendar events...")
    try:
        events = connector.get_calendar_events(max_results=10)
        print(f"   Found {len(events)} events")
        
        for event in events[:3]:
            print(f"   - {event.get('subject', 'No subject')}")
    except Exception as e:
        print(f"   Error: {e}")


if __name__ == '__main__':
    main()
