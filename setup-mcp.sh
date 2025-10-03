#!/bin/bash

# Setup script for GitHub MCP server integration
# This script ensures Docker is available and pulls the GitHub MCP server image

set -e

echo "🚀 Setting up GitHub MCP Server for ADK Agent..."

# Check if Docker is installed and running
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "   Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "❌ Docker is not running. Please start Docker daemon."
    exit 1
fi

# Pull the GitHub MCP server image
echo "📦 Pulling GitHub MCP server Docker image..."
docker pull ghcr.io/github/github-mcp-server

# Set up environment variable
if [ -z "$GITHUB_PAT" ]; then
    echo "⚠️  GITHUB_PAT environment variable is not set."
    echo "   This is required for the GitHub MCP server to function."
    echo "   You can set it by running:"
    echo "   export GITHUB_PAT='your_github_personal_access_token_here'"
    echo ""
    echo "   Or add it to your ~/.bashrc or ~/.zshrc file for persistence."
else
    echo "✅ GITHUB_PAT environment variable is set."
fi

# Test the MCP server
echo "🧪 Testing GitHub MCP server..."
if docker run --rm -e GITHUB_PERSONAL_ACCESS_TOKEN="$GITHUB_PAT" ghcr.io/github/github-mcp-server --version &> /dev/null; then
    echo "✅ GitHub MCP server is working correctly!"
else
    echo "⚠️  Could not verify GitHub MCP server functionality."
    echo "   This might be due to missing GITHUB_PAT or network issues."
fi

echo ""
echo "🎉 Setup complete! Your ADK agent is now configured to use GitHub MCP server."
echo ""
echo "To test your agent with GitHub tools:"
echo "1. Make sure GITHUB_PAT is set: export GITHUB_PAT='your_token_here'"
echo "2. Run: make playground"
echo "3. Ask your agent to search GitHub repositories or get repository information"
echo ""
echo "Example queries you can try:"
echo "  - 'Search for repositories related to machine learning'"
echo "  - 'Get information about the microsoft/vscode repository'"
echo "  - 'Show me the latest issues in my repository'"