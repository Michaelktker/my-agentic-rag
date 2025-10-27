#!/bin/bash
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
