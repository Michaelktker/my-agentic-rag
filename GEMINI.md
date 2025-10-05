# My Agentic RAG Development Guide

This document provides context and guidance for AI-assisted development of the Agentic RAG system. It serves as a comprehensive reference for understanding the project's architecture, deployment workflow, and lessons learned during development.

## 📋 Project Overview

### Purpose
A production-ready Retrieval-Augmented Generation (RAG) agent that combines:
- Document search and retrieval using Vertex AI Search
- GitHub repository integration via Model Context Protocol (MCP) tools
- Secure, scalable deployment on Google Cloud Platform

### Current Status
- ✅ **Production Ready**: Deployed to both staging and production environments
- ✅ **CI/CD Pipeline**: Automated deployments with manual production approval
- ✅ **Security**: GitHub tokens managed via Google Secret Manager
- ✅ **Monitoring**: Cloud Logging, Tracing, and observability enabled

## 🏗️ Architecture Deep Dive

### Core Components

1. **ADK Agent** (`app/agent.py`)
   - Built using Google's Agent Development Kit (ADK)
   - Combines RAG retrieval with GitHub MCP tools
   - Uses streaming responses for real-time interaction
   - Mandatory GitHub integration (no fallback logic)

2. **Retrieval System** (`app/retrievers.py`) 
   - Vertex AI Search integration for document indexing
   - Supports multiple data stores (staging/production)
   - Configurable retrieval parameters and scoring

3. **GitHub Integration** (MCP Tools)
   - Repository search and file access
   - Issue and pull request management
   - Code analysis and understanding
   - Secure token authentication via Secret Manager

4. **FastAPI Backend** (`app/server.py`)
   - RESTful API endpoints for agent interaction
   - Health checks and service monitoring
   - CORS configuration for web UI integration

### Infrastructure

- **Staging**: `staging-adk` project with auto-deployment
- **Production**: `production-adk` project with manual approval
- **Secret Management**: GitHub tokens stored in Google Secret Manager
- **Container Registry**: Google Artifact Registry for Docker images
- **CI/CD**: Google Cloud Build triggers for automated deployments

## 🔄 Development Workflow

### Local Development Process

1. **Environment Setup**
   ```bash
   make install     # Install dependencies with uv
   make playground  # Launch ADK web UI at localhost:8080
   ```

2. **Code Development**
   - Modify agent logic in `app/agent.py`
   - Update retrievers in `app/retrievers.py`
   - Test changes immediately via web playground

3. **Quality Assurance**
   ```bash
   make test        # Run unit and integration tests
   make lint        # Code quality checks (ruff, mypy, codespell)
   ```

### Deployment Pipeline

1. **Staging Deployment** (Automatic)
   - Push to `main` branch triggers Cloud Build
   - Automatic deployment to staging environment
   - Service available at staging URL for testing

2. **Production Deployment** (Manual Approval)
   - Trigger production build manually via Cloud Console
   - Requires explicit approval for deployment
   - Production service becomes available after approval

### Key Lessons Learned

#### GitHub Token Management
- **Issue**: Initial token had trailing newline causing HTTP header errors
- **Solution**: Always strip whitespace when reading from Secret Manager
- **Implementation**: `token = token.strip()` in `get_github_token()`

#### Fallback Logic Removal  
- **Decision**: Remove all fallback logic for GitHub tools
- **Rationale**: GitHub integration is core functionality, not optional
- **Implementation**: Raise `RuntimeError` if token unavailable

#### Secret Manager Integration
- **Setup**: Tokens must exist in both staging and production projects
- **Permissions**: Service accounts need `secretmanager.secretAccessor` role
- **Security**: Never commit tokens to repository, always use Secret Manager

## 🛠️ Technical Implementation

### Agent Configuration

```python
# app/agent.py - Key patterns

class MyAgenticRAGAgent:
    def __init__(self):
        # Always require GitHub token - no fallbacks
        github_token = get_github_token()
        if not github_token:
            raise RuntimeError("GitHub token is required")
        
        # Initialize MCP toolset with GitHub integration
        self.toolset = MCPToolset(github_token.strip())
        
        # Configure RAG retriever
        self.retriever = get_retriever()
```

