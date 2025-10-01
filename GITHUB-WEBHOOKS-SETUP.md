# GitHub Webhook Configuration for Production Triggers

This document provides instructions for setting up automated production triggers with GitHub webhooks, approval workflows, and environment-specific variables.

## 🚀 Quick Setup Guide

### 1. Enable GitHub Actions Workflows

The repository now includes two automated workflows:

- **`.github/workflows/staging-deploy.yml`** - Automatically deploys to staging on push to main
- **`.github/workflows/production-deploy.yml`** - Deploys to production with approval workflow

### 2. Configure GitHub Secrets

Add the following secrets to your GitHub repository:

#### For Staging Environment
```bash
# Workload Identity Federation
WIF_PROVIDER=projects/123456789/locations/global/workloadIdentityPools/github-pool/providers/github-provider
WIF_SERVICE_ACCOUNT=github-actions@staging-adk.iam.gserviceaccount.com
```

#### For Production Environment  
```bash
# Workload Identity Federation for Production
WIF_PROVIDER_PROD=projects/987654321/locations/global/workloadIdentityPools/github-pool/providers/github-provider
WIF_SERVICE_ACCOUNT_PROD=github-actions@production-adk.iam.gserviceaccount.com
```

### 3. Create GitHub Environments

Create the following environments in your GitHub repository settings:

#### Staging Environment
- **Name**: `staging`
- **Protection Rules**: None (automatic deployment)
- **Environment Variables**:
  - `STAGING_PROJECT_ID`: `staging-adk`
  - `REGION`: `us-central1`

#### Production Approval Environment
- **Name**: `production-approval`
- **Protection Rules**: 
  - ✅ Required reviewers (add team leads/admins)
  - ✅ Wait timer: 5 minutes (optional)
  - ✅ Restrict to selected branches: `main`

#### Production Environment
- **Name**: `production`
- **Protection Rules**:
  - ✅ Required reviewers (add team leads/admins)
  - ✅ Restrict to selected branches: `main`
- **Environment Variables**:
  - `PROD_PROJECT_ID`: `production-adk`
  - `REGION`: `us-central1`

## 🔧 Automated Triggers Setup

### Staging Deployment (Automatic)

**Triggers on:**
- Push to `main` branch
- Changes to: `app/**`, `data_ingestion/**`, `tests/**`, `pyproject.toml`, `uv.lock`, `.cloudbuild/**`

**Process:**
1. Code pushed to main → GitHub Actions triggered
2. Authenticate with Google Cloud using Workload Identity
3. Submit Cloud Build job for staging deployment
4. Wait for completion and validate deployment
5. Comment on PR with deployment status (if applicable)

### Production Deployment (With Approval)

**Triggers on:**
- Successful completion of staging deployment
- Manual workflow dispatch

**Process:**
1. Validate staging deployment success
2. **APPROVAL REQUIRED** - Manual approval from authorized users
3. Deploy to production with full data pipeline setup
4. Run production smoke tests
5. Create GitHub release on success
6. Create issue on failure

## 📋 Manual Deployment Options

### Option 1: Enhanced Script (Recommended)
```bash
# Interactive deployment with approval workflow
./deploy-to-production-enhanced.sh

# Automated deployment (skip approval)
./deploy-to-production-enhanced.sh --auto

# Wait for completion
./deploy-to-production-enhanced.sh --auto --wait
```

### Option 2: GitHub Actions Manual Trigger
1. Go to GitHub Actions → "Deploy to Production"
2. Click "Run workflow"
3. Fill in required parameters
4. Wait for approval (if not admin)
5. Monitor deployment progress

### Option 3: Direct Cloud Build
```bash
gcloud builds submit \
  --config=.cloudbuild/deploy-to-prod.yaml \
  --project=production-adk \
  --region=us-central1
```

## 🔐 Security & Approval Workflow

### Approval Process
1. **Automatic Staging**: Code changes automatically deploy to staging
2. **Production Gate**: Manual approval required for production deployments
3. **Reviewers**: Only designated team members can approve production deployments
4. **Audit Trail**: All deployments logged in GitHub Actions history

### Security Measures
- ✅ Workload Identity Federation (no service account keys)
- ✅ Environment-specific permissions
- ✅ Approval workflow for production
- ✅ Deployment validation and health checks
- ✅ Automated rollback capabilities

## 🌍 Environment-Specific Variables

### Staging (`config/staging.env`)
- Aggressive caching disabled for testing
- Lower resource limits
- Daily data pipeline schedule
- Debug logging enabled

### Production (`config/production.env`)  
- Optimized for performance and cost
- Higher resource limits with auto-scaling
- Manual data pipeline triggers
- Warning-level logging
- Enhanced monitoring and alerting

## 🚨 Troubleshooting

### Common Issues

1. **Workload Identity Federation Setup**
   ```bash
   # Verify WIF configuration
   gcloud iam workload-identity-pools list --location=global
   ```

2. **GitHub Actions Permission Issues**
   - Ensure `id-token: write` permission is set
   - Verify service account has necessary Cloud Build permissions

3. **Approval Workflow Not Working**
   - Check GitHub environment protection rules
   - Verify required reviewers are configured
   - Ensure branch protection is set to `main`

### Support Commands

```bash
# Check current deployments
gcloud run services list --project=staging-adk
gcloud run services list --project=production-adk

# View recent builds
gcloud builds list --project=staging-adk --limit=5
gcloud builds list --project=production-adk --limit=5

# Monitor service logs
gcloud logs read --project=production-adk --resource-type=cloud_run_revision
```

## 📊 Monitoring & Observability

- **GitHub Actions**: Deployment history and logs
- **Cloud Build**: Build logs and artifacts
- **Cloud Run**: Service metrics and logs
- **Cloud Monitoring**: Custom dashboards and alerting
- **Looker Studio**: Long-term analytics and reporting

## 🎯 Next Steps

1. **Set up GitHub secrets** with Workload Identity Federation
2. **Configure GitHub environments** with approval rules
3. **Test the workflow** with a small change to staging
4. **Approve and deploy** to production
5. **Monitor and iterate** based on deployment metrics