#!/usr/bin/env python3
"""
OAuth Setup Wizard for Email/Calendar Integration

Guides user through Google OAuth setup and stores credentials.
"""

import os
import json
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Scopes needed
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar.readonly'
]

CREDENTIALS_DIR = Path.home() / '.openclaw' / 'proactive' / 'credentials'
CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)


def setup_google_oauth():
    """Run OAuth flow for Google services"""
    print("🔐 Google OAuth Setup")
    print("=" * 50)
    print()
    print("This will authorize OpenClaw to read:")
    print("  ✓ Gmail (for pattern detection)")
    print("  ✓ Google Calendar (for workflow patterns)")
    print()
    print("Your data stays on YOUR VM. No external transmission.")
    print()
    
    # Check if credentials already exist
    token_file = CREDENTIALS_DIR / 'google_token.json'
    if token_file.exists():
        print("⚠️  Existing credentials found.")
        response = input("Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Skipping Google OAuth setup")
            return False
    
    # Check for client secrets
    client_secrets = CREDENTIALS_DIR / 'google_client_secrets.json'
    if not client_secrets.exists():
        print()
        print("❌ Missing OAuth client secrets")
        print()
        print("To set up OAuth:")
        print("1. Go to: https://console.cloud.google.com/apis/credentials")
        print("2. Create OAuth 2.0 Client ID (Desktop app)")
        print("3. Download JSON and save as:")
        print(f"   {client_secrets}")
        print()
        return False
    
    try:
        # Run OAuth flow
        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secrets),
            SCOPES
        )
        
        print("🌐 Opening browser for authorization...")
        print()
        creds = flow.run_local_server(port=0)
        
        # Save credentials
        with open(token_file, 'w') as f:
            f.write(creds.to_json())
        
        # Set permissions
        os.chmod(token_file, 0o600)
        
        print()
        print("✅ Google OAuth setup complete!")
        print(f"   Credentials saved to: {token_file}")
        return True
        
    except Exception as e:
        print(f"❌ OAuth setup failed: {e}")
        return False


def test_credentials():
    """Test that credentials work"""
    token_file = CREDENTIALS_DIR / 'google_token.json'
    if not token_file.exists():
        return False
    
    try:
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        
        # Refresh if needed
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_file, 'w') as f:
                f.write(creds.to_json())
        
        return creds.valid
        
    except Exception as e:
        print(f"❌ Credential test failed: {e}")
        return False


def main():
    """Main setup wizard"""
    print()
    print("╔════════════════════════════════════════════════╗")
    print("║  OpenClaw Proactive Assistant - OAuth Setup   ║")
    print("╚════════════════════════════════════════════════╝")
    print()
    
    # Setup Google OAuth
    if setup_google_oauth():
        print()
        print("🧪 Testing credentials...")
        if test_credentials():
            print("✅ Credentials valid!")
        else:
            print("⚠️  Credentials test failed")
    
    print()
    print("📝 Next steps:")
    print("  1. Restart V8 daemon: systemctl restart openclaw-v8")
    print("  2. Check logs: tail -f ~/.openclaw/proactive/logs/v8_*.log")
    print("  3. Email/calendar patterns will appear in next cycle")
    print()


if __name__ == '__main__':
    main()
