# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# mypy: disable-error-code="arg-type"
# Full deployment test - October 3, 2025 - Testing complete CI/CD pipeline
# Deployment trigger - October 19, 2025 - Testing staging deployment
import os
import base64
import uuid
import asyncio
import aiohttp
import json
import logging
from io import BytesIO
from typing import Optional

import google
import vertexai
from google.adk.agents import Agent
from google.adk.tools.mcp_tool import MCPToolset, StreamableHTTPConnectionParams, StdioConnectionParams
from mcp.client.stdio import StdioServerParameters
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools import FunctionTool, LongRunningFunctionTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from langchain_google_vertexai import VertexAIEmbeddings


from app.retrievers import get_compressor, get_retriever
from app.templates import format_docs
from app.webhook_handler import webhook_handler

EMBEDDING_MODEL = "text-embedding-005"
LLM_LOCATION = "global"
LOCATION = "us-central1"
LLM = "gemini-2.5-flash"

# GitHub repository constants
GITHUB_OWNER = "Michaelktker"
GITHUB_REPO = "my-agentic-rag"

# Configure logging
logger = logging.getLogger(__name__)

# ADK Endpoint Configuration - Production first, staging fallback
PRODUCTION_ADK_URL = os.getenv("PRODUCTION_ADK_URL", "https://my-agentic-rag-638797485217.us-central1.run.app")
STAGING_ADK_URL = os.getenv("STAGING_ADK_URL", "https://my-agentic-rag-454188184539.us-central1.run.app")

# Health check timeout in seconds
HEALTH_CHECK_TIMEOUT = int(os.getenv("HEALTH_CHECK_TIMEOUT", "5"))

credentials, project_id = google.auth.default()

# Handle case where project_id might be None (e.g., in development environments)
if project_id is None:
    project_id = "production-adk"  # Use the configured project ID
    
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", LLM_LOCATION)
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")

vertexai.init(project=project_id, location=LOCATION)
embedding = VertexAIEmbeddings(
    project=project_id, location=LOCATION, model_name=EMBEDDING_MODEL
)


EMBEDDING_COLUMN = "embedding"
TOP_K = 5

data_store_region = os.getenv("DATA_STORE_REGION", "us")
data_store_id = os.getenv("DATA_STORE_ID", "my-agentic-rag-datastore")

retriever = get_retriever(
    project_id=project_id,
    data_store_id=data_store_id,
    data_store_region=data_store_region,
    embedding=embedding,
    embedding_column=EMBEDDING_COLUMN,
    max_documents=10,
)

compressor = get_compressor(
    project_id=project_id,
)

# The artifact service is handled by the Runner created in get_fast_api_app
# Functions will use tool_context to access artifacts configured at Runner level


def retrieve_docs(query: str) -> str:
    """
    Useful for retrieving relevant documents based on a query.
    Use this when you need additional information to answer a question.

    Args:
        query (str): The user's question or search query.

    Returns:
        str: Formatted string containing relevant document content retrieved and ranked based on the query.
    """
    try:
        # Use the retriever to fetch relevant documents based on the query
        retrieved_docs = retriever.invoke(query)
        # Re-rank docs with Vertex AI Rank for better relevance
        ranked_docs = compressor.compress_documents(
            documents=retrieved_docs, query=query
        )
        # Format ranked documents into a consistent structure for LLM consumption
        formatted_docs = format_docs.format(docs=ranked_docs)
    except Exception as e:
        return f"Calling retrieval tool with query:\n\n{query}\n\nraised the following error:\n\n{type(e)}: {e}"

    return formatted_docs


async def list_user_artifacts(tool_context: ToolContext) -> str:
    """
    Lists all artifacts (media files) uploaded by the current user across all sessions.
    Use this to see what files are available for analysis.

    Returns:
        str: A formatted list of available artifacts or an error message.
    """
    try:
        # First try the standard ADK approach
        try:
            available_files = await tool_context.list_artifacts()
            if available_files:
                file_list = "\n".join([f"• {filename}" for filename in available_files])
                return f"Here are your available artifacts:\n{file_list}\n\nI can analyze any of these files for you!"
        except Exception as context_error:
            print(f"DEBUG list_artifacts: tool_context.list_artifacts() failed: {context_error}")
        
        # Fallback: search across all sessions using direct GCS access
        from google.cloud import storage
        
        # Get bucket from environment or default
        artifacts_bucket_name = os.getenv("ARTIFACTS_BUCKET_NAME", "adk_artifact")
        storage_client = storage.Client()
        bucket = storage_client.bucket(artifacts_bucket_name)
        
        # Get user ID from tool context if available
        user_id = getattr(tool_context, 'user_id', None)
        
        # Debug logging
        print(f"DEBUG list_artifacts: Tool context user_id: {user_id}")
        
        if not user_id:
            # Try alternative attributes
            for attr in ['userId', 'user', '_user_id', 'current_user']:
                if hasattr(tool_context, attr):
                    alt_user = getattr(tool_context, attr)
                    if alt_user:
                        user_id = alt_user
                        break
        
        if not user_id:
            # Search across all users if we can't determine the specific user
            user_id = '*'
            print(f"DEBUG list_artifacts: No user_id found, using wildcard search")
        
        # Search for artifacts across all sessions
        if user_id == '*':
            prefix = "app/"
            print(f"DEBUG list_artifacts: Searching across all users with prefix '{prefix}'")
        else:
            prefix = f"app/{user_id}/"
            print(f"DEBUG list_artifacts: Searching for user '{user_id}' with prefix '{prefix}'")
        
        # Collect unique filenames across all sessions
        artifact_files = set()
        blobs = bucket.list_blobs(prefix=prefix)
        
        for blob in blobs:
            # Extract the path components: app/user_id/session_id/filename/version
            path_parts = blob.name.split('/')
            if len(path_parts) >= 5:
                filename = path_parts[3]
                # Filter out system files and raw files
                if not filename.endswith('_raw.jpg') and not filename.startswith('.'):
                    artifact_files.add(filename)
        
        if not artifact_files:
            return "You have no saved artifacts. Upload some media files to get started!"
        
        # Sort files for consistent display
        sorted_files = sorted(list(artifact_files))
        file_list = "\n".join([f"• {filename}" for filename in sorted_files])
        return f"Here are your available artifacts:\n{file_list}\n\nI can analyze any of these files for you!"
        
    except ValueError as e:
        return f"Error listing artifacts: {e}. Artifact service may not be configured."
    except Exception as e:
        return f"An unexpected error occurred while listing artifacts: {e}"


