#!/usr/bin/env python3
"""
Test OAuth Tokens - Verify all accounts work
"""

import json
import sys
from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

CONFIG_DIR = Path.home() / '.openclaw/workspace/transmogrifier/openclaw-proactive-assistant/config'

def test_account(label: str):
    """Test one account"""
    
    token_file = CONFIG_DIR / f'default_google_{label}.json'
    
    print(f"\n{'='*60}")
    print(f"Testing: {label}")
    print('='*60)
    
    if not token_file.exists():
        print(f"❌ Token not found: {token_file}")
        return False
    
    # Load token
    with open(token_file, 'r') as f:
        token_data = json.load(f)
    
    creds = Credentials(
        token=token_data['token'],
        refresh_token=token_data.get('refresh_token'),
        token_uri=token_data['token_uri'],
        client_id=token_data['client_id'],
        client_secret=token_data['client_secret'],
        scopes=token_data.get('scopes', [])
    )
    
    try:
        # Test Gmail
        gmail = build('gmail', 'v1', credentials=creds)
        profile = gmail.users().getProfile(userId='me').execute()
        email = profile.get('emailAddress')
        
        # Get message count
        results = gmail.users().messages().list(userId='me', maxResults=1).execute()
        msg_count = results.get('resultSizeEstimate', 0)
        
        print(f"✅ Gmail: {email}")
        print(f"   Total messages: {msg_count:,}")
        
        # Test Calendar
        calendar = build('calendar', 'v3', credentials=creds)
        cal_list = calendar.calendarList().list().execute()
        calendars = cal_list.get('items', [])
        
        print(f"✅ Calendar: {len(calendars)} calendars")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Test all accounts"""
    
    print("\n" + "="*60)
    print("OAuth Token Test")
    print("="*60)
    
    accounts = ['personal', 'work', 'school']
    results = []
    
    for label in accounts:
        success = test_account(label)
        results.append((label, success))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for label, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {label}")
    
    success_count = sum(1 for _, s in results if s)
    print(f"\n{success_count}/{len(accounts)} accounts working")
    
    if success_count == len(accounts):
        print("\n✅ All accounts verified!")
    else:
        print("\n⚠️  Some accounts failed. Run authorize_accounts.py to fix.")


if __name__ == '__main__':
    main()
