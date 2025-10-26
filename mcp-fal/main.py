"""
fal.ai MCP Server : Main entry point

This module sets up and runs the fal.ai MCP server,
providing tools to interact with fal.ai models and services.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from fastmcp import FastMCP
from api.models import register_model_tools
from api.generate import register_generation_tools
from api.storage import register_storage_tools
from api.config import get_api_key, SERVER_NAME, SERVER_DESCRIPTION, SERVER_VERSION, SERVER_DEPENDENCIES

# Load environment variables from .env file in the parent directory
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

mcp = FastMCP(
    name=SERVER_NAME,
    instructions=SERVER_DESCRIPTION,
    version=SERVER_VERSION,
    dependencies=SERVER_DEPENDENCIES
)

register_model_tools(mcp)
register_generation_tools(mcp)
register_storage_tools(mcp)

def main():
    try:
        get_api_key()
    except ValueError:
        pass
    
    try:
        mcp.run()
    except Exception as e:
        sys.exit(1)

if __name__ == "__main__":
    main()