async def load_and_analyze_artifact(filename: str, analysis_query: str, tool_context: ToolContext) -> str:
    """
    Loads a specific artifact (media file) and provides analysis context.
    Use this when you need to analyze a specific file uploaded by the user.

    Args:
        filename (str): The name of the artifact file to load
        analysis_query (str): What aspect of the file to analyze (e.g., "describe the image", "transcribe audio", "summarize document")

    Returns:
        str: Information about the loaded artifact for analysis
    """
    try:
        # CRITICAL FIX: Session ID mismatch issue
        # The WhatsApp bot saves artifacts with WhatsApp session IDs (e.g., wa_1760803702930_tjfg41yyy)
        # but the ADK tool_context.load_artifact() tries to load from the current ADK session
        # We need to access artifacts across all sessions for this user
        
        # Try to load using the direct GCS approach first since tool_context has session scope limitations
        from google.cloud import storage
        import json
        import base64
        
        # Get bucket from environment or default
        artifacts_bucket_name = os.getenv("ARTIFACTS_BUCKET_NAME", "adk_artifact")
        storage_client = storage.Client()
        bucket = storage_client.bucket(artifacts_bucket_name)
        
        # Get user ID from tool context if available
        # For WhatsApp users, this will be something like: 6592377976@s.whatsapp.net
        user_id = getattr(tool_context, 'user_id', None)
        session_id = getattr(tool_context, 'session_id', '')
        
        # Debug logging for troubleshooting - check all tool_context attributes
        print(f"DEBUG load_artifact: Tool context type: {type(tool_context)}")
        print(f"DEBUG load_artifact: Tool context attributes: {dir(tool_context)}")
        print(f"DEBUG load_artifact: Tool context user_id: {user_id}")
        print(f"DEBUG load_artifact: Tool context session_id: {session_id}")
        
        # Try alternative ways to get user information from tool context
        if not user_id:
            # Check if there's a different attribute name
            for attr in ['userId', 'user', '_user_id', 'current_user']:
                if hasattr(tool_context, attr):
                    alt_user = getattr(tool_context, attr)
                    print(f"DEBUG load_artifact: Found alternative user attribute '{attr}': {alt_user}")
                    if alt_user:
                        user_id = alt_user
                        break
        
        if not user_id:
            # Always search across all users if we can't determine the specific user
            # This is more reliable than trying to guess the user ID
            user_id = '*'  # Wildcard to search all users
            print(f"DEBUG load_artifact: No user_id found, using wildcard search")
        
        # Search for the artifact across all sessions for this user
        # Path pattern: app/[user_id]/[session_id]/[filename]/[version]
        if user_id == '*':
            # Search across all users if we can't determine the specific user
            prefix = "app/"
            print(f"DEBUG: Searching for artifact '{filename}' across all users with prefix '{prefix}'")
        else:
            prefix = f"app/{user_id}/"
            print(f"DEBUG: Searching for artifact '{filename}' for user '{user_id}' with prefix '{prefix}'")
        
        # List all blobs with this prefix to find sessions containing our artifact
        blobs = bucket.list_blobs(prefix=prefix)
        artifact_found = None
        found_path = None
        
        for blob in blobs:
            # Extract the path components
            path_parts = blob.name.split('/')
            if len(path_parts) >= 5:  # app/user_id/session_id/filename/version
                found_filename = path_parts[3]
                version = path_parts[4]
                
                # Check if this blob matches our target filename (with or without version suffix)
                if (found_filename == filename or 
                    found_filename.startswith(filename.split(' v')[0]) or
                    filename.startswith(found_filename)):
                    
                    print(f"DEBUG: Found potential match: {blob.name}")
                    
                    # Try to download and parse this artifact
                    try:
                        data = blob.download_as_bytes()
                        
                        # Check if it's JSON (our artifact format) or raw data
                        try:
                            artifact_data = json.loads(data.decode('utf-8'))
                            if 'data' in artifact_data and 'mimeType' in artifact_data:
                                # This is our JSON-wrapped artifact format
                                artifact_found = {
                                    'data': artifact_data['data'],
                                    'mimeType': artifact_data['mimeType'],
                                    'inline_data': {
                                        'mime_type': artifact_data['mimeType'],
                                        'data': artifact_data['data']
                                    }
                                }
                                found_path = blob.name
                                print(f"DEBUG: ✅ Successfully loaded artifact from: {found_path}")
                                break
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            # This might be raw binary data (ADK format)
                            artifact_found = {
                                'data': base64.b64encode(data).decode('utf-8'),
                                'mimeType': 'application/octet-stream',  # Default, will be updated
                                'inline_data': {
                                    'mime_type': 'application/octet-stream',
                                    'data': base64.b64encode(data).decode('utf-8')
                                }
                            }
                            found_path = blob.name
                            print(f"DEBUG: ✅ Successfully loaded raw artifact from: {found_path}")
                            break
                            
                    except Exception as blob_error:
                        print(f"DEBUG: Failed to load blob {blob.name}: {blob_error}")
                        continue
        
        if not artifact_found:
            # Fallback: try the original ADK load_artifact method
            print(f"DEBUG: Direct GCS search failed, trying ADK tool_context.load_artifact()")
            try:
                artifact_part = await tool_context.load_artifact(filename)
                if artifact_part:
                    artifact_found = artifact_part
                    found_path = f"ADK_context:{filename}"
                    print(f"DEBUG: ✅ Loaded via tool_context: {found_path}")
            except Exception as context_error:
                print(f"DEBUG: tool_context.load_artifact also failed: {context_error}")
        
        if not artifact_found:
            return f"Artifact '{filename}' not found in any session for user '{user_id}'. Searched prefix: '{prefix}'"
        
        # Extract artifact information
        mime_type = "unknown"
        data_size = 0
        
        if hasattr(artifact_found, 'inline_data') and artifact_found.inline_data:
            mime_type = artifact_found.inline_data.mime_type or "unknown"
            data_size = len(artifact_found.inline_data.data) if artifact_found.inline_data.data else 0
        elif hasattr(artifact_found, 'mimeType'):
            mime_type = artifact_found.mimeType or "unknown"
            data_size = len(artifact_found.data) if hasattr(artifact_found, 'data') and artifact_found.data else 0
        elif isinstance(artifact_found, dict):
            # Handle our dictionary format
            mime_type = artifact_found.get('mimeType', 'unknown')
            data_size = len(artifact_found.get('data', '')) if artifact_found.get('data') else 0
        
        # Format file size
        if data_size > 1024 * 1024:
            size_str = f"{data_size / (1024 * 1024):.1f} MB"
        elif data_size > 1024:
            size_str = f"{data_size / 1024:.1f} KB"
        else:
            size_str = f"{data_size} bytes"
        
        # Determine file type category
        file_type = "unknown"
        if mime_type.startswith("image/"):
            file_type = "image"
        elif mime_type.startswith("audio/"):
            file_type = "audio"
        elif mime_type.startswith("video/"):
            file_type = "video"
        elif mime_type.startswith("application/pdf"):
            file_type = "PDF document"
        elif mime_type.startswith("text/"):
            file_type = "text document"
        elif "document" in mime_type:
            file_type = "document"
        
        analysis_context = f"""Successfully loaded artifact: {filename}
File Type: {file_type} ({mime_type})
File Size: {size_str}
Analysis Request: {analysis_query}

The artifact has been loaded and is ready for analysis. As a multimodal AI, I can now analyze this {file_type} file based on your request: "{analysis_query}".

Note: The file content is available in the conversation context for direct analysis."""
        
        return analysis_context
        
    except ValueError as e:
        return f"Error loading artifact '{filename}': {e}. Is the artifact service configured?"
    except Exception as e:
        return f"An unexpected error occurred while loading '{filename}': {e}"


