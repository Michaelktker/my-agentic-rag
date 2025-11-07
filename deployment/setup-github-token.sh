#!/bin/bash
set -e

echo "====================================="
echo "GitHub Token Setup for Copilot CLI"
echo "====================================="
echo ""

# Check if token is provided
if [ -z "$1" ]; then
    echo "❌ Error: GitHub token not provided"
    echo ""
    echo "Usage: $0 <GITHUB_TOKEN>"
    echo ""
    echo "To create a GitHub token:"
    echo "1. Go to: https://github.com/settings/tokens?type=beta"
    echo "2. Click 'Generate new token' (Fine-grained)"
    echo "3. Give it a name: 'WhatsApp Bot Copilot CLI'"
    echo "4. Set expiration (recommended: 90 days)"
    echo "5. Under 'Permissions', select:"
    echo "   - Copilot: Read and write"
    echo "6. Click 'Generate token'"
    echo "7. Copy the token and run: $0 ghp_your_token_here"
    echo ""
    exit 1
fi

GITHUB_TOKEN="$1"

echo "📝 Creating systemd service override with GITHUB_TOKEN..."

# Create systemd override directory
sudo mkdir -p /etc/systemd/system/whatsapp-bot.service.d/

# Create override file with environment variable
sudo tee /etc/systemd/system/whatsapp-bot.service.d/github-token.conf > /dev/null <<EOF
[Service]
Environment="GITHUB_TOKEN=${GITHUB_TOKEN}"
EOF

echo "✅ Override file created"

# Set proper permissions
sudo chmod 600 /etc/systemd/system/whatsapp-bot.service.d/github-token.conf

echo "🔄 Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "🔄 Restarting whatsapp-bot service..."
sudo systemctl restart whatsapp-bot

echo ""
echo "====================================="
echo "✅ Setup Complete!"
echo "====================================="
echo ""
echo "Verifying Copilot authentication..."
sleep 3

# Test copilot authentication
if copilot -p "test" --allow-all-tools 2>&1 | grep -q "No authentication information found"; then
    echo "❌ Authentication failed - token may be invalid"
    exit 1
else
    echo "✅ Copilot CLI authenticated successfully!"
fi

echo ""
echo "You can now use /cop commands in WhatsApp!"
echo "Try: /cop what is terraform"
