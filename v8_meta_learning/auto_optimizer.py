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
from approval_workflow import ApprovalWorkflow

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
        self.approval_workflow = ApprovalWorkflow()
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
            
            # Convert similar_subjects patterns
            for pattern in results.get('similar_subjects', []):
                patterns.append({
                    'type': 'email_template',
                    'subject_pattern': pattern.get('template'),
                    'accounts': pattern.get('accounts', []),
                    'count': pattern.get('count', 0),
                    'confidence': pattern.get('confidence', 0.85),
                    'description': pattern.get('description', ''),
                    'source': 'email'
                })
            
            # Convert frequent_recipients patterns
            for pattern in results.get('frequent_recipients', []):
                patterns.append({
                    'type': 'email_shortcut',
                    'recipient': pattern.get('recipient'),
                    'count': pattern.get('count', 0),
                    'confidence': pattern.get('confidence', 0.80),
                    'description': pattern.get('description', ''),
                    'source': 'email'
                })
            
            # Convert time_patterns
            for pattern in results.get('time_patterns', []):
                patterns.append({
                    'type': 'email_schedule',
                    'pattern': pattern.get('pattern'),
                    'time': pattern.get('time'),
                    'count': pattern.get('count', 0),
                    'confidence': pattern.get('confidence', 0.75),
                    'description': pattern.get('description', ''),
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
            
            # Convert recurring titles
            for pattern in results.get('recurring_titles', []):
                patterns.append({
                    'type': 'recurring_meeting',
                    'title': pattern.get('title'),
                    'count': pattern.get('count', 0),
                    'confidence': pattern.get('confidence', 0.85),
                    'description': pattern.get('description', ''),
                    'source': 'calendar'
                })
            
            # Convert time blocks
            for pattern in results.get('time_blocks', []):
                patterns.append({
                    'type': 'time_block',
                    'weekday': pattern.get('weekday'),
                    'hour': pattern.get('hour'),
                    'count': pattern.get('count', 0),
                    'confidence': pattern.get('confidence', 0.85),
                    'description': pattern.get('description', ''),
                    'source': 'calendar'
                })
            
            # Convert meeting types
            for pattern in results.get('meeting_types', []):
                patterns.append({
                    'type': 'meeting_category',
                    'category': pattern.get('category'),
                    'count': pattern.get('count', 0),
                    'confidence': pattern.get('confidence', 0.85),
                    'description': pattern.get('description', ''),
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
        
        # Filter suitable patterns for code generation
        suitable = self.filter_patterns(all_patterns)
        print(f"   {len(suitable)} suitable for code generation")
        
        # Queue user-friendly insights for ALL high-confidence patterns (not just code-generation-suitable)
        insights_to_queue = [p for p in all_patterns if p.get('confidence', 0) >= 0.75 and p.get('count', 0) >= 3]
        if insights_to_queue:
            self._queue_pattern_insights(insights_to_queue)
        
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
    
    def _queue_pattern_insights(self, patterns: List[Dict]):
        """Queue user-friendly insights about detected patterns to proactive_queue"""
        import sqlite3
        import json
        
        proactive_queue_db = Path.home() / '.openclaw/workspace/integrations/intelligence/proactive_queue.db'
        approvals_db = Path.home() / '.openclaw/workspace/integrations/intelligence/v8_meta_learning/approvals.db'
        
        # Get already deployed/approved patterns
        deployed_patterns = set()
        try:
            conn_approvals = sqlite3.connect(approvals_db)
            cursor_approvals = conn_approvals.cursor()
            cursor_approvals.execute("SELECT script_name FROM proposals WHERE status IN ('deployed', 'approved')")
            deployed_patterns = {row[0] for row in cursor_approvals.fetchall()}
            conn_approvals.close()
        except Exception as e:
            print(f"Warning: Could not check deployed patterns: {e}")
        
        try:
            conn = sqlite3.connect(proactive_queue_db)
            cursor = conn.cursor()
            
            # Ensure columns exist
            cursor.execute("PRAGMA table_info(proactive_queue)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'has_actions' not in columns:
                cursor.execute("ALTER TABLE proactive_queue ADD COLUMN has_actions BOOLEAN DEFAULT 0")
            if 'action_approved' not in columns:
                cursor.execute("ALTER TABLE proactive_queue ADD COLUMN action_approved BOOLEAN DEFAULT NULL")
            if 'pattern_key' not in columns:
                cursor.execute("ALTER TABLE proactive_queue ADD COLUMN pattern_key TEXT")
            
            # Get patterns delivered OR queued in last 24h (to enforce once-per-day limit)
            cursor.execute("""
                SELECT pattern_key, action_approved 
                FROM proactive_queue 
                WHERE pattern_key IS NOT NULL 
                  AND (delivered_at > datetime('now', '-1 day') OR 
                       (delivered_at IS NULL AND created_at > datetime('now', '-1 day')))
            """)
            recent_patterns = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Get patterns that were approved/denied (never resend)
            cursor.execute("""
                SELECT pattern_key 
                FROM proactive_queue 
                WHERE pattern_key IS NOT NULL 
                  AND action_approved IS NOT NULL
            """)
            decided_patterns = {row[0] for row in cursor.fetchall()}
            
            print(f"   {len(recent_patterns)} patterns delivered in last 24h")
            print(f"   {len(decided_patterns)} patterns already approved/denied")
            
            queued_count = 0
            skipped_recent = 0
            skipped_decided = 0
            skipped_deployed = 0
            
            for pattern in patterns:
                # Generate unique key for this pattern (for deduplication)
                pattern_type = pattern.get('type', 'unknown')
                pattern_details = pattern.get('title') or pattern.get('command') or pattern.get('subject_pattern') or pattern.get('recipient') or str(pattern.get('count', 0))
                pattern_key = f"{pattern_type}:{pattern_details}"
                
                # Skip if user already approved/denied this pattern
                if pattern_key in decided_patterns:
                    skipped_decided += 1
                    continue
                
                # Skip if delivered in last 24h (once-per-day limit)
                if pattern_key in recent_patterns:
                    skipped_recent += 1
                    continue
                
                # Skip if already deployed/approved
                pattern_name = self._get_pattern_script_name(pattern)
                if pattern_name in deployed_patterns:
                    skipped_deployed += 1
                    continue
                
                # Generate human-readable message based on pattern type
                message = self._generate_pattern_message(pattern)
                if not message:
                    continue
                
                # Determine priority based on confidence and frequency
                confidence = pattern.get('confidence', 0.0)
                count = pattern.get('count', 0)
                
                if confidence >= 0.9 and count >= 10:
                    priority = 1  # High
                elif confidence >= 0.7 and count >= 5:
                    priority = 2  # Medium
                else:
                    priority = 3  # Low
                
                # Store full pattern in context for later optimization generation
                context = {
                    'pattern': pattern,
                    'type': pattern.get('type'),
                    'confidence': confidence,
                    'count': count
                }
                
                # Insert into queue with action support and pattern_key for deduplication
                cursor.execute("""
                    INSERT INTO proactive_queue 
                    (source, priority, message, context, message_type, user_facing, has_actions, pattern_key)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f"v8_pattern_{pattern.get('type', 'unknown')}",
                    priority,
                    message,
                    json.dumps(context),
                    'insight',
                    1,  # user_facing
                    1,  # has_actions (user can approve/decline)
                    pattern_key  # for deduplication
                ))
                queued_count += 1
            
            conn.commit()
            conn.close()
            
            if queued_count > 0 or skipped_recent > 0 or skipped_decided > 0:
                print(f"📬 Queued {queued_count} new pattern(s)")
                if skipped_recent > 0:
                    print(f"   ⏭️  Skipped {skipped_recent} (delivered in last 24h)")
                if skipped_decided > 0:
                    print(f"   ✅ Skipped {skipped_decided} (already approved/denied)")
                if skipped_deployed > 0:
                    print(f"   🚀 Skipped {skipped_deployed} (already deployed)")
        
        except Exception as e:
            print(f"⚠️  Failed to queue insights: {e}")
            import traceback
            traceback.print_exc()
    
    def _get_pattern_script_name(self, pattern: Dict) -> str:
        """Generate script name from pattern (matching code_generator logic)"""
        pattern_type = pattern.get('type', '')
        command = pattern.get('command', '')
        
        if pattern_type == 'command_retry':
            command_clean = command.replace(' ', '_').replace('/', '_')
            return f"{command_clean}_retry"
        elif pattern_type == 'multi_command':
            workflow = pattern.get('workflow_name', 'workflow')
            return f"{workflow}_multi"
        elif pattern_type in ['recurring_meeting', 'time_block', 'meeting_category']:
            # Calendar patterns don't generate code/scripts, always pass duplicate check
            title = pattern.get('title', pattern.get('weekday', pattern.get('category', 'calendar')))
            title_clean = title.replace(' ', '_').replace('/', '_').lower()[:30]
            return f"{pattern_type}_{title_clean}"
        else:
            command_clean = command.replace(' ', '_').replace('/', '_') if command else 'unknown'
            return f"{pattern_type}_{command_clean}"
    
    def _generate_pattern_message(self, pattern: Dict) -> str:
        """Generate human-readable message for a pattern"""
        pattern_type = pattern.get('type', '')
        count = pattern.get('count', 0)
        confidence = pattern.get('confidence', 0.0)
        command = pattern.get('command', 'unknown')
        
        if pattern_type == 'command_retry':
            # Non-technical explanation for retry wrapper
            return f"""💡 **I noticed a pattern**

You use `{command}` often ({count} times recently).

**The problem:**
Sometimes `{command}` fails due to temporary issues like:
• Slow internet connection
• Server being busy
• Brief outages

When this happens, you have to run it again manually.

**What I can do:**
Make `{command}` automatically retry when it fails, so you don't have to. It will:
• Try up to 3 times before giving up
• Wait 1 second between attempts
• Work exactly like normal when successful

**What changes:**
Nothing! It will look and feel the same. You'll just see fewer errors.

**Example:**
Before: `{command}` fails → You rerun it manually
After: `{command}` fails → Retries automatically → Usually succeeds

Want me to set this up?"""
        
        elif pattern_type == 'repeated_command':
            return f"""💡 **I noticed a pattern**

You run `{command}` frequently ({count} times recently).

Want me to create a shortcut to save you time?"""
        
        elif pattern_type == 'email_template':
            subject = pattern.get('subject_pattern', 'unknown')
            return f"""📧 **Email pattern detected**

You send similar emails with subject: "{subject}" ({count} times recently).

Would you like me to create a template to save time writing these?"""
        
        elif pattern_type == 'email_shortcut':
            recipient = pattern.get('recipient', 'unknown')
            return f"""📧 **Frequent recipient detected**

You email {recipient} often ({count} times recently).

**What I can do:**
• Create a quick-compose shortcut
• Auto-suggest this recipient
• Pre-fill common details

Want me to set this up?"""
        
        elif pattern_type == 'email_schedule':
            time = pattern.get('time', 'regularly')
            return f"""📧 **Email timing pattern detected**

You send certain emails {time} ({count} times).

**What I can do:**
• Set up scheduled reminders
• Auto-draft emails at that time
• Track if you miss the pattern

Want me to automate this?"""
        
        elif pattern_type == 'workflow_sequence':
            commands = pattern.get('commands', [])
            cmd_str = ' → '.join(commands[:3])
            if len(commands) > 3:
                cmd_str += f'... ({len(commands)} steps total)'
            
            return f"""⚙️ **Workflow detected**

You often do these steps in order:
{cmd_str}

I can combine them into a single button to save time.

Want me to set this up?"""
        
        elif pattern_type == 'multi_command':
            commands = pattern.get('commands', [])
            cmd_preview = ' → '.join(commands[:2])
            if len(commands) > 2:
                cmd_preview += f' → ... ({len(commands)} total steps)'
            
            return f"""⚙️ **I noticed a pattern**

You often do these steps together:
{cmd_preview}

**What I can do:**
Combine them into one action, so instead of doing {len(commands)} separate steps, you click once.

**Time saved:** About {len(commands) * 10} seconds each time.

Want me to set this up?"""
        
        elif pattern_type == 'calendar_conflict':
            return f"""📅 **Calendar insight**

I found {count} scheduling conflicts in your calendar.

Want help rearranging meetings to free up time?"""
        
        elif pattern_type == 'recurring_meeting':
            title = pattern.get('title', 'Unknown meeting')
            return f"""📅 **Recurring meeting detected**

"{title}" happens {count} times (repeating pattern).

**What I can do:**
• Auto-prep meeting notes before each occurrence
• Send reminders with context
• Track action items across meetings

Want me to automate this?"""
        
        elif pattern_type == 'time_block':
            weekday = pattern.get('weekday', 'Unknown')
            hour = pattern.get('hour', 0)
            return f"""📅 **Time pattern detected**

You have meetings every {weekday} at {hour}:00 ({count} occurrences).

**What I can do:**
• Block prep time before these meetings
• Suggest focus time in open slots
• Alert if someone tries to book over it

Want me to protect this time?"""
        
        elif pattern_type == 'meeting_category':
            category = pattern.get('category', 'team')
            return f"""📅 **Meeting pattern detected**

You have {count} {category} meetings regularly.

**What I can do:**
• Create standard agendas for {category} meetings
• Auto-send prep materials beforehand
• Track outcomes and follow-ups

Want me to streamline these?"""
        
        else:
            # Generic message for unknown types
            description = pattern.get('description', pattern_type)
            if count >= 5:
                return f"""💡 **Pattern detected**

{description} ({count} times recently, {confidence:.0%} confidence)

Interested in optimizing this?"""
        
        return None
    def _notify_user(self, proposals: List[Dict]):
        """Notify user about new proposals"""
        # Proposals are technical (code generation)
        # User insights are sent via _queue_pattern_insights instead
        pass
    
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
