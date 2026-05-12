#!/usr/bin/env python3
"""
Cross-Platform Desktop Observer - V8

Automatically detects OS and uses the appropriate observer:
- macOS: observer_v2.py (ScreenCapture + OCR)
- Windows: windows_observer.py (win32gui + psutil)
- Linux: linux_observer.py (Xlib/Wayland + psutil)

Provides unified API for all platforms.
"""

import sys
import logging
from pathlib import Path
from typing import Dict, Any, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('v8.cross_platform_observer')


class CrossPlatformObserver:
    """Unified observer for all desktop platforms"""
    
    def __init__(self, workspace_root: str = None):
        self.platform = sys.platform
        self.observer = None
        
        # Import and instantiate platform-specific observer
        if self.platform == 'darwin':
            from observer_v2 import DesktopObserverV2
            self.observer = DesktopObserverV2(workspace_root)
            logger.info("Using macOS observer")
        
        elif self.platform == 'win32':
            from windows_observer import WindowsObserver
            self.observer = WindowsObserver(workspace_root)
            logger.info("Using Windows observer")
        
        elif self.platform in ['linux', 'linux2']:
            from linux_observer import LinuxObserver
            self.observer = LinuxObserver(workspace_root)
            logger.info("Using Linux observer")
        
        else:
            raise RuntimeError(f"Unsupported platform: {self.platform}")
    
    def observe_session(self, duration_minutes: int = 5) -> Dict[str, Any]:
        """
        Observe desktop activity for a duration
        
        Args:
            duration_minutes: How long to observe (default: 5)
        
        Returns:
            Observation results with activities and patterns
        """
        if self.platform == 'darwin':
            # macOS observer uses observe_device_localhost
            return self.observer.observe_device_localhost(duration_minutes)
        else:
            # Windows/Linux use observe_session
            return self.observer.observe_session(duration_minutes)
    
    def get_active_window(self) -> Dict[str, Any]:
        """Get currently active window (platform-independent)"""
        return self.observer.get_active_window()
    
    def get_recent_activities(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get recent activities for pattern detection
        
        Args:
            days: Number of days to look back (default: 7)
        
        Returns:
            List of activity observations
        """
        return self.observer.get_recent_activities(days)


def main():
    """Test cross-platform observer"""
    print("\n" + "=" * 70)
    print("V8 CROSS-PLATFORM OBSERVER - TEST")
    print("=" * 70)
    
    print(f"\nDetected platform: {sys.platform}")
    
    try:
        observer = CrossPlatformObserver()
        
        # Test 1: Get active window
        print("\n1. Testing active window detection...")
        try:
            window = observer.get_active_window()
            if window:
                app_name = window.get('app_name') or window.get('application', 'Unknown')
                print(f"   ✓ Active window: {app_name}")
            else:
                print("   ℹ️  No active window detected")
        except Exception as e:
            print(f"   ⚠️  Could not get active window: {e}")
        
        # Test 2: Short observation
        print("\n2. Starting 1-minute observation...")
        print("   (Switch between apps to test tracking)")
        
        result = observer.observe_session(duration_minutes=1)
        
        activities_count = result.get('activities_count') or result.get('activities_extracted', 0)
        print(f"\n   ✓ Observed {activities_count} activities")
        
        # Test 3: Get recent activities
        print("\n3. Testing recent activities retrieval...")
        activities = observer.get_recent_activities(days=1)
        print(f"   ✓ Found {len(activities)} recent activities")
        
        if activities:
            print("\n   Recent activities:")
            for activity in activities[:5]:  # Show first 5
                app = activity.get('application', 'Unknown')
                timestamp = activity.get('timestamp', '')
                print(f"   - {app} at {timestamp}")
        
        print("\n" + "=" * 70)
        print("✓ Cross-platform observer test complete!")
        print(f"  Platform: {sys.platform}")
        print(f"  Observer: {type(observer.observer).__name__}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