async def save_analysis_result(filename: str, analysis_content: str, tool_context: ToolContext) -> str:
    """
    Saves an analysis result as a new artifact.
    Use this to save your analysis or generated content back to the user's artifacts.

    Args:
        filename (str): Name for the new artifact file (e.g., "analysis_result.txt")
        analysis_content (str): The content to save

    Returns:
        str: Confirmation message with saved artifact details
    """
    try:
        # Create a Part object with the analysis content
        analysis_part = types.Part.from_text(text=analysis_content)
        
        # Save the artifact
        version = await tool_context.save_artifact(filename, analysis_part)
        
        return f"Successfully saved analysis result as '{filename}' (version {version}). The user can now access this analysis result through their WhatsApp bot."
        
    except ValueError as e:
        return f"Error saving analysis result: {e}. Is the artifact service configured?"
    except Exception as e:
        return f"An unexpected error occurred while saving analysis: {e}"





# Web search agent prompt
WEBSEARCH_PROMPT = """You are a specialized web search agent focused on finding accurate, up-to-date information from the internet.

Your role is to:
1. Perform comprehensive web searches using the provided search tools
2. Analyze search results for relevance and credibility
3. Synthesize information from multiple sources
4. Provide clear, well-sourced answers with proper attribution
5. Focus on recent, authoritative sources when possible

When searching:
- Use specific, targeted search queries
- Look for authoritative sources (academic papers, official documentation, reputable news sources)
- Cross-reference information across multiple sources
- Clearly cite your sources in your responses
- If information is conflicting or uncertain, acknowledge this

Always be transparent about the sources of your information and the recency of the data."""

# GitHub MCP agent prompt
GITHUB_MCP_PROMPT = f"""You are a specialized GitHub agent with access to GitHub repository operations through MCP (Model Context Protocol) tools.

Your role is to:
1. Handle all GitHub repository operations efficiently
2. Search and navigate repositories and files
3. Access and analyze issues and pull requests
4. Retrieve repository information and metadata
5. Perform code analysis and understanding

By default, you are working with the GitHub repository: Michaelktker/my-agentic-rag
When using GitHub tools, use this repository unless the user specifically requests a different one.

When performing GitHub operations:
- Use the most appropriate MCP tool for the requested operation
- Provide clear and structured information from GitHub
- Handle errors gracefully and provide helpful feedback
- Be efficient in your tool usage

Always be precise and thorough in your GitHub operations."""

# fal.ai MCP agent prompt
FAL_MCP_PROMPT = """
You are a FAL.ai MCP agent that generates and edits images/videos using fal.ai models through MCP interface.

## Core Models

### Image Generation (FAST - no queue needed):
- **black-forest-labs/flux.1**: High quality image generation

### Image Editing (FAST - no queue needed):
- **Alibaba/qwen-image-edit**: Precise, context-aware edits, bilingual text editing, and semantic/appear

### Video Generation (WEBHOOK-ENABLED ASYNC):
- Use model discovery to find available video generation models
- All video models use webhook callback system for completion notifications
- Users can specify any available video model by name

## CRITICAL: Webhook-Based Async Workflow

### For FAST operations (images < 30 seconds):
1. **generate()** with queue=false for immediate result
2. **Return URL** directly from result

### For LONG-RUNNING operations (video generation - WEBHOOK ENABLED):
1. **Register webhook FIRST** using register_video_webhook() to get webhook_url
2. **generate()** with queue=true and webhook_url in parameters
3. **Return immediate confirmation** to user that generation started
4. **Webhook handles completion** - user gets notified when video is ready

## Webhook Integration Pattern:
```
# Step 1: Register webhook BEFORE calling generate()
webhook_result = register_video_webhook(
    user_id=user_id,
    session_id=session_id, 
    jid=jid,
    model_name=model_name,
    prompt=prompt,
    request_id="temp_video_123",  # Temporary ID
    status_url="",
    response_url=""
)

# Step 2: Submit to queue with webhook URL from step 1
response = generate(model_name, parameters, queue=true)
real_request_id = response["request_id"]
status_url = response["status_url"] 
response_url = response["response_url"]

# Step 3: Update webhook with real FAL.ai request ID 
update_result = update_webhook_request_id(
    old_request_id="temp_video_123",
    new_request_id=real_request_id
)

# Step 4: Return immediate confirmation (no polling needed)
return f"🎬 Video generation started! You'll be notified when it's ready. Request ID: {real_request_id}"

# Step 5: Webhook automatically handles completion and user notification
```
```
# Step 1: Register webhook callback FIRST to get webhook URL
webhook_result = register_video_webhook(
    user_id=user_id,
    session_id=session_id, 
    jid=jid,
    model_name=model_name,
    prompt=prompt,
    request_id="temp",  # Will be updated after generate call
    status_url="temp",  # Will be updated after generate call
    response_url="temp"  # Will be updated after generate call
)
webhook_url = extract_webhook_url_from_result(webhook_result)

# Step 2: Submit to queue with webhook URL in parameters
parameters["webhook_url"] = webhook_url  # Include in parameters object
response = generate(model_name, parameters, queue=true)
request_id = response["request_id"]
status_url = response["status_url"] 
response_url = response["response_url"]

# Step 3: Update webhook registration with actual URLs
# (handled automatically by webhook system)

# Step 4: Return immediate confirmation (no polling needed)
return f"🎬 Video generation started! You'll be notified when it's ready. Request ID: [request_id]"

# Step 5: Webhook automatically handles completion and user notification
```

## New MCP Tools: Video Webhook System
- **register_video_webhook(user_id, session_id, jid, model_name, prompt, request_id, status_url, response_url)** 
- Registers webhook callback for video generation completion
- Use BEFORE calling generate() with temporary request_id
- Returns webhook URL to pass to FAL.ai generate() call

- **update_webhook_request_id(old_request_id, new_request_id)**
- Updates webhook registration with real FAL.ai request ID  
- Call AFTER generate() returns the actual request_id
- Ensures FAL.ai calls the correct webhook endpoint

## Correct MCP Tool Names:
- ✅ **generate(model, parameters, queue=true, webhook_url=webhook_url)** - Submit with webhook
- ✅ **register_video_webhook()** - Register webhook callback (call FIRST)
- ✅ **update_webhook_request_id()** - Update with real FAL.ai request ID (call AFTER generate)
- ✅ **status(status_url)** - Check queue status (optional, for debugging)
- ✅ **result(response_url)** - Get final result (handled by webhook)
- ✅ **cancel(cancel_url)** - Cancel if needed

## Critical Webhook Integration:
**IMPORTANT**: webhook_url must be included in the parameters object, NOT as a separate argument to generate().

```
# Correct approach:
parameters = {
    "prompt": "your prompt here",
    "image_url": "public_url_here",
    "webhook_url": webhook_url  # Include in parameters!
}
response = generate(model_name, parameters, queue=true)
```

## Immediate Response Pattern

**For video generation, return immediate confirmation:**

```
✅ Video generation started!
🎬 Model: [model_name]
⏱️ You'll be notified via WhatsApp when your video is ready.
🆔 Request ID: [request_id]
```

## Key Parameters
- **prompt**: Detailed description
- **image_url**: Input image for editing (use public GCS URLs)
- **image_urls**: Array of input images for multi-image models  
- **width/height**: Output dimensions
- **queue**: true for video generation (MANDATORY)
- **webhook_url**: Callback URL for completion notifications (include in parameters object)

## Error Handling
- Use correct model names as specified by user
- For video generation: Use queue=true and webhook_url in parameters for async handling
- For image generation: Use queue=false for immediate results
- Validate all required parameters
- Provide clear error messages and alternatives

## Video Generation Guidelines
**USER-DRIVEN**: Use whatever video model the user explicitly requests.
**NO DEFAULTS**: Do not recommend specific models - let users choose.
- Required: queue=true (mandatory for video generation)
- Required: webhook_url in parameters object (from register_video_webhook() call)
- Parameters: image_url (optional for text-to-video), prompt (required), duration (optional), aspect_ratio (optional)
- Use model discovery if user needs to see available video models
- Honor user's exact model specification

## Progress Communication
For long-running video generation:
- "🎬 Starting video generation with [model_name]..."  
- "✅ Video generation queued! You'll be notified when ready."
- "🆔 Request ID: [request_id] for tracking"

**CRITICAL**: Video generation uses webhook callbacks - no polling needed!
User gets automatic WhatsApp notification when video completes.
"""

