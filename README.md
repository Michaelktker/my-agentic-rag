# My Agentic RAG - WhatsApp ADK Bot

A comprehensive Retrieval-Augmented Generation (RAG) system with WhatsApp integration, built using Google's Agent Development Kit (ADK). This production-ready application combines intelligent document search, GitHub repository integration, WhatsApp multimodal communication, and advanced artifact management.

## 🚀 Quick Start

### WhatsApp Bot (Recommended)
```bash
npm run start:check
```

This will check dependencies, validate your setup, and start the WhatsApp bot with ADK integration.

### ADK Server Only
```bash
python -m app.server
```

Available at `http://localhost:8000`

## 📋 Project Overview

### Purpose
A production-ready system that combines:
- **WhatsApp Integration**: Full-featured bot with media support using Baileys
- **Document Search**: Vertex AI Search for intelligent retrieval
- **GitHub Integration**: Repository access via Model Context Protocol (MCP) tools
- **Multimodal AI**: Image, audio, video, and document analysis
- **Artifact Management**: GCS-based media storage with versioning
- **Scalable Deployment**: Google Cloud Platform with CI/CD pipeline

### Current Status
- ✅ **Production Ready**: Deployed to staging and production environments
- ✅ **WhatsApp Bot**: Full media support with ADK artifact integration
- ✅ **CI/CD Pipeline**: Automated deployments with manual production approval
- ✅ **Security**: GitHub tokens managed via Google Secret Manager
- ✅ **Monitoring**: Cloud Logging, Tracing, and observability enabled

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    WhatsApp ADK Bot System                          │
├─────────────────────────────────────────────────────────────────────┤
│  WhatsApp ↔ Baileys ↔ Node.js Bot ↔ Google ADK Service             │
│                         ↕                                           │
│  Google Cloud Storage ← Artifacts & Auth State                     │
│                         ↕                                           │
│  ADK Agent ↔ GitHub MCP Tools ↔ Vertex AI Search                   │
└─────────────────────────────────────────────────────────────────────┘
```

### Core Components

1. **WhatsApp Bot** (`index.js`)
   - Baileys v6.7.8 for WhatsApp Web API
   - Google Cloud Storage auth state management
   - ADK streaming integration with Server-Sent Events
   - Full media file processing (images, audio, video, documents)
   - Office document conversion (XLSX → CSV, DOCX → text) for Gemini compatibility
   - User session management with automatic cleanup
   - GcsArtifactService for media storage

2. **ADK Agent** (`app/agent.py`)
   - Built using Google's Agent Development Kit
   - Multimodal capabilities for media analysis
   - GitHub MCP tools integration
   - Vertex AI Search for document retrieval
   - Streaming responses for real-time interaction
   - Three artifact management tools for media processing

3. **Artifact Management System**
   - GCS-based artifact service for media storage
   - User-scoped file organization with versioning
   - Automatic media type detection and processing
   - ADK-compatible multimodal Part objects
   - MediaHandler class for WhatsApp media conversion

4. **FastAPI Backend** (`app/server.py`)
   - RESTful API endpoints for agent interaction
   - Health checks and service monitoring
   - CORS configuration for web UI integration

### Infrastructure

- **Production**: `production-adk` project with manual approval
- **Staging**: `staging-adk` project with auto-deployment
- **Storage**: 
  - Auth states: `gs://authstate`
  - Media artifacts: `gs://adk_artifact`
- **Services**:
  - ADK endpoint: `https://my-agentic-rag-638797485217.us-central1.run.app`
  - Secret Management: GitHub tokens via Google Secret Manager

## 🔧 Installation & Setup

### Prerequisites

1. **Google Cloud Setup**:
   ```bash
   gcloud auth application-default login
   gcloud config set project production-adk
   ```

2. **Node.js**: Version 18+ for WhatsApp bot
3. **Python**: 3.9+ for ADK server
4. **Required Services**:
   - ADK service running on Google Cloud Run
   - GCS buckets: `gs://authstate`, `gs://adk_artifact`
   - Vertex AI Search configured

### Installation

1. **Install Dependencies**:
   ```bash
   # Node.js dependencies for WhatsApp bot
   npm install
   
   # Python dependencies for ADK server
   pip install -r requirements.txt
   ```

2. **Environment Setup**:
   ```bash
   # Copy and configure environment variables
   cp config/staging.env .env
   # Edit .env with your specific settings
   ```

