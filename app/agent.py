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
from google.adk.tools.mcp_tool import MCPToolset, StreamableHTTPConnectionParams, StdioConnectionParams, MCPTool
from mcp.client.stdio import StdioServerParameters
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from langchain_google_vertexai import VertexAIEmbeddings
from pydantic import BaseModel
from typing import Any


def has_myker_mention(text: str) -> bool:
    """
    Check if the text contains a @Myker mention or phone number mention (case-insensitive).
    
    Args:
        text (str): The text to check for mentions
        
    Returns:
        bool: True if @Myker or @92033062547666 mention is found, False otherwise
    """
    if not text:
        return False
    
    # Use regex to find @Myker or phone number mentions (case-insensitive)
    patterns = [
        r'@myker\b',                # Original @myker mention
        r'@92033062547666\b'        # Phone number mention
    ]
    
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    return False


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
            logger.info(f"Checking part: type={type(part).__name__}, attributes={dir(part)}")
            
            # Check if this is a blob directly (ADK might pass blobs instead of inline_data)
            if hasattr(part, 'data') and hasattr(part, 'mime_type'):
                # This is likely a Blob object
                mime_type = part.mime_type
                blob_data = part.data
                
                logger.info(f"Found Blob: mime_type={mime_type}, data_length={len(blob_data) if blob_data else 0}")
                
                # Create a new Part with inline_data structure
                inline_data = types.Blob(mime_type=mime_type, data=blob_data)
                artifact_part = types.Part(inline_data=inline_data)
                
                # Save as artifact using tool_context
                version = await tool_context.save_artifact(filename, artifact_part)
                saved_count += 1
                
                logger.info(f"Saved Blob as artifact: {filename} (version: {version})")
                
                return f"✅ Successfully saved media as artifact: {filename} (MIME: {mime_type}, Version: {version})"
            
            # Check if this part has inline_data attribute
            elif hasattr(part, 'inline_data') and part.inline_data:
                inline_data = part.inline_data
                
                # Extract the media data and MIME type
                if hasattr(inline_data, 'data') and hasattr(inline_data, 'mime_type'):
                    mime_type = inline_data.mime_type
                    
                    # Create a new Part with the inline_data
                    artifact_part = types.Part(inline_data=inline_data)
                    
                    # Save as artifact using tool_context
                    version = await tool_context.save_artifact(filename, artifact_part)
                    saved_count += 1
                    
                    logger.info(f"Saved inline_data as artifact: {filename} (version: {version})")
                    
                    return f"✅ Successfully saved media as artifact: {filename} (MIME: {mime_type}, Version: {version})"
            
            # Also check if this is a file_data part 
            elif hasattr(part, 'file_data') and part.file_data:
                file_data = part.file_data
                if hasattr(file_data, 'mime_type'):
                    mime_type = file_data.mime_type
                    
                    # Create a Part with the file_data
                    artifact_part = types.Part(file_data=file_data)
                    
                    # Save as artifact using tool_context
                    version = await tool_context.save_artifact(filename, artifact_part)
                    saved_count += 1
                    
                    logger.info(f"Saved file_data as artifact: {filename} (version: {version})")
                    
                    return f"✅ Successfully saved media as artifact: {filename} (MIME: {mime_type}, Version: {version})"
        
        if saved_count == 0:
            # Try a different approach - check if the filename already exists in context
            try:
                # Sometimes the media is already saved by the WhatsApp bot
                existing_artifact = await tool_context.load_artifact(filename)
                if existing_artifact:
                    return f"✅ Media already exists as artifact: {filename}. No need to save again."
            except:
                pass
                
            return "❌ No inline_data, file_data, or direct blob found in the current message to save as artifact"
            
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
You are a FAL.ai MCP agent that generates images, videos, audio, and music using fal.ai models through MCP interface.

## YOUR ROLE: Initiate Generation and Return Polling Info

### Workflow for ALL Operations (Image/Video/Audio Generation and Editing):
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
- `model`: The full model ID (e.g., "fal-ai/flux-dev", "fal-ai/musicgen-large", "fal-ai/audio-craft")
- `parameters`: Dict with model-specific parameters including:
  - `prompt`: The generation prompt (required for all types)
  - `image_url`: For image-to-video or image editing operations (optional)
  - `audio_url`: For audio-to-audio or audio processing operations (optional)  
  - `duration`: For audio/music generation (optional, in seconds)
  - `enable_safety_checker`: Set to `false` to disable content filtering (default: true)
  - Other model-specific parameters as needed
