# 🔐 How to Add GitHub Repository Secrets

## Step-by-Step Visual Guide

### 1. Navigate to Repository Settings
- Go to your repository: `https://github.com/Michaelktker/my-agentic-rag`
- Click the **"Settings"** tab (top right of the repository)

### 2. Find Secrets and Variables
- In the left sidebar, scroll down to **"Security"**
- Click **"Secrets and variables"**
- Click **"Actions"**

### 3. Add Each Secret
For each of the 4 secrets, follow these steps:

#### A. Click "New repository secret" (green button)

#### B. Fill in the form:
**Name:** (exactly as shown, case-sensitive)
**Secret:** (copy-paste the exact value)

#### C. Click "Add secret" (green button)

## 🔑 The 4 Secrets to Add

### Secret #1
```
Name: WIF_PROVIDER
Secret: projects/454188184539/locations/global/workloadIdentityPools/github-pool/providers/github-provider
```

### Secret #2
```
Name: WIF_SERVICE_ACCOUNT
Secret: github-actions@staging-adk.iam.gserviceaccount.com
```

### Secret #3
```
Name: WIF_PROVIDER_PROD
Secret: projects/638797485217/locations/global/workloadIdentityPools/github-pool/providers/github-provider
```

### Secret #4
```
Name: WIF_SERVICE_ACCOUNT_PROD
Secret: github-actions@production-adk.iam.gserviceaccount.com
```

## ✅ Verification

After adding all 4 secrets, you should see them listed like this:
```
WIF_PROVIDER                    ••••••••••••••••••••
WIF_SERVICE_ACCOUNT            ••••••••••••••••••••
WIF_PROVIDER_PROD              ••••••••••••••••••••
WIF_SERVICE_ACCOUNT_PROD       ••••••••••••••••••••
```

The actual values will be hidden with dots for security.

## 🚨 Important Notes

- **Names are case-sensitive** - must match exactly
- **No extra spaces** in names or values
- **Copy-paste values** to avoid typos
- Values will be **hidden** after saving (this is normal)

## 🧪 Test After Adding

Once all 4 secrets are added:
1. Go to Actions tab: `https://github.com/Michaelktker/my-agentic-rag/actions`
2. The latest workflow run should now pass the authentication step
3. Or push a new commit to trigger a fresh test

## 🔧 Direct Link

Go directly to the secrets page:
https://github.com/Michaelktker/my-agentic-rag/settings/secrets/actions