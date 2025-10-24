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
import json
import logging
import signal
import atexit
import time
import requests
from io import BytesIO
from typing import Optional

import google
import vertexai
from google.adk.agents import Agent
from google.adk.tools.mcp_tool import MCPToolset, StreamableHTTPConnectionParams, StdioConnectionParams
from mcp.client.stdio import StdioServerParameters
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from langchain_google_vertexai import VertexAIEmbeddings


from app.retrievers import get_compressor, get_retriever
from app.templates import format_docs

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
        available_files = await tool_context.list_artifacts()
        if available_files:
            file_list = "\n".join([f"• {filename}" for filename in available_files])
            return f"Here are your available artifacts:\n{file_list}\n\nI can analyze any of these files for you!"
        else:
            return "You have no saved artifacts. Upload some media files to get started!"
        
    except Exception as e:
        return f"Error listing artifacts: {e}. Artifact service may not be configured."


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
        # Load artifact using ADK tool context
        artifact_part = await tool_context.load_artifact(filename)
        
        if not artifact_part:
            return f"Artifact '{filename}' not found. Use list_user_artifacts to see available files."
        
        # Extract artifact information
        mime_type = "unknown"
        data_size = 0
        
        if hasattr(artifact_part, 'inline_data') and artifact_part.inline_data:
            mime_type = artifact_part.inline_data.mime_type or "unknown"
            data_size = len(artifact_part.inline_data.data) if artifact_part.inline_data.data else 0
        elif hasattr(artifact_part, 'mimeType'):
            mime_type = artifact_part.mimeType or "unknown"
            data_size = len(artifact_part.data) if hasattr(artifact_part, 'data') and artifact_part.data else 0
        elif isinstance(artifact_part, dict):
            # Handle dictionary format
            mime_type = artifact_part.get('mimeType', 'unknown')
            data_size = len(artifact_part.get('data', '')) if artifact_part.get('data') else 0
        
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
        
    except Exception as e:
        return f"Error loading artifact '{filename}': {e}. Use list_user_artifacts to see available files."


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

## CRITICAL: ALL OPERATIONS USE INTERNAL SYNCHRONOUS POLLING

### For ALL Image Generation, Image Editing, and Video Generation:
- **Use specialized tools**: `generate_image()`, `edit_image()`, `generate_video()`
- **These tools handle everything internally**: queue submission, polling, completion
- **Return final results synchronously** - no external polling needed
- **User gets complete results immediately** or error details

### Model Discovery and Selection:

#### **NEVER hardcode models** - Always let users choose:
- **Use `models()` tool** to list available models with pagination
- **Use `search()` tool** to find models by keywords
- **User specifies exact model** they want to use
- **No model recommendations** - present options and let user decide

#### **Model Discovery Workflow:**
1. **User asks for capability** (e.g., "generate an image", "edit a photo", "create a video")
2. **Ask user to specify model** or help them discover available models:
   - "Which model would you like to use?"
   - "Let me search for available [image/video/editing] models"
3. **Use search() or models()** to find relevant models
4. **Present options to user** with model names and descriptions
5. **User selects specific model** by name
6. **Use selected model** in generation call

#### **Example Model Discovery:**
```
User: "Generate an image of a cat"
Agent: "I can help generate an image! Let me find available image generation models for you."
Agent: Uses search("image generation") or models()
Agent: "Here are available image models: [list]. Which would you like to use?"
User: "Use flux-dev"
Agent: Uses generate_image(model="[user-specified-model]", prompt="cat", ...)
```

### **Model Categories** (discovered dynamically):

#### **Image Generation Models:**
- Use `search("image generation")` or `search("text to image")` 
- Common patterns: "flux", "sd", "dall-e", "midjourney" style models
- Let user choose from discovered options

#### **Image Editing Models:**
- Use `search("image editing")` or `search("image edit")`
- Common patterns: editing, inpainting, background removal, upscaling
- User selects based on their specific editing needs