3. **Google Cloud Configuration**:
   ```bash
   # Ensure proper permissions for GCS buckets
   gsutil iam ch user:your-email@domain.com:roles/storage.admin gs://authstate
   gsutil iam ch user:your-email@domain.com:roles/storage.admin gs://adk_artifact
   ```

## 🎯 Features

### WhatsApp Bot Features
- **QR Code Authentication**: Easy WhatsApp Web setup and pairing
- **Media Processing**: Images, audio, video, documents with ADK integration
- **Office Document Support**: Automatic XLSX/DOCX to text conversion for Gemini compatibility
- **Session Management**: Each user gets a unique ADK session
- **Automatic Reconnection**: Handles connection drops gracefully
- **Real-time Responses**: Streaming responses from ADK using Server-Sent Events
- **File Versioning**: User-scoped media storage with version control
- **Processing Indicators**: User feedback during media processing
- **Error Recovery**: Automatic session recreation on service errors

### ADK Agent Capabilities
- **Multimodal Analysis**: 
  - **Images**: Object detection, OCR, composition analysis, content description
  - **Audio**: Transcription, sound identification (when supported)
  - **Video**: Scene analysis, key frame extraction, content understanding
  - **Documents**: Text extraction, summarization, analysis, information retrieval
  - **Office Documents**: XLSX/DOCX automatic conversion to text for Gemini processing
- **GitHub Integration**: Repository search, file access, issue/PR management
- **Document Retrieval**: Vertex AI Search for intelligent information access
- **Artifact Management**: Save, load, and analyze user-uploaded files with versioning

### Office Document Processing

The system automatically handles Microsoft Office documents that are not natively supported by Google's Gemini AI:

- **XLSX Files**: Converted to CSV format using the `xlsx` library, preserving data structure
- **DOCX Files**: Converted to plain text using the `mammoth` library, maintaining readability
- **User Feedback**: Clear indication when conversion is happening ("Converting office document to text...")
- **Seamless Integration**: Converted files are processed through the same ADK pipeline as other documents

**Supported Formats**:
- ✅ PDF (native Gemini support)
- ✅ Images (JPG, PNG, GIF, WebP)
- ✅ Audio (MP3, WAV, etc.)
- ✅ Video (MP4, AVI, etc.)
- ✅ XLSX → CSV (automatic conversion)
- ✅ DOCX → Text (automatic conversion)

### Storage Architecture
```
gs://adk_artifact/
└── artifacts/
    └── app/                    # Application namespace
        └── {userId}/           # WhatsApp user ID (e.g., 1234567890@s.whatsapp.net)
            └── {filename}/     # Media filename (e.g., image_123.png, report.xlsx)
                ├── v1          # Version 1 of the file
                ├── v2          # Version 2 of the file
                └── v3          # Latest version

gs://authstate/
└── whatsapp-auth.json          # WhatsApp authentication state
```

## 🛠️ Development Guide

### Project Structure
```
my-agentic-rag/
├── app/                    # ADK server code
│   ├── agent.py           # Main agent with multimodal tools
│   ├── retrievers.py      # Vertex AI Search integration
│   ├── server.py          # FastAPI application
│   ├── templates.py       # Response templates
│   └── utils/             # Utility functions
│       ├── gcs.py         # Google Cloud Storage utilities
│       ├── tracing.py     # Logging and tracing
│       └── typing.py      # Type definitions
├── config/                # Environment configurations
│   ├── production.env     # Production environment variables
│   └── staging.env        # Staging environment variables
├── deployment/           # Terraform infrastructure code
│   └── terraform/        # Infrastructure as code
├── data_ingestion/       # Document processing pipeline
│   └── data_ingestion_pipeline/  # Pipeline components
├── index.js              # WhatsApp bot main file
├── config.json           # Bot configuration
├── package.json          # Node.js dependencies
├── pyproject.toml        # Python project configuration
├── Dockerfile            # Container configuration
└── Makefile              # Build and deployment commands
```

### Key Classes & Services

#### WhatsApp Bot (`index.js`)
- **GcsArtifactService**: Media file storage and retrieval with versioning
- **MediaHandler**: WhatsApp media processing and ADK conversion with XLSX/DOCX support
- **Document Conversion**: Automatic XLSX to CSV and DOCX to text conversion using xlsx and mammoth libraries
- **ADK Integration**: Streaming communication with agent using SSE
- **Session Management**: User-specific conversation contexts

#### ADK Agent (`app/agent.py`)
- **Artifact Tools**: 
  - `list_user_artifacts`: Lists all media files uploaded by user
  - `load_and_analyze_artifact`: Loads and analyzes specific artifacts
  - `save_analysis_result`: Saves AI analysis results as versioned artifacts
