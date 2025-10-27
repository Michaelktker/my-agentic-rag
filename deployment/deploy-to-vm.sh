#!/bin/bash
set -e

echo "==================================="
echo "WhatsApp Bot - Complete VM Deployment"
echo "==================================="

PROJECT="staging-adk"
ZONE="us-central1-a"
VM_NAME="whatsapp-bot"

# Step 1: Copy application files to VM
echo "📦 Step 1: Copying application files to VM..."
gcloud compute scp --recurse \
  index.js package.json package-lock.json config.json \
  "${VM_NAME}:~/whatsapp-bot/" \
  --project="$PROJECT" \
  --zone="$ZONE"

# Step 2: Install dependencies and setup service
echo "🔧 Step 2: Installing dependencies and setting up service..."
gcloud compute ssh "$VM_NAME" \
  --project="$PROJECT" \
  --zone="$ZONE" \
  --command="bash -s" <<'ENDSSH'

# Upgrade to Node.js 20
echo "📦 Upgrading to Node.js 20..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

echo "✅ Node.js version:"
node --version

# Install dependencies
cd ~/whatsapp-bot
npm install --production

# Get current user and working directory
CURRENT_USER=$(whoami)
WORKING_DIR=$(pwd)

# Create systemd service
sudo tee /etc/systemd/system/whatsapp-bot.service > /dev/null <<EOF
[Unit]
Description=WhatsApp Bot with ADK Integration
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$WORKING_DIR
ExecStart=/usr/bin/node index.js
Restart=always
RestartSec=10
Environment=NODE_ENV=production

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=whatsapp-bot

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable whatsapp-bot
sudo systemctl start whatsapp-bot

# Show status
echo ""
echo "==================================="
echo "✅ Deployment Complete!"
echo "==================================="
sudo systemctl status whatsapp-bot --no-pager

ENDSSH

echo ""
echo "==================================="
echo "✅ All Done!"
echo "==================================="
echo ""
echo "To view logs:"
echo "  gcloud compute ssh $VM_NAME --project=$PROJECT --zone=$ZONE --command='sudo journalctl -u whatsapp-bot -f'"
echo ""
echo "To check status:"
echo "  gcloud compute ssh $VM_NAME --project=$PROJECT --zone=$ZONE --command='sudo systemctl status whatsapp-bot'"
echo ""
