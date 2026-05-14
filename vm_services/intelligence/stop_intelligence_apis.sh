#!/bin/bash
# Stop all intelligence API services

set -euo pipefail

LOG_DIR="$HOME/.openclaw/workspace/logs/intelligence"

# Function to stop service
stop_service() {
    local service_name=$1
    local pid_file="$LOG_DIR/${service_name}.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        
        if kill -0 $pid 2>/dev/null; then
            echo "Stopping $service_name (PID: $pid)..."
            kill $pid
            rm "$pid_file"
            echo "  ✓ Stopped $service_name"
        else
            echo "  ⚠ $service_name not running (stale PID file)"
            rm "$pid_file"
        fi
    else
        echo "  ⚠ $service_name not running"
    fi
}

echo "Stopping Intelligence API Services"
echo "===================================="
echo

stop_service "contact-intelligence"
stop_service "task-intelligence"
stop_service "inbox-intelligence"
stop_service "digest-intelligence"

echo
echo "All services stopped!"
