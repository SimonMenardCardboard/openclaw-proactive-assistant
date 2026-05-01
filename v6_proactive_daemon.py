#!/usr/bin/env python3
"""
Proactive Daemon - Phase 2 (Action Mode)
Background process that monitors data streams and sends notifications

ENABLED: Telegram notifications for high-confidence observations
"""

import asyncio
import sqlite3
import json
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import logging

# Import monitors and notifier
from monitors import (
    CalendarMonitor,
    RecoveryMonitor,
    NutritionMonitor,
    NewsletterMonitor
)
from monitors_extended import (
    TunnelHealthMonitor,
    AuthTokenMonitor,
    LaunchAgentHealthMonitor,
    WHOOPDataFreshnessMonitor
)
from notifier import TelegramNotifier

# Import V6 Autonomous Executor + Approval Handler + Token Cache
import sys
sys.path.insert(0, str(Path.home() / "workspace/integrations/autonomous_executor"))
from executor import AutonomousExecutor
from approval_handler import ApprovalHandler
from cached_actions import should_refresh_token, mark_token_refreshed, should_send_training_rec, mark_training_rec_sent

# Import Chief of Staff triggers (optional)
try:
    cos_path = Path.home() / ".openclaw" / "workspace" / "integrations" / "intelligence" / "integration"
    sys.path.insert(0, str(cos_path))
    from cos_trigger_handlers import get_trigger_handlers
    COS_AVAILABLE = True
except ImportError:
    COS_AVAILABLE = False
    logging.warning("Chief of Staff triggers not available")


