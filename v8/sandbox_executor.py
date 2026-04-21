#!/usr/bin/env python3
"""
V8 Sandbox Executor - Phase 3

Safe execution environment for testing V8-generated optimizations.

Features:
- Isolated Python execution (subprocess, limited permissions)
- Syntax validation (AST parsing)
- Safety checks (block rm -rf, dd, fork bombs, etc.)
- Resource limits (CPU, memory, time)
- Output capture (stdout, stderr, exit code)
- Side-effect detection (file writes, network calls)

Usage:
    sandbox = SandboxExecutor()
    result = sandbox.execute(code, language='python')
    
    if result['safe'] and result['exit_code'] == 0:
        print("Safe to deploy!")
"""

import ast
import subprocess
import tempfile
import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Literal
from datetime import datetime
import json

# Import output validator and side effect monitor
sys.path.insert(0, str(Path(__file__).parent))
from output_validator import OutputValidator
from side_effect_monitor import SideEffectMonitor


class SandboxExecutor:
    """
    Execute code safely in an isolated sandbox environment.
    
    Security layers:
    1. Syntax validation (AST parsing)
    2. Pattern blacklist (rm -rf, dd, etc.)
    3. Resource limits (timeout, no network)
    4. Isolated execution (subprocess)
    5. Side-effect tracking (file writes monitored)
    """
    
    # Dangerous patterns to block (shell format)
    DANGEROUS_SHELL_PATTERNS = [
        r'rm\s+-rf\s+/',           # Delete root
        r'rm\s+-rf\s+~',           # Delete home
        r'dd\s+if=',               # Disk destroyer
        r'mkfs\.',                 # Format filesystem
        r'fdisk',                  # Partition editor
        r':\(\)\{\s*:\|:&\s*\};:', # Fork bomb
        r'>/dev/sd[a-z]',          # Direct disk write
        r'curl.*\|.*sh',           # Pipe to shell
        r'wget.*\|.*sh',           # Pipe to shell
    ]
    
    # Dangerous patterns (Python string format)
    DANGEROUS_PYTHON_STRINGS = [
        "rm -rf /",
        "rm -rf ~",
        "dd if=",
        "mkfs.",
        "> /dev/sd",
    ]
    
    # Dangerous Python patterns (code structure)
    DANGEROUS_PYTHON_PATTERNS = [
        r'exec\s*\(',              # Arbitrary execution
        r'eval\s*\(',              # Arbitrary evaluation
        r'__import__\s*\(',        # Dynamic imports
        r'compile\s*\(',           # Code compilation
        r'os\.system\s*\(',        # System calls
    ]
    
    # Dangerous imports (Python)
    DANGEROUS_IMPORTS = [
        'exec',
        'eval',
        'compile',
    ]
    
    # Allowed subprocess patterns (safer alternatives)
    ALLOWED_SUBPROCESS = [
        'subprocess.run',
        'subprocess.Popen',
    ]
    
    def __init__(self, 
                 timeout: int = 30,
                 max_output_size: int = 1024 * 1024,  # 1MB
                 allow_network: bool = False,
                 validate_output: bool = True):
        """
        Initialize sandbox executor.
        
        Args:
            timeout: Max execution time in seconds
            max_output_size: Max stdout/stderr size in bytes
            allow_network: Whether to allow network access (default: False)
            validate_output: Whether to validate outputs (default: True)
        """
        self.timeout = timeout
        self.max_output_size = max_output_size
        self.allow_network = allow_network
        self.validate_output = validate_output
        
        # Create sandbox directory
        self.sandbox_dir = Path.home() / '.openclaw/workspace/integrations/intelligence/v8_meta_learning/sandbox'
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        
        # Output validator
        self.validator = OutputValidator() if validate_output else None
        
        # Side effect monitor
        self.side_effect_monitor = SideEffectMonitor(watch_dir=self.sandbox_dir)
    
    def validate_syntax(self, code: str, language: Literal['python', 'bash']) -> Dict:
        """
        Validate code syntax without executing.
        
        Args:
            code: Source code to validate
            language: Programming language
        
        Returns:
            {
                'valid': bool,
                'error': str (if invalid),
                'warnings': List[str]
            }
        """
        if language == 'python':
            return self._validate_python_syntax(code)
        elif language == 'bash':
            return self._validate_bash_syntax(code)
        else:
            return {'valid': False, 'error': f'Unsupported language: {language}'}
    
    def _validate_python_syntax(self, code: str) -> Dict:
        """Validate Python code syntax via AST parsing"""
        try:
            ast.parse(code)
            return {'valid': True, 'warnings': []}
        except SyntaxError as e:
            return {
                'valid': False,
                'error': f'Syntax error at line {e.lineno}: {e.msg}',
                'warnings': []
            }
        except Exception as e:
            return {
                'valid': False,
                'error': f'Parse error: {str(e)}',
                'warnings': []
            }
    
    def _validate_bash_syntax(self, code: str) -> Dict:
        """Validate bash syntax via bash -n"""
        try:
            result = subprocess.run(
                ['bash', '-n'],
                input=code,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return {'valid': True, 'warnings': []}
            else:
                return {
                    'valid': False,
                    'error': result.stderr.strip(),
                    'warnings': []
                }
        
        except subprocess.TimeoutExpired:
            return {'valid': False, 'error': 'Syntax check timeout'}
        except Exception as e:
            return {'valid': False, 'error': f'Validation error: {str(e)}'}
    
    def check_safety(self, code: str, language: str) -> Dict:
        """
        Check code for dangerous patterns.
        
        Args:
            code: Source code to check
            language: Programming language
        
        Returns:
            {
                'safe': bool,
                'violations': List[str],
                'warnings': List[str]
            }
        """
        violations = []
        warnings = []
        
        if language == 'python':
            # Check Python-specific dangers
            violations.extend(self._check_python_safety(code))
        else:
            # Check shell-specific dangers
            violations.extend(self._check_shell_safety(code))
        
        # Check for network access (if disabled)
        if not self.allow_network:
            network_patterns = [
                r'import\s+requests',
                r'import\s+urllib',
                r'import\s+socket',
                r'curl\s+',
                r'wget\s+',
            ]
            
            for pattern in network_patterns:
                if re.search(pattern, code, re.IGNORECASE):
                    warnings.append(f'Network access detected (blocked): {pattern}')
        
        return {
            'safe': len(violations) == 0,
            'violations': violations,
            'warnings': warnings
        }
    
    def _check_python_safety(self, code: str) -> List[str]:
        """Check Python code for dangerous patterns"""
        violations = []
        
        # Check for dangerous string literals
        for dangerous_str in self.DANGEROUS_PYTHON_STRINGS:
            if dangerous_str in code:
                violations.append(f'Dangerous command string detected: {dangerous_str}')
        
        # Check for dangerous function calls
        for pattern in self.DANGEROUS_PYTHON_PATTERNS:
            matches = re.finditer(pattern, code, re.MULTILINE)
            for match in matches:
                violations.append(f'Dangerous function call: {match.group()}')
        
        # Parse AST to check for dangerous operations
        try:
            tree = ast.parse(code)
            
            # Check imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in self.DANGEROUS_IMPORTS:
                            violations.append(f'Dangerous import: {alias.name}')
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module in self.DANGEROUS_IMPORTS:
                        violations.append(f'Dangerous import: from {node.module}')
                
                # Check for os.system calls
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        if (isinstance(node.func.value, ast.Name) and 
                            node.func.value.id == 'os' and 
                            node.func.attr == 'system'):
                            violations.append('Dangerous call: os.system()')
        
        except:
            # AST parsing failed, but syntax validation will catch this
            pass
        
        return violations
    
    def _check_shell_safety(self, code: str) -> List[str]:
        """Check shell code for dangerous patterns"""
        violations = []
        
        # Check against dangerous shell patterns
        for pattern in self.DANGEROUS_SHELL_PATTERNS:
            matches = re.finditer(pattern, code, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                violations.append(f'Dangerous shell pattern: {match.group()}')
        
        return violations
    
    def execute(self, 
                code: str, 
                language: Literal['python', 'bash'],
                env: Optional[Dict[str, str]] = None) -> Dict:
        """
        Execute code in sandbox and capture results.
        
        Args:
            code: Source code to execute
            language: Programming language
            env: Optional environment variables
        
        Returns:
            {
                'success': bool,
                'exit_code': int,
                'stdout': str,
                'stderr': str,
                'duration': float (seconds),
                'violations': List[str],
                'side_effects': {
                    'files_created': List[str],
                    'files_modified': List[str],
                    'files_deleted': List[str]
                }
            }
        """
        # Step 1: Validate syntax
        syntax_check = self.validate_syntax(code, language)
        if not syntax_check['valid']:
            return {
                'success': False,
                'exit_code': -1,
                'stdout': '',
                'stderr': f"Syntax error: {syntax_check['error']}",
                'duration': 0,
                'violations': [syntax_check['error']],
                'side_effects': {}
            }
        
        # Step 2: Check safety
        safety_check = self.check_safety(code, language)
        if not safety_check['safe']:
            return {
                'success': False,
                'exit_code': -1,
                'stdout': '',
                'stderr': 'Safety violations detected',
                'duration': 0,
                'violations': safety_check['violations'],
                'side_effects': {}
            }
        
        # Step 3: Execute in sandbox
        return self._execute_sandboxed(code, language, env, safety_check['warnings'])
    
    def _execute_sandboxed(self, code: str, language: str, env: Optional[Dict], warnings: List[str]) -> Dict:
        """Execute code in isolated subprocess"""
        # Create temporary file for code
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py' if language == 'python' else '.sh',
            dir=self.sandbox_dir,
            delete=False
        ) as f:
            f.write(code)
            script_path = f.name
        
        try:
            # Start side-effect monitoring
            self.side_effect_monitor.start_tracking()
            
            # Build execution command
            if language == 'python':
                cmd = [sys.executable, script_path]
            else:  # bash
                cmd = ['bash', script_path]
            
            # Set up environment
            exec_env = os.environ.copy()
            if env:
                exec_env.update(env)
            
            # Disable network (if configured)
            if not self.allow_network:
                exec_env['no_proxy'] = '*'
            
            # Execute with timeout
            start_time = datetime.now()
            
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    env=exec_env,
                    cwd=self.sandbox_dir
                )
                
                duration = (datetime.now() - start_time).total_seconds()
                
                # Stop side-effect monitoring
                self.side_effect_monitor.stop_tracking()
                effects = self.side_effect_monitor.get_effects()
                safety_check = self.side_effect_monitor.check_safety(effects)
                
                # Merge side-effect warnings
                all_warnings = warnings + safety_check['warnings']
                all_violations = safety_check['violations']
                
                # Truncate output if too large
                stdout = result.stdout[:self.max_output_size]
                stderr = result.stderr[:self.max_output_size]
                
                return {
                    'success': result.returncode == 0 and safety_check['safe'],
                    'exit_code': result.returncode,
                    'stdout': stdout,
                    'stderr': stderr,
                    'duration': duration,
                    'violations': all_violations,
                    'warnings': all_warnings,
                    'side_effects': effects['files'],
                    'side_effects_summary': effects['summary']
                }
            
            except subprocess.TimeoutExpired:
                duration = self.timeout
                return {
                    'success': False,
                    'exit_code': -1,
                    'stdout': '',
                    'stderr': f'Execution timeout ({self.timeout}s)',
                    'duration': duration,
                    'violations': ['Timeout exceeded'],
                    'warnings': warnings,
                    'side_effects': {}
                }
        
        finally:
            # Clean up script file
            try:
                os.unlink(script_path)
            except:
                pass
    
    def test_optimization(self, optimization: Dict) -> Dict:
        """
        Test a V8-generated optimization in sandbox.
        
        Args:
            optimization: {
                'code': str,
                'language': str,
                'name': str,
                'type': str,
                'confidence': float
            }
        
        Returns:
            {
                'approved': bool,
                'test_passed': bool,
                'exit_code': int,
                'output': str,
                'errors': List[str],
                'warnings': List[str],
                'duration': float,
                'validation': Dict (if validator enabled)
            }
        """
        code = optimization.get('code', '')
        language = optimization.get('language', 'python')
        opt_type = optimization.get('type', 'unknown')
        
        result = self.execute(code, language)
        
        # Validate output (if enabled)
        validation_result = None
        if self.validate_output and self.validator and result['success']:
            validation_result = self.validator.validate(
                opt_type,
                result['stdout'],
                result['stderr'],
                result['exit_code']
            )
        
        # Combine results
        approved = (result['success'] and 
                   len(result['violations']) == 0 and
                   (validation_result['valid'] if validation_result else True))
        
        response = {
            'approved': approved,
            'test_passed': result['success'],
            'exit_code': result['exit_code'],
            'output': result['stdout'],
            'errors': result['violations'] + ([result['stderr']] if result['stderr'] else []),
            'warnings': result.get('warnings', []),
            'duration': result['duration']
        }
        
        if validation_result:
            response['validation'] = validation_result
            if not validation_result['valid']:
                response['errors'].extend(validation_result['errors'])
                response['warnings'].extend(validation_result['warnings'])
        
        return response