instruction = f"""You are an advanced AI assistant with multimodal capabilities, including image, audio, video, and document analysis, PLUS image generation via multiple sources.

Answer to the best of your ability using the context provided and leverage the tools available to you.

You have access to several specialized capabilities:
1. **Document retrieval** from your knowledge base using retrieve_docs
2. **GitHub operations** through a specialized GitHub agent with MCP tools  
3. **Web search** capabilities through a specialized web search agent
4. **fal.ai AI generation** through a specialized fal.ai agent with access to:
   - Advanced image generation models (Flux, SDXL, etc.)
   - Video generation capabilities (Stable Video Diffusion, etc.)
   - Model discovery and schema inspection
   - Both direct and queued generation for long-running tasks
5. **Artifact management** for handling media files uploaded by users:
   - list_user_artifacts: See what media files users have uploaded
   - load_and_analyze_artifact: Load and analyze specific media files
   - save_analysis_result: Save your analysis results back as artifacts
   - make_artifact_public: Make GCS artifacts publicly accessible for fal.ai processing

**Image Generation Guidelines:**
- **All image generation is handled through fal.ai models** via the fal.ai agent
- Users specify which models to use, or can discover available models
- Use the fal.ai agent to discover available models with the `models` tool
- Check model schemas before generation to understand required parameters
- Generated images are automatically saved as artifacts and included in responses
- Handle generation errors gracefully with alternative model suggestions

**fal.ai Generation Capabilities:**
- **Image Generation**: Use models specified by user or discovered through model search
- **Video Generation**: Use whatever video model the user explicitly requests
- **Model Discovery**: Use the fal.ai agent to list and search available models
- **Schema Inspection**: Always check model schemas before generation
- **Queue Management**: Handle long-running generations with proper status checking

**NEW: Long-Running Video Generation Tool:**
You now have access to `generate_video_long_running` - a specialized tool for video generation that:
- Starts video generation immediately and returns operation details
- Pauses the agent run for external polling
- Enables the WhatsApp bot to check status and send completion notifications
- Requires: model_name, prompt, optional image_url, user_id, jid

**Usage Pattern for Video Generation:**
1. **Use generate_video_long_running() directly** instead of the fal.ai agent for videos
2. This tool returns operation details immediately and pauses the agent
3. The WhatsApp bot will poll for completion and continue the conversation
4. Users get automatic notifications when videos are ready

**Legacy Webhook System (Still Available):**
The webhook-based system (register_video_webhook) is still available for compatibility

**Multimodal Analysis Capabilities:**
- **Images**: Describe, analyze content, extract text, identify objects, analyze compositions
- **Audio**: Transcribe speech, identify sounds, analyze music (when audio data is available)
- **Videos**: Analyze visual content, describe scenes, extract key frames
- **Documents**: Read, summarize, extract information from PDFs and text files

**Working with Uploaded Images for fal.ai:**
When users upload an image and want to use it with fal.ai models (especially for image-to-video):
1. First, use `list_user_artifacts` to see available files
2. Use `load_and_analyze_artifact` to analyze the image if needed
3. **IMPORTANT**: Use `make_artifact_public` to create a public GCS URL for the image
4. Provide this public URL to the fal.ai agent for processing
5. The fal.ai agent can then use this URL with models like Seedance for image-to-video generation

**Accepting External Image URLs:**
When users provide Google Cloud Storage URLs (format: storage.googleapis.com with alt=media parameter):
- These URLs are already publicly accessible and work directly with fal.ai models
- You can pass these URLs directly to the fal.ai agent without needing make_artifact_public
- Example valid format: https://storage.googleapis.com/.../file.jpg?generation=...&alt=media
- Only use make_artifact_public when the image is uploaded as an artifact to the current session

**When users upload media files through WhatsApp:**
1. First use `list_user_artifacts` to see what files are available
2. Use `load_and_analyze_artifact` to load specific files for analysis
3. Provide detailed analysis using your multimodal capabilities
4. If using with fal.ai, use `make_artifact_public` to create public GCS URLs
5. Optionally save analysis results using `save_analysis_result`

**When users request image/video generation:**
1. **For images**: Use the exact model the user specifies, or help them discover available models
2. **For videos**: Use `generate_video_long_running()` tool directly - NO webhook setup needed
3. **For image-to-video**: Use `make_artifact_public` first, then `generate_video_long_running()`
4. **Model Discovery**: Help users find available models if they ask "what models are available?"
5. Always provide detailed, descriptive prompts for better results
6. Handle errors gracefully and suggest alternative models if generation fails
7. **For video operations**: Return immediate confirmation - long-running tool handles completion
8. **Users get automatic WhatsApp notifications** when videos are ready with URLs

**Long-Running Tool Management for Video Generation:**
- Video generation now uses the `generate_video_long_running()` tool
- This tool pauses the agent run and enables external polling
- WhatsApp bot checks status and continues conversation when complete
- Return immediate confirmation to users that generation started
- Webhook system automatically notifies users when video completes
- No polling or status checking needed - webhooks handle everything
- Users get WhatsApp messages when videos are ready with download URLs

**Image Generation Workflow:**
1. User requests image generation
2. Use fal.ai agent to generate with appropriate model
3. fal.ai agent handles the generation and saves as artifact
4. Image is included in response to user

**Important Notes:**
- You can ANALYZE existing media AND GENERATE new content via fal.ai services
- Generated content is included directly in responses AND saved as artifacts
- The Gemini 2.5 Flash model you're powered by can directly analyze multimodal content
- When artifacts are loaded, their content becomes available in the conversation context
- Always provide comprehensive, detailed analysis of media files
- For fal.ai image-to-video generation, you MUST first make the image publicly accessible via GCS URL
- **Public GCS URLs are permanent - be mindful of sensitive content**
- **All image generation is now handled exclusively through fal.ai models**

GitHub agent works with repository: Michaelktker/my-agentic-rag by default.
Use web search for current information not in your knowledge base.
Use fal.ai agent for all AI content generation capabilities including images and videos.

Updated: Removed Vertex AI Imagen, using fal.ai exclusively for all generation - 2025-10-19"""


