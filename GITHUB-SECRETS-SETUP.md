# 🔐 GitHub Secrets Setup Instructions

## ❌ Current Issue
The GitHub Actions workflow is failing because the required secrets are not configured in your repository.

## 🛠️ Manual Setup Required

### Step 1: Add Repository Secrets
Go to your repository settings: `https://github.com/Michaelktker/my-agentic-rag/settings/secrets/actions`

Click **"New repository secret"** and add each of these:

#### Required Secrets:
```
Name: WIF_PROVIDER
Value: projects/454188184539/locations/global/workloadIdentityPools/github-pool/providers/github-provider

Name: WIF_SERVICE_ACCOUNT  
Value: github-actions@staging-adk.iam.gserviceaccount.com

Name: WIF_PROVIDER_PROD
Value: projects/638797485217/locations/global/workloadIdentityPools/github-pool/providers/github-provider

Name: WIF_SERVICE_ACCOUNT_PROD
Value: github-actions@production-adk.iam.gserviceaccount.com
```

### Step 2: Verify Secrets
After adding the secrets, you should see them listed (values will be hidden) at:
`https://github.com/Michaelktker/my-agentic-rag/settings/secrets/actions`

### Step 3: Test the Workflow
1. Make a small change to any file
2. Commit and push to `main` branch
3. Check GitHub Actions tab for successful deployment

## 🔍 Troubleshooting
If you still see authentication errors:
1. Verify all 4 secrets are added exactly as shown above
2. Check that secret names match exactly (case-sensitive)
3. Ensure there are no extra spaces in the secret values

## ✅ Success Indicators
Once working, you should see:
- ✅ "Authenticate to Google Cloud" step passes
- ✅ Cloud Build submission succeeds
- ✅ Staging deployment completes successfully