# Google Agent Development Kit (ADK) - Task Template

## 🚀 Overview

Google's Agent Development Kit (ADK) is a flexible, open-source framework for building, evaluating, and deploying sophisticated AI agents. This template provides a comprehensive guide for implementing ADK-based solutions with production-ready patterns and best practices.

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
image_generator = LlmAgent(name="ImageGen", description="Generates images")

# Wrap as tool
image_tool = AgentTool(agent=image_generator)

# Use in parent agent
artist_agent = LlmAgent(
    name="Artist",
    model="gemini-2.5-flash",
    instruction="Create images using the ImageGen tool",
    tools=[image_tool]
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