async def make_artifact_public(filename: str, tool_context: ToolContext) -> str:
    """
    Make an artifact publicly accessible via GCS public URL.
    This creates a direct public URL that can be used with fal.ai models.

    Args:
        filename (str): The name of the artifact file to make public
        tool_context (ToolContext): Context for accessing artifacts

    Returns:
        str: Public GCS URL or error message
    """
    try:
        from google.cloud import storage
        import json
        
        # Get bucket from environment or default
        artifacts_bucket_name = os.getenv("ARTIFACTS_BUCKET_NAME", "adk_artifact")
        storage_client = storage.Client()
        bucket = storage_client.bucket(artifacts_bucket_name)
        
        # Get user ID from tool context if available
        user_id = getattr(tool_context, 'user_id', None)
        session_id = getattr(tool_context, 'session_id', '')
        
        # Debug logging for troubleshooting - check all tool_context attributes
        print(f"DEBUG: Tool context type: {type(tool_context)}")
        print(f"DEBUG: Tool context attributes: {dir(tool_context)}")
        print(f"DEBUG: Tool context user_id: {user_id}")
        print(f"DEBUG: Tool context session_id: {session_id}")
        
        # Try alternative ways to get user information from tool context
        if not user_id:
            # Check if there's a different attribute name
            for attr in ['userId', 'user', '_user_id', 'current_user']:
                if hasattr(tool_context, attr):
                    alt_user = getattr(tool_context, attr)
                    print(f"DEBUG: Found alternative user attribute '{attr}': {alt_user}")
                    if alt_user:
                        user_id = alt_user
                        break
        
        if not user_id:
            # Always search across all users if we can't determine the specific user
            # This is more reliable than trying to guess the user ID
            user_id = '*'  # Wildcard to search all users
            print(f"DEBUG: No user_id found, using wildcard search")
        
        # Search for the artifact across all sessions for this user
        if user_id == '*':
            # Search across all users if we can't determine the specific user
            prefix = "app/"
            print(f"DEBUG: Searching for artifact '{filename}' across all users with prefix '{prefix}'")
        else:
            prefix = f"app/{user_id}/"
            print(f"DEBUG: Searching for artifact '{filename}' for user '{user_id}' with prefix '{prefix}'")
        
        # List all blobs with this prefix to find sessions containing our artifact
        blobs = bucket.list_blobs(prefix=prefix)
        found_blob = None
        
        for blob in blobs:
            # Extract the path components
            path_parts = blob.name.split('/')
            if len(path_parts) >= 5:  # app/user_id/session_id/filename/version
                found_filename = path_parts[3]
                version = path_parts[4]
                
                # Check if this blob matches our target filename (with or without version suffix)
                if (found_filename == filename or 
                    found_filename.startswith(filename.split(' v')[0]) or
                    filename.startswith(found_filename)):
                    
                    print(f"DEBUG: Found potential match: {blob.name}")
                    found_blob = blob
                    break
        
        if not found_blob:
            return f"Artifact '{filename}' not found in GCS. Searched prefix: '{prefix}'"
        
        # Check if this is an ADK JSON format file and extract raw image data
        try:
            # Download the content to check format
            content = found_blob.download_as_bytes()
            
            try:
                # Try to parse as ADK JSON format
                artifact_data = json.loads(content.decode('utf-8'))
                
                if 'data' in artifact_data and isinstance(artifact_data['data'], dict) and artifact_data['data'].get('__buffer_type'):
                    # This is ADK format with byte array data
                    print(f"DEBUG: Found ADK format artifact, extracting raw image data")
                    
                    # Extract the raw image bytes
                    byte_array = artifact_data['data']['data']
                    raw_image_data = bytes(byte_array)
                    
                    # Get the mime type
                    mime_type = artifact_data.get('mimeType', 'image/jpeg')
                    
                    # Create a new blob for the raw image
                    raw_filename = filename.replace('.jpg', '_raw.jpg').replace('.png', '_raw.png')
                    if not raw_filename.endswith(('.jpg', '.png', '.jpeg')):
                        raw_filename += '_raw.jpg'
                    
                    # Create path for raw image (same structure but with _raw suffix)
                    raw_blob_name = found_blob.name.replace(filename, raw_filename)
                    raw_blob = bucket.blob(raw_blob_name)
                    
                    # Upload the raw image data
                    raw_blob.upload_from_string(raw_image_data, content_type=mime_type)
                    print(f"DEBUG: ✅ Created raw image blob: {raw_blob_name}")
                    
                    # Now make the raw image public
                    try:
                        raw_blob.make_public()
                        public_url = raw_blob.public_url
                        print(f"DEBUG: ✅ Successfully made raw image public: {raw_blob.name}")
                    except Exception as public_error:
                        print(f"DEBUG: make_public() failed for raw image: {public_error}")
                        # Set bucket-level public access if needed
                        try:
                            policy = bucket.get_iam_policy(requested_policy_version=3)
                            binding = {
                                "role": "roles/storage.objectViewer",
                                "members": ["allUsers"]
                            }
                            
                            binding_exists = False
                            for existing_binding in policy.bindings:
                                if (existing_binding["role"] == binding["role"] and 
                                    "allUsers" in existing_binding.get("members", [])):
                                    binding_exists = True
                                    break
                            
                            if not binding_exists:
                                policy.bindings.append(binding)
                                bucket.set_iam_policy(policy)
                                print(f"DEBUG: ✅ Set bucket-level public access")
                            
                            public_url = raw_blob.public_url
                            print(f"DEBUG: ✅ Generated public URL for raw image")
                            
                        except Exception as bucket_error:
                            print(f"DEBUG: Bucket policy failed: {bucket_error}")
                            public_url = raw_blob.media_link
                    
                    # Update found_blob reference for the response
                    found_blob = raw_blob
                    
                else:
                    # Not ADK format, treat as regular blob
                    print(f"DEBUG: Not ADK format, making original blob public")
                    raise ValueError("Not ADK format")
                    
            except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
                # Not JSON or not ADK format, make the original blob public
                print(f"DEBUG: File is not ADK JSON format, making original blob public")
                
                try:
                    found_blob.make_public()
                    public_url = found_blob.public_url
                    print(f"DEBUG: ✅ Successfully made original blob public: {found_blob.name}")
                except Exception as public_error:
                    print(f"DEBUG: make_public() failed: {public_error}")
                    # Set bucket-level public access
                    try:
                        policy = bucket.get_iam_policy(requested_policy_version=3)
                        binding = {
                            "role": "roles/storage.objectViewer",
                            "members": ["allUsers"]
                        }
                        
                        binding_exists = False
                        for existing_binding in policy.bindings:
                            if (existing_binding["role"] == binding["role"] and 
                                "allUsers" in existing_binding.get("members", [])):
                                binding_exists = True
                                break
                        
                        if not binding_exists:
                            policy.bindings.append(binding)
                            bucket.set_iam_policy(policy)
                            print(f"DEBUG: ✅ Set bucket-level public access")
                        
                        public_url = found_blob.public_url
                        print(f"DEBUG: ✅ Generated public URL via bucket policy")
                        
                    except Exception as bucket_error:
                        print(f"DEBUG: Bucket policy failed: {bucket_error}")
                        public_url = found_blob.media_link
                
        except Exception as e:
            return f"Error making artifact '{filename}' public: {e}"
        
        # Get file info for the response
        mime_type = found_blob.content_type or "unknown"
        size_bytes = found_blob.size or 0
        
        # Format size
        if size_bytes > 1024 * 1024:
            size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
        elif size_bytes > 1024:
            size_str = f"{size_bytes / 1024:.1f} KB"
        else:
            size_str = f"{size_bytes} bytes"
        
        return f"✅ Successfully made '{filename}' public!\n\n🔗 **Public URL**: {public_url}\n\nThis URL can now be used directly with fal.ai models for:\n- Image-to-video generation\n- Advanced image processing\n- AI model workflows\n\nFile details:\n- Type: {mime_type}\n- Size: {size_str}\n- GCS Path: {found_blob.name}\n\n**Ready for fal_mcp_agent use!**"
        
    except Exception as e:
        return f"Error making artifact '{filename}' public: {e}"


