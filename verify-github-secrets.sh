#!/bin/bash

# 🧪 GitHub Secrets Verification Script
# This script helps verify that GitHub secrets are properly configured

set -e

echo "🔍 GitHub Secrets Verification"
echo "=============================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if gh CLI is authenticated
echo -e "\n📋 Step 1: Checking GitHub CLI authentication..."
if gh auth status > /dev/null 2>&1; then
    echo -e "${GREEN}✅ GitHub CLI is authenticated${NC}"
else
    echo -e "${RED}❌ GitHub CLI is not authenticated${NC}"
    echo "Run: gh auth login"
    exit 1
fi

# Try to check secrets (this might fail due to permissions)
echo -e "\n📋 Step 2: Attempting to list repository secrets..."
if gh secret list --repo Michaelktker/my-agentic-rag > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Can access repository secrets${NC}"
    gh secret list --repo Michaelktker/my-agentic-rag
else
    echo -e "${YELLOW}⚠️  Cannot list secrets (permission issue)${NC}"
    echo "This is expected if using a limited token."
    echo "Please manually verify secrets at:"
    echo "https://github.com/Michaelktker/my-agentic-rag/settings/secrets/actions"
fi

# Show the required secret values
echo -e "\n📋 Step 3: Required secret values:"
echo "=================================="
echo "WIF_PROVIDER:"
echo "projects/454188184539/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
echo ""
echo "WIF_SERVICE_ACCOUNT:"
echo "github-actions@staging-adk.iam.gserviceaccount.com"
echo ""
echo "WIF_PROVIDER_PROD:"
echo "projects/638797485217/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
echo ""
echo "WIF_SERVICE_ACCOUNT_PROD:"
echo "github-actions@production-adk.iam.gserviceaccount.com"

echo -e "\n📋 Step 4: Testing workflow trigger..."
echo "After adding secrets, push a commit to test:"
echo "git commit --allow-empty -m 'test: trigger staging deployment'"
echo "git push origin main"

echo -e "\n✅ Verification complete!"
echo "Add the secrets manually, then run the test command above."