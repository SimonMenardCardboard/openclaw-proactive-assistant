#!/bin/bash
# OpenClaw Proactive Assistant - Production Install
# Installs V8 + V8.5 on fresh OpenClaw instance

set -e

echo "Installing OpenClaw Proactive Assistant..."

WORKSPACE_DIR="${HOME}/.openclaw/workspace/integrations/intelligence"
mkdir -p "$WORKSPACE_DIR"

# Install V8 meta-learning
echo "Installing V8 meta-learning..."
cp -r v8/*.py "$WORKSPACE_DIR/" 2>/dev/null || true
chmod +x "$WORKSPACE_DIR"/*.py

# Install V8.5 pattern learning + federated learning
echo "Installing V8.5..."
mkdir -p "$WORKSPACE_DIR/v8.5_pattern_learning"
mkdir -p "$WORKSPACE_DIR/v8.5_federated_learning"
cp -r v8.5/pattern_learning/* "$WORKSPACE_DIR/v8.5_pattern_learning/" 2>/dev/null || true
cp -r v8.5/federated_learning/* "$WORKSPACE_DIR/v8.5_federated_learning/" 2>/dev/null || true

# Install dependencies
echo "Installing dependencies..."
pip3 install -q -r requirements.txt 2>/dev/null || echo "Note: Some dependencies may need manual install"

# Set up databases
echo "Initializing databases..."
cd "$WORKSPACE_DIR/v8.5_pattern_learning" && \
sqlite3 pattern_learning.db < database_schema.sql 2>/dev/null || echo "Pattern learning DB already exists"

# Set up cron jobs
echo "Setting up automation..."
(crontab -l 2>/dev/null; echo "0 7 * * * cd $WORKSPACE_DIR && python3 daily_intelligence_report.py") | crontab - || true

echo ""
echo "✅ OpenClaw Proactive Assistant installed!"
echo ""
echo "Features installed:"
echo "  - V8 Meta-Learning (auto-optimization, code generation)"
echo "  - V8.5 Pattern Learning (personalized recommendations)"
echo "  - V8.5 Federated Learning (cross-device intelligence)"
echo ""
echo "Next: Configure your integrations (email, calendar, etc.)"
