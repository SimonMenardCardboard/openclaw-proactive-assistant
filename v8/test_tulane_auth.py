#!/usr/bin/env python3
"""
Test Microsoft Graph authentication with Tulane account

This uses a SEPARATE client ID from production (stored in env var)
so it won't interfere with your main Transmogrifier V8 integration.

Usage:
1. Register app following register_tulane_test_app.sh
2. Set environment variable:
   export TULANE_CLIENT_ID="your-client-id-here"
3. Run this script:
   python3 test_tulane_auth.py
"""

import os
import sys
from pathlib import Path

# Add current dir to path
sys.path.insert(0, str(Path(__file__).parent))

from microsoft_graph_connector import MicrosoftGraphConnector


def main():
    # Use separate client ID for testing
    tulane_client_id = os.environ.get('TULANE_CLIENT_ID')
    
    if not tulane_client_id:
        print("ERROR: TULANE_CLIENT_ID environment variable not set")
        print("")
        print("Set it with:")
        print("  export TULANE_CLIENT_ID='your-azure-app-client-id'")
        print("")
        print("Get your client ID by following:")
        print("  ./register_tulane_test_app.sh")
        return 1
    
    print("=" * 70)
    print("TULANE TEST AUTHENTICATION")
    print("=" * 70)
    print(f"Client ID: {tulane_client_id[:8]}...")
    print(f"Account: tmenard1@tulane.edu")
    print("")
    
    # Use separate token file for testing
    token_file = Path(__file__).parent / 'tulane_test_token.json'
    
    # Create connector with test client ID
    connector = MicrosoftGraphConnector(token_file=token_file)
    connector.CLIENT_ID = tulane_client_id
    
    # Try to authenticate
    print("Starting device code authentication...")
    print("(You'll get a code to enter at microsoft.com/devicelogin)")
    print("")
    
    if connector.authenticate_device_code():
        print("")
        print("✓ Authentication successful!")
        print(f"Token saved to: {token_file}")
        print("")
        
        # Test calendar access
        print("Testing calendar access...")
        try:
            events = connector.get_calendar_events(days_ahead=7)
            print(f"✓ Found {len(events)} upcoming calendar events")
            
            if events:
                print("\nSample events:")
                for event in events[:3]:
                    print(f"  - {event.get('subject', 'No subject')}")
                    print(f"    {event.get('start', {}).get('dateTime', 'No time')}")
        except Exception as e:
            print(f"✗ Calendar test failed: {e}")
        
        print("")
        print("Testing email access...")
        try:
            emails = connector.get_recent_emails(count=5)
            print(f"✓ Found {len(emails)} recent emails")
            
            if emails:
                print("\nSample emails:")
                for email in emails[:3]:
                    print(f"  - {email.get('subject', 'No subject')}")
                    print(f"    From: {email.get('from', {}).get('emailAddress', {}).get('address', 'Unknown')}")
        except Exception as e:
            print(f"✗ Email test failed: {e}")
        
        print("")
        print("=" * 70)
        print("TEST COMPLETE")
        print("=" * 70)
        print("")
        print("Token file: " + str(token_file))
        print("")
        print("To use this in V8 testing:")
        print("  1. Keep TULANE_CLIENT_ID environment variable set")
        print("  2. V8 scripts can use tulane_test_token.json")
        print("  3. Production uses microsoft_graph_token.json (unchanged)")
        
        return 0
    else:
        print("\n✗ Authentication failed")
        print("Check that:")
        print("  1. Client ID is correct")
        print("  2. App registration allows 'Public client flows'")
        print("  3. Tulane account has calendar/email access")
        return 1


if __name__ == '__main__':
    sys.exit(main())
