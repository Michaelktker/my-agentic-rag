#!/bin/bash
# Production Deployment Script for my-agentic-rag

set -e

echo "🚀 Starting production deployment for my-agentic-rag..."

# Check if we're in the right directory
if [ ! -f ".cloudbuild/deploy-to-prod-simple.yaml" ]; then
    echo "❌ Error: deploy-to-prod-simple.yaml not found. Please run this script from the my-agentic-rag directory."
    exit 1
fi

# Check if production project is accessible
if ! gcloud projects describe production-adk >/dev/null 2>&1; then
    echo "❌ Error: Cannot access production-adk project. Please check your permissions."
    exit 1
fi

echo "✅ Production project access confirmed"

# Deploy to production (simple version without data pipeline)
echo "📦 Submitting simple deployment to production..."
gcloud builds submit \
    --config=.cloudbuild/deploy-to-prod-simple.yaml \
    --project=production-adk \
    --region=us-central1 \
    --no-source

echo "🎉 Production deployment initiated!"
echo "🔗 Monitor progress: https://console.cloud.google.com/cloud-build/builds;region=us-central1?project=production-adk"