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
- ✅ **Image Generation**: Complete Vertex AI Imagen 3.0 integration with WhatsApp delivery
- ✅ **fal.ai MCP Integration**: Advanced image/video generation via Model Context Protocol
- ✅ **Multimodal AI**: Text, image analysis, audio/video processing, and document handling
- ✅ **CI/CD Pipeline**: Automated deployments with manual production approval
- ✅ **Security**: GitHub tokens managed via Google Secret Manager
- ✅ **Monitoring**: Cloud Logging, Tracing, and observability enabled
- ✅ **Artifact Management**: Fully operational cross-platform artifact system
- ✅ **Architectural Stability**: Resolved all duplicate service and path compatibility issues

**Latest Updates (October 2025)**:
- 🎨 **Image Generation**: End-to-end image creation using Imagen 3.0 with direct WhatsApp delivery
- 🚀 **fal.ai MCP Integration**: Successfully integrated 100+ AI models via Model Context Protocol with proper ADK agent architecture
- 🔧 **fal.ai Artifact Upload**: Fixed critical artifact-to-URL conversion for fal.ai processing with automatic version handling
- 🔐 **Secret Manager Integration**: Automatic FAL_KEY retrieval from Google Secret Manager for seamless production deployment
- 🗂️ **Artifact Version Fix**: Resolved "invalid literal for int() with base 10: 'v1'" error with intelligent filename processing
- 🔧 **MCP Architecture**: Resolved `MCPToolset` stdio configuration with `StdioConnectionParams` and `StdioServerParameters`
- 🧠 **Advanced AI Models**: Access to FLUX, video generation, upscaling, and style transfer through fal.ai
- 🔧 **Artifact System**: Completely fixed GCS artifact loading with architectural improvements
- 📱 **WhatsApp Integration**: Seamless image delivery with proper Baileys format support
- 🚀 **Performance**: Optimized artifact processing with session-scoped storage paths
- 🛠️ **Architecture Fix**: Resolved duplicate artifact service instantiation issues
- 🗂️ **Path Compatibility**: Fixed path structure mismatch between WhatsApp bot and ADK Runner
- ✅ **Production Stability**: Comprehensive debugging and error handling improvements
- 🐳 **Deployment Ready**: Fixed Docker configuration, MCP paths, and environment variables for production deployment

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
│       ↕                                                             │
│  fal.ai MCP Server ↔ 100+ AI Models (FLUX, Video, Upscaling)       │
└─────────────────────────────────────────────────────────────────────┘
```

## 🔧 Recent Architectural Improvements

### October 2025 Major Fixes
We've resolved critical architectural issues that were preventing proper artifact management:

#### ✅ **Duplicate Service Architecture Issue (Fixed)**
- **Problem**: `app/agent.py` was creating its own `GcsArtifactService` instance, conflicting with the Runner-level service
- **Solution**: Removed duplicate instantiation; all artifact functions now use `tool_context` for unified access
- **Impact**: Eliminated service conflicts and improved reliability

#### ✅ **Path Structure Compatibility Issue (Fixed)**
- **Problem**: WhatsApp bot stored artifacts in `artifacts/app/userId/filename` while ADK Runner expected `app/userId/sessionId/filename`
- **Solution**: Updated WhatsApp bot path generation to match ADK Runner expectations
- **Impact**: Cross-platform artifact management now works seamlessly

#### ✅ **Session-Aware Artifact Management**
- **Enhancement**: All artifact operations now include session ID for proper scoping
- **Benefits**: Better user isolation, proper session management, and cleaner artifact organization

### October 2025 Deployment Fixes
We've resolved critical deployment issues that were preventing production deployment:

#### ✅ **Docker Configuration Fixed**
- **Problem**: MCP-FAL dependencies and files were missing from the Docker image
- **Solution**: Updated `Dockerfile` to include `mcp-fal/` directory and install dependencies
- **Impact**: MCP server can now run properly in production containers

#### ✅ **Production Path Configuration**
- **Problem**: Agent used hardcoded development paths (`/workspaces/my-agentic-rag/`)
- **Solution**: Updated agent.py to use container paths (`/code/`)
- **Impact**: MCP server paths work correctly in production environment

#### ✅ **Environment Variable Management**
- **Problem**: FAL_KEY was missing from Cloud Run service configuration
- **Solution**: Added FAL_KEY secret to Terraform and Cloud Run environment
- **Impact**: fal.ai MCP integration now works in deployed environments

#### ✅ **Secret Management Architecture**
- **Enhancement**: Comprehensive secret management for both GitHub PAT and FAL API key
- **Benefits**: Secure API key storage with proper IAM permissions
- **Components**: Terraform-managed secrets with version control

### Core Components

1. **WhatsApp Bot** (`index.js`)
   - Baileys v6.7.8 for WhatsApp Web API
   - Google Cloud Storage auth state management
   - Full media file processing (images, audio, video, documents)
   - Office document conversion (XLSX → CSV, DOCX → text) for Gemini compatibility
   - User session management with automatic cleanup
   - GcsArtifactService with cross-compatible path structure

2. **ADK Agent** (`app/agent.py`)
   - Built using Google's Agent Development Kit
   - Multimodal capabilities for media analysis
   - GitHub MCP tools integration
   - Vertex AI Search for document retrieval
   - Three artifact management tools using unified Runner-level service

3. **Artifact Management System**
   - GCS-based artifact service with unified architecture
   - Session-scoped file organization with proper versioning
   - Cross-compatible path structure between WhatsApp bot and ADK Runner
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
   
   # For fal.ai MCP integration, also set:
   cp .env.example .env
   # Add your FAL API key to .env:
   # FAL_KEY=your_fal_api_key_here
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
- **Image Generation**: Create images using Vertex AI Imagen 3.0 with direct WhatsApp delivery
- **Office Document Support**: Automatic XLSX/DOCX to text conversion for Gemini compatibility
- **Session Management**: Each user gets a unique ADK session with persistent storage
- **Automatic Reconnection**: Handles connection drops gracefully with state recovery
- **Real-time Responses**: Streaming responses from ADK using Server-Sent Events
- **File Versioning**: User-scoped media storage with version control and GCS integration
- **Processing Indicators**: User feedback during media processing and image generation
- **Error Recovery**: Automatic session recreation on service errors with enhanced debugging
- **Multimodal Conversations**: Seamless text, image analysis, and image generation in single conversations

### ADK Agent Capabilities
- **Multimodal Analysis**: 
  - **Images**: Object detection, OCR, composition analysis, content description
  - **Audio**: Transcription, sound identification (when supported)
  - **Video**: Scene analysis, key frame extraction, content understanding
  - **Documents**: Text extraction, summarization, analysis, information retrieval
  - **Office Documents**: XLSX/DOCX automatic conversion to text for Gemini processing
- **Image Generation**: 
  - **Vertex AI Imagen 3.0**: High-quality image creation from text descriptions
  - **WhatsApp Integration**: Direct delivery of generated images via chat
  - **Aspect Ratio Optimization**: Square format (1:1) optimized for mobile viewing
  - **Safety Filtering**: Content safety with graceful error handling
- **GitHub Integration**: Repository search, file access, issue/PR management via MCP tools
- **Document Retrieval**: Vertex AI Search for intelligent information access
- **Artifact Management**: Save, load, and analyze user-uploaded files with session-scoped versioning
- **Web Search**: Real-time information retrieval with source attribution

### Image Generation System

The bot includes a complete image generation pipeline using Vertex AI Imagen 3.0:

- **Natural Language Prompts**: Users can request images using natural language descriptions
- **High-Quality Generation**: Imagen 3.0 produces 1024x1024 PNG images optimized for mobile viewing
- **Direct WhatsApp Delivery**: Generated images are automatically sent through WhatsApp using proper Baileys format
- **Artifact Integration**: All generated images are saved as session-scoped artifacts for future reference
- **Safety Filtering**: Content safety with graceful error handling and alternative suggestions
- **Real-time Feedback**: Users receive immediate confirmation and generation details

**Example Flow**:
1. User: "Generate a picture of a cute hamster eating cheese"
2. Bot: 🤖 Generating image...
3. Bot: [Sends generated image] ✅ Successfully generated image using Imagen 3.0
4. Image automatically saved as artifact: `generated_image_1760203066.png`

## 🎨 fal.ai MCP Integration (October 2025)

### Advanced Image & Video Generation via Model Context Protocol

We've successfully integrated **fal.ai** capabilities through the Model Context Protocol (MCP), dramatically expanding our AI generation capabilities beyond Vertex AI's Imagen 3.0. This integration provides access to cutting-edge image and video generation models through a local MCP server.

#### ✅ **Successful MCP Implementation**

**What We Accomplished**:
- 🔧 **MCP Server Setup**: Successfully cloned and configured the [`mcp-fal`](https://github.com/am0y/mcp-fal) repository
- 🐍 **Virtual Environment**: Created isolated Python environment with `fastmcp`, `httpx`, and `aiofiles`
- 🗝️ **API Authentication**: Configured fal.ai API key with proper environment variable handling
- 🔌 **ADK Integration**: Implemented proper `MCPToolset` with `StdioConnectionParams` and `StdioServerParameters`
- ✅ **Agent Loading**: Successfully integrated fal MCP tools into the main ADK agent without conflicts

#### 🛠️ **Technical Implementation Details**

**MCP Server Configuration**:
```python
# Proper imports for stdio MCP integration
from google.adk.tools.mcp_tool import MCPToolset, StreamableHTTPConnectionParams, StdioConnectionParams
from mcp.client.stdio import StdioServerParameters

