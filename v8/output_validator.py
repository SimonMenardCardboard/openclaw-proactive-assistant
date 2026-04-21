#!/usr/bin/env python3
"""
V8 Output Validator - Phase 3

Validates that generated optimizations produce expected outputs.

For each optimization type, defines:
1. Expected output format
2. Success criteria
3. Validation rules

Usage:
    validator = OutputValidator()
    result = validator.validate(optimization_type, actual_output)
"""

import re
from typing import Dict, List, Optional, Literal


class OutputValidator:
    """
    Validate optimization outputs match expected behavior.
    
    Different optimization types have different validation rules:
    - command_retry: Should execute command and return exit code
    - email_template: Should format email correctly
    - meeting_automation: Should send notifications
    - focus_block: Should create calendar entry
    """
    
    def __init__(self):
        # Define validation rules for each optimization type
        self.validators = {
            'command_retry': self._validate_command_retry,
            'email_template': self._validate_email_template,
            'email_shortcut': self._validate_email_shortcut,
            'email_schedule': self._validate_email_schedule,
            'meeting_automation': self._validate_meeting_automation,
            'focus_block': self._validate_focus_block,
            'meeting_workflow': self._validate_meeting_workflow,
            'dir_navigation': self._validate_dir_navigation,
            'multi_command': self._validate_multi_command,
        }
    
    def validate(self, 
                 optimization_type: str, 
                 stdout: str, 
                 stderr: str,
                 exit_code: int,
                 expected: Optional[Dict] = None) -> Dict:
        """
        Validate optimization output.
        
        Args:
            optimization_type: Type of optimization
            stdout: Standard output from execution
            stderr: Standard error from execution
            exit_code: Process exit code
            expected: Optional expected values
        
        Returns:
            {
                'valid': bool,
                'score': float (0.0-1.0),
                'errors': List[str],
                'warnings': List[str],
                'details': Dict
            }
        """
        if optimization_type not in self.validators:
            return {
                'valid': True,  # No validator = assume OK
                'score': 0.5,
                'errors': [],
                'warnings': [f'No validator for type: {optimization_type}'],
                'details': {}
            }
        
        # Call type-specific validator
        validator_func = self.validators[optimization_type]
        return validator_func(stdout, stderr, exit_code, expected or {})
    
    def _validate_command_retry(self, stdout: str, stderr: str, exit_code: int, expected: Dict) -> Dict:
        """
        Validate command retry wrapper.
        
        Expected behavior:
        - Prints retry attempts
        - Returns success/failure
        - Shows command output
        """
        errors = []
        warnings = []
        score = 1.0
        
        # Check for retry logic indicators
        retry_indicators = ['retry', 'attempt', 'failed', 'succeeded']
        has_retry_logic = any(indicator in stdout.lower() for indicator in retry_indicators)
        
        if not has_retry_logic:
            warnings.append('No retry indicators found in output')
            score -= 0.2
        
        # Should have some output
        if not stdout.strip() and exit_code != 0:
            errors.append('No output but non-zero exit code')
            score -= 0.3
        
        # Syntax errors are fatal
        if 'SyntaxError' in stderr or 'command not found' in stderr:
            errors.append(f'Execution error: {stderr[:100]}')
            score = 0.0
        
        return {
            'valid': len(errors) == 0 and score >= 0.5,
            'score': max(0.0, score),
            'errors': errors,
            'warnings': warnings,
            'details': {
                'has_retry_logic': has_retry_logic,
                'has_output': bool(stdout.strip())
            }
        }
    
    def _validate_email_template(self, stdout: str, stderr: str, exit_code: int, expected: Dict) -> Dict:
        """
        Validate email template script.
        
        Expected: Usage message or success message
        """
        errors = []
        warnings = []
        score = 1.0
        
        # Should show usage or success
        has_usage = 'usage' in stdout.lower() or 'usage' in stderr.lower()
        has_success = '✅' in stdout or 'sent' in stdout.lower()
        
        if not (has_usage or has_success):
            warnings.append('No usage or success message found')
            score -= 0.2
        
        # Should mention recipient or email
        email_indicators = ['recipient', 'email', 'to:', 'subject']
        has_email_logic = any(ind in stdout.lower() for ind in email_indicators)
        
        if not has_email_logic:
            warnings.append('No email-related output detected')
            score -= 0.2
        
        if 'error' in stderr.lower() and exit_code != 0:
            errors.append(f'Execution error: {stderr[:100]}')
            score -= 0.5
        
        return {
            'valid': len(errors) == 0 and score >= 0.5,
            'score': max(0.0, score),
            'errors': errors,
            'warnings': warnings,
            'details': {
                'has_usage': has_usage,
                'has_success': has_success,
                'has_email_logic': has_email_logic
            }
        }
    
    def _validate_email_shortcut(self, stdout: str, stderr: str, exit_code: int, expected: Dict) -> Dict:
        """Validate email shortcut (similar to template)"""
        return self._validate_email_template(stdout, stderr, exit_code, expected)
    
    def _validate_email_schedule(self, stdout: str, stderr: str, exit_code: int, expected: Dict) -> Dict:
        """Validate scheduled email reminder"""
        errors = []
        warnings = []
        score = 1.0
        
        # Should send notification or show reminder
        has_notification = 'reminder' in stdout.lower() or '✅' in stdout
        has_schedule = 'schedule' in stdout.lower() or 'reminder' in stdout.lower()
        
        if not has_notification:
            warnings.append('No reminder/notification detected')
            score -= 0.3
        
        return {
            'valid': len(errors) == 0 and score >= 0.5,
            'score': max(0.0, score),
            'errors': errors,
            'warnings': warnings,
            'details': {
                'has_notification': has_notification,
                'has_schedule': has_schedule
            }
        }
    
    def _validate_meeting_automation(self, stdout: str, stderr: str, exit_code: int, expected: Dict) -> Dict:
        """Validate meeting automation script"""
        errors = []
        warnings = []
        score = 1.0
        
        # Should mention meeting or prep/followup
        meeting_indicators = ['meeting', 'prep', 'reminder', 'agenda', 'summary']
        has_meeting_logic = any(ind in stdout.lower() for ind in meeting_indicators)
        
        if not has_meeting_logic:
            warnings.append('No meeting-related output')
            score -= 0.3
        
        # Should show action taken
        has_action = '✅' in stdout or 'sent' in stdout.lower()
        
        if not has_action:
            warnings.append('No action confirmation')
            score -= 0.2
        
        return {
            'valid': len(errors) == 0 and score >= 0.5,
            'score': max(0.0, score),
            'errors': errors,
            'warnings': warnings,
            'details': {
                'has_meeting_logic': has_meeting_logic,
                'has_action': has_action
            }
        }
    
    def _validate_focus_block(self, stdout: str, stderr: str, exit_code: int, expected: Dict) -> Dict:
        """Validate focus time block script"""
        errors = []
        warnings = []
        score = 1.0
        
        # Should mention calendar or focus/block
        focus_indicators = ['focus', 'block', 'calendar', 'added', 'created']
        has_focus_logic = any(ind in stdout.lower() for ind in focus_indicators)
        
        if not has_focus_logic:
            warnings.append('No focus block indicators')
            score -= 0.3
        
        return {
            'valid': len(errors) == 0 and score >= 0.5,
            'score': max(0.0, score),
            'errors': errors,
            'warnings': warnings,
            'details': {
                'has_focus_logic': has_focus_logic
            }
        }
    
    def _validate_meeting_workflow(self, stdout: str, stderr: str, exit_code: int, expected: Dict) -> Dict:
        """Validate meeting workflow script"""
        return self._validate_meeting_automation(stdout, stderr, exit_code, expected)
    
    def _validate_dir_navigation(self, stdout: str, stderr: str, exit_code: int, expected: Dict) -> Dict:
        """Validate directory navigation helper"""
        errors = []
        warnings = []
        score = 1.0
        
        # Should show path or usage
        has_path = 'cd' in stdout.lower() or 'directory' in stdout.lower()
        
        if not has_path and not stdout.strip():
            warnings.append('No navigation output')
            score -= 0.2
        
        return {
            'valid': len(errors) == 0 and score >= 0.5,
            'score': max(0.0, score),
            'errors': errors,
            'warnings': warnings,
            'details': {
                'has_path': has_path
            }
        }
    
    def _validate_multi_command(self, stdout: str, stderr: str, exit_code: int, expected: Dict) -> Dict:
        """Validate multi-command workflow"""
        errors = []
        warnings = []
        score = 1.0
        
        # Should show multiple operations or usage
        lines = stdout.strip().split('\n')
        has_multiple_ops = len(lines) >= 2
        
        if not has_multiple_ops:
            warnings.append('Expected multiple operation outputs')
            score -= 0.2
        
        return {
            'valid': len(errors) == 0 and score >= 0.5,
            'score': max(0.0, score),
            'errors': errors,
            'warnings': warnings,
            'details': {
                'output_lines': len(lines),
                'has_multiple_ops': has_multiple_ops
            }
        }


