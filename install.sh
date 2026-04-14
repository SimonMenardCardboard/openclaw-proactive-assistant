#!/bin/bash
# OpenClaw Proactive Assistant - Complete Installation

set -e

echo "🚀 Installing OpenClaw Proactive Assistant (V6+V7+V8)..."
echo ""

# Check prerequisites
if ! command -v openclaw &> /dev/null; then
    echo "❌ OpenClaw not found. Install OpenClaw first:"
    echo "   npm install -g openclaw"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found"
    exit 1
fi

# Create directory structure
echo "📁 Creating directory structure..."
mkdir -p ~/.openclaw/proactive/{v6,v7,v8,logs,scripts,credentials}

# Copy files
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📦 Installing V6 (Proactive Daemon + Executor)..."
cp "$SCRIPT_DIR"/v6/*.py ~/.openclaw/proactive/v6/
chmod +x ~/.openclaw/proactive/v6/daemon.py

echo "📦 Installing V7 (Self-Healing)..."
cp "$SCRIPT_DIR"/v7/*.py ~/.openclaw/proactive/v7/
chmod +x ~/.openclaw/proactive/v7/self_healing.py

echo "📦 Installing V8 (Meta-Learning + Email/Calendar/Cross-Device)..."
cp "$SCRIPT_DIR"/v8/*.py ~/.openclaw/proactive/v8/
chmod +x ~/.openclaw/proactive/v8/meta_learning.py

# Copy OAuth setup script
cp "$SCRIPT_DIR"/scripts/setup_oauth.py ~/.openclaw/proactive/scripts/
chmod +x ~/.openclaw/proactive/scripts/setup_oauth.py

# Initialize databases
echo "💾 Initializing databases..."
python3 ~/.openclaw/proactive/v8/init_db.py

# Create systemd services (Linux)
if [ -d /etc/systemd/system ]; then
    echo "🔧 Installing systemd services..."
    
    # V6 Proactive Daemon
    sudo cat > /etc/systemd/system/openclaw-v6.service << 'EOF'
[Unit]
Description=OpenClaw V6 Proactive Daemon
After=network.target openclaw-gateway.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/.openclaw/proactive/v6
ExecStart=/usr/bin/python3 /root/.openclaw/proactive/v6/daemon.py --interval 60
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
EOF
    
    # V7 Self-Healing
    sudo cat > /etc/systemd/system/openclaw-v7.service << 'EOF'
[Unit]
Description=OpenClaw V7 Self-Healing Daemon
After=network.target openclaw-gateway.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/.openclaw/proactive/v7
ExecStart=/usr/bin/python3 /root/.openclaw/proactive/v7/self_healing.py --interval 300
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
EOF
    
    # V8 Meta-Learning
    sudo cat > /etc/systemd/system/openclaw-v8.service << 'EOF'
[Unit]
Description=OpenClaw V8 Meta-Learning Daemon
After=network.target openclaw-gateway.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/.openclaw/proactive/v8
ExecStart=/usr/bin/python3 /root/.openclaw/proactive/v8/meta_learning.py --interval 30
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload and enable
    sudo systemctl daemon-reload
    sudo systemctl enable openclaw-v6 openclaw-v7 openclaw-v8
    
    echo "✅ Services installed and enabled"
    echo ""
    echo "Start services:"
    echo "  sudo systemctl start openclaw-v6"
    echo "  sudo systemctl start openclaw-v7"
    echo "  sudo systemctl start openclaw-v8"
fi

echo ""
echo "✅ OpenClaw Proactive Assistant installed successfully!"
echo ""
echo "Components installed:"
echo "  ✅ V6 - Proactive monitoring and autonomous actions"
echo "  ✅ V7 - Self-healing system"
echo "  ✅ V8 - Meta-learning (shell patterns enabled)"
echo ""
echo "Optional features (require setup):"
echo "  ⏸️  Email pattern detection (needs OAuth)"
echo "  ⏸️  Calendar pattern detection (needs OAuth)"
echo "  ⏸️  Cross-device observation (needs opt-in)"
echo ""
echo "Next steps:"
echo "  1. (Optional) Setup OAuth for email/calendar:"
echo "     python3 ~/.openclaw/proactive/scripts/setup_oauth.py"
echo ""
echo "  2. Start daemons: systemctl start openclaw-v6 openclaw-v7 openclaw-v8"
echo ""
echo "  3. Check logs: tail -f ~/.openclaw/proactive/logs/*.log"
echo ""
echo "  4. Monitor status: systemctl status openclaw-{v6,v7,v8}"
echo ""
echo "Docs: https://docs.transmogrifier.ai/proactive"
