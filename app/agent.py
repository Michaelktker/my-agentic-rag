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
import time
import re
from datetime import datetime
from io import BytesIO
from typing import Optional

import google
import vertexai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.mcp_tool import MCPToolset, StreamableHTTPConnectionParams, StdioConnectionParams
from mcp.client.stdio import StdioServerParameters
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from langchain_google_vertexai import VertexAIEmbeddings


def has_myker_mention(text: str) -> bool:
    """
    Check if the text contains a @Myker mention (case-insensitive).
    
    Args:
        text (str): The text to check for mentions
        
    Returns:
        bool: True if @Myker mention is found, False otherwise
    """
    if not text:
        return False
    
    # Use regex to find @Myker mentions (case-insensitive)
    pattern = r'@myker\b'
    return bool(re.search(pattern, text, re.IGNORECASE))


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


async def save_inline_media_as_artifact(
    filename: str,
    tool_context: ToolContext
) -> str:
    """
    Save inline_data from the current message as an artifact with the specified filename.
    This extracts media from inline_data in the conversation and stores it as an artifact.
    
    Args:
        filename (str): The filename to use when saving the artifact
        tool_context (ToolContext): Context for accessing current message and saving artifacts
        
    Returns:
        str: Success message with filename or error message
    """
    try:
        # Get the current invocation context to access the message
        invocation_context = getattr(tool_context, '_invocation_context', None)
        if not invocation_context:
            return "❌ Cannot access current message context to extract inline_data"
        
        # Try to get the user content which should contain the inline_data
        user_content = getattr(invocation_context, 'user_content', None)
        if not user_content or not hasattr(user_content, 'parts'):
            return "❌ Cannot access message parts to extract inline_data"
            
        # Look for inline_data in the message parts
        saved_count = 0
        for part in user_content.parts:
            if hasattr(part, 'inline_data') and part.inline_data:
                inline_data = part.inline_data
                
                # Extract the media data and MIME type
                if hasattr(inline_data, 'data') and hasattr(inline_data, 'mime_type'):
                    import base64
                    
                    # Create an artifact part with the inline_data
                    # The tool_context.save_artifact expects an artifact part, not raw data
                    mime_type = inline_data.mime_type
                    
                    # Save as artifact using tool_context - pass the inline_data directly
                    version = await tool_context.save_artifact(filename, inline_data)
                    saved_count += 1
                    
                    logger.info(f"Saved inline_data as artifact: {filename} (version: {version})")
                    
                    return f"✅ Successfully saved media as artifact: {filename} (MIME: {mime_type}, Version: {version})"
        
        if saved_count == 0:
            return "❌ No inline_data found in the current message to save as artifact"
            
    except Exception as e:
        logger.error(f"Error saving inline media as artifact: {e}")
        return f"❌ Error saving media as artifact: {str(e)}"


