#!/bin/bash
# OpenClaw Proactive Assistant - Production Install
# Installs V8 meta-learning system on fresh OpenClaw instance

set -e

echo "Installing OpenClaw Proactive Assistant..."

# Clone repo
git clone https://github.com/SimonMenardCardboard/openclaw-proactive-assistant.git /tmp/openclaw-proactive
cd /tmp/openclaw-proactive

# Install V8 components
cp -r v8/*.py ~/.openclaw/workspace/integrations/intelligence/
chmod +x ~/.openclaw/workspace/integrations/intelligence/*.py

# Install dependencies
pip3 install -r requirements.txt

# Set up cron jobs
echo "Setting up daily intelligence report..."
(crontab -l 2>/dev/null; echo "0 7 * * * cd ~/.openclaw/workspace/integrations/intelligence && python3 daily_intelligence_report.py") | crontab -

echo "✅ OpenClaw Proactive Assistant installed!"
echo "Features: V8 meta-learning, auto-optimization, pattern learning"

