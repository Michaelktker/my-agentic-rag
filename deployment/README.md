# Deployment Guide

This directory contains the complete infrastructure configuration and deployment setup for the Agentic RAG system. The infrastructure is managed using Terraform and deployed across multiple Google Cloud Platform projects.

## 🏗️ Infrastructure Overview

### Multi-Project Architecture

The system uses a multi-project setup for security and environment isolation:

- **`production-adk`**: Production environment and CI/CD runner
- **`staging-adk`**: Staging/development environment

### Key Components

- **Cloud Run**: Serverless container hosting for the ADK agent
- **Artifact Registry**: Docker image storage and management
- **Secret Manager**: Secure GitHub token storage
- **Vertex AI Search**: Document indexing and retrieval backend
- **Cloud Build**: CI/CD pipeline automation
- **IAM**: Service account and permission management

## 📁 Directory Structure

```
deployment/
├── terraform/              # Production infrastructure
│   ├── apis.tf            # Google Cloud APIs
│   ├── backend.tf         # Terraform state backend
│   ├── build_triggers.tf  # Cloud Build triggers
│   ├── github.tf          # GitHub integration
│   ├── iam.tf             # IAM roles and permissions
│   ├── service.tf         # Cloud Run service
│   ├── storage.tf         # Storage buckets and data stores
│   └── vars/
│       └── env.tfvars     # Production environment variables
└── terraform/dev/         # Staging infrastructure
    ├── apis.tf            # Development APIs
    ├── backend.tf         # Development state backend
    ├── iam.tf             # Development IAM
    ├── service.tf         # Development Cloud Run
    ├── storage.tf         # Development storage
    └── vars/
        └── env.tfvars     # Staging environment variables
```

## 🚀 Deployment Process

### Prerequisites

