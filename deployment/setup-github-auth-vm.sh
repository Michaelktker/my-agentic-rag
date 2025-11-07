#!/bin/bash
# ============================================================================
# GitHub Authentication Setup for VM
# ============================================================================
#
# PURPOSE:
#   Configure GitHub CLI authentication on the WhatsApp bot VM so that
#   Copilot CLI can push commits to GitHub
#
# USAGE:
#   ./deployment/setup-github-auth-vm.sh <GITHUB_TOKEN>
#
# PREREQUISITES:
#   - GitHub Personal Access Token with repo permissions
#   - Create token at: https://github.com/settings/tokens?type=beta
#   - Required permissions: Contents (Read/Write), Pull requests (Read/Write)
#
# ============================================================================

set -e

if [ -z "$1" ]; then
    echo "❌ Error: GitHub token not provided"
    echo ""
    echo "Usage: $0 <GITHUB_TOKEN>"
    echo ""
    echo "To create a GitHub token:"
    echo "1. Go to: https://github.com/settings/tokens?type=beta"
    echo "2. Click 'Generate new token' (Fine-grained)"
    echo "3. Set repository access: 'All repositories' or select 'my-agentic-rag'"
    echo "4. Set permissions:"
    echo "   - Contents: Read and write"
    echo "   - Pull requests: Read and write"
    echo "5. Generate token and copy it"
    echo "6. Run: $0 ghp_your_token_here"
    exit 1
fi

GITHUB_TOKEN="$1"
PROJECT="staging-adk"
ZONE="us-central1-a"
VM_NAME="whatsapp-bot"

echo "==================================="
echo "Setting up GitHub Authentication"
echo "==================================="

gcloud compute ssh "$VM_NAME" \
  --project="$PROJECT" \
  --zone="$ZONE" \
  --command="bash -s" <<ENDSSH
set -e

echo "📝 Authenticating GitHub CLI with token..."

# Login using token
echo "$GITHUB_TOKEN" | gh auth login --with-token

# Setup git credential helper
gh auth setup-git

echo "✅ GitHub CLI authenticated"

# Configure git identity
git config --global user.name "Michaelktker"
git config --global user.email "michaelktker@gmail.com"

echo "✅ Git identity configured"

# Verify authentication
echo ""
echo "==================================="
echo "Verification:"
echo "==================================="
gh auth status

echo ""
echo "Git config:"
git config --global --list | grep -E 'user|credential'

echo ""
echo "==================================="
echo "✅ GitHub Authentication Complete!"
echo "==================================="
echo ""
echo "Your Copilot CLI can now push to GitHub!"
echo "Test with: /cop commit and push changes"
ENDSSH

echo ""
echo "==================================="
echo "✅ Setup Complete!"
echo "==================================="
echo ""
echo "Your bot can now:"
echo "  • Commit changes via Copilot CLI"
echo "  • Push to GitHub repositories"
echo "  • Create pull requests"
echo ""
