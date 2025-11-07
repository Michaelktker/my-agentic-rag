#!/bin/bash
# ============================================================================
# WhatsApp Bot Deployment Script
# ============================================================================
#
# PURPOSE:
#   Deploy code updates to a RUNNING WhatsApp bot VM. Does NOT create new VM.
#   Copies application files, installs dependencies, and restarts service.
#
# USAGE:
#   # From local machine (workspace root):
#   ./deployment/deploy-to-vm.sh
#
# PREREQUISITES:
#   - VM already exists and is running (use vm-setup.sh for initial setup)
#   - gcloud CLI authenticated
#   - Appropriate GCP permissions
#
# CONFIGURATION:
#   PROJECT: staging-adk
#   ZONE: us-central1-a
#   VM_NAME: whatsapp-bot
#
# WHAT IT DOES:
#   1. Copies files to VM: index.js, package.json, package-lock.json, config.json
#   2. SSHs into VM and:
#      - Upgrades to Node.js 20 (if needed)
#      - Installs npm dependencies
#      - Creates/updates systemd service
#      - Reloads systemd daemon
#      - Restarts whatsapp-bot service
#   3. Shows service status
#
# AFTER RUNNING:
#   - Bot restarted with latest code
#   - Check logs: gcloud compute ssh whatsapp-bot --project=staging-adk \
#                 --zone=us-central1-a --command='sudo journalctl -u whatsapp-bot -f'
#
# TROUBLESHOOTING:
#   - If QR code scanning fails: sudo systemctl restart whatsapp-bot
#   - View full logs: sudo journalctl -u whatsapp-bot -n 100
#   - Check service status: sudo systemctl status whatsapp-bot
#
# RELATED SCRIPTS:
#   - vm-setup.sh: Initial VM setup (first-time only)
#
# ============================================================================
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
  index.js terminal-handler.js package.json package-lock.json config.json \
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

# Install build tools for node-pty
echo "🔨 Installing build tools for native modules..."
sudo apt-get install -y build-essential python3

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
