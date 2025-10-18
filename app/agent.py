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
import os
import time
import base64
import uuid
import asyncio
import aiohttp
from io import BytesIO

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
from vertexai.preview.vision_models import ImageGenerationModel

from app.retrievers import get_compressor, get_retriever
from app.templates import format_docs

EMBEDDING_MODEL = "text-embedding-005"
LLM_LOCATION = "global"
LOCATION = "us-central1"
LLM = "gemini-2.5-flash"

# GitHub repository constants
GITHUB_OWNER = "Michaelktker"
GITHUB_REPO = "my-agentic-rag"

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
    Lists all artifacts (media files) uploaded by the current user.
    Use this to see what files are available for analysis.

    Returns:
        str: A formatted list of available artifacts or an error message.
    """
    try:
        available_files = await tool_context.list_artifacts()
        if not available_files:
            return "You have no saved artifacts. Upload some media files to get started!"
        else:
            file_list = "\n".join([f"• {filename}" for filename in available_files])
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
        if not user_id:
            # Try to get from context metadata or session info
            session_id = getattr(tool_context, 'session_id', '')
            if session_id and session_id.startswith('wa_'):
                # Extract user ID from WhatsApp session data - we need to search all users
                # Since we can't determine the exact user, we'll search across all app/ subdirectories
                user_id = '*'  # Wildcard to search all users
            else:
                user_id = 'unknown_user'
        
        # Search for the artifact across all sessions for this user
        # Path pattern: app/{user_id}/{session_id}/{filename}/{version}
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


async def generate_image(prompt: str, tool_context: ToolContext) -> str:
    """
    Generate an image using Vertex AI Imagen model.
    The generated image will be included directly in the agent's response.

    Args:
        prompt (str): Detailed description of the image to generate
        tool_context (ToolContext): Context for adding image to conversation

    Returns:
        str: Success message with generation details
    """
    try:
        # Initialize the latest Imagen model
        model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")
        
        # Generate the image with optimized parameters for WhatsApp
        images = model.generate_images(
            prompt=prompt,
            number_of_images=1,
            language="en",
            aspect_ratio="1:1",  # Square format works well for WhatsApp
            safety_filter_level="allow_most",
            person_generation="allow_adult"
        )
        
        if not images:
            return "Failed to generate image. Please try a different prompt."
        
        # Get the generated image
        generated_image = images[0]
        
        # Convert Vertex AI GeneratedImage to bytes
        img_bytes = generated_image._image_bytes
        
        # Create filename for artifact storage
        timestamp = int(time.time())
        filename = f"generated_image_{timestamp}.png"
        
        # Create Part object for the image
        image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/png")
        
        # Save as artifact - this makes it available for the agent's response
        version = await tool_context.save_artifact(filename, image_part)
        
        # Calculate file size
        size_mb = len(img_bytes) / (1024 * 1024)
        
        return f"""✅ Successfully generated image: "{prompt}"

📁 Saved as: {filename} (version {version})  
📏 Size: {size_mb:.1f} MB
🖼️ Format: PNG (1024x1024)
🎨 Model: Imagen 3.0

The image has been generated and saved as an artifact. You can now include this image in your response to the user by referencing the artifact '{filename}'."""
        
    except Exception as e:
        error_msg = str(e)
        
        # Handle common errors with helpful messages
        if "safety" in error_msg.lower():
            return f"❌ Image generation blocked by safety filters. Please try a different prompt that doesn't include potentially harmful content.\n\nOriginal prompt: {prompt}"
        elif "quota" in error_msg.lower() or "limit" in error_msg.lower():
            return "❌ Image generation quota exceeded. Please try again later or contact support."
        elif "invalid" in error_msg.lower():
            return f"❌ Invalid prompt for image generation. Please provide a more descriptive prompt.\n\nOriginal prompt: {prompt}"
        else:
            return f"❌ Error generating image: {error_msg}\n\nPlease try a different prompt or contact support if the issue persists."


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

By default, you are working with the GitHub repository: {GITHUB_OWNER}/{GITHUB_REPO}
When using GitHub tools, use this repository unless the user specifically requests a different one.

When performing GitHub operations:
- Use the most appropriate MCP tool for the requested operation
- Provide clear and structured information from GitHub
- Handle errors gracefully and provide helpful feedback
- Be efficient in your tool usage

Always be precise and thorough in your GitHub operations."""

