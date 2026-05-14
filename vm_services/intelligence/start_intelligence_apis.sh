#!/bin/bash
# Start all intelligence API services
# Ports: 8011-8014

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$HOME/.openclaw/workspace/logs/intelligence"

# Create log directory
mkdir -p "$LOG_DIR"

# Function to start service
start_service() {
    local service_name=$1
    local port=$2
    local script=$3
    
    echo "Starting $service_name on port $port..."
    
    nohup python3 "$SCRIPT_DIR/$script" \
        > "$LOG_DIR/${service_name}.log" 2>&1 &
    
    local pid=$!
    echo $pid > "$LOG_DIR/${service_name}.pid"
    
    echo "  ✓ Started $service_name (PID: $pid)"
}

echo "Starting Intelligence API Services"
echo "===================================="
echo

# Start all services
start_service "contact-intelligence" 8011 "contact_intelligence_api.py"
start_service "task-intelligence" 8012 "task_intelligence_api.py"
start_service "inbox-intelligence" 8013 "inbox_intelligence_api.py"
start_service "digest-intelligence" 8014 "digest_intelligence_api.py"

echo
echo "All services started!"
echo
echo "Health checks:"
echo "  http://localhost:8011/health"
echo "  http://localhost:8012/health"
echo "  http://localhost:8013/health"
echo "  http://localhost:8014/health"
echo
echo "Logs:"
echo "  $LOG_DIR/contact-intelligence.log"
echo "  $LOG_DIR/task-intelligence.log"
echo "  $LOG_DIR/inbox-intelligence.log"
echo "  $LOG_DIR/digest-intelligence.log"