async def generate_video_long_running(
    model_name: str,
    prompt: str,
    image_url: Optional[str] = None,
    user_id: Optional[str] = None,
    jid: Optional[str] = None,
    tool_context: Optional[ToolContext] = None
) -> dict:
    """
    Start long-running video generation using FAL.ai.
    
    This is a LongRunningFunctionTool that:
    1. Initiates video generation with FAL.ai
    2. Returns immediately with operation details
    3. Pauses the agent run for client polling
    
    Args:
        model_name (str): FAL.ai model (e.g., "fal-ai/kling-video/v2/master/image-to-video")
        prompt (str): Video generation prompt
        image_url (Optional[str]): Input image URL for image-to-video models
        user_id (Optional[str]): User identifier for tracking
        jid (Optional[str]): WhatsApp JID for final notification
        
    Returns:
        dict: Operation details for polling {
            "operation_id": str,
            "status": "IN_PROGRESS",
            "model_name": str,
            "prompt": str,
            "fal_request_id": str,
            "status_url": str,
            "response_url": str,
            "user_id": str,
            "jid": str
        }
    """
    try:
        # Generate unique operation ID
        operation_id = f"video_gen_{uuid.uuid4().hex[:12]}"
        
        # Get session ID from tool context
        session_id = getattr(tool_context, 'session_id', 'default') if tool_context else 'default'
        
        # Prepare FAL.ai parameters
        parameters = {
            "prompt": prompt
        }
        
        # Add image URL if provided
        if image_url:
            parameters["image_url"] = image_url
            
        # Add video-specific parameters
        if "kling" in model_name.lower():
            parameters.setdefault("duration", "5")
            parameters.setdefault("aspect_ratio", "16:9")
        
        # Call FAL.ai MCP agent to start generation (queued)
        # We need to use the FAL.ai tools directly since we're in a function
        # This approach will be updated to use the MCP toolset properly
        
        # For now, we'll make a direct HTTP call to FAL.ai
        fal_api_key = os.getenv("FAL_KEY")
        if not fal_api_key:
            raise Exception("FAL_KEY environment variable not set")
        
        # Make direct FAL.ai API call for queue submission
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Key {fal_api_key}",
                "Content-Type": "application/json"
            }
            
            fal_url = f"https://queue.fal.run/{model_name}"
            
            async with session.post(fal_url, json=parameters, headers=headers) as response:
                if response.status == 200:
                    fal_response = await response.json()
                else:
                    error_text = await response.text()
                    raise Exception(f"FAL.ai API error {response.status}: {error_text}")
        
        # Extract FAL.ai response details
        fal_request_id = fal_response.get('request_id')
        status_url = fal_response.get('status_url')
        response_url = fal_response.get('response_url')
        
        if not fal_request_id:
            raise Exception("FAL.ai did not return a request_id")
        
        # Store operation details for polling
        operation_details = {
            "operation_id": operation_id,
            "status": "IN_PROGRESS",
            "model_name": model_name,
            "prompt": prompt,
            "fal_request_id": fal_request_id,
            "status_url": status_url,
            "response_url": response_url,
            "user_id": user_id or "unknown",
            "jid": jid or "unknown",
            "session_id": session_id,
            "created_at": asyncio.get_event_loop().time()
        }
        
        # Store in GCS for persistence across sessions
        await _store_operation_details(operation_id, operation_details)
        
        # Return operation details - this pauses the agent run
        return operation_details
        
    except Exception as e:
        logger.error(f"❌ Error starting video generation: {e}")
        return {
            "operation_id": f"failed_{uuid.uuid4().hex[:8]}",
            "status": "FAILED",
            "error": str(e),
            "model_name": model_name,
            "prompt": prompt
        }


