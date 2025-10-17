# 🧠 Local MCP Server Setup (mcp-fal) and ADK Agent Integration

This guide explains how to set up the [`mcp-fal`](https://github.com/am0y/mcp-fal) server locally and connect it as an `AgentTool` under your **Google ADK root agent**.  
It is based on the ADK architecture defined in `ADK_Task_Template.md` and follows Google ADK’s best practices.

---

## ⚙️ 1. Clone and Prepare the `mcp-fal` Repository

```bash
git clone https://github.com/am0y/mcp-fal.git
cd mcp-fal
```

> The repository provides a Model Context Protocol (MCP) server that exposes fal.ai’s image/video generation models, schema inspection, and file upload tools.

---

## 🧩 2. Create Virtual Environment and Install Dependencies

```bash
# Create and activate environment
python3 -m venv .venv
source .venv/bin/activate    # (Windows: .venv\Scripts\Activate.ps1)

# Install required libraries
pip install fastmcp httpx aiofiles
```

---

## 🔑 3. Set Your fal.ai API Key

```bash
export FAL_KEY="YOUR_FAL_API_KEY_HERE"
```

- Generate the key from [https://fal.ai/dashboard](https://fal.ai/dashboard).
- Ensure the key has **API** scope.

---

## 🚀 4. Run the MCP Server

You can run `mcp-fal` in two ways:

### Option A – Development Mode (with Inspector)

```bash
fastmcp dev main.py
```

### Option B – Production Mode (for ADK integration)

```bash
python main.py
```

> Running with `python main.py` will launch the server ready for the ADK agent to connect over **stdio**.

**Note:** If you encounter a `TypeError` about unexpected keyword arguments, ensure your `main.py` uses the correct FastMCP initialization:

```python
mcp = FastMCP(
    name=SERVER_NAME,
    instructions=SERVER_DESCRIPTION,
    version=SERVER_VERSION,
    dependencies=SERVER_DEPENDENCIES
)
```

---

## 🧠 5. Configure Google ADK Agent to Use MCP as an AgentTool

### Step 1 – Import Required ADK Classes

```python
from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.mcp_tool import MCPToolset
```

### Step 2 – Define the MCP Toolset for mcp-fal

```python
fal_mcp_toolset = MCPToolset(
    label="fal-mcp",
    transport="stdio",
    command="python",
    args=["main.py"],
    env={"FAL_KEY": "YOUR_FAL_API_KEY_HERE"}
)
```

> The `MCPToolset` connects your ADK agent to the MCP server via **stdio**, launching `python main.py` in a subprocess.

---

### Step 3 – Wrap MCP Toolset as an AgentTool

To make the MCP functions (like `generate`, `search`, `schema`, etc.) callable directly by your root agent, wrap it with `AgentTool`.

```python
fal_agent_tool = AgentTool(agent=fal_mcp_toolset)
```

---

### Step 4 – Register the MCP AgentTool Under the Root Agent

Example of integrating it into your **root ADK agent**:

```python
from google.adk.agents import Agent
from google.adk.planners import BuiltInPlanner

# Root Agent Setup
root_agent = Agent(
    name="root_agent",
    model="gemini-2.5-flash",
    instruction="You are an intelligent assistant that can use fal.ai models via the mcp-fal server.",
    description="Root ADK agent integrating mcp-fal as a toolset",
    planner=BuiltInPlanner(),
    tools=[fal_agent_tool]
)
```

> This allows your ADK root agent to automatically discover and use all tools registered in the `mcp-fal` MCP server (`models`, `search`, `generate`, `upload`, etc.) as native ADK tools.

---

## 🧪 6. Test ADK + MCP Integration

Once connected, try prompting the root agent:

| Example Prompt | ADK → MCP Tool Mapping |
|----------------|------------------------|
| “List available fal.ai models.” | `models(page=1, total=20)` |
| “Search for text-to-video models.” | `search(keywords="video")` |
| “Show the schema for fal-ai/flux/dev.” | `schema(model_id="fal-ai/flux/dev")` |
| “Generate a 768×768 image of a popiah platter.” | `generate(model="fal-ai/flux/dev", parameters={"prompt": "popiah platter"}, queue=False)` |
| “Upload local image for enhancement.” | `upload(path="./image.jpg")` |

---

## 🩺 7. Troubleshooting

| Issue | Resolution |
|-------|-------------|
| **FastMCP TypeError** | If you get `TypeError: FastMCP.__init__() got an unexpected keyword argument 'description'`, update `main.py` to use `name=SERVER_NAME, instructions=SERVER_DESCRIPTION` instead of positional arguments. |
| **Unauthorized / 401** | Ensure `FAL_KEY` is valid and has `API` scope. |
| **No tools listed** | Confirm the ADK toolset is launched with correct `command="python" args=["main.py"]`. |
| **Long job duration** | Use `queue=True` and poll using `status()` → `result()`. |
| **Schema mismatch** | Always call `schema(model_id)` before `generate()` to confirm parameter fields. |
| **Dependencies Warning** | The `dependencies` parameter is deprecated in FastMCP 2.11.4+. This warning can be ignored or migrate to `fastmcp.json` config file. |

---

## 🧱 8. Recommended Project Structure

```
my_adk_project/
├── agents/
│   ├── root_agent/
│   │   └── agent.py
│   └── fal_mcp/
│       └── main.py
├── tools/
│   └── custom_tools.py
├── .env
└── requirements.txt
```

---

## ✅ 9. Final Checklist

- [x] Clone and set up `mcp-fal`.  
- [x] Install dependencies (`fastmcp`, `httpx`, `aiofiles`).  
- [x] Set `FAL_KEY`.  
- [x] Fix FastMCP initialization if needed (use `name=` and `instructions=` parameters).
- [x] Run `python main.py` locally to verify tools list.  
- [x] Define and register `MCPToolset` in ADK code.  
- [x] Wrap the toolset in `AgentTool` and add it to your root agent.  
- [x] Test by prompting the ADK root agent to list or generate using fal.ai models.
- [x] **Production Deployment**: Configure Docker, paths, and environment variables for cloud deployment.

---

## 🚀 Production Deployment Configuration

### Docker Configuration
The production deployment requires proper Docker configuration to include MCP-FAL dependencies:

```dockerfile
# Dockerfile updates for MCP-FAL integration
COPY ./mcp-fal ./mcp-fal

# Install MCP-FAL dependencies
RUN cd mcp-fal && python -m venv .venv && \
    .venv/bin/pip install fastmcp httpx aiofiles
```

### Production Paths
Update agent.py to use container paths instead of development paths:

```python
# Production-ready MCP configuration
fal_mcp_tools = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="/code/mcp-fal/.venv/bin/python",  # Container path
            args=["/code/mcp-fal/main.py"],           # Container path
            env={"FAL_KEY": os.getenv("FAL_KEY", "")}
        )
    )
)
```

### Environment Variables
Ensure FAL_KEY is available in production via Secret Manager:

```bash
# Create production secret
gcloud secrets create fal-api-key \
  --project=production-adk \
  --data-file=-  # Enter your fal.ai API key
```

The Terraform configuration automatically handles:
- Secret creation and IAM permissions
- Cloud Run environment variable injection
- Proper service account access

---

## 🧭 Summary

- `mcp-fal` provides a local MCP server that interfaces with fal.ai.  
- The ADK agent connects to it via `stdio` using `MCPToolset`.  
- Wrapping it in `AgentTool` allows seamless model and generation commands through the root agent.  
- All tools exposed by `mcp-fal` become callable through natural language prompts in your ADK agent.

---

**Author:** Google ADK x fal.ai Integration Setup  
**Last Updated:** 2025-10-17  
**Status:** ✅ Verified Working - FastMCP initialization fix applied
