# Google Agent Development Kit (ADK) - Task Template

## 🚀 Overview

Google's Agent Development Kit (ADK) is a flexible, open-source framework for building, evaluating, and deploying sophisticated AI agents. This template provides a comprehensive guide for implementing ADK-based solutions with production-ready patterns and best practices.

**⭐ Updated for Production Patterns**: This template includes battle-tested patterns from real-world deployment including polling agents, MCP integration, media handling, and advanced artifact management.

## 🏗️ Core Architecture & Concepts

### 1. **Agent Types**
- **LlmAgent**: LLM-powered agents with tools and planners
- **BaseAgent**: Custom agents with full control over execution logic
- **SequentialAgent**: Runs sub-agents in sequence
- **ParallelAgent**: Runs sub-agents concurrently
- **LoopAgent**: Runs sub-agents in a loop

### 2. **Core Components**

#### **Agents**
```python
from google.adk.agents import Agent, LlmAgent

# Basic Agent
root_agent = Agent(
    name="my_agent",
    model="gemini-2.5-flash",
    instruction="You are a helpful assistant...",
    description="Agent description",
    tools=[tool1, tool2],
    sub_agents=[sub_agent1, sub_agent2]
)

# Advanced LLM Agent with Configuration
advanced_agent = LlmAgent(
    model="gemini-2.5-pro",
    name="advanced_agent",
    instruction="Detailed instructions...",
    planner=BuiltInPlanner(),
    tools=[custom_tools],
    input_schema=InputSchema,
    output_schema=OutputSchema,
    output_key="result_key",
    before_agent_callback=before_callback,
    after_agent_callback=after_callback
)
```

#### **Runners & Sessions**
```python
from google.adk.runners import Runner, InMemoryRunner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Session Management
session_service = InMemorySessionService()
session = await session_service.create_session(
    app_name="my_app",
    user_id="user123",
    session_id="session456"
)

# Runner Setup
runner = Runner(
    agent=root_agent,
    app_name="my_app",
    session_service=session_service
)

# Execute Agent
content = types.Content(role='user', parts=[types.Part(text="Hello")])
events = runner.run(
    user_id="user123",
    session_id="session456",
    new_message=content
)

# Async Execution
async for event in runner.run_async(
    user_id="user123",
    session_id="session456",
    new_message=content
):
    if event.is_final_response():
        print(event.content.parts[0].text)
```

#### **Tools & Function Tools**
```python
from google.adk.tools import FunctionTool, GoogleTool
from typing import Optional, Literal

def custom_tool_function(
    param1: str,
    param2: int,
    optional_param: Optional[str] = None
) -> dict:
    """
    Custom tool function with proper docstring.
    
    Args:
        param1: Description of parameter 1
        param2: Description of parameter 2  
        optional_param: Optional parameter description
        
    Returns:
        Dictionary with results
    """
    return {"status": "success", "result": "data"}

# Async Tool
async def async_tool_function(endpoint: str) -> dict:
    """Async tool with external API calls."""
    import asyncio
    await asyncio.sleep(0.1)  # Non-blocking
    return {"data": "async_result"}

# Create Function Tools
sync_tool = FunctionTool(func=custom_tool_function)
async_tool = FunctionTool(func=async_tool_function)
```

#### **Built-in Tools**
```python
from google.adk.tools import google_search
from google.adk.tools.code_execution import BuiltInCodeExecutor

# Google Search Tool
search_agent = Agent(
    name="search_agent",
    model="gemini-2.5-flash",
    instruction="Use Google Search to find information",
    tools=[google_search]
)

# Code Execution (Root agent only)
code_agent = Agent(
    name="code_agent",
    model="gemini-2.5-flash",
    instruction="Execute code when needed",
    code_executor=BuiltInCodeExecutor()
)
```

### 3. **Multi-Agent Patterns**

#### **Coordinator Pattern**
```python
# Sub-agents for specific tasks
billing_agent = LlmAgent(name="Billing", description="Handles billing inquiries")
support_agent = LlmAgent(name="Support", description="Handles technical support")

# Coordinator routes requests
coordinator = LlmAgent(
    name="HelpDeskCoordinator",
    model="gemini-2.5-flash",
    instruction="Route requests: billing to Billing, technical to Support",
    sub_agents=[billing_agent, support_agent]
)
```

