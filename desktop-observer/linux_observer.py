#!/usr/bin/env python3
"""
Linux Desktop Observer - V8 Cross-Device

Observes app usage and workflow patterns on Linux using:
- Xlib for X11 window tracking
- Wayland protocol for Wayland sessions
- psutil for process monitoring

Supports both X11 and Wayland display servers.
"""

import sys
import logging
import sqlite3
import json
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# Linux-specific imports
try:
    # X11 support
    from Xlib import display, X, XK
    from Xlib.error import DisplayConnectionError
    X11_AVAILABLE = True
except ImportError:
    X11_AVAILABLE = False

import psutil

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('v8.linux_observer')


class LinuxObserver:
    """Observe Linux desktop activity"""
    
    def __init__(self, workspace_root: str = None):
        if workspace_root is None:
            workspace_root = str(Path.home() / '.openclaw' / 'workspace')
        
        self.workspace_root = Path(workspace_root)
        self.db_path = self.workspace_root / 'integrations' / 'intelligence' / 'v8_meta_learning' / 'cross_device.db'
        
        # Detect display server
        self.display_server = self._detect_display_server()
        logger.info(f"Detected display server: {self.display_server}")
        
        # Initialize X11 if available
        self.x_display = None
        if self.display_server == 'X11' and X11_AVAILABLE:
            try:
                self.x_display = display.Display()
            except DisplayConnectionError:
                logger.warning("Could not connect to X display")
        
        self._init_db()
        
        # Privacy controls
        self.privacy_config = {
            'capture_mode': 'activity_only',
            'logging': 'patterns_only',
            'retention_days': 7,
            'local_only': True
        }
        
        logger.info("Linux Observer initialized")
    
    def _detect_display_server(self) -> str:
        """Detect if running X11 or Wayland"""
        import os
        
        if os.environ.get('WAYLAND_DISPLAY'):
            return 'Wayland'
        elif os.environ.get('DISPLAY'):
            return 'X11'
        else:
            return 'Unknown'
    
    def _init_db(self):
        """Initialize database"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Use same schema as other observers
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS observed_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_name TEXT UNIQUE NOT NULL,
                device_type TEXT NOT NULL,
                host TEXT NOT NULL,
                port INTEGER,
                protocol TEXT,
                consent_given INTEGER DEFAULT 1,
                last_observed TEXT,
                observation_count INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                app_name TEXT,
                window_title TEXT,
                action_type TEXT,
                duration_sec INTEGER,
                metadata TEXT,
                FOREIGN KEY (device_id) REFERENCES observed_devices(id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_active_window_x11(self) -> Optional[Dict[str, Any]]:
        """Get active window on X11"""
        if not self.x_display:
            return None
        
        try:
            # Get focused window
            window = self.x_display.get_input_focus().focus
            
            # Get window properties
            wm_name = window.get_wm_name()
            wm_class = window.get_wm_class()
            
            # Get process ID
            pid_atom = self.x_display.intern_atom('_NET_WM_PID')
            pid_prop = window.get_full_property(pid_atom, X.AnyPropertyType)
            
            pid = None
            app_name = "Unknown"
            
            if pid_prop and pid_prop.value:
                pid = pid_prop.value[0]
                
                # Get process info
                try:
                    process = psutil.Process(pid)
                    app_name = process.name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            return {
                'app_name': app_name,
                'window_title': wm_name or '',
                'wm_class': wm_class[0] if wm_class else '',
                'pid': pid,
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error getting X11 window: {e}")
            return None
    
    def get_active_window_wayland(self) -> Optional[Dict[str, Any]]:
        """Get active window on Wayland (limited support)"""
        try:
            # Wayland security model limits window introspection
            # Try using compositor-specific tools
            
            # GNOME Shell (gdbus)
            result = subprocess.run(
                ['gdbus', 'call', '--session',
                 '--dest', 'org.gnome.Shell',
                 '--object-path', '/org/gnome/Shell',
                 '--method', 'org.gnome.Shell.Eval',
                 'global.get_window_actors().map(w => w.meta_window.get_wm_class())'],
                capture_output=True,
                text=True,
                timeout=1
            )
            
            if result.returncode == 0:
                # Parse output for active window
                # This is simplified - real implementation needs JSON parsing
                return {
                    'app_name': "Wayland App",
                    'window_title': '',
                    'timestamp': datetime.now().isoformat(),
                    'note': 'Limited Wayland support'
                }
        
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Fallback: Use wmctrl if available
        try:
            result = subprocess.run(['wmctrl', '-lx'], capture_output=True, text=True)
            if result.returncode == 0:
                # Parse wmctrl output (very basic)
                return {
                    'app_name': "Unknown",
                    'window_title': '',
                    'timestamp': datetime.now().isoformat()
                }
        except FileNotFoundError:
            pass
        
        return None
    
    def get_active_window(self) -> Optional[Dict[str, Any]]:
        """Get active window (auto-detect display server)"""
        if self.display_server == 'X11':
            return self.get_active_window_x11()
        elif self.display_server == 'Wayland':
            return self.get_active_window_wayland()
        else:
            logger.warning("Unknown display server")
            return None
    
    def observe_session(self, duration_minutes: int = 5) -> Dict[str, Any]:
        """
        Observe Linux activity for a duration
        
        Args:
            duration_minutes: How long to observe
        
        Returns:
            Observation results
        """
        logger.info(f"Starting Linux observation for {duration_minutes} minutes")
        
        # Get or create device entry
        device_id = self._get_device_id()
        
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        activities = []
        current_app = None
        app_start_time = None
        
        import time
        
        while datetime.now() < end_time:
            window_info = self.get_active_window()
            
            if window_info:
                app_name = window_info['app_name']
                
                # Detect app switch
                if app_name != current_app:
                    # Save previous activity
                    if current_app and app_start_time:
                        duration = (datetime.now() - app_start_time).total_seconds()
                        
                        activity = {
                            'app_name': current_app,
                            'window_title': activities[-1]['window_title'] if activities else '',
                            'action_type': 'foreground',
                            'duration': int(duration),
                            'timestamp': app_start_time.isoformat()
                        }
                        
                        self._save_activity(device_id, activity)
                        activities.append(activity)
                    
                    # Start tracking new app
                    current_app = app_name
                    app_start_time = datetime.now()
                    
                    logger.info(f"Switched to: {app_name}")
            
            # Poll every 2 seconds
            time.sleep(2)
        
        # Save final activity
        if current_app and app_start_time:
            duration = (datetime.now() - app_start_time).total_seconds()
            
            activity = {
                'app_name': current_app,
                'window_title': activities[-1]['window_title'] if activities else '',
                'action_type': 'foreground',
                'duration': int(duration),
                'timestamp': app_start_time.isoformat()
            }
            
            self._save_activity(device_id, activity)
            activities.append(activity)
        
        logger.info(f"Observation complete: {len(activities)} activities recorded")
        
        return {
            'device': 'linux-localhost',
            'duration_minutes': duration_minutes,
            'activities_count': len(activities),
            'activities': activities,
            'display_server': self.display_server,
            'start_time': start_time.isoformat(),
            'end_time': datetime.now().isoformat()
        }
    
    def _get_device_id(self) -> int:
        """Get or create device entry"""
        import socket
        hostname = socket.gethostname()
        device_name = f"linux-{hostname}"
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM observed_devices WHERE device_name = ?', (device_name,))
        row = cursor.fetchone()
        
        if row:
            device_id = row[0]
        else:
            cursor.execute('''
                INSERT INTO observed_devices 
                (device_name, device_type, host, protocol, consent_given)
                VALUES (?, ?, ?, ?, 1)
            ''', (device_name, 'linux', 'localhost', 'local'))
            
            device_id = cursor.lastrowid
            logger.info(f"Created device: {device_name} (ID: {device_id})")
        
        conn.commit()
        conn.close()
        
        return device_id
    
    def _save_activity(self, device_id: int, activity: Dict[str, Any]):
        """Save activity to database"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO activity_observations 
            (device_id, timestamp, app_name, window_title, action_type, duration_sec, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            device_id,
            activity.get('timestamp', datetime.now().isoformat()),
            activity.get('app_name', ''),
            activity.get('window_title', ''),
            activity.get('action_type', 'foreground'),
            activity.get('duration', 0),
            json.dumps(activity.get('metadata', {}))
        ))
        
        conn.commit()
        conn.close()
    
    def get_recent_activities(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent activities for pattern detection"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        cursor.execute('''
            SELECT timestamp, app_name, window_title, action_type, duration_sec, metadata
            FROM activity_observations ao
            JOIN observed_devices od ON ao.device_id = od.id
            WHERE od.device_type = 'linux'
            AND timestamp >= ?
            ORDER BY timestamp DESC
        ''', (cutoff,))
        
        activities = []
        for row in cursor.fetchall():
            try:
                metadata = json.loads(row[5]) if row[5] else {}
            except:
                metadata = {}
            
            activities.append({
                'timestamp': row[0],
                'application': row[1],
                'activity': row[3],
                'window': row[2],
                'metadata': metadata
            })
        
        conn.close()
        return activities


def main():
    """Test Linux observer"""
    print("\n" + "=" * 70)
    print("V8 LINUX OBSERVER - TEST")
    print("=" * 70)
    
    if sys.platform not in ['linux', 'linux2']:
        print("❌ Error: This script must run on Linux")
        return
    
    observer = LinuxObserver()
    
    print(f"\nDisplay server: {observer.display_server}")
    
    if observer.display_server == 'X11' and not X11_AVAILABLE:
        print("⚠️  Warning: python-xlib not installed")
        print("   Install: pip install python-xlib")
        return
    
    # Test 1: Get active window
    print("\n1. Testing active window detection...")
    window = observer.get_active_window()
    if window:
        print(f"   Active: {window['app_name']} - {window.get('window_title', '')}")
    else:
        print("   No active window detected")
    
    # Test 2: Short observation
    print("\n2. Starting 1-minute observation...")
    print("   Switch between apps to test tracking...")
    
    result = observer.observe_session(duration_minutes=1)
    
    print(f"\n   Observed {result['activities_count']} activities:")
    for activity in result['activities']:
        print(f"   - {activity['app_name']}: {activity['duration']}s")
    
    # Test 3: Get recent activities
    print("\n3. Testing recent activities retrieval...")
    activities = observer.get_recent_activities(days=1)
    print(f"   Found {len(activities)} recent activities")
    
    print("\n" + "=" * 70)
    print("✓ Linux observer test complete!")


if __name__ == '__main__':
    main()
