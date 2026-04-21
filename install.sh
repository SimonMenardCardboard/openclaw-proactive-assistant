#!/bin/bash
# OpenClaw Proactive Assistant - Production Install
# Full Hobbes stack: V6 + V7 + V8 + V8.5 + Workspace

set -e

echo "Installing OpenClaw Proactive Assistant (Full Hobbes Stack)..."

WORKSPACE_DIR="${HOME}/.openclaw/workspace"
INTEL_DIR="$WORKSPACE_DIR/integrations/intelligence"
mkdir -p "$INTEL_DIR"

# Copy workspace template files
echo "Setting up workspace..."
cp workspace_template/*.md "$WORKSPACE_DIR/" 2>/dev/null || true

# Install V6 Proactive Daemon
echo "Installing V6 Proactive Daemon..."
mkdir -p "$INTEL_DIR/v6_proactive"
cp -r v6/*.py "$INTEL_DIR/v6_proactive/" 2>/dev/null || true
chmod +x "$INTEL_DIR/v6_proactive"/*.py

# Install V7 Self-Healing
echo "Installing V7 Self-Healing..."
mkdir -p "$INTEL_DIR/v7_self_healing"
cp -r v7/*.py "$INTEL_DIR/v7_self_healing/" 2>/dev/null || true
chmod +x "$INTEL_DIR/v7_self_healing"/*.py

# Install V8 meta-learning
echo "Installing V8 Meta-Learning..."
cp -r v8/*.py "$INTEL_DIR/" 2>/dev/null || true
chmod +x "$INTEL_DIR"/*.py

# Install V8.5 pattern learning + federated learning
echo "Installing V8.5..."
mkdir -p "$INTEL_DIR/v8.5_pattern_learning"
mkdir -p "$INTEL_DIR/v8.5_federated_learning"
cp -r v8.5/pattern_learning/* "$INTEL_DIR/v8.5_pattern_learning/" 2>/dev/null || true
cp -r v8.5/federated_learning/* "$INTEL_DIR/v8.5_federated_learning/" 2>/dev/null || true

# Install dependencies
echo "Installing dependencies..."
pip3 install -q -r requirements.txt 2>/dev/null || echo "Some dependencies need manual install"

# Set up databases
echo "Initializing databases..."
cd "$INTEL_DIR/v8.5_pattern_learning" && \
sqlite3 pattern_learning.db < database_schema.sql 2>/dev/null || true

# Set up cron jobs
echo "Setting up automation..."
(crontab -l 2>/dev/null; echo "0 7 * * * cd $INTEL_DIR && python3 daily_intelligence_report.py") | crontab - || true

echo ""
echo "✅ Full Hobbes Stack Installed!"
echo ""
echo "Features:"
echo "  - SOUL.md, AGENTS.md, workspace files"
echo "  - V6 Proactive Daemon"
echo "  - V7 Self-Healing"
echo "  - V8 Meta-Learning"
echo "  - V8.5 Pattern + Federated Learning"
echo ""
echo "Configure: Edit ~/.openclaw/workspace/USER.md"