#### **Sequential Workflow**
```python
from google.adk.agents import SequentialAgent

# Individual agents for each step
prepare_agent = LlmAgent(name="PrepareRequest", ...)
process_agent = LlmAgent(name="ProcessRequest", ...)
finalize_agent = LlmAgent(name="FinalizeRequest", ...)

# Sequential execution
workflow = SequentialAgent(
    name="RequestWorkflow",
    sub_agents=[prepare_agent, process_agent, finalize_agent]
)
```

#### **Parallel Processing**
```python
from google.adk.agents import ParallelAgent

# Agents that can run concurrently
api1_agent = LlmAgent(name="API1Fetcher", ...)
api2_agent = LlmAgent(name="API2Fetcher", ...)

# Parallel execution
parallel_fetch = ParallelAgent(
    name="ConcurrentFetch",
    sub_agents=[api1_agent, api2_agent]
)
```

#### **Agent as Tool Pattern**
```python
from google.adk.tools.agent_tool import AgentTool

# Specialized agent
specialized_agent = LlmAgent(name="DataAnalyzer", ...)

# Wrap as tool for parent agent
analyzer_tool = AgentTool(agent=specialized_agent)

# Use in parent agent
parent_agent = Agent(
    name="parent",
    tools=[analyzer_tool, other_tools]
)
```

#### **MCP Integration Pattern**
```python
from google.adk.tools.mcp_tool import MCPToolset

# External MCP server (e.g., fal.ai models)
fal_mcp_toolset = MCPToolset(
    label="fal-mcp",
    command="python",
    args=["main.py"],
    cwd="/path/to/mcp-fal",
    env={"FAL_KEY": "your_api_key"}
)

# Wrap as AgentTool
fal_agent_tool = AgentTool(agent=fal_mcp_toolset)

# Integration with root agent
root_agent = Agent(
    name="root_agent",
    tools=[fal_agent_tool]
)
```

### 4. **Planners**

#### **Built-in Planner** (Default for Gemini models)
```python
from google.adk.planners import BuiltInPlanner
from google.genai.types import ThinkingConfig

thinking_config = ThinkingConfig(
    include_thoughts=True,
    thinking_budget=256
)

planner = BuiltInPlanner(thinking_config=thinking_config)

agent = LlmAgent(
    model="gemini-2.5-flash",
    planner=planner,
    tools=[tool1, tool2]
)
```

#### **PlanReActPlanner** (For non-Gemini models)
```python
from google.adk.planners import PlanReActPlanner

planner = PlanReActPlanner()

agent = LlmAgent(
    model="claude-3-opus",
    planner=planner,
    tools=[tools]
)
```

### 5. **Memory & State Management**

#### **Session State**
```python
from google.adk.agents.callback_context import CallbackContext

def initialize_session_state(callback_context: CallbackContext):
    """Initialize session with default values."""
    if "conversation_history" not in callback_context.state:
        callback_context.state["conversation_history"] = []
    
    if "user_preferences" not in callback_context.state:
        callback_context.state["user_preferences"] = {}

def track_conversation(callback_context: CallbackContext):
    """Track conversation turns."""
    current_message = callback_context._invocation_context.message
    callback_context.state["conversation_history"].append({
        "turn": len(callback_context.state["conversation_history"]) + 1,
        "message": current_message,
        "timestamp": datetime.now().isoformat()
    })

# Stateful Agent
stateful_agent = Agent(
    name="stateful_assistant",
    model="gemini-2.5-flash",
    instruction="Use conversation history for context",
    before_agent_callback=initialize_session_state,
    before_turn_callback=track_conversation
)
```

### 6. **Artifacts & Context**

#### **Tool Context**
```python
from google.adk.tools.tool_context import ToolContext

async def artifact_tool(filename: str, tool_context: ToolContext) -> str:
    """Tool that uses artifacts."""
    # List available artifacts
    artifacts = await tool_context.list_artifacts()
    
    # Load specific artifact
    artifact = await tool_context.load_artifact(filename)
    
    # Save new artifact
    from google.genai import types
    new_artifact = types.Part.from_text("Analysis result")
    version = await tool_context.save_artifact("result.txt", new_artifact)
    
    return f"Processed {filename}, saved result as version {version}"
```

### 7. **Advanced Features**