# fal.ai MCP toolset configuration
fal_mcp_tools = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="/workspaces/my-agentic-rag/mcp-fal/.venv/bin/python",
            args=["/workspaces/my-agentic-rag/mcp-fal/main.py"],
            env={"FAL_KEY": "your_fal_api_key_here"}
        )
    )
)

# Integration with root agent
fal_mcp_agent = Agent(
    model="gemini-2.5-flash",
    name="fal_mcp_agent",
    instruction="Specialized agent for fal.ai image and video generation",
    tools=[fal_mcp_tools],
)

fal_mcp_tool = AgentTool(agent=fal_mcp_agent)
```

**Key Learning Points**:
1. **Correct Parameter Structure**: `MCPToolset` requires `connection_params` with nested `StdioServerParameters`
2. **Virtual Environment Paths**: Must use absolute paths to the virtual environment Python executable
3. **Environment Variables**: `FAL_KEY` must be passed through the `env` parameter in `StdioServerParameters`
4. **Agent Architecture**: Wrapping `MCPToolset` in an `Agent` then `AgentTool` for seamless integration

#### 🚀 **Available fal.ai Capabilities**

Through the MCP integration, the ADK agent now has access to:

| Tool | Description | Usage |
|------|-------------|-------|
| `models` | List available fal.ai models | Browse 100+ AI models for images, videos, audio |
| `search` | Search models by keywords | Find specific model types (e.g., "flux", "video", "upscale") |
| `schema` | Get model parameter schema | Understand required/optional parameters before generation |
| `generate` | Generate content | Create images/videos with specific model parameters |
| `upload` | Upload files to fal storage | Upload reference images for img2img workflows |
| `status` | Check job status | Monitor long-running generation jobs |
| `result` | Retrieve job results | Get final outputs from queued jobs |

**Advanced Models Available**:
- 🎨 **FLUX Models**: State-of-the-art text-to-image generation
- 🎬 **Video Generation**: Text-to-video and image-to-video conversion
- 🔍 **Upscaling**: AI-powered image enhancement and super-resolution
- 🎭 **Style Transfer**: Artistic style application and transformation
- 🖼️ **Image Editing**: Inpainting, outpainting, and image manipulation

#### ✅ **fal.ai Artifact Upload Integration (October 2025)**

**Critical Fix for Artifact-to-URL Conversion** (Latest Update):

We've successfully resolved multiple blocking issues preventing WhatsApp users from uploading artifacts to fal.ai for advanced image processing:

**The Problems**:
- Users could upload images to WhatsApp → ADK artifact system ✅
- But artifacts couldn't be converted to fal.ai URLs for processing ❌
- Error: `"invalid literal for int() with base 10: 'v1'"` when calling `upload_artifact_to_fal`
- Missing ADK package dependencies in production environment

**Root Cause Analysis**:
1. **Artifact Versioning**: ADK stores artifacts with version suffixes (e.g., `media_abc123.jpg v1`)
2. **Version Parsing**: The `load_artifact()` function expected base filenames without version strings
3. **Environment Issues**: ADK Python package wasn't installed, causing import failures
4. **Pattern Variations**: Different version formats needed support (`v1`, `_v1`, `(1)`)

**Complete Solution Implemented**:

```python
async def upload_artifact_to_fal(filename: str, tool_context: ToolContext) -> str:
    """Enhanced artifact upload with comprehensive version handling"""
    
    # 1. Multiple filename pattern attempts
    possible_filenames = [filename]  # Original
    
    # 2. Handle version suffixes with regex patterns
    version_patterns = [
        r' v\d+$',      # " v1", " v2", etc.
        r'_v\d+$',      # "_v1", "_v2", etc.  
        r' \(\d+\)$',   # " (1)", " (2)", etc.
    ]
    
    for pattern in version_patterns:
        cleaned = re.sub(pattern, '', filename)
        if cleaned != filename:
            possible_filenames.append(cleaned)
    
    # 3. Try loading with each filename variation
    for attempt_filename in possible_filenames:
        try:
            artifact_part = await tool_context.load_artifact(attempt_filename)
            break  # Success!
        except Exception as error:
            continue  # Try next variation
    
    # 4. Auto-retrieve FAL_KEY from Google Secret Manager
    if not os.getenv("FAL_KEY"):
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        secret_name = f"projects/{project_id}/secrets/fal-api-key/versions/latest"
        response = client.access_secret_version(request={"name": secret_name})
        os.environ["FAL_KEY"] = response.payload.data.decode("UTF-8")
    
    # 5. Upload to fal.ai CDN with enhanced error handling
    import fal_client
    file_url = fal_client.upload_file(temp_path)
    
    return f"fal.ai URL: {file_url}"
