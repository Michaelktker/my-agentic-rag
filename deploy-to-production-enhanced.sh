# Enhanced production deployment script with approval workflow
#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Load environment-specific configurations
if [ -f "config/production.env" ]; then
    source config/production.env
    echo -e "${GREEN}✅ Loaded production environment configuration${NC}"
else
    echo -e "${YELLOW}⚠️ Production environment file not found, using defaults${NC}"
fi

echo -e "${BLUE}🚀 Starting automated production deployment with approval workflow...${NC}"

# Function to print status
print_status() {
    echo -e "${BLUE}📊 $1${NC}"
}

# Function to print success
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

# Function to print error
print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if we're in the right directory
if [ ! -f ".cloudbuild/deploy-to-prod.yaml" ]; then
    print_error "deploy-to-prod.yaml not found. Please run this script from the my-agentic-rag directory."
    exit 1
fi

# Check if production project is accessible
if ! gcloud projects describe $PROD_PROJECT_ID >/dev/null 2>&1; then
    print_error "Cannot access $PROD_PROJECT_ID project. Please check your permissions."
    exit 1
fi

print_success "Production project access confirmed"

# Check if staging deployment is successful and recent
print_status "Validating staging deployment..."

STAGING_URL="https://my-agentic-rag-454188184539.us-central1.run.app"
if curl -f -s --max-time 30 "$STAGING_URL/docs" > /dev/null; then
    print_success "Staging environment is healthy"
else
    print_error "Staging environment health check failed. Please ensure staging is working before deploying to production."
    exit 1
fi

# Get staging image details
print_status "Retrieving staging image information..."
STAGING_IMAGE=$(gcloud run services describe my-agentic-rag \
    --region us-central1 \
    --project staging-adk \
    --format="value(spec.template.spec.template.spec.containers[0].image)" 2>/dev/null || echo "unknown")

print_success "Staging image: $STAGING_IMAGE"

# Approval workflow (interactive)
if [ "$1" != "--auto" ]; then
    echo
    echo -e "${YELLOW}🔒 PRODUCTION DEPLOYMENT APPROVAL REQUIRED${NC}"
    echo "=============================================="
    echo "Environment: PRODUCTION"
    echo "Project: $PROD_PROJECT_ID" 
    echo "Region: $REGION"
    echo "Staging Image: $STAGING_IMAGE"
    echo "Staging URL: $STAGING_URL"
    echo "Production URL: https://my-agentic-rag-638797485217.us-central1.run.app"
    echo
    echo -e "${YELLOW}This will deploy to PRODUCTION environment.${NC}"
    echo -e "${YELLOW}Please verify that staging tests have passed and the deployment is approved.${NC}"
    echo
    
    read -p "Do you want to proceed with production deployment? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        print_warning "Production deployment cancelled by user."
        exit 0
    fi
    
    print_success "Production deployment approved!"
fi

# Pre-deployment checks
print_status "Running pre-deployment checks..."

# Check if required substitution variables are set
required_vars=("PROD_PROJECT_ID" "REGION" "DATA_STORE_ID" "PIPELINE_SA_EMAIL")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        print_error "Required variable $var is not set"
        exit 1
    fi
done

print_success "Pre-deployment checks passed"

# Submit deployment to Cloud Build
print_status "Submitting production deployment to Cloud Build..."

BUILD_ID=$(gcloud builds submit \
    --config=.cloudbuild/deploy-to-prod.yaml \
    --project=$PROD_PROJECT_ID \
    --region=$REGION \
    --format="value(name)" \
    --async \
    --substitutions="_PROD_PROJECT_ID=$PROD_PROJECT_ID,_REGION=$REGION,_DATA_STORE_ID_PROD=$DATA_STORE_ID,_PIPELINE_SA_EMAIL_PROD=$PIPELINE_SA_EMAIL,_PIPELINE_ROOT_PROD=$PIPELINE_ROOT")

if [ $? -eq 0 ]; then
    print_success "Production deployment submitted successfully!"
    echo "Build ID: $BUILD_ID"
    echo
    print_status "Monitor progress at:"
    echo "🔗 https://console.cloud.google.com/cloud-build/builds;region=$REGION?project=$PROD_PROJECT_ID"
    echo
    
    # Wait for deployment completion (optional)
    if [ "$2" = "--wait" ]; then
        print_status "Waiting for deployment completion..."
        
        if gcloud builds wait $BUILD_ID --project=$PROD_PROJECT_ID --region=$REGION; then
            print_success "🎉 Production deployment completed successfully!"
            echo
            echo "🌐 Production URL: https://my-agentic-rag-638797485217.us-central1.run.app"
            echo "📊 Console: https://console.cloud.google.com/run/detail/$REGION/my-agentic-rag?project=$PROD_PROJECT_ID"
            echo "📈 Monitoring: https://console.cloud.google.com/monitoring/dashboards?project=$PROD_PROJECT_ID"
            
            # Quick health check
            print_status "Performing final health check..."
            sleep 30
            if curl -f -s --max-time 30 "https://my-agentic-rag-638797485217.us-central1.run.app/docs" > /dev/null; then
                print_success "Production health check passed!"
            else
                print_warning "Production health check failed - service may still be starting"
            fi
        else
            print_error "Production deployment failed"
            exit 1
        fi
    else
        print_status "Deployment submitted. Use --wait flag to wait for completion."
    fi
else
    print_error "Failed to submit production deployment"
    exit 1
fi

echo
print_success "Production deployment script completed!"