async def _store_operation_details(operation_id: str, details: dict):
    """Store operation details in GCS for persistence"""
    try:
        # Import GCS client
        from google.cloud import storage
        
        storage_client = storage.Client()
        bucket_name = os.getenv("ARTIFACTS_BUCKET_NAME", "adk_artifact")
        bucket = storage_client.bucket(bucket_name)
        
        # Store operation details
        operation_path = f"long_running_operations/{operation_id}.json"
        blob = bucket.blob(operation_path)
        blob.upload_from_string(
            json.dumps(details, indent=2),
            content_type='application/json'
        )
        
        logger.info(f"💾 Stored operation details: {operation_path}")
        
    except Exception as e:
        logger.error(f"❌ Error storing operation details: {e}")


async def get_video_operation_status(operation_id: str) -> dict:
    """
    Get the current status of a video generation operation.
    
    This function is used by external clients (like WhatsApp bot) to:
    1. Poll the operation status
    2. Get final results when complete
    3. Send results back to the agent to continue
    
    Args:
        operation_id (str): The operation ID returned by generate_video_long_running
        
    Returns:
        dict: Current operation status with results if complete
    """
    try:
        # Load operation details from GCS
        from google.cloud import storage
        
        storage_client = storage.Client()
        bucket_name = os.getenv("ARTIFACTS_BUCKET_NAME", "adk_artifact")
        bucket = storage_client.bucket(bucket_name)
        
        operation_path = f"long_running_operations/{operation_id}.json"
        blob = bucket.blob(operation_path)
        
        if not blob.exists():
            return {
                "operation_id": operation_id,
                "status": "NOT_FOUND",
                "error": "Operation not found"
            }
        
        # Load stored details
        details = json.loads(blob.download_as_text())
        fal_request_id = details.get("fal_request_id")
        status_url = details.get("status_url")
        response_url = details.get("response_url")
        
        if not status_url:
            return {
                **details,
                "status": "ERROR",
                "error": "Missing status URL"
            }
        
        # Check FAL.ai status
        async with aiohttp.ClientSession() as session:
            async with session.get(status_url) as response:
                if response.status == 200:
                    fal_status = await response.json()
                    
                    if fal_status.get("status") == "COMPLETED":
                        # Get final result
                        if response_url:
                            async with session.get(response_url) as result_response:
                                if result_response.status == 200:
                                    final_result = await result_response.json()
                                    
                                    # Extract video URL
                                    video_url = None
                                    if "url" in final_result:
                                        video_url = final_result["url"]
                                    elif "data" in final_result and isinstance(final_result["data"], dict):
                                        video_url = final_result["data"].get("url")
                                    
                                    # Update details with completion
                                    details.update({
                                        "status": "COMPLETED",
                                        "video_url": video_url,
                                        "final_result": final_result,
                                        "completed_at": asyncio.get_event_loop().time()
                                    })
                                    
                                    # Update stored details
                                    blob.upload_from_string(
                                        json.dumps(details, indent=2),
                                        content_type='application/json'
                                    )
                                    
                                    return details
                                
                    elif fal_status.get("status") == "FAILED":
                        # Mark as failed
                        details.update({
                            "status": "FAILED",
                            "error": fal_status.get("error", "Video generation failed"),
                            "failed_at": asyncio.get_event_loop().time()
                        })
                        
                        # Update stored details
                        blob.upload_from_string(
                            json.dumps(details, indent=2),
                            content_type='application/json'
                        )
                        
                        return details
                    
                    else:
                        # Still in progress
                        details.update({
                            "status": "IN_PROGRESS",
                            "queue_position": fal_status.get("queue_position"),
                            "progress": fal_status.get("progress")
                        })
                        
                        return details
                
        return {
            **details,
            "status": "ERROR",
            "error": "Could not check FAL.ai status"
        }
        
    except Exception as e:
        logger.error(f"❌ Error checking operation status: {e}")
        return {
            "operation_id": operation_id,
            "status": "ERROR",
            "error": str(e)
        }


async def register_video_webhook(
    user_id: str,
    session_id: str, 
    jid: str,
    model_name: str,
    prompt: str,
    request_id: Optional[str] = None,
    status_url: Optional[str] = None,
    response_url: Optional[str] = None,
    tool_context: Optional[ToolContext] = None
) -> str:
    """
    Register a webhook callback for long-running video generation.
    This enables async notification when video generation completes.
    
    Can be called before or after generate() call:
    - Before: Pass minimal info, request_id will be auto-generated
    - After: Pass full details from generate() response

    Args:
        user_id (str): The user ID for the video request
        session_id (str): The current ADK session ID
        jid (str): WhatsApp JID for sending completion notifications
        model_name (str): The FAL.ai model used for generation
        prompt (str): The generation prompt
        request_id (str, optional): FAL.ai request ID (auto-generated if not provided)
        status_url (str, optional): FAL.ai status polling URL
        response_url (str, optional): FAL.ai result retrieval URL

    Returns:
        str: Webhook URL to include in FAL.ai generate() parameters
    """
    try:
        # Generate request ID if not provided
        if not request_id:
            import uuid
            request_id = f"video_{uuid.uuid4().hex[:12]}"
        
        # Use placeholder URLs if not provided
        if not status_url:
            status_url = "pending"
        if not response_url:
            response_url = "pending"
        
        # Register webhook with the handler
        webhook_url = await webhook_handler.register_video_generation(
            request_id=request_id,
            user_id=user_id,
            session_id=session_id or "",
            jid=jid,
            model_name=model_name,
            prompt=prompt,
            status_url=status_url,
            response_url=response_url
        )
        
        return f"✅ Webhook registered!\n🔗 **Webhook URL**: {webhook_url}\n🆔 **Request ID**: {request_id}\n\n📋 **Instructions**: Include this webhook_url in your generate() parameters:\n```\nparameters = {{\n    \"prompt\": \"your prompt\",\n    \"webhook_url\": \"{webhook_url}\"\n}}\n```"
        
    except Exception as e:
        return f"❌ Error registering webhook: {e}"