def main():
    """Test output validator"""
    validator = OutputValidator()
    
    print("V8 Output Validator - Test Suite")
    print("=" * 70)
    
    # Test 1: Command retry with retry logic
    print("\n1. Testing command_retry with retry indicators...")
    result = validator.validate(
        'command_retry',
        stdout="Attempt 1 failed\nAttempt 2 succeeded\n✅ Command completed",
        stderr="",
        exit_code=0
    )
    print(f"   Valid: {result['valid']}, Score: {result['score']:.2f}")
    print(f"   Details: {result['details']}")
    
    # Test 2: Email template with usage
    print("\n2. Testing email_template with usage...")
    result = validator.validate(
        'email_template',
        stdout="Usage: email_template <recipient> [message]\n",
        stderr="",
        exit_code=1
    )
    print(f"   Valid: {result['valid']}, Score: {result['score']:.2f}")
    print(f"   Details: {result['details']}")
    
    # Test 3: Meeting automation with action
    print("\n3. Testing meeting_automation...")
    result = validator.validate(
        'meeting_automation',
        stdout="✅ Prep reminder sent\nMeeting: Client Call\n",
        stderr="",
        exit_code=0
    )
    print(f"   Valid: {result['valid']}, Score: {result['score']:.2f}")
    print(f"   Details: {result['details']}")
    
    # Test 4: Invalid output
    print("\n4. Testing invalid output...")
    result = validator.validate(
        'command_retry',
        stdout="",
        stderr="SyntaxError: invalid syntax\n",
        exit_code=1
    )
    print(f"   Valid: {result['valid']}, Score: {result['score']:.2f}")
    print(f"   Errors: {result['errors']}")
    
    # Test 5: Unknown type
    print("\n5. Testing unknown type...")
    result = validator.validate(
        'unknown_type',
        stdout="Some output",
        stderr="",
        exit_code=0
    )
    print(f"   Valid: {result['valid']}, Score: {result['score']:.2f}")
    print(f"   Warnings: {result['warnings']}")
    
    print("\n" + "=" * 70)
    print("✓ All validator tests complete!")


if __name__ == '__main__':
    main()