- `queue`: Always set to `True` for queued processing

**IMPORTANT: Content Safety Control**
- By default, fal.ai models have safety checkers enabled to filter content
- To allow unrestricted generation, add `"enable_safety_checker": false` to parameters
- This bypasses content policy filters that might reject certain prompts
- Use when user explicitly requests unrestricted or artistic content

### Step 2: Return Polling Information (YOUR JOB)
After getting the queue response, IMMEDIATELY return a clear message with:
- The request_id from the response
- The status_url from the response (important for polling)
- The submission type (text-to-video, text-to-image, etc.)
- A note that polling will be handled automatically

Example responses:
"Generation started successfully! 
- Request ID: <THE_REQUEST_ID>
- Status URL: <THE_STATUS_URL>
- Type: text-to-video
The polling agent will now monitor this operation and return the final result."

"Audio generation started successfully! 
- Request ID: <THE_REQUEST_ID>
- Status URL: <THE_STATUS_URL>
- Type: text-to-music
The polling agent will now monitor this operation and return the final result."

DO NOT try to poll yourself - just return the information and let the parent agent handle polling delegation.

## Key Principles:
1. **USER-DRIVEN MODEL SELECTION** - Never choose for them
2. **DYNAMIC MODEL DISCOVERY** - Always use search/models tools
3. **RETURN POLLING INFO** - Don't poll, just pass the info back
"""

instruction = f"""You are an advanced AI assistant with multimodal capabilities, including image, audio, video, and document analysis, PLUS comprehensive AI content generation via fal.ai including images, videos, audio, and music.

**PLATFORM CONTEXT - WhatsApp Chat Integration:**
You are operating within a WhatsApp chat environment. Messages you receive are from WhatsApp users, and may come from individual chats or group conversations.

**Message Format:**
- Messages are prefixed with the sender's name, formatted as: "Username: message content"
- The username is the WhatsApp display name (pushName) of the person sending the message
- This prefix is INFORMATIONAL ONLY - it tells you WHO is speaking, not what they're asking you to do
- The username is NOT part of the user's request or command
- Example: "CherylChua: Can you help me?" means Cheryl Chua is asking for help
- Example: "Joyce: What time are we leaving?" means Joyce is asking about departure time

**Important Username Handling Rules:**
1. The username prefix (e.g., "CherylChua:") identifies the SPEAKER, not the subject
2. Do NOT treat usernames as part of commands or requests
3. When responding, you can naturally address users by their name if appropriate
4. In group chats, multiple users may send messages - each will have their own username prefix
5. The username helps you understand conversation context and who said what

**Activation:**
You are activated via @Myker mentions or @92033062547666 mentions. The mention is automatically detected and removed from messages before you see them, so you don't need to check for it - just respond naturally to all requests you receive.

Answer to the best of your ability using the context provided and leverage the tools available to you.

You have access to several specialized capabilities:
1. **Document retrieval** from your knowledge base using retrieve_docs
2. **GitHub operations** through a specialized GitHub agent with MCP tools  
3. **Web search** capabilities through a specialized web search agent
3. **fal.ai AI generation** through a specialized fal.ai agent with access to:
   - Advanced image generation models (Flux, SDXL, etc.)
   - Video generation capabilities (Stable Video Diffusion, etc.)
   - Audio & music generation models (text-to-audio, text-to-music, music synthesis)
   - Sound effect generation and audio processing
   - Model discovery and schema inspection for all media types
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

**FAL.ai Content Generation Workflow:**
When a user requests FAL.ai generation (image, video, audio, or music):
1. **Delegate to fal_mcp_agent** - it will call generate() and return polling info
2. **Extract fal_request_id, status_url, and type** from the fal_mcp_agent response
3. **Call poll_fal_operation tool** with fal_request_id and status_url (or model_name)
4. **Wait for polling to complete** - it will return the final result
5. **Present the final media URL** to the user

Example flows:
User: "Generate a video of a cat playing"
→ You delegate to fal_mcp_agent to initiate generation
→ fal_mcp_agent returns: "Generation started! Request ID: abc123, Status URL: https://queue.fal.run/fal-ai/model/requests/abc123/status, Type: text-to-video"
→ You extract the status_url or note the model_name from the response
→ You then call poll_fal_operation(fal_request_id="abc123", status_url="<the_status_url>", submission_type="text-to-video")
→ poll_fal_operation polls and returns: "🎬 https://..." 
→ You present the video URL to the user

User: "Create music for a relaxing beach scene"
→ You delegate to fal_mcp_agent to initiate audio generation
→ fal_mcp_agent returns: "Generation started! Request ID: xyz789, Status URL: https://queue.fal.run/fal-ai/audiomodel/requests/xyz789/status, Type: text-to-music"
→ You call poll_fal_operation(fal_request_id="xyz789", status_url="<the_status_url>", submission_type="text-to-music")
→ poll_fal_operation polls and returns: "🎵 https://..."
→ You present the audio URL to the user

**CRITICAL: Timeout Message Handling**
When poll_fal_operation returns a timeout message (starting with "@Fal"), you MUST pass it through to the user EXACTLY as written, word-for-word, without any modifications, paraphrasing, or rewording. DO NOT summarize it. DO NOT change the wording. The timeout message contains specific formatting and information that must be preserved exactly.

Example of what poll_fal_operation might return on timeout:
"@Fal Your video/image is still being generated (taking longer than 90 seconds).\n\nVideo generation can take 2-5 minutes depending on the model and complexity.\n\nRequest ID: abc123\nStatus URL: https://...\n\nYou can:\n\nWait a few minutes and ask me to check the status again\nCheck the status directly at: https://...\nI'll keep monitoring this in the background and will notify you when it's ready!"

When you receive this message from poll_fal_operation, return it VERBATIM to the user. Do not modify, rewrite, or paraphrase it in any way.

IMPORTANT: Always pass the status_url from the fal_mcp_agent response to poll_fal_operation to ensure correct polling endpoint.

**AI Content Generation Guidelines:**
- **All AI content generation is handled through fal.ai models** via the fal.ai agent
- Users specify which models to use, or can discover available models
- Use the fal.ai agent to discover available models with the `models` tool
- Check model schemas before generation to understand required parameters
- Generated content is automatically saved as artifacts and included in responses
- Handle generation errors gracefully with alternative model suggestions

**fal.ai Generation Capabilities:**
- **Image Generation**: Use models specified by user or discovered through model search (Flux, SDXL, etc.)
- **Video Generation**: Use whatever video model the user explicitly requests (Stable Video Diffusion, etc.)
- **Audio & Music Generation**: Support text-to-audio, text-to-music, music synthesis, and sound effects
- **Audio Processing**: Handle various audio formats and generation types
- **Model Discovery**: Use the fal.ai agent to list and search available models for all media types
- **Schema Inspection**: Always check model schemas before generation for any content type
- **Queue Management**: Handle long-running generations with proper status checking for all media types

**Legacy Webhook System (Still Available):**
The webhook-based system (register_video_webhook) is still available for compatibility

**Multimodal Analysis & Generation Capabilities:**
- **Images**: Describe, analyze content, extract text, identify objects, analyze compositions + GENERATE new images via fal.ai
- **Audio**: Transcribe speech, identify sounds, analyze music (when audio data is available) + GENERATE music, sound effects, speech via fal.ai
- **Videos**: Analyze visual content, describe scenes, extract key frames + GENERATE videos via fal.ai
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

**When users request AI content generation (images/videos/audio/music):**
1. **For images**: Use the exact model the user specifies, or help them discover available models
2. **For videos**: Delegate to the fal_mcp_agent which will use polling agent
3. **For audio/music**: Delegate to the fal_mcp_agent with appropriate audio generation models
4. **For image-to-video**: Use `rename_and_save_media_artifact` first, then `make_artifact_public`, then delegate to fal_mcp_agent
5. **For audio with reference**: Process uploaded audio files if needed before generation
6. **Model Discovery**: Help users find available models for any media type if they ask "what models are available?"
7. Always provide detailed, descriptive prompts for better results across all media types
8. Handle errors gracefully and suggest alternative models if generation fails
9. **For long-running operations (video/audio)**: Return immediate confirmation - polling tool handles completion
10. **Users get automatic WhatsApp notifications** when content is ready with URLs



GitHub agent works with repository: Michaelktker/my-agentic-rag by default.
Use web search for current information not in your knowledge base.
Use fal.ai agent for all AI content generation capabilities including images and videos.

