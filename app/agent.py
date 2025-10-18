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
        # Handle potential version suffixes in filename
        # The ADK artifact system stores files with version suffixes like " v1", " v2" etc.
        # but list_user_artifacts() returns filenames without the version suffix
        # We need to try different variations to find the actual artifact
        
        possible_filenames = []
        
        # If the filename already has a version suffix, use it as-is and try without it
        if ' v' in filename:
            possible_filenames.append(filename)  # Try with version first
            base_filename = filename.split(' v')[0]
            possible_filenames.append(base_filename)  # Then try without version
        else:
            # If no version suffix, try adding common version patterns first
            # since ADK often stores with versions even if list doesn't show them
            version_suffixes = [' v1', ' v2', ' v3', '_v1', '_v2', '_v3', ' (1)', ' (2)', ' (3)']
            for suffix in version_suffixes:
                possible_filenames.append(filename + suffix)
            
            # Then try the original filename as-is
            possible_filenames.append(filename)
        
        # Try loading artifact with different filename variations
        artifact_part = None
        successful_filename = None
        last_error = None
        
        for attempt_filename in possible_filenames:
            try:
                artifact_part = await tool_context.load_artifact(attempt_filename)
                successful_filename = attempt_filename
                break
            except Exception as error:
                last_error = error
                continue
        
        if artifact_part is None:
            return f"Artifact '{filename}' not found. Tried variations: {possible_filenames}. Last error: {last_error}"
        
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
        # Handle version suffixes more robustly
        # The ADK artifact system stores files with version suffixes like " v1", " v2" etc.
        # but list_user_artifacts() returns filenames without the version suffix
        # We need to try different variations to find the actual artifact
        
        possible_filenames = []
        base_filename = filename  # Initialize base_filename with the original filename
        
        # If the filename already has a version suffix, use it as-is and try without it
        if ' v' in filename:
            possible_filenames.append(filename)  # Try with version first
            base_filename = filename.split(' v')[0]
            possible_filenames.append(base_filename)  # Then try without version
            print(f"DEBUG: Detected version in filename: '{filename}' -> base: '{base_filename}'")
        else:
            # If no version suffix, try adding common version patterns first
            # since ADK often stores with versions even if list doesn't show them
            version_suffixes = [' v1', ' v2', ' v3', '_v1', '_v2', '_v3', ' (1)', ' (2)', ' (3)']
            for suffix in version_suffixes:
                possible_filenames.append(filename + suffix)
            
            # Then try the original filename as-is
            possible_filenames.append(filename)
            base_filename = filename
        
        print(f"DEBUG: Will try these filenames: {possible_filenames}")
        
        # Try loading artifact with different filename variations
        artifact_part = None
        successful_filename = None
        last_error = None
        
        for attempt_filename in possible_filenames:
            try:
                print(f"DEBUG: Attempting to load artifact with filename: '{attempt_filename}'")
                artifact_part = await tool_context.load_artifact(attempt_filename)
                successful_filename = attempt_filename
                print(f"DEBUG: ✅ Successfully loaded artifact with filename: '{attempt_filename}'")
                break
            except Exception as error:
                print(f"DEBUG: ❌ Failed to load with filename '{attempt_filename}': {error}")
                last_error = error
                continue
        
        if artifact_part is None:
            return f"Could not load artifact '{filename}'. Tried filenames: {possible_filenames}. Last error: {last_error}"
        
        if not artifact_part:
            return f"Artifact '{filename}' not found or is empty. Use list_user_artifacts to see available files."
        
        # Debug: Log the artifact structure to understand it better
        print(f"DEBUG: artifact_part type: {type(artifact_part)}")
        if hasattr(artifact_part, '__dict__'):
            print(f"DEBUG: artifact_part attributes: {list(artifact_part.__dict__.keys())}")
        else:
            print(f"DEBUG: artifact_part dir: {[attr for attr in dir(artifact_part) if not attr.startswith('_')]}")
        
        # Extract artifact data more carefully
        data = None
        mime_type = 'application/octet-stream'
        
        try:
            if hasattr(artifact_part, 'inline_data') and artifact_part.inline_data:
                mime_type = artifact_part.inline_data.mime_type
                data = artifact_part.inline_data.data
                print(f"DEBUG: Using inline_data, mime_type: {mime_type}, data_type: {type(data)}")
            elif hasattr(artifact_part, 'data'):
                mime_type = getattr(artifact_part, 'mimeType', 'application/octet-stream')
                data = artifact_part.data
                print(f"DEBUG: Using direct data, mime_type: {mime_type}, data_type: {type(data)}")
            else:
                # Try alternative attribute names
                for attr in ['content', 'bytes', 'binary_data']:
                    if hasattr(artifact_part, attr):
                        data = getattr(artifact_part, attr)
                        print(f"DEBUG: Found data in {attr}, data_type: {type(data)}")
                        break
                        
            if data is None:
                return f"Could not extract data from artifact '{filename}'. Available attributes: {dir(artifact_part)}"
        
        except Exception as extract_error:
            return f"Error extracting data from artifact '{filename}': {extract_error}"
        
        # Convert data to bytes if needed
        if isinstance(data, str):
            try:
                import base64
                data = base64.b64decode(data)
                print(f"DEBUG: Decoded base64 string to bytes, length: {len(data)}")
            except Exception as b64_error:
                print(f"DEBUG: Failed to decode as base64: {b64_error}")
                data = data.encode('utf-8')
        elif not isinstance(data, bytes):
            return f"Unexpected data type: {type(data)}. Expected bytes or base64 string."
        
        print(f"DEBUG: Final data type: {type(data)}, length: {len(data)}")
        
        # Upload to fal.ai storage using their client
        try:
            import tempfile
            import os
            import uuid
            
            # Create a temporary file with the artifact data
            temp_filename = f"fal_upload_{uuid.uuid4()}_{base_filename}"
            temp_path = os.path.join(tempfile.gettempdir(), temp_filename)
            
            # Write artifact data to temporary file
            with open(temp_path, 'wb') as temp_file:
                temp_file.write(data)
            
            print(f"DEBUG: Wrote {len(data)} bytes to {temp_path}")
            
            # Use fal_client to upload to fal.ai CDN
            try:
                import fal_client
                
                # Ensure FAL_KEY is available - get it from Secret Manager if needed
                if not os.getenv("FAL_KEY"):
                    try:
                        from google.cloud import secretmanager
                        client = secretmanager.SecretManagerServiceClient()
                        secret_name = f"projects/{project_id}/secrets/fal-api-key/versions/latest"
                        response = client.access_secret_version(request={"name": secret_name})
                        fal_key = response.payload.data.decode("UTF-8")
                        os.environ["FAL_KEY"] = fal_key
                        print(f"DEBUG: Retrieved FAL_KEY from Secret Manager")
                    except Exception as secret_error:
                        os.unlink(temp_path)  # Clean up
                        return f"Error accessing FAL_KEY from Secret Manager: {secret_error}"
                
                # Upload file to fal.ai storage
                print(f"DEBUG: Uploading to fal.ai...")
                file_url = fal_client.upload_file(temp_path)
                print(f"DEBUG: Upload successful: {file_url}")
                
                # Clean up temporary file
                os.unlink(temp_path)
                
                return f"Successfully uploaded '{filename}' to fal.ai storage!\n\nfal.ai URL: {file_url}\n\nThis URL can now be used with fal.ai models for image-to-video generation and other processing."
                
            except ImportError:
                # Fallback: Try to use the MCP fal server's upload functionality
                # This would require making a request to the MCP server
                os.unlink(temp_path)  # Clean up
                return f"fal_client not available. To upload artifacts to fal.ai storage, you need to install fal_client: pip install fal-client\n\nAlternatively, the fal.ai agent can help with uploads using the MCP server."
                
            except Exception as fal_error:
                # Clean up temporary file on error
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                return f"Error uploading to fal.ai storage: {fal_error}\n\nMake sure your FAL_KEY environment variable is set correctly."
            
        except Exception as e:
            return f"Error preparing file for fal.ai upload: {e}"
    
    except Exception as e:
        return f"Error processing artifact '{filename}': {e}"


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
