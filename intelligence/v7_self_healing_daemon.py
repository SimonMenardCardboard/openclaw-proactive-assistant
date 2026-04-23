#!/usr/bin/env python3
"""
Intelligence Layer V7: Self-Healing Daemon

Main daemon that orchestrates self-healing:
- Monitors system health continuously
- Diagnoses failures automatically
- Executes pre-approved repairs
- Logs all actions for audit
- Notifies user only for novel failures

Run modes:
- dry-run: Log what would be done, don't execute
- live: Execute repairs autonomously
"""

import time
import json
import signal
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
import argparse

from v7_system_health_monitor import SystemHealthMonitor, HealthAlert
from v7_dependency_graph import DependencyGraph
from v7_auto_diagnosis import AutoDiagnosis
from v7_self_repair import SelfRepair

try:
    from v7_telegram_notifier import V7TelegramNotifier
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False


class SelfHealingDaemon:
    """Main self-healing daemon."""
    
    def __init__(self, workspace: Optional[Path] = None, dry_run: bool = False, check_interval: int = 60):
        """
        Initialize self-healing daemon.
        
        Args:
            workspace: Workspace root
            dry_run: If True, log actions but don't execute
            check_interval: Seconds between health checks
        """
        if workspace is None:
            workspace = Path.home() / ".openclaw" / "workspace"
        
        self.workspace = Path(workspace)
        self.dry_run = dry_run
        self.check_interval = check_interval
        self.running = False
        
        # Initialize components
        self.health_monitor = SystemHealthMonitor(workspace)
        self.dependency_graph = DependencyGraph(workspace)
        self.diagnosis_engine = AutoDiagnosis(workspace)
        self.repair_engine = SelfRepair(workspace, dry_run=dry_run)
        
        # Initialize Telegram notifier
        if TELEGRAM_AVAILABLE:
            diagnostics_db = workspace / "integrations/intelligence/diagnostics.db"
            self.notifier = V7TelegramNotifier(diagnostics_db)
        else:
            self.notifier = None
        
        # State tracking
        self.last_check = None
        self.repairs_attempted = 0
        self.repairs_succeeded = 0
        self.repairs_failed = 0
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print(f"\n[{datetime.now().isoformat()}] Received signal {signum}, shutting down...", flush=True)
        self.running = False
    
    def start(self):
        """Start the daemon."""
        mode = "DRY-RUN" if self.dry_run else "LIVE"
        print(f"[{datetime.now().isoformat()}] Self-Healing Daemon starting [{mode}]", flush=True)
        print(f"  Check interval: {self.check_interval}s", flush=True)
        print(f"  Workspace: {self.workspace}", flush=True)
        print(flush=True)
        
        self.running = True
        
        while self.running:
            try:
                self._health_check_cycle()
                
                if self.running:
                    time.sleep(self.check_interval)
            
            except KeyboardInterrupt:
                break
            
            except Exception as e:
                print(f"[{datetime.now().isoformat()}] Error in health check: {e}", flush=True)
                if self.running:
                    time.sleep(self.check_interval)
        
        print(f"\n[{datetime.now().isoformat()}] Self-Healing Daemon stopped", flush=True)
        self._print_stats()
    
    def _health_check_cycle(self):
        """Execute one health check cycle."""
        now = datetime.now()
        print(f"[{now.isoformat()}] Health check starting...", flush=True)
        
        # Check all services
        health_map = self.health_monitor.check_all_services()
        
        # Count health status
        healthy = sum(1 for h in health_map.values() if h.status == "healthy")
        degraded = sum(1 for h in health_map.values() if h.status == "degraded")
        failed = sum(1 for h in health_map.values() if h.status == "failed")
        
        print(f"  Status: {healthy} healthy, {degraded} degraded, {failed} failed", flush=True)
        
        if failed == 0 and degraded == 0:
            print(f"  ✅ All systems healthy\n", flush=True)
            self.last_check = now
            return
        
        # Get failed services
        failed_services = self.health_monitor.get_failed_services()
        
        if not failed_services:
            print(f"  ⚠️  {degraded} degraded services (monitoring)\n", flush=True)
            self.last_check = now
            return
        
        print(f"  ❌ {len(failed_services)} failed services detected", flush=True)
        
        # CRITICAL: Alert immediately if critical services are down
        critical_services = [
            "com.openclaw.proactive-daemon-v2",
            "com.openclaw.v7-self-healing",
            "api_google_oauth_default"
        ]
        critical_failed = [s for s in failed_services if s.name in critical_services]
        
        if critical_failed and self.notifier:
            for service in critical_failed:
                print(f"  🚨 CRITICAL: {service.name} is down! Sending alert...", flush=True)
                try:
                    text = f"🚨 **CRITICAL SERVICE DOWN**\n\n"
                    text += f"**Service:** {service.name}\n"
                    text += f"**Status:** {service.status}\n"
                    text += f"**Error:** {service.error_message or 'Unknown'}\n"
                    text += f"**Time:** {now.strftime('%I:%M %p')}\n\n"
                    text += f"V7 will attempt auto-repair..."
                    
                    import requests
                    token = self.notifier.token
                    chat_id = self.notifier.chat_id
                    if token:
                        requests.post(
                            f"https://api.telegram.org/bot{token}/sendMessage",
                            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
                            timeout=5
                        )
                except Exception as e:
                    print(f"  Failed to send critical alert: {e}", flush=True)
        
        # Diagnose failures
        diagnoses = []
        for service in failed_services:
            diagnosis = self.diagnosis_engine.diagnose(service.name)
            if diagnosis:
                diagnoses.append(diagnosis)
                print(f"     - {service.name}: {diagnosis.root_cause} (confidence: {diagnosis.confidence:.0%})", flush=True)
        
        if not diagnoses:
            print(f"  ⚠️  Could not diagnose failures (manual intervention needed)\n", flush=True)
            self.last_check = now
            return
        
        # Attempt repairs
        print(f"\n  Evaluating repairs...", flush=True)
        
        for diagnosis in diagnoses:
            if self.repair_engine.can_auto_repair(diagnosis):
                print(f"  🔧 Auto-repairing: {diagnosis.service}", flush=True)
                print(f"     Template: {diagnosis.fix_template}", flush=True)
                print(f"     Risk: {self.repair_engine.templates[diagnosis.fix_template].risk_level:.0%}", flush=True)
                
                self.repairs_attempted += 1
                
                try:
                    execution = self.repair_engine.execute_repair(diagnosis)
                    
                    if execution.status == "success":
                        print(f"     ✅ Repair succeeded ({execution.steps_completed} steps)", flush=True)
                        self.repairs_succeeded += 1
                    else:
                        print(f"     ❌ Repair failed: {execution.error_message}", flush=True)
                        self.repairs_failed += 1
                
                except Exception as e:
                    print(f"     ❌ Repair error: {e}", flush=True)
                    self.repairs_failed += 1
            
            else:
                print(f"  ⚠️  Cannot auto-repair: {diagnosis.service}", flush=True)
                reason = "No template" if not diagnosis.fix_template else f"Risk too high or low confidence"
                print(f"     Reason: {reason}", flush=True)
                print(f"     Manual fix: {diagnosis.suggested_fix}", flush=True)
                
                # Create alert for manual intervention
                alert = HealthAlert(
                    service=diagnosis.service,
                    severity="warning" if diagnosis.confidence > 0.5 else "info",
                    message=diagnosis.root_cause,
                    root_cause=diagnosis.root_cause,
                    suggested_fix=diagnosis.suggested_fix,
                    timestamp=now.isoformat()
                )
                self.health_monitor.create_alert(alert)
                
                # Send Telegram notification
                diagnosis_id = None
                if self.notifier and diagnosis.confidence > 0.6 and diagnosis_id:
                    try:
                        diagnosis_id = self.diagnosis_engine.last_diagnosis_id
                        self.notifier.send_diagnosis_alert(
                            diagnosis_id=diagnosis_id,
                            service=diagnosis.service,
                            failure_type=diagnosis.failure_type,
                            root_cause=diagnosis.root_cause,
                            suggested_fix=diagnosis.suggested_fix,
                            confidence=diagnosis.confidence
                        )
                    except Exception as e:
                        print(f"     ⚠️  Failed to send Telegram alert: {e}", flush=True)
        
        print(flush=True)
        self.last_check = now
    
    def _print_stats(self):
        """Print daemon statistics."""
        print("\nDaemon Statistics:", flush=True)
        print(f"  Repairs attempted: {self.repairs_attempted}", flush=True)
        print(f"  Repairs succeeded: {self.repairs_succeeded}", flush=True)
        print(f"  Repairs failed: {self.repairs_failed}", flush=True)
        if self.repairs_attempted > 0:
            success_rate = (self.repairs_succeeded / self.repairs_attempted) * 100
            print(f"  Success rate: {success_rate:.1f}%", flush=True)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Intelligence Layer V7: Self-Healing Daemon")
    parser.add_argument("--dry-run", action="store_true", help="Log actions but don't execute")
    parser.add_argument("--interval", type=int, default=60, help="Check interval in seconds (default: 60)")
    parser.add_argument("--workspace", type=Path, help="Workspace directory")
    parser.add_argument("--once", action="store_true", help="Run once and exit (for testing)")
    
    args = parser.parse_args()
    
    daemon = SelfHealingDaemon(
        workspace=args.workspace,
        dry_run=args.dry_run,
        check_interval=args.interval
    )
    
    if args.once:
        # Run single health check
        daemon._health_check_cycle()
        daemon._print_stats()
    else:
        # Run continuously
        daemon.start()


if __name__ == "__main__":
    main()
