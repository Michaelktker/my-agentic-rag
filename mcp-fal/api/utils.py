"""
Utility functions for the fal.ai MCP server.

This module provides helper functions for making API requests
and handling authentication with the fal.ai service.
"""

import httpx
import json
from typing import Optional, Dict, Any, Union
from .config import get_api_key, DEFAULT_TIMEOUT, AUTHENTICATED_TIMEOUT

class FalAPIError(Exception):
    """Exception raised for errors in the fal.ai API responses."""
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        """
        Initialize the exception with error details.
        
        Args:
            message: The error message
            status_code: Optional HTTP status code
            details: Optional error details as a dictionary
        """
        self.status_code = status_code
        self.details = details or {}
        error_msg = message
        if status_code:
            error_msg = f"[{status_code}] {error_msg}"
        super().__init__(error_msg)

async def authenticated_request(
    url: str, 
    method: str = "GET", 
    json_data: Optional[Dict[str, Any]] = None,
    timeout: float = AUTHENTICATED_TIMEOUT
) -> Dict[str, Any]:
    """
    Make an authenticated request to fal.ai API.
    
    Args:
        url: The URL to make the request to
        method: The HTTP method to use (GET, POST, PUT)
        json_data: Optional JSON data to send with the request
        timeout: Request timeout in seconds
        
    Returns:
        The JSON response from the API
        
    Raises:
        FalAPIError: If the API returns an error
        httpx.HTTPStatusError: If the HTTP request fails
    """
    try:
        headers = {"Authorization": f"Key {get_api_key()}"}
        
        async with httpx.AsyncClient() as client:
            if method == "GET":
                response = await client.get(url, headers=headers, timeout=timeout)
            elif method == "POST":
                response = await client.post(url, headers=headers, json=json_data, timeout=timeout)
            elif method == "PUT":
                response = await client.put(url, headers=headers, json=json_data, timeout=timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                try:
                    error_details = json.loads(e.response.text)
                    raise FalAPIError(
                        f"API error: {error_details}",
                        status_code=e.response.status_code,
                        details=error_details
                    )
                except json.JSONDecodeError:
                    raise FalAPIError(
                        f"API error: {e.response.text}",
                        status_code=e.response.status_code
                    )
            
            return response.json()
            
    except httpx.RequestError as e:
        raise FalAPIError(f"Request failed: {str(e)}")

async def public_request(url: str, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """
    Make a non-authenticated request to fal.ai API.
    
    Args:
        url: The URL to make the request to
        timeout: Request timeout in seconds
        
    Returns:
        The JSON response from the API
        
    Raises:
        FalAPIError: If the API returns an error
        httpx.HTTPStatusError: If the HTTP request fails
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=timeout)
            
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                try:
                    error_details = json.loads(e.response.text)
                    raise FalAPIError(
                        f"API error: {error_details}",
                        status_code=e.response.status_code,
                        details=error_details
                    )
                except json.JSONDecodeError:
                    raise FalAPIError(
                        f"API error: {e.response.text}",
                        status_code=e.response.status_code
                    )
            
            return response.json()
            
    except httpx.RequestError as e:
        raise FalAPIError(f"Request failed: {str(e)}")

def sanitize_parameters(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize parameters for API requests.
    
    Args:
        parameters: The parameters to sanitize
        
    Returns:
        Sanitized parameters
    """
    sanitized = parameters.copy()
    sanitized = {k: v for k, v in sanitized.items() if v is not None}
    
    return sanitized