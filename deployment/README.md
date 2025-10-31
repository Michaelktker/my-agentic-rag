# Deployment Guide# Deployment Guide



**Infrastructure**: Cloud Run + Cloud SQL PostgreSQL + Terraform  Complete infrastructure and deployment documentation for the WhatsApp ADK bot with Cloud SQL persistence.

**Services**: WhatsApp Bot (VM) + ADK Agent (Cloud Run) + MCP Servers

**Stack**: Cloud Run + Cloud SQL PostgreSQL + ADK + WhatsApp (Baileys) + MCP Servers

---

## 🏗️ Infrastructure Overview

## Quick Reference

### Multi-Project Architecture

### WhatsApp Bot Commands (Compute Engine VM)

```bashThe system uses a multi-project setup for security and environment isolation:

# View live logs

gcloud compute ssh whatsapp-bot --project=staging-adk --zone=us-central1-a \- **`production-adk`**: Production environment and CI/CD runner

  --command='sudo journalctl -u whatsapp-bot -f'- **`staging-adk`**: Staging/development environment



# Restart bot### Key Components

gcloud compute ssh whatsapp-bot --project=staging-adk --zone=us-central1-a \

  --command='sudo systemctl restart whatsapp-bot'- **Cloud Run**: Serverless container hosting for the ADK agent

- **Artifact Registry**: Docker image storage and management

# Deploy updates- **Secret Manager**: Secure GitHub token storage

./deployment/deploy-to-vm.sh- **Vertex AI Search**: Document indexing and retrieval backend

```- **Cloud Build**: CI/CD pipeline automation

- **IAM**: Service account and permission management

### Cloud Run Deployments

```bash## 📁 Directory Structure

# Staging (auto on push to main)

git push origin main```

deployment/

# Production (manual trigger)├── terraform/              # Production infrastructure

gcloud builds triggers run deploy-my-agentic-rag --project=production-adk --branch=main│   ├── apis.tf            # Google Cloud APIs

│   ├── backend.tf         # Terraform state backend

# Check deployment status│   ├── build_triggers.tf  # Cloud Build triggers

gcloud run services describe my-agentic-rag --region=us-central1 --project=staging-adk│   ├── github.tf          # GitHub integration

```│   ├── iam.tf             # IAM roles and permissions

│   ├── service.tf         # Cloud Run service

### Database Operations│   ├── storage.tf         # Storage buckets and data stores

```bash│   └── vars/

# Connection string (from Secret Manager)│       └── env.tfvars     # Production environment variables

gcloud secrets versions access latest --secret=adk-db-connection --project=staging-adk└── terraform/dev/         # Staging infrastructure

    ├── apis.tf            # Development APIs

# View database logs    ├── backend.tf         # Development state backend

gcloud logging read "resource.type=cloudsql_database" --project=staging-adk --limit=20    ├── iam.tf             # Development IAM

```    ├── service.tf         # Development Cloud Run

    ├── storage.tf         # Development storage

---    └── vars/

        └── env.tfvars     # Staging environment variables

## Architecture```



### Multi-Environment Setup## 🚀 Deployment Process

| Environment | Project ID | Purpose |

|-------------|-----------|---------|### Prerequisites

| Development | `staging-adk` | Local dev + dev Cloud SQL |