#### **Video Generation Models:**
- Use `search("video generation")` or `search("text to video")`
- Common patterns: text-to-video, image-to-video models
- User chooses model based on their video generation requirements

## NEW: Specialized Generation Tools with Internal Polling

### `generate_image(model, prompt, width, height, **kwargs)`:
- **Complete image generation workflow** - queues request and polls until done
- **Returns final image result** or error details
- **No external polling needed** - handles everything internally
- **User gets immediate results** when tool completes

### `generate_video(model, prompt, image_url, **kwargs)`:
- **Complete video generation workflow** - queues request and polls until done
- **Returns final video result** or error details  
- **No external polling needed** - handles everything internally
- **User gets immediate results** when tool completes

### `edit_image(model, image_url, prompt, **kwargs)`:
- **Complete image editing workflow** - queues request and polls until done
- **Returns final edited image result** or error details
- **No external polling needed** - handles everything internally
- **User gets immediate results** when tool completes

## Lower-Level Tools (for advanced users):

### For Manual Queue Management:
- **`generate()`** - Start queued operations (returns status_url, response_url)
- **`poll_until_complete()`** - Manual polling tool
- **`status()`** and `result()`** - Individual status/result checking

## Dynamic Model Usage Pattern:
```
# WRONG - Don't hardcode models:
# result = generate_image(model="[hardcoded-model]", ...)

# RIGHT - User-driven model selection:
# 1. Discover models
models = search("image generation")
# 2. Present options to user
# 3. User selects model_name
# 4. Use selected model with specialized tool
result = generate_image(
    model=user_selected_model,
    prompt=prompt,
    **additional_params
)
```

## Model Parameter Discovery:
- **Use `schema(model_id)`** to get model-specific parameters
- **Show available parameters** to user when relevant
- **Let user specify** width, height, steps, guidance, etc.
- **Don't assume defaults** - ask user for important parameters

## Response Handling:
- **Specialized tools return complete results** - no additional polling
- **Include final URLs, metadata, and completion status**
- **Handle errors gracefully** with clear error messages
- **Return structured results** for easy parsing

## User Communication:
- **"Let me find available models for you..."**
- **"Here are the [type] models I found: [list]"**
- **"Which model would you like to use?"**
- **"I'll use [model_name] for your request"**
- **"Generation complete! Here's your result..."**

## Key Principles:
1. **USER-DRIVEN MODEL SELECTION** - Never choose for them
2. **DYNAMIC MODEL DISCOVERY** - Always use search/models tools
3. **NO HARDCODED MODELS** - Every model comes from user choice
4. **PRESENT OPTIONS** - Show what's available, let user decide
5. **SYNCHRONOUS OPERATION** - Return complete results, no external polling
6. **RESPECT USER PREFERENCES** - Use exactly what they specify
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
   - Image editing capabilities
   - Model discovery and schema inspection
   - **NEW: Synchronous generation** - all operations complete before returning
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
- **Generated images are returned synchronously** - no waiting required
- Handle generation errors gracefully with alternative model suggestions

**fal.ai Generation Capabilities:**
- **Image Generation**: Use models specified by user or discovered through model search
- **Video Generation**: Use whatever video model the user explicitly requests
- **Image Editing**: Use appropriate editing models for user requirements
- **Model Discovery**: Use the fal.ai agent to list and search available models
- **Schema Inspection**: Always check model schemas before generation
- **Synchronous Operation**: All generation completes before returning results

**NEW: Synchronous Generation System:**
The fal.ai agent now handles all generation internally with polling:
- **`generate_image()`** - Returns completed image generation results
- **`generate_video()`** - Returns completed video generation results
- **`edit_image()`** - Returns completed image editing results
- **All operations are synchronous** - results are available immediately
- **No external polling needed** - the MCP agent handles everything
- **Users get immediate feedback** when generation is complete

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
1. **For all generation**: Use the fal.ai agent with appropriate specialized tools
2. **Model Discovery**: Help users find available models if they ask "what models are available?"
3. **Synchronous Results**: All generation completes before responding to user
4. Always provide detailed, descriptive prompts for better results
5. Handle errors gracefully and suggest alternative models if generation fails
6. **Results include final URLs** and are ready for immediate use
7. **Generated content is also saved as artifacts** automatically

