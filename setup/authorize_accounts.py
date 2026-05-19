#!/usr/bin/env python3
"""
Authorize Multiple Google Accounts
Uses existing credentials.json to authorize 3 accounts
"""

import json
import sys
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Scopes needed
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/calendar.events.readonly'
]

# Credentials file - Transmogrifier uses its own credentials
CREDS_FILE = Path.home() / '.openclaw/workspace/transmogrifier/openclaw-proactive-assistant/config/credentials.json'
CONFIG_DIR = Path.home() / '.openclaw/workspace/transmogrifier/openclaw-proactive-assistant/config'

def authorize_account(account_label: str, hint_email: str) -> bool:
    """Authorize one Google account"""
    
    print(f"\n{'='*60}")
    print(f"Authorizing: {account_label}")
    print(f"Email: {hint_email}")
    print('='*60)
    
    if not CREDS_FILE.exists():
        print(f"❌ Credentials file not found: {CREDS_FILE}")
        return False
    
    # Run OAuth flow
    flow = InstalledAppFlow.from_client_secrets_file(
        str(CREDS_FILE),
        SCOPES,
        redirect_uri='http://localhost'
    )
    
    # Add login hint to pre-fill email
    flow.oauth2session.authorization_url(
        flow.client_config['auth_uri'],
        access_type='offline',
        login_hint=hint_email,
        prompt='consent'
    )
    
    print(f"\n🌐 Opening browser for {hint_email}...")
    print(f"   If not the right account, switch to: {hint_email}")
    
    try:
        creds = flow.run_local_server(port=0)
    except Exception as e:
        print(f"❌ Authorization failed: {e}")
        return False
    
    # Save token
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    token_file = CONFIG_DIR / f'default_google_{account_label}.json'
    
    token_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes,
        'account': hint_email
    }
    
    with open(token_file, 'w') as f:
        json.dump(token_data, f, indent=2)
    
    print(f"✅ Token saved: {token_file}")
    
    # Test it
    from googleapiclient.discovery import build
    
    try:
        service = build('gmail', 'v1', credentials=creds)
        profile = service.users().getProfile(userId='me').execute()
        email = profile.get('emailAddress', 'unknown')
        
        print(f"✅ Verified: {email}")
        
        if email.lower() != hint_email.lower():
            print(f"⚠️  WARNING: Expected {hint_email}, got {email}")
            print(f"   You may have authorized the wrong account!")
        
        return True
        
    except Exception as e:
        print(f"⚠️  Token saved but verification failed: {e}")
        return True  # Still count as success


def main():
    """Authorize all 3 accounts"""
    
    print("\n" + "="*60)
    print("Google OAuth - Multi-Account Authorization")
    print("="*60)
    
    accounts = [
        ('personal', 'lacrosseguy76665@gmail.com'),
        ('work', 'simon@legalmensch.com'),
        ('school', 'tmenard1@tulane.edu')
    ]
    
    print(f"\nWill authorize {len(accounts)} accounts:")
    for label, email in accounts:
        print(f"  • {label}: {email}")
    
    input("\nPress Enter to begin...")
    
    results = []
    
    for label, email in accounts:
        success = authorize_account(label, email)
        results.append((label, email, success))
    
    # Summary
    print("\n" + "="*60)
    print("AUTHORIZATION SUMMARY")
    print("="*60)
    
    for label, email, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {label}: {email}")
    
    success_count = sum(1 for _, _, s in results if s)
    print(f"\n{success_count}/{len(accounts)} accounts authorized")
    
    if success_count == len(accounts):
        print("\n✅ All accounts authorized successfully!")
        print(f"\nTokens saved to: {CONFIG_DIR}/")
        print("\nNext steps:")
        print("  1. Test with: python3 test_oauth.py")
        print("  2. Start COS services: python3 oauth_manager.py")
    else:
        print("\n⚠️  Some accounts failed. Re-run to retry.")


if __name__ == '__main__':
    main()