class ProactiveDaemonV2:
    """Main daemon process with notifications enabled"""
    
    def __init__(self, db_path: Path, log_path: Path, notify: bool = True):
        self.db_path = db_path
        self.log_path = log_path
        self.notify_enabled = notify
        self.running = False
        self.check_interval = 60  # seconds
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(log_path),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Safety: Check permissions before doing anything
        self._check_permissions()
        
        # Initialize database
        self._init_database()
        
        # Initialize monitors
        self.monitors = [
            # Original monitors
            CalendarMonitor(db_path),
            RecoveryMonitor(db_path),
            NutritionMonitor(db_path),
            NewsletterMonitor(db_path),
            # Extended monitors (infrastructure health)
            TunnelHealthMonitor(db_path),
            AuthTokenMonitor(db_path),
            LaunchAgentHealthMonitor(db_path),
            WHOOPDataFreshnessMonitor(db_path)
        ]
        
        # Initialize notifier
        self.notifier = TelegramNotifier(min_confidence=0.75) if notify else None
        
        # Initialize V6 Autonomous Executor (for action submission)
        # PARTIAL ROLLOUT: Only safe, reversible actions enabled
        executor_db = Path.home() / "workspace/integrations/autonomous_executor/execution_log.db"
        executor_log = Path.home() / "workspace/logs/autonomous_executor.log"
        self.executor = AutonomousExecutor(executor_db, executor_log, dry_run=False)
        
        # Initialize Approval Handler (Apr 6, 2026)
        approval_log = Path.home() / "workspace/integrations/autonomous_executor/approval_handler.log"
        self.approval_handler = ApprovalHandler(executor_db, approval_log)
        
        # Whitelist for partial rollout - EXPANDED (Apr 6, 2026)
        # Enabled: auth refresh, form reminders, training recs, service restarts
        # All actions now enabled for full V6 rollout
        self.enabled_actions = ['refresh_auth_token', 'send_form_reminder', 'send_training_rec', 'restart_launchagent', 'restart_tunnel']
        self.logger.info(f"✅ V6 Executor PARTIAL ROLLOUT - Enabled actions: {self.enabled_actions}")
        
        # Initialize Chief of Staff triggers (if available)
        self.cos_triggers = None
        if COS_AVAILABLE:
            try:
                self.cos_triggers = get_trigger_handlers()
                self.logger.info("✅ Chief of Staff integration enabled in daemon")
            except Exception as e:
                self.logger.warning(f"⚠️ COS integration failed: {e}")
                self.cos_triggers = None
        
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _init_database(self):
        """Initialize SQLite database with schema"""
        schema_path = Path(__file__).parent / "schema.sql"
        
        if not schema_path.exists():
            self.logger.error(f"Schema file not found: {schema_path}")
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        
        conn = sqlite3.connect(self.db_path)
        with open(schema_path, 'r') as f:
            schema = f.read()
        conn.executescript(schema)
        conn.commit()
        conn.close()
        
        self.logger.info(f"✅ Database initialized: {self.db_path}")
    
    def _check_permissions(self):
        """Safety check: Ensure we're not running as root and have proper permissions"""
        import os
        import getpass
        
        # Never run as root
        if os.getuid() == 0:
            self.logger.error("❌ SAFETY: Running as root is dangerous and not allowed!")
            sys.exit(1)
        
        # Check write permissions
        db_dir = self.db_path.parent
        if not os.access(db_dir, os.W_OK):
            self.logger.error(f"❌ SAFETY: Cannot write to {db_dir}")
            self.logger.error(f"   Fix: sudo chown -R $(whoami):staff ~/workspace/integrations/proactive_daemon/")
            sys.exit(1)
        
        self.logger.info(f"✅ Permission check passed (user: {getpass.getuser()})")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    async def run_monitors(self) -> Dict[str, List[Dict]]:
        """Run all monitors and collect observations"""
        results = {}
        
        for monitor in self.monitors:
            try:
                observations = await monitor.check()
                results[monitor.monitor_type] = observations
                
                if observations:
                    self.logger.info(
                        f"📊 {monitor.monitor_type}: {len(observations)} observation(s)"
                    )
                    for obs in observations:
                        self.logger.info(f"   └─ {obs['type']}: {obs['message']}")
            
            except Exception as e:
                self.logger.error(f"❌ {monitor.monitor_type} failed: {e}", exc_info=True)
                results[monitor.monitor_type] = []
        
        # Trigger Chief of Staff for calendar events
        if self.cos_triggers and 'calendar' in results and results['calendar']:
            self._trigger_cos_calendar(results['calendar'])
        
        return results
    
    def _trigger_cos_calendar(self, calendar_observations: List[Dict]):
        """Trigger Chief of Staff for calendar events."""
        try:
            # Convert calendar observations to COS format
            # Calendar observations contain event data in their 'data' field
            events = []
            for obs in calendar_observations:
                data = obs.get('data', {})
                if 'events' in data:
                    events.extend(data['events'])
            
            if not events:
                return
            
            # Trigger COS calendar sync
            calendar_data = {
                'events': events,
                'sync_timestamp': datetime.now().isoformat()
            }
            
            cos_result = self.cos_triggers.on_calendar_sync(calendar_data)
            
            # Store recommendations for Telegram delivery
            if cos_result.get('recommendations'):
                self._store_cos_recommendations(cos_result['recommendations'])
                self.logger.info(f"📡 COS calendar: {len(cos_result['recommendations'])} recommendations")
        
        except Exception as e:
            self.logger.warning(f"⚠️ COS calendar trigger failed: {e}")
    
    def _store_cos_recommendations(self, recommendations: List[Dict]):
        """Store Chief of Staff recommendations for Telegram delivery."""
        try:
            # Use executor's database for consistency
            executor_db = Path.home() / "workspace/integrations/autonomous_executor/execution_log.db"
            conn = sqlite3.connect(executor_db)
            cursor = conn.cursor()
            
            # Create table if doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cos_recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    title TEXT NOT NULL,
                    context TEXT,
                    actions TEXT,
                    created_at TEXT NOT NULL,
                    delivered BOOLEAN DEFAULT 0,
                    dismissed BOOLEAN DEFAULT 0
                )
            """)
            
            # Insert recommendations
            for rec in recommendations:
                cursor.execute("""
                    INSERT INTO cos_recommendations 
                    (type, priority, title, context, actions, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    rec['type'],
                    rec['priority'],
                    rec['title'],
                    rec.get('context', ''),
                    json.dumps(rec.get('actions', [])),
                    datetime.now().isoformat()
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"❌ Failed to store COS recommendations: {e}")
    
    def process_observations(self, results: Dict[str, List[Dict]]) -> List[Dict]:
        """Process observations and prepare for notification"""
        # Monitors return simplified dicts but log full data to DB
        # Read the full observations from database (most recent per monitor)
        all_observations = []
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for monitor_type, observations in results.items():
            if not observations:
                continue
            
            # Get the most recent observation for this monitor
            cursor.execute("""
                SELECT observation_type, confidence, severity, data
                FROM observations
                WHERE monitor_type = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (monitor_type,))
            
            result = cursor.fetchone()
            if result:
                obs_type, confidence, severity, data_json = result
                data = json.loads(data_json)
                
                full_obs = {
                    'monitor_type': monitor_type,
                    'observation_type': obs_type,
                    'confidence': confidence,
                    'severity': severity,
                    'data': data
                }
                all_observations.append(full_obs)
        
        conn.close()
        return all_observations
    
    def _is_action_enabled(self, action_name: str) -> bool:
        """Check if action is enabled in partial rollout whitelist"""
        return action_name in self.enabled_actions
    
    async def submit_actions(self, observations: List[Dict]):
        """Submit autonomous actions to V6 based on observations"""
        if not self.executor or not observations:
            return
        
        actions_submitted = 0
        actions_skipped = 0
        
        for obs in observations:
            monitor_type = obs['monitor_type']
            obs_type = obs['observation_type']
            data = obs.get('data', {})
            
            # Recovery-based actions (V8 OPTIMIZATION: Cache-aware)
            if monitor_type == 'recovery':
                if obs_type == 'low_recovery':
                    action_name = "send_training_rec"
                    
                    if not self._is_action_enabled(action_name):
                        self.logger.debug(f"⏸️  Skipping {action_name} (not in partial rollout whitelist)")
                        actions_skipped += 1
                        continue
                    
                    recovery_score = data.get('recovery_score', 0)
                    
                    # V8 OPTIMIZATION: Check if we already sent rec for this recovery level
                    if not should_send_training_rec(recovery_score):
                        self.logger.info(f"⏭️  Skipped training rec ({recovery_score}%) - already sent recently")
                        actions_skipped += 1
                        continue
                    
                    # V8 OPTIMIZATION #3: Check cooldown before submitting
                    if not self.executor.check_cooldown(action_name):
                        self.logger.debug(f"⏭️  Skipped {action_name} - on cooldown")
                        actions_skipped += 1
                        continue
                    
                    # Submit training recommendation
                    exec_id = self.executor.submit_action(
                        action_name,
                        {
                            "recovery_score": recovery_score,
                            "recommendation": "technique_only" if recovery_score < 33 else "reduced"
                        }
                    )
                    if exec_id > 0:
                        self.logger.info(f"⚙️  Submitted training rec action (recovery {recovery_score}%)")
                        # Mark as sent in cache (12 hour TTL)
                        mark_training_rec_sent(recovery_score, ttl_minutes=720)
                        actions_submitted += 1
            
            # Tunnel health actions
            elif monitor_type == 'tunnel_health':
                if obs_type in ['tunnel_down', 'tunnel_unreachable']:
                    action_name = "restart_tunnel"
                    
                    if not self._is_action_enabled(action_name):
                        self.logger.debug(f"⏸️  Skipping {action_name} (not in partial rollout whitelist)")
                        actions_skipped += 1
                        continue
                    
                    tunnel_name = data.get('tunnel_name', 'unknown')
                    # Map tunnel names to ports
                    tunnel_ports = {
                        'tunnel-macrofactor': 8765,
                        'tunnel-supplements': 8766,
                        'tunnel-watchapi': 9000
                    }
                    port = tunnel_ports.get(tunnel_name, 8765)
                    
                    # V8 OPTIMIZATION #3: Check cooldown before submitting
                    if not self.executor.check_cooldown(action_name):
                        self.logger.debug(f"⏭️  Skipped {action_name} - on cooldown")
                        actions_skipped += 1
                        continue
                    
                    exec_id = self.executor.submit_action(
                        action_name,
                        {
                            "tunnel_name": tunnel_name,
                            "port": port
                        }
                    )
                    if exec_id > 0:
                        self.logger.info(f"⚙️  Submitted tunnel restart ({tunnel_name})")
                        actions_submitted += 1
            
            # Auth token actions (V8 OPTIMIZATION: Cache-aware)
            elif monitor_type == 'auth_tokens':
                if obs_type in ['token_expired', 'token_expiring_soon', 'token_missing']:
                    service = data.get('service', 'unknown')
                    
                    # V8 OPTIMIZATION: Check cache before submitting
                    if not should_refresh_token(service, f"~/.tokens/{service}"):
                        self.logger.info(f"⏭️  Skipped auth refresh ({service}) - cached token still valid")
                        actions_skipped += 1
                        continue
                    
                    # V8 OPTIMIZATION #3: Check cooldown before submitting
                    if not self.executor.check_cooldown("refresh_auth_token"):
                        self.logger.debug(f"⏭️  Skipped refresh_auth_token - on cooldown")
                        actions_skipped += 1
                        continue
                    
                    exec_id = self.executor.submit_action(
                        "refresh_auth_token",
                        {
                            "service": service,
                            "token_path": f"~/.tokens/{service}"
                        }
                    )
                    if exec_id > 0:
                        self.logger.info(f"⚙️  Submitted auth refresh ({service})")
                        # Mark as refreshed in cache
                        mark_token_refreshed(service, ttl_minutes=60)
                        actions_submitted += 1
            
            # LaunchAgent health actions
            elif monitor_type == 'launchagent_health':
                if obs_type in ['launchagent_stopped', 'launchagent_crashed']:
                    action_name = "restart_launchagent"
                    
                    if not self._is_action_enabled(action_name):
                        self.logger.debug(f"⏸️  Skipping {action_name} (not in partial rollout whitelist)")
                        actions_skipped += 1
                        continue
                    
                    agent_name = data.get('agent_name', 'unknown')
                    
                    # V8 OPTIMIZATION #3: Check cooldown before submitting
                    if not self.executor.check_cooldown(action_name):
                        self.logger.debug(f"⏭️  Skipped {action_name} - on cooldown")
                        actions_skipped += 1
                        continue
                    
                    exec_id = self.executor.submit_action(
                        action_name,
                        {
                            "agent_name": agent_name
                        }
                    )
                    if exec_id > 0:
                        self.logger.info(f"⚙️  Submitted LaunchAgent restart ({agent_name})")
                        actions_submitted += 1
        
        if actions_submitted > 0 or actions_skipped > 0:
            self.logger.info(
                f"🚀 V6 Actions: {actions_submitted} submitted, {actions_skipped} skipped (partial rollout)"
            )
    
    async def send_notifications(self, observations: List[Dict]):
        """Send notifications for high-confidence observations"""
        if not self.notifier or not observations:
            return
        
        # Filter to unique, non-duplicate notifications
        # Avoid spamming same observation every minute
        unique_obs = self._deduplicate_observations(observations)
        
        if unique_obs:
            sent = self.notifier.send_batch(unique_obs)
            if sent > 0:
                self.logger.info(f"📤 Sent {sent} notification(s)")
    
    def _deduplicate_observations(self, observations: List[Dict]) -> List[Dict]:
        """Smart alert deduplication with escalation"""
        try:
            from use_escalation import use_smart_alerts
            return use_smart_alerts(self.db_path, observations)
        except ImportError:
            # Fallback to old logic if module not found
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            unique = []
            for obs in observations:
                # Check if same observation type exists in last 24 hours
                # Changed from 1 hour to allow daily reminders
                cursor.execute("""
                    SELECT COUNT(*) FROM observations
                    WHERE monitor_type = ?
                      AND observation_type = ?
                      AND timestamp >= datetime('now', '-24 hours')
                """, (obs['monitor_type'], obs['observation_type']))
                
                count = cursor.fetchone()[0]
                
                # Only include if this is first occurrence in last 24 hours
                # This gives daily reminders for ongoing issues
                if count <= 2:  # Allow if 2 or fewer recent observations
                    unique.append(obs)
            
            conn.close()
            return unique
    
    async def check_v8_queue(self):
        """Check V8 proactive queue for undelivered insights"""
        v8_queue_path = Path.home() / '.openclaw/workspace/integrations/intelligence/proactive_queue.db'
        
        if not v8_queue_path.exists():
            return []
        
        try:
            conn = sqlite3.connect(v8_queue_path)
            cursor = conn.cursor()
            
            # Get all undelivered user-facing messages, ordered by priority
            cursor.execute("""
                SELECT id, source, priority, message, created_at
                FROM proactive_queue
                WHERE delivered = 0 AND user_facing = 1
                ORDER BY priority ASC, created_at ASC
                LIMIT 10
            """)
            
            messages = cursor.fetchall()
            
            if messages:
                self.logger.info(f"📬 Found {len(messages)} V8 insight(s) to deliver")
                
                # Send each message
                for msg_id, source, priority, message, created_at in messages:
                    if self.notifier:
                        obs = {'message': message, 'confidence': 0.9}
                        success = self.notifier.send(obs)
                        
                        if success:
                            # Mark as delivered
                            cursor.execute("""
                                UPDATE proactive_queue
                                SET delivered = 1, delivered_at = ?
                                WHERE id = ?
                            """, (datetime.now().isoformat(), msg_id))
                            conn.commit()
                            self.logger.info(f"   ✅ Delivered: {source} (priority {priority})")
                        else:
                            self.logger.warning(f"   ⚠️  Failed to deliver: {source}")
            
            conn.close()
            return messages
            
        except Exception as e:
            self.logger.error(f"❌ Error checking V8 queue: {e}")
            return []
    
    async def monitoring_loop(self):
        """Main monitoring loop"""
        mode = "ACTION MODE (Notifications Enabled)" if self.notify_enabled else "READ-ONLY MODE"
        self.logger.info(f"🚀 Proactive Daemon V2 started - {mode}")
        self.logger.info(f"   Check interval: {self.check_interval}s")
        self.logger.info(f"   Database: {self.db_path}")
        self.logger.info(f"   Log: {self.log_path}")
        self.logger.info(f"   V8 integration: ENABLED (checks proactive_queue every cycle)")
        
        if self.notify_enabled:
            self.logger.info(f"   Notifications: Telegram (min confidence: 75%)")
        
        self.logger.info("")
        
        self.running = True
        cycle_count = 0
        
        while self.running:
            cycle_count += 1
            self.logger.info(f"{'='*60}")
            self.logger.info(f"Cycle #{cycle_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"{'='*60}")
            
            try:
                # Run all monitors
                results = await self.run_monitors()
                
                # Process observations
                observations = self.process_observations(results)
                
                # Submit actions to V6 executor
                await self.submit_actions(observations)
                
                # Check for pending approvals (every cycle)
                try:
                    await self.approval_handler.check_and_notify()
                except Exception as e:
                    self.logger.error(f"Error checking approvals: {e}")
                
                # Send notifications if enabled
                if self.notify_enabled:
                    await self.send_notifications(observations)
                
                # Check V8 proactive queue for insights
                if self.notify_enabled:
                    await self.check_v8_queue()
                
                # Count total observations
                total_obs = len(observations)
                
                if total_obs == 0:
                    self.logger.info("✅ All systems nominal - no patterns detected")
                else:
                    self.logger.info(f"📌 Total observations: {total_obs}")
                
                self.logger.info("")
                self.logger.info(f"💤 Sleeping for {self.check_interval}s...")
                self.logger.info("")
                
            except Exception as e:
                self.logger.error(f"❌ Monitoring cycle failed: {e}", exc_info=True)
            
            # Sleep until next check
            await asyncio.sleep(self.check_interval)
        
        self.logger.info("👋 Daemon stopped gracefully")
    
    def run(self):
        """Start the daemon"""
        try:
            asyncio.run(self.monitoring_loop())
        except KeyboardInterrupt:
            self.logger.info("Interrupted by user")
        except Exception as e:
            self.logger.error(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)


def main():
    """Entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Proactive Daemon V2')
    parser.add_argument('--no-notify', action='store_true', 
                       help='Disable notifications (read-only mode)')
    args = parser.parse_args()
    
    # Paths
    workspace = Path.home() / "workspace"
    daemon_dir = workspace / "integrations" / "proactive_daemon"
    db_path = daemon_dir / "working_memory.db"
    log_path = workspace / "logs" / "proactive_daemon.log"
    
    # Ensure directories exist
    daemon_dir.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Start daemon
    daemon = ProactiveDaemonV2(db_path, log_path, notify=not args.no_notify)
    daemon.run()


if __name__ == "__main__":
    main()
