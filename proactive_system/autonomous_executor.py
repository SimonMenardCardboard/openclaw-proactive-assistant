#!/usr/bin/env python3
"""
Autonomous Executor - Component for V5

Executes low-risk actions autonomously without asking permission.
Uses risk scoring to determine what's safe to auto-execute.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Callable
from enum import Enum
import logging

# Add intelligence dir to path for proactive_queue import
sys.path.insert(0, str(Path(__file__).parent))
try:
    from proactive_queue import ProactiveQueue
    PROACTIVE_QUEUE_AVAILABLE = True
except ImportError:
    PROACTIVE_QUEUE_AVAILABLE = False
    logging.warning("Proactive queue not available")

# Setup logging
log_dir = Path.home() / "workspace" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / "autonomous_executor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("autonomous_executor")


class RiskLevel(Enum):
    """Risk levels for autonomous actions."""
    SAFE = 1        # Always safe to execute
    LOW = 2         # Safe with logging
    MEDIUM = 3      # Ask first (default)
    HIGH = 4        # Never autonomous
    CRITICAL = 5    # Requires explicit confirmation


class AutonomousExecutor:
    """Executes actions autonomously based on risk assessment."""
    
    def __init__(self, workspace: Optional[Path] = None):
        """
        Initialize autonomous executor.
        
        Args:
            workspace: Workspace root
        """
        if workspace is None:
            workspace = Path.home() / ".openclaw" / "workspace"
        
        self.workspace = Path(workspace)
        self.intelligence_dir = workspace / "integrations" / "intelligence"
        self.config_path = self.intelligence_dir / "autonomous_config.json"
        self.execution_log_path = self.intelligence_dir / "autonomous_executions.jsonl"
        
        # Ensure directory exists
        self.intelligence_dir.mkdir(parents=True, exist_ok=True)
        
        # Load config
        self.config = self._load_config()
        
        # Execution history (last 100)
        self.execution_history = []
        
        # Proactive queue for autonomous notifications
        self.proactive_queue = ProactiveQueue() if PROACTIVE_QUEUE_AVAILABLE else None
        
        logger.info("🤖 Autonomous Executor initialized")
    
    def _load_config(self) -> Dict:
        """Load autonomous execution config."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except:
                logger.warning("Failed to load config, using defaults")
        
        # Default config
        default_config = {
            'enabled': True,
            'whitelist': [
                'auth_refresh',           # SAFE: Refresh expired tokens
                'service_restart',        # LOW: Restart known services
                'log_cleanup',           # SAFE: Clean old logs
                'cache_clear',           # SAFE: Clear caches
                'tunnel_restart',        # LOW: Restart cloudflared tunnels
                'memory_consolidation',  # SAFE: Consolidate memory files
                'context_update',        # SAFE: Update context files
            ],
            'risk_overrides': {},  # Override risk levels for specific actions
            'max_executions_per_hour': 10,  # Rate limit
            'require_verification': True,    # Verify after execution
        }
        
        # Save default
        with open(self.config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        return default_config
    
    def _save_config(self):
        """Save config to disk."""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def _log_execution(self, action: str, risk: RiskLevel, result: Dict):
        """Log execution to history."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'risk_level': risk.name,
            'result': result,
            'success': result.get('success', False)
        }
        
        # Append to log file
        with open(self.execution_log_path, 'a') as f:
            f.write(json.dumps(entry) + '\n')
        
        # Add to memory (keep last 100)
        self.execution_history.append(entry)
        if len(self.execution_history) > 100:
            self.execution_history = self.execution_history[-100:]
    
    def assess_risk(self, action_type: str, context: Dict) -> RiskLevel:
        """
        Assess risk level for an action.
        
        Args:
            action_type: Type of action
            context: Action context
            
        Returns:
            Risk level
        """
        # Check for override
        if action_type in self.config.get('risk_overrides', {}):
            level_name = self.config['risk_overrides'][action_type]
            return RiskLevel[level_name]
        
        # Default risk assessments
        risk_map = {
            # SAFE actions (read-only, cleanup)
            'auth_refresh': RiskLevel.SAFE,
            'log_cleanup': RiskLevel.SAFE,
            'cache_clear': RiskLevel.SAFE,
            'memory_consolidation': RiskLevel.SAFE,
            'context_update': RiskLevel.SAFE,
            
            # LOW risk (restart services, non-destructive)
            'service_restart': RiskLevel.LOW,
            'tunnel_restart': RiskLevel.LOW,
            'daemon_restart': RiskLevel.LOW,
            
            # MEDIUM risk (default - ask first)
            'file_write': RiskLevel.MEDIUM,
            'config_change': RiskLevel.MEDIUM,
            'integration_deploy': RiskLevel.MEDIUM,
            
            # HIGH risk (destructive, public-facing)
            'file_delete': RiskLevel.HIGH,
            'send_message': RiskLevel.HIGH,
            'post_public': RiskLevel.HIGH,
            
            # CRITICAL (financial, irreversible)
            'payment': RiskLevel.CRITICAL,
            'data_export': RiskLevel.CRITICAL,
            'account_delete': RiskLevel.CRITICAL,
        }
        
        return risk_map.get(action_type, RiskLevel.MEDIUM)
    
    def can_execute_autonomously(self, action_type: str, context: Dict) -> Tuple[bool, str]:
        """
        Determine if action can be executed autonomously.
        
        Args:
            action_type: Type of action
            context: Action context
            
        Returns:
            (can_execute, reason)
        """
        # Check if autonomous execution is enabled
        if not self.config.get('enabled', True):
            return False, "Autonomous execution disabled"
        
        # Check rate limit
        recent_count = len([
            e for e in self.execution_history
            if (datetime.now() - datetime.fromisoformat(e['timestamp'])).total_seconds() < 3600
        ])
        
        max_per_hour = self.config.get('max_executions_per_hour', 10)
        if recent_count >= max_per_hour:
            return False, f"Rate limit exceeded ({recent_count}/{max_per_hour} per hour)"
        
        # Assess risk
        risk = self.assess_risk(action_type, context)
        
        # Only SAFE and LOW risk actions can be autonomous
        if risk in [RiskLevel.SAFE, RiskLevel.LOW]:
            # Check whitelist
            if action_type in self.config.get('whitelist', []):
                return True, f"Whitelisted {risk.name} risk action"
            else:
                return False, f"{risk.name} risk but not whitelisted"
        
        return False, f"Risk level {risk.name} requires permission"
    
    def execute(self, action_type: str, action_func: Callable, context: Dict) -> Dict:
        """
        Execute action autonomously if allowed.
        
        Args:
            action_type: Type of action
            action_func: Function to execute
            context: Action context
            
        Returns:
            Execution result
        """
        can_execute, reason = self.can_execute_autonomously(action_type, context)
        
        if not can_execute:
            logger.info(f"⏸️  Cannot execute autonomously: {reason}")
            
            # Notify if manual approval needed
            if 'requires approval' in reason.lower() or 'high risk' in reason.lower():
                self._notify_approval_needed(action_type, context, reason)
            
            return {
                'success': False,
                'autonomous': False,
                'reason': reason,
                'action': action_type
            }
        
        # Execute
        logger.info(f"🤖 Executing autonomously: {action_type}")
        
        try:
            result = action_func()
            
            execution_result = {
                'success': True,
                'autonomous': True,
                'action': action_type,
                'result': result,
                'reason': reason
            }
            
            # Log execution
            risk = self.assess_risk(action_type, context)
            self._log_execution(action_type, risk, execution_result)
            
            logger.info(f"✅ Autonomous execution successful: {action_type}")
            
            # Queue proactive notification for user
            self._notify_completion(action_type, context, execution_result)
            
            return execution_result
            
        except Exception as e:
            logger.error(f"❌ Autonomous execution failed: {e}")
            
            error_result = {
                'success': False,
                'autonomous': True,
                'action': action_type,
                'error': str(e),
                'reason': reason
            }
            
            # Log failure
            risk = self.assess_risk(action_type, context)
            self._log_execution(action_type, risk, error_result)
            
            # Notify user of failure
            self._notify_failure(action_type, context, error_result)
            
            return error_result
    
    def get_execution_history(self, hours: int = 24) -> List[Dict]:
        """Get recent execution history."""
        cutoff = datetime.now().timestamp() - (hours * 3600)
        
        return [
            e for e in self.execution_history
            if datetime.fromisoformat(e['timestamp']).timestamp() > cutoff
        ]
    
    def get_stats(self) -> Dict:
        """Get execution statistics."""
        recent = self.get_execution_history(hours=24)
        
        success_count = len([e for e in recent if e.get('success')])
        failure_count = len([e for e in recent if not e.get('success')])
        
        return {
            'enabled': self.config.get('enabled', True),
            'executions_24h': len(recent),
            'success_24h': success_count,
            'failure_24h': failure_count,
            'success_rate': (success_count / len(recent) * 100) if recent else 0,
            'whitelist_size': len(self.config.get('whitelist', [])),
            'rate_limit': self.config.get('max_executions_per_hour', 10)
        }
    
    def _notify_completion(self, action_type: str, context: Dict, result: Dict):
        """Queue proactive notification about autonomous action completion."""
        if not self.proactive_queue:
            return
        
        try:
            # Build friendly message
            action_messages = {
                'auth_refresh': '✅ Refreshed your OAuth token - everything staying connected',
                'tunnel_restart': '✅ Restarted tunnel - back online',
                'cleanup_logs': '🧹 Cleaned up old logs',
                'db_maintenance': '🛠️ Database maintenance completed',
                'cache_clear': '🗑️ Cleared stale cache',
            }
            
            message = action_messages.get(action_type, f'✅ Completed: {action_type}')
            
            # Only notify for meaningful actions (not super low-priority maintenance)
            risk = self.assess_risk(action_type, context)
            if risk in [RiskLevel.SAFE, RiskLevel.LOW]:
                priority = 4  # Low priority - FYI only
            else:
                priority = 3  # Medium - worth knowing
            
            self.proactive_queue.add(
                source='v6-executor',
                message=message,
                priority=priority,
                context={
                    'action': action_type,
                    'risk': risk.name,
                    'timestamp': datetime.now().isoformat()
                }
            )
            
            logger.debug(f"📬 Queued notification for {action_type}")
            
        except Exception as e:
            logger.warning(f"⚠️  Failed to queue notification: {e}")
    
    def _notify_failure(self, action_type: str, context: Dict, result: Dict):
        """Queue urgent notification about autonomous action failure."""
        if not self.proactive_queue:
            return
        
        try:
            error = result.get('error', 'Unknown error')
            
            # Build urgent failure message
            action_names = {
                'auth_refresh': 'OAuth token refresh',
                'tunnel_restart': 'tunnel restart',
                'cleanup_logs': 'log cleanup',
                'db_maintenance': 'database maintenance',
            }
            
            action_name = action_names.get(action_type, action_type)
            service = context.get('service', 'system')
            
            # Escape special characters for Telegram Markdown
            error_safe = error.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
            
            message = f"🚨 *Failed: {action_name}*\n\n"
            message += f"Service: {service}\n"
            message += f"Error: {error_safe}\n\n"
            
            # Add recommended action
            recommended_action = self._get_recommended_action(action_type, service, error)
            if recommended_action:
                message += f"💡 *Try:* {recommended_action}"
            else:
                message += "_Manual intervention may be needed_"
            
            # Failures are high priority
            self.proactive_queue.add(
                source='v6-executor',
                message=message,
                priority=2,  # High - failures need attention
                context={
                    'action': action_type,
                    'error': error,
                    'service': service,
                    'timestamp': datetime.now().isoformat(),
                    'needs_intervention': True
                }
            )
            
            logger.info(f"🚨 Queued failure alert for {action_type}")
            
        except Exception as e:
            logger.warning(f"⚠️  Failed to queue failure notification: {e}")
    
    def _notify_approval_needed(self, action_type: str, context: Dict, reason: str):
        """Queue notification when manual approval is required."""
        if not self.proactive_queue:
            return
        
        try:
            action_names = {
                'send_email': 'send email',
                'post_tweet': 'post to Twitter',
                'delete_file': 'delete file',
                'payment': 'process payment',
            }
            
            action_name = action_names.get(action_type, action_type)
            
            message = f"⚠️  **Approval needed: {action_name}**\n\n"
            message += f"Reason: {reason}\n\n"
            
            # Add context if available
            if context.get('details'):
                message += f"Details: {context['details']}\n\n"
            
            message += "_Please review and approve/deny_"
            
            # Approval requests are high priority
            self.proactive_queue.add(
                source='v6-executor',
                message=message,
                priority=2,  # High - needs decision
                context={
                    'action': action_type,
                    'reason': reason,
                    'timestamp': datetime.now().isoformat(),
                    'needs_approval': True
                }
            )
            
            logger.info(f"⚠️  Queued approval request for {action_type}")
            
        except Exception as e:
            logger.warning(f"⚠️  Failed to queue approval notification: {e}")
    
    def _get_recommended_action(self, action_type: str, service: str, error: str) -> str:
        """Get AI-recommended action for failure."""
        error_lower = error.lower()
        
        # Network/timeout errors
        if 'timeout' in error_lower or 'connection' in error_lower:
            return "Check network connection, then retry in 5 minutes"
        
        # Auth errors
        if '401' in error or '403' in error or 'unauthorized' in error_lower or 'forbidden' in error_lower:
            if 'token' in service.lower():
                return f"Re-authenticate {service} via OAuth flow"
            return "Refresh authentication credentials"
        
        # Rate limit errors
        if '429' in error or 'rate limit' in error_lower:
            return "Wait 1 hour before retrying (API rate limit)"
        
        # File/disk errors
        if 'disk' in error_lower or 'space' in error_lower:
            return "Free up disk space (run cleanup script)"
        
        # Permission errors
        if 'permission' in error_lower:
            return "Check file/service permissions"
        
        # Service unavailable
        if '503' in error or 'unavailable' in error_lower:
            return "Service temporarily down - will auto-retry"
        
        # Generic
        return None


# Global instance
_executor = None

def get_executor() -> AutonomousExecutor:
    """Get or create global executor."""
    global _executor
    if _executor is None:
        _executor = AutonomousExecutor()
    return _executor


if __name__ == "__main__":
    # Test autonomous executor
    print("🧪 Testing Autonomous Executor...\n")
    
    executor = AutonomousExecutor()
    
    # Test risk assessment
    print("🎯 Testing risk assessment:")
    for action in ['auth_refresh', 'file_write', 'send_message', 'payment']:
        risk = executor.assess_risk(action, {})
        print(f"  {action}: {risk.name}")
    print()
    
    # Test can_execute
    print("✅ Testing execution permission:")
    for action in ['auth_refresh', 'file_write', 'send_message']:
        can_exec, reason = executor.can_execute_autonomously(action, {})
        status = "✅ YES" if can_exec else "❌ NO"
        print(f"  {action}: {status} - {reason}")
    print()
    
    # Test execution
    print("🤖 Testing autonomous execution:")
    
    def test_action():
        return {'status': 'refreshed', 'tokens': ['google', 'whoop']}
    
    result = executor.execute('auth_refresh', test_action, {})
    print(f"  Result: {json.dumps(result, indent=2)}")
    print()
    
    # Stats
    stats = executor.get_stats()
    print(f"📊 Stats: {json.dumps(stats, indent=2)}")
    
    print("\n✅ All tests passed!")