#### **Context Caching**
```python
from google.adk.context_cache import ContextCacheConfig

cache_config = ContextCacheConfig(
    min_tokens=4096,
    ttl_seconds=600,  # 10 minutes
    cache_intervals=3  # Max invocations before invalidation
)

agent = Agent(
    name="cached_agent",
    model="gemini-2.5-flash",
    instruction="Agent with context caching",
    context_cache_config=cache_config
)
```

#### **Input/Output Schemas**
```python
from pydantic import BaseModel
from typing import Optional

class UserInput(BaseModel):
    name: str
    age: int
    preferences: Optional[dict] = None

class AgentOutput(BaseModel):
    recommendation: str
    confidence: float
    reasoning: str

structured_agent = LlmAgent(
    name="structured_agent",
    model="gemini-2.5-flash",
    instruction="Provide structured recommendations",
    input_schema=UserInput,
    output_schema=AgentOutput,
    output_key="recommendation_result"
)
```

#### **MCP (Model Context Protocol) Tools**
```python
from google.adk.tools.mcp_tool import MCPToolset, StreamableHTTPConnectionParams

# GitHub MCP Tools
mcp_tools = MCPToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://api.githubcopilot.com/mcp/",
        headers={"Authorization": f"Bearer {github_token}"}
    )
)

github_agent = Agent(
    name="github_agent",
    model="gemini-2.5-flash",
    instruction="Use GitHub tools for repository operations",
    tools=[mcp_tools]
)
```

## 🛠️ Implementation Patterns

### 1. **Project Structure**
```
my_adk_project/
├── src/
│   └── my_app/
│       ├── agents/
│       │   ├── my_agent/
│       │   │   ├── __init__.py      # from . import agent
│       │   │   └── agent.py         # root_agent = Agent(...)
│       │   └── another_agent/
│       ├── tools/
│       │   ├── __init__.py
│       │   └── custom_tools.py
│       └── utils/
│           ├── __init__.py
│           └── helpers.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── evaluation/
├── deployment/
│   ├── deploy.py
│   └── Dockerfile
├── .env.example
├── pyproject.toml
└── README.md
```

### 2. **Environment Configuration**
```bash
# .env file
GOOGLE_GENAI_USE_VERTEXAI=True
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_API_KEY=your-api-key  # For AI Studio

# Optional
GITHUB_PAT=your-github-token
ARTIFACTS_BUCKET_NAME=your-bucket
```

### 3. **Development Workflow**
```bash
# Install dependencies
pip install google-adk
# or
poetry install
# or  
uv sync

# Run agent locally
adk run path/to/agent

# Web interface
adk web path/to/agent

# Evaluation
adk eval agent_path eval_set.json

# Deploy to Vertex AI
adk deploy agent_engine \
  --project=your-project \
  --region=us-central1 \
  --staging_bucket="gs://your-bucket" \
  --display_name="My Agent" \
  ./agent_directory
```

### 4. **FastAPI Integration**
```python
from google.adk.cli.fast_api import get_fast_api_app

# Generate FastAPI app from agent
app = get_fast_api_app(agent_dir="./agents")

# Add custom endpoints
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Run with uvicorn
# uvicorn main:app --host 0.0.0.0 --port 8000
```

### 5. **Testing Framework**
```python
# tests/test_agent.py
import pytest
from google.adk.evaluation import AgentEvaluator
from my_app.agents.my_agent.agent import root_agent

def test_agent_basic_functionality():
    """Test basic agent responses."""
    response = root_agent.query("Hello")
    assert response is not None
    assert len(response) > 0

def test_agent_evaluation():
    """Evaluate agent performance."""
    evaluator = AgentEvaluator(
        agent=root_agent,
        test_data_path="eval/test_cases.json",
        config_path="eval/config.json"
    )
    
    results = evaluator.run()
    assert results["tool_trajectory_avg_score"] >= 0.7
    assert results["response_match_score"] >= 0.75

# Run tests
# pytest tests/ -v
# pytest --cov=my_app tests/
```

## 🔧 Production Deployment

### 1. **Vertex AI Agent Engine**
```python
# deployment/deploy.py
import vertexai
from vertexai import reasoning_engines

vertexai.init(project="your-project", location="us-central1")

# Deploy agent
reasoning_engine = reasoning_engines.ReasoningEngine.create(
    display_name="My Production Agent",
    spec=reasoning_engines.ReasoningEngineSpec(
        package_spec=reasoning_engines.ReasoningEngineSpec.PackageSpec(
            pickle_object_gcs_uri="gs://bucket/agent.pkl",
            dependency_files_gcs_uri="gs://bucket/dependencies/",
            requirements_gcs_uri="gs://bucket/requirements.txt"
        ),
        class_methods=["query"]
    )
)

print(f"Deployed: {reasoning_engine.resource_id}")
```