async def rename_and_save_media_artifact(
    original_filename: str, 
    description: str, 
    tool_context: ToolContext
) -> str:
    """
    Rename and save a media artifact with a descriptive filename.
    
    Args:
        original_filename (str): The current name of the artifact
        description (str): A descriptive name (max 50 chars) for the new filename
        tool_context (ToolContext): Context for accessing artifacts
    
    Returns:
        str: Success message with old and new filenames
    """
    try:
        # Load the original artifact
        artifact_part = await tool_context.load_artifact(original_filename)
        
        if not artifact_part:
            return f"Error: Artifact '{original_filename}' not found. Use list_user_artifacts to see available files."
        
        # Validate description length (should be ~50 chars)
        if len(description) > 60:
            description = description[:60]
        
        # Clean the description to make it a valid filename
        # Replace spaces with underscores and remove invalid characters
        clean_description = description.strip()
        clean_description = clean_description.replace(' ', '_')
        clean_description = ''.join(c for c in clean_description if c.isalnum() or c in ('_', '-'))
        
        # Get file extension from original filename
        original_ext = ""
        if '.' in original_filename:
            original_ext = original_filename.rsplit('.', 1)[1]
        
        # Determine extension from mime type if not available
        if not original_ext and hasattr(artifact_part, 'inline_data') and artifact_part.inline_data:
            mime_type = artifact_part.inline_data.mime_type
            if mime_type:
                if 'jpeg' in mime_type or 'jpg' in mime_type:
                    original_ext = 'jpg'
                elif 'png' in mime_type:
                    original_ext = 'png'
                elif 'mp4' in mime_type:
                    original_ext = 'mp4'
                elif 'webm' in mime_type:
                    original_ext = 'webm'
        
        # Create new filename with description
        if original_ext:
            new_filename = f"{clean_description}.{original_ext}"
        else:
            new_filename = clean_description
        
        # Save the artifact with the new filename
        version = await tool_context.save_artifact(new_filename, artifact_part)
        
        return f"""✅ Successfully renamed and saved media artifact!

**Original filename**: {original_filename}
**New filename**: {new_filename}
**Description**: {description}
**Version**: {version}

The artifact has been saved with a descriptive filename and is now available to the user."""
        
    except ValueError as e:
        return f"Error: {e}. Is the artifact service configured?"
    except Exception as e:
        return f"An unexpected error occurred while renaming artifact: {type(e).__name__}: {e}"





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

## YOUR ROLE: Initiate Generation and Return Polling Info

### Workflow for ALL Operations (Image/Video Generation and Image Editing):
1. **User requests generation/editing** with optional model specification
2. **YOU call the `generate()` tool** with `queue=True` (always queued)
3. **YOU receive operation details** (status_url, response_url, request_id)
4. **YOU return this information to the parent agent** so it can delegate polling
5. **Parent agent will handle polling** through its specialized polling agent

### Model Discovery and Selection:

#### **NEVER hardcode models** - Always let users choose:
- **Use `models()` tool** to list available models with pagination
- **Use `search()` tool** to find models by keywords
- **User specifies exact model** they want to use
- **No model recommendations** - present options and let user decide

### Step 1: Start Generation (YOUR JOB)
Call the `generate()` tool with:
- `model`: The full model ID (e.g., "fal-ai/flux-dev")
- `parameters`: Dict with model-specific parameters (prompt, image_url, etc.)
- `queue`: Always set to `True` for queued processing

### Step 2: Return Polling Information (YOUR JOB)
After getting the queue response, IMMEDIATELY return a clear message with:
- The request_id from the response
- The status_url from the response (important for polling)
- The submission type (text-to-video, text-to-image, etc.)
- A note that polling will be handled automatically

Example response:
"Generation started successfully! 
- Request ID: <THE_REQUEST_ID>
- Status URL: <THE_STATUS_URL>
- Type: text-to-video
The polling agent will now monitor this operation and return the final result."

DO NOT try to poll yourself - just return the information and let the parent agent handle polling delegation.

## Key Principles:
1. **USER-DRIVEN MODEL SELECTION** - Never choose for them
2. **DYNAMIC MODEL DISCOVERY** - Always use search/models tools
3. **RETURN POLLING INFO** - Don't poll, just pass the info back
"""

instruction = f"""You are an advanced AI assistant with multimodal capabilities, including image, audio, video, and document analysis, PLUS image generation via multiple sources.

**IMPORTANT**: You are activated via @Myker mentions. The mention is automatically detected and removed from messages before you see them, so you don't need to check for it - just respond naturally to all requests you receive.

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
5. **FAL.ai polling tool** for handling long-running FAL.ai operations:
   - poll_fal_operation: Automatically polls FAL.ai until generation completes
   - Takes fal_request_id and submission_type as parameters
   - Returns final media URLs when ready
   - Handles timeouts and errors gracefully
6. **Artifact management** for handling media files uploaded by users:
   - list_user_artifacts: See what media files users have uploaded
   - rename_and_save_media_artifact: Automatically rename images/videos with descriptive filenames
   - make_artifact_public: Make GCS artifacts publicly accessible for fal.ai processing