# fal.ai MCP agent prompt
FAL_MCP_PROMPT = """You are a specialized fal.ai agent with access to fal.ai's image and video generation models through MCP (Model Context Protocol) tools.

Your role is to:
1. Handle all fal.ai model operations efficiently
2. List available models and search for specific ones
3. Generate images and videos using various fal.ai models
4. Retrieve model schemas and capabilities
5. Handle both direct and queued generation requests
6. Work with artifacts uploaded by users through the main agent

**IMPORTANT: Artifact Handling**
- When the user references an uploaded image or media file, you need to work with the main agent
- If you receive a request mentioning an uploaded image, ask the main agent to first load the artifact
- You can then work with the artifact data once it's made available
- For image-to-video generation, you may need the main agent to save the image as a publicly accessible URL

When working with fal.ai models:
- Use the most appropriate model for the requested content type
- Always check model schemas before generating to understand required parameters
- Handle queued requests appropriately for long-running generations
- Provide clear feedback about generation progress and results
- Be efficient in your tool usage
- If you need access to uploaded media, coordinate with the main agent through the tool context

Common fal.ai models you can use:
- fal-ai/flux/dev: High-quality image generation
- fal-ai/flux/schnell: Fast image generation
- fal-ai/stable-video-diffusion: Video generation
- fal-ai/seedance-1-0-pro: Image-to-Video generation
- And many others available through the models tool

**For Image-to-Video Generation:**
- If the user uploads an image and wants to generate a video from it
- Ask the main agent to first load and provide the image artifact
- You may need the image to be saved to a publicly accessible URL for fal.ai to process
- Work with the main agent to handle this workflow

Always be precise and thorough in your fal.ai operations."""

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
   - upload_artifact_to_fal: Upload artifacts to public URLs for fal.ai processing
6. **Image generation** using Vertex AI Imagen:
   - generate_image: Create images from detailed text descriptions

**Image Generation Guidelines:**
- You now have TWO image generation options:
  1. **Vertex AI Imagen** (generate_image): Google's high-quality image generation
  2. **fal.ai models** (via fal.ai agent): Various cutting-edge models like Flux, SDXL
- For advanced or specialized image generation, consider using fal.ai models
- For quick, reliable generation, use Vertex AI Imagen
- When users request image creation, choose the most appropriate method
- Generated images are automatically included in your response AND saved as artifacts
- Handle safety filter rejections gracefully with alternative suggestions

**fal.ai Generation Capabilities:**
- **Image Generation**: Use models like "fal-ai/flux/dev" for high-quality images
- **Video Generation**: Use models like "fal-ai/stable-video-diffusion" 
- **Model Discovery**: Use the fal.ai agent to list and search available models
- **Schema Inspection**: Always check model schemas before generation
- **Queue Management**: Handle long-running generations with proper status checking

**Multimodal Analysis Capabilities:**
- **Images**: Describe, analyze content, extract text, identify objects, analyze compositions
- **Audio**: Transcribe speech, identify sounds, analyze music (when audio data is available)
- **Videos**: Analyze visual content, describe scenes, extract key frames
- **Documents**: Read, summarize, extract information from PDFs and text files

