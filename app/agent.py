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

credentials, project_id = google.auth.default()
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
        # Load the artifact
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

When working with fal.ai models:
- Use the most appropriate model for the requested content type
- Always check model schemas before generating to understand required parameters
- Handle queued requests appropriately for long-running generations
- Provide clear feedback about generation progress and results
- Be efficient in your tool usage

Common fal.ai models you can use:
- fal-ai/flux/dev: High-quality image generation
- fal-ai/flux/schnell: Fast image generation
- fal-ai/stable-video-diffusion: Video generation
- And many others available through the models tool

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

**When users upload media files through WhatsApp:**
1. First use `list_user_artifacts` to see what files are available
2. Use `load_and_analyze_artifact` to load specific files for analysis
3. Provide detailed analysis using your multimodal capabilities
4. Optionally save analysis results using `save_analysis_result`

**When users request image/video generation:**
1. For images: Choose between Vertex AI Imagen or fal.ai models based on requirements
2. For videos: Use the fal.ai agent with appropriate video generation models
3. For specialized effects or styles: Consider fal.ai's diverse model ecosystem
4. Always provide detailed, descriptive prompts for better results
5. Handle errors gracefully and suggest alternatives if generation fails

**Important Notes:**
- You can ANALYZE existing media AND GENERATE new content via multiple AI services
- Generated content is included directly in responses AND saved as artifacts
- The Gemini 2.5 Flash model you're powered by can directly analyze multimodal content
- When artifacts are loaded, their content becomes available in the conversation context
- Always provide comprehensive, detailed analysis of media files

GitHub agent works with repository: {GITHUB_OWNER}/{GITHUB_REPO} by default.
Use web search for current information not in your knowledge base.
Use fal.ai agent for advanced AI content generation capabilities.

Updated: Added fal.ai MCP integration for advanced AI generation - 2025-10-17"""


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
            command="/workspaces/my-agentic-rag/mcp-fal/.venv/bin/python",
            args=["/workspaces/my-agentic-rag/mcp-fal/main.py"],
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

tools = [retrieve_docs, github_mcp_tool, fal_mcp_tool, websearch_tool, list_artifacts_tool, load_artifact_tool, save_artifact_tool, generate_image_tool]

root_agent = Agent(
    name="root_agent",
    model="gemini-2.5-flash",
    instruction=instruction,
    tools=tools,
)
# CI/CD Test: Fri Oct  3 15:49:27 UTC 2025 - Testing deployment pipeline
# CI/CD Pipeline Test: Sun Oct  5 16:29:20 UTC 2025 - Testing automated deployment with latest Secret Manager integration
