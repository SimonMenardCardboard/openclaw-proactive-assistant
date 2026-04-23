#!/usr/bin/env python3
"""
V7 Health Check HTTP Endpoint

Simple HTTP server that reports system health status.
Useful for:
- External monitoring (Uptime Robot, Pingdom, etc.)
- Load balancers
- Kubernetes health checks
- Quick status checks via curl

Usage:
    python3 v7_health_endpoint.py --port 8888
    
    # Check health
    curl http://localhost:8888/health
    
    # Get detailed status
    curl http://localhost:8888/status
"""

import json
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from datetime import datetime
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from v7_system_health_monitor import SystemHealthMonitor


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP request handler for health checks."""
    
    def __init__(self, *args, workspace=None, **kwargs):
        self.workspace = workspace or Path.home() / ".openclaw" / "workspace"
        self.health_monitor = SystemHealthMonitor(self.workspace)
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/health":
            self._handle_health()
        elif self.path == "/status":
            self._handle_status()
        elif self.path == "/ping":
            self._handle_ping()
        else:
            self.send_error(404, "Not Found")
    
    def _handle_health(self):
        """
        Simple health check endpoint.
        
        Returns:
            200 if all critical services healthy
            503 if any critical service unhealthy
        """
        try:
            health_map = self.health_monitor.check_all_services()
            
            # Define critical services
            critical_services = [
                "com.openclaw.proactive-daemon-v2",
                "com.openclaw.v7-self-healing",
                "api_google_oauth_default"
            ]
            
            # Check critical services
            critical_health = {
                name: health_map.get(name)
                for name in critical_services
                if name in health_map
            }
            
            all_healthy = all(
                h.status == "healthy" 
                for h in critical_health.values() 
                if h is not None
            )
            
            status_code = 200 if all_healthy else 503
            
            response = {
                "status": "healthy" if all_healthy else "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "critical_services": {
                    name: {
                        "status": h.status if h else "unknown",
                        "error": h.error_message if h and h.error_message else None
                    }
                    for name, h in critical_health.items()
                }
            }
            
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        except Exception as e:
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, indent=2).encode())
    
    def _handle_status(self):
        """
        Detailed status endpoint.
        
        Returns:
            All service health information
        """
        try:
            health_map = self.health_monitor.check_all_services()
            
            response = {
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total": len(health_map),
                    "healthy": sum(1 for h in health_map.values() if h.status == "healthy"),
                    "degraded": sum(1 for h in health_map.values() if h.status == "degraded"),
                    "failed": sum(1 for h in health_map.values() if h.status == "failed"),
                    "unknown": sum(1 for h in health_map.values() if h.status == "unknown")
                },
                "services": {
                    name: {
                        "type": h.type,
                        "status": h.status,
                        "last_check": h.last_check,
                        "last_success": h.last_success,
                        "error": h.error_message,
                        "metrics": h.metrics
                    }
                    for name, h in health_map.items()
                }
            }
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, indent=2).encode())
    
    def _handle_ping(self):
        """Simple ping endpoint."""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"pong")
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass  # Silent unless error


def main():
    parser = argparse.ArgumentParser(description="V7 Health Check HTTP Endpoint")
    parser.add_argument("--port", type=int, default=8888, help="Port to listen on (default: 8888)")
    parser.add_argument("--workspace", type=Path, help="Workspace directory")
    args = parser.parse_args()
    
    workspace = args.workspace or Path.home() / ".openclaw" / "workspace"
    
    def handler(*handler_args, **handler_kwargs):
        return HealthHandler(*handler_args, workspace=workspace, **handler_kwargs)
    
    server = HTTPServer(("127.0.0.1", args.port), handler)
    
    print(f"V7 Health Check Endpoint", flush=True)
    print(f"Listening on http://127.0.0.1:{args.port}", flush=True)
    print(f"", flush=True)
    print(f"Endpoints:", flush=True)
    print(f"  GET /health  - Simple health check (200 or 503)", flush=True)
    print(f"  GET /status  - Detailed service status", flush=True)
    print(f"  GET /ping    - Simple ping (always 200)", flush=True)
    print(f"", flush=True)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\nShutting down...", flush=True)
        server.shutdown()


if __name__ == "__main__":
    main()
