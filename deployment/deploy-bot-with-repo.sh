#!/bin/bash
# ============================================================================
# WhatsApp Bot Deployment with Full GitHub Repository Access
# ============================================================================
#
# PURPOSE:
#   Deploy bot to VM with complete GitHub repository access, CLI tools,
#   and ability to modify code and deploy infrastructure
#
# USAGE:
#   ./deployment/deploy-bot-with-repo.sh
#
# WHAT IT DOES:
#   1. Installs all CLI tools (gcloud, terraform, gh, copilot)
#   2. Clones your GitHub repository to /home/user/workspace/my-agentic-rag
#   3. Sets up GitHub authentication
#   4. Configures workspace directory in config.json
#   5. Installs dependencies
#   6. Creates and starts systemd service
#
# ============================================================================
set -e

echo "==================================="
echo "WhatsApp Bot - Full Deployment with Repo Access"
echo "==================================="

PROJECT="staging-adk"
ZONE="us-central1-a"
VM_NAME="whatsapp-bot"
REPO_URL="https://github.com/Michaelktker/my-agentic-rag.git"

# Step 1: Copy application files to VM
echo "📦 Step 1: Copying application files to VM..."
gcloud compute scp --recurse \
  index.js terminal-handler.js package.json package-lock.json config.json \
  "${VM_NAME}:~/whatsapp-bot/" \
  --project="$PROJECT" \
  --zone="$ZONE"

# Step 2: Setup complete development environment on VM
echo "🔧 Step 2: Setting up complete dev environment on VM..."
gcloud compute ssh "$VM_NAME" \
  --project="$PROJECT" \
  --zone="$ZONE" \
  --command="bash -s" <<'ENDSSH'

set -e

echo "================================================"
echo "1. Installing CLI Tools (gcloud, terraform, gh, copilot)"
echo "================================================"

# Install Google Cloud SDK
if ! command -v gcloud &> /dev/null; then
    echo "Installing Google Cloud SDK..."
    curl https://sdk.cloud.google.com | bash
    exec -l $SHELL
    source ~/.bashrc
fi

# Install Terraform
if ! command -v terraform &> /dev/null; then
    echo "Installing Terraform..."
    wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
    echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
    sudo apt update && sudo apt install -y terraform
fi

# Install GitHub CLI
if ! command -v gh &> /dev/null; then
    echo "Installing GitHub CLI..."
    (type -p wget >/dev/null || (sudo apt update && sudo apt-get install wget -y)) \
    && sudo mkdir -p -m 755 /etc/apt/keyrings \
    && wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
    && sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && sudo apt update \
    && sudo apt install gh -y
fi

# Install GitHub Copilot CLI
if ! command -v copilot &> /dev/null; then
    echo "Installing GitHub Copilot CLI..."
    gh extension install github/gh-copilot
fi

# Install Node.js 20
echo "Installing Node.js 20..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install build tools for node-pty
echo "Installing build tools..."
sudo apt-get install -y build-essential python3 git

echo "✅ CLI tools installed:"
echo "  Node.js: $(node --version)"
echo "  gcloud: $(gcloud --version | head -1)"
echo "  terraform: $(terraform version | head -1)"
echo "  gh: $(gh --version | head -1)"
echo "  copilot: $(gh copilot --version 2>&1 || echo 'installed')"

echo ""
echo "================================================"
echo "2. Setting up GitHub Repository"
echo "================================================"

# Create workspace directory
mkdir -p ~/workspace
cd ~/workspace

# Clone repository if it doesn't exist
if [ ! -d "my-agentic-rag" ]; then
    echo "Cloning repository..."
    echo "⚠️  Note: If this fails, you'll need to authenticate GitHub first"
    echo "   Run: gh auth login"
    
    # Try using gh CLI to clone (handles auth automatically)
    if command -v gh &> /dev/null; then
        gh repo clone Michaelktker/my-agentic-rag || {
            echo "❌ GitHub authentication required. Please run:"
            echo "   gcloud compute ssh whatsapp-bot --project=staging-adk --zone=us-central1-a"
            echo "   gh auth login"
            echo "   Then re-run this script."
            exit 1
        }
    else
        git clone https://github.com/Michaelktker/my-agentic-rag.git || {
            echo "❌ Git clone failed. Repository will be skipped for now."
            echo "   You can clone it manually after GitHub authentication."
        }
    fi