### 2. **Cloud Run Deployment**
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### 3. **Docker Compose (Local Development)**
```yaml
# docker-compose.yml
version: '3.8'
services:
  adk-agent:
    build: .
    ports:
      - "8000:8000"
    environment:
      - GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}
      - GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json
    volumes:
      - ./credentials.json:/app/credentials.json:ro
```

## 📊 Monitoring & Observability

### 1. **Agent Callbacks**
```python
def before_agent_callback(callback_context: CallbackContext):
    """Log agent invocation."""
    logger.info(f"Agent {callback_context.agent.name} starting")
    callback_context.state["start_time"] = time.time()

def after_agent_callback(callback_context: CallbackContext):
    """Log agent completion."""
    duration = time.time() - callback_context.state["start_time"]
    logger.info(f"Agent completed in {duration:.2f}s")

monitored_agent = Agent(
    name="monitored_agent",
    model="gemini-2.5-flash",
    instruction="Agent with monitoring",
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback
)
```

### 2. **Tool Callbacks** 
```python
def before_tool_callback(
    tool_name: str,
    tool_input: dict,
    callback_context: CallbackContext
) -> Optional[dict]:
    """Security and audit logging before tool execution."""
    logger.info(f"Tool {tool_name} called with {tool_input}")
    
    # Security check example
    if "classified" in str(tool_input).lower():
        return {"error": "Access denied: classified content"}
    
    return None  # Allow execution

def after_tool_callback(
    tool_name: str,
    tool_input: dict,
    tool_output: dict,
    callback_context: CallbackContext
) -> dict:
    """Enhance tool output."""
    logger.info(f"Tool {tool_name} completed")
    
    # Enhance output
    enhanced_output = tool_output.copy()
    enhanced_output["execution_timestamp"] = datetime.now().isoformat()
    
    return enhanced_output

agent_with_tool_callbacks = Agent(
    name="secure_agent",
    model="gemini-2.5-flash",
    instruction="Agent with tool security",
    tools=[custom_tool],
    before_tool_callback=before_tool_callback,
    after_tool_callback=after_tool_callback
)
```

## 🔄 Common Use Cases & Examples

### 1. **RAG Agent**
```python
from google.adk.tools.retrieval.vertex_ai_rag_retrieval import VertexAiRagRetrieval
from vertexai.preview import rag

# RAG retrieval tool
rag_tool = VertexAiRagRetrieval(
    name='retrieve_documentation',
    description='Retrieve relevant documentation',
    rag_resources=[
        rag.RagResource(
            rag_corpus=os.environ.get("RAG_CORPUS")
        )
    ],
    similarity_top_k=10,
    vector_distance_threshold=0.6
)

rag_agent = Agent(
    name="documentation_assistant",
    model="gemini-2.5-flash",
    instruction="Use RAG retrieval to answer questions with citations",
    tools=[rag_tool]
)
```

### 2. **Data Analysis Agent**
```python
def query_database(sql: str) -> dict:
    """Execute SQL query against database."""
    # Database logic here
    return {"results": [], "row_count": 0}

def create_visualization(data: dict, chart_type: str) -> dict:
    """Create data visualization."""
    # Visualization logic here
    return {"chart_url": "https://example.com/chart.png"}

data_agent = Agent(
    name="data_analyst",
    model="gemini-2.5-pro",
    instruction="Analyze data and create visualizations",
    tools=[
        FunctionTool(query_database),
        FunctionTool(create_visualization)
    ]
)
```

### 3. **Customer Service Agent**
```python
# Multi-agent customer service system
billing_agent = LlmAgent(
    name="billing_specialist",
    model="gemini-2.5-flash",
    instruction="Handle billing inquiries and payment issues"
)

technical_agent = LlmAgent(
    name="technical_support",
    model="gemini-2.5-flash", 
    instruction="Provide technical support and troubleshooting"
)

escalation_agent = LlmAgent(
    name="escalation_handler",
    model="gemini-2.5-pro",
    instruction="Handle complex issues requiring human intervention"
)

customer_service = LlmAgent(
    name="customer_service_coordinator",
    model="gemini-2.5-flash",
    instruction="""Route customer inquiries:
    - Billing issues → billing_specialist
    - Technical problems → technical_support  
    - Complex issues → escalation_handler""",
    sub_agents=[billing_agent, technical_agent, escalation_agent]
)
```

