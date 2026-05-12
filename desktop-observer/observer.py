#!/usr/bin/env python3
"""
V8 Cross-Device Observer - Desktop Observer

Observes workflows on remote desktop devices (Mac/Windows/Linux).

Platform support:
- Mac → Mac: Screen Sharing (native, port 5900)
- Mac → Windows: RDP (port 3389)
- Mac → Linux: VNC (port 5900)
- Cross-platform via VNC/RDP clients

Architecture:
1. Screen capture layer (platform-specific)
2. Activity extraction (OCR + vision)
3. Pattern detection
4. Privacy filtering
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
import subprocess
import time

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('v8.cross_device.desktop')


class DesktopObserver:
    """Observe workflows on remote desktop devices."""
    
    def __init__(self, workspace_root: str = None):
        if workspace_root is None:
            workspace_root = str(Path('/Users/tsmolty/workspace'))
        
        self.workspace_root = Path(workspace_root)
        self.observer_db = self.workspace_root / 'integrations' / 'intelligence' / 'v8_meta_learning' / 'cross_device.db'
        
        self._init_db()
        
        # Privacy controls
        self.privacy_config = {
            'capture_mode': 'activity_only',  # Don't save raw screenshots
            'ocr_filter': ['password', 'credit_card', 'ssn', 'api_key', 'token', 'secret'],
            'logging': 'patterns_only',
            'retention_days': 7,
            'encryption': 'at_rest',
            'local_only': True,
            'consent_required': True
        }
    
    def _init_db(self):
        """Initialize cross-device observation database."""
        self.observer_db.parent.mkdir(parents=True, exist_ok=True)
        
        import sqlite3
        conn = sqlite3.connect(str(self.observer_db))
        cursor = conn.cursor()
        
        # Observed devices table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS observed_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_name TEXT UNIQUE NOT NULL,
                device_type TEXT NOT NULL,
                host TEXT NOT NULL,
                port INTEGER,
                protocol TEXT,
                consent_given INTEGER DEFAULT 0,
                last_observed TEXT,
                observation_count INTEGER DEFAULT 0
            )
        ''')
        
        # Activity observations table
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
        
        # Detected patterns table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS detected_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                pattern_type TEXT NOT NULL,
                description TEXT,
                frequency INTEGER DEFAULT 1,
                time_saved_min INTEGER,
                automation_candidate INTEGER DEFAULT 0,
                first_seen TEXT,
                last_seen TEXT,
                FOREIGN KEY (device_id) REFERENCES observed_devices(id)
            )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("Cross-device observer database initialized")
    
    def register_device(self, device_name: str, device_type: str, host: str, 
                       port: int, protocol: str) -> int:
        """
        Register a device for observation.
        
        Args:
            device_name: Friendly device name
            device_type: 'mac', 'windows', or 'linux'
            host: Hostname or IP
            port: Connection port (5900 for VNC, 3389 for RDP)
            protocol: 'vnc', 'rdp', or 'screen_sharing'
            
        Returns:
            Device ID
        """
        import sqlite3
        
        try:
            conn = sqlite3.connect(str(self.observer_db))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO observed_devices 
                (device_name, device_type, host, port, protocol)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(device_name) DO UPDATE SET
                    host = excluded.host,
                    port = excluded.port,
                    protocol = excluded.protocol
            ''', (device_name, device_type, host, port, protocol))
            
            device_id = cursor.lastrowid
            
            conn.commit()
            conn.close()
            
            logger.info(f"Registered device: {device_name} ({device_type}) at {host}:{port}")
            return device_id
            
        except Exception as e:
            logger.error(f"Error registering device: {e}")
            return -1
    
    def observe_device(self, device_id: int, duration_minutes: int = 5) -> Dict[str, Any]:
        """
        Observe a device for a period of time.
        
        Args:
            device_id: Device to observe
            duration_minutes: How long to observe
            
        Returns:
            Observation summary
        """
        import sqlite3
        
        try:
            # Get device info
            conn = sqlite3.connect(str(self.observer_db))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT device_name, device_type, host, port, protocol, consent_given
                FROM observed_devices
                WHERE id = ?
            ''', (device_id,))
            
            device_row = cursor.fetchone()
            conn.close()
            
            if not device_row:
                return {'error': 'Device not found'}
            
            device_name, device_type, host, port, protocol, consent = device_row
            
            # Check consent
            if not consent:
                logger.warning(f"No consent for device {device_name}")
                return {'error': 'Consent not given', 'device': device_name}
            
            logger.info(f"Starting observation of {device_name} for {duration_minutes} min")
            
            # Collect observations
            start_time = datetime.now()
            end_time = start_time + timedelta(minutes=duration_minutes)
            
            activities = []
            
            # Observation loop (simplified - real implementation would capture screens)
            while datetime.now() < end_time:
                # Simulate activity observation
                # Real implementation would:
                # 1. Capture screen via VNC/RDP
                # 2. Extract text via OCR
                # 3. Detect window/app changes
                # 4. Log activity
                
                activity = self._simulate_activity_capture(device_type)
                
                if activity:
                    activities.append(activity)
                    self._save_activity(device_id, activity)
                
                time.sleep(10)  # Sample every 10 seconds
            
            # Analyze collected activities
            patterns = self._detect_patterns(device_id, activities)
            
            # Update device stats
            self._update_device_stats(device_id, len(activities))
            
            result = {
                'device': device_name,
                'duration_minutes': duration_minutes,
                'activities_observed': len(activities),
                'patterns_detected': len(patterns),
                'patterns': patterns
            }
            
            logger.info(f"Observation complete: {len(activities)} activities, {len(patterns)} patterns")
            
            return result
            
        except Exception as e:
            logger.error(f"Error observing device: {e}")
            return {'error': str(e)}
    
    def _simulate_activity_capture(self, device_type: str) -> Optional[Dict[str, Any]]:
        """
        Simulate activity capture (placeholder).
        
        Real implementation would:
        - Connect to device via VNC/RDP/Screen Sharing
        - Capture screenshot
        - Run OCR to extract text
        - Detect app/window changes
        - Identify user actions
        """
        # Placeholder: return mock activity
        import random
        
        apps = ['Mail', 'Slack', 'Chrome', 'Terminal', 'VS Code']
        actions = ['typing', 'clicking', 'scrolling', 'switching']
        
        return {
            'timestamp': datetime.now().isoformat(),
            'app_name': random.choice(apps),
            'window_title': f"Work Project {random.randint(1, 5)}",
            'action_type': random.choice(actions),
            'duration_sec': random.randint(5, 30)
        }
    
    def _save_activity(self, device_id: int, activity: Dict[str, Any]):
        """Save observed activity to database."""
        import sqlite3
        
        try:
            conn = sqlite3.connect(str(self.observer_db))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO activity_observations
                (device_id, timestamp, app_name, window_title, action_type, duration_sec, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                device_id,
                activity['timestamp'],
                activity.get('app_name'),
                activity.get('window_title'),
                activity.get('action_type'),
                activity.get('duration_sec'),
                json.dumps(activity.get('metadata', {}))
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving activity: {e}")
    
    def _detect_patterns(self, device_id: int, activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect workflow patterns from activities."""
        patterns = []
        
        # Pattern 1: Repeated app sequences
        app_sequence = [a['app_name'] for a in activities if a.get('app_name')]
        
        # Find 3+ repeated sequences
        for i in range(len(app_sequence) - 2):
            seq = tuple(app_sequence[i:i+3])
            count = sum(1 for j in range(len(app_sequence) - 2) 
                       if tuple(app_sequence[j:j+3]) == seq)
            
            if count >= 2:  # Repeated at least twice
                patterns.append({
                    'type': 'repeated_app_sequence',
                    'description': f"User switches between {' → '.join(seq)} repeatedly",
                    'frequency': count,
                    'automation_candidate': 1
                })
        
        # Pattern 2: Long duration in single app (potential bottleneck)
        app_durations = {}
        for activity in activities:
            app = activity.get('app_name')
            duration = activity.get('duration_sec', 0)
            if app:
                app_durations[app] = app_durations.get(app, 0) + duration
        
        for app, total_duration in app_durations.items():
            if total_duration > 180:  # >3 minutes
                patterns.append({
                    'type': 'time_intensive_task',
                    'description': f"Spent {total_duration}s in {app} (potential automation)",
                    'frequency': 1,
                    'time_saved_min': int(total_duration / 60 * 0.7),  # Est 70% time savings
                    'automation_candidate': 1
                })
        
        return patterns
    
    def _update_device_stats(self, device_id: int, activity_count: int):
        """Update device observation statistics."""
        import sqlite3
        
        try:
            conn = sqlite3.connect(str(self.observer_db))
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE observed_devices
                SET last_observed = ?,
                    observation_count = observation_count + ?
                WHERE id = ?
            ''', (datetime.now().isoformat(), activity_count, device_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error updating device stats: {e}")
    
    def grant_consent(self, device_id: int):
        """Grant observation consent for a device."""
        import sqlite3
        
        try:
            conn = sqlite3.connect(str(self.observer_db))
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE observed_devices
                SET consent_given = 1
                WHERE id = ?
            ''', (device_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Consent granted for device {device_id}")
            
        except Exception as e:
            logger.error(f"Error granting consent: {e}")


if __name__ == '__main__':
    # Test desktop observer
    observer = DesktopObserver()
    
    print("\n=== Desktop Observer Test ===")
    
    # Register a test device
    device_id = observer.register_device(
        device_name='Work-MacBook-Pro',
        device_type='mac',
        host='192.168.1.100',
        port=5900,
        protocol='screen_sharing'
    )
    
    print(f"Registered device: {device_id}")
    
    # Grant consent
    observer.grant_consent(device_id)
    print("Consent granted")
    
    # Observe device (short duration for testing)
    print("\nStarting observation...")
    result = observer.observe_device(device_id, duration_minutes=1)
    
    if 'error' not in result:
        print(f"\nObservation complete:")
        print(f"  Activities observed: {result['activities_observed']}")
        print(f"  Patterns detected: {result['patterns_detected']}")
        
        if result['patterns']:
            print(f"\nDetected patterns:")
            for pattern in result['patterns']:
                print(f"  - {pattern['description']}")
    else:
        print(f"Error: {result['error']}")
