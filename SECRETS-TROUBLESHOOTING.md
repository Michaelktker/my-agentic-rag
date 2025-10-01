# 🚨 GitHub Secrets Not Working - Troubleshooting Guide

## Current Issue
The GitHub Actions workflow is still showing:
```
Error: the GitHub Action workflow must specify exactly one of "workload_identity_provider" or "credentials_json"
```

This means the secrets are NOT being injected into the workflow environment.

## 🔍 Diagnostic Steps

### 1. Check the Debug Workflow
I've created a debug workflow that will run and show if secrets are available:
- Go to: https://github.com/Michaelktker/my-agentic-rag/actions
- Look for "Debug Secrets" workflow
- Check the output to see if secrets are detected

### 2. Common Issues and Solutions

#### Issue A: Secrets Not Actually Added
**Symptoms:** Debug workflow shows "❌ WIF_PROVIDER is empty or not set"
**Solution:** 
- Go to: https://github.com/Michaelktker/my-agentic-rag/settings/secrets/actions
- Verify all 4 secrets are listed
- If missing, add them using "New repository secret"

#### Issue B: Repository Permissions
**Symptoms:** Secrets exist but still not injected
**Solution:**
- Check if Actions are enabled: Settings → Actions → General
- Ensure "Allow all actions and reusable workflows" is selected
- Check if repository is private (secrets work differently)

#### Issue C: Secret Names Don't Match
**Symptoms:** Some secrets work, others don't
**Solution:**
- Verify exact spelling: WIF_PROVIDER (not wif_provider)
- Check for extra spaces in secret names
- Ensure no special characters in names

#### Issue D: Organization/Enterprise Restrictions
**Symptoms:** All seems correct but secrets still don't work
**Solution:**
- Check organization settings if this is an org repo
- Verify no enterprise policies blocking secrets
- Try creating a test repository to isolate the issue

### 3. Manual Verification Steps

#### Step A: Check Repository Settings
```bash
# Repository URL
https://github.com/Michaelktker/my-agentic-rag

# Settings → Secrets and variables → Actions
https://github.com/Michaelktker/my-agentic-rag/settings/secrets/actions
```

#### Step B: Verify Secret Values
The secrets should be:
```
WIF_PROVIDER: projects/454188184539/locations/global/workloadIdentityPools/github-pool/providers/github-provider
WIF_SERVICE_ACCOUNT: github-actions@staging-adk.iam.gserviceaccount.com
WIF_PROVIDER_PROD: projects/638797485217/locations/global/workloadIdentityPools/github-pool/providers/github-provider
WIF_SERVICE_ACCOUNT_PROD: github-actions@production-adk.iam.gserviceaccount.com
```

#### Step C: Test with Manual Trigger
- Go to Actions tab
- Find "Debug Secrets" workflow
- Click "Run workflow" to trigger manually
- Check the output

### 4. Alternative Solutions

#### Option A: Use Repository Environment Secrets
Instead of repository secrets, try environment secrets:
1. Settings → Environments
2. Create "staging" environment
3. Add secrets to that environment
4. Reference in workflow with `environment: staging`

#### Option B: Use Service Account Key (Temporary)
As a last resort, you can use a service account key:
1. Create and download a service account key JSON
2. Add it as `GOOGLE_CREDENTIALS` secret
3. Modify workflow to use `credentials_json: ${{ secrets.GOOGLE_CREDENTIALS }}`

## 🎯 Next Steps

1. **Check the debug workflow output** first
2. **Verify secrets exist** in repository settings
3. **Try manual workflow trigger** if automatic doesn't work
4. **Report findings** so we can determine the exact issue

## 🔗 Quick Links
- [Repository Secrets](https://github.com/Michaelktker/my-agentic-rag/settings/secrets/actions)
- [Actions Settings](https://github.com/Michaelktker/my-agentic-rag/settings/actions)
- [GitHub Actions](https://github.com/Michaelktker/my-agentic-rag/actions)