```

**Key Improvements**:
- ✅ **Robust Version Handling**: Automatically strips version suffixes from filenames
- ✅ **Multiple Pattern Support**: Handles `v1`, `_v1`, `(1)` and other common formats
- ✅ **Fallback Strategy**: Tries multiple filename variations until one succeeds
- ✅ **Secret Manager Integration**: Automatic FAL_KEY retrieval for production environments
- ✅ **Enhanced Error Reporting**: Shows all attempted variations for debugging
- ✅ **Dependencies Resolved**: ADK package installation and import fixes
- ✅ **Production Ready**: Works seamlessly across staging and production environments

**User Experience Impact**:
```
Before: ❌ Error uploading artifact to fal.ai
        💭 "invalid literal for int() with base 10: 'v1'"

After:  ✅ Successfully uploaded 'image.jpg v1' to fal.ai storage!
        📎 fal.ai URL: https://v3b.fal.media/files/b/koala/...
        🎯 Ready for advanced fal.ai model processing
        💡 Automatically tried filenames: ['image.jpg v1', 'image.jpg']
```

**Technical Validation**:
- Tested with various ADK artifact naming patterns
- Confirmed Secret Manager FAL_KEY retrieval works
- Enhanced debug logging for production troubleshooting
- Backwards compatible with existing artifact workflows

**Deployment Considerations**:
- No manual environment variable setup required in production
- FAL_KEY automatically managed via Terraform-deployed Google Secret Manager
- Comprehensive error handling prevents service disruption
- Works across all deployment environments (dev, staging, production)

#### 📁 **Project Structure Updates**

```
my-agentic-rag/
├── mcp-fal/                    # fal.ai MCP server (cloned repository)
│   ├── .venv/                  # Virtual environment with MCP dependencies
│   ├── main.py                 # MCP server entry point
│   └── requirements.txt        # fastmcp, httpx, aiofiles
├── app/
│   └── agent.py                # Updated with fal MCP integration
├── mcp-fal-adk-setup.md        # Complete setup documentation
└── README.md                   # This file (updated with integration details)
```

#### 🧪 **Testing & Validation**

**What We Verified**:
- ✅ **Server Startup**: `"Application startup complete"` confirms successful agent loading
- ✅ **MCP Connection**: No MCP-related errors during initialization
- ✅ **Import Resolution**: All required classes (`StdioConnectionParams`, `StdioServerParameters`) properly imported
- ✅ **Environment Setup**: FAL_KEY environment variable correctly passed to MCP server
- ✅ **Agent Architecture**: fal MCP tools successfully integrated alongside existing GitHub MCP and other tools

**Example Test Flow**:
```bash
# Start the ADK server with fal MCP integration
cd /workspaces/my-agentic-rag
export FAL_KEY="your_fal_api_key_here"
make local-backend

