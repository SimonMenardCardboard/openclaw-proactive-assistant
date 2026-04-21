#!/usr/bin/env python3
"""
V8 Auto-Optimizer - Phase 2

Automatically generates and proposes optimizations from detected patterns.

Flow:
1. Read pattern detections from V8
2. Generate code using CodeGenerator
3. Submit proposals via ApprovalWorkflow
4. Notify user for review
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Add modules to path
sys.path.insert(0, str(Path(__file__).parent))
from code_generator import CodeGenerator
from deployment_manager import DeploymentManager
from pattern_learner.detector import PatternDetector
from shell_history_analyzer import ShellHistoryAnalyzer
from telegram_notifier import TelegramNotifier
from multi_account_email_analyzer import MultiAccountEmailAnalyzer
from multi_account_calendar_analyzer import MultiAccountCalendarAnalyzer

# NEW: Import all 4 critical analyzers
try:
    from location_analyzer import LocationAnalyzer
except ImportError:
    LocationAnalyzer = None

try:
    from cross_device_observer.mobile.ios_observer import iOSObserver
except ImportError:
    iOSObserver = None

try:
    from file_operations_analyzer import FileOperationsAnalyzer
except ImportError:
    FileOperationsAnalyzer = None

try:
    from browser_history_analyzer import BrowserHistoryAnalyzer
except ImportError:
    BrowserHistoryAnalyzer = None

try:
    from daemon_pattern_analyzer import DaemonPatternAnalyzer
except ImportError:
    DaemonPatternAnalyzer = None

# NEW: Chief of Staff Integration
try:
    from chief_of_staff_adapter import ChiefOfStaffV8Adapter
except ImportError:
    ChiefOfStaffV8Adapter = None


class AutoOptimizer:
    """Automatically generate optimizations from patterns"""
    
    def __init__(self, enable_auto_deploy: bool = False):
        self.pattern_detector = PatternDetector()  # V6 execution patterns
        self.shell_analyzer = ShellHistoryAnalyzer()  # User shell patterns
        self.email_analyzer = MultiAccountEmailAnalyzer()  # Email patterns
        self.calendar_analyzer = MultiAccountCalendarAnalyzer()  # Calendar patterns
        
        # NEW: Initialize critical analyzers
        self.location_analyzer = LocationAnalyzer() if LocationAnalyzer else None
        self.ios_observer = iOSObserver() if iOSObserver else None
        self.file_ops_analyzer = FileOperationsAnalyzer() if FileOperationsAnalyzer else None
        self.browser_analyzer = BrowserHistoryAnalyzer() if BrowserHistoryAnalyzer else None
        self.daemon_analyzer = DaemonPatternAnalyzer() if DaemonPatternAnalyzer else None
        
        # NEW: Chief of Staff intelligence layer
        self.cos_adapter = ChiefOfStaffV8Adapter() if ChiefOfStaffV8Adapter else None
        
        self.code_generator = CodeGenerator()
        self.deployment_manager = DeploymentManager(
            auto_approve_threshold=0.90,
            enable_auto_deploy=enable_auto_deploy
        )
        self.telegram_notifier = TelegramNotifier()  # Telegram notifications
        
        self.min_confidence = 0.75  # Only generate for high-confidence patterns
        self.min_occurrences = 5    # Pattern must appear at least 5 times
        self.enable_auto_deploy = enable_auto_deploy
    
    def scan_for_patterns(self) -> List[Dict]:
        """Scan V6 logs, shell history, email, calendar, and cross-device for patterns"""
        all_patterns = []
        
        # 1. Get V6 execution patterns (system automation)
        v6_patterns = self._get_v6_patterns()
        all_patterns.extend(v6_patterns)
        print(f"   V6 patterns: {len(v6_patterns)}")
        
        # 2. Get shell history patterns (user workflows)
        shell_patterns = self._get_shell_patterns()
        all_patterns.extend(shell_patterns)
        print(f"   Shell patterns: {len(shell_patterns)}")
        
        # 3. Get email patterns (communication workflows)
        email_patterns = self._get_email_patterns()
        all_patterns.extend(email_patterns)
        print(f"   Email patterns: {len(email_patterns)}")
        
        # 4. Get calendar patterns (meeting workflows)
        calendar_patterns = self._get_calendar_patterns()
        all_patterns.extend(calendar_patterns)
        print(f"   Calendar patterns: {len(calendar_patterns)}")
        
        # 5. Get cross-device patterns (desktop + mobile workflows)
        device_patterns = self._get_device_patterns()
        all_patterns.extend(device_patterns)
        print(f"   Device patterns: {len(device_patterns)}")
        
        # 6. NEW: Get location patterns (GPS + geofence)
        location_patterns = self._get_location_patterns()
        all_patterns.extend(location_patterns)
        print(f"   Location patterns: {len(location_patterns)}")
        
        # 7. NEW: Get mobile usage patterns (iOS app usage)
        mobile_patterns = self._get_mobile_patterns()
        all_patterns.extend(mobile_patterns)
        print(f"   Mobile patterns: {len(mobile_patterns)}")
        
        # 8. NEW: Get file operation patterns
        file_patterns = self._get_file_patterns()
        all_patterns.extend(file_patterns)
        print(f"   File patterns: {len(file_patterns)}")
        
        # 9. NEW: Get browser workflow patterns
        browser_patterns = self._get_browser_patterns()
        all_patterns.extend(browser_patterns)
        print(f"   Browser patterns: {len(browser_patterns)}")
        
        # 10. NEW: Get daemon health patterns
        daemon_patterns = self._get_daemon_patterns()
        all_patterns.extend(daemon_patterns)
        print(f"   Daemon patterns: {len(daemon_patterns)}")
        
        # 11. NEW: Get Chief of Staff intelligence patterns
        cos_patterns = self._get_cos_patterns()
        all_patterns.extend(cos_patterns)
        print(f"   Chief of Staff patterns: {len(cos_patterns)}")
        
        return all_patterns
    
    def _get_v6_patterns(self) -> List[Dict]:
        """Get patterns from V6 execution logs"""
        # Run detection cycle
        self.pattern_detector.run_detection_cycle(lookback_days=7)
        
        # Get patterns from database
        import sqlite3
        db_path = Path.home() / 'workspace/integrations/intelligence/v8_meta_learning/patterns.db'
        
        if not db_path.exists():
            return []
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get recent high-confidence patterns
        cursor.execute("""
            SELECT pattern_type, metadata, confidence, frequency, description
            FROM pattern_candidates
            WHERE last_seen >= datetime('now', '-7 days')
            AND confidence >= 0.70
            AND status = 'candidate'
            ORDER BY confidence DESC, frequency DESC
            LIMIT 20
        """)
        
        patterns = []
        for row in cursor.fetchall():
            import json
            try:
                metadata = json.loads(row[1]) if row[1] else {}
            except:
                metadata = {}
            
            # Skip V6 internal actions (not useful for shell wrappers)
            action_name = metadata.get('action_name', '')
            if action_name in ['restart_launchagent', 'refresh_auth_token', 
                              'send_form_reminder', 'send_training_rec']:
                continue
            
            patterns.append({
                'type': row[0],  # repeated_action or workflow_sequence
                'confidence': row[2],
                'count': row[3],
                'description': row[4],
                'metadata': metadata,
                'source': 'v6'
            })
        
        conn.close()
        return patterns
    
    def _get_shell_patterns(self) -> List[Dict]:
        """Get patterns from shell history"""
        try:
            results = self.shell_analyzer.analyze()
            
            patterns = []
            
            # Add repeated commands
            for pattern in results.get('repeated_commands', []):
                patterns.append({
                    'type': pattern['template'],  # 'command_retry'
                    'command': pattern['command'],
                    'confidence': pattern['confidence'],
                    'count': pattern['occurrences'],
                    'description': pattern['description'],
                    'source': 'shell'
                })
            
            # Add git workflows
            for pattern in results.get('git_workflows', []):
                patterns.append({
                    'type': pattern['template'],  # 'multi_command'
                    'commands': pattern['commands'],
                    'name': 'git_' + pattern['sequence'].replace(' → ', '_').replace(' ', '_'),
                    'confidence': pattern['confidence'],
                    'count': pattern['occurrences'],
                    'description': pattern['description'],
                    'source': 'shell'
                })
            
            return patterns
        
        except Exception as e:
            print(f"   Shell history error: {e}")
            return []
    
    def _get_email_patterns(self) -> List[Dict]:
        """Get patterns from email across all accounts"""
        try:
            results = self.email_analyzer.analyze_all_accounts()
            patterns = []
            
            # Convert email patterns to optimization format
            for pattern in results.get('patterns', []):
                pattern_type = pattern.get('type')
                
                if pattern_type == 'similar_subjects':
                    # Email template opportunity
                    patterns.append({
                        'type': 'email_template',
                        'subject_pattern': pattern.get('subject_pattern'),
                        'accounts': pattern.get('accounts', []),
                        'count': pattern.get('count', 0),
                        'confidence': 0.85 if pattern.get('count', 0) >= 5 else 0.70,
                        'description': f"Repeated email: '{pattern.get('subject_pattern')}' ({pattern.get('count')} times)",
                        'source': 'email'
                    })
                
                elif pattern_type == 'frequent_recipients':
                    # Auto-compose to frequent contacts
                    for recipient, count in pattern.get('recipients', {}).items():
                        if count >= 5:
                            patterns.append({
                                'type': 'email_shortcut',
                                'recipient': recipient,
                                'count': count,
                                'confidence': 0.80,
                                'description': f"Frequent recipient: {recipient} ({count} emails)",
                                'source': 'email'
                            })
                
                elif pattern_type == 'time_patterns':
                    # Scheduled email reminders
                    patterns.append({
                        'type': 'email_schedule',
                        'pattern': pattern.get('pattern'),
                        'time': pattern.get('time'),
                        'count': pattern.get('count', 0),
                        'confidence': 0.75,
                        'description': f"Email pattern: {pattern.get('pattern')} at {pattern.get('time')}",
                        'source': 'email'
                    })
            
            return patterns
        
        except Exception as e:
            print(f"   Email pattern error: {e}")
            return []
    
    def _get_calendar_patterns(self) -> List[Dict]:
        """Get patterns from calendar across all accounts"""
        try:
            results = self.calendar_analyzer.analyze_all_accounts()
            patterns = []
            
            # Convert calendar patterns to optimization format
            for pattern in results.get('patterns', []):
                pattern_type = pattern.get('type')
                
                if pattern_type == 'recurring_event':
                    # Meeting prep/follow-up automation
                    patterns.append({
                        'type': 'meeting_automation',
                        'event_pattern': pattern.get('event_pattern'),
                        'recurrence': pattern.get('recurrence'),
                        'count': pattern.get('count', 0),
                        'confidence': 0.85,
                        'description': f"Recurring: '{pattern.get('event_pattern')}' ({pattern.get('recurrence')})",
                        'source': 'calendar'
                    })
                
                elif pattern_type == 'time_block':
                    # Focus time protection
                    patterns.append({
                        'type': 'focus_block',
                        'day': pattern.get('day'),
                        'time': pattern.get('time'),
                        'duration': pattern.get('duration', 60),
                        'confidence': 0.80,
                        'description': f"Focus time: {pattern.get('day')} {pattern.get('time')} ({pattern.get('duration')}min)",
                        'source': 'calendar'
                    })
                
                elif pattern_type == 'meeting_category':
                    # Category-specific automation (client meetings, team sync, etc.)
                    patterns.append({
                        'type': 'meeting_workflow',
                        'category': pattern.get('category'),
                        'count': pattern.get('count', 0),
                        'confidence': 0.75,
                        'description': f"{pattern.get('category')} meetings ({pattern.get('count')} occurrences)",
                        'source': 'calendar'
                    })
            
            return patterns
        
        except Exception as e:
            print(f"   Calendar pattern error: {e}")
            return []
    
    def _get_device_patterns(self) -> List[Dict]:
        """Get patterns from cross-device observation"""
        try:
            # Import cross-device observer
            sys.path.insert(0, str(Path(__file__).parent / 'cross_device_observer' / 'desktop'))
            from observer_v2 import DesktopObserverV2
            
            observer = DesktopObserverV2()
            patterns = []
            
            # Get recent observations (last 7 days)
            observations = observer.get_recent_activities(days=7)
            
            # Analyze for patterns
            if observations:
                # Group by application
                app_usage = {}
                for obs in observations:
                    app = obs.get('application', 'unknown')
                    if app not in app_usage:
                        app_usage[app] = {'count': 0, 'actions': []}
                    app_usage[app]['count'] += 1
                    app_usage[app]['actions'].append(obs.get('activity', ''))
                
                # Detect repeated application workflows
                for app, data in app_usage.items():
                    if data['count'] >= 5:  # Minimum threshold
                        # Check for repeated action sequences
                        action_sequences = self._find_action_sequences(data['actions'])
                        
                        for seq in action_sequences:
                            if len(seq['actions']) >= 2:  # Multi-step workflow
                                patterns.append({
                                    'type': 'multi_command',
                                    'name': f"{app.lower().replace(' ', '_')}_workflow",
                                    'commands': seq['actions'],
                                    'count': seq['count'],
                                    'confidence': min(0.70 + (seq['count'] / 20), 0.95),
                                    'description': f"{app} workflow: {' → '.join(seq['actions'][:3])}",
                                    'source': 'device_observation'
                                })
            
            return patterns
        
        except Exception as e:
            print(f"   Device pattern error: {e}")
            return []
    
    def _find_action_sequences(self, actions: List[str], min_length: int = 2) -> List[Dict]:
        """Find repeated action sequences in a list of actions"""
        sequences = {}
        
        # Look for sequences of length 2-5
        for seq_len in range(min_length, min(6, len(actions))):
            for i in range(len(actions) - seq_len + 1):
                seq = tuple(actions[i:i+seq_len])
                if seq not in sequences:
                    sequences[seq] = 0
                sequences[seq] += 1
        
        # Return sequences that occurred multiple times
        result = []
        for seq, count in sequences.items():
            if count >= 3:  # Repeated at least 3 times
                result.append({
                    'actions': list(seq),
                    'count': count
                })
        
        return sorted(result, key=lambda x: x['count'], reverse=True)
    
    def filter_patterns(self, patterns: List[Dict]) -> List[Dict]:
        """Filter patterns suitable for code generation"""
        suitable = []
        
        for pattern in patterns:
            confidence = pattern.get('confidence', 0.0)
            occurrences = pattern.get('count', 0)
            pattern_type = pattern.get('type', '')
            
            # Must be high confidence
            if confidence < self.min_confidence:
                continue
            
            # Must occur frequently enough
            if occurrences < self.min_occurrences:
                continue
            
            # Must be a supported template type
            if not self._is_supported_type(pattern_type):
                continue
            
            suitable.append(pattern)
        
        return suitable
    
    def _map_to_template_type(self, pattern_type: str) -> str:
        """Map V8 pattern type to code generator template type"""
        type_mapping = {
            'repeated_action': 'command_retry',
            'workflow_sequence': 'multi_command',
            'retry_pattern': 'command_retry',
            'navigation_pattern': 'dir_navigation',
            'workflow_pattern': 'multi_command',
            'cache_pattern': 'cache_operation',
            'dedup_pattern': 'deduplication'
        }
        return type_mapping.get(pattern_type)
    
    def _extract_pattern_parameters(self, pattern: Dict) -> Dict:
        """Extract code generation parameters from pattern"""
        pattern_type = pattern['type']
        source = pattern.get('source', 'v6')
        
        if pattern_type == 'command_retry':
            # Shell history patterns already have 'command'
            if 'command' not in pattern:
                # V6 pattern - extract from metadata/description
                metadata = pattern.get('metadata', {})
                description = pattern.get('description', '')
                
                command = metadata.get('action_name', 'unknown')
                if not command or command == 'unknown':
                    # Try to extract from description
                    import re
                    match = re.search(r"Action '([^']+)'", description)
                    if match:
                        command = match.group(1)
                
                pattern['command'] = command
            
            # Set retry parameters
            pattern['parameters'] = {
                'max_retries': 3,
                'delay': 2
            }
        
        elif pattern_type == 'multi_command':
            # Shell history patterns already have 'commands' and 'name'
            if 'commands' not in pattern:
                # V6 pattern - extract from metadata
                metadata = pattern.get('metadata', {})
                
                commands = metadata.get('actions', [])
                if isinstance(commands, str):
                    import json
                    try:
                        commands = json.loads(commands)
                    except:
                        commands = commands.split(' && ')
                
                # Skip if no commands
                if not commands:
                    return None
                
                pattern['commands'] = commands
                pattern['name'] = metadata.get('action_name', 'workflow')
        
        return pattern
    
    def _is_supported_type(self, pattern_type: str) -> bool:
        """Check if pattern type is supported by code generator"""
        supported = [
            'command_retry',
            'dir_navigation', 
            'multi_command',
            'cache_operation',
            'deduplication'
        ]
        
        # Map V8 pattern types to template types
        type_mapping = {
            # V8 actual types
            'repeated_action': 'command_retry',  # Repeated commands → retry wrapper
            'workflow_sequence': 'multi_command',  # Command sequences → workflow script
            # Legacy types (if any)
            'retry_pattern': 'command_retry',
            'navigation_pattern': 'dir_navigation',
            'workflow_pattern': 'multi_command',
            'cache_pattern': 'cache_operation',
            'dedup_pattern': 'deduplication'
        }
        
        mapped_type = type_mapping.get(pattern_type, pattern_type)
        return mapped_type in supported
    
    def _get_existing_proposal_names(self) -> set:
        """Get set of existing pending proposal script names"""
        pending = self.approval_workflow.get_pending()
        return {p['script_name'] for p in pending}
    
    def generate_proposals(self, patterns: List[Dict]) -> List[Dict]:
        """Generate code for each pattern and create proposals"""
        proposals = []
        existing_proposals = self._get_existing_proposal_names()
        
        for pattern in patterns:
            # Map V8 pattern type to template type
            pattern_copy = pattern.copy()
            
            # Check if already a template type (from shell analyzer)
            if pattern['type'] in ['command_retry', 'multi_command', 'dir_navigation', 'cache_operation', 'deduplication']:
                mapped_type = pattern['type']
            else:
                # V6 pattern - needs mapping
                mapped_type = self._map_to_template_type(pattern['type'])
                if not mapped_type:
                    continue
            
            pattern_copy['type'] = mapped_type
            
            # Extract parameters from pattern data
            pattern_copy = self._extract_pattern_parameters(pattern_copy)
            
            # Skip if extraction failed (e.g., no commands for workflow)
            if pattern_copy is None:
                continue
            
            # Generate code
            result = self.code_generator.generate(pattern_copy)
            
            if not result:
                print(f"❌ Failed to generate code for {pattern.get('type')}")
                continue
            
            # Check if proposal already exists
            script_name = result.get('script_name')
            if script_name in existing_proposals:
                print(f"⏭️  Skipped duplicate: {script_name}")
                continue
            
            # Deploy with full pipeline (sandbox + approval + deploy if auto-approved)
            try:
                deployment_result = self.deployment_manager.deploy_optimization(
                    pattern=pattern,
                    generated_code=result
                )
                
                proposals.append({
                    'id': deployment_result['proposal_id'],
                    'deployment_id': deployment_result.get('deployment_id'),
                    'pattern': pattern,
                    'generated_code': result,
                    'status': deployment_result['status'],
                    'approval_status': deployment_result['approval_status']
                })
                existing_proposals.add(script_name)  # Track new proposals
                
                # Log result
                status_icon = '🚀' if deployment_result['status'] == 'deployed' else '📝' if deployment_result['approval_status'] == 'approved' else '⏸️'
                print(f"{status_icon} Proposal #{deployment_result['proposal_id']}: {result['script_name']} ({deployment_result['status']})")
                
            except Exception as e:
                print(f"❌ Failed to deploy optimization: {e}")
                import traceback
                traceback.print_exc()
        
        return proposals
    
    def run_cycle(self) -> Dict:
        """
        Run one optimization cycle:
        1. Scan for patterns
        2. Filter suitable ones
        3. Generate code
        4. Submit proposals
        """
        print("🔍 Scanning for new optimization opportunities...")
        
        # Get patterns from V8
        all_patterns = self.scan_for_patterns()
        print(f"   Found {len(all_patterns)} total patterns")
        
        # Filter suitable patterns
        suitable = self.filter_patterns(all_patterns)
        print(f"   {len(suitable)} suitable for code generation")
        
        if not suitable:
            print("✅ No new optimization opportunities")
            return {
                'patterns_found': len(all_patterns),
                'proposals_generated': 0
            }
        
        # Generate proposals
        print(f"🔧 Generating code for {len(suitable)} pattern(s)...")
        proposals = self.generate_proposals(suitable)
        
        print(f"✅ Generated {len(proposals)} proposal(s)")
        
        # Generate notification
        if proposals:
            self._notify_user(proposals)
        
        return {
            'patterns_found': len(all_patterns),
            'patterns_suitable': len(suitable),
            'proposals_generated': len(proposals),
            'proposals': proposals
        }
    
    def _notify_user(self, proposals: List[Dict]):
        """Notify user about new proposals"""
        # Send Telegram notification
        try:
            self.telegram_notifier.notify_new_proposals(proposals)
        except Exception as e:
            print(f"⚠️  Telegram notification failed: {e}")
            # Fall back to console output
            message = f"🔧 **V8 Generated {len(proposals)} Optimization Proposal(s)**\n\n"
            
            for i, prop in enumerate(proposals, 1):
                code = prop['generated_code']
                pattern = prop['pattern']
                
                message += f"{i}. **{code['script_name']}** ({code['language']})\n"
                message += f"   • Confidence: {pattern.get('confidence', 0.0):.0%}\n"
                message += f"   • Savings: {code.get('estimated_savings', 'Unknown')}\n"
                message += f"   • Type: {pattern.get('type')}\n"
                message += f"   • Review: `/v8-review {prop['id']}`\n\n"
            
            message += "\nView all proposals: `/v8-proposals`"
            
            print("\n" + "="*60)
            print(message)
            print("="*60)


def main():
    """Run auto-optimizer"""
    import argparse
    
    parser = argparse.ArgumentParser(description='V8 Auto-Optimizer')
    parser.add_argument('--test', action='store_true', help='Test mode with sample patterns')
    parser.add_argument('--live', action='store_true', help='Live mode (scan V6 logs)')
    
    args = parser.parse_args()
    
    optimizer = AutoOptimizer()
    
    if args.test:
        # Test with sample patterns
        print("🧪 TEST MODE: Using sample patterns\n")
        
        sample_patterns = [
            {
                'type': 'command_retry',
                'command': 'npm',
                'confidence': 0.82,
                'count': 12,
                'parameters': {
                    'max_retries': 3,
                    'delay': 2
                }
            },
            {
                'type': 'dir_navigation',
                'command': 'make',
                'confidence': 0.78,
                'count': 8,
                'parameters': {
                    'directory': 'BUILD_DIR'
                }
            }
        ]
        
        # Override scan method for testing
        optimizer.scan_for_patterns = lambda: sample_patterns
        
    result = optimizer.run_cycle()
    
    print("\n" + "="*60)
    print("📊 CYCLE SUMMARY")
    print("="*60)
    print(f"Patterns found: {result['patterns_found']}")
    print(f"Suitable for generation: {result.get('patterns_suitable', 0)}")
    print(f"Proposals generated: {result['proposals_generated']}")
    
    if result['proposals_generated'] > 0:
        print("\n✅ New optimization proposals ready for review!")
    else:
        print("\n✅ No new proposals this cycle")


if __name__ == '__main__':
    main()
    
    def _get_location_patterns(self) -> List[Dict]:
        """Get patterns from location analyzer (NEW)"""
        if not self.location_analyzer:
            return []
        
        try:
            return self.location_analyzer.get_patterns()
        except Exception as e:
            print(f"⚠️  Location analyzer error: {e}")
            return []
    
    def _get_mobile_patterns(self) -> List[Dict]:
        """Get patterns from iOS mobile observer (NEW)"""
        if not self.ios_observer:
            return []
        
        try:
            return self.ios_observer.get_patterns()
        except Exception as e:
            print(f"⚠️  Mobile observer error: {e}")
            return []
    
    def _get_file_patterns(self) -> List[Dict]:
        """Get patterns from file operations analyzer (NEW)"""
        if not self.file_ops_analyzer:
            return []
        
        try:
            return self.file_ops_analyzer.get_patterns()
        except Exception as e:
            print(f"⚠️  File operations analyzer error: {e}")
            return []
    
    def _get_browser_patterns(self) -> List[Dict]:
        """Get patterns from browser history analyzer (NEW)"""
        if not self.browser_analyzer:
            return []
        
        try:
            return self.browser_analyzer.get_patterns()
        except Exception as e:
            print(f"⚠️  Browser history analyzer error: {e}")
            return []
    
    def _get_daemon_patterns(self) -> List[Dict]:
        """Get patterns from daemon monitor (NEW)"""
        if not self.daemon_analyzer:
            return []
        
        try:
            return self.daemon_analyzer.get_patterns()
        except Exception as e:
            print(f"⚠️  Daemon analyzer error: {e}")
            return []
    
    def _get_cos_patterns(self) -> List[Dict]:
        """Get patterns from Chief of Staff intelligence (NEW)"""
        if not self.cos_adapter or not self.cos_adapter.enabled:
            return []
        
        try:
            cos_data = self.cos_adapter.get_v8_compatible_patterns()
            
            # Flatten all patterns from all sources
            all_patterns = []
            for source in cos_data.get('sources', []):
                for pattern in source.get('patterns', []):
                    # Convert to V8 format
                    all_patterns.append({
                        'type': pattern['type'],
                        'confidence': pattern['confidence'],
                        'count': pattern.get('occurrence_count', 1),
                        'description': pattern.get('suggestion', ''),
                        'metadata': pattern,
                        'source': source['source']
                    })
            
            return all_patterns
        except Exception as e:
            print(f"⚠️  Chief of Staff adapter error: {e}")
            return []
