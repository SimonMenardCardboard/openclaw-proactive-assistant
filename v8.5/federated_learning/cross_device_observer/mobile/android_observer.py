#!/usr/bin/env python3
"""
V8 Cross-Device Observer - Android Observer

Observes workflows on Android devices via UsageStatsManager and OpenClaw nodes.

Requires:
- OpenClaw Android app installed on target device
- Device paired with gateway
- Usage access permissions granted

Data sources:
1. UsageStatsManager API (app usage stats)
2. Screen recording (targeted samples)
3. OpenClaw nodes API for invocation
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('v8.cross_device.android')


class AndroidObserver:
    """Observe workflows on Android devices."""
    
    def __init__(self, workspace_root: str = None):
        if workspace_root is None:
            workspace_root = str(Path('/Users/tsmolty/workspace'))
        
        self.workspace_root = Path(workspace_root)
        
        # Privacy controls (same as iOS)
        self.privacy_config = {
            'excluded_apps': [
                'Banking', 'Health', 'Photos', 'Messages', 'Phone',
                'Settings', 'Wallet', 'Password Manager', 'Dating',
                'Social Media', 'Shopping'
            ],
            'allowed_apps': [
                'Gmail', 'Outlook', 'Slack', 'Teams', 'Discord',
                'Jira', 'Asana', 'Notion', 'GitHub',
                'Google Drive', 'Dropbox', 'OneDrive',
                'Calendar', 'Zoom', 'Meet'
            ],
            'observe_only_during': 'work_hours',
            'exclude_weekends': True,
            'max_recording_per_day': 5,
            'require_explicit_start': True,
            'retention_days': 3,
            'auto_delete_recordings': True
        }
    
    def get_app_usage(self, node_id: str, start_time: str, end_time: str) -> Dict[str, Any]:
        """
        Get app usage stats from Android UsageStatsManager.
        
        Args:
            node_id: OpenClaw node ID for Android device
            start_time: Start timestamp (ISO format)
            end_time: End timestamp (ISO format)
            
        Returns:
            App usage data (app name -> minutes used)
        """
        try:
            # In real implementation, would call OpenClaw nodes API:
            # nodes.invoke(
            #     node=node_id, 
            #     invokeCommand='get_usage_stats',
            #     invokeParamsJson=json.dumps({'start': start_time, 'end': end_time})
            # )
            
            # Placeholder: return mock data
            usage_data = {
                'Gmail': 50,
                'Slack': 135,
                'Calendar': 20,
                'Jira': 75,
                'GitHub': 40
            }
            
            logger.info(f"Retrieved app usage: {len(usage_data)} apps")
            return usage_data
            
        except Exception as e:
            logger.error(f"Error getting app usage: {e}")
            return {}
    
    def detect_foreground_events(self, node_id: str, duration_minutes: int = 60) -> List[Dict[str, Any]]:
        """
        Monitor foreground app changes in real-time.
        
        Args:
            node_id: Android device node ID
            duration_minutes: How long to monitor
            
        Returns:
            List of app launch/switch events
        """
        try:
            # In real implementation, would stream events from device
            # via OpenClaw nodes API
            
            # Placeholder: simulate events
            events = [
                {'timestamp': '2026-04-08T10:15:00', 'app': 'Gmail', 'action': 'launched'},
                {'timestamp': '2026-04-08T10:18:30', 'app': 'Slack', 'action': 'switched'},
                {'timestamp': '2026-04-08T10:25:15', 'app': 'Gmail', 'action': 'switched'},
                {'timestamp': '2026-04-08T10:32:00', 'app': 'Jira', 'action': 'launched'},
            ]
            
            logger.info(f"Detected {len(events)} foreground events")
            return events
            
        except Exception as e:
            logger.error(f"Error detecting foreground events: {e}")
            return []
    
    def analyze_app_switching_pattern(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze app switching patterns for multitasking insights.
        
        Args:
            events: List of foreground app events
            
        Returns:
            Switching pattern analysis
        """
        if len(events) < 2:
            return {'pattern': 'insufficient_data'}
        
        # Count app switches
        app_switches = {}
        for i in range(len(events) - 1):
            current_app = events[i]['app']
            next_app = events[i+1]['app']
            
            switch = f"{current_app} → {next_app}"
            app_switches[switch] = app_switches.get(switch, 0) + 1
        
        # Identify most common switches
        frequent_switches = sorted(app_switches.items(), key=lambda x: x[1], reverse=True)[:3]
        
        analysis = {
            'pattern': 'frequent_switching' if len(frequent_switches) > 0 else 'single_focus',
            'top_switches': [
                {'switch': switch, 'count': count}
                for switch, count in frequent_switches
            ],
            'total_switches': len(events) - 1
        }
        
        # Detect interruption patterns
        if analysis['total_switches'] > 10:
            analysis['interruption_rate'] = 'high'
            analysis['recommendation'] = 'Consider batch processing or notification management'
        else:
            analysis['interruption_rate'] = 'moderate'
        
        logger.info(f"App switching pattern: {analysis['pattern']}")
        return analysis
    
    def request_screen_recording(self, node_id: str, app_name: str, duration_sec: int = 60) -> Optional[str]:
        """
        Request screen recording for Android app.
        
        Args:
            node_id: Android device node ID
            app_name: App to record
            duration_sec: Recording duration
            
        Returns:
            Recording file path or None
        """
        try:
            # Check privacy controls
            if not self._check_recording_allowed(app_name):
                logger.warning(f"Recording not allowed for {app_name} (privacy settings)")
                return None
            
            # In real implementation:
            # nodes.screen_record(node=node_id, durationMs=duration_sec*1000, outPath=...)
            
            logger.info(f"Recording {duration_sec}s of {app_name} on Android")
            
            return f"/tmp/android_recording_{app_name}_{datetime.now().timestamp()}.mp4"
            
        except Exception as e:
            logger.error(f"Error requesting screen recording: {e}")
            return None
    
    def _check_recording_allowed(self, app_name: str) -> bool:
        """Check if app is allowed to be recorded."""
        return app_name in self.privacy_config['allowed_apps']
    
    def compare_ios_android_workflows(self, ios_usage: Dict, android_usage: Dict) -> Dict[str, Any]:
        """
        Compare workflows across iOS and Android to identify device preferences.
        
        Args:
            ios_usage: iOS app usage data
            android_usage: Android app usage data
            
        Returns:
            Cross-device workflow analysis
        """
        # Find common apps
        common_apps = set(ios_usage.keys()) & set(android_usage.keys())
        
        device_preferences = {}
        for app in common_apps:
            ios_time = ios_usage[app]
            android_time = android_usage[app]
            
            total = ios_time + android_time
            ios_pct = (ios_time / total * 100) if total > 0 else 0
            
            if ios_pct > 70:
                preferred = 'iOS'
            elif ios_pct < 30:
                preferred = 'Android'
            else:
                preferred = 'Both'
            
            device_preferences[app] = {
                'preferred_device': preferred,
                'ios_minutes': ios_time,
                'android_minutes': android_time,
                'total_minutes': total
            }
        
        analysis = {
            'common_apps': len(common_apps),
            'device_preferences': device_preferences,
            'recommendations': self._generate_device_recommendations(device_preferences)
        }
        
        logger.info(f"Cross-device analysis: {len(common_apps)} apps used on both platforms")
        return analysis
    
    def _generate_device_recommendations(self, preferences: Dict) -> List[str]:
        """Generate recommendations for optimal device usage."""
        recommendations = []
        
        # Count preferences
        ios_preferred = sum(1 for p in preferences.values() if p['preferred_device'] == 'iOS')
        android_preferred = sum(1 for p in preferences.values() if p['preferred_device'] == 'Android')
        
        if ios_preferred > android_preferred * 2:
            recommendations.append("Consider consolidating workflows on iOS for efficiency")
        elif android_preferred > ios_preferred * 2:
            recommendations.append("Consider consolidating workflows on Android for efficiency")
        
        # Identify long-duration apps that could be automated
        for app, pref in preferences.items():
            if pref['total_minutes'] > 60:  # >1 hour/day
                recommendations.append(f"Automate {app} workflows (spending {pref['total_minutes']}min/day)")
        
        return recommendations


