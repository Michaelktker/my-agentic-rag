"""
Configuration module for the fal.ai MCP server.

This module provides centralized configuration settings for the fal.ai MCP server, including API endpoints, timeouts, and more.
"""

import os
from typing import Dict, Any, Optional

FAL_BASE_URL = "https://fal.ai/api"
FAL_QUEUE_URL = "https://queue.fal.run"
FAL_DIRECT_URL = "https://fal.run"
FAL_REST_URL = "https://rest.alpha.fal.ai"

DEFAULT_TIMEOUT = 30.0
AUTHENTICATED_TIMEOUT = 100.0

API_KEY_ENV_VAR = "FAL_KEY"

SERVER_NAME = "fal.ai MCP Server"
SERVER_DESCRIPTION = "Access fal.ai models and generate content through MCP"
SERVER_VERSION = "1.0.0"
SERVER_DEPENDENCIES = ["httpx", "aiofiles"]


def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get an environment variable with optional default value.
    
    Args:
        key: The name of the environment variable
        default: Optional default value if not found
        
    Returns:
        The value of the environment variable or the default
    """
    return os.environ.get(key, default)

def get_api_key() -> str:
    """
    Get the fal.ai API key from environment variables.
    
    Returns:
        The API key as a string
        
    Raises:
        ValueError: If the FAL_KEY environment variable is not set
    """
    api_key = get_env(API_KEY_ENV_VAR)
    if not api_key:
        raise ValueError(f"{API_KEY_ENV_VAR} environment variable not set")
    return api_key