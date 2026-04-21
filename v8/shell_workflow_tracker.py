#!/usr/bin/env python3
"""
Shell Workflow Tracker - V8 Phase 1 Breadth Expansion

Analyzes shell command history to find workflow patterns:
- Repetitive command sequences (candidates for aliases/scripts)
- Long-running commands (candidates for background automation)
- Error-prone patterns (typos, retries, common mistakes)
- Directory navigation patterns (wasteful cd sequences)

Goal: Find 5-10 shell optimizations from actual usage
"""

import sqlite3
import re
from pathlib import Path
from typing import List, Dict, Tuple
from collections import Counter, defaultdict


class ShellWorkflowTracker:
    """Track shell command patterns for optimization"""
    
    def __init__(self, db_path: Path = None):
        if db_path is None:
            db_path = Path.home() / '.openclaw/workspace/integrations/intelligence/v8_meta_learning/universal_workflows.db'
        
        self.db_path = db_path
        self.history_file = Path.home() / '.zsh_history'
        self._init_db()
    
    def _init_db(self):
        """Initialize shell workflow tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shell_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command TEXT,
                frequency INTEGER,
                avg_length INTEGER,
                tracked_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shell_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT,
                description TEXT,
                commands TEXT,
                occurrences INTEGER,
                time_impact_seconds INTEGER,
                detected_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def load_history(self) -> List[str]:
        """Load zsh history"""
        try:
            with open(self.history_file, 'rb') as f:
                # zsh history has metadata, extract commands
                lines = f.read().decode('utf-8', errors='ignore').split('\n')
                commands = []
                
                for line in lines:
                    # Skip empty lines
                    if not line.strip():
                        continue
                    
                    # zsh format: ": timestamp:duration;command"
                    if line.startswith(':'):
                        parts = line.split(';', 1)
                        if len(parts) == 2:
                            commands.append(parts[1].strip())
                    else:
                        commands.append(line.strip())
                
                return commands[-10000:]  # Last 10k commands
                
        except Exception as e:
            print(f"Error loading history: {e}")
            return []
    
    def detect_patterns(self, commands: List[str]) -> List[Dict]:
        """Analyze commands for optimization opportunities"""
        patterns = []
        
        # Pattern 1: Repetitive command sequences
        sequences = self._find_command_sequences(commands)
        for seq, count in sequences.items():
            if count >= 3 and len(seq) >= 2:  # 3+ occurrences, 2+ commands
                time_saved = len(seq) * 5 * count  # 5sec per command typing
                patterns.append({
                    'type': 'repetitive_sequence',
                    'description': f'"{" && ".join(seq)}" repeated {count} times',
                    'commands': ' && '.join(seq),
                    'occurrences': count,
                    'time_impact': time_saved,
                    'optimization': f'Create alias or script'
                })
        
        # Pattern 2: Directory navigation waste
        nav_waste = self._find_navigation_waste(commands)
        if nav_waste['occurrences'] > 5:
            patterns.append({
                'type': 'directory_navigation_waste',
                'description': f'{nav_waste["occurrences"]} wasteful cd sequences',
                'commands': 'cd ... (multiple hops)',
                'occurrences': nav_waste['occurrences'],
                'time_impact': nav_waste['time_saved'],
                'optimization': 'Use autojump/z, create directory aliases'
            })
        
        # Pattern 3: Typo patterns (command not found retries)
        typos = self._find_typo_patterns(commands)
        if typos > 10:
            patterns.append({
                'type': 'command_typos',
                'description': f'{typos} likely typos (common misspellings)',
                'commands': 'Various (git commands, common tools)',
                'occurrences': typos,
                'time_impact': typos * 3,  # 3sec per typo
                'optimization': 'Install thefuck or create typo aliases'
            })
        
        # Pattern 4: Long git sequences
        git_patterns = self._find_git_patterns(commands)
        for pattern in git_patterns:
            if pattern['count'] >= 3:
                patterns.append({
                    'type': 'git_workflow',
                    'description': f'Git sequence: {pattern["sequence"]} ({pattern["count"]}x)',
                    'commands': pattern['sequence'],
                    'occurrences': pattern['count'],
                    'time_impact': pattern['time_saved'],
                    'optimization': pattern['optimization']
                })
        
        # Store patterns
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for pattern in patterns:
            cursor.execute("""
                INSERT INTO shell_patterns 
                (pattern_type, description, commands, occurrences, time_impact_seconds)
                VALUES (?, ?, ?, ?, ?)
            """, (
                pattern['type'],
                pattern['description'],
                pattern['commands'],
                pattern['occurrences'],
                pattern['time_impact']
            ))
        
        conn.commit()
        conn.close()
        
        return patterns
    
    def _find_command_sequences(self, commands: List[str]) -> Dict[Tuple[str], int]:
        """Find repeated command sequences"""
        sequences = defaultdict(int)
        
        # Look for 2-4 command sequences
        for i in range(len(commands) - 1):
            for length in [2, 3, 4]:
                if i + length > len(commands):
                    break
                
                seq = tuple(commands[i:i+length])
                # Normalize (remove args for matching)
                normalized = tuple(cmd.split()[0] if cmd.split() else cmd for cmd in seq)
                sequences[normalized] += 1
        
        # Filter low-value sequences
        return {k: v for k, v in sequences.items() if v >= 3}
    
    def _find_navigation_waste(self, commands: List[str]) -> Dict:
        """Find wasteful directory navigation"""
        cd_sequences = []
        current_seq = []
        
        for cmd in commands:
            if cmd.startswith('cd '):
                current_seq.append(cmd)
            elif current_seq:
                if len(current_seq) >= 3:  # 3+ cd commands in a row
                    cd_sequences.append(current_seq)
                current_seq = []
        
        occurrences = len(cd_sequences)
        time_saved = occurrences * 10  # 10sec per wasteful sequence
        
        return {'occurrences': occurrences, 'time_saved': time_saved}
    
    def _find_typo_patterns(self, commands: List[str]) -> int:
        """Estimate typos from common patterns"""
        typo_count = 0
        
        # Common typos
        typo_patterns = [
            (r'^gti ', r'git '),  # gti -> git
            (r'^pytohn', r'python'),
            (r'^cd\.\.', r'cd ..'),
            (r'^mak ', r'make '),
            (r'^gerp', r'grep'),
        ]
        
        for cmd in commands:
            for typo, correct in typo_patterns:
                if re.match(typo, cmd):
                    typo_count += 1
        
        return typo_count
    
    def _find_git_patterns(self, commands: List[str]) -> List[Dict]:
        """Find common git workflow patterns"""
        patterns = []
        
        # Pattern: add + commit + push
        add_commit_push = 0
        for i in range(len(commands) - 2):
            if (commands[i].startswith('git add') and
                commands[i+1].startswith('git commit') and
                commands[i+2].startswith('git push')):
                add_commit_push += 1
        
        if add_commit_push >= 3:
            patterns.append({
                'sequence': 'git add → git commit → git push',
                'count': add_commit_push,
                'time_saved': add_commit_push * 15,  # 15sec per sequence
                'optimization': 'Create "gcp" alias: add, commit, push in one command'
            })
        
        # Pattern: status checks (excessive)
        status_checks = sum(1 for cmd in commands if cmd == 'git status')
        if status_checks > 50:
            patterns.append({
                'sequence': 'git status (excessive)',
                'count': status_checks,
                'time_saved': status_checks * 2,  # 2sec per check
                'optimization': 'Use git prompt in shell (shows status automatically)'
            })
        
        return patterns
    
    def generate_report(self) -> str:
        """Generate optimization report"""
        commands = self.load_history()
        print(f"📊 Loaded {len(commands)} shell commands")
        
        patterns = self.detect_patterns(commands)
        
        if not patterns:
            return "✅ No shell optimization opportunities detected"
        
        report = "🐚 SHELL WORKFLOW OPTIMIZATION OPPORTUNITIES\n"
        report += "=" * 60 + "\n\n"
        
        total_time_saved = sum(p['time_impact'] for p in patterns)
        
        # Sort by time impact
        patterns.sort(key=lambda x: x['time_impact'], reverse=True)
        
        for i, pattern in enumerate(patterns, 1):
            report += f"{i}. {pattern['description']}\n"
            report += f"   Time Impact: {pattern['time_impact']}sec saved\n"
            report += f"   Optimization: {pattern['optimization']}\n\n"
        
        report += f"Total Time Savings: {total_time_saved}sec = {total_time_saved/60:.1f} min\n"
        report += f"Optimizations Found: {len(patterns)}\n"
        
        return report


if __name__ == '__main__':
    tracker = ShellWorkflowTracker()
    
    print("🔍 Analyzing shell command history...")
    report = tracker.generate_report()
    print("\n" + report)
