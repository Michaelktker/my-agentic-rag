# Disabled GitHub Actions Workflows

These GitHub Actions workflows have been disabled to avoid conflicts with Google Cloud Build triggers.

## Why Disabled?

This project uses **Terraform-managed Google Cloud Build triggers** for CI/CD instead of GitHub Actions:

- **PR Checks**: `pr-my-agentic-rag` trigger (runs `.cloudbuild/pr_checks.yaml`)
- **Staging Deploy**: `cd-my-agentic-rag` trigger (runs `.cloudbuild/staging.yaml`) 
- **Production Deploy**: `deploy-my-agentic-rag` trigger (runs `.cloudbuild/deploy-to-prod.yaml`)

## Disabled Workflows

- `staging-deploy.yml` - Conflicts with Cloud Build staging trigger
- `production-deploy.yml` - Conflicts with Cloud Build production trigger  
- `debug-secrets.yml` - No longer needed

## Re-enabling

To re-enable GitHub Actions (not recommended):
```bash
mv .github/workflows-disabled/*.yml .github/workflows/
```

## Current CI/CD Architecture

```
GitHub Push/PR → GitHub App Webhook → Google Cloud Build → Deploy to GCP
```

Date disabled: October 3, 2025
Reason: Eliminate conflicts between GitHub Actions and Cloud Build triggers