#!/bin/bash

echo "🔐 Adding GitHub Repository Secrets for my-agentic-rag..."
echo "=================================================="

# Define all secrets as key=value pairs
declare -A secrets=(
    ["STAGING_PROJECT_ID"]="staging-adk"
    ["PROD_PROJECT_ID"]="production-adk"
    ["CICD_RUNNER_PROJECT_ID"]="production-adk"
    ["REGION"]="us-central1"
    ["DATA_STORE_REGION"]="us"
    ["REPOSITORY_NAME"]="my-agentic-rag"
    ["REPOSITORY_OWNER"]="Michaelktker"
    ["HOST_CONNECTION_NAME"]="git-my-agentic-rag"
    ["GITHUB_APP_INSTALLATION_ID"]="54681073"
    ["GITHUB_PAT_SECRET_ID"]="git-my-agentic-rag-github-oauthtoken-ddff64"
    ["DATA_STORE_ID_STAGING"]="my-agentic-rag-datastore-staging"
    ["DATA_STORE_ID_PROD"]="my-agentic-rag-datastore"
    ["ARTIFACT_REGISTRY_REPO_NAME"]="my-agentic-rag-docker-repo"
    ["CONTAINER_NAME"]="my-agentic-rag"
    ["BUCKET_NAME_LOAD_TEST_RESULTS"]="staging-adk-my-agentic-rag-load-test-results"
    ["PIPELINE_GCS_ROOT_STAGING"]="gs://staging-adk-my-agentic-rag-rag"
    ["PIPELINE_GCS_ROOT_PROD"]="gs://production-adk-my-agentic-rag-rag"
    ["PIPELINE_SA_EMAIL_STAGING"]="my-agentic-rag-rag@staging-adk.iam.gserviceaccount.com"
    ["PIPELINE_SA_EMAIL_PROD"]="my-agentic-rag-rag@production-adk.iam.gserviceaccount.com"
    ["PIPELINE_NAME"]="data-ingestion-pipeline"
    ["PIPELINE_CRON_SCHEDULE"]=""
    ["DISABLE_CACHING"]="TRUE"
    ["STAGING_URL"]="https://my-agentic-rag-454188184539.us-central1.run.app"
    ["PROD_URL"]="https://my-agentic-rag-638797485217.us-central1.run.app"
    ["CREATE_CB_CONNECTION"]="true"
    ["CREATE_REPOSITORY"]="false"
)

# Counter for progress
total=${#secrets[@]}
current=0

# Add each secret
for key in "${!secrets[@]}"; do
    current=$((current + 1))
    echo "[$current/$total] Adding secret: $key"
    
    if gh secret set "$key" --body "${secrets[$key]}" --repo Michaelktker/my-agentic-rag; then
        echo "  ✅ Success: $key"
    else
        echo "  ❌ Failed: $key"
    fi
    
    # Small delay to avoid rate limiting
    sleep 0.5
done

echo ""
echo "🎉 Script completed!"
echo "📋 Added $total secrets to GitHub repository"
echo "🔗 View secrets at: https://github.com/Michaelktker/my-agentic-rag/settings/secrets/actions"