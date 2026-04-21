#!/usr/bin/env python3
"""
Shell History Analyzer

Detects patterns from user's shell history (zsh/bash).
Complements V6 execution log analysis with ACTUAL user behavior.

Patterns detected:
1. Repeated commands (candidates for retry wrappers)
2. Command sequences (candidates for workflows)
3. Directory navigation patterns
4. Git workflows
"""

import re
from pathlib import Path
from collections import defaultdict, Counter
from typing import List, Dict, Tuple
from datetime import datetime


class ShellHistoryAnalyzer:
    """Analyze shell history for optimization patterns"""
    
    def __init__(self, history_file: Path = None):
        if history_file is None:
            # Try zsh history first, fall back to bash
            zsh_history = Path.home() / '.zsh_history'
            bash_history = Path.home() / '.bash_history'
            
            if zsh_history.exists():
                history_file = zsh_history
            elif bash_history.exists():
                history_file = bash_history
            else:
                raise FileNotFoundError("No shell history file found")
        
        self.history_file = history_file
        self.min_occurrences = 5  # Pattern must appear 5+ times
        self.lookback_lines = 5000  # Analyze last 5000 commands
    
    def parse_zsh_history(self) -> List[Tuple[int, str]]:
        """Parse zsh history (supports both timestamped and plain format)"""
        commands = []
        
        try:
            with open(self.history_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Error reading history: {e}")
            return []
        
        # Take last N lines
        lines = lines[-self.lookback_lines:]
        
        # Use line number as timestamp if no real timestamp
        base_timestamp = 1000000
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Try zsh extended format: : <timestamp>:<duration>;<command>
            match = re.match(r'^:\s*(\d+):\d+;(.+)$', line)
            if match:
                timestamp = int(match.group(1))
                command = match.group(2).strip()
                commands.append((timestamp, command))
            else:
                # Plain format (no timestamp)
                # Use line number as pseudo-timestamp
                timestamp = base_timestamp + i
                commands.append((timestamp, line))
        
        return commands
    
    def detect_repeated_commands(self, commands: List[Tuple[int, str]]) -> List[Dict]:
        """Detect frequently repeated commands"""
        # Extract just command (ignore args for frequency)
        command_bases = []
        
        for ts, full_cmd in commands:
            # Get base command (first word)
            parts = full_cmd.split()
            if not parts:
                continue
            
            base = parts[0]
            
            # Skip common navigation/listing commands
            if base in ['cd', 'ls', 'pwd', 'clear', 'exit', 'history']:
                continue
            
            command_bases.append((base, full_cmd))
        
        # Count occurrences
        counter = Counter([cmd[0] for cmd in command_bases])
        
        patterns = []
        for command, count in counter.most_common(20):
            if count >= self.min_occurrences:
                patterns.append({
                    'type': 'repeated_command',
                    'command': command,
                    'occurrences': count,
                    'confidence': min(0.95, 0.7 + (count / 100)),
                    'description': f"Command '{command}' repeated {count} times",
                    'template': 'command_retry'
                })
        
        return patterns
    
    def detect_command_sequences(self, commands: List[Tuple[int, str]]) -> List[Dict]:
        """Detect frequently occurring command sequences"""
        sequences = defaultdict(int)
        
        # Look for sequences of 2-4 commands
        for window_size in [2, 3, 4]:
            for i in range(len(commands) - window_size + 1):
                window = commands[i:i+window_size]
                
                # Extract base commands
                bases = []
                for ts, full_cmd in window:
                    parts = full_cmd.split()
                    if parts:
                        bases.append(parts[0])
                
                # Skip if contains too many cd/ls
                if bases.count('cd') + bases.count('ls') > window_size / 2:
                    continue
                
                # Create sequence key
                seq_key = ' → '.join(bases)
                
                # Check time gap (must be within 5 minutes)
                time_diff = window[-1][0] - window[0][0]
                if time_diff < 300:  # 5 minutes
                    sequences[seq_key] += 1
        
        patterns = []
        for sequence, count in sorted(sequences.items(), key=lambda x: x[1], reverse=True)[:10]:
            if count >= self.min_occurrences:
                patterns.append({
                    'type': 'command_sequence',
                    'sequence': sequence,
                    'commands': sequence.split(' → '),
                    'occurrences': count,
                    'confidence': min(0.90, 0.65 + (count / 50)),
                    'description': f"Sequence '{sequence}' repeated {count} times",
                    'template': 'multi_command'
                })
        
        return patterns
    
    def detect_git_workflows(self, commands: List[Tuple[int, str]]) -> List[Dict]:
        """Detect common git workflows"""
        git_sequences = defaultdict(int)
        
        for i in range(len(commands) - 2):
            window = commands[i:i+3]
            
            # Check if all commands are git
            git_cmds = []
            for ts, full_cmd in window:
                if full_cmd.startswith('git '):
                    # Extract git subcommand
                    parts = full_cmd.split()
                    if len(parts) >= 2:
                        git_cmds.append(parts[1])
            
            if len(git_cmds) >= 2:
                # Check time gap
                time_diff = window[-1][0] - window[0][0]
                if time_diff < 300:
                    seq_key = ' → '.join(git_cmds)
                    git_sequences[seq_key] += 1
        
        patterns = []
        for sequence, count in sorted(git_sequences.items(), key=lambda x: x[1], reverse=True)[:5]:
            if count >= 3:  # Lower threshold for git workflows
                git_commands = ['git ' + cmd for cmd in sequence.split(' → ')]
                patterns.append({
                    'type': 'git_workflow',
                    'sequence': sequence,
                    'commands': git_commands,
                    'occurrences': count,
                    'confidence': min(0.85, 0.70 + (count / 30)),
                    'description': f"Git workflow '{sequence}' repeated {count} times",
                    'template': 'multi_command'
                })
        
        return patterns
    
    def analyze(self) -> Dict[str, List[Dict]]:
        """Run full analysis"""
        print(f"📊 Analyzing shell history: {self.history_file}")
        
        # Parse history
        commands = self.parse_zsh_history()
        print(f"   Loaded {len(commands)} commands")
        
        # Detect patterns
        results = {
            'repeated_commands': self.detect_repeated_commands(commands),
            'command_sequences': self.detect_command_sequences(commands),
            'git_workflows': self.detect_git_workflows(commands)
        }
        
        total = sum(len(patterns) for patterns in results.values())
        print(f"   Found {total} patterns")
        
        return results


def main():
    """Test shell history analyzer"""
    analyzer = ShellHistoryAnalyzer()
    
    results = analyzer.analyze()
    
    print("\n" + "="*60)
    print("SHELL HISTORY PATTERNS")
    print("="*60)
    
    for category, patterns in results.items():
        if patterns:
            print(f"\n{category.upper().replace('_', ' ')} ({len(patterns)}):")
            for i, pattern in enumerate(patterns[:5], 1):
                print(f"\n{i}. {pattern['description']}")
                print(f"   Confidence: {pattern['confidence']:.0%}")
                if 'commands' in pattern:
                    print(f"   Commands: {', '.join(pattern['commands'])}")


if __name__ == '__main__':
    main()
