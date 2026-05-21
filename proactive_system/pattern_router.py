#!/usr/bin/env python3
"""
Pattern Router - Route patterns to appropriate approval flows

For Transmogrifier product VMs:
- Shell command optimizations → Hobbes Control (automated/centralized approval)
- All other patterns → End user (manual approval via app)

For Hobbes Prime (dev/test):
- All patterns → User (Simon via Telegram)
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Optional

# Check if running on Transmogrifier VM or Hobbes Prime
IS_PRODUCTION_VM = os.getenv('TRANSMOGRIFIER_VM', 'false').lower() == 'true'
IS_HOBBES_PRIME = os.getenv('HOBBES_PRIME', 'false').lower() == 'true'

# Import routing targets
sys.path.insert(0, str(Path(__file__).parent))
from proactive_queue import ProactiveQueue

# Hobbes Control client (only for production VMs)
if IS_PRODUCTION_VM:
    sys.path.insert(0, str(Path(__file__).parent / "v8.5_pattern_learning"))
    try:
        from hobbes_control_client import HobbesControlClient
        HOBBES_CONTROL_AVAILABLE = True
    except ImportError:
        HOBBES_CONTROL_AVAILABLE = False
        logging.warning("Hobbes Control client not available on production VM")
else:
    HOBBES_CONTROL_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Shell command pattern types (route to Hobbes Control)
SHELL_PATTERN_TYPES = {
    'command_retry',
    'dir_navigation',
    'multi_command',
    'cache_operation',
    'git_workflow',
    'npm_workflow',
    'docker_workflow',
    'system_admin',
    'development_workflow',
    'file_management',
    'shell_automation'
}


class PatternRouter:
    """Route patterns to appropriate approval flows."""
    
    def __init__(self, user_id: str = 'default'):
        """
        Initialize pattern router.
        
        Args:
            user_id: User identifier for control plane routing
        """
        self.user_id = user_id
        self.user_queue = ProactiveQueue()
        
        # Hobbes Control client (production VMs only)
        if IS_PRODUCTION_VM and HOBBES_CONTROL_AVAILABLE:
            self.control_client = HobbesControlClient(user_id=user_id)
            logger.info(f"Pattern router initialized (VM mode, user={user_id})")
        else:
            self.control_client = None
            logger.info(f"Pattern router initialized (Prime mode, all patterns → user)")
    
    def route_pattern(self, pattern: Dict, generated_code: Optional[Dict] = None) -> Dict:
        """
        Route pattern to appropriate approval flow.
        
        Args:
            pattern: Detected pattern
            generated_code: Optional generated code/automation
        
        Returns:
            {
                'routed_to': 'user' or 'control_plane',
                'queue_id': int (if queued for user),
                'control_id': str (if sent to control plane),
                'message': str (what was sent)
            }
        """
        pattern_type = pattern.get('type')
        
        # On Hobbes Prime: everything goes to user (Simon)
        if IS_HOBBES_PRIME or not IS_PRODUCTION_VM:
            return self._route_to_user(pattern, generated_code)
        
        # On production VM: shell patterns → control, others → user
        if pattern_type in SHELL_PATTERN_TYPES:
            return self._route_to_control_plane(pattern, generated_code)
        else:
            return self._route_to_user(pattern, generated_code)
    
    def _route_to_user(self, pattern: Dict, generated_code: Optional[Dict]) -> Dict:
        """
        Route pattern to end user for approval.
        
        Creates user-facing message in proactive_queue.
        """
        from non_technical_approval import format_approval_message
        
        # Format non-technical message
        message = format_approval_message(pattern, generated_code or {})
        
        # Add to user's proactive queue
        priority = self._calculate_priority(pattern)
        queue_id = self.user_queue.add(
            source='v8-pattern-router',
            message=message,
            priority=priority,
            context={
                'pattern': pattern,
                'generated_code': generated_code,
                'approval_flow': 'user'
            }
        )
        
        logger.info(f"Routed {pattern.get('type')} to user queue (ID: {queue_id})")
        
        return {
            'routed_to': 'user',
            'queue_id': queue_id,
            'control_id': None,
            'message': message
        }
    
    def _route_to_control_plane(self, pattern: Dict, generated_code: Optional[Dict]) -> Dict:
        """
        Route shell pattern to Hobbes Control for automated approval.
        
        Control plane will:
        1. Validate security (no sudo, no network access, etc.)
        2. Sandbox test on control VM
        3. Auto-approve if safe + beneficial
        4. Deploy to user VM if approved
        5. Notify user after deployment (not before)
        """
        if not self.control_client:
            logger.warning("Hobbes Control not available, falling back to user approval")
            return self._route_to_user(pattern, generated_code)
        
        try:
            # Submit to control plane
            control_id = self.control_client.submit_shell_optimization(
                pattern=pattern,
                generated_code=generated_code,
                user_id=self.user_id
            )
            
            logger.info(f"Routed {pattern.get('type')} to Hobbes Control (ID: {control_id})")
            
            # Control plane handles approval + deployment
            # User will be notified AFTER successful deployment
            return {
                'routed_to': 'control_plane',
                'queue_id': None,
                'control_id': control_id,
                'message': f"Shell optimization submitted to control plane: {control_id}"
            }
        
        except Exception as e:
            logger.error(f"Failed to submit to control plane: {e}", exc_info=True)
            # Fallback to user approval
            return self._route_to_user(pattern, generated_code)
    
    def _calculate_priority(self, pattern: Dict) -> int:
        """
        Calculate delivery priority for user-facing patterns.
        
        Returns:
            1 = urgent (show immediately)
            2 = high (show within hours)
            3 = medium (show within day)
            4 = low (batch with other updates)
        """
        confidence = pattern.get('confidence', 0.0)
        count = pattern.get('count', pattern.get('occurrences', 0))
        
        # High confidence + frequent usage → higher priority
        if confidence > 0.9 and count > 50:
            return 2
        elif confidence > 0.8 and count > 20:
            return 2
        elif confidence > 0.7:
            return 3
        else:
            return 3
    
    def get_routing_stats(self) -> Dict:
        """
        Get routing statistics.
        
        Returns:
            {
                'mode': 'vm' or 'prime',
                'total_routed': int,
                'to_user': int,
                'to_control': int,
                'control_available': bool
            }
        """
        # TODO: Track stats in database
        return {
            'mode': 'vm' if IS_PRODUCTION_VM else 'prime',
            'control_available': HOBBES_CONTROL_AVAILABLE and self.control_client is not None
        }


# Convenience function for existing code
def route_pattern(pattern: Dict, generated_code: Optional[Dict] = None, user_id: str = 'default') -> Dict:
    """
    Route a pattern to appropriate approval flow.
    
    Usage:
        result = route_pattern(pattern, generated_code)
        if result['routed_to'] == 'user':
            print(f"Queued for user approval: {result['queue_id']}")
        else:
            print(f"Sent to control plane: {result['control_id']}")
    """
    router = PatternRouter(user_id=user_id)
    return router.route_pattern(pattern, generated_code)


if __name__ == '__main__':
    # Test routing
    
    # Shell pattern (should go to control on VM, user on Prime)
    shell_pattern = {
        'type': 'command_retry',
        'command': 'git',
        'count': 15,
        'confidence': 0.85
    }
    
    # Non-shell pattern (should always go to user)
    calendar_pattern = {
        'type': 'meeting_prep',
        'meeting_type': 'standup',
        'count': 52,
        'confidence': 0.92
    }
    
    router = PatternRouter()
    
    print("Shell pattern routing:")
    result1 = router.route_pattern(shell_pattern)
    print(f"  → {result1['routed_to']}")
    
    print("\nCalendar pattern routing:")
    result2 = router.route_pattern(calendar_pattern)
    print(f"  → {result2['routed_to']}")
    
    print("\nStats:")
    print(router.get_routing_stats())