- **GitHub Tools**: Repository search, file access, issue management
- **Retrieval Tools**: Document search and context provision via Vertex AI

### Environment Variables
```bash
# ADK Configuration
ADK_URL=https://my-agentic-rag-638797485217.us-central1.run.app
ARTIFACTS_BUCKET_NAME=adk_artifact

# WhatsApp Configuration
AUTH_BUCKET_NAME=authstate
MAX_MESSAGE_LENGTH=1500

# Google Cloud
GOOGLE_CLOUD_PROJECT=production-adk
```

## 🚀 Deployment

### Local Development
```bash
# Start WhatsApp bot in development mode
npm run dev

# Start ADK server with hot reload
python -m app.server --reload
```

### Staging Deployment (Automatic)
```bash
git push origin main
# Triggers automatic staging deployment via Cloud Build
```

### Production Deployment (Manual Approval)
1. Create and push a tag:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
2. Approve deployment in Google Cloud Build console

### Docker Deployment
```bash
# Build and run WhatsApp bot
docker build -t whatsapp-adk-bot .
docker run -p 3000:3000 whatsapp-adk-bot

# Build and run ADK server
docker build -f Dockerfile -t adk-server .
docker run -p 8000:8000 adk-server
```

## 📱 Usage Examples

### WhatsApp Interactions

1. **Text Queries**:
   ```
   User: "Search for information about machine learning"
   Bot: [Returns comprehensive ML information from documents and web]
   
   User: "Find issues in my GitHub repository"
   Bot: [Searches GitHub and returns relevant issues and PRs]
   ```

2. **Media Analysis**:
   ```
   User: [Sends an image of a document]
   Bot: 🤖 Processing your image...
   Bot: [Detailed OCR results and document analysis]
   
   User: [Sends an audio file]
   Bot: 🤖 Processing your audio...
   Bot: [Transcription and audio content analysis]
   
   User: [Sends an XLSX/DOCX file]
   Bot: 🤖 Converting office document to text for processing...
   Bot: [Converted text content analysis and insights]
   ```

3. **Artifact Management**:
   ```
   User: "List my uploaded files"
   Bot: [Shows all user's uploaded media with versions]
   
   User: "Analyze the image I sent earlier"
   Bot: [Loads specific artifact and provides detailed analysis]
   ```

### API Endpoints

- `GET /health` - Service health check
- `POST /chat` - Direct ADK agent interaction
- `POST /run` - Standard ADK API calls
- `POST /run_sse` - Streaming ADK responses
- `GET /docs` - Interactive API documentation

## 🔍 Monitoring & Observability

### Logging
- **WhatsApp Bot**: Structured JSON logging with Pino
- **ADK Agent**: Python logging with Cloud Logging integration
- **Media Processing**: Detailed artifact processing logs
- **User Sessions**: Session lifecycle and management events

### Metrics
- Message processing latency and throughput
- ADK response times and streaming performance
- Media file processing success rates and error rates
- User engagement analytics and session duration
- GitHub API usage and rate limiting

### Error Handling
- **Connection Issues**: Automatic retry with exponential backoff
- **Service Errors**: Graceful fallbacks and user-friendly messages
- **Media Processing**: Comprehensive error handling with user feedback
- **Session Management**: Automatic recreation on service failures

### Log Examples
```json
{"level":30,"time":1696982345000,"msg":"Received message from 6592377976@s.whatsapp.net"}
{"level":30,"time":1696982346000,"msg":"Processing media: image.jpg (image/jpeg, 245KB)"}
{"level":30,"time":1696982347000,"msg":"Artifact saved: user123/image_001.jpg v1"}
{"level":30,"time":1696982348000,"msg":"ADK Streaming Response: 200, 1247 characters"}
```

## 🔒 Security & Compliance

### Authentication & Authorization
- **Google Cloud IAM**: Service-to-service authentication
- **WhatsApp Web**: Secure QR code authentication with persistent sessions
- **GitHub Integration**: Token management via Google Secret Manager
- **User Isolation**: Per-user artifact scoping and session management

### Data Protection
- **Encryption**: At-rest encryption in Google Cloud Storage
- **User Privacy**: User data isolation and scoping by WhatsApp ID
- **Automatic Cleanup**: Session and temporary data lifecycle management
- **GDPR Compliance**: User data handling and retention policies

### Best Practices
- **Principle of Least Privilege**: Minimal required permissions
- **Regular Security Audits**: Automated vulnerability scanning
- **Encrypted Communication**: TLS/HTTPS for all external communications
- **Secure Credential Management**: No hardcoded secrets or tokens

