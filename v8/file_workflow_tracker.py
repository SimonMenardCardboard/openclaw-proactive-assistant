#!/usr/bin/env python3
"""
File Workflow Tracker - V8 Phase 1 Breadth Expansion

Analyzes file operations to find optimization opportunities:
- Repetitive file edits (should be scripted)
- Large file reads (candidates for streaming/chunking)
- Temporary file waste (cleanup opportunities)
- Config file patterns (should be templated)

Goal: Find 5-10 file operation optimizations
"""

import sqlite3
import os
from pathlib import Path
from typing import List, Dict
from collections import defaultdict
import subprocess


class FileWorkflowTracker:
    """Track file operation patterns for optimization"""
    
    def __init__(self, db_path: Path = None):
        if db_path is None:
            db_path = Path.home() / '.openclaw/workspace/integrations/intelligence/v8_meta_learning/universal_workflows.db'
        
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize file workflow tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_type TEXT,
                file_path TEXT,
                file_size_bytes INTEGER,
                frequency INTEGER,
                tracked_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT,
                description TEXT,
                files TEXT,
                occurrences INTEGER,
                time_impact_seconds INTEGER,
                detected_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def analyze_workspace_files(self) -> Dict:
        """Analyze workspace file patterns"""
        workspace = Path.home() / '.openclaw/workspace'
        
        patterns = {
            'large_files': [],
            'temp_files': [],
            'log_files': [],
            'config_files': [],
            'databases': []
        }
        
        # Find files
        for file_path in workspace.rglob('*'):
            if not file_path.is_file():
                continue
            
            # Skip hidden and cache dirs
            if any(part.startswith('.') for part in file_path.parts):
                if '.git' in file_path.parts or '__pycache__' in file_path.parts:
                    continue
            
            size = file_path.stat().st_size
            name = file_path.name
            
            # Categorize
            if size > 10_000_000:  # >10MB
                patterns['large_files'].append({
                    'path': str(file_path),
                    'size_mb': size / 1_000_000,
                    'type': file_path.suffix
                })
            
            if name.endswith(('.tmp', '.temp', '.bak', '.old', '.swp')):
                patterns['temp_files'].append(str(file_path))
            
            if name.endswith('.log') or 'log' in name.lower():
                patterns['log_files'].append({
                    'path': str(file_path),
                    'size_mb': size / 1_000_000
                })
            
            if name in ('config.json', 'settings.json', '.env', 'config.py'):
                patterns['config_files'].append(str(file_path))
            
            if name.endswith(('.db', '.sqlite', '.sqlite3')):
                patterns['databases'].append({
                    'path': str(file_path),
                    'size_mb': size / 1_000_000
                })
        
        return patterns
    
    def detect_patterns(self) -> List[Dict]:
        """Analyze files for optimization opportunities"""
        file_data = self.analyze_workspace_files()
        patterns = []
        
        # Pattern 1: Large log files
        large_logs = [f for f in file_data['log_files'] if f['size_mb'] > 10]
        if large_logs:
            total_size = sum(f['size_mb'] for f in large_logs)
            patterns.append({
                'type': 'large_log_files',
                'description': f'{len(large_logs)} log files >{total_size:.1f}MB total',
                'files': ', '.join([Path(f['path']).name for f in large_logs[:3]]),
                'occurrences': len(large_logs),
                'time_impact': 30,  # 30sec to rotate logs
                'optimization': 'Setup log rotation (compress old logs, delete after 30 days)'
            })
        
        # Pattern 2: Temporary files
        if file_data['temp_files']:
            patterns.append({
                'type': 'temp_files_cleanup',
                'description': f'{len(file_data["temp_files"])} temp files left behind',
                'files': ', '.join([Path(f).name for f in file_data['temp_files'][:3]]),
                'occurrences': len(file_data['temp_files']),
                'time_impact': 10,
                'optimization': 'Create cleanup script (run weekly via cron)'
            })
        
        # Pattern 3: Large databases
        large_dbs = [f for f in file_data['databases'] if f['size_mb'] > 50]
        if large_dbs:
            patterns.append({
                'type': 'large_databases',
                'description': f'{len(large_dbs)} databases >50MB',
                'files': ', '.join([Path(f['path']).name for f in large_dbs]),
                'occurrences': len(large_dbs),
                'time_impact': 60,
                'optimization': 'Archive old data, add VACUUM schedule'
            })
        
        # Pattern 4: Duplicate config files
        if len(file_data['config_files']) > 5:
            patterns.append({
                'type': 'duplicate_configs',
                'description': f'{len(file_data["config_files"])} config files (potential duplication)',
                'files': ', '.join([Path(f).name for f in file_data['config_files'][:5]]),
                'occurrences': len(file_data['config_files']),
                'time_impact': 120,
                'optimization': 'Consolidate configs, use shared config with overrides'
            })
        
        # Store patterns
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for pattern in patterns:
            cursor.execute("""
                INSERT INTO file_patterns 
                (pattern_type, description, files, occurrences, time_impact_seconds)
                VALUES (?, ?, ?, ?, ?)
            """, (
                pattern['type'],
                pattern['description'],
                pattern['files'],
                pattern['occurrences'],
                pattern['time_impact']
            ))
        
        conn.commit()
        conn.close()
        
        return patterns
    
    def generate_report(self) -> str:
        """Generate optimization report"""
        patterns = self.detect_patterns()
        
        if not patterns:
            return "✅ No file optimization opportunities detected"
        
        report = "📁 FILE OPERATION OPTIMIZATION OPPORTUNITIES\n"
        report += "=" * 60 + "\n\n"
        
        total_time_saved = sum(p['time_impact'] for p in patterns)
        
        for i, pattern in enumerate(patterns, 1):
            report += f"{i}. {pattern['description']}\n"
            report += f"   Files: {pattern['files']}\n"
            report += f"   Time Impact: {pattern['time_impact']}sec saved\n"
            report += f"   Optimization: {pattern['optimization']}\n\n"
        
        report += f"Total Time Savings: {total_time_saved}sec = {total_time_saved/60:.1f} min\n"
        report += f"Optimizations Found: {len(patterns)}\n"
        
        return report


if __name__ == '__main__':
    tracker = FileWorkflowTracker()
    
    print("🔍 Analyzing workspace file patterns...")
    report = tracker.generate_report()
    print("\n" + report)