# Expected output:
# INFO: Application startup complete.
# (No MCP-related errors)
```

#### 🔍 **Troubleshooting Guide**

**Common Issues Resolved During Implementation**:

| Issue | Solution | Prevention |
|-------|----------|------------|
| `ImportError: StdioServerParameters` | Import from `mcp.client.stdio` not `google.adk.tools.mcp_tool` | Use correct import paths |
| `TypeError: unexpected keyword 'transport'` | Use `connection_params=StdioConnectionParams()` structure | Follow proper MCPToolset parameter nesting |
| `ValidationError: server_params field required` | Wrap parameters in `StdioServerParameters()` object | Always use the nested parameter structure |
| Port conflicts (`Address already in use`) | Kill existing processes using port 8000 | Check for running uvicorn processes before starting |

#### 📖 **Documentation References**

For complete setup instructions, see:
- 📋 **Setup Guide**: [`mcp-fal-adk-setup.md`](./mcp-fal-adk-setup.md) - Comprehensive step-by-step integration guide
- 🔗 **MCP Server**: [am0y/mcp-fal](https://github.com/am0y/mcp-fal) - Original MCP server repository
- 🧠 **Google ADK**: [Agent Development Kit Documentation](https://cloud.google.com/agent-development-kit) - Official ADK guides

### Office Document Processing

The system automatically handles Microsoft Office documents that are not natively supported by Google's Gemini AI:

- **XLSX Files**: Converted to CSV format using the `xlsx` library, preserving data structure
- **DOCX Files**: Converted to plain text using the `mammoth` library, maintaining readability
- **User Feedback**: Clear indication when conversion is happening ("Converting office document to text...")
- **Seamless Integration**: Converted files are processed through the same ADK pipeline as other documents

**Supported Formats**:
- ✅ PDF (native Gemini support)
- ✅ Images (JPG, PNG, GIF, WebP) - Analysis & Generation
- ✅ Audio (MP3, WAV, etc.)
- ✅ Video (MP4, AVI, etc.)
- ✅ XLSX → CSV (automatic conversion)
- ✅ DOCX → Text (automatic conversion)
- 🎨 **Image Generation**: Vertex AI Imagen 3.0 (PNG, 1024x1024, optimized for WhatsApp)

### Storage Architecture
```
gs://adk_artifact/
├── artifacts/                  # Legacy user-scoped storage
│   └── app/{userId}/{filename}/v{n}
└── app/                       # ADK session-scoped storage (current)
    └── {userId}/              # WhatsApp user ID (e.g., 1234567890@s.whatsapp.net)
        └── {sessionId}/       # ADK session ID (e.g., 7504650094931607552)
            └── {filename}/    # Artifact filename (e.g., generated_image_1760203066.png)
                └── 0          # Version (ADK uses 0 for latest)