else
    echo "Repository already exists, pulling latest changes..."
    cd my-agentic-rag
    git pull || echo "⚠️  Could not pull latest changes (auth may be needed)"
fi

cd ~/workspace/my-agentic-rag

echo "✅ Repository cloned to: $(pwd)"

echo ""
echo "================================================"
echo "3. Configuring Workspace in Bot Config"
echo "================================================"

# Update config.json to use the workspace directory
cat > ~/whatsapp-bot/config.json <<'EOF'
{
  "adk": {
    "url": "https://my-agentic-rag-638797485217.us-central1.run.app",
    "appName": "app",
    "timeout": 180000
  },
  "gcs": {
    "projectId": "staging-adk",
    "bucketName": "authstate",
    "authFolder": "whatsapp-auth",
    "artifactsBucketName": "adk_artifact",
    "artifactsFolder": "",
    "mediaBucketName": "whatsapp-media-uploads"
  },
  "whatsapp": {
    "browser": ["WhatsApp ADK Bot", "Chrome", "1.0.0"],
    "printQRInTerminal": false,
    "markOnlineOnConnect": true,
    "syncFullHistory": false,
    "generateHighQualityLinkPreview": true,
    "defaultQueryTimeoutMs": 60000
  },
  "bot": {
    "sessionCleanupIntervalMs": 3600000,
    "sessionMaxAgeMs": 86400000,
    "logLevel": "info",
    "maxRetries": 3,
    "retryDelayMs": 5000
  },
  "terminal": {
    "allowedJids": ["120363423143842705@g.us"],
    "workspaceDir": "/home/$(whoami)/workspace/my-agentic-rag",
    "maxTextLen": 3000,
    "idleTtyTimeoutSec": 600,
    "allowedPrefixes": ["gcloud", "terraform", "gh", "copilot", "git", "ls", "cat", "echo", "jq", "tail", "head", "cd", "pwd", "find", "grep", "npm", "python", "pip", "docker", "kubectl", "make"],
    "blockedSymbols": [";", "&&", ">", ">>", "2>", "$(", ")"]
  }
}
EOF

echo "✅ Config updated with workspace directory"

echo ""
echo "================================================"
echo "4. Installing Bot Dependencies"
echo "================================================"

cd ~/whatsapp-bot
npm install --production

echo ""
echo "================================================"
echo "5. Setting up Systemd Service"
echo "================================================"

# Get current user and working directory
CURRENT_USER=$(whoami)
WORKING_DIR=$(pwd)

# Create systemd service with environment variables
sudo tee /etc/systemd/system/whatsapp-bot.service > /dev/null <<EOF
[Unit]
Description=WhatsApp Bot with Full DevOps Access
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$WORKING_DIR
ExecStart=/usr/bin/node index.js
Restart=always
RestartSec=10
Environment=NODE_ENV=production
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=whatsapp-bot

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and restart service
sudo systemctl daemon-reload
sudo systemctl enable whatsapp-bot
sudo systemctl restart whatsapp-bot

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
echo "🔐 IMPORTANT: GitHub Authentication Required!"
echo ""
echo "To enable GitHub operations, SSH into the VM and authenticate:"
echo ""
echo "  gcloud compute ssh $VM_NAME --project=$PROJECT --zone=$ZONE"
echo ""
echo "Then run these commands on the VM:"
echo "  # Authenticate GitHub CLI"
echo "  gh auth login"
echo ""
echo "  # Authenticate GitHub Copilot"
echo "  gh copilot auth"
echo ""
echo "  # Set up Google Cloud credentials"
echo "  gcloud auth login"
echo "  gcloud config set project staging-adk"
echo "  gcloud auth application-default login"
echo ""
echo "  # Configure git"
echo "  git config --global user.name 'Your Name'"
echo "  git config --global user.email 'your-email@example.com'"
echo ""
echo "📋 Useful Commands:"
echo "  View logs:   gcloud compute ssh $VM_NAME --project=$PROJECT --zone=$ZONE --command='sudo journalctl -u whatsapp-bot -f'"
echo "  Check status: gcloud compute ssh $VM_NAME --project=$PROJECT --zone=$ZONE --command='sudo systemctl status whatsapp-bot'"
echo "  Restart bot: gcloud compute ssh $VM_NAME --project=$PROJECT --zone=$ZONE --command='sudo systemctl restart whatsapp-bot'"
echo ""
