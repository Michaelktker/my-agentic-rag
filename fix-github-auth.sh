#!/bin/bash

# 🚨 GitHub Secrets Verification and Setup Guide
# This script helps diagnose and fix GitHub Actions authentication issues

set -e

echo "🔍 GitHub Actions Authentication Troubleshooting"
echo "================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "\n${BLUE}📋 Step 1: Verify Repository Settings${NC}"
echo "Repository: https://github.com/Michaelktker/my-agentic-rag"
echo "Current branch: $(git branch --show-current)"
echo "Latest commit: $(git log -1 --oneline)"

echo -e "\n${BLUE}📋 Step 2: Required GitHub Secrets${NC}"
echo "Go to: https://github.com/Michaelktker/my-agentic-rag/settings/secrets/actions"
echo ""
echo "Add these EXACT secrets (copy-paste the values):"
echo ""
echo -e "${YELLOW}Secret Name: WIF_PROVIDER${NC}"
echo "Value: projects/454188184539/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
echo ""
echo -e "${YELLOW}Secret Name: WIF_SERVICE_ACCOUNT${NC}" 
echo "Value: github-actions@staging-adk.iam.gserviceaccount.com"
echo ""
echo -e "${YELLOW}Secret Name: WIF_PROVIDER_PROD${NC}"
echo "Value: projects/638797485217/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
echo ""
echo -e "${YELLOW}Secret Name: WIF_SERVICE_ACCOUNT_PROD${NC}"
echo "Value: github-actions@production-adk.iam.gserviceaccount.com"

echo -e "\n${BLUE}📋 Step 3: Common Issues and Solutions${NC}"
echo ""
echo "❌ If secrets are missing:"
echo "   - Click 'New repository secret' for each one"
echo "   - Copy-paste the EXACT values (no extra spaces)"
echo "   - Secret names are case-sensitive"
echo ""
echo "❌ If workflow still fails:"
echo "   - Delete and re-add all secrets"
echo "   - Ensure repository has Actions enabled"
echo "   - Check repository permissions"

echo -e "\n${BLUE}📋 Step 4: Test the Fix${NC}"
echo "After adding secrets, run:"
echo "git commit --allow-empty -m 'test: verify GitHub secrets fix'"
echo "git push origin main"

echo -e "\n${BLUE}📋 Step 5: Verify Success${NC}"
echo "✅ Authentication step should pass"
echo "✅ Cloud Build should trigger"
echo "✅ No more 'workload_identity_provider' errors"

echo -e "\n${GREEN}🔧 Ready to add secrets? Open this URL:${NC}"
echo "https://github.com/Michaelktker/my-agentic-rag/settings/secrets/actions"