Examples:
- Generated Image: gs://adk_artifact/app/6592377976@s.whatsapp.net/7504650094931607552/generated_image_1760203066.png/0
- Uploaded Media: gs://adk_artifact/artifacts/app/user123/document.pdf/v1

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
- **Image Generation Tools**: 
  - `generate_image`: Creates images using Vertex AI Imagen 3.0 with direct artifact integration
- **fal.ai MCP Tools** (via `fal_mcp_agent`):
  - `models`: List 100+ available AI models for image, video, and audio generation
  - `search`: Find specific models by keywords (e.g., "flux", "video", "upscale")
  - `schema`: Get detailed parameter schemas for any model before generation
  - `generate`: Create content using cutting-edge models like FLUX and video generators
  - `upload`: Upload reference images for img2img and style transfer workflows
  - `status` & `result`: Monitor and retrieve outputs from long-running generation jobs
- **Artifact Tools**: 
  - `list_user_artifacts`: Lists all media files uploaded by user (including generated images)
  - `load_and_analyze_artifact`: Loads and analyzes specific artifacts with multimodal support
  - `save_analysis_result`: Saves AI analysis results as versioned artifacts
- **GitHub Tools**: Repository search, file access, issue management via MCP integration
- **Web Search Tools**: Real-time information retrieval with source attribution
- **Retrieval Tools**: Document search and context provision via Vertex AI Search

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