| Staging | `staging-adk` | Auto-deployed on push to main |1. **Terraform**: Install [Terraform CLI](https://developer.hashicorp.com/terraform/downloads)

| Production | `production-adk` | Manual approval required |2. **Google Cloud CLI**: Install and authenticate with `gcloud auth login`

3. **Project Setup**: Ensure both projects exist and billing is enabled

### Core Components4. **GitHub Token**: Create a Personal Access Token with required scopes



**Cloud Run** (`my-agentic-rag` service):### Initial Infrastructure Setup

- ADK FastAPI server

- 4 CPU, 8GB RAM#### 1. Deploy Staging Environment

- Connects to Cloud SQL via Unix socket

- Auto-scales 1-10 instances```bash

cd deployment/terraform/dev

**Cloud SQL PostgreSQL**:

- Dev: `db-f1-micro` (~$7/month)# Initialize Terraform

- Staging: `db-f1-micro` (~$7/month)  terraform init

- Production: `db-g1-small` with HA (~$50/month)

- Database: `adk_sessions`# Plan deployment

- User: `adk_app`terraform plan -var-file=vars/env.tfvars



**Compute Engine VM** (`whatsapp-bot`):# Apply configuration

- Node.js 20 WhatsApp botterraform apply -var-file=vars/env.tfvars

- Systemd service (auto-restart)```

- Connects to staging ADK endpoint

#### 2. Deploy Production Environment

**Secret Manager**:

- `github-pat-mcp`: GitHub token for MCP```bash

- `fal-api-key`: FAL.ai API keycd deployment/terraform

- `adk-db-password`: Database password

- `adk-db-connection`: Full connection string# Initialize Terraform  

terraform init

**Storage**:

- `adk_artifact`: Media files & generated content# Plan deployment

- `{project}-my-agentic-rag-logs-data`: Application logsterraform plan -var-file=vars/env.tfvars

- `{project}-my-agentic-rag-rag`: Document storage

# Apply configuration

---terraform apply -var-file=vars/env.tfvars

```

## Infrastructure Setup

### GitHub Token Setup

### Prerequisites

```bashAfter infrastructure deployment, configure the GitHub token and FAL API key in Secret Manager:

# Install tools

brew install terraform google-cloud-sdk```bash

# Create GitHub PAT secret in staging

# Authenticategcloud secrets create github-pat-mcp \

gcloud auth login  --project=staging-adk \

gcloud auth application-default login  --data-file=-  # Enter token when prompted



# Set project# Create GitHub PAT secret in production  

gcloud config set project staging-adkgcloud secrets create github-pat-mcp \

```  --project=production-adk \

  --data-file=-  # Enter token when prompted

### Deploy Infrastructure

# Create FAL API key secret in staging

#### 1. Development Environmentgcloud secrets create fal-api-key \

```bash  --project=staging-adk \

cd deployment/terraform/dev  --data-file=-  # Enter FAL API key when prompted

terraform init

terraform plan -var-file=vars/env.tfvars# Create FAL API key secret in production

terraform apply -var-file=vars/env.tfvarsgcloud secrets create fal-api-key \

```  --project=production-adk \

  --data-file=-  # Enter FAL API key when prompted

**Creates**:```

- Cloud SQL instance: `adk-sessions-staging-adk`

- Database: `adk_sessions`## 🔄 CI/CD Pipeline

- Secrets: `adk-db-password`, `adk-db-connection`

- Storage buckets### Build Triggers

- IAM permissions

The system includes two Cloud Build triggers:

#### 2. Staging & Production

```bash1. **Staging Trigger** (`deploy-my-agentic-rag-staging`)

cd deployment/terraform   - **Event**: Push to `main` branch

terraform init   - **Action**: Automatic deployment to staging

terraform plan -var-file=vars/env.tfvars   - **Project**: `production-adk` (runner project)

terraform apply -var-file=vars/env.tfvars   - **Target**: `staging-adk` environment

```

2. **Production Trigger** (`deploy-my-agentic-rag`)

**Creates**:   - **Event**: Manual trigger

- 2 Cloud SQL instances (staging + prod)   - **Action**: Deployment with manual approval

- Cloud Run services   - **Project**: `production-adk` 

- Build triggers   - **Target**: `production-adk` environment

- Secret Manager secrets

- All IAM bindings### Deployment Workflow



### Configure Secrets```mermaid

graph TD

```bash    A[Push to main] --> B[Staging Build Triggered]

# GitHub PAT (for MCP GitHub integration)    B --> C[Deploy to Staging]

echo "YOUR_GITHUB_TOKEN" | gcloud secrets create github-pat-mcp \    C --> D[Test Staging Environment]

  --project=staging-adk --data-file=-    D --> E[Manual Production Trigger]

    E --> F[Production Approval Required]

# FAL API Key (for AI model generation)    F --> G[Deploy to Production]

echo "YOUR_FAL_KEY" | gcloud secrets create fal-api-key \```

  --project=staging-adk --data-file=-

```### Triggering Deployments



---```bash

# Staging (automatic on push to main)

## Session Persistence (Cloud SQL)git push origin main



### How It Works# Production (manual trigger)

gcloud builds triggers run deploy-my-agentic-rag \

**Before (SQLite)**: Sessions lost on container restart    --project=production-adk \

**After (PostgreSQL)**: Sessions persist across:  --branch=main

- ✅ Container restarts```

- ✅ Deployments

- ✅ Scaling events (including scale-to-zero)## 🔐 Security Configuration

- ✅ Multiple instances (shared state)

### Service Accounts

### Configuration

- **Cloud Run Service Account**: `{project-id}-compute@developer.gserviceaccount.com`

**app/server.py**:- **Required Roles**:

```python  - `secretmanager.secretAccessor`: Access GitHub tokens and FAL API key

session_service_uri = os.getenv(  - `aiplatform.user`: Vertex AI Search access

    "DB_CONNECTION_STRING",  # From Secret Manager  - `logging.logWriter`: Application logging

    "sqlite:///./sessions.db"  # Fallback for local dev

)### Secret Management

```

Secrets are stored securely in Google Secret Manager:

**Cloud Run** (auto-configured by Terraform):

- Environment variable: `DB_CONNECTION_STRING` → Secret Manager- **GitHub PAT**: `github-pat-mcp`

- Unix socket: `/cloudsql/project:region:instance`- **FAL API Key**: `fal-api-key`

- IAM role: `roles/cloudsql.client`- **Access**: Limited to Cloud Run service accounts

- **Rotation**: Manual process (update secret versions)

### Verify Persistence

### Required GitHub Token Scopes

```bash

# Check Cloud SQL connection- `repo`: Full repository access

gcloud sql instances describe adk-sessions-staging-adk \- `read:org`: Organization member access

  --project=staging-adk \- `read:user`: User profile access

  --format="value(connectionName)"

### Required FAL API Key

# View Cloud Run logs

gcloud run services logs read my-agentic-rag \- **Source**: Generate from [https://fal.ai/dashboard](https://fal.ai/dashboard)

  --region=us-central1 \- **Scope**: API access for image/video generation models

  --project=staging-adk \- **Format**: `{key_id}:{secret}` (e.g., `14fcfa4a-1f68-4e1f-ac71-75088668eeac:ab3d5f08a5f11e46b820aa729748027e`)

  --limit=20 | grep "Session Service"

## 🌐 Service URLs

# Expected output:

# "Session Service Type: PostgreSQL (Persistent)"### Staging Environment

```- **Service**: `https://my-agentic-rag-aktu2chyfa-uc.a.run.app`

- **Web UI**: `https://my-agentic-rag-aktu2chyfa-uc.a.run.app/dev-ui/`

### Database Access- **Health**: `https://my-agentic-rag-aktu2chyfa-uc.a.run.app/health`



```bash### Production Environment

# Connect via Cloud SQL proxy- **Service**: `https://my-agentic-rag-dyrqvuqk4a-uc.a.run.app`

./cloud-sql-proxy staging-adk:us-central1:adk-sessions-staging-adk- **Web UI**: `https://my-agentic-rag-dyrqvuqk4a-uc.a.run.app/dev-ui/`

- **Health**: `https://my-agentic-rag-dyrqvuqk4a-uc.a.run.app/health`

# In another terminal

psql "host=127.0.0.1 user=adk_app dbname=adk_sessions"## 🔧 Maintenance & Updates



# View sessions### Infrastructure Updates

SELECT * FROM sessions LIMIT 10;

```1. **Modify Terraform Configuration**: Update `.tf` files as needed

2. **Plan Changes**: Run `terraform plan` to review changes

---3. **Apply Updates**: Run `terraform apply` to deploy changes

4. **Verify Deployment**: Check services and functionality

## WhatsApp Bot Deployment

### Service Updates

### Initial Setup

Application updates are deployed automatically through the CI/CD pipeline:

```bash

# Create VM1. **Code Changes**: Modify application code

gcloud compute instances create whatsapp-bot \2. **Commit & Push**: Push changes to `main` branch

  --project=staging-adk \3. **Staging Deploy**: Automatic deployment to staging

  --zone=us-central1-a \4. **Test & Validate**: Verify functionality in staging

  --machine-type=e2-medium \5. **Production Deploy**: Manual trigger and approval

  --image-family=debian-12 \

  --image-project=debian-cloud \### Token Rotation

  --scopes=cloud-platform

To rotate GitHub tokens:

# Setup bot (one-time)

./deployment/vm-setup.sh```bash

```# Update staging secret

echo "NEW_TOKEN" | gcloud secrets versions add github-personal-access-token \

### Update Deployment  --project=staging-adk \

  --data-file=-

```bash

# Deploy code changes# Update production secret

./deployment/deploy-to-vm.shecho "NEW_TOKEN" | gcloud secrets versions add github-personal-access-token \

```  --project=production-adk \

  --data-file=-

**What it does**:

1. Copies `index.js`, `package.json`, `config.json` to VM# Restart services to pick up new token

2. Installs dependencies (`npm install`)gcloud run services update-traffic my-agentic-rag \

3. Restarts systemd service  --to-latest --region=us-central1

```

### Manage Service

### CI/CD Service Account Permissions

```bash

# Status**Important**: The CI/CD service accounts need access to the GitHub token secret for PR checks and integration tests to pass:

gcloud compute ssh whatsapp-bot --project=staging-adk --zone=us-central1-a \

  --command='sudo systemctl status whatsapp-bot'```bash

# Grant production CI service account access to GitHub token

# Logs (live)gcloud secrets add-iam-policy-binding github-personal-access-token \

gcloud compute ssh whatsapp-bot --project=staging-adk --zone=us-central1-a \  --project=production-adk \

  --command='sudo journalctl -u whatsapp-bot -f'  --member="serviceAccount:my-agentic-rag-cb@production-adk.iam.gserviceaccount.com" \

  --role="roles/secretmanager.secretAccessor"

# Logs (last 50)

gcloud compute ssh whatsapp-bot --project=staging-adk --zone=us-central1-a \# Grant staging GitHub Actions service account access to GitHub token  

  --command='sudo journalctl -u whatsapp-bot -n 50'gcloud secrets add-iam-policy-binding github-personal-access-token \

  --project=staging-adk \

# Restart  --member="serviceAccount:github-actions@staging-adk.iam.gserviceaccount.com" \

gcloud compute ssh whatsapp-bot --project=staging-adk --zone=us-central1-a \  --role="roles/secretmanager.secretAccessor"

  --command='sudo systemctl restart whatsapp-bot'```

```

**Required Service Account Roles for CI/CD:**

### Cost Optimization- `secretmanager.secretAccessor`: Access to GitHub tokens

- `cloudbuild.builds.builder`: Execute build steps

```bash- `aiplatform.user`: Access Vertex AI services for testing

# Stop VM when not in use- `logging.logWriter`: Write build logs

gcloud compute instances stop whatsapp-bot --project=staging-adk --zone=us-central1-a

## 📊 Monitoring & Troubleshooting

# Start VM

gcloud compute instances start whatsapp-bot --project=staging-adk --zone=us-central1-a### Health Monitoring

```

```bash

**Note**: Bot auto-starts when VM boots (systemd enabled)# Check service health

curl https://service-url/health

---

# View service logs

## CI/CD Pipelinegcloud run services logs read my-agentic-rag \

  --region=us-central1 --project=PROJECT_ID

### Build Triggers

# Monitor build status

**Staging** (`deploy-my-agentic-rag-staging`):gcloud builds list --project=production-adk --limit=10

- Trigger: Push to `main` branch```

- Target: `staging-adk` project

- Steps: Build → Test → Deploy → Load Test### Common Issues



**Production** (`deploy-my-agentic-rag`):#### Deployment Failures

- Trigger: Manual only- Check build logs: `gcloud builds log BUILD_ID`

- Target: `production-adk` project- Verify IAM permissions

- Steps: Build → Deploy (no auto-test)- Ensure secrets exist and are accessible



### Deployment Flow#### PR Check Failures

- **Common Issue**: CI service account lacks access to GitHub token secret

```- **Solution**: Grant `secretmanager.secretAccessor` role to CI service accounts

Push to main- **Verification**: Check integration tests can access MCP GitHub tools

    ↓

Cloud Build Triggered#### Service Errors

    ↓- Check Cloud Run logs for application errors

Build Docker Image- Verify GitHub token validity and scopes

    ↓- Test Vertex AI Search connectivity

Push to Artifact Registry

    ↓## 📚 Additional Resources

Deploy to Cloud Run (Staging)

    ↓- [Google Cloud Run Documentation](https://cloud.google.com/run/docs)

Run Load Tests (30s)- [Terraform Google Provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs)

    ↓- [Cloud Build Configuration](https://cloud.google.com/build/docs/configuring-builds/create-basic-configuration)

✅ Success / ❌ Rollback- [Secret Manager Best Practices](https://cloud.google.com/secret-manager/docs/best-practices)

```

---

### Manual Production Deploy

## 🗂️ Data Ingestion Pipeline

```bash

gcloud builds triggers run deploy-my-agentic-rag \### Overview

  --project=production-adk \Automated data ingestion into Vertex AI Search for building Retrieval Augmented Generation (RAG) applications. The pipeline orchestrates the complete workflow: loading data, chunking, generating embeddings, and importing into Vertex AI Search datastore.

  --branch=main

```### Setup and Execution



---#### Prerequisites

```bash

## Monitoring & Troubleshooting# Set project ID environment variable

export PROJECT_ID="YOUR_PROJECT_ID"

### Health Checks```



```bash#### Infrastructure Setup

# Staging```bash

curl https://my-agentic-rag-454188184539.us-central1.run.app/health# Deploy development environment with Terraform

make setup-dev-env

# Production  ```

curl https://my-agentic-rag-638797485217.us-central1.run.app/health

#### Pipeline Execution

# Expected response:```bash

# {"status": "healthy", "timestamp": "...", "version": "v1.3"}# Run data ingestion pipeline

```make data-ingestion

```

### Logs

### Pipeline Configuration

```bash- **Parameters**: Automatically configured based on datastore type

# Cloud Run application logs- **Scheduling**: Supports cron-based periodic execution via `--schedule-only` and `--cron-schedule` flags

gcloud run services logs read my-agentic-rag \- **Monitoring**: Vertex AI Pipelines dashboard for progress tracking

  --region=us-central1 \- **Dependencies**: Automatic installation via `make install`

  --project=staging-adk \

  --limit=50### Troubleshooting

If you encounter `"embedding field path: embedding not found in schema"` error after initial ingestion, wait a few minutes for Vertex AI Search to complete indexing.

# Cloud SQL logs

gcloud logging read "resource.type=cloudsql_database" \## 🧪 Load Testing Framework

  --project=staging-adk \

  --limit=20### Overview

Comprehensive load testing using [Locust](https://locust.io/) to measure performance under various load conditions.

# Build logs

gcloud builds log $(gcloud builds list --limit=1 --format="value(id)") \### Test Configuration

  --project=production-adk- **Framework**: Locust v2.31.1

```- **Duration**: 30-second test runs

- **Concurrency**: 10 users with 0.5/second ramp-up rate

### Common Issues- **Scenarios**: Health checks, chat requests, authentication, response time measurements



**Issue**: Cloud Run fails to start  ### Local Testing

**Solution**: Check environment variables and Cloud SQL connection```bash

```bash# Install Locust

gcloud run services describe my-agentic-rag \pip install locust==2.31.1

  --region=us-central1 \

  --project=staging-adk \# Run against staging with web UI

  --format="yaml(spec.template.spec.containers[0].env)"locust -f tests/load_test/load_test.py -H https://your-staging-url

```

# Headless execution

**Issue**: WhatsApp bot not responding  locust -f tests/load_test/load_test.py --headless \

**Solution**: Check systemd service status and logs  -H https://your-staging-url -t 30s -u 10 -r 0.5

```bash```

gcloud compute ssh whatsapp-bot --project=staging-adk --zone=us-central1-a \

  --command='sudo systemctl status whatsapp-bot && sudo journalctl -u whatsapp-bot -n 20'### CI/CD Integration

```Load tests execute automatically after successful staging deployment:

1. **Trigger**: Post-deployment validation

**Issue**: Database connection errors  2. **Results**: CSV/HTML reports stored in GCS

**Solution**: Verify IAM permissions and connection string3. **Metrics**: Request/response times, success rates, throughput analysis

```bash4. **Validation**: Performance regression detection

gcloud projects get-iam-policy staging-adk \

  --flatten="bindings[].members" \### Results Analysis

  --filter="bindings.members:*my-agentic-rag-app*"Test outputs include:

```- **Performance Metrics**: Latency percentiles and throughput measurements

- **Success Rates**: Request success/failure ratios  

---- **Error Analysis**: Detailed failure categorization

- **Trend Analysis**: Performance comparison across deployments

## Service URLs

## 📋 Infrastructure Components

### Staging

- **Cloud Run**: https://my-agentic-rag-454188184539.us-central1.run.app### Terraform Configuration Summary

- **Web UI**: https://my-agentic-rag-454188184539.us-central1.run.app/dev-ui/```

- **Health**: https://my-agentic-rag-454188184539.us-central1.run.app/healthdeployment/terraform/          # Production infrastructure

├── apis.tf                   # Google Cloud API enablement

### Production├── backend.tf                # Terraform state management

- **Cloud Run**: https://my-agentic-rag-638797485217.us-central1.run.app├── build_triggers.tf         # CI/CD pipeline configuration  

- **Web UI**: https://my-agentic-rag-638797485217.us-central1.run.app/dev-ui/├── github.tf                 # GitHub integration setup

- **Health**: https://my-agentic-rag-638797485217.us-central1.run.app/health├── iam.tf                    # Service accounts and permissions

├── service.tf                # Cloud Run service configuration

---├── storage.tf                # GCS buckets and data stores

└── vars/env.tfvars          # Production environment variables

## Cost Summary

deployment/terraform/dev/      # Staging infrastructure  

| Service | Tier | Monthly Cost |├── apis.tf                   # Development API configuration

|---------|------|--------------|├── backend.tf                # Dev state management

| Cloud Run (Staging) | 4CPU/8GB, 1-10 instances | ~$30-50 |├── iam.tf                    # Dev IAM configuration

| Cloud Run (Production) | 4CPU/8GB, 1-10 instances | ~$50-100 |├── service.tf                # Dev Cloud Run setup

| Cloud SQL Dev | db-f1-micro | ~$7 |├── storage.tf                # Dev storage configuration

| Cloud SQL Staging | db-f1-micro | ~$7 |└── vars/env.tfvars          # Staging environment variables

| Cloud SQL Production | db-g1-small + HA | ~$50 |```

| Compute Engine (whatsapp-bot) | e2-medium | ~$25 (if 24/7) |

| Storage (GCS) | Various buckets | ~$5-10 |### Service Dependencies

| **Total** | | **~$174-249/month** |- **Cloud Run**: Serverless ADK agent hosting with automatic scaling

- **Artifact Registry**: Multi-region Docker image storage and management

**Optimization tips**:- **Secret Manager**: Encrypted storage for GitHub PAT and FAL API keys

- Stop WhatsApp VM when not in use (save ~$25/month)- **Cloud Build**: GitOps-based CI/CD with manual production approval

- Use Cloud Scheduler to auto-stop/start services- **Vertex AI Search**: RAG backend with embedding generation and search

- Enable committed use discounts (37% off compute)- **Cloud Storage**: Session state, artifacts, and test results persistence

- **Cloud Logging**: Centralized logging with structured log analysis

---- **IAM**: Principle of least privilege with service account isolation



## Files & Structure---



```*This deployment guide provides comprehensive infrastructure management for production-ready WhatsApp ADK bot deployment with automated testing, monitoring, and data pipeline integration.*
deployment/
├── README.md                  # This file
├── deploy-to-vm.sh            # WhatsApp bot deployment script
├── vm-setup.sh                # Initial VM setup
├── terraform/                 # Infrastructure as Code
│   ├── cloudsql.tf           # Cloud SQL (staging + prod)
│   ├── iam.tf                # IAM roles & permissions
│   ├── service.tf            # Cloud Run services
│   ├── storage.tf            # GCS buckets
│   ├── build_triggers.tf     # CI/CD triggers
│   └── vars/env.tfvars       # Environment variables
└── terraform/dev/
    ├── cloudsql.tf           # Cloud SQL (dev)
    ├── service.tf            # Cloud Run (dev)
    └── vars/env.tfvars       # Dev variables
```

---

## Next Steps

1. **First-time setup**:
   ```bash
   cd deployment/terraform/dev
   terraform apply -var-file=vars/env.tfvars
   ```

2. **Deploy WhatsApp bot**:
   ```bash
   ./deployment/deploy-to-vm.sh
   ```

3. **Push code to staging**:
   ```bash
   git push origin main
   ```

4. **Monitor deployment**:
   ```bash
   gcloud builds list --limit=1 --project=production-adk
   ```

5. **Verify services**:
   ```bash
   curl https://my-agentic-rag-454188184539.us-central1.run.app/health
   ```