## 🎯 Best Practices

### 1. **Agent Design**
- ✅ Use clear, specific instructions
- ✅ Implement proper error handling in tools
- ✅ Use appropriate agent types for use cases
- ✅ Design for async execution when possible
- ✅ Implement proper state management

### 2. **Tool Development**
- ✅ Write comprehensive docstrings
- ✅ Use type hints for all parameters
- ✅ Handle exceptions gracefully
- ✅ Use async/await for I/O operations
- ✅ Return structured data

### 3. **Multi-Agent Systems**
- ✅ Design clear agent responsibilities
- ✅ Use coordinator patterns for routing
- ✅ Implement proper handoff mechanisms
- ✅ Consider parallel vs sequential execution
- ✅ Design for failure recovery

### 4. **Production Deployment**
- ✅ Implement comprehensive logging
- ✅ Use proper authentication and authorization
- ✅ Monitor performance metrics
- ✅ Implement health checks
- ✅ Use environment-specific configurations

### 5. **Security**
- ✅ Validate all inputs
- ✅ Implement tool execution guardrails
- ✅ Use secure credential management
- ✅ Audit tool usage
- ✅ Implement rate limiting

## 🎯 Production-Ready Patterns

### Mention-Based Activation
```python
from google.adk.agents.callback_context import CallbackContext
import re

def before_agent_callback(callback_context: CallbackContext):
    """Check for @Myker mention before agent execution."""
    message_parts = callback_context.request.new_message.parts
    message_text = ""
    
    # Extract text from message parts
    for part in message_parts:
        if hasattr(part, 'text') and part.text:
            message_text += part.text + " "
    
    # Check for mention (case-insensitive)
    if "@myker" not in message_text.lower():
        callback_context.context["skip_processing"] = True
        callback_context.context["mention_response"] = (
            "I only respond when mentioned with @Myker. "
            "Please include @Myker in your message."
        )
        return
        
    # Clean message by removing @Myker mention
    cleaned_text = re.sub(r'@myker\s*', '', message_text, flags=re.IGNORECASE)
    for part in message_parts:
        if hasattr(part, 'text') and part.text:
            part.text = cleaned_text.strip()
            break
    callback_context.context["skip_processing"] = False

def after_agent_callback(callback_context: CallbackContext):
    """Handle mention response if processing was skipped."""
    if callback_context.context.get("skip_processing", False):
        mention_response = callback_context.context.get("mention_response", "")
        callback_context.response.candidates[0].content.parts[0].text = mention_response
```

### Polling Agent for Long Operations
```python
async def poll_fal_operation(
    fal_request_id: str,
    status_url: str = "",
    model_name: str = "",
    submission_type: str = "image"
) -> str:
    """Smart polling strategy for long-running operations."""
    
    # Quick check attempts based on media type
    max_quick_checks = 20 if submission_type != "text-to-video" else 3
    
    for attempt in range(max_quick_checks):
        try:
            final_status_url = status_url or f"https://queue.fal.run/{model_name}/requests/{fal_request_id}/status"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(final_status_url, headers=headers)
                
            if response.status_code in [200, 202]:
                data = response.json()
                status = data.get("status", "unknown")
                
                if status == "completed":
                    # Return completed result
                    return format_completion_response(data)
                elif status in ["failed", "cancelled"]:
                    return f"❌ Operation {status}: {data.get('error', 'Unknown error')}"
                    
            await asyncio.sleep(3)
            
        except Exception as e:
            if attempt == max_quick_checks - 1:
                return f"❌ Polling error: {str(e)}"
    
    # For videos, return guidance message
    if submission_type == "text-to-video":
        return f"""⏳ **Your video is being generated!** 🎬

Video generation typically takes **2-5 minutes**. 

**What to do:**
1. ✨ Wait 2-3 minutes  
2. 💬 Ask me: *"Check the status of my video"*
3. 🔄 I'll check and get your video for you!

**Request ID:** `{fal_request_id}`
"""
    
    return "⏳ Still processing, please try again in a moment..."
```