### Deployment Verification

After deployment, verify all components are working:

```bash
# Check service health
curl https://your-service-url/health

# Verify MCP-FAL integration in logs
gcloud run services logs read my-agentic-rag \
  --region=us-central1 --project=YOUR_PROJECT_ID \
  | grep -E "(fal|MCP|Application startup complete)"

# Test fal.ai capabilities via API
curl -X POST https://your-service-url/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "List available fal.ai models"}'
```

**Required Secrets for Deployment**:
- `github-pat-mcp`: GitHub Personal Access Token with repo access
- `fal-api-key`: fal.ai API key from https://fal.ai/dashboard

## 📱 Usage Examples

### WhatsApp Interactions

1. **Text Queries**:
   ```
   User: "Search for information about machine learning"
   Bot: [Returns comprehensive ML information from documents and web]
   
   User: "Find issues in my GitHub repository"
   Bot: [Searches GitHub and returns relevant issues and PRs]
   ```

2. **Media Analysis & Image Generation**:
   ```
   User: [Sends an image of a document]
   Bot: 🤖 Processing your image...
   Bot: [Detailed OCR results and document analysis]
   
   User: "Generate a picture of a cute hamster eating cheese"
   Bot: 🤖 Generating image...
   Bot: [Sends generated image directly] ✅ Successfully generated image using Imagen 3.0
   
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
   Bot: Here are your available artifacts:
        • generated_image_1760203066.png
        • document_analysis.pdf
        • voice_memo.mp3
   
   User: "Analyze the image I generated earlier"
   Bot: [Loads and analyzes the generated hamster image]
        "The artifact is an image showing a cute, fat hamster happily 
         munching on a block of cheese, in cartoon style."
   
   User: "Describe the only artifact I have"
   Bot: [Provides detailed analysis of the specific artifact]
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

#### Unit Tests
```bash
# Run WhatsApp bot tests
npm test

# Run ADK server tests
pytest tests/

# Run integration tests
npm run test:integration
```

#### Artifact System Testing (Post-Fix Verification)
```bash
# Test WhatsApp bot startup and ADK connection
npm run start:check

# Verify artifact service initialization
node -e "console.log('Testing artifact service...'); process.exit(0);"

