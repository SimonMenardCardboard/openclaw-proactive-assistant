#!/bin/bash
# Deploy Gmail + Calendar webhook servers to production VPS
# Creates systemd services and Nginx configuration

set -e

echo "=== Webhook Server Deployment ==="
echo ""

# Check if running on VPS
if [ ! -f /etc/os-release ]; then
    echo "❌ This script must run on the VPS (not local machine)"
    exit 1
fi

# Get configuration
read -p "Enter your domain (e.g., transmogrifier.example.com): " DOMAIN

if [ -z "$DOMAIN" ]; then
    echo "❌ Domain is required"
    exit 1
fi

WEBHOOK_DIR="$HOME/.openclaw/workspace/integrations/intelligence/webhooks"
USER=$(whoami)

echo ""
echo "Domain: $DOMAIN"
echo "Webhook directory: $WEBHOOK_DIR"
echo "User: $USER"
echo ""
read -p "Proceed with deployment? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled"
    exit 0
fi

# Install dependencies
echo "📦 Installing Python dependencies..."
cd "$WEBHOOK_DIR"
pip install --quiet flask gunicorn google-cloud-pubsub

# Create systemd service for Gmail webhook
echo "🔧 Creating systemd service for Gmail webhook..."
sudo tee /etc/systemd/system/gmail-webhook.service > /dev/null <<EOF
[Unit]
Description=Gmail Push Webhook Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$WEBHOOK_DIR
ExecStart=/usr/bin/gunicorn -w 4 -b 127.0.0.1:5001 gmail_webhook:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create systemd service for Calendar webhook
echo "🔧 Creating systemd service for Calendar webhook..."
sudo tee /etc/systemd/system/calendar-webhook.service > /dev/null <<EOF
[Unit]
Description=Calendar Watch Webhook Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$WEBHOOK_DIR
ExecStart=/usr/bin/gunicorn -w 4 -b 127.0.0.1:5002 calendar_webhook:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start services
echo "🚀 Enabling and starting webhook services..."
sudo systemctl daemon-reload
sudo systemctl enable gmail-webhook
sudo systemctl enable calendar-webhook
sudo systemctl start gmail-webhook
sudo systemctl start calendar-webhook

# Check service status
echo ""
echo "✅ Services started:"
sudo systemctl status gmail-webhook --no-pager || true
sudo systemctl status calendar-webhook --no-pager || true

# Create Nginx configuration
echo ""
echo "🌐 Creating Nginx configuration..."

NGINX_CONF="/etc/nginx/sites-available/$DOMAIN-webhooks"

sudo tee "$NGINX_CONF" > /dev/null <<EOF
server {
    listen 443 ssl http2;
    server_name $DOMAIN;
    
    # SSL configuration (assumes Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    
    # SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # Gmail webhook endpoint
    location /api/gmail/webhook {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Increase timeout for long-running webhook processing
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Calendar webhook endpoint
    location /api/calendar/webhook {
        proxy_pass http://127.0.0.1:5002;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Increase timeout for long-running webhook processing
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Health check endpoints
    location /health {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host \$host;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$server_name\$request_uri;
}
EOF

# Enable Nginx site
sudo ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/

# Test Nginx configuration
echo ""
echo "🧪 Testing Nginx configuration..."
sudo nginx -t

# Reload Nginx
echo "🔄 Reloading Nginx..."
sudo systemctl reload nginx

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Webhook endpoints:"
echo "  https://$DOMAIN/api/gmail/webhook"
echo "  https://$DOMAIN/api/calendar/webhook"
echo "  https://$DOMAIN/health"
echo ""
echo "Check service logs:"
echo "  sudo journalctl -u gmail-webhook -f"
echo "  sudo journalctl -u calendar-webhook -f"
echo ""
echo "Next steps:"
echo "1. Configure Google Cloud Pub/Sub to point to these endpoints"
echo "2. Subscribe Gmail/Calendar via API"
echo "3. Test with real email/calendar event"
echo ""