**Working with Uploaded Images for fal.ai:**
When users upload an image and want to use it with fal.ai models (especially for image-to-video):
1. First, use `list_user_artifacts` to see available files
2. Use `load_and_analyze_artifact` to analyze the image if needed
3. **IMPORTANT**: Use `upload_artifact_to_fal` to create a public URL for the image
4. Provide this public URL to the fal.ai agent for processing
5. The fal.ai agent can then use this URL with models like Seedance for image-to-video generation

**When users upload media files through WhatsApp:**
1. First use `list_user_artifacts` to see what files are available
2. Use `load_and_analyze_artifact` to load specific files for analysis
3. Provide detailed analysis using your multimodal capabilities
4. If using with fal.ai, use `upload_artifact_to_fal` to create public URLs
5. Optionally save analysis results using `save_analysis_result`

**When users request image/video generation:**
1. For images: Choose between Vertex AI Imagen or fal.ai models based on requirements
2. For videos: Use the fal.ai agent with appropriate video generation models
3. For image-to-video: Use `upload_artifact_to_fal` first, then fal.ai agent with the URL
4. For specialized effects or styles: Consider fal.ai's diverse model ecosystem
5. Always provide detailed, descriptive prompts for better results
6. Handle errors gracefully and suggest alternatives if generation fails

**Important Notes:**
- You can ANALYZE existing media AND GENERATE new content via multiple AI services
- Generated content is included directly in responses AND saved as artifacts
- The Gemini 2.5 Flash model you're powered by can directly analyze multimodal content
- When artifacts are loaded, their content becomes available in the conversation context
- Always provide comprehensive, detailed analysis of media files
- For fal.ai image-to-video generation, you MUST first upload the image to a public URL

GitHub agent works with repository: {GITHUB_OWNER}/{GITHUB_REPO} by default.
Use web search for current information not in your knowledge base.
Use fal.ai agent for advanced AI content generation capabilities.

