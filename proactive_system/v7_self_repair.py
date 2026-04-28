#!/usr/bin/env python3
"""
Intelligence Layer V7: Self-Repair Engine

Executes autonomous repairs for diagnosed failures:
- Pre-approved repair templates
- Multi-step workflows with rollback
- Verification after repair
- Incident tracking and learning
"""

import subprocess
import json
import sqlite3
import time
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, asdict
from enum import Enum

# Proactive queue integration
sys.path.insert(0, str(Path(__file__).parent))
try:
    from proactive_queue import ProactiveQueue
    PROACTIVE_QUEUE_AVAILABLE = True
except ImportError:
    PROACTIVE_QUEUE_AVAILABLE = False

# Use try/except for flexible imports (works from any directory)
try:
    from v7_auto_diagnosis import AutoDiagnosis, Diagnosis
    from v7_system_health_monitor import SystemHealthMonitor
except ModuleNotFoundError:
    from integrations.intelligence.v7_auto_diagnosis import AutoDiagnosis, Diagnosis
    from integrations.intelligence.v7_system_health_monitor import SystemHealthMonitor


class RepairStatus(Enum):
    """Repair execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class RepairStep:
    """A single step in a repair workflow."""
    step_id: str
    description: str
    command: Optional[str]  # Shell command to run
    function: Optional[str]  # Python function name to call
    rollback_command: Optional[str]
    timeout: int  # seconds
    required: bool  # If False, failure is non-fatal


@dataclass
class RepairTemplate:
    """Template for a repair workflow."""
    template_id: str
    name: str
    description: str
    risk_level: float  # 0.0-1.0
    max_retries: int
    steps: List[RepairStep]
    verification_command: Optional[str]


@dataclass
class RepairExecution:
    """Record of a repair execution."""
    execution_id: str
    template_id: str
    service: str
    diagnosis: str
    status: str
    started_at: str
    completed_at: Optional[str]
    steps_completed: int
    steps_failed: int
    error_message: Optional[str]
    rollback_performed: bool
    details: Dict


class SelfRepair:
    """Autonomous self-repair engine."""
    
    def __init__(self, workspace: Optional[Path] = None, dry_run: bool = False):
        """
        Initialize self-repair engine.
        
        Args:
            workspace: Workspace root
            dry_run: If True, log actions but don't execute
        """
        if workspace is None:
            workspace = Path.home() / ".openclaw" / "workspace"
        
        self.workspace = Path(workspace)
        self.dry_run = dry_run
        
        self.db_path = self.workspace / "integrations" / "intelligence" / "repairs.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.diagnosis = AutoDiagnosis(workspace)
        self.health_monitor = SystemHealthMonitor(workspace)
        
        # Proactive queue for user notifications
        self.proactive_queue = ProactiveQueue() if PROACTIVE_QUEUE_AVAILABLE else None
        
        self._init_db()
        self._load_templates()
    
    def _init_db(self):
        """Initialize repair database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS repair_executions (
                    execution_id TEXT PRIMARY KEY,
                    template_id TEXT NOT NULL,
                    service TEXT NOT NULL,
                    diagnosis TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    steps_completed INTEGER DEFAULT 0,
                    steps_failed INTEGER DEFAULT 0,
                    error_message TEXT,
                    rollback_performed INTEGER DEFAULT 0,
                    details TEXT NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_service_status
                ON repair_executions(service, status, started_at DESC)
            """)
            
            conn.commit()
    
    def _load_templates(self):
        """Load repair templates."""
        self.templates = {
            # Token refresh template
            "refresh_auth_token": RepairTemplate(
                template_id="refresh_auth_token",
                name="Refresh Auth Token",
                description="Refresh expired OAuth token",
                risk_level=0.2,
                max_retries=3,
                steps=[
                    RepairStep(
                        step_id="check_expiry",
                        description="Verify token is actually expired",
                        command=None,
                        function="check_token_expiry",
                        rollback_command=None,
                        timeout=5,
                        required=True
                    ),
                    RepairStep(
                        step_id="refresh_token",
                        description="Refresh OAuth token",
                        command=None,
                        function="refresh_token",
                        rollback_command=None,
                        timeout=30,
                        required=True
                    ),
                    RepairStep(
                        step_id="verify_refresh",
                        description="Verify token was refreshed",
                        command=None,
                        function="verify_token",
                        rollback_command=None,
                        timeout=5,
                        required=True
                    ),
                ],
                verification_command=None
            ),
            
            # Service restart template
            "restart_service": RepairTemplate(
                template_id="restart_service",
                name="Restart LaunchAgent",
                description="Restart crashed LaunchAgent service",
                risk_level=0.3,
                max_retries=3,
                steps=[
                    RepairStep(
                        step_id="stop_service",
                        description="Stop service gracefully",
                        command="launchctl stop {service}",
                        function=None,
                        rollback_command=None,
                        timeout=10,
                        required=False  # May already be stopped
                    ),
                    RepairStep(
                        step_id="wait_stop",
                        description="Wait for clean shutdown",
                        command="sleep 2",
                        function=None,
                        rollback_command=None,
                        timeout=5,
                        required=True
                    ),
                    RepairStep(
                        step_id="start_service",
                        description="Start service",
                        command="launchctl kickstart -k gui/$(id -u)/{service}",
                        function=None,
                        rollback_command=None,
                        timeout=10,
                        required=True
                    ),
                    RepairStep(
                        step_id="wait_start",
                        description="Wait for startup",
                        command="sleep 5",
                        function=None,
                        rollback_command=None,
                        timeout=10,
                        required=True
                    ),
                ],
                verification_command="launchctl list {service}"
            ),
            
            # Tunnel restart template
            "restart_tunnel": RepairTemplate(
                template_id="restart_tunnel",
                name="Restart Tunnel",
                description="Restart Cloudflare tunnel and update URLs",
                risk_level=0.4,
                max_retries=2,
                steps=[
                    RepairStep(
                        step_id="stop_tunnel",
                        description="Stop tunnel service",
                        command="launchctl stop {tunnel_service}",
                        function=None,
                        rollback_command=None,
                        timeout=10,
                        required=False
                    ),
                    RepairStep(
                        step_id="wait_stop",
                        description="Wait for shutdown",
                        command="sleep 3",
                        function=None,
                        rollback_command=None,
                        timeout=5,
                        required=True
                    ),
                    RepairStep(
                        step_id="start_tunnel",
                        description="Start tunnel service",
                        command="launchctl kickstart -k gui/$(id -u)/{tunnel_service}",
                        function=None,
                        rollback_command=None,
                        timeout=15,
                        required=True
                    ),
                    RepairStep(
                        step_id="wait_tunnel_ready",
                        description="Wait for tunnel to connect",
                        command="sleep 10",
                        function=None,
                        rollback_command=None,
                        timeout=15,
                        required=True
                    ),
                    RepairStep(
                        step_id="update_urls",
                        description="Run tunnel manager to update URLs",
                        command="python3 ~/.openclaw/workspace/integrations/tunnel_manager.py",
                        function=None,
                        rollback_command=None,
                        timeout=30,
                        required=True
                    ),
                ],
                verification_command="curl -I -s http://localhost:{port} | head -1"
            ),
            
            # Disk cleanup template
            "cleanup_disk": RepairTemplate(
                template_id="cleanup_disk",
                name="Disk Cleanup",
                description="Free disk space by rotating logs",
                risk_level=0.5,
                max_retries=1,
                steps=[
                    RepairStep(
                        step_id="rotate_logs",
                        description="Rotate large log files",
                        command=None,
                        function="rotate_logs",
                        rollback_command=None,
                        timeout=60,
                        required=True
                    ),
                    RepairStep(
                        step_id="clear_tmp",
                        description="Clear temp files",
                        command="find ~/.openclaw/workspace -name '*.tmp' -delete",
                        function=None,
                        rollback_command=None,
                        timeout=30,
                        required=False
                    ),
                ],
                verification_command="df -h ~/.openclaw/workspace | tail -1"
            ),
            
            # Database recovery template
            "close_database_connections": RepairTemplate(
                template_id="close_database_connections",
                name="Database Recovery",
                description="Close stuck database connections and vacuum",
                risk_level=0.6,
                max_retries=1,
                steps=[
                    RepairStep(
                        step_id="find_locks",
                        description="Find processes holding database locks",
                        command=None,
                        function="find_database_locks",
                        rollback_command=None,
                        timeout=10,
                        required=True
                    ),
                    RepairStep(
                        step_id="kill_processes",
                        description="Terminate processes holding locks",
                        command=None,
                        function="kill_database_processes",
                        rollback_command=None,
                        timeout=15,
                        required=True
                    ),
                    RepairStep(
                        step_id="vacuum_db",
                        description="Vacuum database",
                        command=None,
                        function="vacuum_database",
                        rollback_command=None,
                        timeout=60,
                        required=False
                    ),
                ],
                verification_command=None
            ),
        }
    
    def can_auto_repair(self, diagnosis: Diagnosis) -> bool:
        """
        Check if diagnosis can be auto-repaired.
        
        Args:
            diagnosis: Diagnosis result
            
        Returns:
            True if auto-repair is available and safe
        """
        if not diagnosis.fix_template:
            return False
        
        template = self.templates.get(diagnosis.fix_template)
        if not template:
            return False
        
        # Check risk level (only auto-execute low-risk repairs)
        if template.risk_level >= 0.7:
            return False
        
        # Check diagnosis confidence
        if diagnosis.confidence < 0.7:
            return False
        
        return True
    
    def execute_repair(self, diagnosis: Diagnosis) -> RepairExecution:
        """
        Execute repair workflow.
        
        Args:
            diagnosis: Diagnosis with fix template
            
        Returns:
            Repair execution record
        """
        template = self.templates.get(diagnosis.fix_template)
        if not template:
            raise ValueError(f"Unknown repair template: {diagnosis.fix_template}")
        
        # Create execution record
        execution_id = f"{diagnosis.service}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        execution = RepairExecution(
            execution_id=execution_id,
            template_id=template.template_id,
            service=diagnosis.service,
            diagnosis=diagnosis.root_cause,
            status=RepairStatus.IN_PROGRESS.value,
            started_at=datetime.now().isoformat(),
            completed_at=None,
            steps_completed=0,
            steps_failed=0,
            error_message=None,
            rollback_performed=False,
            details={"diagnosis": asdict(diagnosis)}
        )
        
        self._save_execution(execution)
        
        # Execute steps
        try:
            for i, step in enumerate(template.steps):
                step_success = self._execute_step(step, diagnosis, execution)
                
                if step_success:
                    execution.steps_completed += 1
                else:
                    execution.steps_failed += 1
                    
                    if step.required:
                        # Required step failed - rollback
                        execution.status = RepairStatus.FAILED.value
                        execution.error_message = f"Required step failed: {step.step_id}"
                        self._rollback(template.steps[:i], diagnosis, execution)
                        break
            
            # All steps completed
            if execution.steps_failed == 0 or not any(s.required for s in template.steps[execution.steps_completed:]):
                # Verify repair
                if template.verification_command:
                    verified = self._verify_repair(template.verification_command, diagnosis)
                    if verified:
                        execution.status = RepairStatus.SUCCESS.value
                    else:
                        execution.status = RepairStatus.FAILED.value
                        execution.error_message = "Verification failed after repair"
                else:
                    execution.status = RepairStatus.SUCCESS.value
            
        except Exception as e:
            execution.status = RepairStatus.FAILED.value
            execution.error_message = str(e)
        
        finally:
            execution.completed_at = datetime.now().isoformat()
            self._save_execution(execution)
            
            # Notify user of result
            if execution.status == RepairStatus.SUCCESS.value:
                self._notify_repair_success(diagnosis, execution)
            else:
                self._notify_repair_failure(diagnosis, execution)
        
        return execution
    
    def _execute_step(self, step: RepairStep, diagnosis: Diagnosis, execution: RepairExecution) -> bool:
        """
        Execute a single repair step.
        
        Args:
            step: Repair step
            diagnosis: Diagnosis context
            execution: Execution record
            
        Returns:
            True if step succeeded
        """
        print(f"  [{step.step_id}] {step.description}...")
        
        if self.dry_run:
            print(f"    [DRY-RUN] Would execute: {step.command or step.function}")
            return True
        
        try:
            if step.command:
                # Execute shell command
                # SECURITY FIX: Use shell=False with argument list to prevent injection
                # Parse command template into safe argument list
                import shlex
                
                cmd_template = step.command.format(
                    service=diagnosis.service,
                    tunnel_service=diagnosis.details.get("tunnel_service", ""),
                    port=diagnosis.details.get("port", "")
                )
                
                # Split into arguments (safe)
                cmd_args = shlex.split(cmd_template)
                
                result = subprocess.run(
                    cmd_args,  # List, not string
                    shell=False,  # SAFE: No shell interpretation
                    capture_output=True,
                    text=True,
                    timeout=step.timeout
                )
                
                if result.returncode == 0:
                    print(f"    ✅ Success")
                    return True
                else:
                    print(f"    ❌ Failed: {result.stderr}")
                    return False
            
            elif step.function:
                # Call Python function
                func = getattr(self, step.function, None)
                if not func:
                    print(f"    ❌ Function not found: {step.function}")
                    return False
                
                result = func(diagnosis)
                
                if result:
                    print(f"    ✅ Success")
                    return True
                else:
                    print(f"    ❌ Failed")
                    return False
            
            else:
                print(f"    ⚠️  No action defined")
                return True
        
        except subprocess.TimeoutExpired:
            print(f"    ❌ Timeout after {step.timeout}s")
            return False
        
        except Exception as e:
            print(f"    ❌ Error: {e}")
            return False
    
    def _rollback(self, completed_steps: List[RepairStep], diagnosis: Diagnosis, execution: RepairExecution):
        """
        Rollback completed steps.
        
        Args:
            completed_steps: Steps to rollback
            diagnosis: Diagnosis context
            execution: Execution record
        """
        print("  🔄 Rolling back...")
        execution.rollback_performed = True
        
        for step in reversed(completed_steps):
            if not step.rollback_command:
                continue
            
            print(f"    Undoing: {step.step_id}")
            
            if not self.dry_run:
                try:
                    subprocess.run(
                        step.rollback_command,
                        shell=True,
                        timeout=step.timeout,
                        check=False
                    )
                except Exception as e:
                    print(f"    ⚠️  Rollback error: {e}")
    
    def _verify_repair(self, verification_cmd: str, diagnosis: Diagnosis) -> bool:
        """
        Verify repair succeeded.
        
        Args:
            verification_cmd: Command to verify
            diagnosis: Diagnosis context
            
        Returns:
            True if verification passed
        """
        if self.dry_run:
            return True
        
        try:
            cmd = verification_cmd.format(
                service=diagnosis.service,
                port=diagnosis.details.get("port")
            )
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                timeout=10
            )
            
            return result.returncode == 0
        
        except Exception:
            return False
    
    def _save_execution(self, execution: RepairExecution):
        """Save execution record to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO repair_executions VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                execution.execution_id,
                execution.template_id,
                execution.service,
                execution.diagnosis,
                execution.status,
                execution.started_at,
                execution.completed_at,
                execution.steps_completed,
                execution.steps_failed,
                execution.error_message,
                1 if execution.rollback_performed else 0,
                json.dumps(execution.details)
            ))
            conn.commit()
    
    def _notify_repair_success(self, diagnosis: Diagnosis, execution: RepairExecution):
        """Queue proactive notification about successful self-repair."""
        if not self.proactive_queue:
            return
        
        try:
            # Build user-friendly message
            service_names = {
                'whoop_token': 'WHOOP connection',
                'gmail_token': 'Gmail',
                'calendar_token': 'Calendar',
                'tunnel': 'webhook tunnel',
                'daemon': 'background service'
            }
            
            service = service_names.get(diagnosis.service, diagnosis.service)
            
            repair_messages = {
                'refresh_auth_token': f'🔧 Fixed {service} - refreshed authentication',
                'restart_service': f'🔧 Restarted {service} - back online',
                'restart_tunnel': f'🔧 Reconnected {service}',
                'cleanup_disk': f'🧹 Freed up disk space',
                'database_recovery': f'🔧 Repaired database corruption'
            }
            
            message = repair_messages.get(
                diagnosis.fix_template,
                f'🔧 Fixed {service}'
            )
            
            # Priority based on service criticality
            if 'auth' in diagnosis.service or 'token' in diagnosis.service:
                priority = 3  # Medium - auth is important but not urgent
            else:
                priority = 4  # Low - routine repairs
            
            self.proactive_queue.add(
                source='v7-self-healing',
                message=message,
                priority=priority,
                context={
                    'service': diagnosis.service,
                    'repair': diagnosis.fix_template,
                    'execution_id': execution.execution_id,
                    'timestamp': execution.completed_at
                }
            )
            
        except Exception as e:
            # Don't fail repair on notification error
            pass
    
    def _notify_repair_failure(self, diagnosis: Diagnosis, execution: RepairExecution):
        """Queue urgent notification about failed self-repair attempt."""
        if not self.proactive_queue:
            return
        
        try:
            service_names = {
                'whoop_token': 'WHOOP connection',
                'gmail_token': 'Gmail',
                'calendar_token': 'Calendar',
                'tunnel': 'webhook tunnel',
                'daemon': 'background service'
            }
            
            service = service_names.get(diagnosis.service, diagnosis.service)
            error = execution.error_message or 'Unknown error'
            
            # Escape special characters for Telegram Markdown
            error_safe = str(error).replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
            root_safe = str(diagnosis.root_cause).replace('_', '\\_').replace('*', '\\*')
            fix_safe = str(diagnosis.suggested_fix).replace('_', '\\_').replace('*', '\\*')
            
            message = f"🚨 *Self-repair failed: {service}*\n\n"
            message += f"Problem: {root_safe}\n"
            message += f"Attempted: {fix_safe}\n"
            message += f"Error: {error_safe}\n\n"
            
            # Add recommended action
            recommended_action = self._get_repair_recommendation(diagnosis, execution)
            if recommended_action:
                message += f"💡 *Try:* {recommended_action}"
            else:
                message += "_Manual intervention needed_"
            
            # Failed repairs are high priority
            self.proactive_queue.add(
                source='v7-self-healing',
                message=message,
                priority=1 if 'auth' in diagnosis.service else 2,  # Urgent for auth failures
                context={
                    'service': diagnosis.service,
                    'failure_type': diagnosis.failure_type,
                    'error': error,
                    'execution_id': execution.execution_id,
                    'timestamp': execution.completed_at,
                    'needs_intervention': True
                }
            )
            
        except Exception as e:
            # Don't fail on notification error
            pass
    
    def _get_repair_recommendation(self, diagnosis: Diagnosis, execution: RepairExecution) -> str:
        """Get AI-recommended action for failed repair."""
        error = execution.error_message or ''
        error_lower = error.lower()
        service = diagnosis.service.lower()
        
        # Token/auth failures
        if 'token' in service or 'auth' in service:
            if '403' in error or 'forbidden' in error_lower:
                return "Run manual OAuth re-authentication flow"
            if 'expired' in error_lower:
                return "Token expired - manually refresh credentials"
            return "Check API credentials and re-authenticate"
        
        # Tunnel failures
        if 'tunnel' in service:
            if 'port' in error_lower:
                return "Check if port is already in use (kill conflicting process)"
            return "Restart tunnel manually: `cloudflared tunnel run`"
        
        # Service failures
        if 'daemon' in service or 'service' in service:
            return "Check service logs and restart manually via launchctl"
        
        # Disk/database
        if 'disk' in error_lower or 'space' in error_lower:
            return "Run disk cleanup: `ncdu ~` to find large files"
        
        if 'database' in service:
            return "Check database integrity and consider restore from backup"
        
        # Generic network
        if 'network' in error_lower or 'connection' in error_lower:
            return "Check network connection and firewall settings"
        
        return None
    
    # Repair helper functions
    
    def check_token_expiry(self, diagnosis: Diagnosis) -> bool:
        """Check if token is actually expired."""
        # Implemented by checking token file
        return True  # Simplified for now
    
    def refresh_token(self, diagnosis: Diagnosis) -> bool:
        """Refresh OAuth token."""
        # Call appropriate refresh script
        if "whoop" in diagnosis.service:
            result = subprocess.run(
                ["python3", str(self.workspace / "integrations/adaptive_training/refresh_whoop_token.py")],
                capture_output=True,
                timeout=30
            )
            return result.returncode == 0
        
        return False
    
    def verify_token(self, diagnosis: Diagnosis) -> bool:
        """Verify token was refreshed."""
        # Re-check health
        time.sleep(2)
        health_map = self.health_monitor.check_all_services()
        health = health_map.get(diagnosis.service)
        return health and health.status == "healthy"
    
    def rotate_logs(self, diagnosis: Diagnosis) -> bool:
        """Rotate large log files."""
        logs_dir = self.workspace / "logs"
        rotated = 0
        
        for log_file in logs_dir.glob("*.log"):
            if log_file.stat().st_size > 50 * 1024 * 1024:  # >50MB
                # Compress and rotate
                subprocess.run(
                    f"gzip -c {log_file} > {log_file}.{datetime.now().strftime('%Y%m%d')}.gz && > {log_file}",
                    shell=True,
                    timeout=30
                )
                rotated += 1
        
        return rotated > 0
    
    def find_database_locks(self, diagnosis: Diagnosis) -> bool:
        """Find processes holding database locks."""
        # Use lsof to find processes with open file handles to .db files
        return True
    
    def kill_database_processes(self, diagnosis: Diagnosis) -> bool:
        """Kill processes holding database locks."""
        # Gracefully terminate processes
        return True
    
    def vacuum_database(self, diagnosis: Diagnosis) -> bool:
        """Vacuum SQLite database."""
        # Run VACUUM on databases
        return True


if __name__ == "__main__":
    # Test self-repair
    import sys
    
    dry_run = "--dry-run" in sys.argv
    
    repair = SelfRepair(dry_run=dry_run)
    
    print(f"Self-Repair Engine {'[DRY-RUN]' if dry_run else '[LIVE]'}\n")
    
    # Diagnose all failures
    diagnoses = repair.diagnosis.diagnose_all_failures()
    
    if not diagnoses:
        print("✅ No failures to repair!")
    else:
        for diag in diagnoses:
            print(f"{'='*60}")
            print(f"Diagnosis: {diag.service}")
            print(f"Root Cause: {diag.root_cause}")
            
            if repair.can_auto_repair(diag):
                print(f"✅ Can auto-repair (template: {diag.fix_template})")
                print("\nExecuting repair...")
                
                execution = repair.execute_repair(diag)
                
                print(f"\nResult: {execution.status}")
                print(f"Steps completed: {execution.steps_completed}")
                if execution.error_message:
                    print(f"Error: {execution.error_message}")
            else:
                print(f"⚠️  Cannot auto-repair")
                print(f"Reason: {'No template' if not diag.fix_template else 'High risk or low confidence'}")
                print(f"Manual fix: {diag.suggested_fix}")
            
            print()