1. **Terraform**: Install [Terraform CLI](https://developer.hashicorp.com/terraform/downloads)
2. **Google Cloud CLI**: Install and authenticate with `gcloud auth login`
3. **Project Setup**: Ensure both projects exist and billing is enabled
4. **GitHub Token**: Create a Personal Access Token with required scopes

### Initial Infrastructure Setup

#### 1. Deploy Staging Environment

```bash
cd deployment/terraform/dev

# Initialize Terraform
terraform init

# Plan deployment
terraform plan -var-file=vars/env.tfvars

# Apply configuration
terraform apply -var-file=vars/env.tfvars
```

#### 2. Deploy Production Environment

```bash
cd deployment/terraform

# Initialize Terraform  
terraform init

# Plan deployment
terraform plan -var-file=vars/env.tfvars

# Apply configuration
terraform apply -var-file=vars/env.tfvars
```

### GitHub Token Setup

After infrastructure deployment, configure the GitHub token in Secret Manager:

```bash
# Create secret in staging
gcloud secrets create github-personal-access-token \
  --project=staging-adk \
  --data-file=-  # Enter token when prompted

# Create secret in production  
gcloud secrets create github-personal-access-token \
  --project=production-adk \
  --data-file=-  # Enter token when prompted
```

## 🔄 CI/CD Pipeline

### Build Triggers

The system includes two Cloud Build triggers:

1. **Staging Trigger** (`deploy-my-agentic-rag-staging`)
   - **Event**: Push to `main` branch
   - **Action**: Automatic deployment to staging
   - **Project**: `production-adk` (runner project)
   - **Target**: `staging-adk` environment

2. **Production Trigger** (`deploy-my-agentic-rag`)
   - **Event**: Manual trigger
   - **Action**: Deployment with manual approval
   - **Project**: `production-adk` 
   - **Target**: `production-adk` environment

### Deployment Workflow

```mermaid
graph TD
    A[Push to main] --> B[Staging Build Triggered]
    B --> C[Deploy to Staging]
    C --> D[Test Staging Environment]
    D --> E[Manual Production Trigger]
    E --> F[Production Approval Required]
    F --> G[Deploy to Production]
```

### Triggering Deployments

```bash
# Staging (automatic on push to main)
git push origin main

# Production (manual trigger)
gcloud builds triggers run deploy-my-agentic-rag \
  --project=production-adk \
  --branch=main
```

## 🔐 Security Configuration

### Service Accounts

- **Cloud Run Service Account**: `{project-id}-compute@developer.gserviceaccount.com`
- **Required Roles**:
  - `secretmanager.secretAccessor`: Access GitHub tokens
  - `aiplatform.user`: Vertex AI Search access
  - `logging.logWriter`: Application logging

### Secret Management

GitHub tokens are stored securely in Google Secret Manager:

- **Secret Name**: `github-personal-access-token`
- **Access**: Limited to Cloud Run service accounts
- **Rotation**: Manual process (update secret versions)

### Required GitHub Token Scopes

- `repo`: Full repository access
- `read:org`: Organization member access
- `read:user`: User profile access

## 🌐 Service URLs

### Staging Environment
- **Service**: `https://my-agentic-rag-aktu2chyfa-uc.a.run.app`
- **Web UI**: `https://my-agentic-rag-aktu2chyfa-uc.a.run.app/dev-ui/`
- **Health**: `https://my-agentic-rag-aktu2chyfa-uc.a.run.app/health`

### Production Environment
- **Service**: `https://my-agentic-rag-dyrqvuqk4a-uc.a.run.app`
- **Web UI**: `https://my-agentic-rag-dyrqvuqk4a-uc.a.run.app/dev-ui/`
- **Health**: `https://my-agentic-rag-dyrqvuqk4a-uc.a.run.app/health`

## 🔧 Maintenance & Updates

### Infrastructure Updates

1. **Modify Terraform Configuration**: Update `.tf` files as needed
2. **Plan Changes**: Run `terraform plan` to review changes
3. **Apply Updates**: Run `terraform apply` to deploy changes
4. **Verify Deployment**: Check services and functionality

### Service Updates

Application updates are deployed automatically through the CI/CD pipeline:

1. **Code Changes**: Modify application code
2. **Commit & Push**: Push changes to `main` branch
3. **Staging Deploy**: Automatic deployment to staging
4. **Test & Validate**: Verify functionality in staging
5. **Production Deploy**: Manual trigger and approval

### Token Rotation

To rotate GitHub tokens:

```bash
# Update staging secret
echo "NEW_TOKEN" | gcloud secrets versions add github-personal-access-token \
  --project=staging-adk \
  --data-file=-

# Update production secret
echo "NEW_TOKEN" | gcloud secrets versions add github-personal-access-token \
  --project=production-adk \
  --data-file=-

# Restart services to pick up new token
gcloud run services update-traffic my-agentic-rag \
  --to-latest --region=us-central1
```

### CI/CD Service Account Permissions

**Important**: The CI/CD service accounts need access to the GitHub token secret for PR checks and integration tests to pass:

```bash
# Grant production CI service account access to GitHub token
gcloud secrets add-iam-policy-binding github-personal-access-token \
  --project=production-adk \
  --member="serviceAccount:my-agentic-rag-cb@production-adk.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Grant staging GitHub Actions service account access to GitHub token  
gcloud secrets add-iam-policy-binding github-personal-access-token \
  --project=staging-adk \
  --member="serviceAccount:github-actions@staging-adk.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

**Required Service Account Roles for CI/CD:**
- `secretmanager.secretAccessor`: Access to GitHub tokens
- `cloudbuild.builds.builder`: Execute build steps
- `aiplatform.user`: Access Vertex AI services for testing
- `logging.logWriter`: Write build logs

## 📊 Monitoring & Troubleshooting

### Health Monitoring

```bash
# Check service health
curl https://service-url/health

# View service logs
gcloud run services logs read my-agentic-rag \
  --region=us-central1 --project=PROJECT_ID

# Monitor build status
gcloud builds list --project=production-adk --limit=10
```

### Common Issues

#### Deployment Failures
- Check build logs: `gcloud builds log BUILD_ID`
- Verify IAM permissions
- Ensure secrets exist and are accessible

#### PR Check Failures
- **Common Issue**: CI service account lacks access to GitHub token secret
- **Solution**: Grant `secretmanager.secretAccessor` role to CI service accounts
- **Verification**: Check integration tests can access MCP GitHub tools

#### Service Errors
- Check Cloud Run logs for application errors
- Verify GitHub token validity and scopes
- Test Vertex AI Search connectivity

## 📚 Additional Resources

- [Google Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Terraform Google Provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
- [Cloud Build Configuration](https://cloud.google.com/build/docs/configuring-builds/create-basic-configuration)
- [Secret Manager Best Practices](https://cloud.google.com/secret-manager/docs/best-practices)

---

*This deployment guide reflects the current infrastructure setup and should be updated as the system evolves.*