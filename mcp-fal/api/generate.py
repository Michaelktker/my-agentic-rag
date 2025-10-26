"""
Generate module for fal.ai MCP server.

This module provides tools for generating content
and managing queue operations with fal.ai models.
"""

from typing import Dict, Any, Optional
from fastmcp import FastMCP
from .utils import authenticated_request, sanitize_parameters, FalAPIError
from .config import FAL_QUEUE_URL, FAL_DIRECT_URL

def register_generation_tools(mcp: FastMCP):
    """Register generation-related tools with the MCP server."""
    
    @mcp.tool()
    async def generate(model: str, parameters: Dict[str, Any], queue: bool) -> Dict[str, Any]:
        """
        Generate content using a fal.ai model through the queue system.
        
        Args:
            model: The model ID to use (e.g., "fal-ai/flux/dev")
            parameters: Model-specific parameters as a dictionary
            queue: Whether to use queue system (should be True for long-running operations)
            
        Returns:
            The queued request details with status_url, response_url, etc.
        """
        if not isinstance(model, str):
            model = str(model)
            
        sanitized_parameters = sanitize_parameters(parameters)
        
        try:
            # Always use queue for consistent long-running behavior
            url = f"{FAL_QUEUE_URL}/{model}"
            
            result = await authenticated_request(url, method="POST", json_data=sanitized_parameters)
            
            return result
            
        except FalAPIError as e:
            raise

    # Removed problematic **kwargs functions to fix FastMCP compatibility
    # Users should use the generic generate() function instead

    @mcp.tool()
    async def result(url: str) -> Dict[str, Any]:
        """
        Get the result of a queued request.
        
        Args:
            url: The response_url from a queued request
            
        Returns:
            The generation result
        """
        if not isinstance(url, str):
            url = str(url)
        
        try:
            result = await authenticated_request(url)
            
            return result
            
        except FalAPIError as e:
            raise

    @mcp.tool()
    async def status(url: str) -> Dict[str, Any]:
        """
        Check the status of a queued request.
        
        Args:
            url: The status_url from a queued request
            
        Returns:
            The current status of the queued request
        """
        if not isinstance(url, str):
            url = str(url)
        
        try:
            result = await authenticated_request(url)
            
            return result
            
        except FalAPIError as e:
            raise

    @mcp.tool()
    async def cancel(url: str) -> Dict[str, Any]:
        """
        Cancel a queued request.
        
        Args:
            url: The cancel_url from a queued request
            
        Returns:
            The result of the cancellation attempt
        """
        if not isinstance(url, str):
            url = str(url)
        
        try:
            result = await authenticated_request(url, method="PUT")
            
            return result
            
        except FalAPIError as e:
            raise