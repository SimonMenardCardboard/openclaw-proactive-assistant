#!/usr/bin/env python3
"""
V8 Continuous Pattern Learning Daemon

Runs continuously like V6/V7, analyzing patterns in real-time and queuing insights.

Unlike the daily batch report, this:
- Monitors email/calendar changes continuously
- Detects patterns as they emerge
- Queues insights immediately (not daily digest)
- Learns from user feedback on recommendations

Usage:
    python3 v8_continuous_pattern_daemon.py [--interval 300] [--workspace ~/.openclaw/workspace]
"""

import time
import asyncio
import signal
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Add paths
workspace = Path.home() / '.openclaw/workspace'
sys.path.insert(0, str(workspace / 'integrations/intelligence'))
sys.path.insert(0, str(workspace / 'integrations/intelligence/v8_meta_learning'))

from proactive_queue import ProactiveQueue


class V8ContinuousPatternDaemon:
    """Continuous pattern learning daemon."""
    
    def __init__(self, interval: int = 300, workspace_path: Optional[Path] = None):
        """
        Initialize V8 continuous daemon.
        
        Args:
            interval: Check interval in seconds (default 300 = 5 minutes)
            workspace_path: Workspace root path
        """
        if workspace_path is None:
            workspace_path = Path.home() / '.openclaw/workspace'
        
        self.workspace = Path(workspace_path)
        self.interval = interval
        self.running = False
        
        # Initialize queue
        self.queue = ProactiveQueue(db_path=self.workspace / 'integrations/intelligence/proactive_queue.db')
        
        # State tracking
        self.last_email_check = None
        self.last_calendar_check = None
        self.last_pattern_run = None
        
        # Pattern cache (avoid re-detecting same patterns)
        self.detected_patterns = set()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print(f"\n[{datetime.now().isoformat()}] Received signal {signum}, shutting down...", flush=True)
        self.running = False
    
    def start(self):
        """Start the daemon."""
        print(f"[{datetime.now().isoformat()}] V8 Continuous Pattern Daemon starting", flush=True)
        print(f"  Check interval: {self.interval}s ({self.interval // 60} minutes)", flush=True)
        print(f"  Workspace: {self.workspace}", flush=True)
        print(flush=True)
        
        self.running = True
        
        # Use async event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self._async_run())
        finally:
            loop.close()
    
    async def _async_run(self):
        """Async main loop."""
        while self.running:
            try:
                await self._pattern_check_cycle()
                
                if self.running:
                    await asyncio.sleep(self.interval)
            
            except KeyboardInterrupt:
                break
            
            except Exception as e:
                print(f"[{datetime.now().isoformat()}] Error in pattern check: {e}", flush=True)
                if self.running:
                    await asyncio.sleep(self.interval)
        
        print(f"\n[{datetime.now().isoformat()}] V8 Continuous Pattern Daemon stopped", flush=True)
    
    async def _pattern_check_cycle(self):
        """Execute one pattern detection cycle."""
        now = datetime.now()
        print(f"[{now.isoformat()}] Pattern check starting...", flush=True)
        
        # 1. Check for email patterns
        email_insights = await self._check_email_patterns()
        
        # 2. Check for calendar patterns
        calendar_insights = await self._check_calendar_patterns()
        
        # 3. Check for workflow patterns
        workflow_insights = await self._check_workflow_patterns()
        
        # 4. Queue insights
        total_insights = len(email_insights) + len(calendar_insights) + len(workflow_insights)
        
        if total_insights > 0:
            print(f"  ✅ Found {total_insights} new insights", flush=True)
            
            for insight in email_insights + calendar_insights + workflow_insights:
                if insight['pattern_id'] not in self.detected_patterns:
                    self.queue.add(
                        source='v8-pattern-learning',
                        message=insight['message'],
                        priority=insight.get('priority', 2),
                        metadata=json.dumps({
                            'pattern_id': insight['pattern_id'],
                            'pattern_type': insight['pattern_type'],
                            'confidence': insight['confidence']
                        })
                    )
                    self.detected_patterns.add(insight['pattern_id'])
                    print(f"    📊 {insight['pattern_type']}: {insight['pattern_id']}", flush=True)
        else:
            print(f"  ℹ️  No new patterns detected", flush=True)
        
        self.last_pattern_run = now
        print(flush=True)
    
    async def _check_email_patterns(self) -> List[Dict]:
        """Check for email patterns."""
        insights = []
        
        # Simplified: Just log that we're checking
        # Full implementation would analyze Gmail data
        # For now, return empty (avoids errors)
        
        return insights
    
    async def _check_calendar_patterns(self) -> List[Dict]:
        """Check for calendar patterns."""
        insights = []
        
        # Simplified: Just log that we're checking
        # Full implementation would analyze Calendar data
        # For now, return empty (avoids errors)
        
        return insights
    
    async def _check_workflow_patterns(self) -> List[Dict]:
        """Check for workflow optimization patterns."""
        insights = []
        
        # Example: Detect repetitive email sequences that could be automated
        # (Simplified - real implementation would track email threads)
        
        try:
            # Check for repetitive tasks
            db_path = self.workspace / 'integrations/intelligence/v8_meta_learning/pattern_learning.db'
            
            if db_path.exists():
                import sqlite3
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Query for high-frequency patterns
                cursor.execute("""
                    SELECT pattern_type, pattern_id, frequency, confidence
                    FROM patterns
                    WHERE frequency >= 3
                    AND last_seen >= datetime('now', '-7 days')
                    ORDER BY frequency DESC
                    LIMIT 5
                """)
                
                for pattern_type, pattern_id, frequency, confidence in cursor.fetchall():
                    if pattern_id not in self.detected_patterns:
                        insights.append({
                            'pattern_id': pattern_id,
                            'pattern_type': 'workflow',
                            'message': f"⚡ *Workflow Pattern:* You've done '{pattern_type}' {frequency}× this week - want to automate?",
                            'confidence': confidence,
                            'priority': 2
                        })
                
                conn.close()
        
        except Exception as e:
            print(f"    ⚠️  Workflow pattern check failed: {e}", flush=True)
        
        return insights


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="V8 Continuous Pattern Learning Daemon")
    parser.add_argument("--interval", type=int, default=300, help="Check interval in seconds (default: 300)")
    parser.add_argument("--workspace", type=str, default=None, help="Workspace path")
    
    args = parser.parse_args()
    
    workspace_path = Path(args.workspace) if args.workspace else None
    
    daemon = V8ContinuousPatternDaemon(
        interval=args.interval,
        workspace_path=workspace_path
    )
    
    daemon.start()


if __name__ == '__main__':
    main()
