#!/bin/bash
# ============================================================================
# Install CLI Tools for WhatsApp Terminal
# ============================================================================
#
# PURPOSE:
#   Install Terraform, GitHub CLI, and Copilot CLI on the WhatsApp bot VM
#   These tools will be accessible via the WhatsApp terminal handler
#
# USAGE:
#   gcloud compute ssh whatsapp-bot --project=staging-adk --zone=us-central1-a \
#     --command='bash -s' < deployment/install-cli-tools.sh
#
# WHAT IT INSTALLS:
#   - Terraform (latest stable)
#   - GitHub CLI (gh)
#   - GitHub Copilot CLI (requires GitHub account with Copilot)
#
# ============================================================================
set -e

echo "==================================="
echo "Installing CLI Tools for Terminal"
echo "==================================="

# ============================================================================
# 1. Install Terraform
# ============================================================================
echo ""
echo "📦 Installing Terraform..."

# Add HashiCorp GPG key
curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg

# Add HashiCorp repository
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list

# Install Terraform
sudo apt-get update
sudo apt-get install -y terraform

echo "✅ Terraform installed:"
terraform version

# ============================================================================
# 2. Install GitHub CLI (gh)
# ============================================================================
echo ""
echo "📦 Installing GitHub CLI (gh)..."

# Add GitHub CLI repository
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null

# Install GitHub CLI
sudo apt-get update
sudo apt-get install -y gh

echo "✅ GitHub CLI installed:"
gh --version

# ============================================================================
# 3. Install GitHub Copilot CLI
# ============================================================================
echo ""
echo "📦 Installing GitHub Copilot CLI..."

# Install Copilot CLI globally via npm
sudo npm install -g @github/copilot

echo "✅ Copilot CLI installed:"
copilot --version || echo "⚠️  Copilot CLI may need authentication"

# ============================================================================
# 4. Summary
# ============================================================================
echo ""
echo "==================================="
echo "✅ CLI Tools Installation Complete"
echo "==================================="
echo ""
echo "Installed tools:"
echo "  • Terraform: $(terraform version | head -1)"
echo "  • GitHub CLI: $(gh --version | head -1)"
echo "  • Copilot CLI: $(npm list -g @github/copilot 2>/dev/null | grep @github/copilot || echo 'installed')"
echo ""
echo "Next steps:"
echo ""
echo "1. GitHub CLI authentication (if needed):"
echo "   gh auth login"
echo ""
echo "2. Copilot CLI authentication (if needed):"
echo "   copilot /login"
echo ""
echo "3. Test from WhatsApp:"
echo "   /help"
echo "   /sh terraform version"
echo "   /sh gh repo list"
echo "   /cop ask \"explain terraform\""
echo ""