Updated: Added artifact-to-URL upload for fal.ai integration - 2025-10-18"""


async def upload_artifact_to_fal(filename: str, tool_context: ToolContext) -> str:
    """
    Upload an artifact to fal.ai storage for processing with fal.ai models.
    This function loads an artifact, saves it temporarily, and uploads it to fal.ai's CDN.

    Args:
        filename (str): The name of the artifact file to upload
        tool_context (ToolContext): Context for accessing artifacts

    Returns:
        str: fal.ai file URL for the uploaded file or error message
    """
    try:
        # CRITICAL FIX: Session ID mismatch issue - same as load_and_analyze_artifact
        # Use direct GCS access to find artifacts across all sessions for this user
        
        from google.cloud import storage
        import json
        import base64
        import tempfile
        
        # Get bucket from environment or default
        artifacts_bucket_name = os.getenv("ARTIFACTS_BUCKET_NAME", "adk_artifact")
        storage_client = storage.Client()
        bucket = storage_client.bucket(artifacts_bucket_name)
        
        # Get user ID from tool context if available
        user_id = getattr(tool_context, 'user_id', None)
        if not user_id:
            # Try to get from context metadata or session info
            session_id = getattr(tool_context, 'session_id', '')
            if session_id and session_id.startswith('wa_'):
                # Extract user ID from WhatsApp session data - we need to search all users
                # Since we can't determine the exact user, we'll search across all app/ subdirectories
                user_id = '*'  # Wildcard to search all users
            else:
                user_id = 'unknown_user'
        
        # Search for the artifact across all sessions for this user
        if user_id == '*':
            # Search across all users if we can't determine the specific user
            prefix = "app/"
            print(f"DEBUG: upload_artifact_to_fal - Searching for artifact '{filename}' across all users with prefix '{prefix}'")
        else:
            prefix = f"app/{user_id}/"
            print(f"DEBUG: upload_artifact_to_fal - Searching for artifact '{filename}' for user '{user_id}' with prefix '{prefix}'")
        
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
            return f"Could not load artifact '{filename}' for fal.ai upload. Searched prefix: '{prefix}'"
        
        print(f"DEBUG: artifact_found type: {type(artifact_found)}")
        
        # Extract data for upload
        file_data = None
        mime_type = None
        
        if isinstance(artifact_found, dict):
            # Our dictionary format
            file_data = artifact_found.get('data')
            mime_type = artifact_found.get('mimeType')
            if artifact_found.get('inline_data'):
                file_data = artifact_found['inline_data'].get('data') or file_data
                mime_type = artifact_found['inline_data'].get('mime_type') or mime_type
        elif hasattr(artifact_found, 'inline_data') and artifact_found.inline_data:
            # ADK Part format
            file_data = artifact_found.inline_data.data
            mime_type = artifact_found.inline_data.mime_type
        elif hasattr(artifact_found, 'data'):
            # Direct data access
            file_data = artifact_found.data
            mime_type = getattr(artifact_found, 'mimeType', 'application/octet-stream')
        
        if not file_data:
            return f"Artifact '{filename}' was found but contains no data"
        
        print(f"DEBUG: Extracted data length: {len(file_data) if file_data else 0}, mime_type: {mime_type}")
        
        # Decode base64 data if needed
        try:
            if isinstance(file_data, str):
                binary_data = base64.b64decode(file_data)
            else:
                binary_data = file_data
        except Exception as decode_error:
            return f"Failed to decode artifact data: {decode_error}"
        
        # Determine file extension from mime type
        file_extension = ".bin"  # Default
        if mime_type:
            if mime_type.startswith("image/jpeg"):
                file_extension = ".jpg"
            elif mime_type.startswith("image/png"):
                file_extension = ".png"
            elif mime_type.startswith("image/webp"):
                file_extension = ".webp"
            elif mime_type.startswith("image/gif"):
                file_extension = ".gif"
            elif mime_type.startswith("video/mp4"):
                file_extension = ".mp4"
            elif mime_type.startswith("audio/"):
                file_extension = ".mp3"
            elif mime_type.startswith("application/pdf"):
                file_extension = ".pdf"
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            temp_file.write(binary_data)
            temp_file_path = temp_file.name
        
        try:
            # Now upload to fal.ai
            import fal_client
            
            print(f"DEBUG: Uploading {len(binary_data)} bytes to fal.ai...")
            url = fal_client.upload_file(temp_file_path)
            print(f"DEBUG: ✅ Successfully uploaded to fal.ai: {url}")
            
            return f"✅ Successfully uploaded '{filename}' to fal.ai!\n\n🔗 **fal.ai URL**: {url}\n\nYou can now use this URL with fal.ai models for:\n- Image-to-video generation\n- Advanced image processing\n- AI model workflows\n\nFile details:\n- Type: {mime_type}\n- Size: {len(binary_data)} bytes\n- Source: {found_path}"
            
        except Exception as upload_error:
            return f"Failed to upload '{filename}' to fal.ai: {upload_error}"
        
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file_path)
            except:
                pass
                
    except Exception as e:
        return f"Error uploading artifact '{filename}' to fal.ai: {e}"


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

# Create image generation tool
generate_image_tool = FunctionTool(func=generate_image)

# Create artifact upload tool for fal.ai integration
upload_artifact_tool = FunctionTool(func=upload_artifact_to_fal)

tools = [retrieve_docs, github_mcp_tool, fal_mcp_tool, websearch_tool, list_artifacts_tool, load_artifact_tool, save_artifact_tool, generate_image_tool, upload_artifact_tool]

root_agent = Agent(
    name="root_agent",
    model="gemini-2.5-flash",
    instruction=instruction,
    tools=tools,
)
# CI/CD Test: Fri Oct  3 15:49:27 UTC 2025 - Testing deployment pipeline
# CI/CD Pipeline Test: Sun Oct  5 16:29:20 UTC 2025 - Testing automated deployment with latest Secret Manager integration
# Force deployment trigger - Sat Oct 18 16:41:33 UTC 2025