**FAL.ai Video/Image Generation Workflow:**
When a user requests FAL.ai generation (image or video):
1. **Delegate to fal_mcp_agent** - it will call generate() and return polling info
2. **Extract fal_request_id, status_url, and type** from the fal_mcp_agent response
3. **Call poll_fal_operation tool** with fal_request_id and status_url (or model_name)
4. **Wait for polling to complete** - it will return the final result
5. **Present the final media URL** to the user

Example flow:
User: "Generate a video of a cat playing"
→ You delegate to fal_mcp_agent to initiate generation
→ fal_mcp_agent returns: "Generation started! Request ID: abc123, Status URL: https://queue.fal.run/fal-ai/model/requests/abc123/status, Type: text-to-video"
→ You extract the status_url or note the model_name from the response
→ You then call poll_fal_operation(fal_request_id="abc123", status_url="<the_status_url>", submission_type="text-to-video")
→ poll_fal_operation polls and returns: "✅ Video generated successfully! Video URL: https://..."
→ You present the video URL to the user

IMPORTANT: Always pass the status_url from the fal_mcp_agent response to poll_fal_operation to ensure correct polling endpoint.

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

**Legacy Webhook System (Still Available):**
The webhook-based system (register_video_webhook) is still available for compatibility

**Multimodal Analysis Capabilities:**
- **Images**: Describe, analyze content, extract text, identify objects, analyze compositions
- **Audio**: Transcribe speech, identify sounds, analyze music (when audio data is available)
- **Videos**: Analyze visual content, describe scenes, extract key frames
- **Documents**: Read, summarize, extract information from PDFs and text files

**CRITICAL: Automatic Media Processing Workflow**
When you receive messages with inline_data (images/videos/audio) from the WhatsApp bot:

**Step 1: Store as Artifact**
- Call `save_inline_media_as_artifact(filename)` with the filename mentioned in the user's message
- This extracts inline_data from your current message and saves it as an artifact
- Use the exact filename the user mentioned (e.g., "media_abc123.jpg")

**Step 2: Rename Images/Videos (Mandatory)**
- For images and videos ONLY, call `rename_and_save_media_artifact` 
- Generate a clean, descriptive 50-character filename based on content analysis
- This replaces the random UUID filename with something meaningful

**Step 3: Analyze and Respond**
- Provide detailed analysis of the media content
- Explain what you renamed the file to and why

**Example workflow:**
User uploads image → Message contains inline_data with filename "media_abc123.jpg"
→ You call save_inline_media_as_artifact("media_abc123.jpg") to store the inline_data as an artifact
→ You analyze the visual content (e.g., see a sunset over mountains)
→ You call rename_and_save_media_artifact("media_abc123.jpg", "golden_sunset_over_snowy_mountain_peaks")
→ File is now stored as "golden_sunset_over_snowy_mountain_peaks.jpg"
→ You explain what you saw and how you renamed it

**Key Points:**
- Always save inline_data as artifacts BEFORE trying to rename
- Only images and videos get renamed - audio/documents keep original names
- Generate descriptive filenames that help users find their media later

**Working with Uploaded Images for fal.ai:**
When users upload an image and want to use it with fal.ai models (especially for image-to-video):
1. First, use `list_user_artifacts` to see available files
2. **IMPORTANT**: Use `rename_and_save_media_artifact` to rename with descriptive name
3. **THEN**: Use `make_artifact_public` to create a public GCS URL for the image
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
2. **MANDATORY**: Call `rename_and_save_media_artifact` for ALL images and videos with 50-char descriptions
3. Provide analysis using your multimodal capabilities
4. If using with fal.ai, use `make_artifact_public` to create public GCS URLs

