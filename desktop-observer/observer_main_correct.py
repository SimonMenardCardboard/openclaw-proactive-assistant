#!/usr/bin/env python3
"""
Transmogrifier Desktop Observer - Correct Device Linking Flow

Flow:
1. New device generates 6-digit code
2. User scans/enters code in their primary mobile app
3. This device polls for approval
4. Once approved, gets device_token + vm_url
5. Starts observing and uploading
"""

import sys
import os
import time
import requests
import json
import argparse
from datetime import datetime
from pathlib import Path

# Configuration
CONTROL_PLANE_URL = "https://control.getcardboardai.com"
POLLING_INTERVAL = 2  # seconds
CODE_EXPIRY = 300  # 5 minutes


def get_device_info():
    """Get current device information"""
    import platform
    import socket
    
    system = platform.system().lower()
    
    # Map system to platform
    platform_map = {
        'darwin': 'macos',
        'windows': 'windows',
        'linux': 'linux'
    }
    
    device_name = socket.gethostname()
    
    return {
        'name': device_name,
        'type': 'desktop',
        'platform': platform_map.get(system, system)
    }


def request_device_link():
    """
    Request a device link and get a 6-digit code.
    
    Returns:
        dict: {'code': '123456', 'expires_at': '...'}
    """
    device_info = get_device_info()
    
    try:
        response = requests.post(
            f"{CONTROL_PLANE_URL}/api/devices/request-link",
            json={'device_info': device_info},
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Failed to request link: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    
    except Exception as e:
        print(f"❌ Error requesting link: {e}")
        return None


def check_approval(code):
    """
    Check if the link request has been approved.
    
    Args:
        code: 6-digit code
    
    Returns:
        dict or None: Approval response if approved, None if pending
    """
    try:
        response = requests.get(
            f"{CONTROL_PLANE_URL}/api/devices/check-approval",
            params={'code': code},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('approved'):
                return data
        
        return None
    
    except Exception as e:
        # Silently continue polling
        return None


def save_credentials(device_token, device_id, vm_url):
    """Save device credentials to local config"""
    config_dir = Path.home() / '.config' / 'transmogrifier'
    config_dir.mkdir(parents=True, exist_ok=True)
    
    config_file = config_dir / 'credentials.json'
    
    credentials = {
        'device_token': device_token,
        'device_id': device_id,
        'vm_url': vm_url,
        'created_at': datetime.now().isoformat()
    }
    
    with open(config_file, 'w') as f:
        json.dump(credentials, f, indent=2)
    
    # Set restrictive permissions (owner only)
    os.chmod(config_file, 0o600)
    
    return config_file


def load_credentials():
    """Load saved credentials"""
    config_file = Path.home() / '.config' / 'transmogrifier' / 'credentials.json'
    
    if not config_file.exists():
        return None
    
    try:
        with open(config_file) as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  Could not load credentials: {e}")
        return None


def display_link_code(code):
    """Display the link code in a nice format"""
    print("\n")
    print("━" * 60)
    print("🔗  LINK THIS DEVICE")
    print("━" * 60)
    print("")
    print(f"   Your Link Code:  {code[0]} {code[1]} {code[2]}  {code[3]} {code[4]} {code[5]}")
    print("")
    print("━" * 60)
    print("")
    print("📱 On your primary device:")
    print("   1. Open Transmogrifier mobile app")
    print("   2. Tap 'Link New Device'")
    print("   3. Scan QR code or enter the code above")
    print("")
    print("⏳ Waiting for approval...")
    print("   (Code expires in 5 minutes)")
    print("")


def start_observing(device_token, vm_url, interval_minutes=5):
    """
    Start observing and uploading to VM.
    
    Args:
        device_token: Device authentication token
        vm_url: VM URL to upload to
        interval_minutes: Upload interval
    """
    # Import observer (only when actually starting)
    try:
        # Try to import from bundled location
        from cross_platform_observer import CrossPlatformObserver
    except ImportError:
        print("❌ Could not import CrossPlatformObserver")
        print("   Make sure the observer module is bundled with the binary")
        return 1
    
    observer = CrossPlatformObserver()
    
    print("\n✅ Device linked successfully!")
    print(f"📊 VM: {vm_url}")
    print(f"⏱️  Upload interval: {interval_minutes} minutes")
    print("\n🔄 Observer started. Press Ctrl+C to stop.\n")
    
    upload_count = 0
    
    while True:
        try:
            # Observe for the interval
            observation = observer.observe_session(interval_minutes)
            
            # Add metadata
            observation['uploaded_at'] = datetime.utcnow().isoformat()
            observation['observer_version'] = '1.0.0'
            observation['device_id'] = load_credentials()['device_id']
            
            # Upload to VM
            try:
                response = requests.post(
                    f'{vm_url}/api/desktop/activity',
                    json=observation,
                    headers={
                        'Authorization': f'Bearer {device_token}',
                        'Content-Type': 'application/json'
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    upload_count += 1
                    activity_count = len(observation.get('activities', []))
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    print(f"[{timestamp}] ✅ Upload #{upload_count}: {activity_count} activities")
                else:
                    print(f"[{timestamp}] ⚠️  Upload failed: {response.status_code}")
            
            except Exception as e:
                timestamp = datetime.now().strftime('%H:%M:%S')
                print(f"[{timestamp}] ❌ Upload error: {e}")
            
            # Wait before next observation
            time.sleep(interval_minutes * 60)
        
        except KeyboardInterrupt:
            print("\n\n👋 Stopping observer...")
            break
        
        except Exception as e:
            print(f"❌ Observation error: {e}")
            print("   Retrying in 1 minute...")
            time.sleep(60)
    
    return 0


def link_device_flow():
    """
    Complete device linking flow:
    1. Request link code
    2. Display code to user
    3. Poll for approval
    4. Save credentials
    5. Start observing
    """
    print("🚀 Transmogrifier Desktop Observer")
    print("   Version 1.0.0\n")
    
    # Step 1: Request link
    print("📡 Requesting device link...")
    link_request = request_device_link()
    
    if not link_request:
        print("❌ Failed to request device link")
        return 1
    
    code = link_request['code']
    
    # Step 2: Display code
    display_link_code(code)
    
    # Step 3: Poll for approval
    start_time = time.time()
    dots = 0
    
    while True:
        # Check if code expired (5 minutes)
        if time.time() - start_time > CODE_EXPIRY:
            print("\n❌ Code expired. Please restart and try again.")
            return 1
        
        # Check for approval
        approval = check_approval(code)
        
        if approval:
            # Step 4: Save credentials
            device_token = approval['device_token']
            device_id = approval['device_id']
            vm_url = approval['vm_url']
            
            config_file = save_credentials(device_token, device_id, vm_url)
            
            print("\n✅ Device approved!")
            print(f"   Credentials saved to: {config_file}")
            
            # Step 5: Start observing
            return start_observing(device_token, vm_url)
        
        # Visual feedback (animated dots)
        dots = (dots + 1) % 4
        print(f"\r   Waiting{'.' * dots}{' ' * (3 - dots)}", end='', flush=True)
        
        time.sleep(POLLING_INTERVAL)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Transmogrifier Desktop Observer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # First time setup (links device):
  ./TransmogrifierObserver
  
  # Run with custom upload interval:
  ./TransmogrifierObserver --interval 10
  
  # Re-link device (clears saved credentials):
  ./TransmogrifierObserver --relink
        """
    )
    
    parser.add_argument(
        '--interval',
        type=int,
        default=5,
        help='Upload interval in minutes (default: 5)'
    )
    
    parser.add_argument(
        '--relink',
        action='store_true',
        help='Re-link device (clears saved credentials)'
    )
    
    parser.add_argument(
        '--control-plane',
        default=CONTROL_PLANE_URL,
        help=f'Control plane URL (default: {CONTROL_PLANE_URL})'
    )
    
    args = parser.parse_args()
    
    # Override control plane URL if provided
    global CONTROL_PLANE_URL
    CONTROL_PLANE_URL = args.control_plane
    
    # Check if already linked (unless --relink)
    if not args.relink:
        credentials = load_credentials()
        
        if credentials:
            print("🔗 Device already linked")
            print(f"   VM: {credentials['vm_url']}")
            print(f"   Device ID: {credentials['device_id']}")
            print("\n   Use --relink to link a different account\n")
            
            # Start observing with saved credentials
            return start_observing(
                credentials['device_token'],
                credentials['vm_url'],
                args.interval
            )
    
    # Start device linking flow
    return link_device_flow()


if __name__ == '__main__':
    sys.exit(main())
