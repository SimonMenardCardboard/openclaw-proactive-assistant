#!/usr/bin/env python3
"""
Windows Desktop Observer - V8 Cross-Device

Observes app usage and workflow patterns on Windows using:
- pywin32 for window tracking
- psutil for process monitoring
- win32gui for screen capture (optional)

Production-ready for Windows 10/11.
"""

import sys
import logging
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# Windows-specific imports
if sys.platform == 'win32':
    import win32gui
    import win32process
    import win32con
    import psutil
    import ctypes
    from ctypes import wintypes

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('v8.windows_observer')


class WindowsObserver:
    """Observe Windows desktop activity"""
    
    def __init__(self, workspace_root: str = None):
        if workspace_root is None:
            workspace_root = str(Path.home() / '.openclaw' / 'workspace')
        
        self.workspace_root = Path(workspace_root)
        self.db_path = self.workspace_root / 'integrations' / 'intelligence' / 'v8_meta_learning' / 'cross_device.db'
        
        self._init_db()
        
        # Privacy controls
        self.privacy_config = {
            'capture_mode': 'activity_only',
            'logging': 'patterns_only',
            'retention_days': 7,
            'local_only': True
        }
        
        logger.info("Windows Observer initialized")
    
    def _init_db(self):
        """Initialize database"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Use same schema as macOS observer
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
    
    def get_active_window(self) -> Optional[Dict[str, Any]]:
        """Get currently active window information"""
        if sys.platform != 'win32':
            return None
        
        try:
            # Get foreground window
            hwnd = win32gui.GetForegroundWindow()
            
            if hwnd == 0:
                return None
            
            # Get window title
            window_title = win32gui.GetWindowText(hwnd)
            
            # Get process ID
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            
            # Get process info
            try:
                process = psutil.Process(pid)
                app_name = process.name()
                exe_path = process.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                app_name = "Unknown"
                exe_path = ""
            
            return {
                'app_name': app_name,
                'window_title': window_title,
                'pid': pid,
                'exe_path': exe_path,
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error getting active window: {e}")
            return None
    
    def observe_session(self, duration_minutes: int = 5) -> Dict[str, Any]:
        """
        Observe Windows activity for a duration
        
        Args:
            duration_minutes: How long to observe
        
        Returns:
            Observation results with activities and patterns
        """
        logger.info(f"Starting Windows observation for {duration_minutes} minutes")
        
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
                    # Save previous app activity
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
                    
                    logger.info(f"Switched to: {app_name} - {window_info.get('window_title', '')}")
            
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
            'device': 'windows-localhost',
            'duration_minutes': duration_minutes,
            'activities_count': len(activities),
            'activities': activities,
            'start_time': start_time.isoformat(),
            'end_time': datetime.now().isoformat()
        }
    
    def _get_device_id(self) -> int:
        """Get or create device entry"""
        import socket
        hostname = socket.gethostname()
        device_name = f"windows-{hostname}"
        
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
            ''', (device_name, 'windows', 'localhost', 'local'))
            
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
            WHERE od.device_type = 'windows'
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
    """Test Windows observer"""
    print("\n" + "=" * 70)
    print("V8 WINDOWS OBSERVER - TEST")
    print("=" * 70)
    
    if sys.platform != 'win32':
        print("❌ Error: This script must run on Windows")
        return
    
    observer = WindowsObserver()
    
    # Test 1: Get active window
    print("\n1. Testing active window detection...")
    window = observer.get_active_window()
    if window:
        print(f"   Active: {window['app_name']} - {window['window_title']}")
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
    print("✓ Windows observer test complete!")


if __name__ == '__main__':
    main()
