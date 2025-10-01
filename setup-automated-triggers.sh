#!/bin/bash
# Setup script for automated production triggers with GitHub webhooks

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
STAGING_PROJECT_ID="staging-adk"
PROD_PROJECT_ID="production-adk"
REGION="us-central1"
REPO_OWNER="Michaelktker"
REPO_NAME="my-agentic-rag"

print_header() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}🚀 Setting up Automated Production Triggers${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo
}

print_step() {
    echo -e "${BLUE}📋 Step $1: $2${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_prerequisites() {
    print_step "1" "Checking prerequisites"
    
    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check if gh CLI is installed
    if ! command -v gh &> /dev/null; then
        print_warning "GitHub CLI (gh) is not installed. Some steps will need to be done manually."
        GH_AVAILABLE=false
    else
        GH_AVAILABLE=true
    fi
    
    # Check if user is authenticated
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1 > /dev/null; then
        print_error "Please authenticate with gcloud: gcloud auth login"
        exit 1
    fi
    
    print_success "Prerequisites check completed"
}

setup_workload_identity_federation() {
    print_step "2" "Setting up Workload Identity Federation"
    
    for PROJECT in $STAGING_PROJECT_ID $PROD_PROJECT_ID; do
        echo -e "${BLUE}Setting up WIF for project: $PROJECT${NC}"
        
        # Create workload identity pool (if not exists)
        if ! gcloud iam workload-identity-pools describe github-pool \
            --project=$PROJECT \
            --location=global >/dev/null 2>&1; then
            
            echo "Creating workload identity pool..."
            gcloud iam workload-identity-pools create github-pool \
                --project=$PROJECT \
                --location=global \
                --display-name="GitHub Actions Pool"
        fi
        
        # Create workload identity provider (if not exists)
        if ! gcloud iam workload-identity-pools providers describe github-provider \
            --project=$PROJECT \
            --location=global \
            --workload-identity-pool=github-pool >/dev/null 2>&1; then
            
            echo "Creating workload identity provider..."
            gcloud iam workload-identity-pools providers create-oidc github-provider \
                --project=$PROJECT \
                --location=global \
                --workload-identity-pool=github-pool \
                --display-name="GitHub Actions Provider" \
                --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
                --issuer-uri="https://token.actions.githubusercontent.com"
        fi
        
        # Create service account for GitHub Actions (if not exists)
        SA_EMAIL="github-actions@$PROJECT.iam.gserviceaccount.com"
        if ! gcloud iam service-accounts describe $SA_EMAIL --project=$PROJECT >/dev/null 2>&1; then
            echo "Creating GitHub Actions service account..."
            gcloud iam service-accounts create github-actions \
                --project=$PROJECT \
                --display-name="GitHub Actions Service Account"
        fi
        
        # Grant necessary permissions
        echo "Granting permissions to service account..."
        gcloud projects add-iam-policy-binding $PROJECT \
            --member="serviceAccount:$SA_EMAIL" \
            --role="roles/cloudbuild.builds.editor" \
            --quiet
        
        gcloud projects add-iam-policy-binding $PROJECT \
            --member="serviceAccount:$SA_EMAIL" \
            --role="roles/run.admin" \
            --quiet
        
        gcloud projects add-iam-policy-binding $PROJECT \
            --member="serviceAccount:$SA_EMAIL" \
            --role="roles/storage.admin" \
            --quiet
        
        # Allow GitHub Actions to impersonate the service account
        gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
            --project=$PROJECT \
            --role="roles/iam.workloadIdentityUser" \
            --member="principalSet://iam.googleapis.com/projects/$(gcloud projects describe $PROJECT --format='value(projectNumber)')/locations/global/workloadIdentityPools/github-pool/attribute.repository/$REPO_OWNER/$REPO_NAME"
        
        # Get WIF provider name for GitHub secrets
        WIF_PROVIDER=$(gcloud iam workload-identity-pools providers describe github-provider \
            --project=$PROJECT \
            --location=global \
            --workload-identity-pool=github-pool \
            --format="value(name)")
        
        echo "WIF Provider for $PROJECT: $WIF_PROVIDER"
        echo "Service Account: $SA_EMAIL"
        echo
    done
    
    print_success "Workload Identity Federation setup completed"
}

setup_cloud_build_triggers() {
    print_step "3" "Setting up Cloud Build triggers"
    
    # Enable necessary APIs
    for PROJECT in $STAGING_PROJECT_ID $PROD_PROJECT_ID; do
        echo "Enabling APIs for $PROJECT..."
        gcloud services enable cloudbuild.googleapis.com --project=$PROJECT
        gcloud services enable run.googleapis.com --project=$PROJECT
        gcloud services enable artifactregistry.googleapis.com --project=$PROJECT
    done
    
    # Note: Actual trigger creation should be done via Terraform or manually
    # as it requires GitHub connection setup
    print_warning "Cloud Build triggers need to be created manually or via Terraform"
    print_warning "Use the configuration in cloud-build-triggers.yaml as reference"
    
    print_success "Cloud Build API setup completed"
}