**When users request image/video generation:**
1. **For images**: Use the exact model the user specifies, or help them discover available models
2. **For videos**: Delegate to the fal_mcp_agent which will use polling agent
3. **For image-to-video**: Use `rename_and_save_media_artifact` first, then `make_artifact_public`, then delegate to fal_mcp_agent
4. **Model Discovery**: Help users find available models if they ask "what models are available?"
5. Always provide detailed, descriptive prompts for better results
6. Handle errors gracefully and suggest alternative models if generation fails
7. **For video operations**: Return immediate confirmation - long-running tool handles completion
8. **Users get automatic WhatsApp notifications** when videos are ready with URLs



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
                if len(path_parts) >= 4 and path_parts[2] == 'shared':
                    found_filename = path_parts[3]
                    print(f"DEBUG: Checking wildcard blob: {blob.name}, extracted filename: {found_filename}")
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
                
                print(f"DEBUG: Found matching blob: {blob.name}")
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
# Fixed **kwargs compatibility issue by removing problematic functions from generate.py
import os
mcp_fal_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mcp-fal", "main.py")
fal_mcp_tools = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="python",
            args=[mcp_fal_path],
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
save_inline_media_tool = FunctionTool(func=save_inline_media_as_artifact)
rename_media_artifact_tool = FunctionTool(func=rename_and_save_media_artifact)



# Create artifact public URL tool for fal.ai integration
make_public_tool = FunctionTool(func=make_artifact_public)

# Import and create polling tool from polling_agent
from app.polling_agent import poll_fal_operation
poll_fal_tool = FunctionTool(func=poll_fal_operation)


# Mention checking callbacks for @Myker
async def before_agent_callback(callback_context: CallbackContext) -> None:
    """Check if message contains @Myker mention before processing."""
    try:
        # Get the current user message from invocation context
        user_content = callback_context._invocation_context.user_content
        
        if user_content and hasattr(user_content, 'parts'):
            # Extract text from all parts
            message_text = ""
            for part in user_content.parts:
                if hasattr(part, 'text') and part.text:
                    message_text += part.text + " "
            
            message_text = message_text.strip()
            print(f"[MENTION CHECK] Checking message: {message_text}")
            
            # Check for @Myker mention
            if not has_myker_mention(message_text):
                print("[MENTION CHECK] No @Myker mention found - ending invocation")
                callback_context._invocation_context.end_invocation = True
            else:
                print("[MENTION CHECK] @Myker mention found - proceeding with agent")
                
    except Exception as e:
        print(f"[MENTION CHECK] Error in before_agent_callback: {e}")
        # On error, proceed normally to avoid blocking the system
        pass


async def after_agent_callback(callback_context: CallbackContext) -> None:
    """Log completion of agent processing."""
    try:
        user_content = callback_context._invocation_context.user_content
        
        if user_content and hasattr(user_content, 'parts'):
            message_text = ""
            for part in user_content.parts:
                if hasattr(part, 'text') and part.text:
                    message_text += part.text + " "
            
            message_text = message_text.strip()
            
            if has_myker_mention(message_text):
                print(f"[MENTION CHECK] Completed processing message with @Myker: {message_text}")
            
    except Exception as e:
        print(f"[MENTION CHECK] Error in after_agent_callback: {e}")
        pass


tools = [retrieve_docs, github_mcp_tool, fal_mcp_tool, websearch_tool, list_artifacts_tool, save_inline_media_tool, rename_media_artifact_tool, make_public_tool, poll_fal_tool]

root_agent = Agent(
    name="root_agent",
    model="gemini-2.5-flash",
    instruction=instruction,
    tools=tools,
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback,
)
# CI/CD Test: Fri Oct  3 15:49:27 UTC 2025 - Testing deployment pipeline
# CI/CD Pipeline Test: Sun Oct  5 16:29:20 UTC 2025 - Testing automated deployment with latest Secret Manager integration
# Force deployment trigger - Sat Oct 18 16:41:33 UTC 2025
# URGENT: Fix deployment - wildcard artifact search not working - Sat Oct 18 17:19:00 UTC 2025
