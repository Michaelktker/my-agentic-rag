#!/bin/bash

echo "📋 GitHub Secrets Import Helper"
echo "==============================="
echo ""
echo "The GitHub CLI method failed due to permission issues."
echo "Here are 3 alternative ways to add your secrets:"
echo ""

echo "🔗 METHOD 1: Manual Copy-Paste (Recommended)"
echo "1. Open: https://github.com/Michaelktker/my-agentic-rag/settings/secrets/actions"
echo "2. Click 'New repository secret'"
echo "3. Copy each line from github-secrets.env (format: NAME=value)"
echo ""

echo "📱 METHOD 2: Browser Extension"
echo "Use a password manager or browser extension to auto-fill forms"
echo ""

echo "🔧 METHOD 3: Personal Access Token"
echo "Create a new GitHub Personal Access Token with 'repo' and 'admin:repo_hook' scopes"
echo "Then re-run the GitHub CLI with: gh auth login --with-token"
echo ""

echo "📄 All secrets are available in: github-secrets.env"
echo "📊 Total secrets to add: $(grep -c "^[A-Z]" github-secrets.env)"
echo ""
echo "🎯 Priority Secrets (add these first if doing manually):"
echo "  - STAGING_PROJECT_ID"
echo "  - PROD_PROJECT_ID"
echo "  - REGION" 
echo "  - DATA_STORE_ID_STAGING"
echo "  - DATA_STORE_ID_PROD"