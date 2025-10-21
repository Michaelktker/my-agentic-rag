#!/bin/bash

# Development Environment Setup Script
# This script installs Terraform and Google Cloud CLI for the development environment

set -e

echo "🚀 Setting up development environment..."

# Install Terraform
echo "📦 Installing Terraform..."
if ! command -v terraform &> /dev/null; then
    echo "Adding HashiCorp GPG key..."
    wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
    
    echo "Adding HashiCorp repository..."
    echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
    
    echo "Installing Terraform..."
    sudo apt update && sudo apt install -y terraform
    
    echo "✅ Terraform $(terraform version | head -n1) installed successfully"
else
    echo "✅ Terraform is already installed: $(terraform version | head -n1)"
fi

# Install Google Cloud CLI
echo "📦 Installing Google Cloud CLI..."
if ! command -v gcloud &> /dev/null; then
    echo "Downloading Google Cloud CLI..."
    curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-459.0.0-linux-x86_64.tar.gz
    
    echo "Extracting Google Cloud CLI..."
    tar -xf google-cloud-cli-459.0.0-linux-x86_64.tar.gz
    
    echo "Installing Google Cloud CLI..."
    ./google-cloud-sdk/install.sh --quiet
    
    echo "Setting up PATH..."
    export PATH=$PATH:$(pwd)/google-cloud-sdk/bin
    source ./google-cloud-sdk/path.bash.inc
    source ./google-cloud-sdk/completion.bash.inc
    
    echo "✅ Google Cloud CLI $(gcloud version | head -n1) installed successfully"
else
    echo "✅ Google Cloud CLI is already installed: $(gcloud version | head -n1)"
fi

echo ""
echo "🎉 Development environment setup complete!"
echo ""
echo "Next steps:"
echo "1. Authenticate with Google Cloud: gcloud auth login"
echo "2. Set your project: gcloud config set project YOUR_PROJECT_ID"
echo "3. Set up Application Default Credentials: gcloud auth application-default login"
echo ""
echo "Available projects can be listed with: gcloud projects list"