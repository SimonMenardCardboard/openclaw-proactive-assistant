#!/usr/bin/env python3
"""
Alias management for V8 deployments
"""

from pathlib import Path
import re


def add_shell_alias(script_name: str, script_path: Path) -> bool:
    """
    Add shell alias for a deployed script.
    
    Args:
        script_name: Name of the script (e.g., 'npx_retry')
        script_path: Full path to the script
    
    Returns:
        True if alias added successfully
    """
    # Extract base command from script name (remove _retry suffix)
    command = script_name.replace('_retry', '').replace('_', ' ')
    
    # Shell config file
    zshrc = Path.home() / '.zshrc'
    
    if not zshrc.exists():
        return False
    
    # Check if alias already exists
    with open(zshrc, 'r') as f:
        content = f.read()
        if f"alias {command}='{script_path}'" in content:
            print(f"   Alias already exists: {command}")
            return True
    
    # Add alias
    alias_line = f"alias {command}='{script_path}'"
    
    with open(zshrc, 'a') as f:
        # Add section header if not present
        if '# V8 Auto-generated aliases' not in content:
            f.write('\n\n# V8 Auto-generated aliases\n')
        f.write(f"{alias_line}\n")
    
    print(f"   ✅ Alias added: {command} → {script_path}")
    print(f"   Run 'source ~/.zshrc' or restart shell to activate")
    
    return True