Updated: Comprehensive fal.ai integration for images, videos, audio, and music generation - 2025-10-28"""


async def make_artifact_public(filename: str, tool_context: ToolContext) -> str:
    """
    Make an artifact publicly accessible via GCS public URL.
    This creates a direct public URL that can be used with fal.ai models.
    
    Uses user-scoped artifact paths following ADK best practices:
    - Path structure: app/{user_id}/{filename}/{version}
    - Artifacts are scoped by user, not by session
    - This allows artifacts to persist across different sessions

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
        logger.info(f"🪣 Using GCS bucket: {artifacts_bucket_name}")
        
        storage_client = storage.Client()
        bucket = storage_client.bucket(artifacts_bucket_name)
        
        # Get user ID from tool context - this is the primary scoping mechanism
        user_id = getattr(tool_context, 'user_id', None)
        
        logger.info(f"🔍 Tool context: type={type(tool_context).__name__}, user_id={user_id}")
        
        # Try alternative ways to get user information from tool context
        if not user_id:
            for attr in ['userId', 'user', '_user_id', 'current_user']:
                if hasattr(tool_context, attr):
                    alt_user = getattr(tool_context, attr)
                    if alt_user:
                        logger.info(f"✅ Found user via '{attr}': {alt_user}")
                        user_id = alt_user
                        break
        
        if not user_id:
            # Search across all users - wildcard approach
            user_id = '*'
            logger.info(f"⚠️ No user_id found, using wildcard search across all users")
        
        # Determine search prefix based on user_id
        # USER-SCOPED GCS structure (ADK best practice): app/{user_id}/{filename}/{version}
        # This allows artifacts to persist across different sessions for the same user
        if user_id == '*':
            prefix = "app/"
            logger.info(f"🔎 Wildcard search with prefix: {prefix}")
        else:
            prefix = f"app/{user_id}/"
            logger.info(f"🔎 User-scoped search with prefix: {prefix}")
        
        # List all blobs with this prefix to find artifacts
        logger.info(f"📋 Listing blobs in bucket '{artifacts_bucket_name}' with prefix '{prefix}'")
        blobs = list(bucket.list_blobs(prefix=prefix))
        logger.info(f"📊 Found {len(blobs)} total blobs in prefix")
        
        found_blob = None

        for blob in blobs:
            # Extract the path components for USER-SCOPED artifacts
            # Expected path structure: app/{user_id}/{filename}/{version}
            # However, legacy session-scoped paths may exist: app/{user_id}/{session_id}/{filename}/{version}
            path_parts = blob.name.split('/')
            logger.info(f"🔍 Checking blob: {blob.name} (parts: {len(path_parts)})")

            # Handle both user-scoped (3-part) and legacy session-scoped (5-part) paths
            # User-scoped: app/user_id/filename/version (4 parts total)
            # Session-scoped: app/user_id/session_id/filename/version (5 parts total)
            if len(path_parts) >= 4:
                # filename is always second-to-last component (before version)
                found_filename = path_parts[-2]
                user_from_path = path_parts[1] if len(path_parts) > 1 else None
                logger.info(f"  📄 Candidate filename: {found_filename} (user_from_path={user_from_path})")
            else:
                logger.info(f"  ⏭️ Skipping: insufficient path parts (got {len(path_parts)})")
                continue

            # Normalize and compare the filename variations (strip ADK version suffixes if present)
            filename_base = filename.split(' v')[0].lower()
            found_filename_base = found_filename.split(' v')[0].lower()

            # Also consider matches where extension was added/removed or only a prefix/suffix differs
            def norm(s: str) -> str:
                return s.lower().strip().rstrip('/')

            if (
                norm(found_filename) == norm(filename)
                or norm(found_filename_base) == norm(filename_base)
                or norm(filename).startswith(norm(found_filename_base))
                or norm(found_filename).startswith(norm(filename_base))
                or f"/{filename}/" in f"/{blob.name}/"
            ):
                logger.info(f"✅ MATCH FOUND: {blob.name}")
                # if caller lacked user_id, capture the user we discovered in the path
                if not user_id and user_from_path:
                    user_id = user_from_path
                    logger.info(f"ℹ️ Inferred user_id from blob path: {user_id}")
                found_blob = blob
                break
            else:
                logger.info(f"  ❌ No match: '{found_filename}' != '{filename}'")
        
        if not found_blob:
            error_msg = f"❌ Artifact '{filename}' not found in GCS.\n\nSearched:\n- Bucket: {artifacts_bucket_name}\n- Prefix: {prefix}\n- Found {len(blobs)} blobs total\n\nFull blob paths (first 10):\n"
            for blob in blobs[:10]:  # Show first 10 files
                error_msg += f"  • {blob.name}\n"
            if len(blobs) > 10:
                error_msg += f"  ... and {len(blobs) - 10} more files"
            logger.error(error_msg)
            return error_msg
        
        logger.info(f"🎯 Found target blob: {found_blob.name}")
        
        # Check if this is an ADK JSON format file and extract raw image data
        try:
            # Download the content to check format
            logger.info(f"⬇️ Downloading blob content to check format...")
            content = found_blob.download_as_bytes()
            logger.info(f"✅ Downloaded {len(content)} bytes")
            
            try:
                # Try to parse as ADK JSON format
                artifact_data = json.loads(content.decode('utf-8'))
                logger.info(f"📄 Parsed as JSON, checking for ADK format...")
                
                if 'data' in artifact_data and isinstance(artifact_data['data'], dict) and artifact_data['data'].get('__buffer_type'):
                    # This is ADK format with byte array data
                    logger.info(f"🔧 ADK JSON format detected - extracting raw image data")
                    
                    # Extract the raw image bytes
                    byte_array = artifact_data['data']['data']
                    raw_image_data = bytes(byte_array)
                    logger.info(f"✅ Extracted {len(raw_image_data)} bytes of raw image data")
                    
                    # Get the mime type
                    mime_type = artifact_data.get('mimeType', 'image/jpeg')
                    logger.info(f"📝 MIME type: {mime_type}")
                    
                    # Create a new blob for the raw image
                    raw_filename = filename.replace('.jpg', '_raw.jpg').replace('.png', '_raw.png')
                    if not raw_filename.endswith(('.jpg', '.png', '.jpeg')):
                        raw_filename += '_raw.jpg'
                    
                    # Create path for raw image (same structure but with _raw suffix)
                    raw_blob_name = found_blob.name.replace(filename, raw_filename)
                    raw_blob = bucket.blob(raw_blob_name)
                    logger.info(f"📤 Uploading raw image to: {raw_blob_name}")
                    
                    # Upload the raw image data
                    raw_blob.upload_from_string(raw_image_data, content_type=mime_type)
                    logger.info(f"✅ Raw image uploaded successfully")
                    
                    # Now make the raw image public
                    try:
                        raw_blob.make_public()
                        public_url = raw_blob.public_url
                        logger.info(f"✅ Made raw image public: {public_url}")
                    except Exception as public_error:
                        logger.warning(f"⚠️ make_public() failed: {public_error}, trying bucket policy...")
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
                                logger.info(f"✅ Set bucket-level public access")
                            
                            public_url = raw_blob.public_url
                            logger.info(f"✅ Generated public URL via bucket policy")
                            
                        except Exception as bucket_error:
                            logger.error(f"❌ Bucket policy failed: {bucket_error}")
                            # Use simple public_url format instead of media_link - FAL.ai prefers this
                            public_url = raw_blob.public_url
                    
                    # Update found_blob reference for the response
                    found_blob = raw_blob
                    
                else:
                    # Not ADK format, treat as regular blob
                    logger.info(f"ℹ️ Not ADK JSON format, treating as regular blob")
                    raise ValueError("Not ADK format")
                    
            except (json.JSONDecodeError, ValueError, UnicodeDecodeError) as e:
                # Not JSON or not ADK format, make the original blob public
                logger.info(f"ℹ️ File is not ADK JSON format ({type(e).__name__}), making original blob public")
                
                try:
                    found_blob.make_public()
                    public_url = found_blob.public_url
                    logger.info(f"✅ Made original blob public: {public_url}")
                except Exception as public_error:
                    logger.warning(f"⚠️ make_public() failed: {public_error}, trying bucket policy...")
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
                            logger.info(f"✅ Set bucket-level public access")
                        
                        public_url = found_blob.public_url
                        logger.info(f"✅ Generated public URL via bucket policy")
                        
                    except Exception as bucket_error:
                        logger.error(f"❌ Bucket policy failed: {bucket_error}")
                        # Use simple public_url format instead of media_link - FAL.ai prefers this
                        public_url = found_blob.public_url
                
        except Exception as e:
            logger.error(f"❌ Error processing artifact: {e}")
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
        
        logger.info(f"🎉 Success! Public URL generated: {public_url}")
        
        return f"✅ Successfully made '{filename}' public!\n\n🔗 **Public URL**: {public_url}\n\nThis URL can now be used directly with fal.ai models for:\n- Image-to-video generation\n- Advanced image processing\n- AI model workflows\n\nFile details:\n- Type: {mime_type}\n- Size: {size_str}\n- GCS Path: {found_blob.name}\n\n**Ready for fal_mcp_agent use!**"
        
    except Exception as e:
        logger.error(f"❌ Critical error in make_artifact_public: {e}", exc_info=True)
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


