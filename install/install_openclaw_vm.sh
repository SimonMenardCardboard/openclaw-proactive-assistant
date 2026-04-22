#!/bin/bash
#
# Transmogrifier VM Install Script
# Provisions a fresh Ubuntu VM with OpenClaw Gateway and Transmogrifier integrations
# Runs via cloud-init on Hetzner VMs
#

set -e

# Configuration (passed via cloud-init)
SUBDOMAIN="${SUBDOMAIN:-user-example}"
USER_ID="${USER_ID:-user_example}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@getcardboardai.com}"

echo "=========================================="
echo "Transmogrifier VM Setup"
echo "Subdomain: $SUBDOMAIN.getcardboardai.com"
echo "User ID: $USER_ID"
echo "=========================================="

# 1. Update system
echo "[1/10] Updating system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq

# 2. Install dependencies
echo "[2/10] Installing dependencies..."
apt-get install -y -qq \
    curl \
    git \
    nodejs \
    npm \
    python3 \
    python3-pip \
    sqlite3 \
    nginx \
    certbot \
    python3-certbot-nginx \
    build-essential

# 3. Install OpenClaw
echo "[3/10] Installing OpenClaw..."
npm install -g openclaw@latest

# 3.5. Install Proactive Assistant from GitHub
echo "[3.5/10] Installing Proactive Assistant..."
cd /tmp
git clone https://github.com/SimonMenardCardboard/openclaw-proactive-assistant.git
cd openclaw-proactive-assistant
bash install.sh

# Install Accounts API
echo "[3.7/10] Installing Accounts API..."
mkdir -p /opt/transmogrifier
cd /tmp/openclaw-proactive-assistant/vm-services
cp accounts_api.py /opt/transmogrifier/
cp accounts-api.service /etc/systemd/system/

# Update service file with subdomain
sed -i "s/SUBDOMAIN/$SUBDOMAIN/g" /etc/systemd/system/accounts-api.service

# Install Python dependencies for accounts API
pip3 install flask flask-cors requests

# Start accounts API
systemctl daemon-reload
systemctl enable accounts-api
systemctl start accounts-api

# 4. Create openclaw user
echo "[4/10] Creating openclaw user..."
if ! id -u openclaw >/dev/null 2>&1; then
    useradd -r -m -s /bin/bash openclaw
fi

# 5. Clone Transmogrifier workspace
echo "[5/10] Setting up workspace..."
mkdir -p /opt/openclaw-workspace
cd /opt/openclaw-workspace

# Initialize workspace structure
cat > README.md <<EOF
# Transmogrifier OpenClaw Instance
User: $USER_ID
Subdomain: $SUBDOMAIN.getcardboardai.com
Provisioned: $(date)
EOF

# Create pattern learning database schema
cat > schema.sql <<EOF
CREATE TABLE IF NOT EXISTS patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type TEXT NOT NULL,
    context TEXT NOT NULL,
    action TEXT NOT NULL,
    success_rate REAL DEFAULT 1.0,
    usage_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pattern_type ON patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_success_rate ON patterns(success_rate);
EOF

sqlite3 pattern_learning.db < schema.sql

# Create Python requirements
cat > requirements.txt <<EOF
google-auth==2.25.2
google-auth-oauthlib==1.2.0
google-api-python-client==2.111.0
openai==1.7.0
anthropic==0.8.0
EOF

pip3 install -r requirements.txt

# 6. Configure OpenClaw
echo "[6/10] Configuring OpenClaw..."
mkdir -p /home/openclaw/.openclaw

# Set up API keys from environment (passed via cloud-init)
cat > /home/openclaw/.openclaw/.env <<EOF
GOOGLE_API_KEY=${GOOGLE_AI_API_KEY}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
EOF

cat > /home/openclaw/.openclaw/config.json <<EOF
{
  "gateway": {
    "port": 28789,
    "host": "0.0.0.0",
    "ssl": false
  },
  "workspace": "/opt/openclaw-workspace",
  "user_id": "$USER_ID",
  "model": "google/gemini-2.5-flash",
  "fallbackModels": ["anthropic/claude-sonnet-4-5"],
  "features": {
    "pattern_learning": true,
    "cross_device_sync": true,
    "oauth_integrations": true
  }
}
EOF

chown -R openclaw:openclaw /home/openclaw/.openclaw
chown -R openclaw:openclaw /opt/openclaw-workspace

# 7. Set up systemd service
echo "[7/10] Creating systemd service..."
cat > /etc/systemd/system/openclaw-gateway.service <<EOF
[Unit]
Description=OpenClaw Gateway for Transmogrifier
After=network.target

[Service]
Type=simple
User=openclaw
WorkingDirectory=/opt/openclaw-workspace
Environment="HOME=/home/openclaw"
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/local/bin/openclaw gateway start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable openclaw-gateway
systemctl start openclaw-gateway

# Wait for gateway to start
echo "Waiting for OpenClaw Gateway to start..."
sleep 5

# 8. Set up Nginx reverse proxy
echo "[8/10] Configuring Nginx..."
cat > /etc/nginx/sites-available/openclaw <<EOF
server {
    listen 80;
    server_name $SUBDOMAIN.getcardboardai.com;

    location / {
        proxy_pass http://localhost:28789;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }
}
EOF

ln -sf /etc/nginx/sites-available/openclaw /etc/nginx/sites-enabled/openclaw
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl reload nginx

# 9. Get SSL certificate
echo "[9/10] Obtaining SSL certificate..."
certbot --nginx \
    -d $SUBDOMAIN.getcardboardai.com \
    --non-interactive \
    --agree-tos \
    --email $ADMIN_EMAIL \
    --redirect

# 10. Mark as ready
echo "[10/10] Finalizing setup..."
cat > /opt/openclaw-workspace/.provisioned <<EOF
{
  "status": "ready",
  "user_id": "$USER_ID",
  "subdomain": "$SUBDOMAIN",
  "vm_url": "https://$SUBDOMAIN.getcardboardai.com",
  "provisioned_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "openclaw_version": "$(openclaw --version 2>/dev/null || echo 'unknown')"
}
EOF

echo "=========================================="
echo "✅ Transmogrifier VM Ready!"
echo "URL: https://$SUBDOMAIN.getcardboardai.com"
echo "Gateway Status: $(systemctl is-active openclaw-gateway)"
echo "=========================================="

# Send ready signal to control plane (if configured)
if [ -n "$CONTROL_PLANE_URL" ]; then
    curl -X POST "$CONTROL_PLANE_URL/api/vm/ready" \
        -H "Content-Type: application/json" \
        -d "{\"user_id\": \"$USER_ID\", \"vm_url\": \"https://$SUBDOMAIN.getcardboardai.com\"}" \
        || true
fi