### Smart Media Artifact Management
```python
async def rename_and_save_media_artifact(
    filename: str,
    tool_context: ToolContext
) -> str:
    """AI-powered smart media renaming and persistence."""
    
    # Load artifact from current session
    try:
        artifacts = await tool_context.list_artifacts()
        target_artifact = None
        
        for artifact in artifacts:
            if artifact.name == filename:
                target_artifact = artifact
                break
        
        if not target_artifact:
            return f"❌ Artifact '{filename}' not found in current session"
            
        # Check if it's an image for smart renaming
        mime_type = target_artifact.mime_type or "application/octet-stream"
        
        if mime_type.startswith('image/'):
            # AI-powered filename generation
            analysis_prompt = f"""Analyze this image and provide a 45-character descriptive filename summary.

Rules:
1. Describe the main subject, context, or purpose
2. Use clear, specific terms
3. Maximum 45 characters
4. No file extension needed
5. Focus on what makes this image unique or useful

Provide only the filename description, nothing else."""
            
            # Send multimodal analysis request
            content = types.Content(
                role="user",
                parts=[
                    types.Part(text=analysis_prompt),
                    types.Part(inline_data=types.Blob(
                        mime_type=mime_type,
                        data=target_artifact.data
                    ))
                ]
            )
            
            response = await tool_context.send_message(content)
            
            if response and response.candidates:
                ai_summary = response.candidates[0].content.parts[0].text.strip()
                
                # Clean and format the summary
                cleaned_summary = _clean_filename_text(ai_summary, 45)
                
                # Generate new filename with proper extension
                new_filename = _generate_smart_filename(cleaned_summary, mime_type)
                
                # Save with new descriptive name
                new_version = await tool_context.save_artifact(new_filename, target_artifact.data, mime_type)
                
                return f"""✅ **Image Analysis & Auto-Rename Complete!**

📁 **Filename Updated:** 
   • From: `{filename}`
   • To: `{new_filename}`

📊 **File Details:** {mime_type} • {len(target_artifact.data) / 1024:.1f} KB

🔍 **Analysis Results:**
{ai_summary[:200]}{'...' if len(ai_summary) > 200 else ''}

Your image has been automatically renamed with a descriptive filename!"""
        
        else:
            # Non-image files - save as-is
            new_version = await tool_context.save_artifact(filename, target_artifact.data, mime_type)
            return f"✅ Artifact '{filename}' saved successfully (Version: {new_version})"
            
    except Exception as e:
        return f"❌ Error processing artifact: {str(e)}"

def _clean_filename_text(text: str, max_length: int = 50) -> str:
    """Clean AI-generated text for use as filename."""
    # Remove quotes and clean text
    cleaned = text.strip().strip('"\'')
    
    # Replace special characters with underscores
    cleaned = re.sub(r'[^\w\s-]', '', cleaned)
    cleaned = re.sub(r'[-\s]+', '_', cleaned)
    
    # Convert to lowercase and truncate
    cleaned = cleaned.lower()[:max_length].strip('_')
    
    return cleaned or "unnamed_media"

def _generate_smart_filename(summary: str, mime_type: str) -> str:
    """Generate filename with proper extension based on MIME type."""
    extension_map = {
        'image/jpeg': '.jpg',
        'image/png': '.png', 
        'image/gif': '.gif',
        'image/webp': '.webp',
        'image/bmp': '.bmp'
    }
    
    extension = extension_map.get(mime_type, '.jpg')
    return f"{summary}{extension}"
```

## 📚 Additional Resources

### Official Documentation
- [ADK Python Documentation](https://google.github.io/adk-docs/)
- [ADK Python GitHub](https://github.com/google/adk-python)
- [ADK Samples Repository](https://github.com/google/adk-samples)

### Key Dependencies
```toml
# pyproject.toml
[dependencies]
google-adk = "^1.8.0"
google-genai = "^0.8.0"
vertexai = "^1.70.0"
pydantic = "^2.0.0"
fastapi = "^0.104.0"
uvicorn = "^0.24.0"
```

### CLI Commands
```bash
# Installation
pip install google-adk

# Agent Operations
adk run <agent_path>              # Run agent
adk web <agent_path>              # Web interface
adk eval <agent> <eval_set>       # Evaluation

# Deployment
adk deploy agent_engine           # Deploy to Vertex AI
adk api_server --a2a             # A2A server
```

---

*This template provides a comprehensive foundation for building production-ready AI agents with Google's ADK. Adapt the patterns and examples to your specific use case and requirements.*