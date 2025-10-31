#!/bin/bash
# ============================================================================
# WhatsApp Bot VM Initial Setup
# ============================================================================
# 
# PURPOSE:
#   First-time setup of a new Compute Engine VM for WhatsApp bot deployment.
#   Installs Node.js 20, clones repository, installs dependencies, and 
#   creates systemd service for auto-restart.
#
# USAGE:
#   # SSH into VM and run:
#   bash <(curl -s https://raw.githubusercontent.com/Michaelktker/my-agentic-rag/main/deployment/vm-setup.sh)
#
#   # Or copy and run locally on VM:
#   ./vm-setup.sh
#
# PREREQUISITES:
#   - Fresh Compute Engine VM (Debian/Ubuntu)
#   - Internet access
#   - sudo privileges
#
# WHAT IT DOES:
#   1. Updates system packages
#   2. Installs Node.js 20 LTS
#   3. Clones GitHub repository
#   4. Installs npm dependencies
#   5. Creates systemd service (whatsapp-bot.service)
#   6. Enables auto-start on boot
#   7. Starts the bot service
#
# AFTER RUNNING:
#   - Bot will be running as systemd service
#   - QR code available in logs: sudo journalctl -u whatsapp-bot -f
#   - Auto-restarts on failure
#   - Auto-starts on VM reboot
#
# RELATED SCRIPTS:
#   - deploy-to-vm.sh: Update running bot with code changes
#
# ============================================================================
set -e

echo "==================================="
echo "WhatsApp Bot VM Setup Script"
echo "==================================="

# Update system
echo "📦 Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install Node.js 20
echo "📦 Installing Node.js 20..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs git

# Verify installations
echo "✅ Node.js version:"
node --version
echo "✅ npm version:"
npm --version

# Get current user
CURRENT_USER=$(whoami)
HOME_DIR="/home/$CURRENT_USER"

# Clone repository
echo "📂 Cloning repository..."
cd "$HOME_DIR"
if [ -d "my-agentic-rag" ]; then
    echo "Repository already exists, pulling latest changes..."
    cd my-agentic-rag
    git pull
else
    git clone https://github.com/Michaelktker/my-agentic-rag.git
    cd my-agentic-rag
fi

# Install dependencies
echo "📦 Installing npm dependencies..."
npm install --production

# Create systemd service
echo "🔧 Creating systemd service..."
sudo tee /etc/systemd/system/whatsapp-bot.service > /dev/null <<EOF
[Unit]
Description=WhatsApp Bot with ADK Integration
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$HOME_DIR/my-agentic-rag
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
echo "🔄 Enabling and starting service..."
sudo systemctl daemon-reload
sudo systemctl enable whatsapp-bot
sudo systemctl start whatsapp-bot

# Check status
echo ""
echo "==================================="
echo "✅ Setup Complete!"
echo "==================================="
echo ""
echo "Service Status:"
sudo systemctl status whatsapp-bot --no-pager
echo ""
echo "Useful commands:"
echo "  View logs:    sudo journalctl -u whatsapp-bot -f"
echo "  Stop bot:     sudo systemctl stop whatsapp-bot"
echo "  Start bot:    sudo systemctl start whatsapp-bot"
echo "  Restart bot:  sudo systemctl restart whatsapp-bot"
echo "  Check status: sudo systemctl status whatsapp-bot"
echo ""
