# Security Guide

## 🔐 Managing Secrets

This repository does NOT contain any hardcoded secrets. All sensitive information must be managed securely.

### Required Secrets

1. **FAL API Key** - For fal.ai image/video generation
2. **GitHub Token** - For repository operations via terminal
3. **GCP Service Account Keys** - Managed via Google Cloud IAM

### How to Set Secrets

#### Option 1: Environment Variables (Local Development)

```bash
# Set in your shell
export FAL_KEY="your-fal-api-key-here"
export GITHUB_TOKEN="your-github-token-here"

# Then run commands
make local-backend
make playground
```

#### Option 2: Google Secret Manager (Production)

All production secrets are stored in Google Secret Manager:

```bash
# Store FAL API key
gcloud secrets create fal-api-key \
  --data-file=- <<< "your-fal-api-key" \
  --project=staging-adk

# Store GitHub token
gcloud secrets create github-pat \
  --data-file=- <<< "your-github-token" \
  --project=staging-adk
```

#### Option 3: Local .env File (Development)

Create a `.env` file in the project root (this is gitignored):

```bash
# .env (DO NOT COMMIT THIS FILE)
FAL_KEY=your-fal-api-key-here
GITHUB_TOKEN=your-github-token-here
```

Then source it:

```bash
source .env
```

### Terraform Variables

When deploying infrastructure, pass secrets via command line:

```bash
cd deployment/terraform
terraform apply \
  -var-file=vars/env.tfvars \
  -var="fal_api_key=$FAL_KEY"
```

### VM Deployment

When deploying the bot to a VM, secrets should be configured after deployment:

```bash
# SSH into VM
gcloud compute ssh whatsapp-bot --project=staging-adk --zone=us-central1-a

# Set environment variables in service file
sudo mkdir -p /etc/systemd/system/whatsapp-bot.service.d
sudo tee /etc/systemd/system/whatsapp-bot.service.d/secrets.conf > /dev/null <<EOF
[Service]
Environment="FAL_KEY=your-fal-api-key-here"
Environment="GITHUB_TOKEN=your-github-token-here"
EOF

# Secure the file
sudo chmod 600 /etc/systemd/system/whatsapp-bot.service.d/secrets.conf

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart whatsapp-bot
```

## 🚨 What NOT to Do

- ❌ Never commit API keys, tokens, or passwords to Git
- ❌ Never include secrets in `.env` files that aren't gitignored
- ❌ Never share your `config/*.env` files publicly
- ❌ Never hardcode secrets in code or configuration files
- ❌ Never include secrets in Terraform `.tfvars` files tracked by Git

## ✅ What TO Do

- ✅ Use environment variables for local development
- ✅ Use Google Secret Manager for production
- ✅ Use `.env.example` files to document required variables (without actual values)
- ✅ Rotate secrets regularly
- ✅ Use different secrets for staging and production
- ✅ Keep secrets out of logs and error messages

## 📋 Creating API Keys

### FAL API Key

1. Go to https://fal.ai/dashboard
2. Click "API Keys"
3. Generate new key
4. Store securely (you won't be able to see it again)

### GitHub Token

1. Go to https://github.com/settings/tokens?type=beta
2. Click "Generate new token" (Fine-grained)
3. Set permissions:
   - Repository access: Select repositories
   - Permissions: Contents (Read/Write), Pull requests (Read/Write), Issues (Read/Write)
4. Generate and copy token
5. Store securely

## 🔍 Checking for Exposed Secrets

Before making the repository public, run:

```bash
# Check for common secret patterns
grep -r "api[_-]key\|secret\|password\|token" --exclude-dir={node_modules,.git,google-cloud-sdk} .

# Check for specific patterns
grep -r "[0-9a-f]\{8\}-[0-9a-f]\{4\}-[0-9a-f]\{4\}" --exclude-dir={node_modules,.git} .
```

## 📞 Reporting Security Issues

If you find a security vulnerability, please DO NOT open a public issue. Instead:

1. Email: michaelktker@gmail.com
2. Include detailed description
3. Allow time for a fix before public disclosure

## 🔄 Rotating Compromised Secrets

If a secret is accidentally exposed:

1. **Immediately revoke** the compromised key
2. **Generate new** credentials
3. **Update** all deployments with new credentials
4. **Remove** from Git history if committed (use `git filter-branch` or BFG Repo-Cleaner)
5. **Audit** for any unauthorized access