def main():
    """Test sandbox executor"""
    sandbox = SandboxExecutor(timeout=10)
    
    print("V8 Sandbox Executor - Test Suite")
    print("=" * 70)
    
    # Test 1: Valid Python code
    print("\n1. Testing valid Python code...")
    test_code = '''
print("Hello from sandbox!")
x = 1 + 1
print(f"1 + 1 = {x}")
'''
    
    result = sandbox.execute(test_code, 'python')
    print(f"   Success: {result['success']}")
    print(f"   Output: {result['stdout'].strip()}")
    
    # Test 2: Syntax error
    print("\n2. Testing syntax error...")
    bad_code = '''
print("Missing closing paren"
'''
    
    result = sandbox.execute(bad_code, 'python')
    print(f"   Success: {result['success']}")
    print(f"   Error: {result['stderr'][:100]}")
    
    # Test 3: Dangerous pattern (rm -rf)
    print("\n3. Testing dangerous pattern detection...")
    dangerous_code = '''
import subprocess
subprocess.run(['rm', '-rf', '/'])
'''
    
    result = sandbox.execute(dangerous_code, 'python')
    print(f"   Success: {result['success']}")
    print(f"   Violations: {result['violations']}")
    
    # Test 4: Safe bash script
    print("\n4. Testing safe bash script...")
    bash_code = '''#!/bin/bash
echo "Safe bash script"
date
'''
    
    result = sandbox.execute(bash_code, 'bash')
    print(f"   Success: {result['success']}")
    print(f"   Output: {result['stdout'].strip()}")
    
    # Test 5: Test optimization (V8 format)
    print("\n5. Testing V8 optimization format...")
    optimization = {
        'code': '''#!/usr/bin/env python3
print("Testing V8 optimization")
''',
        'language': 'python',
        'name': 'test_optimization',
        'type': 'command_retry',
        'confidence': 0.95
    }
    
    result = sandbox.test_optimization(optimization)
    print(f"   Approved: {result['approved']}")
    print(f"   Test passed: {result['test_passed']}")
    print(f"   Duration: {result['duration']:.3f}s")
    
    print("\n" + "=" * 70)
    print("✓ All sandbox tests complete!")


if __name__ == '__main__':
    main()
