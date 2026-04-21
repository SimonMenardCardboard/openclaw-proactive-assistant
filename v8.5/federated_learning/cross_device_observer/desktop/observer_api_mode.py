#!/usr/bin/env python3
"""
Desktop Observer with API Mode

Extends observer_v2.py to support sending activity to remote VM via API.

Usage:
    # Local mode (existing)
    observer = DesktopObserverV2(mode='local')
    
    # API mode (new)
    observer = DesktopObserverV2(
        mode='api',
        api_endpoint='https://getcardboardai.com/api/activity',
        api_token='tk_abc123...'
    )
"""

import sys
import os
from pathlib import Path
import requests
import time
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from observer_v2 import DesktopObserverV2 as BaseObserver


class DesktopObserverAPIMode(BaseObserver):
    """Desktop observer with API mode for sending to VM"""
    
    def __init__(self,
                 workspace_root: str = None,
                 mode: str = 'local',  # 'local' or 'api'
                 api_endpoint: str = None,
                 api_token: str = None):
        """
        Initialize observer.
        
        Args:
            workspace_root: Workspace directory
            mode: 'local' (store in local DB) or 'api' (send to VM)
            api_endpoint: API endpoint URL (for API mode)
            api_token: Bearer token (for API mode)
        """
        # Initialize base observer
        super().__init__(workspace_root)
        
        self.mode = mode
        self.api_endpoint = api_endpoint
        self.api_token = api_token
        
        # For API mode, also keep a local cache for offline
        if mode == 'api':
            if not api_endpoint or not api_token:
                raise ValueError("API mode requires api_endpoint and api_token")
            
            print(f"🌐 API mode enabled")
            print(f"   Endpoint: {api_endpoint}")
            print(f"   Token: {api_token[:10]}...")
            print(f"   Fallback: Local cache")
    
    def _record_activity_to_api(self, activity: dict) -> bool:
        """Send activity to VM API"""
        try:
            response = requests.post(
                self.api_endpoint,
                headers={'Authorization': f'Bearer {self.api_token}'},
                json=activity,
                timeout=5
            )
            
            if response.status_code == 200:
                return True
            else:
                print(f"❌ API error: {response.status_code}")
                return False
        
        except requests.exceptions.Timeout:
            print(f"⏱️  API timeout")
            return False
        
        except requests.exceptions.ConnectionError:
            print(f"📡 Connection error (offline?)")
            return False
        
        except Exception as e:
            print(f"❌ API error: {e}")
            return False
    
    def record_activity(self, device_id: str, activity: dict):
        """
        Record activity (override base method).
        
        In API mode, send to VM first, fall back to local cache if offline.
        """
        if self.mode == 'local':
            # Use base class method
            super().record_activity(device_id, activity)
        
        elif self.mode == 'api':
            # Try to send to API first
            success = self._record_activity_to_api(activity)
            
            if not success:
                # Fall back to local cache
                print(f"💾 Caching locally (will retry later)")
                super().record_activity(device_id, activity)
    
    def sync_cached_activities(self):
        """
        Sync locally cached activities to API (for offline → online recovery).
        
        This would read from local DB and send any unsent activities to API.
        """
        # TODO: Implement sync logic
        # For now, just a placeholder
        pass


def main():
    """Example usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Desktop Observer with API mode')
    parser.add_argument('--mode', choices=['local', 'api'], default='local',
                       help='Storage mode: local DB or remote API')
    parser.add_argument('--endpoint', help='API endpoint (for API mode)')
    parser.add_argument('--token', help='API token (for API mode)')
    parser.add_argument('--device-id', default='desktop-test',
                       help='Device identifier')
    
    args = parser.parse_args()
    
    # Get token from env if not provided
    api_token = args.token or os.getenv('TRANSMOGRIFIER_TOKEN')
    
    # Create observer
    observer = DesktopObserverAPIMode(
        mode=args.mode,
        api_endpoint=args.endpoint,
        api_token=api_token
    )
    
    print(f"🔍 Starting observer in {args.mode} mode")
    print(f"   Device: {args.device_id}")
    print()
    
    # Test: Record a sample activity
    test_activity = {
        'device_id': args.device_id,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'app': 'Terminal',
        'window_title': '[REDACTED]',
        'activity_type': 'app_switch',
        'duration_seconds': 60
    }
    
    print("📝 Recording test activity...")
    observer.record_activity(args.device_id, test_activity)
    print("✅ Done!")
    
    if args.mode == 'api':
        print()
        print("💡 Tip: Run with --mode local to test offline caching")


if __name__ == "__main__":
    main()
