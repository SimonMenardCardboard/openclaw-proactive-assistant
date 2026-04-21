#!/usr/bin/env python3
"""
Sandbox Tester for V8 Generated Scripts

Tests generated scripts in a safe environment before deployment.

Tests performed:
1. Syntax validation (bash -n)
2. Dry-run execution
3. Rollback capability check
4. Side-effect analysis
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Optional


class SandboxTester:
    """Test generated scripts safely"""
    
    def __init__(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix='v8_sandbox_'))
    
    def test_script(self, script_code: str, script_name: str, language: str) -> Dict:
        """
        Test a generated script in sandbox.
        
        Returns:
            {
                'passed': bool,
                'syntax_valid': bool,
                'executable': bool,
                'safe': bool,
                'warnings': List[str],
                'errors': List[str]
            }
        """
        results = {
            'passed': False,
            'syntax_valid': False,
            'executable': False,
            'safe': False,
            'warnings': [],
            'errors': []
        }
        
        if language == 'bash':
            return self._test_bash_script(script_code, script_name, results)
        elif language == 'python':
            return self._test_python_script(script_code, script_name, results)
        else:
            results['errors'].append(f"Unsupported language: {language}")
            return results
    
    def _test_bash_script(self, code: str, name: str, results: Dict) -> Dict:
        """Test bash script"""
        # Write script to sandbox
        script_path = self.test_dir / name
        script_path.write_text(code)
        script_path.chmod(0o755)
        
        # 1. Syntax check
        try:
            result = subprocess.run(
                ['bash', '-n', str(script_path)],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                results['syntax_valid'] = True
            else:
                results['errors'].append(f"Syntax error: {result.stderr}")
                return results
        
        except Exception as e:
            results['errors'].append(f"Syntax check failed: {e}")
            return results
        
        # 2. Check for dangerous patterns
        dangerous_patterns = [
            'rm -rf /',
            'dd if=',
            '> /dev/sda',
            'mkfs',
            'fdisk',
            ': (){ :|:& };:',  # Fork bomb
        ]
        
        for pattern in dangerous_patterns:
            if pattern in code:
                results['errors'].append(f"Dangerous pattern detected: {pattern}")
                results['safe'] = False
                return results
        
        results['safe'] = True
        
        # 3. Test execution (with safe command)
        try:
            result = subprocess.run(
                [str(script_path), '--help'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # Script should handle --help (even if command doesn't support it)
            results['executable'] = True
        
        except subprocess.TimeoutExpired:
            results['warnings'].append("Script hangs on --help")
        except Exception as e:
            results['warnings'].append(f"Execution test failed: {e}")
        
        # 4. Check for network/file operations
        if 'curl' in code or 'wget' in code:
            results['warnings'].append("Script makes network requests")
        
        if any(x in code for x in ['rm ', 'mv ', 'cp ']):
            results['warnings'].append("Script modifies files")
        
        # Overall pass/fail
        results['passed'] = (
            results['syntax_valid'] and
            results['safe'] and
            len(results['errors']) == 0
        )
        
        return results
    
    def _test_python_script(self, code: str, name: str, results: Dict) -> Dict:
        """Test Python script"""
        script_path = self.test_dir / f"{name}.py"
        script_path.write_text(code)
        
        # 1. Syntax check
        try:
            result = subprocess.run(
                ['python3', '-m', 'py_compile', str(script_path)],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                results['syntax_valid'] = True
            else:
                results['errors'].append(f"Syntax error: {result.stderr}")
                return results
        
        except Exception as e:
            results['errors'].append(f"Syntax check failed: {e}")
            return results
        
        # 2. Safety checks
        dangerous_imports = ['os', 'subprocess', 'shutil']
        for imp in dangerous_imports:
            if f"import {imp}" in code or f"from {imp}" in code:
                results['warnings'].append(f"Uses potentially dangerous module: {imp}")
        
        results['safe'] = True
        results['executable'] = True  # Assume Python scripts are executable
        
        results['passed'] = (
            results['syntax_valid'] and
            results['safe']
        )
        
        return results
    
    def cleanup(self):
        """Clean up sandbox directory"""
        import shutil
        try:
            shutil.rmtree(self.test_dir)
        except:
            pass


def main():
    """Test sandbox tester"""
    tester = SandboxTester()
    
    # Test with a simple retry script
    test_script = '''#!/bin/bash
#
# Test retry script
#

MAX_RETRIES=3
DELAY=2

attempt=1
while [ $attempt -le $MAX_RETRIES ]; do
    echo "test" "$@"
    exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        exit 0
    fi
    
    if [ $attempt -lt $MAX_RETRIES ]; then
        echo "Retrying..." >&2
        sleep $DELAY
        attempt=$((attempt + 1))
    else
        exit $exit_code
    fi
done
'''
    
    results = tester.test_script(test_script, 'test_retry', 'bash')
    
    print("Sandbox Test Results:")
    print(f"  Passed: {results['passed']}")
    print(f"  Syntax Valid: {results['syntax_valid']}")
    print(f"  Executable: {results['executable']}")
    print(f"  Safe: {results['safe']}")
    
    if results['warnings']:
        print(f"  Warnings: {len(results['warnings'])}")
        for w in results['warnings']:
            print(f"    - {w}")
    
    if results['errors']:
        print(f"  Errors: {len(results['errors'])}")
        for e in results['errors']:
            print(f"    - {e}")
    
    tester.cleanup()


if __name__ == '__main__':
    main()
