#!/usr/bin/env python3
"""
V8 Cross-Device Observer - Desktop Observer V2
Integrated version with real screen capture and activity extraction.
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
import time

from screen_capture import ScreenCapture
from activity_extractor import ActivityExtractor

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('v8.cross_device.desktop_v2')


class DesktopObserverV2:
    """Observe workflows on remote desktop devices with real capture."""
    
    def __init__(self, workspace_root: str = None):
        if workspace_root is None:
            workspace_root = str(Path.home() / '.openclaw' / 'workspace')
        
        self.workspace_root = Path(workspace_root)
        self.observer_db = self.workspace_root / 'integrations' / 'intelligence' / 'v8_meta_learning' / 'cross_device.db'
        
        # Initialize components
        self.screen_capture = ScreenCapture(privacy_mode='activity_only')
        self.activity_extractor = ActivityExtractor()
        
        self._init_db()
        
        # Privacy controls
        self.privacy_config = {
            'capture_mode': 'activity_only',
            'ocr_filter': self.activity_extractor.privacy_filters,
            'logging': 'patterns_only',
            'retention_days': 7,
            'encryption': 'at_rest',
            'local_only': True,
            'consent_required': True
        }
        
        logger.info("Desktop Observer V2 initialized with real capture")
    
    def _init_db(self):
        """Initialize cross-device observation database."""
        self.observer_db.parent.mkdir(parents=True, exist_ok=True)
        
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
        """Register a device for observation."""
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
            if device_id == 0:  # Update case
                cursor.execute('SELECT id FROM observed_devices WHERE device_name = ?', (device_name,))
                device_id = cursor.fetchone()[0]
            
            conn.commit()
            conn.close()
            
            logger.info(f"Registered device: {device_name} ({device_type}) at {host}:{port}")
            return device_id
            
        except Exception as e:
            logger.error(f"Error registering device: {e}")
            return -1
    
    def grant_consent(self, device_id: int):
        """Grant observation consent for a device."""
        try:
            conn = sqlite3.connect(str(self.observer_db))
            cursor = conn.cursor()
            
            cursor.execute('UPDATE observed_devices SET consent_given = 1 WHERE id = ?', (device_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Consent granted for device {device_id}")
            
        except Exception as e:
            logger.error(f"Error granting consent: {e}")
    
    def observe_device_localhost(self, duration_minutes: int = 2) -> Dict[str, Any]:
        """
        Observe localhost device (for testing on Mac).
        
        Uses native screencapture instead of VNC for simpler testing.
        
        Args:
            duration_minutes: How long to observe
            
        Returns:
            Observation summary
        """
        logger.info(f"Starting localhost observation for {duration_minutes} minutes")
        
        # Register localhost
        device_id = self.register_device(
            device_name='localhost',
            device_type='mac',
            host='localhost',
            port=0,
            protocol='native'
        )
        
        self.grant_consent(device_id)
        
        return self.observe_device(device_id, duration_minutes, use_localhost=True)
    
    def observe_device(self, device_id: int, duration_minutes: int = 5, 
                      use_localhost: bool = False) -> Dict[str, Any]:
        """
        Observe a device for a period of time with real capture.
        
        Args:
            device_id: Device to observe
            duration_minutes: How long to observe
            use_localhost: Use localhost native capture instead of VNC
            
        Returns:
            Observation summary
        """
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
            capture_count = 0
            capture_errors = 0
            
            # Observation loop with real capture
            while datetime.now() < end_time:
                try:
                    # Capture screenshot
                    if use_localhost:
                        screenshot_path = self.screen_capture.capture_localhost_screenshot()
                    else:
                        screenshot_path = self.screen_capture.capture_vnc(host, port)
                    
                    if screenshot_path and screenshot_path.exists():
                        capture_count += 1
                        
                        # Extract activity from screenshot
                        activity = self.activity_extractor.extract_from_screenshot(screenshot_path)
                        
                        if activity and 'error' not in activity:
                            activity['timestamp'] = datetime.now().isoformat()
                            activities.append(activity)
                            self._save_activity(device_id, activity)
                            
                            logger.debug(f"Activity captured: {activity.get('app_name')} - {activity.get('action_type')}")
                        
                        # Delete screenshot (privacy)
                        self.screen_capture.cleanup_screenshot(screenshot_path)
                    else:
                        capture_errors += 1
                        logger.warning("Screenshot capture failed")
                    
                except Exception as e:
                    capture_errors += 1
                    logger.error(f"Error in observation loop: {e}")
                
                # Wait before next capture
                time.sleep(15)  # Sample every 15 seconds
            
            # Analyze collected activities
            patterns = self._detect_patterns_from_activities(device_id, activities)
            
            # Update device stats
            self._update_device_stats(device_id, len(activities))
            
            result = {
                'device': device_name,
                'duration_minutes': duration_minutes,
                'captures_attempted': capture_count,
                'captures_failed': capture_errors,
                'activities_extracted': len(activities),
                'patterns_detected': len(patterns),
                'patterns': patterns,
                'sample_activities': activities[:5]  # First 5 for review
            }
            
            logger.info(f"Observation complete: {len(activities)} activities, {len(patterns)} patterns")
            
            return result
            
        except Exception as e:
            logger.error(f"Error observing device: {e}")
            return {'error': str(e)}
        finally:
            # Cleanup any remaining screenshots
            self.screen_capture.cleanup_all()
    
    def _save_activity(self, device_id: int, activity: Dict[str, Any]):
        """Save observed activity to database."""
        try:
            conn = sqlite3.connect(str(self.observer_db))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO activity_observations
                (device_id, timestamp, app_name, window_title, action_type, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                device_id,
                activity.get('timestamp'),
                activity.get('app_name'),
                activity.get('window_title'),
                activity.get('action_type'),
                json.dumps({k: v for k, v in activity.items() if k not in ['timestamp', 'app_name', 'window_title', 'action_type']})
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving activity: {e}")
    
    def _detect_patterns_from_activities(self, device_id: int, activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect workflow patterns from collected activities."""
        if not activities:
            return []
        
        # Use activity extractor's pattern detection
        pattern_result = self.activity_extractor.extract_pattern_from_sequence(activities)
        
        patterns = []
        
        if pattern_result.get('pattern') != 'none':
            pattern = {
                'type': pattern_result['pattern'],
                'description': pattern_result.get('description', ''),
                'frequency': pattern_result.get('frequency', 1),
                'automation_candidate': 1 if pattern_result['pattern'] == 'repeated_app_switch' else 0
            }
            patterns.append(pattern)
            
            # Save to database
            self._save_pattern(device_id, pattern)
        
        return patterns
    
    def _save_pattern(self, device_id: int, pattern: Dict[str, Any]):
        """Save detected pattern to database."""
        try:
            conn = sqlite3.connect(str(self.observer_db))
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            
            cursor.execute('''
                INSERT INTO detected_patterns
                (device_id, pattern_type, description, frequency, automation_candidate, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                device_id,
                pattern['type'],
                pattern.get('description', ''),
                pattern.get('frequency', 1),
                pattern.get('automation_candidate', 0),
                now,
                now
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving pattern: {e}")
    
    def _update_device_stats(self, device_id: int, activity_count: int):
        """Update device observation statistics."""
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


if __name__ == '__main__':
    # Test desktop observer V2 with real capture
    print("\n" + "=" * 70)
    print("V8 DESKTOP OBSERVER V2 - REAL CAPTURE TEST")
    print("=" * 70)
    
    observer = DesktopObserverV2()
    
    print("\n✓ Observer initialized")
    print(f"  Database: {observer.observer_db}")
    print(f"  Privacy mode: {observer.privacy_config['capture_mode']}")
    print(f"  OCR filters: {len(observer.privacy_config['ocr_filter'])} keywords")
    
    # Test localhost observation
    print("\n--- Testing Localhost Observation ---")
    print("This will capture screenshots of your current desktop.")
    print("Duration: 1 minute (4 samples at 15-second intervals)")
    print("\nPress Ctrl+C to cancel, or wait to continue...")
    
    try:
        time.sleep(3)
        
        print("\nStarting observation...")
        result = observer.observe_device_localhost(duration_minutes=1)
        
        print("\n" + "=" * 70)
        print("OBSERVATION RESULTS")
        print("=" * 70)
        
        if 'error' not in result:
            print(f"✓ Device: {result['device']}")
            print(f"✓ Duration: {result['duration_minutes']} minutes")
            print(f"✓ Captures attempted: {result['captures_attempted']}")
            print(f"✓ Captures failed: {result['captures_failed']}")
            print(f"✓ Activities extracted: {result['activities_extracted']}")
            print(f"✓ Patterns detected: {result['patterns_detected']}")
            
            if result['patterns']:
                print("\nDetected Patterns:")
                for pattern in result['patterns']:
                    print(f"  • {pattern['description']}")
                    print(f"    Type: {pattern['type']}")
                    print(f"    Frequency: {pattern['frequency']}")
            
            if result.get('sample_activities'):
                print("\nSample Activities:")
                for i, activity in enumerate(result['sample_activities'][:3], 1):
                    print(f"  {i}. App: {activity.get('app_name', 'Unknown')}")
                    print(f"     Action: {activity.get('action_type', 'Unknown')}")
                    print(f"     Window: {activity.get('window_title', 'N/A')}")
        else:
            print(f"✗ Error: {result['error']}")
        
        print("\n" + "=" * 70)
        
    except KeyboardInterrupt:
        print("\n\n✗ Observation cancelled by user")
    except Exception as e:
        print(f"\n✗ Error: {e}")