def serialize_pydantic_to_dict(obj: Any) -> Any:
    """
    Recursively convert Pydantic models and special types (like AnyUrl) to JSON-serializable dicts.
    This fixes the TypeError: Object of type AnyUrl is not JSON serializable error.
    
    Args:
        obj: Any object that might contain Pydantic models or AnyUrl objects
        
    Returns:
        JSON-serializable version of the object
    """
    # Handle Pydantic models
    if isinstance(obj, BaseModel):
        return serialize_pydantic_to_dict(obj.model_dump())
    
    # Handle dictionaries
    elif isinstance(obj, dict):
        return {k: serialize_pydantic_to_dict(v) for k, v in obj.items()}
    
    # Handle lists
    elif isinstance(obj, list):
        return [serialize_pydantic_to_dict(item) for item in obj]
    
    # Handle AnyUrl and other special Pydantic types - convert to string
    elif hasattr(obj, '__str__') and type(obj).__module__ == 'pydantic_core._pydantic_core':
        return str(obj)
    
    # Return as-is for primitive types
    return obj


# Removed SerializingMCPTool and SerializingMCPToolset classes
# The MCP tools should work without custom serialization wrappers
# Test comment: Cloud Build trigger test - November 1, 2025


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

# Create the fal.ai MCP subagent for comprehensive AI content generation
# Supports image, video, audio, and music generation via fal.ai models
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