**Generation Workflow:**
1. User requests image/video generation
2. Use fal.ai agent to generate with appropriate model (synchronously)
3. fal.ai agent handles queue submission, polling, and result retrieval
4. Final result is returned to user with URLs and metadata
5. Generated content is automatically saved as artifacts

**Important Notes:**
- You can ANALYZE existing media AND GENERATE new content via fal.ai services
- **All generation is now synchronous** - no external polling or waiting
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

Updated: New synchronous polling architecture - fal.ai agent handles everything internally - 2025-10-19"""


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
            # User-based storage: all artifacts are in app/user_id/shared/
            prefix = f"app/{user_id}/shared/"
            print(f"DEBUG: Searching for artifact '{filename}' for user '{user_id}' with prefix '{prefix}'")
        
        # List all blobs with this prefix to find artifacts
        blobs = bucket.list_blobs(prefix=prefix)
        found_blob = None
        
        for blob in blobs:
            # Extract the path components: app/user_id/shared/filename
            path_parts = blob.name.split('/')
            if user_id == '*':
                # Path: app/user_id/shared/filename (4 parts minimum)
                if len(path_parts) >= 4 and len(path_parts) >= 3 and path_parts[2] == 'shared':
                    found_filename = path_parts[3]
                else:
                    continue
            else:
                # Path: app/user_id/shared/filename (4 parts exact for our prefix)
                if len(path_parts) >= 4:
                    found_filename = path_parts[3]
                else:
                    continue
                
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


def check_endpoint_health(url: str, timeout: int = HEALTH_CHECK_TIMEOUT) -> bool:
    """
    Check if an ADK endpoint is healthy and responding.
    
    Args:
        url (str): The endpoint URL to check
        timeout (int): Timeout in seconds for the health check
    
    Returns:
        bool: True if endpoint is healthy, False otherwise
    """
    try:
        # Try health endpoint first (common pattern)
        health_url = f"{url.rstrip('/')}/health"
        response = requests.get(health_url, timeout=timeout)
        if response.status_code == 200:
            return True
        
        # If health endpoint doesn't exist, try root endpoint
        response = requests.get(url, timeout=timeout)
        return response.status_code in [200, 404]  # 404 is okay for root
        
    except (requests.RequestException, Exception):
        return False


async def get_active_adk_endpoint() -> str:
    """
    Get the active ADK endpoint, preferring production but falling back to staging.
    
    Returns:
        str: The URL of the active endpoint
    """
    # Always try production first
    if check_endpoint_health(PRODUCTION_ADK_URL):
        print(f"✅ Using production endpoint: {PRODUCTION_ADK_URL}")
        return PRODUCTION_ADK_URL
    
    # Fallback to staging
    if check_endpoint_health(STAGING_ADK_URL):
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

# MCP Connection Manager for proper lifecycle management
import signal
import atexit
import logging
import time
from typing import Optional

class MCPHealthMonitor:
    """Monitor MCP connection health and handle reconnections"""
    
    def __init__(self, mcp_tools, name: str):
        self.mcp_tools = mcp_tools
        self.name = name
        self.last_health_check = None
        self.health_check_interval = 60  # seconds
        self._logger = logging.getLogger(__name__)
        
    def is_healthy(self) -> bool:
        """Quick health check without async operations"""
        try:
            # Simple check - if the toolset exists and has tools
            return self.mcp_tools is not None
        except Exception as e:
            self._logger.warning(f"{self.name} MCP health check failed: {e}")
            return False

class MCPConnectionManager:
    """Singleton manager for MCP connections to prevent recreation and resource leaks"""
    _fal_mcp_tools = None
    _github_mcp_tools = None
    _fal_health_monitor = None
    _github_health_monitor = None
    _logger = logging.getLogger(__name__)
    
    @classmethod
    def get_fal_mcp_tools(cls):
        """Get or create FAL MCP toolset (singleton pattern)"""
        if cls._fal_mcp_tools is None:
            cls._logger.info("Creating FAL MCP toolset...")
            mcp_fal_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mcp-fal", "main.py")
            cls._fal_mcp_tools = MCPToolset(
                connection_params=StdioConnectionParams(
                    server_params=StdioServerParameters(
                        command="python",
                        args=[mcp_fal_path],
                        env={"FAL_KEY": os.getenv("FAL_KEY", "")}
                    ),
                    timeout=300.0  # 5 minute timeout for MCP operations
                )
            )
            cls._fal_health_monitor = MCPHealthMonitor(cls._fal_mcp_tools, "FAL")
            cls._logger.info("FAL MCP toolset created successfully")
        return cls._fal_mcp_tools
    
    @classmethod
    def get_github_mcp_tools(cls):
        """Get or create GitHub MCP toolset (singleton pattern)"""
        if cls._github_mcp_tools is None:
            cls._logger.info("Creating GitHub MCP toolset...")
            cls._github_mcp_tools = mcp_tools  # Use existing mcp_tools
            cls._github_health_monitor = MCPHealthMonitor(cls._github_mcp_tools, "GitHub")
            cls._logger.info("GitHub MCP toolset created successfully")
        return cls._github_mcp_tools
    
    @classmethod
    def get_health_status(cls) -> dict:
        """Get health status of all MCP connections"""
        status = {}
        if cls._fal_health_monitor:
            status['fal'] = cls._fal_health_monitor.is_healthy()
        if cls._github_health_monitor:
            status['github'] = cls._github_health_monitor.is_healthy()
        return status
    
    @classmethod
    def cleanup_connections(cls):
        """Cleanup all MCP connections"""
        cls._logger.info("Cleaning up MCP connections...")
        try:
            if cls._fal_mcp_tools:
                # MCP toolsets don't have explicit close methods, but we can clear the reference
                cls._fal_mcp_tools = None
                cls._fal_health_monitor = None
                cls._logger.info("FAL MCP toolset cleaned up")
            if cls._github_mcp_tools:
                cls._github_mcp_tools = None
                cls._github_health_monitor = None
                cls._logger.info("GitHub MCP toolset cleaned up")
        except Exception as e:
            cls._logger.error(f"Error during MCP cleanup: {e}")

def setup_cleanup_handlers():
    """Setup proper cleanup handlers for graceful shutdown"""
    def cleanup_handler():
        MCPConnectionManager.cleanup_connections()
        
    # Register cleanup on normal exit
    atexit.register(cleanup_handler)
    
    # Register cleanup on signals
    def signal_handler(signum, frame):
        logging.getLogger(__name__).info(f"Received signal {signum}, cleaning up...")
        cleanup_handler()
        
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

# Setup cleanup handlers
setup_cleanup_handlers()

# Create the fal.ai MCP toolset using connection manager
fal_mcp_tools = MCPConnectionManager.get_fal_mcp_tools()

# Create the GitHub MCP subagent using connection manager
github_mcp_tools = MCPConnectionManager.get_github_mcp_tools()
github_mcp_agent = Agent(
    model="gemini-2.5-flash",
    name="github_mcp_agent",
    instruction=GITHUB_MCP_PROMPT,
    tools=[github_mcp_tools],
)

# Create the fal.ai MCP subagent
# Fixed **kwargs compatibility issue by removing problematic functions from generate.py
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

tools = [retrieve_docs, github_mcp_tool, fal_mcp_tool, websearch_tool, list_artifacts_tool, load_artifact_tool, save_artifact_tool, make_public_tool]

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
