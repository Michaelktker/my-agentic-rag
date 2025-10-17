"""
Storage module for fal.ai MCP server.

This module provides tools for uploading files to fal.ai storage.
"""

import os
import mimetypes
import aiofiles
from typing import Dict, Any, Optional
from fastmcp import FastMCP
from .utils import authenticated_request, FalAPIError
from .config import FAL_REST_URL

def register_storage_tools(mcp: FastMCP):
    """Register storage-related tools with the MCP server."""
    
    @mcp.tool()
    async def upload(path: str) -> Dict[str, Any]:
        """
        Upload a file to fal.ai storage.
        
        Args:
            path: The absolute path to the file to upload
            
        Returns:
            Information about the uploaded file, including the file_url
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")
            
        filename = os.path.basename(path)
        file_size = os.path.getsize(path)
        
        content_type = mimetypes.guess_type(path)[0]
        if not content_type:
            content_type = "application/octet-stream"
        
        initiate_url = f"{FAL_REST_URL}/storage/upload/initiate?storage_type=fal-cdn-v3"
        initiate_payload = {
            "content_type": content_type,
            "file_name": filename
        }
        
        try:
            initiate_response = await authenticated_request(
                url=initiate_url, 
                method="POST",
                json_data=initiate_payload
            )
            
            file_url = initiate_response["file_url"]
            upload_url = initiate_response["upload_url"]
            
            async with aiofiles.open(path, "rb") as file:
                file_content = await file.read()
                
                import httpx
                async with httpx.AsyncClient() as client:
                    upload_response = await client.put(
                        upload_url,
                        content=file_content,
                        headers={"Content-Type": content_type}
                    )
                    upload_response.raise_for_status()
            
            return {
                "file_url": file_url,
                "file_name": filename,
                "file_size": file_size,
                "content_type": content_type
            }
            
        except FalAPIError as e:
            raise