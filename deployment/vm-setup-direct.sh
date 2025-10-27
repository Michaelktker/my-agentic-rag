#!/bin/bash
set -e

echo "==================================="
echo "WhatsApp Bot VM Setup Script"
echo "==================================="

# Get current user and home directory
CURRENT_USER=$(whoami)
HOME_DIR="/home/$CURRENT_USER"
APP_DIR="$HOME_DIR/whatsapp-bot"

# Create application directory
echo "📂 Creating application directory..."
mkdir -p "$APP_DIR"
cd "$APP_DIR"

echo "✅ Application directory created at: $APP_DIR"
echo "📦 Please copy your application files to this directory"
echo ""
echo "From your local machine, run:"
echo "  gcloud compute scp --recurse /workspaces/my-agentic-rag/{index.js,package.json,package-lock.json,config.json} whatsapp-bot:~/whatsapp-bot/ --project=staging-adk --zone=us-central1-a"
echo ""
echo "Then run: ~/whatsapp-bot/install-deps.sh"