## 🤝 Contributing

### Development Guidelines
1. **Fork the repository** and create a feature branch
2. **Follow existing patterns**: Maintain consistency with current codebase
3. **Add comprehensive tests**: Include unit and integration tests
4. **Update documentation**: Keep README and code comments current
5. **Code style**: Use ESLint for JavaScript, Black for Python
6. **Ensure backward compatibility** when possible

### Pull Request Process
1. Create feature branch: `git checkout -b feature/amazing-feature`
2. Make changes and test thoroughly
3. Update documentation and add tests
4. Submit PR with detailed description
5. Address code review feedback
6. Ensure CI/CD pipeline passes

### Testing
```bash
# Run WhatsApp bot tests
npm test

# Run ADK server tests
pytest tests/

# Run integration tests
npm run test:integration
```

## 🆘 Troubleshooting

### Common Issues

1. **WhatsApp Connection Failed**:
   ```bash
   # Clear auth state and restart
   gsutil rm gs://authstate/whatsapp-auth.json
   npm run start:check
   ```

2. **ADK Service Unreachable**:
   ```bash
   # Check service status
   curl https://my-agentic-rag-638797485217.us-central1.run.app/health
   ```

3. **Media Processing Errors**:
   - Verify GCS bucket permissions and access
   - Check artifact bucket connectivity and quotas
   - Review media file size limits and formats
   - Validate ADK service artifact endpoints

4. **Session Management Issues**:
   ```bash
   # Check session status
   curl -X POST https://my-agentic-rag-638797485217.us-central1.run.app/apps/app/users/{user_id}/sessions
   ```

### Debug Mode
```bash
# Enable detailed WhatsApp bot logging
DEBUG=* npm start

# Enable verbose ADK server logging
PYTHONPATH=. python -m app.server --log-level debug
```

### Getting Help
- **Google Cloud Console**: Check logs and service metrics
- **WhatsApp Bot Console**: Review real-time processing logs
- **ADK Documentation**: Consult official ADK guides
- **GitHub Issues**: Open issues for bugs or feature requests

## 📚 Related Documentation

### Original Documentation Files (Consolidated)
- ✅ **WhatsApp Setup**: Previously in `WHATSAPP_README.md` - now integrated
- ✅ **Development Guide**: Previously in `GEMINI.md` - now integrated
- ✅ **Artifact Implementation**: Previously in `ADK_ARTIFACTS_IMPLEMENTATION.md` - now integrated
- ✅ **Agent Integration**: Previously in `ADK_AGENT_INTEGRATION_COMPLETE.md` - now integrated

### External Resources
- [Google Agent Development Kit Documentation](https://cloud.google.com/agent-development-kit)
- [Baileys WhatsApp Library](https://github.com/WhiskeySockets/Baileys)
- [Google Cloud Storage Documentation](https://cloud.google.com/storage/docs)
- [Vertex AI Search Documentation](https://cloud.google.com/vertex-ai-search-and-conversation)

## 🏷️ Built With

### Core Technologies
- **[Baileys](https://github.com/WhiskeySockets/Baileys)** - WhatsApp Web API library
- **[Google Agent Development Kit (ADK)](https://cloud.google.com/adk)** - AI agent framework
- **[FastAPI](https://fastapi.tiangolo.com/)** - Python web framework
- **[Google Cloud Storage](https://cloud.google.com/storage)** - File and state storage

### Supporting Libraries
- **[Axios](https://axios-http.com/)** - HTTP client for ADK communication
- **[Pino](https://getpino.io/)** - High-performance logging for Node.js
- **[XLSX](https://www.npmjs.com/package/xlsx)** - Excel file parsing and conversion to CSV
- **[Mammoth](https://www.npmjs.com/package/mammoth)** - DOCX to text conversion
- **[Vertex AI](https://cloud.google.com/vertex-ai)** - Document search and retrieval
- **[Google Cloud Run](https://cloud.google.com/run)** - Serverless deployment platform

### Development Tools
- **[Terraform](https://terraform.io/)** - Infrastructure as code
- **[Docker](https://docker.com/)** - Containerization
- **[Google Cloud Build](https://cloud.google.com/build)** - CI/CD pipeline
- **[ESLint](https://eslint.org/) / [Black](https://black.readthedocs.io/)** - Code formatting

---

**Built with ❤️ using Google's Agent Development Kit and Baileys WhatsApp library**

*Production-ready • Scalable • Secure • Multimodal • Open Source*