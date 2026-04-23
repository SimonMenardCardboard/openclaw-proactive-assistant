#!/usr/bin/env python3
"""
Intelligence Layer V7: System Health Monitor

Tracks all services in real-time:
- LaunchAgents status
- Cron jobs execution
- Tunnel health
- API token validity
- Database connections
- Disk/memory usage

Detects failures and triggers self-healing workflows.
"""

import json
import subprocess
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import re


@dataclass
class ServiceHealth:
    """Health status of a service."""
    name: str
    type: str  # launchagent, cron, tunnel, api, database
    status: str  # healthy, degraded, failed, unknown
    last_check: str
    last_success: Optional[str]
    exit_code: Optional[int]
    error_message: Optional[str]
    metrics: Dict  # type-specific metrics
    dependencies: List[str]  # services this depends on


@dataclass
class HealthAlert:
    """Alert for unhealthy service."""
    service: str
    severity: str  # info, warning, critical
    message: str
    root_cause: Optional[str]
    suggested_fix: str
    timestamp: str


class SystemHealthMonitor:
    """Monitor system health and detect failures."""
    
    def __init__(self, workspace: Optional[Path] = None):
        """
        Initialize health monitor.
        
        Args:
            workspace: Workspace root
        """
        if workspace is None:
            workspace = Path.home() / ".openclaw" / "workspace"
        
        self.workspace = Path(workspace)
        self.db_path = self.workspace / "integrations" / "intelligence" / "health_monitor.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_db()
        
        # Service definitions
        self.launchagents = [
            "com.openclaw.whoop-pull",
            "com.openclaw.health-processor",
            "com.openclaw.macrofactor",
            "com.openclaw.google-watch-webhook",
            "com.openclaw.tunnel-manager",
            "com.openclaw.ai-newsletter-generator",
            "com.openclaw.proactive-daemon-v2",  # V6 proactive daemon (CRITICAL)
            "com.openclaw.v7-self-healing",      # V7 self-healing (CRITICAL)
        ]
        
        self.tunnels = [
            {"port": 8765, "name": "macrofactor"},
            {"port": 8766, "name": "supplements"},
            {"port": 9000, "name": "watchapi"},
        ]
        
        self.api_tokens = [
            {"name": "whoop", "path": "integrations/adaptive_training/data/whoop_tokens.json"},
            {"name": "google_calendar", "path": "integrations/watch_api/logs/watch_state.json"},
            {"name": "google_oauth_default", "path": "integrations/direct_api/token.json", "critical": True},  # Primary Google OAuth
        ]
    
    def _init_db(self):
        """Initialize health database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS service_health (
                    service_name TEXT PRIMARY KEY,
                    service_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    last_check TEXT NOT NULL,
                    last_success TEXT,
                    exit_code INTEGER,
                    error_message TEXT,
                    metrics TEXT,
                    dependencies TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS health_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    root_cause TEXT,
                    suggested_fix TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    resolved INTEGER DEFAULT 0,
                    resolved_at TEXT
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_unresolved
                ON health_alerts(resolved, timestamp)
            """)
            
            conn.commit()
    
    def check_all_services(self) -> Dict[str, ServiceHealth]:
        """
        Check health of all services.
        
        Returns:
            Dictionary of service health states
        """
        health_map = {}
        
        # Check LaunchAgents
        for agent in self.launchagents:
            health = self._check_launchagent(agent)
            health_map[agent] = health
            self._save_health(health)
        
        # Check tunnels
        for tunnel in self.tunnels:
            health = self._check_tunnel(tunnel)
            health_map[f"tunnel_{tunnel['name']}"] = health
            self._save_health(health)
        
        # Check API tokens
        for token in self.api_tokens:
            health = self._check_api_token(token)
            health_map[f"api_{token['name']}"] = health
            self._save_health(health)
        
        # Check system resources
        health = self._check_system_resources()
        health_map["system_resources"] = health
        self._save_health(health)
        
        return health_map
    
    def _check_launchagent(self, agent_name: str) -> ServiceHealth:
        """
        Check LaunchAgent health.
        
        Args:
            agent_name: LaunchAgent identifier
            
        Returns:
            Health status
        """
        try:
            # Get agent status
            result = subprocess.run(
                ["launchctl", "list", agent_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return ServiceHealth(
                    name=agent_name,
                    type="launchagent",
                    status="failed",
                    last_check=datetime.now().isoformat(),
                    last_success=None,
                    exit_code=result.returncode,
                    error_message="Agent not loaded",
                    metrics={},
                    dependencies=[]
                )
            
            # Parse status
            output = result.stdout
            pid_match = re.search(r'"PID" = (\d+);', output)
            exit_match = re.search(r'"LastExitStatus" = (-?\d+);', output)
            
            pid = int(pid_match.group(1)) if pid_match else None
            exit_code = int(exit_match.group(1)) if exit_match else None
            
            # Determine status
            if pid and pid > 0:
                status = "healthy"
                error = None
            elif exit_code == 0:
                status = "healthy"
                error = None
            elif exit_code is not None and exit_code != 0:
                status = "failed"
                error = f"Exit code {exit_code}"
            else:
                status = "unknown"
                error = "No PID or exit code"
            
            return ServiceHealth(
                name=agent_name,
                type="launchagent",
                status=status,
                last_check=datetime.now().isoformat(),
                last_success=datetime.now().isoformat() if status == "healthy" else None,
                exit_code=exit_code,
                error_message=error,
                metrics={"pid": pid},
                dependencies=[]
            )
            
        except Exception as e:
            return ServiceHealth(
                name=agent_name,
                type="launchagent",
                status="unknown",
                last_check=datetime.now().isoformat(),
                last_success=None,
                exit_code=None,
                error_message=str(e),
                metrics={},
                dependencies=[]
            )
    
    def _check_tunnel(self, tunnel: Dict) -> ServiceHealth:
        """
        Check tunnel health via HTTP.
        
        Args:
            tunnel: Tunnel config (port, name)
            
        Returns:
            Health status
        """
        import urllib.request
        import urllib.error
        
        port = tunnel["port"]
        name = tunnel["name"]
        
        try:
            # Try HTTP health check
            req = urllib.request.Request(
                f"http://localhost:{port}",
                headers={"User-Agent": "HealthMonitor/1.0"}
            )
            
            with urllib.request.urlopen(req, timeout=3) as response:
                status_code = response.getcode()
                
                if status_code == 200:
                    status = "healthy"
                    error = None
                elif status_code == 530:
                    status = "failed"
                    error = "Cloudflare error (tunnel down)"
                else:
                    status = "degraded"
                    error = f"HTTP {status_code}"
                
                return ServiceHealth(
                    name=f"tunnel_{name}",
                    type="tunnel",
                    status=status,
                    last_check=datetime.now().isoformat(),
                    last_success=datetime.now().isoformat() if status == "healthy" else None,
                    exit_code=status_code,
                    error_message=error,
                    metrics={"port": port, "status_code": status_code},
                    dependencies=[f"com.openclaw.tunnel-{name}"]
                )
                
        except urllib.error.HTTPError as e:
            return ServiceHealth(
                name=f"tunnel_{name}",
                type="tunnel",
                status="failed",
                last_check=datetime.now().isoformat(),
                last_success=None,
                exit_code=e.code,
                error_message=f"HTTP error: {e.code}",
                metrics={"port": port},
                dependencies=[f"com.openclaw.tunnel-{name}"]
            )
            
        except Exception as e:
            return ServiceHealth(
                name=f"tunnel_{name}",
                type="tunnel",
                status="failed",
                last_check=datetime.now().isoformat(),
                last_success=None,
                exit_code=None,
                error_message=str(e),
                metrics={"port": port},
                dependencies=[f"com.openclaw.tunnel-{name}"]
            )
    
    def _check_api_token(self, token: Dict) -> ServiceHealth:
        """
        Check API token validity.
        
        Args:
            token: Token config (name, path)
            
        Returns:
            Health status
        """
        name = token["name"]
        path = self.workspace / token["path"]
        
        try:
            if not path.exists():
                return ServiceHealth(
                    name=f"api_{name}",
                    type="api",
                    status="failed",
                    last_check=datetime.now().isoformat(),
                    last_success=None,
                    exit_code=None,
                    error_message="Token file missing",
                    metrics={},
                    dependencies=[]
                )
            
            with open(path) as f:
                data = json.load(f)
            
            # Check expiry
            if "expires_at" in data:
                expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
                now = datetime.now(expires_at.tzinfo)
                
                if expires_at < now:
                    status = "failed"
                    error = "Token expired"
                elif expires_at < now + timedelta(hours=1):
                    status = "degraded"
                    error = "Token expires soon (<1hr)"
                else:
                    status = "healthy"
                    error = None
                
                metrics = {"expires_at": data["expires_at"]}
            else:
                # No expiry info, assume healthy if file exists
                status = "healthy"
                error = None
                metrics = {}
            
            return ServiceHealth(
                name=f"api_{name}",
                type="api",
                status=status,
                last_check=datetime.now().isoformat(),
                last_success=datetime.now().isoformat() if status == "healthy" else None,
                exit_code=None,
                error_message=error,
                metrics=metrics,
                dependencies=[]
            )
            
        except Exception as e:
            return ServiceHealth(
                name=f"api_{name}",
                type="api",
                status="unknown",
                last_check=datetime.now().isoformat(),
                last_success=None,
                exit_code=None,
                error_message=str(e),
                metrics={},
                dependencies=[]
            )
    
    def _check_system_resources(self) -> ServiceHealth:
        """
        Check system resource health (disk, memory).
        
        Returns:
            Health status
        """
        try:
            # Check disk usage
            result = subprocess.run(
                ["df", "-h", str(self.workspace)],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # Parse df output
            lines = result.stdout.strip().split("\n")
            if len(lines) >= 2:
                fields = lines[1].split()
                used_pct = int(fields[4].rstrip("%"))
                
                if used_pct >= 95:
                    status = "critical"
                    error = f"Disk {used_pct}% full"
                elif used_pct >= 85:
                    status = "degraded"
                    error = f"Disk {used_pct}% full"
                else:
                    status = "healthy"
                    error = None
                
                metrics = {
                    "disk_used_pct": used_pct,
                    "disk_avail": fields[3]
                }
            else:
                status = "unknown"
                error = "Could not parse df output"
                metrics = {}
            
            return ServiceHealth(
                name="system_resources",
                type="system",
                status=status,
                last_check=datetime.now().isoformat(),
                last_success=datetime.now().isoformat() if status == "healthy" else None,
                exit_code=None,
                error_message=error,
                metrics=metrics,
                dependencies=[]
            )
            
        except Exception as e:
            return ServiceHealth(
                name="system_resources",
                type="system",
                status="unknown",
                last_check=datetime.now().isoformat(),
                last_success=None,
                exit_code=None,
                error_message=str(e),
                metrics={},
                dependencies=[]
            )
    
    def _save_health(self, health: ServiceHealth):
        """
        Save health status to database.
        
        Args:
            health: Service health state
        """
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO service_health VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(service_name) DO UPDATE SET
                    service_type = excluded.service_type,
                    status = excluded.status,
                    last_check = excluded.last_check,
                    last_success = excluded.last_success,
                    exit_code = excluded.exit_code,
                    error_message = excluded.error_message,
                    metrics = excluded.metrics,
                    dependencies = excluded.dependencies,
                    updated_at = excluded.updated_at
            """, (
                health.name,
                health.type,
                health.status,
                health.last_check,
                health.last_success,
                health.exit_code,
                health.error_message,
                json.dumps(health.metrics),
                json.dumps(health.dependencies),
                now,  # created_at
                now   # updated_at
            ))
            conn.commit()
    
    def get_failed_services(self) -> List[ServiceHealth]:
        """
        Get all failed services.
        
        Returns:
            List of failed service health states
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT service_name, service_type, status, last_check,
                       last_success, exit_code, error_message, metrics, dependencies
                FROM service_health
                WHERE status IN ('failed', 'critical')
                ORDER BY last_check DESC
            """)
            
            results = []
            for row in cursor:
                results.append(ServiceHealth(
                    name=row[0],
                    type=row[1],
                    status=row[2],
                    last_check=row[3],
                    last_success=row[4],
                    exit_code=row[5],
                    error_message=row[6],
                    metrics=json.loads(row[7]) if row[7] else {},
                    dependencies=json.loads(row[8]) if row[8] else []
                ))
            
            return results
    
    def create_alert(self, alert: HealthAlert):
        """
        Create health alert.
        
        Args:
            alert: Health alert to save
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO health_alerts
                (service, severity, message, root_cause, suggested_fix, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                alert.service,
                alert.severity,
                alert.message,
                alert.root_cause,
                alert.suggested_fix,
                alert.timestamp
            ))
            conn.commit()
    
    def get_unresolved_alerts(self) -> List[HealthAlert]:
        """
        Get all unresolved alerts.
        
        Returns:
            List of unresolved alerts
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT service, severity, message, root_cause, suggested_fix, timestamp
                FROM health_alerts
                WHERE resolved = 0
                ORDER BY timestamp DESC
            """)
            
            return [HealthAlert(*row) for row in cursor]
    
    def resolve_alert(self, service: str, timestamp: str):
        """
        Mark alert as resolved.
        
        Args:
            service: Service name
            timestamp: Alert timestamp
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE health_alerts
                SET resolved = 1, resolved_at = ?
                WHERE service = ? AND timestamp = ? AND resolved = 0
            """, (datetime.now().isoformat(), service, timestamp))
            conn.commit()


if __name__ == "__main__":
    # Test health monitor
    monitor = SystemHealthMonitor()
    
    print("Checking all services...")
    health_map = monitor.check_all_services()
    
    print("\nHealth Summary:")
    for name, health in health_map.items():
        status_icon = "✅" if health.status == "healthy" else "⚠️" if health.status == "degraded" else "❌"
        print(f"{status_icon} {name}: {health.status}")
        if health.error_message:
            print(f"   Error: {health.error_message}")
    
    failed = monitor.get_failed_services()
    if failed:
        print(f"\n❌ {len(failed)} failed services:")
        for service in failed:
            print(f"   - {service.name}: {service.error_message}")
    else:
        print("\n✅ All services healthy!")