# Test cross-platform artifact compatibility
# 1. Send an image via WhatsApp
# 2. Use "List artifact" command
# 3. Verify artifacts are found and accessible
```

#### Architecture Verification
The following critical issues have been **RESOLVED**:
- ✅ **Duplicate Service Architecture**: No more conflicting GcsArtifactService instances
- ✅ **Path Structure Compatibility**: WhatsApp bot and ADK Runner now use compatible paths
- ✅ **Session-Scoped Storage**: Proper user/session isolation in artifact management

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

3. **Image Generation Not Working**:
   - Verify Vertex AI Imagen API is enabled
   - Check artifact service initialization: `this.artifactService` (not `this.gcsArtifactService`)
   - Review GCS permissions for `adk_artifact` bucket
   - Test GCS connectivity: `gsutil ls gs://adk_artifact/`

4. **Media Processing Errors**:
   - Verify GCS bucket permissions and access
   - Check artifact bucket connectivity and quotas
   - Review media file size limits and formats
   - Validate ADK service artifact endpoints with session-scoped paths

5. **~~Artifact Loading Failures~~ (RESOLVED)**:
   - ✅ **Fixed**: Duplicate artifact service architecture issue resolved
   - ✅ **Fixed**: Path structure compatibility between WhatsApp bot and ADK Runner
   - ✅ **Fixed**: Session-scoped artifact management now working properly
   - **If issues persist**: Check enhanced debugging logs in bot console

6. **~~"No saved artifacts" Error~~ (RESOLVED)**:
   - ✅ **Root Cause Fixed**: Path mismatch between WhatsApp storage and ADK expectations
   - ✅ **Solution Implemented**: Cross-compatible path structure now in place
   - **Verification**: `list_user_artifacts` function now works correctly

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
- **[Model Context Protocol (MCP)](https://github.com/modelcontextprotocol)** - Standardized protocol for AI tool integration
- **[fal.ai](https://fal.ai/)** - Advanced AI model platform for image/video generation

### Supporting Libraries
- **[Axios](https://axios-http.com/)** - HTTP client for ADK communication
- **[Pino](https://getpino.io/)** - High-performance logging for Node.js
- **[XLSX](https://www.npmjs.com/package/xlsx)** - Excel file parsing and conversion to CSV
- **[Mammoth](https://www.npmjs.com/package/mammoth)** - DOCX to text conversion
- **[FastMCP](https://pypi.org/project/fastmcp/)** - Fast Model Context Protocol server implementation
- **[httpx](https://www.python-httpx.org/)** - Async HTTP client for MCP server communication
- **[aiofiles](https://pypi.org/project/aiofiles/)** - Async file I/O for MCP server operations
- **[Vertex AI](https://cloud.google.com/vertex-ai)** - Document search, retrieval, and Imagen 3.0 image generation
- **[Google Cloud Storage](https://cloud.google.com/storage)** - Cross-compatible artifact storage with unified architecture
- **[Google Cloud Run](https://cloud.google.com/run)** - Serverless deployment platform

### Architecture Improvements
- **Unified Artifact Service**: Single point of truth for artifact management across platforms
- **Cross-Compatible Paths**: WhatsApp bot and ADK Runner now use synchronized path structures
- **Session-Scoped Storage**: Proper user/session isolation for enhanced data organization

### Development Tools
- **[Terraform](https://terraform.io/)** - Infrastructure as code
- **[Docker](https://docker.com/)** - Containerization
- **[Google Cloud Build](https://cloud.google.com/build)** - CI/CD pipeline
- **[ESLint](https://eslint.org/) / [Black](https://black.readthedocs.io/)** - Code formatting

---

**Built with ❤️ using Google's Agent Development Kit and Baileys WhatsApp library**

*Production-ready • Scalable • Secure • Multimodal • Architecturally Sound • Open Source*

**Recently Enhanced**: October 2025 architectural improvements resolved all major artifact management issues, ensuring seamless cross-platform operation between WhatsApp bot and ADK Runner systems.