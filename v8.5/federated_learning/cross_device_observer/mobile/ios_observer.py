#!/usr/bin/env python3
"""
V8 Cross-Device Observer - iOS Observer

Observes workflows on iOS devices via ScreenTime API and OpenClaw nodes.

Requires:
- OpenClaw iOS app installed on target device
- Device paired with gateway
- ScreenTime permissions granted

Data sources:
1. ScreenTime API (app usage stats)
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
logger = logging.getLogger('v8.cross_device.ios')


class iOSObserver:
    """Observe workflows on iOS devices."""
    
    def __init__(self, workspace_root: str = None):
        if workspace_root is None:
            workspace_root = str(Path('/Users/tsmolty/workspace'))
        
        self.workspace_root = Path(workspace_root)
        
        # Privacy controls (stricter for mobile)
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
            'observe_only_during': 'work_hours',  # 9 AM - 6 PM
            'exclude_weekends': True,
            'max_recording_per_day': 5,  # minutes
            'require_explicit_start': True,
            'retention_days': 3,
            'auto_delete_recordings': True
        }
    
    def get_app_usage(self, node_id: str, date: str = 'today') -> Dict[str, Any]:
        """
        Get app usage stats from iOS ScreenTime API.
        
        Args:
            node_id: OpenClaw node ID for iOS device
            date: Date to query ('today', 'yesterday', or ISO date)
            
        Returns:
            App usage data (app name -> minutes used)
        """
        try:
            # In real implementation, would call OpenClaw nodes API:
            # nodes.invoke(node=node_id, invokeCommand='get_screentime_data', invokeParamsJson=...)
            
            # Placeholder: return mock data
            usage_data = {
                'Gmail': 45,
                'Slack': 120,
                'Calendar': 25,
                'Notion': 60,
                'GitHub': 30
            }
            
            logger.info(f"Retrieved app usage for {date}: {len(usage_data)} apps")
            return usage_data
            
        except Exception as e:
            logger.error(f"Error getting app usage: {e}")
            return {}
    
    def identify_high_usage_apps(self, usage_data: Dict[str, int], threshold_minutes: int = 30) -> List[str]:
        """
        Identify apps with high usage that should be analyzed.
        
        Args:
            usage_data: App usage dict (app -> minutes)
            threshold_minutes: Minimum usage to consider
            
        Returns:
            List of high-usage app names
        """
        high_usage = [
            app for app, minutes in usage_data.items()
            if minutes >= threshold_minutes and app in self.privacy_config['allowed_apps']
        ]
        
        logger.info(f"Identified {len(high_usage)} high-usage apps")
        return high_usage
    
    def request_workflow_sample(self, node_id: str, app_name: str, duration_sec: int = 60) -> Optional[str]:
        """
        Request a short screen recording sample for workflow analysis.
        
        Args:
            node_id: iOS device node ID
            app_name: App to record
            duration_sec: Recording duration (max 60s)
            
        Returns:
            Recording file path or None
        """
        try:
            # Check privacy limits
            if not self._check_recording_allowed(node_id):
                logger.warning("Recording quota exceeded for today")
                return None
            
            # In real implementation:
            # nodes.screen_record(node=node_id, durationMs=duration_sec*1000, outPath=...)
            
            logger.info(f"Recording {duration_sec}s sample of {app_name}")
            
            # Placeholder return
            return f"/tmp/workflow_sample_{app_name}_{datetime.now().timestamp()}.mp4"
            
        except Exception as e:
            logger.error(f"Error requesting workflow sample: {e}")
            return None
    
    def analyze_mobile_workflow(self, recording_path: str, app_name: str) -> Dict[str, Any]:
        """
        Analyze mobile app workflow from recording.
        
        Args:
            recording_path: Path to screen recording
            app_name: App being analyzed
            
        Returns:
            Workflow analysis (actions, patterns, automation opportunities)
        """
        try:
            # In real implementation:
            # 1. Extract frames from video
            # 2. Run mobile-optimized OCR
            # 3. Detect taps, swipes, scrolls
            # 4. Identify repeated patterns
            
            # Placeholder analysis
            analysis = {
                'app': app_name,
                'duration_sec': 60,
                'actions': [
                    {'type': 'scroll', 'count': 15},
                    {'type': 'tap', 'count': 8},
                    {'type': 'swipe', 'count': 3}
                ],
                'patterns': [
                    {
                        'description': f'Repeated email filtering in {app_name}',
                        'frequency': 3,
                        'time_spent_sec': 180,
                        'automation_potential': 0.7
                    }
                ]
            }
            
            logger.info(f"Analyzed workflow in {app_name}: {len(analysis['patterns'])} patterns found")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing mobile workflow: {e}")
            return {}
    
    def propose_mobile_automation(self, workflow_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Propose automations based on mobile workflow analysis.
        
        Args:
            workflow_analysis: Analysis from analyze_mobile_workflow()
            
        Returns:
            List of automation proposals
        """
        proposals = []
        
        app_name = workflow_analysis.get('app', '')
        patterns = workflow_analysis.get('patterns', [])
        
        for pattern in patterns:
            if pattern.get('automation_potential', 0) > 0.6:
                proposals.append({
                    'app': app_name,
                    'pattern': pattern['description'],
                    'time_saved_sec': int(pattern.get('time_spent_sec', 0) * 0.7),
                    'approach': self._suggest_automation_approach(app_name, pattern)
                })
        
        logger.info(f"Proposed {len(proposals)} mobile automations")
        return proposals
    
    def _suggest_automation_approach(self, app_name: str, pattern: Dict) -> str:
        """Suggest how to automate a mobile workflow."""
        # Map common patterns to automation approaches
        description = pattern.get('description', '').lower()
        
        if 'email' in description and 'filter' in description:
            return "Use email API to pre-filter messages before they reach your phone"
        elif 'calendar' in description:
            return "Sync calendar events automatically via CalDAV/Google Calendar API"
        elif 'notification' in description:
            return "Configure notification filters to reduce interruptions"
        elif 'message' in description:
            return "Set up auto-responders or message templates"
        else:
            return "Monitor via API and push summarized updates instead of manual checks"
    
    def _check_recording_allowed(self, node_id: str) -> bool:
        """Check if we're within recording limits."""
        # In real implementation, would check database for today's recording count
        # For now, always allow
        return True