### Secret Manager Integration

```python
def get_github_token() -> str:
    """Retrieve GitHub token from Secret Manager"""
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/github-personal-access-token/versions/latest"
        response = client.access_secret_version(request={"name": name})
        token = response.payload.data.decode("UTF-8").strip()  # Critical: strip whitespace
        return token
    except Exception as e:
        logger.error(f"Failed to retrieve GitHub token: {e}")
        raise RuntimeError("GitHub token unavailable")
```

### Cloud Build Configuration

```yaml
# .cloudbuild/cloudbuild-staging.yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/my-agentic-rag', '.']
  - name: 'gcr.io/cloud-builders/docker'  
    args: ['push', 'gcr.io/$PROJECT_ID/my-agentic-rag']
  - name: 'gcr.io/cloud-builders/gcloud'
    args: ['run', 'deploy', 'my-agentic-rag', '--image', 'gcr.io/$PROJECT_ID/my-agentic-rag', '--region', 'us-central1']
```

## 🔍 Debugging & Troubleshooting

### Common Issues and Solutions

#### 1. Agent Not Responding
**Symptoms**: No response from agent in web UI
**Causes**: 
- GitHub token errors (trailing whitespace)
- Secret Manager permissions
- Service startup failures

**Debug Steps**:
```bash
# Check service logs
gcloud run services logs read my-agentic-rag --region=us-central1

# Verify token exists
gcloud secrets list --filter="name:github-personal-access-token"

# Test service health
curl https://service-url/health
```

#### 2. Deployment Failures
**Symptoms**: Cloud Build fails or times out
**Causes**:
- Docker build errors
- Missing permissions
- Resource constraints

**Debug Steps**:
```bash  
# View build logs
gcloud builds log BUILD_ID

# Check service account permissions
gcloud projects get-iam-policy PROJECT_ID
```

#### 3. GitHub Integration Errors
**Symptoms**: GitHub tools not working, authentication errors
**Causes**:
- Invalid or expired GitHub token
- Insufficient token scopes
- Network connectivity issues

**Debug Steps**:
- Verify token scopes include `repo`, `read:org`, `read:user`
- Test token manually via GitHub API
- Check Secret Manager access patterns

## 📊 Performance & Monitoring

### Key Metrics to Monitor
- **Response Time**: Agent query processing speed
- **Error Rate**: Failed requests and exceptions  
- **Token Usage**: LLM and GitHub API consumption
- **Memory Usage**: Container resource utilization

### Observability Tools
- **Cloud Logging**: Application logs and error tracking
- **Cloud Trace**: Request tracing and latency analysis
- **Cloud Monitoring**: Service health and performance metrics
- **BigQuery**: Long-term analytics and usage patterns

## 🚀 Future Enhancements

### Potential Improvements
1. **Enhanced RAG**: Support for more document types and sources
2. **Advanced GitHub Features**: PR review automation, code generation
3. **Multi-Modal Support**: Image and diagram understanding
4. **Performance Optimization**: Caching, response streaming improvements
5. **Security Enhancements**: Fine-grained access controls, audit logging

### Development Considerations
- Maintain backward compatibility with existing APIs
- Preserve security-first approach to token management
- Continue automated testing and quality assurance
- Monitor performance impact of new features

## 📚 Additional Resources

### Documentation Links
- [Google ADK Documentation](https://cloud.google.com/agent-development-kit/docs)
- [Vertex AI Search Guide](https://cloud.google.com/vertex-ai/docs/vector-search/overview)
- [Model Context Protocol](https://github.com/modelcontextprotocol/mcp)
- [Google Cloud Build](https://cloud.google.com/build/docs)

### Internal References
- [`deployment/README.md`](deployment/README.md) - Infrastructure setup
- [`data_ingestion/README.md`](data_ingestion/README.md) - Document ingestion
- [`tests/`](tests/) - Test suites and examples

---

*This guide is maintained to reflect the current state of the system and should be updated as the project evolves.*

**Last Updated**: October 5, 2025