# Mention checking callbacks for @Myker and phone number
async def before_agent_callback(callback_context: CallbackContext) -> None:
    """Check if message contains @Myker or @92033062547666 mention before processing."""
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
            
            # Check for @Myker or phone number mention
            if not has_myker_mention(message_text):
                print("[MENTION CHECK] No @Myker or @92033062547666 mention found - ending invocation")
                callback_context._invocation_context.end_invocation = True
            else:
                print("[MENTION CHECK] Valid mention found - proceeding with agent")
                
    except Exception as e:
        print(f"[MENTION CHECK] Error in before_agent_callback: {e}")
        # On error, proceed normally to avoid blocking the system
        pass


async def after_agent_callback(callback_context: CallbackContext) -> None:
    """Log completion of agent processing."""
    # Enforce exact timeout message for poll_fal_operation
    try:
        tool_name = getattr(callback_context, 'tool_name', None)
        result = getattr(callback_context, 'tool_result', None)
        
        # Debug: log what we're getting
        print(f"[CALLBACK DEBUG] Tool name: {tool_name}, Result type: {type(result)}")
        if isinstance(result, str) and len(result) < 200:
            print(f"[CALLBACK DEBUG] Result preview: {result[:200]}")
        
        # Check for timeout message from any FAL-related tool
        if isinstance(result, str) and "still being generated" in result and "I'll keep monitoring" in result:
            print(f"[CALLBACK DEBUG] Found timeout message, attempting to enforce scripted message")
            import re
            req_id_match = re.search(r'Request ID: ([^\n]+)', result)
            status_url_match = re.search(r'Status URL: ([^\n]+)', result)
            fal_request_id = req_id_match.group(1).strip() if req_id_match else "[unknown]"
            final_status_url = status_url_match.group(1).strip() if status_url_match else "[unknown]"
            enforced_message = (
                f"@Fal Your video/image is still being generated (taking longer than 90 seconds).\n\n"
                f"Video generation can take 2-5 minutes depending on the model and complexity.\n\n"
                f"Request ID: {fal_request_id}\n"
                f"Status URL: {final_status_url}\n\n"
                f"You can:\n\n"
                f"Wait a few minutes and ask me to check the status again\n"
                f"Check the status directly at: {final_status_url.replace('/status', '')}\n"
                f"I'll keep monitoring this in the background and will notify you when it's ready!"
            )
            callback_context.tool_result = enforced_message
            print(f"[CALLBACK DEBUG] Enforced message set successfully")
    except Exception as e:
        print(f"[MENTION CHECK] Error in after_agent_callback (enforce timeout): {e}")


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