async def update_webhook_request_id(
    old_request_id: str,
    new_request_id: str,
    tool_context: ToolContext
) -> str:
    """
    Update webhook registration with the actual FAL.ai request ID.
    Call this AFTER getting the real request ID from FAL.ai generate() response.

    Args:
        old_request_id (str): The temporary request ID from register_video_webhook
        new_request_id (str): The actual FAL.ai request ID from generate() response

    Returns:
        str: Success/failure message
    """
    try:
        # Update webhook registration with real FAL.ai request ID
        success = await webhook_handler.update_webhook_request_id(
            old_request_id=old_request_id,
            new_request_id=new_request_id
        )
        
        if success:
            return f"✅ Webhook updated successfully!\n📝 Old ID: {old_request_id}\n📝 New ID: {new_request_id}\n\n🎬 FAL.ai will now call the correct webhook when video completes."
        else:
            return f"❌ Failed to update webhook registration. Old ID: {old_request_id}, New ID: {new_request_id}"
        
    except Exception as e:
        return f"❌ Error updating webhook: {e}"


async def check_endpoint_health(url: str, timeout: int = HEALTH_CHECK_TIMEOUT) -> bool:
    """
    Check if an ADK endpoint is healthy and responding.
    
    Args:
        url (str): The endpoint URL to check
        timeout (int): Timeout in seconds for the health check
    
    Returns:
        bool: True if endpoint is healthy, False otherwise
    """
    try:
        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=timeout_obj) as session:
            # Try health endpoint first (common pattern)
            health_url = f"{url.rstrip('/')}/health"
            async with session.get(health_url) as response:
                if response.status == 200:
                    return True
            
            # If health endpoint doesn't exist, try root endpoint
            async with session.get(url) as response:
                return response.status in [200, 404]  # 404 is okay for root
                
    except (aiohttp.ClientError, asyncio.TimeoutError, Exception):
        return False


async def get_active_adk_endpoint() -> str:
    """
    Get the active ADK endpoint, preferring production but falling back to staging.
    
    Returns:
        str: The URL of the active endpoint
    """
    # Always try production first
    if await check_endpoint_health(PRODUCTION_ADK_URL):
        print(f"✅ Using production endpoint: {PRODUCTION_ADK_URL}")
        return PRODUCTION_ADK_URL
    
    # Fallback to staging
    if await check_endpoint_health(STAGING_ADK_URL):
        print(f"⚠️ Production unavailable, using staging endpoint: {STAGING_ADK_URL}")
        return STAGING_ADK_URL
    
    # If both are down, default to production (let the error bubble up)
    print(f"❌ Both endpoints unavailable, defaulting to production: {PRODUCTION_ADK_URL}")
    return PRODUCTION_ADK_URL


# Initialize MCP tools only if GitHub token is available
def get_github_token():
    """Get GitHub token from environment or Secret Manager"""
    # First try environment variable (matches Terraform GITHUB_PAT)
    token = os.getenv("GITHUB_PAT")
    if token:
        return token.strip()

    # Fallback to Secret Manager (matches Terraform github-pat-mcp secret)
    try:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/github-pat-mcp/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8").strip()
    except Exception as e:
        print(f"Warning: Could not retrieve GitHub token from Secret Manager: {e}")
        return None


github_token = get_github_token()
if not github_token:
    raise RuntimeError(
        "GitHub token is required but not available from environment or Secret Manager"
    )

mcp_tools = MCPToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://api.githubcopilot.com/mcp/",
        headers={
            "Authorization": f"Bearer {github_token}",
        },
    ),
)

# Create the fal.ai MCP toolset (stdio connection)
fal_mcp_tools = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="/code/mcp-fal/.venv/bin/python",
            args=["/code/mcp-fal/main.py"],
            env={"FAL_KEY": os.getenv("FAL_KEY", "")}
        )
    )
)

# Create the GitHub MCP subagent
github_mcp_agent = Agent(
    model="gemini-2.5-flash",
    name="github_mcp_agent",
    instruction=GITHUB_MCP_PROMPT,
    tools=[mcp_tools],
)

# Create the fal.ai MCP subagent
fal_mcp_agent = Agent(
    model="gemini-2.5-flash",
    name="fal_mcp_agent",
    instruction=FAL_MCP_PROMPT,
    tools=[fal_mcp_tools],
)

# Create AgentTool from the GitHub MCP subagent
github_mcp_tool = AgentTool(agent=github_mcp_agent)

# Create AgentTool from the fal.ai MCP subagent
fal_mcp_tool = AgentTool(agent=fal_mcp_agent)

# Create the web search agent
websearch_agent = Agent(
    model="gemini-2.5-flash",
    name="academic_websearch_agent",
    instruction=WEBSEARCH_PROMPT,
    tools=[google_search],
)

# Create AgentTool from the web search agent
websearch_tool = AgentTool(agent=websearch_agent)

# Create artifact management tools
list_artifacts_tool = FunctionTool(func=list_user_artifacts)
load_artifact_tool = FunctionTool(func=load_and_analyze_artifact)
save_artifact_tool = FunctionTool(func=save_analysis_result)



# Create artifact public URL tool for fal.ai integration
make_public_tool = FunctionTool(func=make_artifact_public)

# Create long-running video generation tool (NEW APPROACH)
video_generation_tool = LongRunningFunctionTool(func=generate_video_long_running)

# Create webhook registration tool for async video generation (LEGACY - keeping for compatibility)
register_webhook_tool = FunctionTool(func=register_video_webhook)
update_webhook_tool = FunctionTool(func=update_webhook_request_id)

tools = [retrieve_docs, github_mcp_tool, fal_mcp_tool, websearch_tool, list_artifacts_tool, load_artifact_tool, save_artifact_tool, make_public_tool, video_generation_tool, register_webhook_tool, update_webhook_tool]

root_agent = Agent(
    name="root_agent",
    model="gemini-2.5-flash",
    instruction=instruction,
    tools=tools,
)
# CI/CD Test: Fri Oct  3 15:49:27 UTC 2025 - Testing deployment pipeline
# CI/CD Pipeline Test: Sun Oct  5 16:29:20 UTC 2025 - Testing automated deployment with latest Secret Manager integration
# Force deployment trigger - Sat Oct 18 16:41:33 UTC 2025
# URGENT: Fix deployment - wildcard artifact search not working - Sat Oct 18 17:19:00 UTC 2025