if __name__ == '__main__':
    # Test Android observer
    observer = AndroidObserver()
    
    print("\n=== Android Observer Test ===")
    
    # Get app usage
    start = datetime.now().replace(hour=0, minute=0, second=0).isoformat()
    end = datetime.now().isoformat()
    
    usage = observer.get_app_usage('android-node-456', start, end)
    
    print(f"\nApp usage (minutes):")
    for app, minutes in sorted(usage.items(), key=lambda x: x[1], reverse=True):
        print(f"  {app}: {minutes} min")
    
    # Detect foreground events
    events = observer.detect_foreground_events('android-node-456', duration_minutes=60)
    
    print(f"\nForeground events: {len(events)}")
    for event in events[:5]:  # Show first 5
        print(f"  {event['timestamp']}: {event['app']} ({event['action']})")
    
    # Analyze switching patterns
    if events:
        pattern = observer.analyze_app_switching_pattern(events)
        
        print(f"\nApp switching pattern: {pattern['pattern']}")
        print(f"Total switches: {pattern['total_switches']}")
        
        if pattern.get('top_switches'):
            print(f"\nMost frequent switches:")
            for switch_info in pattern['top_switches']:
                print(f"  {switch_info['switch']} ({switch_info['count']}x)")
        
        if pattern.get('recommendation'):
            print(f"\nRecommendation: {pattern['recommendation']}")
    
    # Cross-device comparison (mock iOS data)
    ios_usage = {'Gmail': 45, 'Slack': 120, 'Calendar': 25, 'Jira': 30}
    
    print(f"\n=== Cross-Device Analysis ===")
    comparison = observer.compare_ios_android_workflows(ios_usage, usage)
    
    print(f"Common apps: {comparison['common_apps']}")
    
    if comparison.get('recommendations'):
        print(f"\nRecommendations:")
        for rec in comparison['recommendations']:
            print(f"  - {rec}")