if __name__ == '__main__':
    # Test iOS observer
    observer = iOSObserver()
    
    print("\n=== iOS Observer Test ===")
    
    # Get app usage
    usage = observer.get_app_usage('ios-node-123', date='today')
    
    print(f"\nApp usage (minutes):")
    for app, minutes in sorted(usage.items(), key=lambda x: x[1], reverse=True):
        print(f"  {app}: {minutes} min")
    
    # Identify high-usage apps
    high_usage = observer.identify_high_usage_apps(usage, threshold_minutes=30)
    
    print(f"\nHigh-usage work apps ({len(high_usage)}):")
    for app in high_usage:
        print(f"  - {app}")
    
    # Simulate workflow analysis
    if high_usage:
        app = high_usage[0]
        print(f"\nAnalyzing workflow in {app}...")
        
        # Request sample recording
        recording = observer.request_workflow_sample('ios-node-123', app, duration_sec=60)
        
        if recording:
            # Analyze workflow
            analysis = observer.analyze_mobile_workflow(recording, app)
            
            print(f"\nWorkflow analysis:")
            print(f"  Actions: {analysis.get('actions', [])}")
            print(f"  Patterns detected: {len(analysis.get('patterns', []))}")
            
            # Propose automations
            proposals = observer.propose_mobile_automation(analysis)
            
            if proposals:
                print(f"\nAutomation proposals:")
                for prop in proposals:
                    print(f"  - {prop['pattern']}")
                    print(f"    Time saved: {prop['time_saved_sec']}s/day")
                    print(f"    Approach: {prop['approach']}")