setup_github_secrets() {
    print_step "4" "Setting up GitHub secrets"
    
    if [ "$GH_AVAILABLE" = true ]; then
        echo "Setting up GitHub repository secrets..."
        
        # Get WIF providers
        STAGING_WIF=$(gcloud iam workload-identity-pools providers describe github-provider \
            --project=$STAGING_PROJECT_ID \
            --location=global \
            --workload-identity-pool=github-pool \
            --format="value(name)")
        
        PROD_WIF=$(gcloud iam workload-identity-pools providers describe github-provider \
            --project=$PROD_PROJECT_ID \
            --location=global \
            --workload-identity-pool=github-pool \
            --format="value(name)")
        
        # Set GitHub secrets
        gh secret set WIF_PROVIDER --body="$STAGING_WIF"
        gh secret set WIF_SERVICE_ACCOUNT --body="github-actions@$STAGING_PROJECT_ID.iam.gserviceaccount.com"
        gh secret set WIF_PROVIDER_PROD --body="$PROD_WIF"
        gh secret set WIF_SERVICE_ACCOUNT_PROD --body="github-actions@$PROD_PROJECT_ID.iam.gserviceaccount.com"
        
        print_success "GitHub secrets configured"
    else
        print_warning "GitHub CLI not available. Please set up secrets manually:"
        echo
        echo "Required GitHub Secrets:"
        echo "========================"
        
        STAGING_WIF=$(gcloud iam workload-identity-pools providers describe github-provider \
            --project=$STAGING_PROJECT_ID \
            --location=global \
            --workload-identity-pool=github-pool \
            --format="value(name)")
        
        PROD_WIF=$(gcloud iam workload-identity-pools providers describe github-provider \
            --project=$PROD_PROJECT_ID \
            --location=global \
            --workload-identity-pool=github-pool \
            --format="value(name)")
        
        echo "WIF_PROVIDER: $STAGING_WIF"
        echo "WIF_SERVICE_ACCOUNT: github-actions@$STAGING_PROJECT_ID.iam.gserviceaccount.com"
        echo "WIF_PROVIDER_PROD: $PROD_WIF"
        echo "WIF_SERVICE_ACCOUNT_PROD: github-actions@$PROD_PROJECT_ID.iam.gserviceaccount.com"
        echo
    fi
}

setup_github_environments() {
    print_step "5" "Setting up GitHub environments"
    
    if [ "$GH_AVAILABLE" = true ]; then
        echo "Creating GitHub environments..."
        
        # Note: GitHub CLI doesn't support environment creation yet
        # This would need to be done via GitHub API or manually
        print_warning "GitHub environments need to be created manually"
    fi
    
    print_warning "Please create the following GitHub environments manually:"
    echo
    echo "1. staging (no protection rules)"
    echo "2. production-approval (with required reviewers)"
    echo "3. production (with required reviewers)"
    echo
    echo "See GITHUB-WEBHOOKS-SETUP.md for detailed instructions"
}

test_setup() {
    print_step "6" "Testing the setup"
    
    echo "Testing staging deployment capability..."
    if gcloud builds submit --config=.cloudbuild/staging.yaml \
        --project=$STAGING_PROJECT_ID \
        --region=$REGION \
        --dry-run >/dev/null 2>&1; then
        print_success "Staging deployment configuration is valid"
    else
        print_warning "Staging deployment configuration needs review"
    fi
    
    echo "Testing production deployment capability..."
    if gcloud builds submit --config=.cloudbuild/deploy-to-prod.yaml \
        --project=$PROD_PROJECT_ID \
        --region=$REGION \
        --dry-run >/dev/null 2>&1; then
        print_success "Production deployment configuration is valid"
    else
        print_warning "Production deployment configuration needs review"
    fi
}

print_summary() {
    echo
    echo -e "${GREEN}🎉 Setup completed!${NC}"
    echo
    echo "Next steps:"
    echo "1. Create GitHub environments (see GITHUB-WEBHOOKS-SETUP.md)"
    echo "2. Set up Cloud Build GitHub connections"
    echo "3. Create Cloud Build triggers using cloud-build-triggers.yaml"
    echo "4. Test the workflows with a small change"
    echo
    echo "Documentation:"
    echo "- GITHUB-WEBHOOKS-SETUP.md - Complete setup guide"
    echo "- deploy-to-production-enhanced.sh - Enhanced deployment script"
    echo "- config/staging.env - Staging environment variables"
    echo "- config/production.env - Production environment variables"
    echo
    echo -e "${BLUE}Happy deploying! 🚀${NC}"
}

# Main execution
main() {
    print_header
    check_prerequisites
    setup_workload_identity_federation
    setup_cloud_build_triggers
    setup_github_secrets
    setup_github_environments
    test_setup
    print_summary
}

# Run the setup if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi