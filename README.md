# My Agentic RAG System

A production-ready Retrieval-Augmented Generation (RAG) agent built with Google's Agent Development Kit (ADK) that combines document retrieval with GitHub repository integration. The system provides intelligent responses by searching through indexed documents and can interact with GitHub repositories using Model Context Protocol (MCP) tools.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Production System                             │
├─────────────────────────────────────────────────────────────────────┤
│  Frontend: ADK Web UI → Backend: Cloud Run → Agent: RAG + GitHub    │
│  ├── Document Retrieval: Vertex AI Search                          │
│  ├── GitHub Integration: MCP Tools (Issues, PRs, Files)           │
│  └── Secure Token Storage: Google Secret Manager                   │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Components

- **ADK Agent** (`app/agent.py`): Core RAG agent with GitHub MCP integration
- **Vertex AI Search**: Document indexing and retrieval backend  
- **GitHub MCP Tools**: Repository interaction capabilities (issues, PRs, code search)
- **Cloud Run**: Scalable serverless deployment
- **Secret Manager**: Secure GitHub Personal Access Token storage
- **CI/CD Pipeline**: Automated staging and production deployments

## 🚀 Quick Start

### Prerequisites

- **uv**: Python package manager - [Install](https://docs.astral.sh/uv/getting-started/installation/)
- **Google Cloud CLI**: [Install](https://cloud.google.com/sdk/docs/install) and authenticate
- **GitHub Personal Access Token**: For repository integration

### Local Development

```bash
# Install dependencies
make install

# Launch local development environment
make playground
```

This opens the ADK web playground at `http://localhost:8080` where you can test the agent locally.

## 📋 Available Commands

| Command | Description |
|---------|-------------|
| `make install` | Install all dependencies using uv |
| `make playground` | Launch local ADK web development environment |
| `make local-backend` | Run backend server only (for API testing) |
| `make backend` | Deploy to Cloud Run staging environment |
| `make test` | Run unit and integration tests |
| `make lint` | Run code quality checks (ruff, mypy, codespell) |
| `make data-ingestion` | Run document ingestion pipeline |

## 🌐 Deployed Services

### Staging Environment
- **Service URL**: `https://my-agentic-rag-aktu2chyfa-uc.a.run.app/dev-ui/`
- **Project**: `staging-adk`
- **Purpose**: Development testing and validation

### Production Environment  
- **Service URL**: `https://my-agentic-rag-dyrqvuqk4a-uc.a.run.app/dev-ui/`
- **Project**: `production-adk` 
- **Purpose**: Production deployment with manual approval

## 🔄 CI/CD Pipeline

The system uses Google Cloud Build with automated deployments:

1. **Staging**: Automatic deployment on push to `main` branch
2. **Production**: Manual approval required after staging success

### GitHub Triggers
- `deploy-my-agentic-rag-staging`: Auto-deploy to staging
- `deploy-my-agentic-rag`: Production deployment (requires approval)

## 🔐 Security & Configuration

### GitHub Integration
The agent requires a GitHub Personal Access Token stored in Google Secret Manager:

```bash
# The token is automatically accessed from Secret Manager
# Secret name: "github-personal-access-token"
# Projects: staging-adk, production-adk
```

### Required Scopes
- `repo`: Full repository access
- `read:org`: Organization member access  
- `read:user`: User profile access

## 📁 Project Structure

```
my-agentic-rag/
├── app/                    # Core application
│   ├── agent.py           # Main RAG agent with GitHub integration  
│   ├── server.py          # FastAPI backend server
│   ├── retrievers.py      # Document retrieval logic
│   ├── templates.py       # Agent prompt templates
│   └── utils/             # Utility functions
├── .cloudbuild/           # CI/CD pipeline configurations
├── deployment/            # Terraform infrastructure code
│   ├── terraform/         # Production infrastructure
│   └── dev/              # Development/staging infrastructure
├── data_ingestion/        # Document ingestion pipeline
├── tests/                 # Test suites
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── load_test/        # Load testing
├── notebooks/             # Jupyter notebooks for evaluation
├── config/               # Environment configurations
└── Makefile              # Development commands
```

## 🧠 Agent Capabilities

### Document Retrieval (RAG)
- Searches indexed documents using Vertex AI Search
- Provides context-aware responses based on document content
- Supports various document types and formats

### GitHub Integration (MCP Tools)
- **Repository Search**: Find files, code, issues, and PRs
- **Issue Management**: Create, read, and comment on GitHub issues  
- **Pull Request Operations**: List, create, and manage PRs
- **Code Analysis**: Search and analyze repository code
- **File Operations**: Read and understand repository structure

### Usage Examples
```
"Search for documents about machine learning deployment"
"Find GitHub issues related to authentication bugs"  
"Show me the latest pull requests in the backend repository"
"What's the current status of issue #123?"
```

## 🚀 Deployment Process

### Infrastructure Setup
All infrastructure is managed via Terraform:

1. **Development**: `deployment/terraform/dev/`
2. **Production**: `deployment/terraform/`

### Deployment Workflow
1. Push code to `main` branch
2. Cloud Build automatically deploys to staging
3. Test staging deployment at the staging URL
4. Manually approve production deployment in Cloud Console
5. Production deployment completes automatically after approval

## 📊 Monitoring & Observability

- **Cloud Logging**: Application logs and error tracking
- **Cloud Trace**: Request tracing and performance monitoring  
- **BigQuery**: Long-term event storage and analytics
- **Health Checks**: Automated service health monitoring

## 🔧 Development Workflow

1. **Local Development**: Use `make playground` for rapid iteration
2. **Testing**: Run `make test` before committing changes
3. **Code Quality**: `make lint` ensures code standards
4. **Staging Deploy**: Push to `main` triggers automatic staging deployment
5. **Production**: Approve production deployment through Cloud Console

## 📚 Documentation

- **Deployment Guide**: [`deployment/README.md`](deployment/README.md)
- **Data Ingestion**: [`data_ingestion/README.md`](data_ingestion/README.md)
- **Development Notes**: [`GEMINI.md`](GEMINI.md)

## 🏷️ Built With

- [Google Agent Development Kit (ADK)](https://cloud.google.com/agent-development-kit)
- [Vertex AI Search](https://cloud.google.com/vertex-ai/docs/vector-search/overview)
- [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol)
- [Google Cloud Run](https://cloud.google.com/run)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Terraform](https://terraform.io/)

---

*Last updated: October 5, 2025*
