"""
Models module for fal.ai MCP server.

This module provides tools for listing, searching,
and retrieving schemas for fal.ai models.
"""

from typing import Optional, Dict, Any, List
from fastmcp import FastMCP
from .utils import public_request
from .config import FAL_BASE_URL

def register_model_tools(mcp: FastMCP):
    """Register model-related tools with the MCP server."""
    
    @mcp.tool()
    async def models(page: Optional[int] = None, total: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        List available models on fal.ai. Ensure to use the total and page arguments. Avoid listing all the models at once.
        
        Args:
            page: The page number of models to retrieve (pagination)
            total: The total number of models to retrieve per page
            
        Returns:
            A list of models with their metadata
        """
        url = f"{FAL_BASE_URL}/models"
        
        params = {}
        if page is not None:
            params["page"] = page
        if total is not None:
            params["total"] = total
        
        if params:
            url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
        
        result = await public_request(url)
        
        return result

    @mcp.tool()
    async def search(keywords: str) -> List[Dict[str, Any]]:
        """
        Search for models on fal.ai based on keywords.
        
        Args:
            keywords: The search terms to find models
            
        Returns:
            A list of models matching the search criteria
        """
        if not isinstance(keywords, str):
            keywords = str(keywords)
        
        url = f"{FAL_BASE_URL}/models?keywords={keywords}"
        
        result = await public_request(url)
        
        return result

    @mcp.tool()
    async def schema(model_id: str) -> Dict[str, Any]:
        """
        Get the OpenAPI schema for a specific model.
        
        Args:
            model_id: The ID of the model (e.g., "fal-ai/flux/dev")
            
        Returns:
            The OpenAPI schema for the model
        """
        if not isinstance(model_id, str):
            model_id = str(model_id)
            
        url = f"{FAL_BASE_URL}/openapi/queue/openapi.json?endpoint_id={model_id}"
        
        return await public_request(url)